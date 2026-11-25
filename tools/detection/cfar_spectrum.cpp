// S1c: the shared S1b CA-CFAR kernel applied to an exported E14 Q15 spectrum.
// CSV IO is outside CFAR timing. This is not an integrated end-to-end benchmark.
#include "../../src/PS/receiver/cfar_ca.hpp"
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#if defined(__linux__)
#include <sched.h>
#endif

int main(int argc,char** argv) {
    try {
        std::string input,output,timings;
        int warmup=0,repeat=1;
        bool cpu0=false;
        for(int i=1;i<argc;++i) {
            std::string key=argv[i];
            if(key=="--cpu0") {cpu0=true;continue;}
            if(i+1>=argc) throw std::runtime_error("Missing value for "+key);
            std::string value=argv[++i];
            if(key=="--input") input=value;
            else if(key=="--output") output=value;
            else if(key=="--timings") timings=value;
            else if(key=="--warmup" || key=="--repeat") {
                size_t end=0;int n=std::stoi(value,&end);
                if(end!=value.size() || n<0 || n>1000000) throw std::runtime_error("Invalid repeat/warmup");
                if(key=="--warmup") warmup=n;else repeat=n;
            } else throw std::runtime_error("Unknown option: "+key);
        }
        if(input.empty() || output.empty() || timings.empty() || repeat<1)
            throw std::runtime_error("Use --input E14.csv --output detections.csv --timings timings.csv [--warmup N --repeat N --cpu0]");
        if(cpu0) {
#if defined(__linux__)
            cpu_set_t set;CPU_ZERO(&set);CPU_SET(0,&set);
            if(sched_setaffinity(0,sizeof(set),&set)) throw std::runtime_error("CPU0 affinity failed");
            std::cout<<"CPU_AFFINITY=0\n";
#else
            throw std::runtime_error("--cpu0 requires Linux");
#endif
        }
        std::ifstream in(input);
        std::string line;
        if(!std::getline(in,line) || line!="doppler_bin_unshifted,range_bin,real_q15,imag_q15")
            throw std::runtime_error("Expected E14 Q15 spectrum CSV header");
        std::vector<double> real(16384),imag(16384),power(16384);
        for(int d=0;d<128;++d) for(int r=0;r<128;++r) {
            if(!std::getline(in,line)) throw std::runtime_error("Truncated spectrum");
            std::replace(line.begin(),line.end(),',',' ');
            std::istringstream row(line);int di,ri,re,im;
            if(!(row>>di>>ri>>re>>im) || di!=d || ri!=r || re< -32768 || re>32767 || im< -32768 || im>32767)
                throw std::runtime_error("Invalid spectrum bin/order/Q15 value");
            row>>std::ws;
            if(!row.eof()) throw std::runtime_error("Extra spectrum fields");
            real[size_t(d)*128+r]=re;imag[size_t(d)*128+r]=im;
        }
        if(std::getline(in,line)) throw std::runtime_error("Extra spectrum rows");
        radar::CaCfar cfar(128,128);
        const std::vector<radar::CfarPeak>* peaks=nullptr;
        std::vector<double> times;times.reserve(repeat);
        auto detect=[&]{
            for(size_t i=0;i<power.size();++i) power[i]=real[i]*real[i]+imag[i]*imag[i];
            peaks=&cfar.detect(power);
        };
        for(int i=0;i<warmup;++i) detect();
        for(int i=0;i<repeat;++i) {
            auto start=std::chrono::steady_clock::now();detect();
            times.push_back(std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count());
        }
        std::ofstream out(output),clock(timings);
        if(!out || !clock) throw std::runtime_error("Cannot open output CSV");
        out<<"doppler_bin_unshifted,range_bin,power,threshold\n"<<std::setprecision(17);
        for(const auto& p:*peaks) out<<p.doppler<<','<<p.range<<','<<p.power<<','<<p.threshold<<'\n';
        clock<<"stage,iteration,wall_ms\n"<<std::setprecision(17);
        for(size_t i=0;i<times.size();++i) clock<<"cfar,"<<i+1<<','<<times[i]<<'\n';
        out.close();clock.close();
        if(!out || !clock) throw std::runtime_error("Failed writing CSV");
        std::cout<<"S1C_CFAR_COMPLETE peaks="<<peaks->size()<<" repeat="<<repeat
                 <<" scope=power+CA+cluster+sort; CSV IO excluded; no end-to-end timing\n";
        return 0;
    } catch(const std::exception& e) {
        std::cerr<<"Error: "<<e.what()<<'\n';return 1;
    }
}
