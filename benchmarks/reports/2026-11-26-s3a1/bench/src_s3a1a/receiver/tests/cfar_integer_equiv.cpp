// S3a-0: CaCfar::detect_integer must equal CaCfar::detect bit-for-bit (thresholds, peaks) for integer powers.
// Shapes include Doppler windows wider than nd (wrap repeats rows), non-square and 256/512 sizes.
#include "../cfar_ca.hpp"
#include <cstdio>
#include <cstring>
#include <random>
int main() {
    struct S{int nd,nr,gd,gr,td,tr;};
    const S shapes[]={{128,128,2,2,8,8},{256,128,2,2,8,8},{128,256,2,2,8,8},{256,256,2,2,8,8},{512,512,2,2,8,8},
                      {16,8,2,2,8,8},{5,40,1,2,3,8},{3,3,0,0,1,1},{64,32,0,3,4,1}};
    std::mt19937 rng(20261126);
    int cases=0;
    for(const S& s:shapes) for(int mode=0;mode<5;++mode) {
        size_t n=size_t(s.nd)*s.nr;
        std::vector<uint32_t> ip(n);std::vector<double> p(n);
        for(size_t i=0;i<n;++i) {
            uint32_t v;
            switch(mode){
                case 0: v=rng()%(1U<<31)+(rng()&1); break;               // full range incl. 2^31
                case 1: v=2147483648U; break;                            // all max
                case 2: v=0; break;                                      // all zero (threshold 0)
                case 3: {int32_t re=int16_t(rng()),im=int16_t(rng()>>16);re>>=8;im>>=8;v=uint32_t(re*re)+uint32_t(im*im);} break;
                default: v=(rng()%97==0)?uint32_t(rng()%(1U<<31)):uint32_t(rng()%64); // sparse peaks on low floor
            }
            ip[i]=v;p[i]=double(v);
        }
        radar::CaCfar a(s.nd,s.nr,s.gd,s.gr,s.td,s.tr),b(s.nd,s.nr,s.gd,s.gr,s.td,s.tr);
        const auto& pa=a.detect(p);const auto& pb=b.detect_integer(ip.data());
        bool ok=std::memcmp(a.thresholds().data(),b.thresholds().data(),n*sizeof(double))==0 && pa.size()==pb.size();
        for(size_t k=0;ok&&k<pa.size();++k)
            ok=pa[k].doppler==pb[k].doppler&&pa[k].range==pb[k].range&&
               std::memcmp(&pa[k].power,&pb[k].power,8)==0&&std::memcmp(&pa[k].threshold,&pb[k].threshold,8)==0;
        if(!ok){std::printf("CFAR_INTEGER_MISMATCH nd=%d nr=%d mode=%d\n",s.nd,s.nr,mode);return 1;}
        ++cases;
    }
    std::printf("CFAR_INTEGER_EQUIV_PASS cases=%d\n",cases);
    return 0;
}
