// Fixed ADC numeric edge cases, independent of the FFT and operating system.
#include "../stream_adc16.hpp"
#include <iostream>
#include <stdexcept>
int main() {
    using namespace stream128;
    auto require=[](bool ok){if(!ok)throw std::runtime_error("ADC numeric contract");};
    for(int v : {-32768,-32767,-3,-1,0,1,3,32767}) {
        require(adc_window(static_cast<int16_t>(v),1U<<30)==v);
        require(adc_window(static_cast<int16_t>(v),0)==0);
    }
    require(adc_window(1,1U<<29)==0);
    require(adc_window(3,1U<<29)==2);
    require(adc_window(5,1U<<29)==2);
    require(adc_window(-1,1U<<29)==0);
    require(adc_window(-3,1U<<29)==-2);
    require(adc_window(-5,1U<<29)==-2);
    require(adc_pack(-32768,32767)==0x7fff8000U);
    require(adc_pack(32767,-32768)==0x80007fffU);
    std::cout<<"ADC16_NUMERIC_PASS\n";
}
