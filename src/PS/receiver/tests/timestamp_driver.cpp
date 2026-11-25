#include "../stream_timestamp.hpp"
#include <array>
#include <iostream>
#include <stdexcept>
int main(){try {
    int32_t old[2]={1510000000,123456789};
    int64_t modern[2]={1510000000,123456789};
    constexpr uint64_t expected=1510000000123456789ULL;
    if(stream128::socket_timestamp_ns(old,sizeof(old))!=expected ||
       stream128::socket_timestamp_ns(modern,sizeof(modern))!=expected)
        throw std::runtime_error("time32/time64 differ");
    modern[0]=2200000000LL;modern[1]=999999999;
    if(stream128::socket_timestamp_ns(modern,sizeof(modern))!=2200000000999999999ULL)
        throw std::runtime_error("time64 beyond 2038");
    for(const auto& bad:std::array<std::array<int64_t,2>,4>{{
            {{-1,0}},{{1,-1}},{{1,1000000000}},{{INT64_MAX,0}}}}) {
        bool rejected=false;
        try{stream128::socket_timestamp_ns(bad.data(),sizeof(bad));}
        catch(const std::runtime_error&){rejected=true;}
        if(!rejected)throw std::runtime_error("invalid timestamp accepted");
    }
    bool rejected=false;
    try{stream128::socket_timestamp_ns(modern,12);}
    catch(const std::runtime_error&){rejected=true;}
    if(!rejected)throw std::runtime_error("invalid layout accepted");
    // Independently derived Linux ARM32 cmsg alignment/header sizes.
    constexpr size_t old_timestamp=20, appended_time64=28, overflow=16;
    if(old_timestamp+overflow>=old_timestamp+appended_time64 ||
       stream128::control_capacity<old_timestamp+appended_time64+overflow)
        throw std::runtime_error("insufficient dual-timestamp capacity");
    std::cout<<"TIMESTAMP_ABI_PASS time32 time64 malformed capacity\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
