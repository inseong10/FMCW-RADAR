// S2a integrated pipeline. No disk spectrum handoff and no hardware fallback.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <memory>
#include <string>
#include <vector>
#include "cfar_ca.hpp"
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
class Pipeline {
    using Cell=double[2];
    void* library=nullptr;
    void* (*make_plan)(int,int,Cell*,Cell*,int,unsigned)=nullptr;
    void (*execute)(void*)=nullptr;
    void (*destroy)(void*)=nullptr;
    void* plan=nullptr;
    std::unique_ptr<Cell[]> fft_in{new Cell[16384]},fft_out{new Cell[16384]};
    std::array<fft128_sample,16384> weighted{};
    std::array<uint32_t,16384> packed{},spectrum{};
    std::array<double,128> window{};
    std::vector<double> powers=std::vector<double>(16384);
    radar::CaCfar cfar{128,128};
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
    Pipeline(const std::string& kind,bool hann,const std::string& fftw):backend(kind) {
        for(int i=0;i<128;++i) window[i]=hann ? 0.5-0.5*std::cos(2*3.14159265358979323846*i/127) : 1;
        try {
            if(backend=="ps") {
#ifdef _WIN32
                library=LoadLibraryA(fftw.c_str());
#else
                library=dlopen(fftw.empty()?"libfftw3.so.3":fftw.c_str(),RTLD_NOW|RTLD_LOCAL);
#endif
                if(!library) throw std::runtime_error("Cannot load double FFTW; use --fftw-lib");
                symbol(make_plan,"fftw_plan_dft_2d"); symbol(execute,"fftw_execute");
                symbol(destroy,"fftw_destroy_plan");
                plan=make_plan(128,128,fft_in.get(),fft_out.get(),-1,64U);
                if(!plan) throw std::runtime_error("Cannot create FFTW ESTIMATE plan");
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
    void prepare(const fft128_sample* input) {
        for(int d=0;d<128;++d) for(int r=0;r<128;++r) {
            int i=d*128+r; double w=window[d]*window[r];
            double re=input[i].real*w,im=input[i].imag*w;
            if(backend=="ps") {fft_in[i][0]=re;fft_in[i][1]=im;}
            // S1c contract: window -> float32 wire rounding -> magnitude Q15.
            else weighted[i]={static_cast<float>(re),static_cast<float>(im)};
        }
        if(backend!="ps" && fft128_quantize(weighted.data(),packed.data(),&scale))
            throw std::runtime_error("Q15 quantization failed");
    }
    double scale=1;
    void transform() {
        if(backend=="ps") execute(plan);
        else if(backend=="model") {
            if(fft128_process(packed.data(),spectrum.data(),fft128_model,nullptr))
                throw std::runtime_error("Integer software model failed");
        } else {
#ifdef __linux__
            auto& m=request->meta; m={};
            m.abi=FFT128_DMA_FRAME_ABI;m.timeout_ms=1000;m.frame_words=16384;
            std::copy(packed.begin(),packed.end(),request->input);
            if(ioctl(fd,FFT128_DMA_FRAME_RUN,request.get())<0)
                throw std::runtime_error("E14 frame ioctl failed");
            if(m.abi!=8 || m.core_count!=1 || m.status!=2 || m.completed_ffts!=256 ||
               m.input_count!=16384 || m.output_count!=16384)
                throw std::runtime_error("E14 frame completion mismatch");
            std::copy(std::begin(request->output),std::end(request->output),spectrum.begin());
#endif
        }
    }
    const std::vector<radar::CfarPeak>& detect() {
        for(int i=0;i<16384;++i) {
            auto z=spectrum_at(i);powers[i]=z.real*z.real+z.imag*z.imag;
        }
        return cfar.detect(powers);
    }
    const std::vector<double>& power() const {return powers;}
    fft128_sample spectrum_at(size_t i) const {
        return backend=="ps" ? fft128_sample{fft_out[i][0]/16384,fft_out[i][1]/16384} :
            fft128_sample{double(fft128_real(spectrum[i])),double(fft128_imag(spectrum[i]))};
    }
};
} // namespace stream128
