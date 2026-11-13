// C++17, Linux/macOS. FFTW3 double-precision runtime is loaded dynamically.
// No FFTW headers are required. Public FFTW3 C ABI declarations below.
#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <poll.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

using Steady = std::chrono::steady_clock;
using Complex = std::complex<double>;
constexpr double PI = 3.14159265358979323846;
constexpr double C = 299792458.0;
constexpr int DOPPLER_TILE = 32;
struct fftw_plan_s;
using Plan = fftw_plan_s*;
using FComplex = double[2];

struct FFTW {
    void* lib = nullptr;
    void* (*alloc)(size_t) = nullptr;
    void (*release)(void*) = nullptr;
    Plan (*plan_many)(int,const int*,int,FComplex*,const int*,int,int,
                      FComplex*,const int*,int,int,int,unsigned) = nullptr;
    void (*execute)(Plan) = nullptr;
    void (*destroy)(Plan) = nullptr;
    void (*print_plan)(Plan) = nullptr;
    int (*import_wisdom)(const char*) = nullptr;
    int (*export_wisdom)(const char*) = nullptr;
    template<class T> void symbol(T& target, const char* name) {
        target = reinterpret_cast<T>(dlsym(lib, name));
        if (!target) throw std::runtime_error(std::string("Missing FFTW symbol: ")+name);
    }
    explicit FFTW(const std::string& path) {
        const char* paths[] = {"libfftw3.so.3", "libfftw3.dylib",
            "/opt/homebrew/lib/libfftw3.dylib", "/usr/local/lib/libfftw3.dylib"};
        if (!path.empty()) lib = dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
        else for (auto p : paths) { lib = dlopen(p, RTLD_NOW | RTLD_LOCAL); if (lib) break; }
        if (!lib) throw std::runtime_error("Cannot load FFTW3. Install FFTW or use --fftw-lib PATH.");
        try {
            symbol(alloc,"fftw_malloc"); symbol(release,"fftw_free");
            symbol(plan_many,"fftw_plan_many_dft"); symbol(execute,"fftw_execute");
            symbol(destroy,"fftw_destroy_plan");
            symbol(print_plan,"fftw_print_plan");
            symbol(import_wisdom,"fftw_import_wisdom_from_filename");
            symbol(export_wisdom,"fftw_export_wisdom_to_filename");
        } catch (...) { dlclose(lib); lib=nullptr; throw; }
    }
    ~FFTW() { if(lib) dlclose(lib); }
    FFTW(const FFTW&)=delete; FFTW& operator=(const FFTW&)=delete;
};
struct Buffer {
    FFTW& api; FComplex* p;
    Buffer(FFTW& a,size_t n): api(a),p(static_cast<FComplex*>(a.alloc(n*sizeof(FComplex)))) {
        if(!p) throw std::bad_alloc();
        std::memset(p,0,n*sizeof(FComplex));
    }
    ~Buffer(){api.release(p);}
    Buffer(const Buffer&)=delete; Buffer& operator=(const Buffer&)=delete;
};
struct Plans {
    FFTW& api; Plan range=nullptr,doppler=nullptr; bool from_wisdom=false;
    Plans(FFTW& a,int pulses,int samples,FComplex* input,FComplex* r,
          FComplex* d,FComplex* out,bool measure,bool wisdom):api(a) {
        // FFTW_FORWARD=-1, FFTW_MEASURE=0, FFTW_ESTIMATE=1U<<6, FFTW_WISDOM_ONLY=1U<<21.
        unsigned flags=measure?0U:64U;
        auto make_range=[&](unsigned fl){return a.plan_many(1,&samples,pulses,input,nullptr,1,samples,
                                                            r,nullptr,1,samples,-1,fl);};
        // Doppler buffers are transposed: each FFT input/output column is contiguous.
        auto make_doppler=[&](unsigned fl){return a.plan_many(1,&pulses,samples,d,nullptr,1,pulses,
                                                              out,nullptr,1,pulses,-1,fl);};
        if(wisdom) {
            range=make_range(1U<<21);doppler=make_doppler(1U<<21);
            from_wisdom=range && doppler;
        }
        if(!range) range=make_range(flags);
        if(!doppler) doppler=make_doppler(flags);
        if(!range || !doppler) {
            if(range) a.destroy(range);
            if(doppler) a.destroy(doppler);
            throw std::runtime_error("FFTW plan creation failed");
        }
    }
    ~Plans(){api.destroy(range);api.destroy(doppler);}
    Plans(const Plans&)=delete; Plans& operator=(const Plans&)=delete;
};

