/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef FFT128_DMA_BF2_UAPI_H
#define FFT128_DMA_BF2_UAPI_H
#include <linux/ioctl.h>
#include <linux/types.h>
#define FFT128_DMA_BF2_ABI 6
#define FFT128_DMA_BF2_PROFILE 1
#define FFT128_DMA_BF2_WORDS 16384
/* Fixed-width, pointer-free header. ioctl encodes ONLY this 112-byte header:
 * the complete argument is fft128_dma_bf2_request (131240 bytes), exceeding
 * the ioctl size field. Payload offsets/capacity are fixed on ARM32 and host64.
 * fft_count is 1..128; only its fft_count*128 words are copied in each direction.
 */
struct fft128_dma_bf2_header {
    __u32 abi, flags, timeout_ms, fft_count;
    __u32 active_cycles, input_stalls, output_stalls, status;
    __u32 input_count, output_count, completed_ffts, reserved;
    __u32 core0_cycles, core1_cycles, any_busy_cycles, all_work_cycles;
    __u32 arbitration_stalls, core_count;
    __aligned_u64 copy_in_ns, submit_ns, wait_ns, check_ns, copy_out_ns;
};
/* Keep payload offsets IDENTICAL to ABI3 (112/65648) to keep host copies comparable.
 * Extra profile counters follow both arrays; they are returned only for PROFILE. */
struct fft128_dma_bf2_extra {
    __u32 core2_cycles, core3_cycles, multi_busy_cycles, all_busy_cycles, multi_work_cycles, reserved;
    __u32 io_cycles, input_work_cycles, output_work_cycles, three_cycles;
    __u32 butterflies_per_core, dual_issue_events, dual_retire_events, calc_lane_cycles;
};
struct fft128_dma_bf2_request {
    struct fft128_dma_bf2_header meta;
    __u32 input[FFT128_DMA_BF2_WORDS];
    __u32 output[FFT128_DMA_BF2_WORDS];
    struct fft128_dma_bf2_extra extra;
};
#define FFT128_DMA_BF2_RUN _IOWR('F', 0x16, struct fft128_dma_bf2_header)
#endif
