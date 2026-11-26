// S3a-2b micro: time only the split-path pieces of Pipeline::transform at 256x128 / 128x256 / 256x256
// (block gather, block placement, Doppler/range combine stages), old vs new header.
// Needs bench-only access: build from a copy whose "private:" lines are replaced by "public:".
// Usage: micro_s3a2 REPS
#include "../stream_pipeline.hpp"
#include <chrono>
#include <cstdio>
#include <random>
#ifdef __linux__
#include <sched.h>
#endif
using stream128::Pipeline;
static double now_us() {
    return std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static void report(const char* name,unsigned M,unsigned N,std::vector<double> t) {
    std::sort(t.begin(),t.end());
    std::printf("S3A2B_MICRO %s shape=%ux%u median_us=%.1f min_us=%.1f n=%zu\n",name,M,N,t[t.size()/2],t.front(),t.size());
}
int main(int argc,char** argv){try{
#ifdef __linux__
    cpu_set_t set;CPU_ZERO(&set);CPU_SET(1,&set);sched_setaffinity(0,sizeof set,&set);
#endif
    const int reps=argc>1?std::atoi(argv[1]):200;
    const unsigned shapes[][2]={{256,128},{128,256},{256,256}};
    uint64_t checksum=0;
    for(auto& sh:shapes){
        const unsigned M=sh[0],N=sh[1];
        Pipeline pipe("model",true,"",false,false,M,N);
        std::mt19937 g(7);
        for(auto& w:pipe.packed) w=g();
        std::vector<double> gather,place,combine;
        std::vector<uint32_t> work(pipe.cells);
        for(int k=0;k<reps;++k){
            // gather: same loops as transform (into sub_in)
            double a=now_us();
            for(unsigned p=0;p<pipe.split_d;++p) for(unsigned q=0;q<pipe.split_r;++q)
                for(unsigned d=0;d<128;++d){
                    const uint32_t* src=pipe.packed.data()+size_t(d*pipe.split_d+p)*N+q;
                    uint32_t* dst=pipe.sub_in.data()+d*128;
                    for(unsigned r=0;r<128;++r) dst[r]=src[size_t(r)*pipe.split_r];
                }
            gather.push_back(now_us()-a);
            a=now_us();
            for(unsigned b=0;b<pipe.split_d*pipe.split_r;++b)
                for(unsigned d=0;d<128;++d)
                    std::copy(pipe.sub_in.begin()+d*128,pipe.sub_in.begin()+d*128+128,work.begin()+size_t(d)*N);
            place.push_back(now_us()-a);
            std::copy(pipe.packed.begin(),pipe.packed.end(),work.begin());
            a=now_us();
            uint32_t* s=work.data();
            for(unsigned half=128;half<M;half*=2)
                for(unsigned base=0;base<M;base+=2*half)
                    for(unsigned j=0;j<half;++j){
                        const unsigned t=j*M/(2*half);
                        uint32_t* x=s+size_t(base+j)*N;uint32_t* y=s+size_t(base+j+half)*N;
                        for(unsigned r=0;r<N;++r) Pipeline::butterfly(x[r],y[r],pipe.tw_d_re[t],pipe.tw_d_im[t]);
                    }
            if(pipe.split_r>1)
                for(unsigned d=0;d<M;++d){
                    uint32_t* row=s+size_t(d)*N;
                    for(unsigned half=128;half<N;half*=2)
                        for(unsigned base=0;base<N;base+=2*half)
                            for(unsigned j=0;j<half;++j){
                                const unsigned t=j*N/(2*half);
                                Pipeline::butterfly(row[base+j],row[base+j+half],pipe.tw_r_re[t],pipe.tw_r_im[t]);
                            }
                }
            combine.push_back(now_us()-a);
            checksum+=work[k%work.size()];
        }
        report("gather",M,N,gather);report("place",M,N,place);report("combine",M,N,combine);
    }
    std::printf("S3A2B_MICRO_DONE checksum=%llu\n",(unsigned long long)checksum);
    return 0;
}catch(const std::exception& e){std::fprintf(stderr,"error: %s\n",e.what());return 1;}}
