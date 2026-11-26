// S2a-int16 profile1: signed ADC codes; no frame normalization.
#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>
namespace stream128 {
struct Iq16 { int16_t real,imag; };
static_assert(sizeof(Iq16)==4,"interleaved signed16 IQ");
constexpr uint32_t adc_profile_id=1;
constexpr unsigned adc_bits=16;
constexpr double adc_scale=1600000.0;
// S3a-1 frame shapes: M chirps in {128,256,512}, N samples in {128,256} (N=512 exceeds one MTU packet).
inline bool valid_shape(unsigned pulses,unsigned samples) {
    return (pulses==128 || pulses==256 || pulses==512) && (samples==128 || samples==256);
}
// Symmetric Hann h[n]=0.5-0.5*cos(2*pi*n/127), rint(h*32768).
constexpr std::array<uint32_t,128> adc_hann_q15{{
    0,20,80,180,320,499,717,973,1267,1597,1965,2367,2804,3273,3775,4308,
    4871,5461,6078,6721,7387,8075,8784,9511,10255,11014,11786,12569,13362,14162,14967,15776,
    16587,17397,18204,19007,19804,20592,21370,22136,22887,23623,24341,25039,25717,26371,27001,27606,
    28182,28730,29247,29734,30187,30607,30991,31341,31653,31928,32165,32364,32523,32643,32723,32763,
    32763,32723,32643,32523,32364,32165,31928,31653,31341,30991,30607,30187,29734,29247,28730,28182,
    27606,27001,26371,25717,25039,24341,23623,22887,22136,21370,20592,19804,19007,18204,17397,16587,
    15776,14967,14162,13362,12569,11786,11014,10255,9511,8784,8075,7387,6721,6078,5461,4871,
    4308,3775,3273,2804,2367,1965,1597,1267,973,717,499,320,180,80,20,0
}};
// S3a-1: rint(h*32768) for h[n]=0.5-0.5*cos(2*pi*n/(L-1)) (numpy.hanning). L=128 returns the frozen table.
inline std::vector<uint32_t> adc_hann_q15_table(unsigned length) {
    if(length==128) return std::vector<uint32_t>(adc_hann_q15.begin(),adc_hann_q15.end());
    if(length<2) throw std::runtime_error("Hann length");
    std::vector<uint32_t> h(length);
    for(unsigned n=0;n<length;++n)
        h[n]=uint32_t(std::lrint((0.5-0.5*std::cos(2*3.14159265358979323846*n/(length-1)))*32768));
    return h;
}
inline int16_t adc_window(int16_t value,uint32_t weight_q30) {
    // S3a-0: branchless round-half-even of |value|*weight/2^30, then restore the sign with a mask.
    // m=|v|*w < 2^46. q0=floor(m/2^30), rem=m mod 2^30; q0+1 iff rem>2^29, or rem==2^29 with odd q0,
    // i.e. iff rem+(2^29-1)+(q0&1) >= 2^30. 32-bit pieces only, so no sign branch is generated.
    const int32_t v=value,sign=v>>31;
    const uint32_t a=uint32_t((v^sign)-sign);
    const uint64_t m=uint64_t(a)*weight_q30;
    const uint32_t lo=uint32_t(m),hi=uint32_t(m>>32);
    const uint32_t q0=(hi<<2)|(lo>>30);
    const uint32_t q=q0+(((lo&0x3fffffffU)+0x1fffffffU+(q0&1U))>>30);
    return static_cast<int16_t>((int32_t(q)^sign)-sign); // weights<=1 preserve signed16 range
}
inline uint32_t adc_pack(int16_t real,int16_t imag) {
    return uint32_t(static_cast<uint16_t>(real)) | (uint32_t(static_cast<uint16_t>(imag))<<16);
}
} // namespace stream128
