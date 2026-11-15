/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef FFT128_DMA_UAPI_H
#define FFT128_DMA_UAPI_H
#include <linux/ioctl.h>
#include <linux/types.h>
#define FFT128_DMA_ABI 1
#define FFT128_DMA_PROFILE 1
/* Fixed-width, pointer-free ABI shared by ARM32 userspace and the kernel. */
struct fft128_dma_request {
    __u32 abi, flags, timeout_ms, reserved;
    __u32 input[128];
    __u32 output[128];
    __u32 active_cycles, input_stalls, output_stalls, status;
    __aligned_u64 copy_in_ns, submit_ns, wait_ns, check_ns, copy_out_ns;
};
#define FFT128_DMA_RUN _IOWR('F', 0x11, struct fft128_dma_request)
#endif
