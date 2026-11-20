/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef FFT128_DMA_QUAD_UAPI_H
#define FFT128_DMA_QUAD_UAPI_H
#include <linux/ioctl.h>
#include <linux/types.h>
#define FFT128_DMA_QUAD_ABI 4
#define FFT128_DMA_QUAD_PROFILE 1
#define FFT128_DMA_QUAD_WORDS 16384
/* Fixed-width, pointer-free header. ioctl encodes ONLY this 112-byte header:
 * the complete argument is fft128_dma_quad_request (131208 bytes), exceeding
 * the ioctl size field. Payload offsets/capacity are fixed on ARM32 and host64.
 * fft_count is 1..128; only its fft_count*128 words are copied in each direction.
 */
struct fft128_dma_quad_header {
    __u32 abi, flags, timeout_ms, fft_count;
    __u32 active_cycles, input_stalls, output_stalls, status;
    __u32 input_count, output_count, completed_ffts, reserved;
    __u32 core0_cycles, core1_cycles, any_busy_cycles, all_work_cycles;
    __u32 arbitration_stalls, core_count;
    __aligned_u64 copy_in_ns, submit_ns, wait_ns, check_ns, copy_out_ns;
};
/* Keep payload offsets IDENTICAL to ABI3 (112/65648) for the core-count experiment.
 * Extra profile counters follow both arrays; they are returned only for PROFILE. */
struct fft128_dma_quad_extra {
    __u32 core2_cycles, core3_cycles, multi_busy_cycles, all_busy_cycles, multi_work_cycles, reserved;
};
struct fft128_dma_quad_request {
    struct fft128_dma_quad_header meta;
    __u32 input[FFT128_DMA_QUAD_WORDS];
    __u32 output[FFT128_DMA_QUAD_WORDS];
    struct fft128_dma_quad_extra extra;
};
#define FFT128_DMA_QUAD_RUN _IOWR('F', 0x14, struct fft128_dma_quad_header)
#endif
