// S2a integrated pipeline. No disk spectrum handoff and no hardware fallback.
#pragma once
#include <algorithm>
#include <array>
#include <cctype>
#include <cstdlib>
#include <cmath>
#include <cstring>
#include <memory>
#include <string>
#include <vector>
#include "cfar_ca.hpp"
#include "stream_adc16.hpp"
extern "C" {
#include "../fft128/native_core.h"
}
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif
#ifdef __linux__
#include <fcntl.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include "../fft128/dma_frame/fft128_dma_frame_uapi.h"
#endif

namespace stream128 {
#ifdef FFT128_SINGLE
using FftReal=float;
constexpr const char* fftw_prefix="fftwf_";
constexpr const char* fft_precision="float32";
#else
using FftReal=double;
constexpr const char* fftw_prefix="fftw_";
constexpr const char* fft_precision="float64";
#endif
#if defined(__arm__) && defined(__GNUC__)
// S3a-3b: split-path combine rows on 32-bit ARM. The int32 equations of Pipeline::butterfly run 4 lanes at a
// time with NEON, enabled for these functions only (Cortex-A9 has NEON; the build keeps its default FPU flags).
// Products |b*w| <= 2^30 fit int32 (vmull_s16); vqmovn_s32 is sat16; >> on int32 lanes is arithmetic.
#define STREAM128_SPLIT_NEON 1
#pragma GCC push_options
#pragma GCC target("fpu=neon")
#include <arm_neon.h>
namespace split_neon {
inline void half4(int16x4_t ar,int16x4_t ai,int16x4_t br,int16x4_t bi,int16x4_t wr,int16x4_t wi,
                  int16x4_t& oar,int16x4_t& oai,int16x4_t& obr,int16x4_t& obi) {
    const int32x4_t m=vdupq_n_s32(0x7fff);
    const int32x4_t p1=vmull_s16(br,wr),p2=vmull_s16(bi,wi),p3=vmull_s16(br,wi),p4=vmull_s16(bi,wr);
    const int32x4_t l1=vandq_s32(p1,m),l2=vandq_s32(p2,m);
    // hr=(p1>>15)-(p2>>15)-(l1<l2): the compare mask is -1 when true
    const int32x4_t hr=vaddq_s32(vsubq_s32(vshrq_n_s32(p1,15),vshrq_n_s32(p2,15)),
                                 vreinterpretq_s32_u32(vcltq_s32(l1,l2)));
    const int32x4_t lr=vandq_s32(vsubq_s32(l1,l2),m);
    const int32x4_t l3=vandq_s32(p3,m),l4=vandq_s32(p4,m),s=vaddq_s32(l3,l4);
    const int32x4_t hi=vaddq_s32(vaddq_s32(vshrq_n_s32(p3,15),vshrq_n_s32(p4,15)),vshrq_n_s32(s,15));
    const int32x4_t li=vandq_s32(s,m);
    const int32x4_t A=vmovl_s16(ar),B=vmovl_s16(ai);
    const int32x4_t nr=vreinterpretq_s32_u32(vtstq_s32(lr,lr)),ni=vreinterpretq_s32_u32(vtstq_s32(li,li)); // -(x!=0)
    oar=vqmovn_s32(vshrq_n_s32(vaddq_s32(A,hr),1));
    oai=vqmovn_s32(vshrq_n_s32(vaddq_s32(B,hi),1));
    obr=vqmovn_s32(vshrq_n_s32(vaddq_s32(vsubq_s32(A,hr),nr),1));
    obi=vqmovn_s32(vshrq_n_s32(vaddq_s32(vsubq_s32(B,hi),ni),1));
}
// 8 words: a[k],bi[k] -> a[k],bo[k] (bo may equal bi; all loads happen before the stores).
inline void eight(uint32_t* a,uint32_t* bo,const uint32_t* bi,int16x8_t wr,int16x8_t wi) {
    const int16x8x2_t x=vuzpq_s16(vreinterpretq_s16_u32(vld1q_u32(a)),vreinterpretq_s16_u32(vld1q_u32(a+4)));
    const int16x8x2_t y=vuzpq_s16(vreinterpretq_s16_u32(vld1q_u32(bi)),vreinterpretq_s16_u32(vld1q_u32(bi+4)));
    int16x4_t r0,i0,r1,i1,r2,i2,r3,i3;
    half4(vget_low_s16(x.val[0]),vget_low_s16(x.val[1]),vget_low_s16(y.val[0]),vget_low_s16(y.val[1]),
          vget_low_s16(wr),vget_low_s16(wi),r0,i0,r1,i1);
    half4(vget_high_s16(x.val[0]),vget_high_s16(x.val[1]),vget_high_s16(y.val[0]),vget_high_s16(y.val[1]),
          vget_high_s16(wr),vget_high_s16(wi),r2,i2,r3,i3);
    const int16x8x2_t oa=vzipq_s16(vcombine_s16(r0,r2),vcombine_s16(i0,i2));
    const int16x8x2_t ob=vzipq_s16(vcombine_s16(r1,r3),vcombine_s16(i1,i3));
    vst1q_u32(a,vreinterpretq_u32_s16(oa.val[0]));vst1q_u32(a+4,vreinterpretq_u32_s16(oa.val[1]));
    vst1q_u32(bo,vreinterpretq_u32_s16(ob.val[0]));vst1q_u32(bo+4,vreinterpretq_u32_s16(ob.val[1]));
}
inline void rows_tw(uint32_t* a,uint32_t* bo,const uint32_t* bi,const int16_t* wr,const int16_t* wi,unsigned n) {
    for(unsigned k=0;k<n;k+=8) eight(a+k,bo+k,bi+k,vld1q_s16(wr+k),vld1q_s16(wi+k));
}
inline void rows_const(uint32_t* a,uint32_t* b,int16_t wr,int16_t wi,unsigned n) {
    const int16x8_t R=vdupq_n_s16(wr),I=vdupq_n_s16(wi);
    for(unsigned k=0;k<n;k+=8) eight(a+k,b+k,b+k,R,I);
}
// S3a-3b: adc_window for 8 components with per-component Q30 weights, the same 32-bit-piece equations.
// |v| as u16 (vabs wraps -32768 to 0x8000 = 32768); m=|v|*w < 2^46 (vmull_u32); q0=m>>30 (vshrn), lo=m mod 2^32.
inline int16x8_t window8(int16x8_t v,uint32x4_t w0,uint32x4_t w1) {
    const uint32x4_t a0=vmovl_u16(vget_low_u16(vreinterpretq_u16_s16(vabsq_s16(v))));
    const uint32x4_t a1=vmovl_u16(vget_high_u16(vreinterpretq_u16_s16(vabsq_s16(v))));
    const uint64x2_t m0=vmull_u32(vget_low_u32(a0),vget_low_u32(w0)),m1=vmull_u32(vget_high_u32(a0),vget_high_u32(w0));
    const uint64x2_t m2=vmull_u32(vget_low_u32(a1),vget_low_u32(w1)),m3=vmull_u32(vget_high_u32(a1),vget_high_u32(w1));
    const uint32x4_t q0a=vcombine_u32(vshrn_n_u64(m0,30),vshrn_n_u64(m1,30)),q0b=vcombine_u32(vshrn_n_u64(m2,30),vshrn_n_u64(m3,30));
    const uint32x4_t loa=vcombine_u32(vmovn_u64(m0),vmovn_u64(m1)),lob=vcombine_u32(vmovn_u64(m2),vmovn_u64(m3));
    const uint32x4_t mask=vdupq_n_u32(0x3fffffffU),half=vdupq_n_u32(0x1fffffffU),one=vdupq_n_u32(1U);
    const uint32x4_t qa=vaddq_u32(q0a,vshrq_n_u32(vaddq_u32(vaddq_u32(vandq_u32(loa,mask),half),vandq_u32(q0a,one)),30));
    const uint32x4_t qb=vaddq_u32(q0b,vshrq_n_u32(vaddq_u32(vaddq_u32(vandq_u32(lob,mask),half),vandq_u32(q0b,one)),30));
    const int16x8_t q=vreinterpretq_s16_u16(vcombine_u16(vmovn_u32(qa),vmovn_u32(qb)));
    const int16x8_t sign=vshrq_n_s16(v,15);
    return vsubq_s16(veorq_s16(q,sign),sign); // (q^sign)-sign mod 2^16 = the scalar int32 result cast to int16
}
inline void store8(uint32_t* o,int16x8_t re,int16x8_t im) {
    const int16x8x2_t z=vzipq_s16(re,im);
    vst1q_u32(o,vreinterpretq_u32_s16(z.val[0]));vst1q_u32(o+4,vreinterpretq_u32_s16(z.val[1]));
}
// count cells in order (count a multiple of 8).
inline void prepare_plain(const int16_t* in,const uint32_t* w,uint32_t* o,unsigned count) {
    for(unsigned i=0;i<count;i+=8) {
        const int16x8x2_t x=vld2q_s16(in+2*i);
        const uint32x4_t w0=vld1q_u32(w+i),w1=vld1q_u32(w+i+4);
        store8(o+i,window8(x.val[0],w0,w1),window8(x.val[1],w0,w1));
    }
}
// rows of 256 cells stored deinterleaved: sample 2k+q at q*128+k; w is already in that order.
inline void prepare_deint256(const int16_t* in,const uint32_t* w,uint32_t* o,unsigned rows) {
    for(unsigned d=0;d<rows;++d,in+=512,w+=256,o+=256)
        for(unsigned k=0;k<128;k+=8) {
            const int16x8x4_t x=vld4q_s16(in+4*k); // re/im of samples 2k.., then of 2k+1..
            const uint32x4_t e0=vld1q_u32(w+k),e1=vld1q_u32(w+k+4),f0=vld1q_u32(w+128+k),f1=vld1q_u32(w+132+k);
            store8(o+k,window8(x.val[0],e0,e1),window8(x.val[1],e0,e1));
            store8(o+128+k,window8(x.val[2],f0,f1),window8(x.val[3],f0,f1));
        }
}
} // namespace split_neon
#pragma GCC pop_options
#endif
class Pipeline { public:
    using Cell=FftReal[2];
    void* library=nullptr;
    void* (*allocate)(size_t)=nullptr;
    void (*release)(void*)=nullptr;
    void* (*make_plan)(int,int,Cell*,Cell*,int,unsigned)=nullptr;
    void (*execute)(void*)=nullptr;
    void (*destroy)(void*)=nullptr;
    void* plan=nullptr;
    Cell* fft_in=nullptr;
    Cell* fft_out=nullptr;
    std::string plan_text;
    bool neon_plan=false;
    // S3a-1: M chirps (Doppler) x N samples (range). Float32 input stays 128x128.
    unsigned M=128,N=128,cells=16384;
    unsigned split_d=1,split_r=1; // pl/model: number of 128-point blocks per axis
    std::array<fft128_sample,16384> weighted{};
    std::vector<uint32_t> packed,spectrum,sub_in,sub_out;
    std::vector<double> window_d,window_r;
    std::vector<uint32_t> adc_weights;
    std::vector<int> tw_d_re,tw_d_im,tw_r_re,tw_r_im; // Q15 twiddles of length M and N (k < L/2)
    std::vector<int16_t> tw_r16_re,tw_r16_im; // S3a-3b: the same range twiddles as int16 for combine_tw
    mutable std::vector<double> powers;
    mutable bool powers_from_integer=false; // pl/model: double powers are filled only when power() is read
    std::vector<uint32_t> ipowers;
    radar::CaCfar cfar;
    std::string backend;
#ifdef __linux__
    int fd=-1;
    std::unique_ptr<fft128_dma_frame_request> request;
#endif
    template<class T> void symbol(T& out,const char* name) {
#ifdef _WIN32
        auto address=GetProcAddress(static_cast<HMODULE>(library),name);
        static_assert(sizeof(out)==sizeof(address),"Windows function pointer size");
        std::memcpy(&out,&address,sizeof(out));
#else
        out=reinterpret_cast<T>(dlsym(library,name));
#endif
        if(!out) throw std::runtime_error(std::string("Missing FFTW symbol: ")+name);
    }
    void close() {
        if(plan) destroy(plan);
        if(fft_in) release(fft_in);
        if(fft_out) release(fft_out);
        if(library) {
#ifdef _WIN32
            FreeLibrary(static_cast<HMODULE>(library));
#else
            dlclose(library);
#endif
        }
#ifdef __linux__
        if(fd>=0) ::close(fd);
#endif
    }
public:
    Pipeline(const std::string& kind,bool hann,const std::string& fftw,
             bool measure=false,bool require_neon=false,unsigned pulses=128,unsigned samples=128)
        :M(pulses),N(samples),cells(pulses*samples),split_d(pulses/128),split_r(samples/128),
         cfar(int(pulses),int(samples)),backend(kind) {
        if(!valid_shape(M,N)) throw std::runtime_error("Unsupported frame shape");
        packed.resize(cells);spectrum.resize(cells);powers.resize(cells);ipowers.resize(cells);adc_weights.resize(cells);
        if(split_d*split_r>1){sub_in.resize(16384);sub_out.resize(16384);}
        auto hann_double=[&](unsigned L){std::vector<double> w(L);
            for(unsigned i=0;i<L;++i) w[i]=hann ? 0.5-0.5*std::cos(2*3.14159265358979323846*i/(L-1)) : 1;
            return w;};
        window_d=hann_double(M);window_r=hann_double(N);
        const auto hq_d=adc_hann_q15_table(M),hq_r=adc_hann_q15_table(N);
        for(unsigned d=0;d<M;++d)for(unsigned r=0;r<N;++r)
            adc_weights[d*N+(split_r==2?(r&1)*128+(r>>1):r)]=hann ? hq_d[d]*hq_r[r] : (1U<<30);
        twiddles(M,tw_d_re,tw_d_im);twiddles(N,tw_r_re,tw_r_im);
        tw_r16_re.assign(tw_r_re.begin(),tw_r_re.end());tw_r16_im.assign(tw_r_im.begin(),tw_r_im.end());
        try {
            if(backend=="ps") {
#ifdef _WIN32
                library=LoadLibraryA(fftw.c_str());
#else
                const char* fallback=sizeof(FftReal)==4?"libfftw3f.so.3":"libfftw3.so.3";
                library=dlopen(fftw.empty()?fallback:fftw.c_str(),RTLD_NOW|RTLD_LOCAL);
#endif
                if(!library) throw std::runtime_error("Cannot load matching FFTW precision; use --fftw-lib");
                auto load=[&](auto& target,const char* name) {
                    auto full=std::string(fftw_prefix)+name;symbol(target,full.c_str());
                };
                load(allocate,"malloc");load(release,"free");
                load(make_plan,"plan_dft_2d");load(execute,"execute");load(destroy,"destroy_plan");
                // FFTW-aligned storage permits SIMD plans. Planning stays before warmup/READY.
                fft_in=static_cast<Cell*>(allocate(size_t(cells)*sizeof(Cell)));
                fft_out=static_cast<Cell*>(allocate(size_t(cells)*sizeof(Cell)));
                if(!fft_in || !fft_out)throw std::bad_alloc();
                std::memset(fft_in,0,size_t(cells)*sizeof(Cell));
                std::memset(fft_out,0,size_t(cells)*sizeof(Cell));
                if(measure) {
                    void (*limit)(double)=nullptr;load(limit,"set_timelimit");limit(2.0);
                }
                plan=make_plan(int(M),int(N),fft_in,fft_out,-1,measure?0U:64U);
                if(!plan) throw std::runtime_error("Cannot create FFTW plan");
#ifdef _WIN32
                // Portable tests may load a DLL using a different C runtime.
                // Do not transfer malloc-owned diagnostic strings across that boundary.
                plan_text="Plan text unavailable for Windows DLL runtime boundary";
#else
                char* (*describe)(void*)=nullptr;load(describe,"sprint_plan");
                // FFTW sprint_plan uses ordinary malloc, not fftw_malloc.
                std::unique_ptr<char,void(*)(void*)> description(describe(plan),std::free);
                if(!description)throw std::runtime_error("Cannot describe FFTW plan");
                plan_text=description.get();
#endif
                std::string lower=plan_text;
                std::transform(lower.begin(),lower.end(),lower.begin(),
                    [](unsigned char c){return static_cast<char>(std::tolower(c));});
                neon_plan=lower.find("neon")!=std::string::npos;
                if(require_neon && !neon_plan)throw std::runtime_error("Required NEON FFTW plan is absent");
            } else if(backend=="pl") {
#ifdef __linux__
                static_assert(sizeof(fft128_dma_frame_header)==112,"ABI8 header");
                static_assert(sizeof(fft128_dma_frame_request)==131280,"ABI8 request");
                static_assert(offsetof(fft128_dma_frame_request,input)==112,"ABI8 input");
                static_assert(offsetof(fft128_dma_frame_request,output)==65648,"ABI8 output");
                request=std::make_unique<fft128_dma_frame_request>();
                fd=open("/dev/fft128-dma-frame",O_RDWR);
                if(fd<0) throw std::runtime_error("Cannot open /dev/fft128-dma-frame");
#else
                throw std::runtime_error("PL backend requires Linux and E14 ABI8 device");
#endif
            } else if(backend!="model") throw std::runtime_error("backend must be ps, pl or model");
        } catch(...) { close(); throw; }
    }
    ~Pipeline(){close();}
    Pipeline(const Pipeline&)=delete;
    Pipeline& operator=(const Pipeline&)=delete;
    const std::string& fftw_plan() const {return plan_text;}
    bool uses_neon() const {return neon_plan;}
    unsigned pulses() const {return M;}
    unsigned samples() const {return N;}
    unsigned bins() const {return cells;}
    void prepare(const fft128_sample* input) {
        if(M!=128 || N!=128) throw std::runtime_error("Float32 input is 128x128 only");
        if(backend=="ps") {
            for(int d=0;d<128;++d)for(int r=0;r<128;++r) {
                int i=d*128+r;double w=window_d[d]*window_r[r];
                fft_in[i][0]=input[i].real*w;fft_in[i][1]=input[i].imag*w;
            }
            return;
        }
        for(int d=0;d<128;++d) for(int r=0;r<128;++r) {
            int i=d*128+r; double w=window_d[d]*window_r[r];
            double re=input[i].real*w,im=input[i].imag*w;
            // S1c contract: window -> float32 wire rounding -> magnitude Q15.
            weighted[i]={static_cast<float>(re),static_cast<float>(im)};
        }
        if(fft128_quantize(weighted.data(),packed.data(),&scale))
            throw std::runtime_error("Q15 quantization failed");
    }
    void prepare_adc16(const Iq16* input) {
        scale=1; // ADC codes directly map to ABI8 signed Q15 codes; no frame gain.
        if(backend=="ps") {
            for(unsigned d=0;d<M;++d)for(unsigned r=0;r<N;++r) {
                size_t i=size_t(d)*N+r;double w=window_d[d]*window_r[r];
                fft_in[i][0]=double(input[i].real)*w;
                fft_in[i][1]=double(input[i].imag)*w;
            }
        } else {
            // S3a-1: local pointers/count so the loop matches the S3a-0 fixed-size codegen.
            const uint32_t* const weights=adc_weights.data();uint32_t* const out=packed.data();
#ifdef STREAM128_SPLIT_NEON
            // S3a-3b: split shapes (cells > 16384) use the NEON window; 128x128 keeps the S3a-0 scalar loop.
            if(cells>16384) {
                const int16_t* const raw=reinterpret_cast<const int16_t*>(input);
                if(split_r==1) split_neon::prepare_plain(raw,weights,out,cells);
                else split_neon::prepare_deint256(raw,weights,out,M);
                return;
            }
#endif
            if(split_r==1) {
                const unsigned count=cells;
                for(unsigned i=0;i<count;++i)
                    out[i]=adc_pack(adc_window(input[i].real,weights[i]),
                                    adc_window(input[i].imag,weights[i]));
            } else {
                // S3a-3b: N=256 rows are stored deinterleaved (sample 2k+q at q*128+k, weights permuted the same
                // way in the constructor), so each range block is a contiguous 128-word run for transform().
                const unsigned rows=M;
                for(unsigned d=0;d<rows;++d) {
                    const Iq16* const in=input+size_t(d)*256;const uint32_t* const w=weights+size_t(d)*256;
                    uint32_t* const o=out+size_t(d)*256;
                    for(unsigned k=0;k<128;++k) {
                        o[k]=adc_pack(adc_window(in[2*k].real,w[k]),adc_window(in[2*k].imag,w[k]));
                        o[128+k]=adc_pack(adc_window(in[2*k+1].real,w[128+k]),adc_window(in[2*k+1].imag,w[128+k]));
                    }
                }
            }
        }
    }
    double scale=1;
    void transform() {
        if(backend=="ps") {execute(plan);return;}
        if(split_d*split_r==1) {transform128(packed.data(),spectrum.data());return;}
        // S3a-1 method A: decimation in time. Block (p,q) holds chirps d%split_d==p and samples
        // r%split_r==q; its 128x128 integer spectrum (E14 or model: range then Doppler) is placed at the
        // bit-reversed block position, then the remaining radix-2 DIT stages run with the same Q15 butterfly
        // (floor /2 and saturation per stage): Doppler stages first, then range stages.
        // S3a-2b: blocks are gathered straight into the E14 request input (pl) and placed straight from its
        // output, and the butterfly decodes/packs inline with an arithmetic-shift floor (same results).
        const unsigned bits_d=split_d==4?2:split_d==2?1:0,bits_r=split_r==2?1:0;
        // S3a-3b: packed holds each range block contiguously (see prepare_adc16), and when there is no Doppler
        // split the single range stage (L=256, twiddle index j) runs while block 1 is read from the block output.
        const bool fuse_r=split_d==1 && split_r==2;
        uint32_t* const s=spectrum.data();
        for(unsigned p=0;p<split_d;++p) for(unsigned q=0;q<split_r;++q) {
            uint32_t* const block=block_input();
            for(unsigned d=0;d<128;++d) {
                const uint32_t* src=packed.data()+size_t(d*split_d+p)*N+q*128;
                std::copy(src,src+128,block+d*128);
            }
            const uint32_t* const result=run_block();
            const unsigned P=reverse_bits(p,bits_d),Q=reverse_bits(q,bits_r);
            if(fuse_r && q==1) {
                for(unsigned d=0;d<128;++d) {
                    uint32_t* const row=s+size_t(d)*256;
                    combine_tw(row,row+128,result+d*128,tw_r16_re.data(),tw_r16_im.data(),128);
                }
            } else
                for(unsigned d=0;d<128;++d)
                    std::copy(result+d*128,result+d*128+128,s+size_t(P*128+d)*N+Q*128);
        }
        if(fuse_r) return;
        for(unsigned half=128;half<M;half*=2)
            for(unsigned base=0;base<M;base+=2*half)
                for(unsigned j=0;j<half;++j) {
                    const unsigned t=j*M/(2*half);
                    combine_const(s+size_t(base+j)*N,s+size_t(base+j+half)*N,tw_d_re[t],tw_d_im[t],N);
                }
        // N <= 256 (valid_shape), so the range side has one stage: half=128, twiddle index j.
        if(split_r>1)
            for(unsigned d=0;d<M;++d) {
                uint32_t* const row=s+size_t(d)*N;
                combine_tw(row,row+128,row+128,tw_r16_re.data(),tw_r16_im.data(),128);
            }
    }
    const std::vector<radar::CfarPeak>& detect() {
        if(backend=="ps") {
            // Same expression as spectrum_at() for ps, without the per-cell backend string compare.
            // cells is a power of two, so *(1/cells) equals /cells exactly (the S3a-0 /16384 compiled to this).
            const FftReal inv=FftReal(1)/FftReal(cells);
            for(unsigned i=0;i<cells;++i) {
                const double re=fft_out[i][0]*inv,im=fft_out[i][1]*inv;
                powers[i]=re*re+im*im;
            }
            powers_from_integer=false;
            return cfar.detect(powers);
        }
        // S3a-0: integer Q15 words decoded inline (same sign extension as fft128_real/imag);
        // re^2+im^2 <= 2^31 is exact in uint32 and in double.
        for(unsigned i=0;i<cells;++i) {
            const uint32_t w=spectrum[i];
            const int32_t re=int16_t(uint16_t(w)),im=int16_t(uint16_t(w>>16));
            ipowers[i]=uint32_t(re*re)+uint32_t(im*im);
        }
        powers_from_integer=true;
        return cfar.detect_integer(ipowers.data());
    }
    const std::vector<double>& power() const {
        if(powers_from_integer) {
            for(unsigned i=0;i<cells;++i) powers[i]=double(ipowers[i]);
            powers_from_integer=false;
        }
        return powers;
    }
    fft128_sample spectrum_at(size_t i) const {
        const FftReal inv=FftReal(1)/FftReal(cells);
        return backend=="ps" ? fft128_sample{fft_out[i][0]*inv,fft_out[i][1]*inv} :
            fft128_sample{double(fft128_real(spectrum[i])),double(fft128_imag(spectrum[i]))};
    }
public:
    static unsigned reverse_bits(unsigned v,unsigned bits){unsigned r=0;for(unsigned b=0;b<bits;++b)r=(r<<1)|((v>>b)&1);return r;}
    static void twiddles(unsigned L,std::vector<int>& re,std::vector<int>& im) {
        // Same construction as fft128_model for L=128: lrint(32768*cos/sin(-2*pi*k/L)), saturated to Q15.
        const double pi=3.14159265358979323846;
        re.resize(L/2);im.resize(L/2);
        for(unsigned k=0;k<L/2;++k) {
            long r=std::lrint(32768*std::cos(-2*pi*k/L)),i=std::lrint(32768*std::sin(-2*pi*k/L));
            re[k]=r>32767?32767:r<-32768?-32768:int(r);im[k]=i>32767?32767:i<-32768?-32768:int(i);
        }
    }
    // S3a-2b: the fft128_model butterfly, a=sat(floor((A*2^15+P)/2^16)), b=sat(floor((A*2^15-P)/2^16)),
    // in int32 only (the int64 /,% were library calls on ARM32). Each product |br*wr| etc. <= 2^30 fits int32.
    // With P = 2^15*h + l (0 <= l < 2^15): floor((A*2^15+P)/2^16) = (A+h)>>1 and
    // floor((A*2^15-P)/2^16) = (A-h-(l!=0))>>1 (arithmetic shift = floor). h and l of P = p1-p2 or p1+p2
    // come from the products' own 15-bit splits with a borrow/carry. Checked against the int64 form by
    // tests/butterfly_s3a2_equiv.cpp and the split-path dumps (bench_s3a2).
    static inline uint32_t sat16(int32_t v) {
        return uint32_t(uint16_t(int16_t(v>32767?32767:v<-32768?-32768:v)));
    }
    static inline void butterfly(uint32_t& a,uint32_t& b,int32_t wr,int32_t wi) {
        const uint32_t x=a,y=b;
        const int32_t ar=int16_t(uint16_t(x)),ai=int16_t(uint16_t(x>>16));
        const int32_t br=int16_t(uint16_t(y)),bi=int16_t(uint16_t(y>>16));
        const int32_t p1=br*wr,p2=bi*wi,p3=br*wi,p4=bi*wr;
        // real: P = p1 - p2
        const int32_t l1=p1&0x7fff,l2=p2&0x7fff;
        const int32_t hr=(p1>>15)-(p2>>15)-(l1<l2),lr=(l1-l2)&0x7fff;
        // imaginary: P = p3 + p4
        const int32_t l3=p3&0x7fff,l4=p4&0x7fff,s=l3+l4;
        const int32_t hi=(p3>>15)+(p4>>15)+(s>>15),li=s&0x7fff;
        a=sat16((ar+hr)>>1)|(sat16((ai+hi)>>1)<<16);
        b=sat16((ar-hr-(lr!=0))>>1)|(sat16((ai-hi-(li!=0))>>1)<<16);
    }
    // S3a-3b: one combine row, a[k],bi[k] -> a[k],bo[k] for k<n (n a multiple of 8): NEON on ARM, else scalar.
    static void combine_tw(uint32_t* a,uint32_t* bo,const uint32_t* bi,const int16_t* wr,const int16_t* wi,unsigned n) {
#ifdef STREAM128_SPLIT_NEON
        split_neon::rows_tw(a,bo,bi,wr,wi,n);
#else
        for(unsigned k=0;k<n;++k) {uint32_t x=a[k],y=bi[k];butterfly(x,y,wr[k],wi[k]);a[k]=x;bo[k]=y;}
#endif
    }
    static void combine_const(uint32_t* a,uint32_t* b,int32_t wr,int32_t wi,unsigned n) {
#ifdef STREAM128_SPLIT_NEON
        split_neon::rows_const(a,b,int16_t(wr),int16_t(wi),n);
#else
        for(unsigned k=0;k<n;++k) butterfly(a[k],b[k],wr,wi);
#endif
    }
    // S3a-2b split path: the 128x128 block buffer to fill, then run it and return the block spectrum.
    uint32_t* block_input() {
#ifdef __linux__
        if(backend=="pl") return request->input;
#endif
        return sub_in.data();
    }
    const uint32_t* run_block() {
        if(backend=="model") {
            if(fft128_process(sub_in.data(),sub_out.data(),fft128_model,nullptr))
                throw std::runtime_error("Integer software model failed");
            return sub_out.data();
        }
#ifdef __linux__
        auto& m=request->meta; m={};
        m.abi=FFT128_DMA_FRAME_ABI;m.timeout_ms=1000;m.frame_words=16384;
        if(ioctl(fd,FFT128_DMA_FRAME_RUN,request.get())<0)
            throw std::runtime_error("E14 frame ioctl failed");
        if(m.abi!=8 || m.core_count!=1 || m.status!=2 || m.completed_ffts!=256 ||
           m.input_count!=16384 || m.output_count!=16384)
            throw std::runtime_error("E14 frame completion mismatch");
        return request->output;
#else
        throw std::runtime_error("PL backend requires Linux and E14 ABI8 device");
#endif
    }
    void transform128(const uint32_t* in,uint32_t* out) {
        if(backend=="model") {
            if(fft128_process(in,out,fft128_model,nullptr))
                throw std::runtime_error("Integer software model failed");
            return;
        }
#ifdef __linux__
        auto& m=request->meta; m={};
        m.abi=FFT128_DMA_FRAME_ABI;m.timeout_ms=1000;m.frame_words=16384;
        std::copy(in,in+16384,request->input);
        if(ioctl(fd,FFT128_DMA_FRAME_RUN,request.get())<0)
            throw std::runtime_error("E14 frame ioctl failed");
        if(m.abi!=8 || m.core_count!=1 || m.status!=2 || m.completed_ffts!=256 ||
           m.input_count!=16384 || m.output_count!=16384)
            throw std::runtime_error("E14 frame completion mismatch");
        std::copy(std::begin(request->output),std::end(request->output),out);
#else
        (void)in;(void)out;
#endif
    }
};
} // namespace stream128
