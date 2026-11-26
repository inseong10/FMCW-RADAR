// S3a-3b micro at 128x256 (model pipeline, CPU1): prepare_adc16 as built (old or new header), and the
// R-axis split-path pieces outside E14 in the S3a-2b form (strided gather, place 2 blocks, range combine)
// versus the S3a-3b form (contiguous gather, place block 0, range stage fused with block 1).
// Needs bench-only access: build from a copy whose "private:" lines are replaced by "public:".
// Usage: micro_s3a3b REPS
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
static void report(const char* name,std::vector<double> t) {
    std::sort(t.begin(),t.end());
    std::printf("S3A3B_MICRO %s shape=128x256 median_us=%.1f min_us=%.1f n=%zu\n",name,t[t.size()/2],t.front(),t.size());
}
int main(int argc,char** argv){try{
#ifdef __linux__
    cpu_set_t set;CPU_ZERO(&set);CPU_SET(1,&set);sched_setaffinity(0,sizeof set,&set);
#endif
    const int reps=argc>1?std::atoi(argv[1]):200;
    const unsigned M=128,N=256;
    Pipeline pipe("model",true,"",false,false,M,N);
    std::mt19937 g(7);
    std::vector<stream128::Iq16> x(pipe.cells);
    for(auto& v:x){v.real=int16_t(g());v.imag=int16_t(g());}
    std::vector<uint32_t> blk0(16384),blk1(16384),work(pipe.cells);
    for(auto& w:blk0) w=g();
    for(auto& w:blk1) w=g();
    std::vector<double> prep,old_g,old_pc,new_g,new_pc,neon_pc,neon_dop;
#ifdef STREAM128_SPLIT_NEON
    Pipeline dpipe("model",true,"",false,false,256,128);
    std::vector<uint32_t> dop(256*128);
    for(auto& w:dop) w=g();
#endif
    uint64_t checksum=0;
    uint32_t* const s=work.data();uint32_t* const in=pipe.sub_in.data();
    for(int k=0;k<reps;++k){
        double a=now_us();pipe.prepare_adc16(x.data());prep.push_back(now_us()-a);
        const uint32_t* const pk=pipe.packed.data();
        // S3a-2b: strided gather of both blocks
        a=now_us();
        for(unsigned q=0;q<2;++q) for(unsigned d=0;d<128;++d){
            const uint32_t* src=pk+size_t(d)*N+q;uint32_t* dst=in+d*128;
            for(unsigned r=0;r<128;++r) dst[r]=src[size_t(r)*2];
        }
        old_g.push_back(now_us()-a);
        // S3a-2b: place both blocks, then range combine per row
        a=now_us();
        for(unsigned d=0;d<128;++d){
            std::copy(blk0.data()+d*128,blk0.data()+d*128+128,s+size_t(d)*N);
            std::copy(blk1.data()+d*128,blk1.data()+d*128+128,s+size_t(d)*N+128);
        }
        for(unsigned d=0;d<M;++d){
            uint32_t* row=s+size_t(d)*N;
            for(unsigned j=0;j<128;++j){
                const unsigned t=j*N/256;
                Pipeline::butterfly(row[j],row[j+128],pipe.tw_r_re[t],pipe.tw_r_im[t]);
            }
        }
        old_pc.push_back(now_us()-a);
        checksum+=s[k%pipe.cells];
        // S3a-3b: contiguous gather of both blocks
        a=now_us();
        for(unsigned q=0;q<2;++q) for(unsigned d=0;d<128;++d){
            const uint32_t* src=pk+size_t(d)*N+q*128;
            std::copy(src,src+128,in+d*128);
        }
        new_g.push_back(now_us()-a);
        // S3a-3b: place block 0, fused range stage reading block 1
        a=now_us();
        for(unsigned d=0;d<128;++d) std::copy(blk0.data()+d*128,blk0.data()+d*128+128,s+size_t(d)*N);
        {
            const int* const wr=pipe.tw_r_re.data();const int* const wi=pipe.tw_r_im.data();
            for(unsigned d=0;d<128;++d){
                uint32_t* const row=s+size_t(d)*256;const uint32_t* const hi=blk1.data()+d*128;
                for(unsigned j=0;j<128;++j){
                    uint32_t u=row[j],v=hi[j];
                    Pipeline::butterfly(u,v,wr[j],wi[j]);
                    row[j]=u;row[128+j]=v;
                }
            }
        }
        new_pc.push_back(now_us()-a);
        checksum+=s[(k*7)%pipe.cells]+in[k%16384];
#ifdef STREAM128_SPLIT_NEON
        // S3a-3b production form: place block 0, fused range stage through combine_tw (NEON)
        a=now_us();
        for(unsigned d=0;d<128;++d) std::copy(blk0.data()+d*128,blk0.data()+d*128+128,s+size_t(d)*N);
        for(unsigned d=0;d<128;++d){
            uint32_t* const row=s+size_t(d)*256;
            Pipeline::combine_tw(row,row+128,blk1.data()+d*128,pipe.tw_r16_re.data(),pipe.tw_r16_im.data(),128);
        }
        neon_pc.push_back(now_us()-a);
        checksum+=s[(k*5)%pipe.cells];
        // 256x128 Doppler stage (half=128) through combine_const (NEON), on a 256x128-sized buffer
        a=now_us();
        for(unsigned j=0;j<128;++j)
            Pipeline::combine_const(dop.data()+size_t(j)*128,dop.data()+size_t(j+128)*128,dpipe.tw_d_re[j],dpipe.tw_d_im[j],128);
        neon_dop.push_back(now_us()-a);
        checksum+=dop[k%dop.size()];
#endif
    }
    report("prepare",prep);report("old_gather",old_g);report("old_place_combine",old_pc);
    report("new_gather",new_g);report("new_place_fused",new_pc);
#ifdef STREAM128_SPLIT_NEON
    report("neon_place_fused",neon_pc);report("neon_doppler_256x128",neon_dop);
#endif
    std::printf("S3A3B_MICRO_DONE checksum=%llu\n",(unsigned long long)checksum);
    return 0;
}catch(const std::exception& e){std::fprintf(stderr,"error: %s\n",e.what());return 1;}}
