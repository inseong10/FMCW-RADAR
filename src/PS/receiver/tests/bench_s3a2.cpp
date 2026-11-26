// S3a-2b: split-path (method A) equivalence and timing on the production Pipeline, model backend.
// Build twice (old/new stream_pipeline.hpp); the .dump files must be byte-identical.
// Usage: bench_s3a2 OUT_PREFIX REPS
// Inputs per shape x window: 3 seeded uniform full-range frames, all +32767, all -32768, alternating
// +-32767 by cell, a single max impulse. Dump = every spectrum word (spectrum_at) for every case.
#include "../stream_pipeline.hpp"
#include <chrono>
#include <cstdio>
#include <fstream>
#include <random>
#ifdef __linux__
#include <sched.h>
#endif
using stream128::Iq16;
static double now_us() {
    return std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
int main(int argc,char** argv){try{
#ifdef __linux__
    cpu_set_t set;CPU_ZERO(&set);CPU_SET(1,&set);sched_setaffinity(0,sizeof set,&set);
#endif
    if(argc!=3)throw std::runtime_error("usage: bench_s3a2 OUT_PREFIX REPS");
    const int reps=std::atoi(argv[2]);
    std::ofstream dump(std::string(argv[1])+".dump",std::ios::binary);
    const unsigned shapes[][2]={{256,128},{128,256},{256,256},{512,128}};
    for(auto& sh:shapes) for(int hann=0;hann<2;++hann) {
        const unsigned M=sh[0],N=sh[1],cells=M*N;
        stream128::Pipeline pipe("model",hann==1,"",false,false,M,N);
        std::vector<std::vector<Iq16>> inputs;
        for(int seed=0;seed<3;++seed){
            std::mt19937 g(20261126u+seed*7919u+M*3u+N+hann);std::uniform_int_distribution<int> u(-32768,32767);
            std::vector<Iq16> x(cells);for(auto& v:x){v.real=int16_t(u(g));v.imag=int16_t(u(g));}
            inputs.push_back(x);
        }
        inputs.emplace_back(cells,Iq16{32767,32767});
        inputs.emplace_back(cells,Iq16{-32768,-32768});
        {std::vector<Iq16> x(cells);for(unsigned i=0;i<cells;++i){int16_t v=(i&1)?-32767:32767;x[i]={v,int16_t(-v)};}inputs.push_back(x);}
        {std::vector<Iq16> x(cells,Iq16{0,0});x[0]={32767,-32768};inputs.push_back(x);}
        for(auto& x:inputs){
            pipe.prepare_adc16(x.data());pipe.transform();
            for(unsigned i=0;i<cells;++i){auto z=pipe.spectrum_at(i);dump.write((const char*)&z,sizeof z);}
        }
        std::vector<double> t;
        for(int k=0;k<reps;++k){
            pipe.prepare_adc16(inputs[k%3].data());
            const double a=now_us();pipe.transform();t.push_back(now_us()-a);
        }
        std::sort(t.begin(),t.end());
        std::printf("S3A2B_TRANSFORM shape=%ux%u hann=%d median_us=%.1f p99_us=%.1f min_us=%.1f n=%zu\n",
                    M,N,hann,t[t.size()/2],t[std::min(t.size()-1,t.size()*99/100)],t.front(),t.size());
    }
    if(!dump)throw std::runtime_error("dump write failed");
    std::printf("S3A2B_BENCH_DONE\n");
    return 0;
}catch(const std::exception& e){std::fprintf(stderr,"error: %s\n",e.what());return 1;}}