struct Options {
    std::string bind="0.0.0.0",source,output,fftw_lib,window="hann",input,timings,wisdom_in,wisdom_out;
    int port=5000,channel=0,warmup=5,repeat=1;
    double timeout=15,max_frame_mb=128,bandwidth=100,chirp=80,prp=100,fc=24.05;
    bool thread_cpu=false,measure_plan=false;
};
long integer(const std::string& s) {
    size_t n; long v=std::stol(s,&n);
    if(n!=s.size()) throw std::runtime_error("Invalid integer: "+s);
    return v;
}
double positive(const std::string& s) {
    size_t n; double v=std::stod(s,&n);
    if(n!=s.size() || !std::isfinite(v) || v<=0) throw std::runtime_error("Invalid positive value: "+s);
    return v;
}
Options parse(int argc,char** argv) {
    Options o;
    for(int i=1;i<argc;++i) {
        std::string k=argv[i];
        if(k=="--help") {
            std::cout << "UDP RSPY receiver, one channel/frame, C++17 + FFTW3\n"
            "--bind IP --port 5000 --channel 0 --source-ip IP --timeout 15\n"
            "--warmup 5 --repeat 1 --window hann|none --max-frame-mb 128\n"
            "--bandwidth-mhz 100 --chirp-us 80 --prp-us 100 --fc-ghz 24.05\n"
            "--output spectrum.csv --thread-cpu --measure-plan --fftw-lib PATH\n"
            "--input frame.bin --timings timings.csv (offline replay)\n"
            "--wisdom-in plan.wis --wisdom-out plan.wis\n";
            std::exit(0);
        }
        if(k=="--thread-cpu") {o.thread_cpu=true;continue;}
        if(k=="--measure-plan") {o.measure_plan=true;continue;}
        if(i+1>=argc) throw std::runtime_error("Missing value for "+k);
        std::string v=argv[++i];
        auto bounded=[&](long low,long high) {long x=integer(v); if(x<low || x>high) throw std::runtime_error("Out of range: "+k);return int(x);};
        if(k=="--bind") o.bind=v;
        else if(k=="--source-ip") o.source=v;
        else if(k=="--port") o.port=bounded(1,65535);
        else if(k=="--channel") o.channel=bounded(0,65535);
        else if(k=="--warmup") o.warmup=bounded(0,100000);
        else if(k=="--repeat") o.repeat=bounded(1,1000000);
        else if(k=="--timeout") o.timeout=positive(v);
        else if(k=="--max-frame-mb") o.max_frame_mb=positive(v);
        else if(k=="--bandwidth-mhz") o.bandwidth=positive(v);
        else if(k=="--chirp-us") o.chirp=positive(v);
        else if(k=="--prp-us") o.prp=positive(v);
        else if(k=="--fc-ghz") o.fc=positive(v);
        else if(k=="--window") o.window=v;
        else if(k=="--output") o.output=v;
        else if(k=="--fftw-lib") o.fftw_lib=v;
        else if(k=="--input") o.input=v;
        else if(k=="--timings") o.timings=v;
        else if(k=="--wisdom-in") o.wisdom_in=v;
        else if(k=="--wisdom-out") o.wisdom_out=v;
        else throw std::runtime_error("Unknown option: "+k);
    }
    if(o.window!="hann" && o.window!="none") throw std::runtime_error("window must be hann or none");
    return o;
}

