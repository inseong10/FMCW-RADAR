// E13-2core on-board ABI/packet/ownership check; not a performance measurement.
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include "fft128_dma_parallel_uapi.h"
#include "../native_core.h"
_Static_assert(sizeof(struct fft128_dma_parallel_header)==112,"header ABI");
_Static_assert(sizeof(struct fft128_dma_parallel_request)==131184,"request ABI");
_Static_assert(offsetof(struct fft128_dma_parallel_request,input)==112,"input ABI");
_Static_assert(offsetof(struct fft128_dma_parallel_request,output)==65648,"output ABI");
static struct fft128_dma_parallel_request r;
static int reject(int fd,unsigned long cmd,int expected) {
    errno=0;
    if(ioctl(fd,cmd,&r)!=-1 || errno!=expected) {
        fprintf(stderr,"batch ABI reject expected=%d actual=%d\n",expected,errno);return -1;
    }
    return 0;
}
int main(void) {
    uint32_t expected[128];
    int fd=open("/dev/fft128-dma-parallel",O_RDWR),other;
    if(fd<0) { perror("batch open");return 1; }
    other=open("/dev/fft128-dma-parallel",O_RDWR);
    if(other>=0 || errno!=EBUSY) return 1;
    if(reject(fd,_IO('F',0x11),ENOTTY) || reject(fd,FFT128_DMA_PARALLEL_RUN,EINVAL)) return 1;
    r.meta.abi=3;r.meta.timeout_ms=1000;
    r.meta.fft_count=129;if(reject(fd,FFT128_DMA_PARALLEL_RUN,EINVAL)) return 1;
    r.meta.fft_count=128;r.meta.timeout_ms=1001;if(reject(fd,FFT128_DMA_PARALLEL_RUN,EINVAL)) return 1;
    r.meta.timeout_ms=1000;r.meta.flags=2;if(reject(fd,FFT128_DMA_PARALLEL_RUN,EINVAL)) return 1;
    r.meta.flags=1;
    for(unsigned trial=0;trial<3;++trial) {
        r.meta.fft_count=trial ? 128 : 1;
        for(unsigned v=0;v<128;++v)
            for(unsigned k=0;k<128;++k)
                r.input[v*128+k]=fft128_pack((int)((v*173+k*79+trial*431)%32768)-16384,(int)((v*31+k*997)%32768)-16384);
        memset(r.output,0xa5,sizeof(r.output));
        if(ioctl(fd,FFT128_DMA_PARALLEL_RUN,&r)) { perror("batch RUN");return 1; }
        unsigned count=r.meta.fft_count;
        if(r.meta.status!=2 || r.meta.input_count!=count*128 || r.meta.output_count!=count*128 ||
           r.meta.completed_ffts!=count || r.meta.core_count!=2 ||
           !r.meta.core0_cycles || r.meta.both_work_cycles>r.meta.both_busy_cycles ||
           r.meta.both_busy_cycles>r.meta.core0_cycles || r.meta.both_busy_cycles>r.meta.core1_cycles ||
           (count>1 && r.meta.both_work_cycles<=count/2) || (count==1 && r.meta.core1_cycles)) return 1;
        for(unsigned v=0;v<count;++v) {
            fft128_model(r.input+v*128,expected,NULL);
            for(unsigned k=0;k<128;++k) if(r.output[v*128+k]!=expected[k]) {
                fprintf(stderr,"batch mismatch trial=%u vector=%u bin=%u\n",trial,v,k);return 1;
            }
        }
        printf("PARALLEL_PACKET_PASS fft_count=%u bytes_each_direction=%u completed=%u\n",count,count*512,r.meta.completed_ffts);
    }
    printf("PARALLEL_OVERLAP_PASS cores=%u both_busy_cycles=%u both_work_cycles=%u\n",r.meta.core_count,r.meta.both_busy_cycles,r.meta.both_work_cycles);
    close(fd);
    puts("DMA_PARALLEL_CLIENT_PASS exclusive_owner invalid_ABI timeout flags count full_axis repeated_packets");
    return 0;
}
