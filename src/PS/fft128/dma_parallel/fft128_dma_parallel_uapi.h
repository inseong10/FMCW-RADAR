/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef FFT128_DMA_PARALLEL_UAPI_H
#define FFT128_DMA_PARALLEL_UAPI_H
#include <linux/ioctl.h>
#include <linux/types.h>
#define FFT128_DMA_PARALLEL_ABI 3
#define FFT128_DMA_PARALLEL_PROFILE 1
#define FFT128_DMA_PARALLEL_WORDS 16384
/* Fixed-width, pointer-free header. ioctl encodes ONLY this 112-byte header:
 * the complete argument is fft128_dma_parallel_request (131184 bytes), exceeding
 * the ioctl size field. Payload offsets/capacity are fixed on ARM32 and host64.
 * fft_count is 1..128; only its fft_count*128 words are copied in each direction.
 */
struct fft128_dma_parallel_header {
    __u32 abi, flags, timeout_ms, fft_count;
    __u32 active_cycles, input_stalls, output_stalls, status;
    __u32 input_count, output_count, completed_ffts, reserved;
    __u32 core0_cycles, core1_cycles, both_busy_cycles, both_work_cycles;
    __u32 arbitration_stalls, core_count;
    __aligned_u64 copy_in_ns, submit_ns, wait_ns, check_ns, copy_out_ns;
};
struct fft128_dma_parallel_request {
    struct fft128_dma_parallel_header meta;
    __u32 input[FFT128_DMA_PARALLEL_WORDS];
    __u32 output[FFT128_DMA_PARALLEL_WORDS];
};
#define FFT128_DMA_PARALLEL_RUN _IOWR('F', 0x13, struct fft128_dma_parallel_header)
#endif
