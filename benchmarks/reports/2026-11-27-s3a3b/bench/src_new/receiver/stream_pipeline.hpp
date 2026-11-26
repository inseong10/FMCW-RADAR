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
                const int* const wr=tw_r_re.data();const int* const wi=tw_r_im.data();
                for(unsigned d=0;d<128;++d) {
                    uint32_t* const row=s+size_t(d)*256;const uint32_t* const hi=result+d*128;
                    for(unsigned j=0;j<128;++j) {
                        uint32_t x=row[j],y=hi[j];
                        butterfly(x,y,wr[j],wi[j]);
                        row[j]=x;row[128+j]=y;
                    }
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
                    const int32_t wr=tw_d_re[t],wi=tw_d_im[t];
                    uint32_t* const a=s+size_t(base+j)*N;uint32_t* const b=s+size_t(base+j+half)*N;
                    for(unsigned r=0;r<N;++r) butterfly(a[r],b[r],wr,wi);
                }
        if(split_r>1)
            for(unsigned d=0;d<M;++d) {
                uint32_t* const row=s+size_t(d)*N;
                for(unsigned half=128;half<N;half*=2)
                    for(unsigned base=0;base<N;base+=2*half)
                        for(unsigned j=0;j<half;++j) {
                            const unsigned t=j*N/(2*half);
                            butterfly(row[base+j],row[base+j+half],tw_r_re[t],tw_r_im[t]);
                        }
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
