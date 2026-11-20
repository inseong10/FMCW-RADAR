// E13-4core userspace transport: cached arrays -> ioctl -> coherent bounce buffers.
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include "../native_core.h"
#include "fft128_dma_quad_uapi.h"
#include "../dma_batch/batch_process.h"
static int device_fd = -1;
static struct fft128_dma_quad_request request; /* single owner; no per-FFT allocation */
_Static_assert(sizeof(struct fft128_dma_quad_request)==131208, "DMA ABI size");
void fft128_close(void) {
    if(device_fd>=0) close(device_fd);
    device_fd=-1;
}
int fft128_open(uint32_t base) {
    if(device_fd>=0 || base!=0x43c60000) return -EINVAL;
    device_fd=open("/dev/fft128-dma-quad", O_RDWR);
    if(device_fd<0) { int err=errno; perror("/dev/fft128-dma-quad"); return -err; }
    fprintf(stderr,"DMA: kernel-owned control registers, HP0, coherent bounce buffers; 64 KiB per direction/axis, 128 FFTs, 4 arithmetic cores, group barrier\n");
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
    struct fft128_dma_quad_header *m=&request.meta;
    m->abi=FFT128_DMA_QUAD_ABI;m->flags=p ? FFT128_DMA_QUAD_PROFILE : 0;
    m->timeout_ms=timeout_ms;m->fft_count=count;
    memcpy(request.input,input,bytes);
    if(p) { uint64_t end=fft128_now_ns();p->input_write_ns+=end-tick;tick=end; }
    if(ioctl(device_fd,FFT128_DMA_QUAD_RUN,&request)<0) {
        int err=errno;perror("FFT128_DMA_QUAD_RUN");return -err;
    }
    if(p) { uint64_t end=fft128_now_ns();p->start_wait_ns+=end-tick;tick=end; }
    if(m->core_count!=4 || m->status!=2 || m->completed_ffts!=count || m->input_count!=count*128 || m->output_count!=count*128) return -EIO;
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
        p->quad_core0_cycles+=m->core0_cycles;p->quad_core1_cycles+=m->core1_cycles;
        p->quad_core2_cycles+=request.extra.core2_cycles;p->quad_core3_cycles+=request.extra.core3_cycles;
        p->quad_any_busy_cycles+=m->any_busy_cycles;p->quad_multi_busy_cycles+=request.extra.multi_busy_cycles;
        p->quad_all_busy_cycles+=request.extra.all_busy_cycles;p->quad_multi_work_cycles+=request.extra.multi_work_cycles;
        p->quad_all_work_cycles+=m->all_work_cycles;p->quad_arbitration_stalls+=m->arbitration_stalls;
    }
    return 0;
}
int fft128_run_profiled(const uint32_t *in,uint32_t *out,uint32_t timeout,fft128_profile *p) {
    return fft128_batch_axis(in,out,1,timeout,p);
}