struct Record { double wall=0,cpu=0; size_t calls=0; std::vector<std::pair<double,double>> samples; };
struct Profiler {
    clockid_t clock; std::map<std::string,Record> rows;
    explicit Profiler(bool thread):clock(thread?CLOCK_THREAD_CPUTIME_ID:CLOCK_PROCESS_CPUTIME_ID){}
    double cpu_now() const {
        timespec t{};
        if(clock_gettime(clock,&t)!=0) throw std::runtime_error("CPU clock unavailable");
        return double(t.tv_sec)*1e3+double(t.tv_nsec)/1e6;
    }
    template<class F> void run(const std::string& name,F f) {
        auto& r=rows[name]; // map allocations excluded from the inner interval
        auto w=Steady::now(); double c=cpu_now();
        f();
        double dc=cpu_now()-c;
        double dw=std::chrono::duration<double,std::milli>(Steady::now()-w).count();
        r.wall+=dw;r.cpu+=dc;++r.calls;r.samples.emplace_back(dw,dc);
    }
    void report(const std::vector<std::string>& names) const {
        std::cout<<std::left<<std::setw(23)<<"Stage"<<std::right
                 <<std::setw(15)<<"Wall avg(ms)"<<std::setw(15)<<"CPU avg(ms)"
                 <<std::setw(11)<<"CPU(%)"<<std::setw(10)<<"Calls"<<'\n';
        for(const auto& name:names) {
            auto it=rows.find(name);if(it==rows.end()) continue;
            auto r=it->second;
            std::cout<<std::left<<std::setw(23)<<name<<std::right
                     <<std::setw(15)<<r.wall/r.calls<<std::setw(15)<<r.cpu/r.calls
                     <<std::setw(11)<<(r.wall?100*r.cpu/r.wall:0)
                     <<std::setw(10)<<r.calls<<'\n';
        }
    }
};
uint64_t be(const unsigned char* p,int n) {
    uint64_t x=0;for(int i=0;i<n;++i)x=(x<<8)|p[i];return x;
}
float read_float(const unsigned char* p) {
    uint32_t u=static_cast<uint32_t>(be(p,4));float v;std::memcpy(&v,&u,4);return v;
}
double read_double(const unsigned char* p) {
    uint64_t u=be(p,8);double v;std::memcpy(&v,&u,8);return v;
}
struct Header {int channel;uint32_t index,pulses,samples;double fs;};
bool header(const unsigned char* p,size_t len,Header& h) {
    if(len<28 || std::memcmp(p,"RSPY",4) || p[4]!=1 || p[5]!=1) return false;
    h={int(be(p+6,2)),uint32_t(be(p+8,4)),uint32_t(be(p+12,4)),
       uint32_t(be(p+16,4)),read_double(p+20)};
    return h.pulses>0 && h.pulses<=100000 && h.samples>0 && h.samples<=8184
        && h.index<h.pulses && std::isfinite(h.fs) && h.fs>0
        && len==28+size_t(h.samples)*8;
}
struct Socket {int fd; Socket():fd(socket(AF_INET,SOCK_DGRAM,0)){if(fd<0)throw std::runtime_error("socket failed");}~Socket(){close(fd);}};
struct Frame {int pulses=0,samples=0;double fs=0;std::vector<Complex> data;};
Frame receive(const Options& o,Profiler& prof) {
    Socket sock;
    int capacity=4*1024*1024;
    setsockopt(sock.fd,SOL_SOCKET,SO_RCVBUF,&capacity,sizeof(capacity));
    sockaddr_in local{};local.sin_family=AF_INET;local.sin_port=htons(uint16_t(o.port));
    if(inet_pton(AF_INET,o.bind.c_str(),&local.sin_addr)!=1) throw std::runtime_error("Invalid bind IPv4");
    in_addr source{};
    if(!o.source.empty() && inet_pton(AF_INET,o.source.c_str(),&source)!=1) throw std::runtime_error("Invalid source IPv4");
    if(bind(sock.fd,reinterpret_cast<sockaddr*>(&local),sizeof(local))) throw std::runtime_error(std::string("bind: ")+strerror(errno));
    std::cout<<"Listening on "<<o.bind<<':'<<o.port<<", channel="<<o.channel<<std::endl;
    Frame frame;std::vector<bool> seen;std::vector<Complex> decoded;
    sockaddr_in peer{};size_t count=0,duplicates=0,invalid=0,ignored=0;
    Steady::time_point first{},last{};
    auto deadline=Steady::now()+std::chrono::duration<double>(o.timeout);
    auto timeout=[&](){
        std::string text="Incomplete frame: received "+std::to_string(count);
        if(!seen.empty()) {text+="/"+std::to_string(frame.pulses)+"; first missing indices:";int n=0;
            for(size_t i=0;i<seen.size() && n<20;++i)if(!seen[i]){text+=' '+std::to_string(i);++n;}}
        throw std::runtime_error(text);
    };
    prof.run("receive_total",[&]{
        while(true) {
            double remaining=std::chrono::duration<double>(deadline-Steady::now()).count();
            if(remaining<=0) timeout();
            int ms=int(std::min(remaining*1000.0+1.0,1000.0));
            std::array<unsigned char,65536> packet;
            sockaddr_in address{};socklen_t addrlen=sizeof(address);ssize_t length=-1;
            int ready=0;
            prof.run("socket_wait",[&]{
                pollfd poller{sock.fd,POLLIN,0};ready=poll(&poller,1,ms);
                if(ready>0 && (poller.revents&POLLIN))
                    length=recvfrom(sock.fd,packet.data(),packet.size(),0,reinterpret_cast<sockaddr*>(&address),&addrlen);
                else if(ready>0) throw std::runtime_error("Socket poll error");
            });
            auto arrival=Steady::now();
            if(ready<0){if(errno==EINTR)continue;throw std::runtime_error("poll failed");}
            if(!ready) continue;
            if(length<0){if(errno==EINTR)continue;throw std::runtime_error("recvfrom failed");}
            if((!o.source.empty() && address.sin_addr.s_addr!=source.s_addr)
               || (count && (address.sin_addr.s_addr!=peer.sin_addr.s_addr || address.sin_port!=peer.sin_port))) {++ignored;continue;}
            Header h{};bool valid=false;
            prof.run("decode",[&]{
                valid=header(packet.data(),size_t(length),h);
                if(!valid || h.channel!=o.channel) return;
                decoded.resize(h.samples);
                for(size_t i=0;i<h.samples;++i) {
                    float re=read_float(packet.data()+28+i*8),im=read_float(packet.data()+32+i*8);
                    if(!std::isfinite(re)||!std::isfinite(im)){valid=false;return;}
                    decoded[i]=Complex(re,im);
                }
            });
            if(!valid){++invalid;continue;}
            if(h.channel!=o.channel){++ignored;continue;}
            prof.run("reassembly",[&]{
                if(!count) {
                    size_t n=size_t(h.pulses)*h.samples;
                    if(double(n)*sizeof(Complex)>o.max_frame_mb*1024*1024) throw std::runtime_error("Frame exceeds --max-frame-mb");
                    frame.pulses=int(h.pulses);frame.samples=int(h.samples);frame.fs=h.fs;
                    frame.data.resize(n);seen.resize(h.pulses,false);peer=address;first=arrival;
                }
                if(frame.pulses!=int(h.pulses)||frame.samples!=int(h.samples)||frame.fs!=h.fs)
                    throw std::runtime_error("Metadata changed: restart sender and receiver");
                if(seen[h.index]){++duplicates;return;}
                std::copy(decoded.begin(),decoded.end(),frame.data.begin()+size_t(h.index)*h.samples);
                seen[h.index]=true;++count;last=arrival;
            });
            if(count==size_t(frame.pulses)) break;
        }
    });
    char ip[INET_ADDRSTRLEN];inet_ntop(AF_INET,&peer.sin_addr,ip,sizeof(ip));
    std::cout<<"Sender: "<<ip<<':'<<ntohs(peer.sin_port)<<"\nFrame: ("<<frame.pulses<<", "<<frame.samples<<"), fs="<<frame.fs<<" Hz\n"
             <<"duplicates="<<duplicates<<", invalid="<<invalid<<", ignored="<<ignored<<"\n"
             <<"First-to-last packet: "<<std::chrono::duration<double,std::milli>(last-first).count()<<" ms\n";
    return frame;
}

