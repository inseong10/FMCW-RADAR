// RSPY v2 float32 and v3 ADC16 are explicit, incompatible wire formats.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <vector>
#include "stream_adc16.hpp"
extern "C" {
#include "../fft128/native_core.h"
}

namespace stream128 {
constexpr size_t header_bytes=52, packet_bytes=52+128*8;
constexpr size_t adc_header_bytes=56, adc_packet_bytes=56+128*4;
// S3a-1: ADC16 frames may be M chirps x N samples (header pulses/samples). Float32 v2 stays 128x128.
constexpr unsigned max_adc_samples=256, max_pulses=512;
constexpr size_t max_packet_bytes=adc_header_bytes+max_adc_samples*4; // >= float packet_bytes
static_assert(max_packet_bytes>=packet_bytes,"receive buffer");
inline size_t adc_packet_size(unsigned samples){return adc_header_bytes+size_t(samples)*4;}

enum class InputFormat { Float32, Adc16 };
inline uint64_t be(const unsigned char* p, unsigned n) {
    uint64_t v=0; for(unsigned i=0;i<n;++i) v=(v<<8)|p[i]; return v;
}
inline double number(const unsigned char* p, bool single) {
    if(single) { uint32_t u=static_cast<uint32_t>(be(p,4)); float v; std::memcpy(&v,&u,4); return v; }
    uint64_t u=be(p,8); double v; std::memcpy(&v,&u,8); return v;
}
struct Packet {
    uint64_t run=0,id=0,sender_ns=0;
    unsigned chirp=0,pulses=128,samples=128;
    double fs=0;
    InputFormat format=InputFormat::Float32;
    uint32_t profile=0;
    std::array<fft128_sample,128> row{};
    std::array<Iq16,max_adc_samples> adc_row{};
};
// The expected shape is a receiver option; packets of any other shape are rejected.
inline Packet decode(const unsigned char* p,size_t n,unsigned pulses=128,unsigned samples=128) {
    if(n<header_bytes) throw std::runtime_error("Truncated RSPY header");
    bool adc=p[4]==3 && p[5]==2;
    bool legacy=p[4]==2 && p[5]==1;
    if(!valid_shape(pulses,samples) || (legacy && (pulses!=128 || samples!=128)))
        throw std::runtime_error("Invalid RSPY v2/v3 packet");
    if((!adc && !legacy) || n!=(adc?adc_packet_size(samples):packet_bytes) || std::memcmp(p,"RSPY",4) || be(p+6,2)!=0 ||
       be(p+28,4)!=pulses || be(p+32,4)!=samples || be(p+24,4)>=pulses)
        throw std::runtime_error("Invalid RSPY v2/v3 packet");
    Packet r; r.run=be(p+8,8); r.id=be(p+16,8); r.chirp=static_cast<unsigned>(be(p+24,4));
    r.pulses=pulses;r.samples=samples;
    r.fs=number(p+36,false); r.sender_ns=be(p+44,8);
    if(!r.run || !r.id || !r.sender_ns || !std::isfinite(r.fs) || r.fs<=0)
        throw std::runtime_error("Invalid frame metadata");
    if(adc) {
        r.format=InputFormat::Adc16;r.profile=static_cast<uint32_t>(be(p+52,4));
        if(r.profile!=adc_profile_id)throw std::runtime_error("Unsupported ADC profile");
        auto signed16=[](const unsigned char* value) {
            int v=static_cast<int>(be(value,2));return static_cast<int16_t>(v>=32768?v-65536:v);
        };
        for(size_t i=0;i<samples;++i)
            r.adc_row[i]={signed16(p+56+i*4),signed16(p+58+i*4)};
    } else {
        for(size_t i=0;i<128;++i) {
            r.row[i]={number(p+52+i*8,true),number(p+56+i*8,true)};
            if(!std::isfinite(r.row[i].real) || !std::isfinite(r.row[i].imag))
                throw std::runtime_error("Non-finite IQ");
        }
    }
    return r;
}
struct Frame {
    uint64_t id=0,sender_ns=0,first_ns=0,complete_ns=0,first_kernel_ns=0;
    double fs=0;
    InputFormat format=InputFormat::Float32;
    uint32_t profile=0;
    unsigned pulses=128,samples=128;
    std::array<bool,max_pulses> seen{};
    unsigned count=0;
    std::vector<fft128_sample> iq;
    std::vector<Iq16> adc_iq;
    bool add(const Packet& p) {
        if(p.chirp>=p.pulses || p.id!=id || (count && (fs!=p.fs || sender_ns!=p.sender_ns || format!=p.format ||
           profile!=p.profile || pulses!=p.pulses || samples!=p.samples)))
            throw std::runtime_error("Inconsistent frame metadata");
        if(seen[p.chirp]) return false;
        if(!count) {
            format=p.format;profile=p.profile;pulses=p.pulses;samples=p.samples;
            if(format==InputFormat::Adc16)adc_iq.resize(size_t(pulses)*samples);else iq.resize(16384);
        }
        fs=p.fs; sender_ns=p.sender_ns; seen[p.chirp]=true; ++count;
        if(format==InputFormat::Adc16)
            std::copy(p.adc_row.begin(),p.adc_row.begin()+samples,adc_iq.begin()+size_t(p.chirp)*samples);
        else std::copy(p.row.begin(),p.row.end(),iq.begin()+p.chirp*128);
        return true;
    }
};
} // namespace stream128
