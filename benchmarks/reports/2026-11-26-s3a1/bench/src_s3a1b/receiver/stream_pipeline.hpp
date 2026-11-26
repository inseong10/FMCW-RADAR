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
class Pipeline { public: // bench-only access
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
            adc_weights[d*N+r]=hann ? hq_d[d]*hq_r[r] : (1U<<30);
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
            const unsigned count=cells;
            for(unsigned i=0;i<count;++i)
                out[i]=adc_pack(adc_window(input[i].real,weights[i]),
                                adc_window(input[i].imag,weights[i]));
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
        const unsigned bits_d=split_d==4?2:split_d==2?1:0,bits_r=split_r==2?1:0;
        for(unsigned p=0;p<split_d;++p) for(unsigned q=0;q<split_r;++q) {
            for(unsigned d=0;d<128;++d) {
                const uint32_t* src=packed.data()+size_t(d*split_d+p)*N+q;
                uint32_t* dst=sub_in.data()+d*128;
                for(unsigned r=0;r<128;++r) dst[r]=src[size_t(r)*split_r];
            }
            transform128(sub_in.data(),sub_out.data());
            const unsigned P=reverse_bits(p,bits_d),Q=reverse_bits(q,bits_r);
            for(unsigned d=0;d<128;++d)
                std::copy(sub_out.begin()+d*128,sub_out.begin()+d*128+128,spectrum.begin()+size_t(P*128+d)*N+Q*128);
        }
        for(unsigned half=128;half<M;half*=2)
            for(unsigned base=0;base<M;base+=2*half)
                for(unsigned j=0;j<half;++j) {
                    const unsigned t=j*M/(2*half);
                    uint32_t* a=spectrum.data()+size_t(base+j)*N;uint32_t* b=spectrum.data()+size_t(base+j+half)*N;
                    for(unsigned r=0;r<N;++r) butterfly(a[r],b[r],tw_d_re[t],tw_d_im[t]);
                }
        if(split_r>1)
            for(unsigned d=0;d<M;++d) {
                uint32_t* row=spectrum.data()+size_t(d)*N;
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
private:
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
    static int saturate_q15(int64_t value) { // floor(value/65536) then saturate, as fft128_model
        int64_t q=value/65536;
        if(value<0 && value%65536) --q;
        return q>32767?32767:q<-32768?-32768:int(q);
    }
    static void butterfly(uint32_t& a,uint32_t& b,int wr,int wi) {
        const int64_t ar=fft128_real(a),ai=fft128_imag(a),br=fft128_real(b),bi=fft128_imag(b);
        const int64_t pr=br*wr-bi*wi,pim=br*wi+bi*wr;
        a=fft128_pack(saturate_q15(ar*32768+pr),saturate_q15(ai*32768+pim));
        b=fft128_pack(saturate_q15(ar*32768-pr),saturate_q15(ai*32768-pim));
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