// Disk I/O is outside profiling. Container: RSPB0001, then BE u32 length + UDP packet.
using Packets=std::vector<std::vector<unsigned char>>;
Packets read_packets(const Options& o) {
    std::ifstream in(o.input,std::ios::binary);
    char magic[8];
    if(!in.read(magic,8) || std::memcmp(magic,"RSPB0001",8))
        throw std::runtime_error("Invalid packet file magic");
    Packets packets; size_t total=0;
    while(in.peek()!=std::char_traits<char>::eof()) {
        unsigned char bytes[4];
        if(!in.read(reinterpret_cast<char*>(bytes),4)) throw std::runtime_error("Truncated packet length");
        size_t size=be(bytes,4);
        if(size<28 || size>65535) throw std::runtime_error("Invalid packet length");
        total+=size;
        if(total>o.max_frame_mb*1024*1024 || packets.size()>=100000)
            throw std::runtime_error("Packet file exceeds memory limit");
        packets.emplace_back(size);
        if(!in.read(reinterpret_cast<char*>(packets.back().data()),size)) throw std::runtime_error("Truncated packet");
    }
    if(packets.empty()) throw std::runtime_error("Empty packet file");
    return packets;
}
Frame replay(const Packets& packets,const Options& o,Profiler& prof) {
    Frame f;
    std::vector<Header> headers(packets.size());
    std::vector<std::vector<Complex>> decoded(packets.size());
    prof.run("decode",[&]{
        for(size_t k=0;k<packets.size();++k) {
            const auto& p=packets[k]; auto& h=headers[k];
            if(!header(p.data(),p.size(),h) || h.channel!=o.channel)
                throw std::runtime_error("Invalid packet/channel");
            decoded[k].resize(h.samples);
            for(size_t i=0;i<h.samples;++i) {
                float re=read_float(p.data()+28+i*8),im=read_float(p.data()+32+i*8);
                if(!std::isfinite(re)||!std::isfinite(im)) throw std::runtime_error("Nonfinite IQ");
                decoded[k][i]=Complex(re,im);
            }
        }
    });
    prof.run("reassembly",[&]{
        const auto& first=headers.front();
        size_t n=size_t(first.pulses)*first.samples;
        if(n*sizeof(Complex)>o.max_frame_mb*1024*1024) throw std::runtime_error("Frame exceeds memory limit");
        f.pulses=first.pulses;f.samples=first.samples;f.fs=first.fs;f.data.resize(n);
        std::vector<bool> seen(f.pulses,false);
        for(size_t k=0;k<headers.size();++k) {
            auto h=headers[k];
            if(h.pulses!=first.pulses || h.samples!=first.samples || h.fs!=f.fs || seen[h.index])
                throw std::runtime_error("Inconsistent/duplicate packet");
            std::copy(decoded[k].begin(),decoded[k].end(),f.data.begin()+size_t(h.index)*h.samples);
            seen[h.index]=true;
        }
        if(std::find(seen.begin(),seen.end(),false)!=seen.end()) throw std::runtime_error("Missing chirp");
    });
    return f;
}
void save_timings(const Options& o,const Profiler& prof) {
    if(o.timings.empty()) return;
    std::ofstream out(o.timings);
    if(!out) throw std::runtime_error("Cannot open timing CSV");
    out<<"stage,iteration,wall_ms,cpu_ms\n"<<std::setprecision(17);
    for(const auto& item:prof.rows) {
        for(size_t i=0;i<item.second.samples.size();++i) {
            auto t=item.second.samples[i];
            out<<item.first<<','<<i+1<<','<<t.first<<','<<t.second<<'\n';
        }
    }
    if(!out) throw std::runtime_error("Failed writing timing CSV");
}

