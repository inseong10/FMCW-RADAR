#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
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
    // S3a-0 integer path (pl/model spectra): exact uint64 Doppler column sums slid along d,
    // then a per-row 1D range prefix. All values are integers, so the order of summation is irrelevant.
    std::vector<uint64_t> co_, cg_, so_, sg_;
    std::vector<int> ro0_, ro1_, rg0_, rg1_;
    int r_in0_=0, r_in1_=0; // [r_in0_, r_in1_): range cells whose outer window needs no clamping
    bool integer_exact_=false;
    static double exact_double(uint64_t x) { // exact for x < 2^53; avoids the soft 64-bit conversion helper
        return double(uint32_t(x>>32))*4294967296.0 + double(uint32_t(x));
    }

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
        co_.resize(nr);cg_.resize(nr);so_.assign(nr+1,0);sg_.assign(nr+1,0);
        ro0_.resize(nr);ro1_.resize(nr);rg0_.resize(nr);rg1_.resize(nr);
        for(int r=0;r<nr;++r) {
            ro0_[r]=std::max(0,r-hr_);ro1_[r]=std::min(nr,r+hr_+1);
            rg0_[r]=std::max(0,r-gr_);rg1_[r]=std::min(nr,r+gr_+1);
        }
        r_in0_=std::min(nr,hr_);r_in1_=std::max(r_in0_,nr-hr_);
        // detect() prefix values are <= (nd+2hd)*nr*2^31. Below 2^53 they are exact doubles, so detect()'s
        // window totals are the exact integer totals that detect_integer() computes (bit-identical thresholds).
        integer_exact_=double(nd+2*hd_)*double(nr)*2147483648.0 < 9007199254740992.0;
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
    // S3a-0: same thresholds and peaks as detect() for integer powers p <= 2^31 (pl/model).
    // Integer window totals equal the exact double sums of detect(), so total*scale is bit-identical.
    // Precondition: ipower has nd*nr values, each <= 2^31 (re^2+im^2 of signed 16-bit words).
    // Equals detect() on double(ipower): integer comparisons order exactly like the exact doubles.
    const std::vector<CfarPeak>& detect_integer(const uint32_t* ipower) {
        if(!integer_exact_) throw std::runtime_error("CA-CFAR integer path exceeds exact double range");
        const int nd=nd_,nr=nr_;
        auto row=[&](int d){return ipower+size_t(((d%nd)+nd)%nd)*nr;};
        uint64_t* co=co_.data();uint64_t* cg=cg_.data();uint64_t* so=so_.data();uint64_t* sg=sg_.data();
        const int* ro0=ro0_.data();const int* ro1=ro1_.data();const int* rg0=rg0_.data();const int* rg1=rg1_.data();
        const double* scale=scale_.data();
        std::fill(co_.begin(),co_.end(),0);std::fill(cg_.begin(),cg_.end(),0);
        for(int dd=-hd_;dd<=hd_;++dd){const uint32_t* x=row(dd);for(int r=0;r<nr;++r)co[r]+=x[r];}
        for(int dd=-gd_;dd<=gd_;++dd){const uint32_t* x=row(dd);for(int r=0;r<nr;++r)cg[r]+=x[r];}
        peaks_.clear();
        for(int d=0;d<nd;++d) {
            // Slide the Doppler column sums to row d and build the 1D range prefixes in one pass.
            uint64_t a=0,b=0;
            if(d) {
                const uint32_t* oa=row(d+hd_);const uint32_t* os=row(d-1-hd_);
                const uint32_t* ga=row(d+gd_);const uint32_t* gs=row(d-1-gd_);
                for(int r=0;r<nr;++r) {
                    const uint64_t o=co[r]+oa[r]-os[r],g=cg[r]+ga[r]-gs[r];
                    co[r]=o;cg[r]=g;a+=o;b+=g;so[r+1]=a;sg[r+1]=b;
                }
            } else {
                for(int r=0;r<nr;++r){a+=co[r];b+=cg[r];so[r+1]=a;sg[r+1]=b;}
            }
            double* th=threshold_.data()+size_t(d)*nr;
            // Range edges use the clamped index tables; interior cells (outer window unclamped, so the
            // guard is too) use fixed offsets. Both compute the same integer total.
            for(int r=0;r<r_in0_;++r)
                th[r]=exact_double((so[ro1[r]]-so[ro0[r]])-(sg[rg1[r]]-sg[rg0[r]]))*scale[r];
            {
                const int ho=hr_+1,lo=hr_,hg=gr_+1,lg=gr_;
                for(int r=r_in0_;r<r_in1_;++r)
                    th[r]=exact_double((so[r+ho]-so[r-lo])-(sg[r+hg]-sg[r-lg]))*scale[r];
            }
            for(int r=r_in1_;r<nr;++r)
                th[r]=exact_double((so[ro1[r]]-so[ro0[r]])-(sg[rg1[r]]-sg[rg0[r]]))*scale[r];
            const uint32_t* pw=ipower+size_t(d)*nr;
            for(int r=0;r<nr;++r) {
                if(double(pw[r])<=th[r]) continue;
                bool maximum=true;
                for(int dd=-1;dd<=1;++dd) for(int rr=std::max(0,r-1);rr<=std::min(nr-1,r+1);++rr)
                    if(ipower[size_t((d+dd+nd)%nd)*nr+rr]>pw[r]) maximum=false;
                if(maximum) peaks_.push_back({d,r,double(pw[r]),th[r]});
            }
        }
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
