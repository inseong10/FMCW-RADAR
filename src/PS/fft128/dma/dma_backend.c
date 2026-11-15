// E11a userspace transport: cached arrays -> ioctl -> coherent bounce buffers.
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include "../native_core.h"
#include "fft128_dma_uapi.h"
static int device_fd = -1;
static struct fft128_dma_request request; /* single owner; no per-FFT allocation */
_Static_assert(sizeof(struct fft128_dma_request)==1096, "DMA ABI size");
void fft128_close(void) {
    if(device_fd>=0) close(device_fd);
    device_fd=-1;
}
int fft128_open(uint32_t base) {
    if(device_fd>=0 || base!=0x43c60000) return -EINVAL;
    device_fd=open("/dev/fft128-dma", O_RDWR);
    if(device_fd<0) { int err=errno; perror("/dev/fft128-dma"); return -err; }
    fprintf(stderr,"DMA: kernel-owned control registers, HP0, coherent bounce buffers; 512 B per direction/FFT\n");
    return 0;
}
int fft128_run(const uint32_t *input,uint32_t *output,uint32_t timeout_ms) {
    return fft128_run_profiled(input,output,timeout_ms,NULL);
}
int fft128_run_profiled(const uint32_t *input,uint32_t *output,uint32_t timeout_ms,fft128_profile *p) {
    uint64_t tick=p ? fft128_now_ns() : 0;
    if(device_fd<0 || !input || !output) return -EINVAL;
    request.abi=FFT128_DMA_ABI;request.flags=p ? FFT128_DMA_PROFILE : 0;
    request.timeout_ms=timeout_ms;request.reserved=0;
    memcpy(request.input,input,sizeof(request.input));
    if(p) { uint64_t end=fft128_now_ns();p->input_write_ns+=end-tick;tick=end; }
    if(ioctl(device_fd,FFT128_DMA_RUN,&request)<0) {
        int err=errno;perror("FFT128_DMA_RUN");return -err;
    }
    if(p) { uint64_t end=fft128_now_ns();p->start_wait_ns+=end-tick;tick=end; }
    if(request.status!=2) return -EIO;
    memcpy(output,request.output,sizeof(request.output));
    if(p) {
        p->output_read_ns+=fft128_now_ns()-tick;
        p->pl_cycles+=request.active_cycles;
        if(!p->calls || request.active_cycles<p->min_cycles) p->min_cycles=request.active_cycles;
        if(request.active_cycles>p->max_cycles) p->max_cycles=request.active_cycles;
        ++p->calls;
        p->dma_copy_in_ns+=request.copy_in_ns;p->dma_submit_ns+=request.submit_ns;
        p->dma_wait_ns+=request.wait_ns;p->dma_check_ns+=request.check_ns;
        p->dma_copy_out_ns+=request.copy_out_ns;
        p->dma_input_stalls+=request.input_stalls;p->dma_output_stalls+=request.output_stalls;
    }
    return 0;
}
