// E13-4core on-board ABI/packet/ownership check; not a performance measurement.
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include "fft128_dma_quad_uapi.h"
#include "../native_core.h"
_Static_assert(sizeof(struct fft128_dma_quad_header)==112,"header ABI");
_Static_assert(sizeof(struct fft128_dma_quad_request)==131208,"request ABI");
_Static_assert(offsetof(struct fft128_dma_quad_request,input)==112,"input ABI");
_Static_assert(offsetof(struct fft128_dma_quad_request,output)==65648,"output ABI");
_Static_assert(offsetof(struct fft128_dma_quad_request,extra)==131184,"extra ABI");
static struct fft128_dma_quad_request r;
static int reject(int fd,unsigned long cmd,int expected) {
    errno=0;
    if(ioctl(fd,cmd,&r)!=-1 || errno!=expected) {
        fprintf(stderr,"batch ABI reject expected=%d actual=%d\n",expected,errno);return -1;
    }
    return 0;
}
int main(void) {
    uint32_t expected[128];
    int fd=open("/dev/fft128-dma-quad",O_RDWR),other;
    if(fd<0) { perror("batch open");return 1; }
    other=open("/dev/fft128-dma-quad",O_RDWR);
    if(other>=0 || errno!=EBUSY) return 1;
    if(reject(fd,_IO('F',0x11),ENOTTY) || reject(fd,FFT128_DMA_QUAD_RUN,EINVAL)) return 1;
    if(reject(fd,_IOWR('F',0x13,struct fft128_dma_quad_header),ENOTTY)) return 1;
    r.meta.abi=3;r.meta.fft_count=1;r.meta.timeout_ms=1000;
    if(reject(fd,FFT128_DMA_QUAD_RUN,EINVAL)) return 1;
    r.meta.abi=4;r.meta.timeout_ms=1000;
    r.meta.fft_count=129;if(reject(fd,FFT128_DMA_QUAD_RUN,EINVAL)) return 1;
    r.meta.fft_count=128;r.meta.timeout_ms=1001;if(reject(fd,FFT128_DMA_QUAD_RUN,EINVAL)) return 1;
    r.meta.timeout_ms=1000;r.meta.flags=2;if(reject(fd,FFT128_DMA_QUAD_RUN,EINVAL)) return 1;
    r.meta.flags=1;
    const unsigned counts[]={1,2,3,4,5,127,128,128};
    for(unsigned trial=0;trial<sizeof(counts)/sizeof(counts[0]);++trial) {
        r.meta.fft_count=counts[trial];
        for(unsigned v=0;v<128;++v)
            for(unsigned k=0;k<128;++k)
                r.input[v*128+k]=fft128_pack((int)((v*173+k*79+trial*431)%32768)-16384,(int)((v*31+k*997)%32768)-16384);
        memset(r.output,0xa5,sizeof(r.output));
        if(ioctl(fd,FFT128_DMA_QUAD_RUN,&r)) { perror("batch RUN");return 1; }
        unsigned count=r.meta.fft_count;
        struct fft128_dma_quad_header *m=&r.meta;
        struct fft128_dma_quad_extra *e=&r.extra;
        if(m->status!=2 || m->input_count!=count*128 || m->output_count!=count*128 ||
           m->completed_ffts!=count || m->core_count!=4 || !m->core0_cycles ||
           m->any_busy_cycles>m->active_cycles || m->active_cycles-m->any_busy_cycles!=(count+3)/4 ||
           e->all_busy_cycles>e->multi_busy_cycles || e->multi_busy_cycles>m->any_busy_cycles ||
           m->all_work_cycles>e->all_busy_cycles || e->multi_work_cycles>e->multi_busy_cycles ||
           m->all_work_cycles>e->multi_work_cycles || m->arbitration_stalls>m->any_busy_cycles ||
           (count>1 && e->multi_work_cycles<=count) || (count>=4 && m->all_work_cycles<=count/4) ||
           (count<4 && (e->core3_cycles || m->all_work_cycles)) ||
           (count<3 && e->core2_cycles) || (count<2 && (m->core1_cycles || e->multi_work_cycles))) return 1;
        const unsigned c[]={m->core0_cycles,m->core1_cycles,e->core2_cycles,e->core3_cycles};
        for(unsigned i=0;i<4;++i) if(c[i]>m->any_busy_cycles || e->all_busy_cycles>c[i]) return 1;
        for(unsigned v=0;v<count;++v) {
            fft128_model(r.input+v*128,expected,NULL);
            for(unsigned k=0;k<128;++k) if(r.output[v*128+k]!=expected[k]) {
                fprintf(stderr,"batch mismatch trial=%u vector=%u bin=%u\n",trial,v,k);return 1;
            }
        }
        printf("QUAD_PACKET_PASS fft_count=%u bytes_each_direction=%u completed=%u\n",count,count*512,r.meta.completed_ffts);
    }
    printf("QUAD_OVERLAP_PASS cores=%u multi_busy_cycles=%u all_busy_cycles=%u multi_work_cycles=%u all_work_cycles=%u\n",r.meta.core_count,r.extra.multi_busy_cycles,r.extra.all_busy_cycles,r.extra.multi_work_cycles,r.meta.all_work_cycles);
    close(fd);
    puts("DMA_QUAD_CLIENT_PASS exclusive_owner invalid_ABI timeout flags count full_axis repeated_packets");
    return 0;
}
