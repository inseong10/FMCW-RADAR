// S3a-0: exhaustive check of the branchless adc_window against the S2a reference rounding.
// Every int16 value x every distinct Q30 weight used by the pipeline (Hann products and 1<<30).
#include "../stream_adc16.hpp"
#include <cstdio>
#include <set>
static int16_t reference(int16_t value,uint32_t weight_q30) { // S2a-int16 implementation, verbatim logic
    int64_t product=static_cast<int64_t>(value)*weight_q30;
    uint64_t magnitude=static_cast<uint64_t>(product<0?-product:product);
    uint64_t rounded=magnitude>>30;
    uint64_t remainder=magnitude&((uint64_t(1)<<30)-1);
    if(remainder>(uint64_t(1)<<29) || (remainder==(uint64_t(1)<<29) && (rounded&1))) ++rounded;
    int64_t signed_value=product<0?-static_cast<int64_t>(rounded):static_cast<int64_t>(rounded);
    return static_cast<int16_t>(signed_value);
}
int main() {
    std::set<uint32_t> weights{1U<<30};
    for(int d=0;d<128;++d)for(int r=0;r<128;++r)weights.insert(stream128::adc_hann_q15[d]*stream128::adc_hann_q15[r]);
    unsigned long long checked=0,ties=0;
    for(uint32_t w:weights)for(int v=-32768;v<=32767;++v) {
        int16_t x=int16_t(v);
        if(stream128::adc_window(x,w)!=reference(x,w)){std::printf("MISMATCH v=%d w=%u\n",v,w);return 1;}
        uint64_t m=uint64_t(v<0?-v:v)*w; if((m&((1ULL<<30)-1))==(1ULL<<29))++ties;
        ++checked;
    }
    std::printf("ADC_WINDOW_EXHAUSTIVE_PASS weights=%zu values=65536 checked=%llu exact_ties=%llu\n",weights.size(),checked,ties);
    // Tie coverage: Hann weights produce no exact .5 remainders, so also sweep synthetic weights in [0,2^30]
    // (powers of two, 2^29 +/- k, 3*2^27+k, and 20,000 seeded random weights) where ties occur.
    std::set<uint32_t> extra;
    for(int k=0;k<=30;++k)extra.insert(1U<<k);
    for(uint32_t k=0;k<64;++k){extra.insert((1U<<29)+k);extra.insert((1U<<29)-k);extra.insert((3U<<27)|k);}
    uint32_t x=20261126;
    for(int i=0;i<20000;++i){x=x*1664525U+1013904223U;extra.insert(x%((1U<<30)+1));}
    unsigned long long xc=0,xt=0;
    for(uint32_t w:extra)for(int v=-32768;v<=32767;++v) {
        int16_t y=int16_t(v);
        if(stream128::adc_window(y,w)!=reference(y,w)){std::printf("MISMATCH_SYNTH v=%d w=%u\n",v,w);return 1;}
        uint64_t m=uint64_t(v<0?-v:v)*w; if((m&((1ULL<<30)-1))==(1ULL<<29))++xt;
        ++xc;
    }
    std::printf("ADC_WINDOW_SYNTHETIC_PASS weights=%zu checked=%llu exact_ties=%llu\n",extra.size(),xc,xt);
    if(xt==0){std::printf("NO_TIES_COVERED\n");return 1;}
    return 0;
}
