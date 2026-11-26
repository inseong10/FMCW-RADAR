// Linux S2a: receive/reassemble -> bounded queue -> FFT/CFAR -> flushed CSV.
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include "stream_protocol.hpp"
#include "stream_pipeline.hpp"
#include "stream_timestamp.hpp"
#include <arpa/inet.h>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <csignal>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <poll.h>
#include <sched.h>
#include <sstream>
#include <sys/socket.h>
#include <thread>
#include <time.h>

using namespace stream128;
static uint64_t ns(clockid_t clock=CLOCK_MONOTONIC) {
    timespec t{}; if(clock_gettime(clock,&t)) throw std::runtime_error("clock_gettime");
    return uint64_t(t.tv_sec)*1000000000ULL+t.tv_nsec;
}
static volatile std::sig_atomic_t interrupted=0;
static void stop(int){interrupted=1;}
struct Options {
    std::string backend="ps",bind="0.0.0.0",out,library,window="hann",input_format="float32";
    uint64_t run=0;
    unsigned frames=0,port=5000,queue=4,partial=4,warmup=10;
    unsigned idle_ms=2000,start_ms=300000;
    bool cpu0=false,diagnose_first=false,measure_plan=false,require_neon=false,diagnostic_spectrum=false;
};
static Options options(int argc,char** argv) {
    Options o;
    for(int i=1;i<argc;++i) {
        std::string k=argv[i];
        if(k=="--cpu0"){o.cpu0=true;continue;}
        if(k=="--diagnose-first-packet"){o.diagnose_first=true;continue;}
        if(k=="--diagnostic-spectrum"){o.diagnostic_spectrum=true;continue;}
        if(k=="--measure-plan"){o.measure_plan=true;continue;}
        if(k=="--require-neon"){o.require_neon=true;continue;}
        if(k=="--help") {
            std::cout<<"--backend ps|pl|model --run-id ID --frames N --out NEW_DIR "
                "[--input-format float32|adc16 --bind IP --port N --window hann|none --queue 4 --partial 4 "
                "--warmup 10 --idle-ms 2000 --start-ms 300000 --fftw-lib PATH --cpu0 "
                "--diagnose-first-packet --diagnostic-spectrum --measure-plan --require-neon]\n";
            std::exit(0);
        }
        if(++i==argc) throw std::runtime_error("Missing option value");
        std::string v=argv[i];
        auto integer=[&](){
            size_t n=0;auto x=std::stoull(v,&n);
            if(n!=v.size() || v[0]=='-')throw std::runtime_error("Invalid integer");
            return x;
        };
        if(k=="--backend")o.backend=v;
        else if(k=="--bind")o.bind=v;
        else if(k=="--out")o.out=v;
        else if(k=="--fftw-lib")o.library=v;
        else if(k=="--window")o.window=v;
        else if(k=="--input-format")o.input_format=v;
        else if(k=="--run-id")o.run=integer();
        else {
            auto x=integer();if(x>1000000)throw std::runtime_error("Option too large");
            if(k=="--frames")o.frames=x;
            else if(k=="--port")o.port=x;
            else if(k=="--queue")o.queue=x;
            else if(k=="--partial")o.partial=x;
            else if(k=="--warmup")o.warmup=x;
            else if(k=="--idle-ms")o.idle_ms=x;
            else if(k=="--start-ms")o.start_ms=x;
            else throw std::runtime_error("Unknown option: "+k);
        }
    }
    if(!o.run || !o.frames || o.frames>100000 || !o.port || o.port>65535 ||
       !o.queue || o.queue>1024 || !o.partial || o.partial>1024 || o.out.empty() ||
       !o.idle_ms || !o.start_ms || (o.window!="hann" && o.window!="none") ||
       (o.input_format!="float32" && o.input_format!="adc16") ||
       (o.input_format=="adc16" && (o.queue!=4 || o.partial!=4)) ||
       (o.diagnostic_spectrum && !o.diagnose_first) ||
       (o.backend!="ps" && (o.measure_plan || o.require_neon)))
        throw std::runtime_error("Invalid arguments; see --help");
    return o;
}
struct Event {
    std::string status="missing";
    uint64_t first=0,kernel=0,complete=0,start=0,prepared=0,fft=0,cfar=0,output=0,sender=0;
    unsigned packets=0,peaks=0,depth=0;
};
struct Socket {
    int fd=-1;
    Socket(){fd=socket(AF_INET,SOCK_DGRAM,0);if(fd<0)throw std::runtime_error("socket");}
    ~Socket(){if(fd>=0)close(fd);}
};
struct Resources {
    uint64_t at=0,cpu=0,total=0,idle=0,rss=0;
    static Resources sample() {
        Resources r;r.at=ns();r.cpu=ns(CLOCK_PROCESS_CPUTIME_ID);
        std::ifstream stat("/proc/stat");std::string name;stat>>name;
        for(int i=0;i<8;++i){uint64_t v=0;stat>>v;r.total+=v;if(i==3 || i==4)r.idle+=v;}
        std::ifstream mem("/proc/self/statm");uint64_t pages=0;mem>>pages>>pages;
        if(!stat || !mem) throw std::runtime_error("Cannot read resource counters");
        r.rss=pages*uint64_t(sysconf(_SC_PAGESIZE));return r;
    }
};
static int run(const Options& o) {
    if(o.cpu0) {cpu_set_t cpus;CPU_ZERO(&cpus);CPU_SET(0,&cpus);
        if(sched_setaffinity(0,sizeof(cpus),&cpus))throw std::runtime_error("CPU0 affinity failed");}
    if(!std::filesystem::create_directory(o.out))throw std::runtime_error("Use a new output directory");
    auto file=[&](const std::string& name){std::ofstream f(o.out+"/"+name);
        f.exceptions(std::ios::failbit|std::ios::badbit);f<<std::setprecision(17);return f;};
    auto detections=file("detections.csv");
    detections<<"run_id,frame_id,doppler_bin,range_bin,power,threshold\n";
    Pipeline pipeline(o.backend,o.window=="hann",o.library,o.measure_plan,o.require_neon);
    if(o.backend=="ps") {auto plan_file=file("fftw_plan.txt");plan_file<<pipeline.fftw_plan()<<'\n';}
    std::array<fft128_sample,16384> zero{};
    std::array<Iq16,16384> adc_zero{};
    for(unsigned i=0;i<o.warmup;++i){
        if(o.input_format=="adc16")pipeline.prepare_adc16(adc_zero.data());
        else pipeline.prepare(zero.data());
        pipeline.transform();pipeline.detect();
    }
    Socket sock;int one=1,requested=4*1024*1024,actual=0;socklen_t size=sizeof(actual);
    if(setsockopt(sock.fd,SOL_SOCKET,SO_TIMESTAMPNS,&one,sizeof(one)) ||
       setsockopt(sock.fd,SOL_SOCKET,SO_RXQ_OVFL,&one,sizeof(one)) ||
       setsockopt(sock.fd,SOL_SOCKET,SO_RCVBUF,&requested,sizeof(requested)))
        throw std::runtime_error("Required socket options failed");
    getsockopt(sock.fd,SOL_SOCKET,SO_RCVBUF,&actual,&size);
    sockaddr_in address{};address.sin_family=AF_INET;address.sin_port=htons(o.port);
    if(inet_pton(AF_INET,o.bind.c_str(),&address.sin_addr)!=1 ||
       bind(sock.fd,reinterpret_cast<sockaddr*>(&address),sizeof(address)))
        throw std::runtime_error("UDP bind failed");
    auto environment=file("environment.txt");
    environment<<"backend="<<o.backend<<"\nhardware="<<(o.backend=="pl")
        <<"\nwindow="<<o.window<<"\ninput_format="<<o.input_format
        <<"\nprotocol_version="<<(o.input_format=="adc16"?3:2)
        <<"\nadc_profile="<<(o.input_format=="adc16"?adc_profile_id:0)
        <<"\nadc_bits="<<(o.input_format=="adc16"?adc_bits:0)
        <<"\nadc_scale="<<(o.input_format=="adc16"?adc_scale:0)
        <<"\nrun_id="<<o.run<<"\nframes="<<o.frames
        <<"\ncpu0="<<o.cpu0<<"\nqueue="<<o.queue<<"\npartial="<<o.partial
        <<"\nsocket_rcvbuf="<<actual<<"\nwarmup="<<o.warmup
        <<"\ntime_t_bytes="<<sizeof(time_t)<<"\ntimespec_bytes="<<sizeof(timespec)
        <<"\ncontrol_capacity="<<control_capacity<<"\ndiagnostic_probe="<<o.diagnose_first
        <<"\ndiagnostic_spectrum="<<o.diagnostic_spectrum
        <<"\nps_precision="<<fft_precision<<"\nps_plan="<<(o.measure_plan?"MEASURE":"ESTIMATE")
        <<"\nps_neon_plan="<<pipeline.uses_neon()<<"\nrequire_neon="<<o.require_neon
        <<"\nPS=FFTW 2D single worker; PL=E14 ABI8; model=software only"
        <<"\noutput=per-frame detections CSV flush (no fsync)"
        <<"\nsender_ns=opaque remote monotonic timestamp; never subtracted\n";
    environment.close();
    std::vector<Event> events(o.frames+1);
    std::vector<fft128_sample> first_spectrum;
    uint64_t first_spectrum_id=0;
    std::map<uint64_t,std::unique_ptr<Frame>> partial;
    std::deque<std::unique_ptr<Frame>> queue;
    std::mutex lock;std::condition_variable cv;
    bool done=false,failed=false;
    std::string error;
    std::atomic<bool> sample_done{false};
    auto resources=file("resources.csv");
    resources<<"start_ns,end_ns,process_cpu_pct_one_core,system_cpu_pct,rss_bytes\n";
    // Resource collection errors invalidate the run, just like worker errors.
    auto failure=[&](const std::string& message){std::lock_guard<std::mutex> guard(lock);
        failed=true;error=message;cv.notify_all();};
    std::thread sampler([&]{try {
        Resources prev=Resources::sample();
        while(!sample_done) {
            std::unique_lock<std::mutex> guard(lock);
            cv.wait_for(guard,std::chrono::milliseconds(200),[&]{return sample_done.load();});guard.unlock();
            auto now=Resources::sample();
            double pc=100.0*(now.cpu-prev.cpu)/double(now.at-prev.at);
            double system=now.total>prev.total ?
                100.0*(1-double(now.idle-prev.idle)/double(now.total-prev.total)):0;
            resources<<prev.at<<','<<now.at<<','<<pc<<','<<system<<','<<now.rss<<'\n';prev=now;
        }
        resources.close();
    } catch(const std::exception& e){failure(e.what());}});
    std::thread worker([&]{try {
        while(true) {
            std::unique_ptr<Frame> f;Event e;
            {
                std::unique_lock<std::mutex> guard(lock);
                cv.wait(guard,[&]{return done || failed || !queue.empty();});
                if(failed || (queue.empty() && done))break;
                f=std::move(queue.front());queue.pop_front();e=events[f->id];
            }
            e.start=ns();
            if(f->format==InputFormat::Adc16)pipeline.prepare_adc16(f->adc_iq.data());
            else pipeline.prepare(f->iq.data());
            e.prepared=ns();
            pipeline.transform();e.fft=ns();const auto& peaks=pipeline.detect();e.cfar=ns();
            e.peaks=static_cast<unsigned>(peaks.size());
            // A sentinel records an output even when there are no detections.
            if(peaks.empty())detections<<o.run<<','<<f->id<<",-1,-1,0,0\n";
            for(const auto& p:peaks)detections<<o.run<<','<<f->id<<','<<p.doppler<<','<<p.range
                <<','<<p.power<<','<<p.threshold<<'\n';
            detections.flush();e.output=ns();e.status="processed";
            // Diagnostic runs only: capture after the measured output timestamp.
            // This extra work can delay later frames, so never use for acceptance.
            if(o.diagnostic_spectrum && first_spectrum.empty()) {
                first_spectrum.resize(16384);first_spectrum_id=f->id;
                for(size_t i=0;i<16384;++i)first_spectrum[i]=pipeline.spectrum_at(i);
            }
            std::lock_guard<std::mutex> guard(lock);events[f->id]=std::move(e);
        }
    } catch(const std::exception& e){failure(e.what());}});
    uint64_t invalid=0,foreign=0,duplicates=0,metadata_errors=0,late=0,kernel_missing=0,clock_errors=0;
    uint64_t finalized=0,last_packet=0,start=ns(),kernel_drops=0;
    uint64_t received_packets=0,payload_truncated=0,control_truncated=0,decode_errors=0;
    bool probed=false;
    int64_t clock_offset=0;bool calibrated=false;
    std::cout<<"S2A_READY backend="<<o.backend<<" run_id="<<o.run<<" port="<<o.port<<std::endl;
    try {
        while(!interrupted && finalized<o.frames) {
            {std::lock_guard<std::mutex> guard(lock);if(failed)break;}
            uint64_t now=ns();
            if((!last_packet && now-start>uint64_t(o.start_ms)*1000000) ||
               (last_packet && now-last_packet>uint64_t(o.idle_ms)*1000000))break;
            pollfd wait{sock.fd,POLLIN,0};int ready=poll(&wait,1,100);
            if(ready<0){if(errno==EINTR)continue;throw std::runtime_error("poll failed");}
            if(!ready)continue;
            if(o.diagnose_first && !probed) {
                // Observe the original ARM32 failure without consuming a packet.
                std::array<unsigned char,packet_bytes+1> probe_bytes{};
                alignas(cmsghdr) unsigned char old_control[CMSG_SPACE(sizeof(timespec))+CMSG_SPACE(sizeof(uint32_t))]{};
                iovec probe_io{probe_bytes.data(),probe_bytes.size()};msghdr probe{};
                probe.msg_iov=&probe_io;probe.msg_iovlen=1;probe.msg_control=old_control;
                probe.msg_controllen=sizeof(old_control);
                ssize_t count=recvmsg(sock.fd,&probe,MSG_PEEK|MSG_DONTWAIT);
                if(count>=0) {
                    std::cout<<"S2A_LEGACY_PROBE bytes="<<count<<" flags="<<probe.msg_flags
                        <<" payload_truncated="<<bool(probe.msg_flags&MSG_TRUNC)
                        <<" control_truncated="<<bool(probe.msg_flags&MSG_CTRUNC)
                        <<" capacity="<<sizeof(old_control)<<" controllen="<<probe.msg_controllen<<std::endl;
                    probed=true;
                }
            }
            std::array<unsigned char,packet_bytes+1> bytes{};
            alignas(cmsghdr) unsigned char control[control_capacity]{};
            iovec io{bytes.data(),bytes.size()};msghdr message{};
            message.msg_iov=&io;message.msg_iovlen=1;message.msg_control=control;message.msg_controllen=sizeof(control);
            ssize_t n=recvmsg(sock.fd,&message,0);uint64_t received=ns();
            if(n<0){if(errno==EINTR)continue;throw std::runtime_error("recvmsg failed");}
            ++received_packets;last_packet=received;
            if(o.diagnose_first && received_packets==1) {
                std::cout<<"S2A_FIRST_PACKET bytes="<<n<<" flags="<<message.msg_flags
                    <<" controllen="<<message.msg_controllen<<" cmsg=";
                for(auto c=CMSG_FIRSTHDR(&message);c;c=CMSG_NXTHDR(&message,c))
                    std::cout<<c->cmsg_level<<':'<<c->cmsg_type<<':'<<c->cmsg_len<<';';
                std::cout<<std::endl;
            }
            if(message.msg_flags&(MSG_TRUNC|MSG_CTRUNC)) {
                ++invalid;
                if(message.msg_flags&MSG_TRUNC)++payload_truncated;
                if(message.msg_flags&MSG_CTRUNC)++control_truncated;
                if(invalid==1)std::cerr<<"S2A_REJECT truncated payload="<<payload_truncated
                    <<" control="<<control_truncated<<std::endl;
                continue;
            }
            Packet p;
            try {p=decode(bytes.data(),static_cast<size_t>(n));}
            catch(const std::exception& e){++invalid;++decode_errors;
                if(decode_errors==1)std::cerr<<"S2A_REJECT decode bytes="<<n<<" reason="<<e.what()<<std::endl;
                continue;
            }
            if(p.run!=o.run || p.id>o.frames){++foreign;continue;}
            if((p.format==InputFormat::Adc16)!=(o.input_format=="adc16")) {
                ++invalid;++decode_errors;continue;
            }
            if(o.diagnose_first && !calibrated)
                std::cout<<"S2A_FIRST_VALID run_id="<<p.run<<" frame_id="<<p.id<<std::endl;
            uint64_t kernel_real=0;
            for(auto c=CMSG_FIRSTHDR(&message);c;c=CMSG_NXTHDR(&message,c)) {
                bool timestamp_type=c->cmsg_type==SCM_TIMESTAMPNS;
#ifdef SO_TIMESTAMPNS_OLD
                timestamp_type=timestamp_type || c->cmsg_type==SO_TIMESTAMPNS_OLD;
#endif
#ifdef SO_TIMESTAMPNS_NEW
                timestamp_type=timestamp_type || c->cmsg_type==SO_TIMESTAMPNS_NEW;
#endif
                if(c->cmsg_level==SOL_SOCKET && timestamp_type && c->cmsg_len>=CMSG_LEN(0)) {
                    try {kernel_real=socket_timestamp_ns(CMSG_DATA(c),c->cmsg_len-CMSG_LEN(0));}
                    catch(const std::exception&){kernel_real=0;}
                }
                if(c->cmsg_level==SOL_SOCKET && c->cmsg_type==SO_RXQ_OVFL &&
                   c->cmsg_len>=CMSG_LEN(sizeof(uint32_t))) {
                    uint32_t count=0;std::memcpy(&count,CMSG_DATA(c),sizeof(count));kernel_drops=count;
                }
            }
            uint64_t before=ns(),real=ns(CLOCK_REALTIME),after=ns();
            int64_t offset=static_cast<int64_t>(real)-static_cast<int64_t>(before+(after-before)/2);
            if(!calibrated){clock_offset=offset;calibrated=true;}
            if(std::llabs(offset-clock_offset)>2000000)++clock_errors;
            uint64_t kernel=0;
            if(kernel_real && static_cast<int64_t>(kernel_real)>offset) {
                kernel=static_cast<uint64_t>(static_cast<int64_t>(kernel_real)-offset);
                if(kernel>received+1000000){kernel=0;++clock_errors;}
            } else ++kernel_missing;
            std::lock_guard<std::mutex> guard(lock);
            auto& event=events[p.id];
            if(event.status!="missing" && event.status!="partial"){++late;continue;}
            auto found=partial.find(p.id);
            if(found==partial.end()) {
                if(partial.size()==o.partial) {
                    auto oldest=partial.begin();events[oldest->first].status="partial_evicted";
                    partial.erase(oldest);++finalized;
                }
                auto f=std::make_unique<Frame>();f->id=p.id;f->first_ns=received;f->first_kernel_ns=kernel;
                found=partial.emplace(p.id,std::move(f)).first;
                event.status="partial";event.first=received;event.kernel=kernel;event.sender=p.sender_ns;
            }
            bool added=false;
            try {added=found->second->add(p);}catch(const std::exception&){++metadata_errors;continue;}
            if(!added){++duplicates;continue;}
            event.packets=found->second->count;
            if(event.packets==128) {
                event.complete=ns();found->second->complete_ns=event.complete;
                event.depth=static_cast<unsigned>(queue.size());
                if(queue.size()==o.queue)event.status="queue_full";
                else {event.status="queued";queue.push_back(std::move(found->second));cv.notify_all();}
                partial.erase(found);++finalized;
            }
        }
    } catch(const std::exception& e){failure(e.what());}
    {std::lock_guard<std::mutex> guard(lock);done=true;cv.notify_all();}
    worker.join();sample_done=true;cv.notify_all();sampler.join();detections.close();
    if(!first_spectrum.empty()) {
        auto diagnostic=file("diagnostic_spectrum.csv");
        diagnostic<<"frame_id,doppler,range,real,imag\n";
        for(size_t i=0;i<16384;++i)diagnostic<<first_spectrum_id<<','<<i/128<<','<<i%128
            <<','<<first_spectrum[i].real<<','<<first_spectrum[i].imag<<'\n';
    }
    auto frames=file("frames.csv");
    frames<<"frame_id,status,packets,first_rx_ns,first_kernel_ns,complete_ns,process_start_ns,prepared_ns,fft_done_ns,cfar_done_ns,output_done_ns,sender_ns,queue_depth,peaks\n";
    unsigned processed=0;
    for(unsigned id=1;id<=o.frames;++id){auto& e=events[id];if(e.status=="processed")++processed;
        frames<<id<<','<<e.status<<','<<e.packets<<','<<e.first<<','<<e.kernel<<','<<e.complete<<','
            <<e.start<<','<<e.prepared<<','<<e.fft<<','<<e.cfar<<','<<e.output<<','<<e.sender<<','<<e.depth<<','<<e.peaks<<'\n';}
    frames.close();auto counters=file("counters.txt");
    counters<<"invalid="<<invalid<<"\nforeign="<<foreign<<"\nduplicates="<<duplicates<<"\nlate="<<late
        <<"\nreceived_packets="<<received_packets<<"\npayload_truncated="<<payload_truncated
        <<"\ncontrol_truncated="<<control_truncated<<"\ndecode_errors="<<decode_errors
        <<"\nmetadata_errors="<<metadata_errors<<"\nkernel_drops="<<kernel_drops
        <<"\nkernel_missing="<<kernel_missing<<"\nclock_errors="<<clock_errors
        <<"\ninterrupted="<<interrupted<<"\nfailed="<<failed<<"\nerror="<<error<<'\n';
    counters.close();
    std::cout<<"S2A_RECORDED processed="<<processed<<" expected="<<o.frames<<std::endl;
    return failed || interrupted || processed!=o.frames || invalid || metadata_errors || kernel_missing || clock_errors || kernel_drops ? 2:0;
}
int main(int argc,char** argv){try {
    std::signal(SIGINT,stop);std::signal(SIGTERM,stop);return run(options(argc,argv));
}catch(const std::exception& e){std::cerr<<"S2A_ERROR "<<e.what()<<'\n';return 1;}}