int signed_bin(int k,int n){return k<=(n-1)/2?k:k-n;}
std::vector<double> window(int n,bool hann) {
    if(hann && n<3)throw std::runtime_error("Hann requires >=3 samples/chirps; use --window none");
    std::vector<double> w(n,1.0);
    if(hann)for(int i=0;i<n;++i)w[i]=0.5-0.5*std::cos(2*PI*i/(n-1));
    return w;
}
void process(const Frame& f,const Options& o,Profiler& prof,FFTW& api) {
    size_t n=f.data.size();
    auto wr=window(f.samples,o.window=="hann"),wd=window(f.pulses,o.window=="hann");
    Buffer input(api,n),range(api,n),doppler_input(api,n),output(api,n);
    if(!o.wisdom_in.empty() && !api.import_wisdom(o.wisdom_in.c_str()))
        throw std::runtime_error("Cannot import FFTW wisdom: "+o.wisdom_in);
    auto plan_start=Steady::now();
    Plans plans(api,f.pulses,f.samples,input.p,range.p,doppler_input.p,output.p,o.measure_plan,!o.wisdom_in.empty());
    double planning=std::chrono::duration<double,std::milli>(Steady::now()-plan_start).count();
    if(!o.wisdom_in.empty() && !plans.from_wisdom)
        std::cerr<<"Warning: wisdom has no plan for "<<f.pulses<<"x"<<f.samples<<"; planning without it\n";
    if(!o.wisdom_out.empty() && !api.export_wisdom(o.wisdom_out.c_str()))
        throw std::runtime_error("Cannot export FFTW wisdom: "+o.wisdom_out);
    // fftw_print_plan은 C stdio(stdout)로 출력하므로 앞뒤로 flush해서 순서를 맞춤
    auto show_plan=[&](const char* name,Plan p){
        std::cout<<name<<" plan ("<<f.pulses<<"x"<<f.samples<<"):\n"<<std::flush;
        api.print_plan(p); std::fflush(stdout); std::cout<<'\n';
    };
    show_plan("Range",plans.range);
    show_plan("Doppler",plans.doppler);
    auto range_window=[&]{for(int p=0;p<f.pulses;++p){size_t off=size_t(p)*f.samples;
        for(int s=0;s<f.samples;++s){size_t i=off+s;double w=wr[s];input.p[i][0]=f.data[i].real()*w;input.p[i][1]=f.data[i].imag()*w;}}};
    // Windows and transposes in tiles: doppler_input[s*pulses+p] = range[p*samples+s]*wd[p].
    auto doppler_window=[&]{for(int sb=0;sb<f.samples;sb+=DOPPLER_TILE)for(int pb=0;pb<f.pulses;pb+=DOPPLER_TILE){
        int se=std::min(f.samples,sb+DOPPLER_TILE),pe=std::min(f.pulses,pb+DOPPLER_TILE);
        for(int s=sb;s<se;++s){size_t col=size_t(s)*f.pulses;
            for(int p=pb;p<pe;++p){size_t i=size_t(p)*f.samples+s;double w=wd[p];
                doppler_input.p[col+p][0]=range.p[i][0]*w;doppler_input.p[col+p][1]=range.p[i][1]*w;}}}};
    for(int i=0;i<o.warmup;++i){range_window();api.execute(plans.range);doppler_window();api.execute(plans.doppler);}
    size_t peak=0;double peak_power=0,beat=0,doppler=0,meters=0,velocity=0;
    for(int iteration=0;iteration<o.repeat;++iteration) {
        prof.run("processing_total",[&]{
            prof.run("range_window",range_window);
            prof.run("range_fft",[&]{api.execute(plans.range);});
            prof.run("doppler_window",doppler_window);
            prof.run("doppler_fft",[&]{api.execute(plans.doppler);});
            prof.run("postprocess",[&]{
                peak=0;peak_power=-1;
                for(size_t i=0;i<n;++i){double power=output.p[i][0]*output.p[i][0]+output.p[i][1]*output.p[i][1];
                    // On an exact tie, keep the lowest chirp index, matching row-major (NumPy) order.
                    if(power>peak_power || (power==peak_power && i%f.pulses<peak%f.pulses)){peak_power=power;peak=i;}}
            });
            prof.run("axis_calculation",[&]{
                beat=signed_bin(int(peak/f.pulses),f.samples)*f.fs/f.samples;
                doppler=signed_bin(int(peak%f.pulses),f.pulses)/(f.pulses*o.prp*1e-6);
                meters=beat*C/(2*(o.bandwidth*1e6/(o.chirp*1e-6)));
                velocity=doppler*C/(2*o.fc*1e9);
            });
        });
    }
    int d=int(peak%f.pulses),r=int(peak/f.pulses);
    std::cout<<"FFT: double precision, single thread, FFTW "<<(plans.from_wisdom?"WISDOM":o.measure_plan?"MEASURE":"ESTIMATE")
             <<"\nPlan creation: "<<planning<<" ms (excluded)\nWarmup: "<<o.warmup<<", repeats of SAME frame: "<<o.repeat
             <<"\nPeak bins: range="<<r<<", doppler_unshifted="<<d<<", doppler_shifted="<<(d+f.pulses/2)%f.pulses
             <<"\nBeat="<<beat<<" Hz, Doppler="<<doppler<<" Hz\nApparent signed range="<<meters
             <<" m, signed velocity="<<velocity<<" m/s\n";
    if(!o.output.empty()) {
        std::ofstream out(o.output);if(!out)throw std::runtime_error("Cannot open output file");
        out<<"doppler_bin_unshifted,range_bin,real,imag\n"<<std::setprecision(17);
        for(int p=0;p<f.pulses;++p)for(int s=0;s<f.samples;++s){size_t i=size_t(s)*f.pulses+p;
            out<<p<<','<<s<<','<<output.p[i][0]<<','<<output.p[i][1]<<'\n';}
        if(!out)throw std::runtime_error("Failed writing output");
        std::cout<<"Saved unshifted spectrum: "<<o.output<<'\n';
    }
}
int main(int argc,char** argv) {
    try {
        static_assert(sizeof(float)==4 && sizeof(double)==8,"Requires IEEE float32/float64");
        static_assert(std::numeric_limits<float>::is_iec559 && std::numeric_limits<double>::is_iec559,"Requires IEEE754");
        auto o=parse(argc,argv);FFTW api(o.fftw_lib);Profiler prof(o.thread_cpu);
        const auto* version=static_cast<const char*>(dlsym(api.lib,"fftw_version"));
        std::cout<<"FFTW version: "<<(version?version:"unknown")<<'\n';
        std::cout<<std::fixed<<std::setprecision(6);
        Frame frame;
        if(o.input.empty()) frame=receive(o,prof);
        else {
            auto packets=read_packets(o);
            Profiler warm(o.thread_cpu);
            for(int i=0;i<o.warmup;++i) frame=replay(packets,o,warm);
            for(int i=0;i<o.repeat;++i) frame=replay(packets,o,prof);
        }
        process(frame,o,prof,api);
        save_timings(o,prof);
        std::cout<<"\nInput timing (offline: per-frame; UDP: per-call; CPU% uses summed times)\n";
        prof.report({"receive_total","socket_wait","decode","reassembly"});
        std::cout<<"\nProcessing timing (per-frame averages)\n";
        prof.report({"range_window","range_fft","doppler_window","doppler_fft","postprocess","axis_calculation","processing_total"});
        auto a=prof.rows.at("range_fft"),b=prof.rows.at("doppler_fft");
        std::cout<<"\nFFT only: wall="<<(a.wall+b.wall)/o.repeat<<" ms, CPU="<<(a.cpu+b.cpu)/o.repeat
                 <<" ms, CPU usage="<<100*(a.cpu+b.cpu)/(a.wall+b.wall)<<"%\n"
                 <<"CPU scope: "<<(o.thread_cpu?"calling thread":"whole receiver process")
                 <<". 100% = one logical core. Total rows overlap child rows.\n"
                 <<"Planning, allocation, window creation, warmup, printing and saving are excluded from processing_total.\n"
                 <<"Repeated-frame measurements reflect warm-cache throughput, not network frame rate.\n";
        return 0;
    } catch(const std::exception& e){std::cerr<<"Error: "<<e.what()<<'\n';return 1;}
}