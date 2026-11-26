// S3a-0 candidate comparison: CA-CFAR threshold layouts and ADC window rounding on real model spectra.
// Every candidate must reproduce CaCfar::detect thresholds/peaks and adc_window bit-for-bit before timing counts.
#include "../cfar_ca.hpp"
#include "../stream_adc16.hpp"
extern "C" {
#include "../../fft128/native_core.h"
}
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>
#ifdef __linux__
#include <sched.h>
#endif
using namespace stream128;
static double now_us(){return std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now().time_since_epoch()).count();}
template<class F> static double med(F f,int reps){std::vector<double> v;for(int k=0;k<reps+10;++k){double t=now_us();f();double u=now_us();if(k>=10)v.push_back(u-t);}
    std::sort(v.begin(),v.end());return v[v.size()/2];}
constexpr int N=128,HD=10,HR=10,GD=2,GR=2;
// Separable column sums (Doppler wrap) + per-row 1D range prefix. T is uint64_t or double (both exact here).
template<class T> struct Sep {
    std::vector<T> co=std::vector<T>(N),cg=std::vector<T>(N),so=std::vector<T>(N+1),sg=std::vector<T>(N+1);
    int ro0[N],ro1[N],rg0[N],rg1[N];
    Sep(){for(int r=0;r<N;++r){ro0[r]=std::max(0,r-HR);ro1[r]=std::min(N,r+HR+1);rg0[r]=std::max(0,r-GR);rg1[r]=std::min(N,r+GR+1);}}
    template<class P> void run(const P* p,const double* scale,double* th){
        std::fill(co.begin(),co.end(),T(0));std::fill(cg.begin(),cg.end(),T(0));
        for(int dd=-HD;dd<=HD;++dd){const P* row=p+size_t((dd+N)%N)*N;for(int r=0;r<N;++r)co[r]+=T(row[r]);}
        for(int dd=-GD;dd<=GD;++dd){const P* row=p+size_t((dd+N)%N)*N;for(int r=0;r<N;++r)cg[r]+=T(row[r]);}
        for(int d=0;d<N;++d){
            if(d){const P* add=p+size_t((d+HD)%N)*N,*sub=p+size_t((d-1-HD+N)%N)*N;
                  const P* gadd=p+size_t((d+GD)%N)*N,*gsub=p+size_t((d-1-GD+N)%N)*N;
                  for(int r=0;r<N;++r){co[r]+=T(add[r]);co[r]-=T(sub[r]);cg[r]+=T(gadd[r]);cg[r]-=T(gsub[r]);}}
            T a=0,b=0;so[0]=0;sg[0]=0;
            for(int r=0;r<N;++r){a+=co[r];so[r+1]=a;b+=cg[r];sg[r+1]=b;}
            double* t=th+size_t(d)*N;
            for(int r=0;r<N;++r){T tot=(so[ro1[r]]-so[ro0[r]])-(sg[rg1[r]]-sg[rg0[r]]);
                t[r]=conv(tot)*scale[r];}
        }
    }
    static double conv(uint64_t x){return double(uint32_t(x>>32))*4294967296.0+double(uint32_t(x));}
    static double conv(double x){return x;}
};
int main(int argc,char** argv){try{
#ifdef __linux__
    cpu_set_t set;CPU_ZERO(&set);CPU_SET(1,&set);std::printf("S3A0_PIN cpu1=%s\n",sched_setaffinity(0,sizeof(set),&set)==0?"ok":"failed");
#endif
    if(argc<3)throw std::runtime_error("FIXTURE REPS");
    int reps=std::atoi(argv[2]);
    std::ifstream f(argv[1],std::ios::binary);std::vector<unsigned char> b((std::istreambuf_iterator<char>(f)),{});
    if(b.size()!=65576)throw std::runtime_error("fixture");
    std::vector<Iq16> x(16384);std::vector<uint32_t> w(16384),packed(16384),spec(16384),ip(16384);
    for(size_t i=0;i<16384;++i){const unsigned char* q=b.data()+40+4*i;x[i].real=int16_t(uint16_t(q[0]<<8|q[1]));x[i].imag=int16_t(uint16_t(q[2]<<8|q[3]));}
    for(int d=0;d<N;++d)for(int r=0;r<N;++r)w[d*N+r]=adc_hann_q15[d]*adc_hann_q15[r];
    std::vector<double> wd(16384);for(size_t i=0;i<16384;++i)wd[i]=double(w[i])*(1.0/1073741824.0);
    for(size_t i=0;i<16384;++i)packed[i]=adc_pack(adc_window(x[i].real,w[i]),adc_window(x[i].imag,w[i]));
    if(fft128_process(packed.data(),spec.data(),fft128_model,nullptr))throw std::runtime_error("model");
    std::vector<double> pw(16384);
    for(size_t i=0;i<16384;++i){int32_t re=int16_t(uint16_t(spec[i])),im=int16_t(uint16_t(spec[i]>>16));ip[i]=uint32_t(re*re)+uint32_t(im*im);pw[i]=double(ip[i]);}
    radar::CaCfar ref(N,N),cur(N,N);
    auto peaks=ref.detect(pw);const auto& rt=ref.thresholds();
    auto peaks2=cur.detect_integer(ip.data());
    bool ok=peaks.size()==peaks2.size() && std::memcmp(rt.data(),cur.thresholds().data(),16384*8)==0;
    std::vector<double> scale(N);
    for(int r=0;r<N;++r){int ow=std::min(N,r+HR+1)-std::max(0,r-HR),gw=std::min(N,r+GR+1)-std::max(0,r-GR);
        scale[r]=std::pow(1e-6,-1.0/((2*HD+1)*ow-(2*GD+1)*gw))-1.0;}
    std::vector<double> th(16384);Sep<uint64_t> su;Sep<double> sd;
    su.run(ip.data(),scale.data(),th.data());bool ok_su=std::memcmp(th.data(),rt.data(),16384*8)==0;
    std::fill(th.begin(),th.end(),-1.0);sd.run(pw.data(),scale.data(),th.data());bool ok_sd=std::memcmp(th.data(),rt.data(),16384*8)==0;
    // ADC window via exact double product + 1.5*2^52 round-half-even (default rounding mode, no fast-math).
    std::vector<uint32_t> pk2(16384);
    auto magic=[&](){volatile double M=6755399441055744.0;double m=M;for(size_t i=0;i<16384;++i){
        double a=double(x[i].real)*wd[i],c=double(x[i].imag)*wd[i];
        int ra=int32_t((a+m)-m),rc=int32_t((c+m)-m);pk2[i]=uint32_t(uint16_t(ra))|(uint32_t(uint16_t(rc))<<16);}};
    magic();bool ok_magic=pk2==packed;
    std::printf("S3A0_EXACT detect_integer=%d sep_u64=%d sep_double=%d window_magic=%d peaks=%zu\n",ok,ok_su,ok_sd,ok_magic,peaks.size());
    std::vector<uint32_t> pk1(16384);
    std::printf("S3A0_MICRO window_int_us=%.1f\n",med([&]{for(size_t i=0;i<16384;++i)pk1[i]=adc_pack(adc_window(x[i].real,w[i]),adc_window(x[i].imag,w[i]));},reps));
    std::printf("S3A0_MICRO window_magic_us=%.1f\n",med(magic,reps));
    std::printf("S3A0_MICRO power_decode_us=%.1f\n",med([&]{for(size_t i=0;i<16384;++i){int32_t re=int16_t(uint16_t(spec[i])),im=int16_t(uint16_t(spec[i]>>16));ip[i]=uint32_t(re*re)+uint32_t(im*im);pw[i]=double(ip[i]);}},reps));
    std::printf("S3A0_MICRO cfar_double_ref_us=%.1f\n",med([&]{ref.detect(pw);},reps));
    std::printf("S3A0_MICRO cfar_detect_integer_us=%.1f\n",med([&]{cur.detect_integer(ip.data());},reps));
    std::printf("S3A0_MICRO sep_u64_threshold_us=%.1f\n",med([&]{su.run(ip.data(),scale.data(),th.data());},reps));
    std::printf("S3A0_MICRO sep_double_threshold_us=%.1f\n",med([&]{sd.run(pw.data(),scale.data(),th.data());},reps));
    std::printf("S3A0_MICRO compare_scan_us=%.1f\n",med([&]{size_t n=0;for(size_t i=0;i<16384;++i)n+=pw[i]>rt[i];if(n==999999)std::puts("");},reps));
    return ok&&ok_su&&ok_sd?0:2;
}catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 1;}}
