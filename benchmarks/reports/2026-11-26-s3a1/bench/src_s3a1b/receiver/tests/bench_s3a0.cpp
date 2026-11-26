// S3a-0 microbenchmark: prepare_adc16 and detect (power + CA-CFAR) on the production Pipeline.
// Build twice (old/new headers); dumps must be byte-identical. Pins itself to CPU1 on Linux.
// Usage: bench_s3a0 BACKEND(model|ps) FFTW_LIB(or -) OUT_PREFIX REPS FIXTURE...
#include "../stream_pipeline.hpp"
#include <chrono>
#include <cstdio>
#include <fstream>
#include <random>
#ifdef __linux__
#include <sched.h>
#endif
using Frame=std::vector<stream128::Iq16>;
static Frame load(const char* path) {
    std::ifstream f(path,std::ios::binary);
    std::vector<unsigned char> b((std::istreambuf_iterator<char>(f)),std::istreambuf_iterator<char>());
    if(b.size()!=40+65536 || std::string(b.begin(),b.begin()+8)!="RSPB0002") throw std::runtime_error("bad fixture");
    Frame x(16384);
    for(size_t i=0;i<16384;++i) {
        const unsigned char* p=b.data()+40+4*i;
        x[i].real=int16_t(uint16_t(p[0]<<8|p[1]));x[i].imag=int16_t(uint16_t(p[2]<<8|p[3]));
    }
    return x;
}
static double now_us() {
    return std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static void stats(const char* name,std::vector<double> v) {
    std::sort(v.begin(),v.end());
    double med=v[v.size()/2],p99=v[std::min(v.size()-1,v.size()*99/100)];
    std::printf("S3A0_STAGE %s median_us=%.1f p99_us=%.1f min_us=%.1f per_cell_us=%.4f n=%zu\n",
                name,med,p99,v.front(),med/16384,v.size());
}
int main(int argc,char** argv){try{
    if(argc<6) throw std::runtime_error("usage: BACKEND FFTW OUT_PREFIX REPS FIXTURE...");
#ifdef __linux__
    cpu_set_t set;CPU_ZERO(&set);CPU_SET(1,&set);
    std::printf("S3A0_PIN cpu1=%s\n",sched_setaffinity(0,sizeof(set),&set)==0?"ok":"failed");
#endif
    std::string backend=argv[1],fftw=argv[2];
    if(std::string(argv[2])=="-")fftw.clear();
    int reps=std::atoi(argv[4]);
    stream128::Pipeline pipe(backend,true,fftw);
    std::vector<std::pair<std::string,Frame>> inputs;
    for(int i=5;i<argc;++i)inputs.push_back({argv[i],load(argv[i])});
    std::mt19937 rng(20261126);
    Frame random(16384),sat(16384),zero(16384),tone(16384);
    for(auto& s:random){s.real=int16_t(rng());s.imag=int16_t(rng());}
    for(size_t i=0;i<16384;++i){sat[i].real=(i&1)?32767:-32768;sat[i].imag=(i&2)?-32768:32767;}
    for(size_t i=0;i<16384;++i){tone[i].real=int16_t(std::lround(30000*std::cos(0.37*double(i%128)+0.11*double(i/128))));
                                tone[i].imag=int16_t(std::lround(30000*std::sin(0.37*double(i%128)+0.11*double(i/128))));}
    inputs.push_back({"random_seed20261126",random});inputs.push_back({"saturated_pm32768",sat});
    inputs.push_back({"zero",zero});inputs.push_back({"tone_30000",tone});
    std::ofstream dump(std::string(argv[3])+".dump",std::ios::binary);
    std::ofstream peaks(std::string(argv[3])+".peaks.txt");
    for(auto& [name,x]:inputs) {
        pipe.prepare_adc16(x.data());pipe.transform();const auto& pk=pipe.detect();
        for(size_t i=0;i<16384;++i){auto z=pipe.spectrum_at(i);dump.write((const char*)&z,sizeof z);}
        dump.write((const char*)pipe.power().data(),16384*sizeof(double));
        dump.write((const char*)pipe.cfar.thresholds().data(),16384*sizeof(double));
        char line[160];
        std::snprintf(line,sizeof line,"%s peaks=%zu\n",name.c_str(),pk.size());peaks<<line;
        for(const auto& p:pk){std::snprintf(line,sizeof line,"%d %d %.17g %.17g\n",p.doppler,p.range,p.power,p.threshold);peaks<<line;}
    }
    if(!dump||!peaks)throw std::runtime_error("dump write failed");
    const Frame& x=inputs.front().second; // first fixture: timing input
    std::vector<double> prep,trans,det;
    for(int k=0;k<reps+20;++k) {
        double t0=now_us();pipe.prepare_adc16(x.data());double t1=now_us();pipe.transform();
        double t2=now_us();pipe.detect();double t3=now_us();
        if(k>=20){prep.push_back(t1-t0);trans.push_back(t2-t1);det.push_back(t3-t2);}
    }
    std::printf("S3A0_BENCH backend=%s reps=%d timing_input=%s\n",backend.c_str(),reps,inputs.front().first.c_str());
    stats("prepare_adc16",prep);stats("transform",trans);stats("detect_power_cfar",det);
    return 0;
}catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 1;}}
