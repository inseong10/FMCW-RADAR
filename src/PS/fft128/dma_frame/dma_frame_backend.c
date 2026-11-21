// E14: one complete two-axis transform/ioctl; original bounce/copy policy.
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include "frame_process.h"
#include "fft128_dma_frame_uapi.h"
static int device_fd=-1;
static struct fft128_dma_frame_request request;
_Static_assert(sizeof(struct fft128_dma_frame_header)==112,"header ABI");
_Static_assert(sizeof(struct fft128_dma_frame_extra)==96,"extra ABI");
_Static_assert(sizeof(struct fft128_dma_frame_request)==131280,"request ABI");
_Static_assert(offsetof(struct fft128_dma_frame_request,input)==112,"input ABI");
_Static_assert(offsetof(struct fft128_dma_frame_request,output)==65648,"output ABI");
_Static_assert(offsetof(struct fft128_dma_frame_request,extra)==131184,"extra ABI");
void fft128_close(void) { if(device_fd>=0) close(device_fd);device_fd=-1; }
int fft128_open(uint32_t base) {
    if(device_fd>=0 || base!=0x43c60000) return -EINVAL;
    device_fd=open("/dev/fft128-dma-frame",O_RDWR);
    if(device_fd<0) {int err=errno;perror("/dev/fft128-dma-frame");return -err;}
    fprintf(stderr,"DMA: E14 complete 128x128 frame; PL transpose/output reorder, 1 reused streaming FFT, 64KiB per direction, 1 ioctl/2 channels; coherent bounce copies retained\n");
    return 0;
}
/* Full-frame firmware deliberately does not emulate the old 1D command. */
int fft128_run(const uint32_t *in,uint32_t *out,uint32_t timeout) {
    (void)in;(void)out;(void)timeout;return -EOPNOTSUPP;
}
int fft128_run_profiled(const uint32_t *in,uint32_t *out,uint32_t timeout,fft128_profile *p) {
    (void)p;return fft128_run(in,out,timeout);
}
int fft128_frame_transfer(const uint32_t *input,uint32_t *output,uint32_t timeout,fft128_profile *p) {
    if(device_fd<0 || !input || !output || !timeout || timeout>1000) return -EINVAL;
    uint64_t tick=p ? fft128_now_ns() : 0;
    struct fft128_dma_frame_header *m=&request.meta;
    m->abi=FFT128_DMA_FRAME_ABI;m->flags=p ? FFT128_DMA_FRAME_PROFILE : 0;
    m->timeout_ms=timeout;m->frame_words=FFT128_DMA_FRAME_WORDS;
    memcpy(request.input,input,sizeof(request.input));
    if(p) {uint64_t end=fft128_now_ns();p->input_write_ns+=end-tick;tick=end;}
    if(ioctl(device_fd,FFT128_DMA_FRAME_RUN,&request)<0) {
        int err=errno;perror("FFT128_DMA_FRAME_RUN");return -err;
    }
    if(p) {uint64_t end=fft128_now_ns();p->start_wait_ns+=end-tick;tick=end;}
    if(m->core_count!=1 || m->status!=2 || m->completed_ffts!=256 || m->input_count!=16384 || m->output_count!=16384) return -EIO;
    memcpy(output,request.output,sizeof(request.output));
    if(p) {
        p->output_read_ns+=fft128_now_ns()-tick;
        p->pl_cycles+=m->active_cycles;
        if(!p->calls || m->active_cycles<p->min_cycles) p->min_cycles=m->active_cycles;
        if(m->active_cycles>p->max_cycles) p->max_cycles=m->active_cycles;
        ++p->calls;
        p->dma_copy_in_ns+=m->copy_in_ns;p->dma_submit_ns+=m->submit_ns;p->dma_wait_ns+=m->wait_ns;
        p->dma_check_ns+=m->check_ns;p->dma_copy_out_ns+=m->copy_out_ns;
        p->dma_input_stalls+=m->input_stalls;p->dma_output_stalls+=m->output_stalls;
        struct fft128_dma_frame_extra *e=&request.extra;
        if(e->stage_count!=7 || e->stage_busy_cycles!=256*7*68 ||
           !m->range_cycles || !m->doppler_cycles || m->drain_cycles<16385 ||
           m->range_cycles+m->doppler_cycles+m->drain_cycles!=m->active_cycles ||
           m->matrix_reads!=32768 || m->matrix_writes!=32768 || e->range_outputs!=16384 ||
           e->doppler_inputs!=16384 || e->doppler_outputs!=16384 || e->overwrite_errors ||
           e->io_overlap_cycles || e->matrix_words!=16384) return -EIO;
        p->frame_range_cycles+=m->range_cycles;p->frame_doppler_cycles+=m->doppler_cycles;p->frame_drain_cycles+=m->drain_cycles;
        p->frame_matrix_reads+=m->matrix_reads;p->frame_matrix_writes+=m->matrix_writes;
        p->frame_range_outputs+=e->range_outputs;p->frame_doppler_inputs+=e->doppler_inputs;p->frame_doppler_outputs+=e->doppler_outputs;
        p->frame_overwrite_errors+=e->overwrite_errors;p->frame_io_overlap_cycles+=e->io_overlap_cycles;p->frame_matrix_words=e->matrix_words;
        p->frame_stage_busy_cycles+=e->stage_busy_cycles;p->frame_multi_stage_cycles+=e->multi_stage_cycles;
        p->frame_vector_overlap_cycles+=e->vector_overlap_cycles;
        for(unsigned stage=0;stage<7;++stage) {
            if(e->issue_events[stage]!=16384 || e->retire_events[stage]!=16384) return -EIO;
            p->frame_issue_events[stage]+=e->issue_events[stage];p->frame_retire_events[stage]+=e->retire_events[stage];
        }
    }
    return 0;
}
