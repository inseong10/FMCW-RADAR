// E11b: two axis requests; cached gather/scatter and copy count unchanged.
#include "batch_process.h"
int fft128_process_batch(const uint32_t *in, uint32_t *out, uint32_t *ranged,
                        uint32_t *axis_in, uint32_t *axis_out, fft128_profile *p) {
    if(!in || !out || !ranged || !axis_in || !axis_out) return -1;
    int rc=fft128_batch_axis(in,ranged,128,1000,p);
    if(rc) return rc;
    uint64_t tick=p ? fft128_now_ns() : 0;
    for(unsigned r=0;r<128;++r)
        for(unsigned ch=0;ch<128;++ch) axis_in[r*128+ch]=ranged[ch*128+r];
    if(p) p->gather_ns+=fft128_now_ns()-tick;
    rc=fft128_batch_axis(axis_in,axis_out,128,1000,p);
    if(rc) return rc;
    tick=p ? fft128_now_ns() : 0;
    for(unsigned r=0;r<128;++r)
        for(unsigned d=0;d<128;++d) out[d*128+r]=axis_out[r*128+d];
    if(p) p->scatter_ns+=fft128_now_ns()-tick;
    return 0;
}
