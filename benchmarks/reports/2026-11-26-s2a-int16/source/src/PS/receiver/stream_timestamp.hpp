// Socket timestamps may contain the old time32 and appended time64 forms.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>
namespace stream128 {
// ARM32: old timestamp cmsg20 + converted time64 cmsg28 + overflow cmsg16.
// Do not size this from just sizeof(timespec) plus one overflow record.
constexpr size_t control_capacity=512;
inline uint64_t socket_timestamp_ns(const void* payload,size_t bytes) {
    int64_t seconds=0,nanos=0;
    if(bytes==8) {
        int32_t fields[2];std::memcpy(fields,payload,sizeof(fields));
        seconds=fields[0];nanos=fields[1];
    } else if(bytes==16) {
        int64_t fields[2];std::memcpy(fields,payload,sizeof(fields));
        seconds=fields[0];nanos=fields[1];
    } else throw std::runtime_error("Unexpected timestamp payload size");
    if(seconds<0 || nanos<0 || nanos>=1000000000 ||
       uint64_t(seconds)>(std::numeric_limits<uint64_t>::max()-uint64_t(nanos))/1000000000ULL)
        throw std::runtime_error("Invalid socket timestamp");
    return uint64_t(seconds)*1000000000ULL+uint64_t(nanos);
}
} // namespace stream128
