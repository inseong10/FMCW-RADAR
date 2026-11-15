// On-board interface check; not a performance measurement.
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include "fft128_dma_uapi.h"
#include "../native_core.h"
static int reject(int fd,unsigned long command,struct fft128_dma_request *r,int expected) {
    errno=0;
    if(ioctl(fd,command,r)!=-1 || errno!=expected) {
        fprintf(stderr,"DMA ABI rejection failed: expected errno=%d actual=%d\n",expected,errno);
        return -1;
    }
    return 0;
}
int main(void) {
    struct fft128_dma_request r={0};
    uint32_t expected[128];
    int fd=open("/dev/fft128-dma",O_RDWR), other;
    if(fd<0) { perror("/dev/fft128-dma");return 1; }
    other=open("/dev/fft128-dma",O_RDWR);
    if(other>=0 || errno!=EBUSY) { fprintf(stderr,"Exclusive ownership check failed\n");return 1; }
    if(reject(fd,_IO('F',0x12),&r,ENOTTY) || reject(fd,FFT128_DMA_RUN,&r,EINVAL)) return 1;
    r.abi=FFT128_DMA_ABI;r.timeout_ms=1001;
    if(reject(fd,FFT128_DMA_RUN,&r,EINVAL)) return 1;
    r.timeout_ms=1000;r.flags=2;
    if(reject(fd,FFT128_DMA_RUN,&r,EINVAL)) return 1;
    r.flags=FFT128_DMA_PROFILE;
    r.input[0]=fft128_pack(16384,-8192);
    fft128_model(r.input,expected,NULL);
    if(ioctl(fd,FFT128_DMA_RUN,&r)) { perror("Valid DMA ioctl");return 1; }
    if(r.status!=2 || !r.active_cycles) { fprintf(stderr,"DMA completion/profile invalid\n");return 1; }
    for(unsigned k=0;k<128;++k) if(r.output[k]!=expected[k]) {
        fprintf(stderr,"DMA ABI output mismatch at bin %u\n",k);return 1;
    }
    close(fd);
    puts("DMA_CLIENT_PASS exclusive_owner invalid_ABI timeout flags unknown_ioctl valid_impulse");
    return 0;
}
