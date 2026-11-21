// E14 board ABI, ownership and complete 2D correctness; not a timing benchmark.
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include "fft128_dma_frame_uapi.h"
#include "../native_core.h"
_Static_assert(sizeof(struct fft128_dma_frame_header)==112,"header ABI");
_Static_assert(sizeof(struct fft128_dma_frame_request)==131280,"request ABI");
_Static_assert(offsetof(struct fft128_dma_frame_request,input)==112,"input ABI");
_Static_assert(offsetof(struct fft128_dma_frame_request,output)==65648,"output ABI");
_Static_assert(offsetof(struct fft128_dma_frame_request,extra)==131184,"extra ABI");
static struct fft128_dma_frame_request r;
static uint32_t expected[FFT128_BINS];
static int reject(int fd,unsigned long cmd,int error) {
    errno=0;
    if(ioctl(fd,cmd,&r)!=-1 || errno!=error) {fprintf(stderr,"Frame ABI reject expected=%d actual=%d\n",error,errno);return -1;}
    return 0;
}
int main(void) {
    int fd=open("/dev/fft128-dma-frame",O_RDWR),other;
    if(fd<0) {perror("frame open");return 1;}
    other=open("/dev/fft128-dma-frame",O_RDWR);
    if(other>=0 || errno!=EBUSY) return 1;
    if(reject(fd,FFT128_DMA_FRAME_RUN,EINVAL)) return 1;
    for(unsigned old=0x11;old<=0x17;++old) if(reject(fd,_IOWR('F',old,struct fft128_dma_frame_header),ENOTTY)) return 1;
    r.meta.abi=7;r.meta.timeout_ms=1000;r.meta.frame_words=16384;
    if(reject(fd,FFT128_DMA_FRAME_RUN,EINVAL)) return 1;
    r.meta.abi=8;
    const unsigned invalid[]={0,128,16383,16385};
    for(unsigned i=0;i<4;++i) {r.meta.frame_words=invalid[i];if(reject(fd,FFT128_DMA_FRAME_RUN,EINVAL)) return 1;}
    r.meta.frame_words=16384;r.meta.timeout_ms=0;if(reject(fd,FFT128_DMA_FRAME_RUN,EINVAL)) return 1;
    r.meta.timeout_ms=1001;if(reject(fd,FFT128_DMA_FRAME_RUN,EINVAL)) return 1;
    r.meta.timeout_ms=1000;r.meta.flags=2;if(reject(fd,FFT128_DMA_FRAME_RUN,EINVAL)) return 1;
    for(unsigned trial=0;trial<4;++trial) {
        r.meta.flags=trial==3 ? 0 : FFT128_DMA_FRAME_PROFILE;
        for(unsigned ch=0;ch<128;++ch) for(unsigned sample=0;sample<128;++sample) {
            unsigned k=ch*128+sample;
            r.input[k]=trial==0 ? (k==17*128+93 ? fft128_pack(32767,-32768) : 0) :
                fft128_pack((int)((ch*173+sample*79+ch*sample*11+trial*431)%65536)-32768,
                            (int)((ch*31+sample*997+ch*sample*17)%65536)-32768);
        }
        if(fft128_process(r.input,expected,fft128_model,NULL)) return 1;
        memset(r.output,0xa5,sizeof(r.output));
        if(ioctl(fd,FFT128_DMA_FRAME_RUN,&r)) {perror("Frame RUN");return 1;}
        struct fft128_dma_frame_header *m=&r.meta;
        if(m->status!=2 || m->input_count!=16384 || m->output_count!=16384 || m->completed_ffts!=256 || m->core_count!=1) return 1;
        for(unsigned k=0;k<FFT128_BINS;++k) if(r.output[k]!=expected[k]) {
            fprintf(stderr,"Frame mismatch trial=%u bin=%u\n",trial,k);return 1;
        }
        if(m->flags) {
            struct fft128_dma_frame_extra *e=&r.extra;
            if(!m->range_cycles || !m->doppler_cycles || m->drain_cycles<16385 ||
               m->range_cycles+m->doppler_cycles+m->drain_cycles!=m->active_cycles ||
               m->matrix_reads!=32768 || m->matrix_writes!=32768 || e->stage_count!=7 ||
               e->stage_busy_cycles!=121856 || !e->multi_stage_cycles || !e->vector_overlap_cycles ||
               e->multi_stage_cycles>m->active_cycles || e->vector_overlap_cycles>m->active_cycles ||
               e->range_outputs!=16384 || e->doppler_inputs!=16384 || e->doppler_outputs!=16384 ||
               e->overwrite_errors || e->io_overlap_cycles || e->matrix_words!=16384) return 1;
            for(unsigned stage=0;stage<7;++stage) if(e->issue_events[stage]!=16384 || e->retire_events[stage]!=16384) return 1;
            printf("FRAME_MATRIX_PASS reads=%u writes=%u range=%u doppler_in=%u doppler_out=%u overwrite_errors=%u phase_cycles=%u/%u/%u\n",
                   m->matrix_reads,m->matrix_writes,e->range_outputs,e->doppler_inputs,e->doppler_outputs,e->overwrite_errors,
                   m->range_cycles,m->doppler_cycles,m->drain_cycles);
        }
        printf("FRAME_PACKET_PASS trial=%u bytes_each_direction=65536 completed_ffts=%u profile=%u bit_exact_bins=16384\n",trial,m->completed_ffts,m->flags);
    }
    close(fd);
    puts("DMA_FRAME_CLIENT_PASS exclusive_owner invalid_ABI timeout flags fixed_frame repeated_frames integer_2D phase_matrix_stage_counters");
    return 0;
}
