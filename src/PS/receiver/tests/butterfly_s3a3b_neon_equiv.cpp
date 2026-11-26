// S3a-3b: Pipeline::combine_tw / combine_const (NEON rows on ARM) equal Pipeline::butterfly lane by lane for
// every input word pair with all components in an edge set x edge twiddles, every twiddle in use x edge
// words, and 2e8 random cases. combine_tw runs with bo != bi (fused form) and bo == bi (in place).
// Needs bench-only access (build from a copy whose class access is opened). On non-ARM hosts it checks the
// scalar fallback against butterfly, which is trivially equal.
#include "../stream_pipeline.hpp"
#include <cstdio>
#include <random>
using stream128::Pipeline;
static uint64_t checked=0;
static uint32_t ca[8],cb[8];static int16_t cwr[8],cwi[8];static unsigned fill=0;
static void flush() {
    if(!fill) return;
    for(unsigned k=fill;k<8;++k){ca[k]=ca[0];cb[k]=cb[0];cwr[k]=cwr[0];cwi[k]=cwi[0];}
    uint32_t ra[8],rb[8];
    for(unsigned k=0;k<8;++k){ra[k]=ca[k];rb[k]=cb[k];Pipeline::butterfly(ra[k],rb[k],cwr[k],cwi[k]);}
    uint32_t a1[8],b1[8],o1[8],a2[8],b2[8];
    for(unsigned k=0;k<8;++k){a1[k]=ca[k];b1[k]=cb[k];o1[k]=0xdeadbeefu;a2[k]=ca[k];b2[k]=cb[k];}
    Pipeline::combine_tw(a1,o1,b1,cwr,cwi,8);
    Pipeline::combine_tw(a2,b2,b2,cwr,cwi,8);
    for(unsigned k=0;k<fill;++k){
        if(a1[k]!=ra[k]||o1[k]!=rb[k]||b1[k]!=cb[k]||a2[k]!=ra[k]||b2[k]!=rb[k]){
            std::printf("MISMATCH tw a=%08x b=%08x wr=%d wi=%d ref=%08x,%08x neon=%08x,%08x\n",
                        ca[k],cb[k],cwr[k],cwi[k],ra[k],rb[k],a1[k],o1[k]);
            std::exit(1);
        }
        // combine_const: same twiddle in all 8 lanes, inputs from this case's words rotated
        uint32_t a3[8],b3[8],ra3[8],rb3[8];
        for(unsigned m=0;m<8;++m){a3[m]=ca[(k+m)&7];b3[m]=cb[(k+3*m)&7];ra3[m]=a3[m];rb3[m]=b3[m];
            Pipeline::butterfly(ra3[m],rb3[m],cwr[k],cwi[k]);}
        Pipeline::combine_const(a3,b3,cwr[k],cwi[k],8);
        for(unsigned m=0;m<8;++m) if(a3[m]!=ra3[m]||b3[m]!=rb3[m]){
            std::printf("MISMATCH const wr=%d wi=%d lane=%u\n",cwr[k],cwi[k],m);std::exit(1);
        }
        ++checked;
    }
    fill=0;
}
static void one(uint32_t a,uint32_t b,int wr,int wi) {
    ca[fill]=a;cb[fill]=b;cwr[fill]=int16_t(wr);cwi[fill]=int16_t(wi);
    if(++fill==8) flush();
}
int main(){
#ifdef STREAM128_SPLIT_NEON
    std::printf("path=neon\n");
#else
    std::printf("path=scalar\n");
#endif
    const int edge[]={-32768,-32767,-32766,-16385,-16384,-1,0,1,2,16383,16384,32766,32767};
    std::vector<int> tw={-32768,-32767,-23170,-1,0,1,23170,32767};
    for(unsigned L:{256u,512u}){
        Pipeline p("model",true,"",false,false,L,L==512?128:256);
        for(int v:p.tw_d_re)tw.push_back(v);
        for(int v:p.tw_d_im)tw.push_back(v);
        for(int v:p.tw_r_re)tw.push_back(v);
        for(int v:p.tw_r_im)tw.push_back(v);
        for(size_t k=0;k<p.tw_r_re.size();++k)
            if(p.tw_r16_re[k]!=p.tw_r_re[k]||p.tw_r16_im[k]!=p.tw_r_im[k]){std::printf("TW16_MISMATCH\n");return 1;}
    }
    std::sort(tw.begin(),tw.end());tw.erase(std::unique(tw.begin(),tw.end()),tw.end());
    const int etw[]={-32768,-32767,-1,0,1,32767,23170,-23170};
    for(int ar:edge)for(int ai:edge)for(int br:edge)for(int bi:edge)for(int wr:etw)for(int wi:etw)
        one(fft128_pack(ar,ai),fft128_pack(br,bi),wr,wi);
    for(int wr:tw)for(int wi:tw)for(int br:edge)for(int bi:edge)for(int ar:{-32768,-1,0,32767})
        one(fft128_pack(ar,-ar-1),fft128_pack(br,bi),wr,wi);
    std::mt19937_64 g(20261127);
    std::uniform_int_distribution<int> u(-32768,32767);std::uniform_int_distribution<size_t> k(0,tw.size()-1);
    for(long i=0;i<200000000L;++i){
        const bool real_tw=i&1;
        one(uint32_t(g()),uint32_t(g()),real_tw?tw[k(g)]:u(g),real_tw?tw[k(g)]:u(g));
    }
    flush();
    std::printf("BUTTERFLY_S3A3B_NEON_EQUIV_PASS checked=%llu twiddles=%zu\n",(unsigned long long)checked,tw.size());
    return 0;
}
