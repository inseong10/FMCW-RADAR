// E13-stream userspace transport: cached arrays -> ioctl -> coherent bounce buffers.
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include "../native_core.h"
#include "fft128_dma_stream_uapi.h"
#include "../dma_batch/batch_process.h"
static int device_fd = -1;
static struct fft128_dma_stream_request request; /* single owner; no per-FFT allocation */
_Static_assert(sizeof(struct fft128_dma_stream_request)==131272, "DMA ABI size");
void fft128_close(void) {
    if(device_fd>=0) close(device_fd);
    device_fd=-1;
}
int fft128_open(uint32_t base) {
    if(device_fd>=0 || base!=0x43c60000) return -EINVAL;
    device_fd=open("/dev/fft128-dma-stream", O_RDWR);
    if(device_fd<0) { int err=errno; perror("/dev/fft128-dma-stream"); return -err; }
    fprintf(stderr,"DMA: kernel-owned control registers, HP0, coherent bounce buffers; 64 KiB per direction/axis, 128 FFTs, 1 streaming core, 7 dedicated stages\n");
    return 0;
}
int fft128_run(const uint32_t *input,uint32_t *output,uint32_t timeout_ms) {
    return fft128_run_profiled(input,output,timeout_ms,NULL);
}
int fft128_batch_axis(const uint32_t *input, uint32_t *output, unsigned count,
                      uint32_t timeout_ms, fft128_profile *p) {
    uint64_t tick=p ? fft128_now_ns() : 0;
    size_t bytes=(size_t)count*512;
    if(device_fd<0 || !input || !output || !count || count>128) return -EINVAL;
    struct fft128_dma_stream_header *m=&request.meta;
    m->abi=FFT128_DMA_STREAM_ABI;m->flags=p ? FFT128_DMA_STREAM_PROFILE : 0;
    m->timeout_ms=timeout_ms;m->fft_count=count;
    memcpy(request.input,input,bytes);
    if(p) { uint64_t end=fft128_now_ns();p->input_write_ns+=end-tick;tick=end; }
    if(ioctl(device_fd,FFT128_DMA_STREAM_RUN,&request)<0) {
        int err=errno;perror("FFT128_DMA_STREAM_RUN");return -err;
    }
    if(p) { uint64_t end=fft128_now_ns();p->start_wait_ns+=end-tick;tick=end; }
    if(m->core_count!=1 || m->status!=2 || m->completed_ffts!=count || m->input_count!=count*128 || m->output_count!=count*128) return -EIO;
    memcpy(output,request.output,bytes);
    if(p) {
        p->output_read_ns+=fft128_now_ns()-tick;
        p->pl_cycles+=m->active_cycles;
        if(!p->calls || m->active_cycles<p->min_cycles) p->min_cycles=m->active_cycles;
        if(m->active_cycles>p->max_cycles) p->max_cycles=m->active_cycles;
        ++p->calls;
        p->dma_copy_in_ns+=m->copy_in_ns;p->dma_submit_ns+=m->submit_ns;
        p->dma_wait_ns+=m->wait_ns;p->dma_check_ns+=m->check_ns;
        p->dma_copy_out_ns+=m->copy_out_ns;
        p->dma_input_stalls+=m->input_stalls;p->dma_output_stalls+=m->output_stalls;
        struct fft128_dma_stream_extra *e=&request.extra;
        if(e->stage_count!=7 || e->stage_busy_cycles!=count*7*68) return -EIO;
        p->stream_stage_busy_cycles+=e->stage_busy_cycles;
        p->stream_multi_stage_cycles+=e->multi_stage_cycles;
        p->stream_vector_overlap_cycles+=e->vector_overlap_cycles;
        p->stream_io_cycles+=e->io_cycles;
        p->stream_input_calc_cycles+=e->input_work_cycles;
        p->stream_output_calc_cycles+=e->output_work_cycles;
        p->stream_three_cycles+=e->three_cycles;
        for(unsigned stage=0;stage<7;++stage) {
            if(e->issue_events[stage]!=count*64 || e->retire_events[stage]!=count*64) return -EIO;
            p->stream_issue_events[stage]+=e->issue_events[stage];
            p->stream_retire_events[stage]+=e->retire_events[stage];
        }
    }
    return 0;
}
int fft128_run_profiled(const uint32_t *in,uint32_t *out,uint32_t timeout,fft128_profile *p) {
    return fft128_batch_axis(in,out,1,timeout,p);
}
