// S2a-int16 profile1: signed ADC codes; no frame normalization.
#pragma once
#include <array>
#include <cstdint>
namespace stream128 {
struct Iq16 { int16_t real,imag; };
static_assert(sizeof(Iq16)==4,"interleaved signed16 IQ");
constexpr uint32_t adc_profile_id=1;
constexpr unsigned adc_bits=16;
constexpr double adc_scale=1600000.0;
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
inline int16_t adc_window(int16_t value,uint32_t weight_q30) {
    int64_t product=static_cast<int64_t>(value)*weight_q30;
    uint64_t magnitude=static_cast<uint64_t>(product<0?-product:product);
    uint64_t rounded=magnitude>>30;
    uint64_t remainder=magnitude&((uint64_t(1)<<30)-1);
    if(remainder>(uint64_t(1)<<29) || (remainder==(uint64_t(1)<<29) && (rounded&1))) ++rounded;
    int64_t signed_value=product<0?-static_cast<int64_t>(rounded):static_cast<int64_t>(rounded);
    return static_cast<int16_t>(signed_value); // weights<=1 preserve signed16 range
}
inline uint32_t adc_pack(int16_t real,int16_t imag) {
    return uint32_t(static_cast<uint16_t>(real)) | (uint32_t(static_cast<uint16_t>(imag))<<16);
}
} // namespace stream128
