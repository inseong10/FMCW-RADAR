#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <stdexcept>
#include <vector>

// S1b square-law CA-CFAR. Layout is [unshifted Doppler][range].
// Doppler wraps, range edges use available cells, and the guard includes the CUT.
// Buffers and range-dependent threshold scales are prepared outside timing.
namespace radar {
struct CfarPeak {
    int doppler, range;
    double power, threshold;
};

class CaCfar {
    int nd_, nr_, gd_, gr_, hd_, hr_, stride_;
    std::vector<double> prefix_, scale_, threshold_;
    std::vector<CfarPeak> peaks_;

    double rectangle(int d0, int d1, int r0, int r1) const {
        r0 = std::max(0, r0);
        r1 = std::min(nr_, r1);
        return prefix_[size_t(d1) * stride_ + r1]
             - prefix_[size_t(d0) * stride_ + r1]
             - prefix_[size_t(d1) * stride_ + r0]
             + prefix_[size_t(d0) * stride_ + r0];
    }

public:
    CaCfar(int nd, int nr, int gd=2, int gr=2, int td=8, int tr=8,
           double pfa=1e-6)
        : nd_(nd), nr_(nr), gd_(gd), gr_(gr), hd_(gd+td), hr_(gr+tr), stride_(nr+1) {
        if(nd<=0 || nr<=0 || gd<0 || gr<0 || td<0 || tr<0 ||
           gd>1024 || gr>1024 || td>1024 || tr>1024 ||
           !std::isfinite(pfa) || pfa<=0 || pfa>=1)
            throw std::runtime_error("Invalid CA-CFAR dimensions/parameters");
        prefix_.resize(size_t(nd+2*hd_+1)*stride_);
        scale_.resize(nr);
        threshold_.resize(size_t(nd)*nr);
        peaks_.reserve(size_t(nd)*nr);
        for(int r=0;r<nr;++r) {
            int outer_width=std::min(nr,r+hr_+1)-std::max(0,r-hr_);
            int guard_width=std::min(nr,r+gr_+1)-std::max(0,r-gr_);
            int count=(2*hd_+1)*outer_width-(2*gd_+1)*guard_width;
            if(count<=0) throw std::runtime_error("CA-CFAR has no training cells");
            // alpha/count; equivalent to the S1a reference threshold.
            scale_[r]=std::pow(pfa,-1.0/count)-1.0;
        }
    }

    const std::vector<CfarPeak>& detect(const std::vector<double>& power) {
        if(power.size()!=size_t(nd_)*nr_) throw std::runtime_error("CA-CFAR power shape mismatch");
        std::fill(prefix_.begin(),prefix_.end(),0.0);
        for(int p=0;p<nd_+2*hd_;++p) {
            int d=((p-hd_)%nd_+nd_)%nd_;
            double row=0;
            for(int r=0;r<nr_;++r) {
                double value=power[size_t(d)*nr_+r];
                if(!std::isfinite(value) || value<0) throw std::runtime_error("Invalid CFAR power");
                row+=value;
                prefix_[size_t(p+1)*stride_+r+1]=prefix_[size_t(p)*stride_+r+1]+row;
            }
        }
        for(int d=0;d<nd_;++d) for(int r=0;r<nr_;++r) {
            double total=rectangle(d,d+2*hd_+1,r-hr_,r+hr_+1)
                        -rectangle(d+hd_-gd_,d+hd_+gd_+1,r-gr_,r+gr_+1);
            // Roundoff in prefix subtraction can produce a tiny negative zero-floor sum.
            threshold_[size_t(d)*nr_+r]=std::max(0.0,total)*scale_[r];
        }
        peaks_.clear();
        for(int d=0;d<nd_;++d) for(int r=0;r<nr_;++r) {
            size_t i=size_t(d)*nr_+r;
            if(power[i]<=threshold_[i]) continue;
            bool maximum=true;
            for(int dd=-1;dd<=1;++dd) for(int rr=std::max(0,r-1);rr<=std::min(nr_-1,r+1);++rr)
                if(power[size_t((d+dd+nd_)%nd_)*nr_+rr]>power[i]) maximum=false;
            if(maximum) peaks_.push_back({d,r,power[i],threshold_[i]});
        }
        // Match S1a stable power ordering, including row-major ordering on ties.
        std::sort(peaks_.begin(),peaks_.end(),[](const CfarPeak& a,const CfarPeak& b){
            if(a.power!=b.power) return a.power>b.power;
            if(a.doppler!=b.doppler) return a.doppler<b.doppler;
            return a.range<b.range;
        });
        return peaks_;
    }
    const std::vector<double>& thresholds() const { return threshold_; }
};
} // namespace radar
