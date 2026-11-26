// S3a-3b: split_neon::window8 (NEON adc_window, ARM only) equals adc_window for every int16 value x edge
// weights, every Q30 weight in use (Hann 128/256/512 products and 2^30) x edge values, and 2e8 random pairs.
// Also checks prepare_plain / prepare_deint256 against the scalar loops on random frames.
#include "../stream_pipeline.hpp"
#include <cstdio>
#include <random>
#include <set>
using namespace stream128;
int main(){
#ifndef STREAM128_SPLIT_NEON
    std::printf("WINDOW_S3A3B_NEON_SKIPPED (not ARM)\n");
    return 0;
#else
    uint64_t checked=0;
    int16_t v[8];uint32_t w[8];unsigned fill=0;
    auto flush=[&]{
        if(!fill) return;
        for(unsigned k=fill;k<8;++k){v[k]=v[0];w[k]=w[0];}
        int16_t out[8];
        vst1q_s16(out,split_neon::window8(vld1q_s16(v),vld1q_u32(w),vld1q_u32(w+4)));
        for(unsigned k=0;k<fill;++k){
            if(out[k]!=adc_window(v[k],w[k])){
                std::printf("MISMATCH v=%d w=%u neon=%d ref=%d\n",v[k],w[k],out[k],adc_window(v[k],w[k]));std::exit(1);
            }
            ++checked;
        }
        fill=0;
    };
    auto one=[&](int value,uint32_t weight){v[fill]=int16_t(value);w[fill]=weight;if(++fill==8)flush();};
    std::set<uint32_t> used{1U<<30};
    for(unsigned L1:{128u,256u,512u})for(unsigned L2:{128u,256u}){
        const auto a=adc_hann_q15_table(L1),b=adc_hann_q15_table(L2);
        for(uint32_t x:a)for(uint32_t y:b)used.insert(x*y);
    }
    std::vector<uint32_t> ew={0,1,2,(1U<<29)-1,1U<<29,(1U<<29)+1,(1U<<30)-1,1U<<30,0x2aaaaaaaU,12345678U};
    std::mt19937_64 g(20261127);
    for(int i=0;i<54;++i) ew.push_back(uint32_t(g()%((1ULL<<30)+1)));
    for(int value=-32768;value<=32767;++value) for(uint32_t weight:ew) one(value,weight);
    const int ev[]={-32768,-32767,-32766,-16385,-16384,-3,-2,-1,0,1,2,3,16383,16384,32766,32767};
    for(uint32_t weight:used) for(int value:ev) one(value,weight);
    std::vector<uint32_t> uv(used.begin(),used.end());
    std::uniform_int_distribution<int> u(-32768,32767);std::uniform_int_distribution<size_t> k(0,uv.size()-1);
    for(long i=0;i<200000000L;++i) one(u(g),(i&1)?uv[k(g)]:uint32_t(g()%((1ULL<<30)+1)));
    flush();
    // whole-row kernels against the scalar loops (natural and deinterleaved orders)
    for(unsigned rep=0;rep<20;++rep){
        std::vector<Iq16> x(256*256);for(auto& c:x){c.real=int16_t(u(g));c.imag=int16_t(u(g));}
        if(rep==0) for(auto& c:x){c.real=-32768;c.imag=32767;}
        std::vector<uint32_t> wt(x.size());for(auto& q:wt) q=uv[k(g)];
        std::vector<uint32_t> o1(x.size()),o2(x.size());
        split_neon::prepare_plain(reinterpret_cast<const int16_t*>(x.data()),wt.data(),o1.data(),unsigned(x.size()));
        for(size_t i=0;i<x.size();++i) o2[i]=adc_pack(adc_window(x[i].real,wt[i]),adc_window(x[i].imag,wt[i]));
        if(o1!=o2){std::printf("MISMATCH prepare_plain rep=%u\n",rep);return 1;}
        split_neon::prepare_deint256(reinterpret_cast<const int16_t*>(x.data()),wt.data(),o1.data(),256);
        for(unsigned d=0;d<256;++d)for(unsigned r=0;r<256;++r){
            const unsigned o=d*256+(r&1)*128+(r>>1);const Iq16 c=x[d*256+r];
            o2[o]=adc_pack(adc_window(c.real,wt[o]),adc_window(c.imag,wt[o]));
        }
        if(o1!=o2){std::printf("MISMATCH prepare_deint256 rep=%u\n",rep);return 1;}
    }
    std::printf("WINDOW_S3A3B_NEON_EQUIV_PASS checked=%llu weights_in_use=%zu frames=20\n",(unsigned long long)checked,used.size());
    return 0;
#endif
}
