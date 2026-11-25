// S2a RSPY v2: fixed 128x128, frame identity is explicit; v1 is unchanged.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <stdexcept>
extern "C" {
#include "../fft128/native_core.h"
}

namespace stream128 {
constexpr size_t header_bytes=52, packet_bytes=52+128*8;
inline uint64_t be(const unsigned char* p, unsigned n) {
    uint64_t v=0; for(unsigned i=0;i<n;++i) v=(v<<8)|p[i]; return v;
}
inline double number(const unsigned char* p, bool single) {
    if(single) { uint32_t u=static_cast<uint32_t>(be(p,4)); float v; std::memcpy(&v,&u,4); return v; }
    uint64_t u=be(p,8); double v; std::memcpy(&v,&u,8); return v;
}
struct Packet {
    uint64_t run=0,id=0,sender_ns=0;
    unsigned chirp=0;
    double fs=0;
    std::array<fft128_sample,128> row{};
};
inline Packet decode(const unsigned char* p,size_t n) {
    if(n!=packet_bytes || std::memcmp(p,"RSPY",4) || p[4]!=2 || p[5]!=1 || be(p+6,2)!=0 ||
       be(p+28,4)!=128 || be(p+32,4)!=128 || be(p+24,4)>=128)
        throw std::runtime_error("Invalid RSPY v2 packet");
    Packet r; r.run=be(p+8,8); r.id=be(p+16,8); r.chirp=static_cast<unsigned>(be(p+24,4));
    r.fs=number(p+36,false); r.sender_ns=be(p+44,8);
    if(!r.run || !r.id || !r.sender_ns || !std::isfinite(r.fs) || r.fs<=0)
        throw std::runtime_error("Invalid frame metadata");
    for(size_t i=0;i<128;++i) {
        r.row[i]={number(p+52+i*8,true),number(p+56+i*8,true)};
        if(!std::isfinite(r.row[i].real) || !std::isfinite(r.row[i].imag))
            throw std::runtime_error("Non-finite IQ");
    }
    return r;
}
struct Frame {
    uint64_t id=0,sender_ns=0,first_ns=0,complete_ns=0,first_kernel_ns=0;
    double fs=0;
    std::array<bool,128> seen{};
    unsigned count=0;
    std::array<fft128_sample,16384> iq{};
    bool add(const Packet& p) {
        if(p.id!=id || (count && (fs!=p.fs || sender_ns!=p.sender_ns)))
            throw std::runtime_error("Inconsistent frame metadata");
        if(seen[p.chirp]) return false;
        fs=p.fs; sender_ns=p.sender_ns; seen[p.chirp]=true; ++count;
        std::copy(p.row.begin(),p.row.end(),iq.begin()+p.chirp*128); return true;
    }
};
} // namespace stream128
