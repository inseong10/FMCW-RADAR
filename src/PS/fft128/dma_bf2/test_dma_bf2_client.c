// E13-bf2 on-board ABI/packet/ownership check; not a performance measurement.
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include "fft128_dma_bf2_uapi.h"
#include "../native_core.h"
_Static_assert(sizeof(struct fft128_dma_bf2_header)==112,"header ABI");
_Static_assert(sizeof(struct fft128_dma_bf2_request)==131240,"request ABI");
_Static_assert(offsetof(struct fft128_dma_bf2_request,input)==112,"input ABI");
_Static_assert(offsetof(struct fft128_dma_bf2_request,output)==65648,"output ABI");
_Static_assert(offsetof(struct fft128_dma_bf2_request,extra)==131184,"extra ABI");
static struct fft128_dma_bf2_request r;
static int reject(int fd,unsigned long cmd,int expected) {
    errno=0;
    if(ioctl(fd,cmd,&r)!=-1 || errno!=expected) {
        fprintf(stderr,"batch ABI reject expected=%d actual=%d\n",expected,errno);return -1;
    }
    return 0;
}
int main(void) {
    uint32_t expected[128];
    int fd=open("/dev/fft128-dma-bf2",O_RDWR),other;
    if(fd<0) { perror("batch open");return 1; }
    other=open("/dev/fft128-dma-bf2",O_RDWR);
    if(other>=0 || errno!=EBUSY) return 1;
    if(reject(fd,_IO('F',0x11),ENOTTY) || reject(fd,FFT128_DMA_BF2_RUN,EINVAL)) return 1;
    if(reject(fd,_IOWR('F',0x13,struct fft128_dma_bf2_header),ENOTTY)) return 1;
    if(reject(fd,_IOWR('F',0x14,struct fft128_dma_bf2_header),ENOTTY)) return 1;
    if(reject(fd,_IOWR('F',0x15,struct fft128_dma_bf2_header),ENOTTY)) return 1;
    r.meta.abi=5;r.meta.fft_count=1;r.meta.timeout_ms=1000;
    if(reject(fd,FFT128_DMA_BF2_RUN,EINVAL)) return 1;
    r.meta.abi=6;r.meta.timeout_ms=1000;
    r.meta.fft_count=129;if(reject(fd,FFT128_DMA_BF2_RUN,EINVAL)) return 1;
    r.meta.fft_count=128;r.meta.timeout_ms=1001;if(reject(fd,FFT128_DMA_BF2_RUN,EINVAL)) return 1;
    r.meta.timeout_ms=1000;r.meta.flags=2;if(reject(fd,FFT128_DMA_BF2_RUN,EINVAL)) return 1;
    r.meta.flags=1;
    const unsigned counts[]={1,2,3,4,5,127,128,128};
    for(unsigned trial=0;trial<sizeof(counts)/sizeof(counts[0]);++trial) {
        r.meta.fft_count=counts[trial];
        for(unsigned v=0;v<128;++v)
            for(unsigned k=0;k<128;++k)
                r.input[v*128+k]=fft128_pack((int)((v*173+k*79+trial*431)%32768)-16384,(int)((v*31+k*997)%32768)-16384);
        memset(r.output,0xa5,sizeof(r.output));
        if(ioctl(fd,FFT128_DMA_BF2_RUN,&r)) { perror("batch RUN");return 1; }
        unsigned count=r.meta.fft_count;
        struct fft128_dma_bf2_header *m=&r.meta;
        struct fft128_dma_bf2_extra *e=&r.extra;
        if(m->status!=2 || m->input_count!=count*128 || m->output_count!=count*128 ||
           m->completed_ffts!=count || m->core_count!=4 || !m->core0_cycles ||
           m->any_busy_cycles>m->active_cycles ||
           e->all_busy_cycles>e->multi_busy_cycles || e->multi_busy_cycles>m->any_busy_cycles ||
           m->all_work_cycles>e->all_busy_cycles || e->multi_work_cycles>e->multi_busy_cycles ||
           m->all_work_cycles>e->multi_work_cycles || m->arbitration_stalls>m->active_cycles ||
           (count<4 && (e->core3_cycles || m->all_work_cycles)) ||
           (count<3 && e->core2_cycles) || (count<2 && (m->core1_cycles || e->multi_work_cycles))) return 1;
        if(e->butterflies_per_core!=2 || e->dual_issue_events!=count*224 ||
           e->dual_retire_events!=count*224 || e->calc_lane_cycles!=count*252) return 1;
        const unsigned c[]={m->core0_cycles,m->core1_cycles,e->core2_cycles,e->core3_cycles};
        for(unsigned i=0;i<4;++i) if(c[i]>m->any_busy_cycles || e->all_busy_cycles>c[i]) return 1;
        for(unsigned v=0;v<count;++v) {
            fft128_model(r.input+v*128,expected,NULL);
            for(unsigned k=0;k<128;++k) if(r.output[v*128+k]!=expected[k]) {
                fprintf(stderr,"batch mismatch trial=%u vector=%u bin=%u\n",trial,v,k);return 1;
            }
        }
        printf("BF2_PACKET_PASS fft_count=%u bytes_each_direction=%u completed=%u\n",count,count*512,r.meta.completed_ffts);
    }
    if(!r.extra.io_cycles || !r.extra.input_work_cycles || !r.extra.output_work_cycles || !r.extra.three_cycles ||
       r.extra.three_cycles>r.extra.io_cycles || r.extra.three_cycles>r.extra.input_work_cycles ||
       r.extra.three_cycles>r.extra.output_work_cycles || r.extra.io_cycles>r.meta.active_cycles) return 1;
    printf("BF2_IO_PASS io=%u input_work=%u output_work=%u three=%u\n",r.extra.io_cycles,r.extra.input_work_cycles,r.extra.output_work_cycles,r.extra.three_cycles);
    printf("BF2_ARITHMETIC_PASS butterflies_per_core=%u dual_issue_events=%u dual_retire_events=%u calc_lane_cycles=%u\n",r.extra.butterflies_per_core,r.extra.dual_issue_events,r.extra.dual_retire_events,r.extra.calc_lane_cycles);
    printf("BF2_WORK_PASS cores=%u multi_busy_cycles=%u all_busy_cycles=%u multi_work_cycles=%u all_work_cycles=%u\n",r.meta.core_count,r.extra.multi_busy_cycles,r.extra.all_busy_cycles,r.extra.multi_work_cycles,r.meta.all_work_cycles);
    close(fd);
    puts("DMA_BF2_CLIENT_PASS exclusive_owner invalid_ABI timeout flags count full_axis repeated_packets");
    return 0;
}
