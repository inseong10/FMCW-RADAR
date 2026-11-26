// S3a-2b: Pipeline::butterfly (int32 form) equals the S3a-1 int64 butterfly for every input word pair
// with all components in an edge set, every twiddle actually used (L = 256, 512), and 2e8 random cases.
// Needs bench-only access (build from a copy whose "private:" lines are replaced by "public:").
#include "../stream_pipeline.hpp"
#include <cstdio>
#include <random>
static int ref_sat(int64_t value) { // S3a-1 saturate_q15, verbatim
    int64_t q=value/65536;
    if(value<0 && value%65536) --q;
    return q>32767?32767:q<-32768?-32768:int(q);
}
static void ref_butterfly(uint32_t& a,uint32_t& b,int wr,int wi) { // S3a-1 butterfly, verbatim
    const int64_t ar=fft128_real(a),ai=fft128_imag(a),br=fft128_real(b),bi=fft128_imag(b);
    const int64_t pr=br*wr-bi*wi,pim=br*wi+bi*wr;
    a=fft128_pack(ref_sat(ar*32768+pr),ref_sat(ai*32768+pim));
    b=fft128_pack(ref_sat(ar*32768-pr),ref_sat(ai*32768-pim));
}
static uint64_t checked=0;
static void one(uint32_t a,uint32_t b,int wr,int wi) {
    uint32_t ra=a,rb=b,na=a,nb=b;
    ref_butterfly(ra,rb,wr,wi);stream128::Pipeline::butterfly(na,nb,wr,wi);
    ++checked;
    if(ra!=na||rb!=nb){
        std::printf("MISMATCH a=%08x b=%08x wr=%d wi=%d ref=%08x,%08x new=%08x,%08x\n",a,b,wr,wi,ra,rb,na,nb);
        std::exit(1);
    }
}
int main(){
    const int edge[]={-32768,-32767,-32766,-16385,-16384,-1,0,1,2,16383,16384,32766,32767};
    std::vector<int> tw={-32768,-32767,-23170,-1,0,1,23170,32767};
    for(unsigned L:{128u,256u,512u}){
        stream128::Pipeline p("model",true,"",false,false,L==128?128:L,128);
        for(int v:p.tw_d_re)tw.push_back(v);
        for(int v:p.tw_d_im)tw.push_back(v);
    }
    std::sort(tw.begin(),tw.end());tw.erase(std::unique(tw.begin(),tw.end()),tw.end());
    // all edge components (13^4 word pairs) x edge twiddles; twiddles in use x a subset of edge words
    const int etw[]={-32768,-32767,-1,0,1,32767,23170,-23170};
    for(int ar:edge)for(int ai:edge)for(int br:edge)for(int bi:edge)for(int wr:etw)for(int wi:etw)
        one(fft128_pack(ar,ai),fft128_pack(br,bi),wr,wi);
    for(int wr:tw)for(int wi:tw)for(int br:edge)for(int bi:edge)for(int ar:{-32768,-1,0,32767})
        one(fft128_pack(ar,-ar-1),fft128_pack(br,bi),wr,wi);
    std::mt19937_64 g(20261126);
    std::uniform_int_distribution<int> u(-32768,32767);std::uniform_int_distribution<size_t> k(0,tw.size()-1);
    for(long i=0;i<200000000L;++i){
        const bool real_tw=i&1;
        one(uint32_t(g()),uint32_t(g()),real_tw?tw[k(g)]:u(g),real_tw?tw[k(g)]:u(g));
    }
    std::printf("BUTTERFLY_S3A2_EQUIV_PASS checked=%llu twiddles=%zu\n",(unsigned long long)checked,tw.size());
    return 0;
}
