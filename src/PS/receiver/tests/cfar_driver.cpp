// Portable host driver: exercises the same header as the Linux receiver.
#include "../cfar_ca.hpp"
#include <iomanip>
#include <iostream>

int main() {
    try {
        int nd,nr,gd,gr,td,tr;
        double pfa;
        if(!(std::cin>>nd>>nr>>gd>>gr>>td>>tr>>pfa)) return 2;
        radar::CaCfar cfar(nd,nr,gd,gr,td,tr,pfa);
        std::vector<double> power(size_t(nd)*nr);
        for(auto& p:power) if(!(std::cin>>p)) return 2;
        const auto& peaks=cfar.detect(power);
        std::cout<<std::setprecision(17);
        for(double t:cfar.thresholds()) std::cout<<t<<' ';
        std::cout<<'\n';
        for(const auto& p:peaks) std::cout<<p.doppler<<' '<<p.range<<'\n';
        return 0;
    } catch(const std::exception& e) {
        std::cerr<<e.what()<<'\n';
        return 1;
    }
}
