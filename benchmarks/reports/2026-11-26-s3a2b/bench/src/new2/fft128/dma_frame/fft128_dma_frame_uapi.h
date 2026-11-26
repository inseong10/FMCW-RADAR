/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef FFT128_DMA_FRAME_UAPI_H
#define FFT128_DMA_FRAME_UAPI_H
#include <linux/ioctl.h>
#include <linux/types.h>
#define FFT128_DMA_FRAME_ABI 8
#define FFT128_DMA_FRAME_PROFILE 1
#define FFT128_DMA_FRAME_WORDS 16384
/* Exactly one complete 128x128 Q15 frame. No partial axes or 1D requests.
 * ioctl encodes only this fixed 112-byte header, not the 131280-byte request.
 * Input/output offsets remain 112/65648 on ARM32 and host64. */
struct fft128_dma_frame_header {
    __u32 abi, flags, timeout_ms, frame_words;
    __u32 active_cycles, input_stalls, output_stalls, status;
    __u32 input_count, output_count, completed_ffts, reserved;
    __u32 range_cycles, doppler_cycles, drain_cycles, core_count;
    __u32 matrix_writes, matrix_reads;
    __aligned_u64 copy_in_ns, submit_ns, wait_ns, check_ns, copy_out_ns;
};
struct fft128_dma_frame_extra {
    __u32 stage_count, stage_busy_cycles, multi_stage_cycles, vector_overlap_cycles;
    __u32 issue_events[7], retire_events[7];
    __u32 range_outputs, doppler_inputs, doppler_outputs, overwrite_errors;
    __u32 io_overlap_cycles, matrix_words;
};
struct fft128_dma_frame_request {
    struct fft128_dma_frame_header meta;
    __u32 input[FFT128_DMA_FRAME_WORDS];
    __u32 output[FFT128_DMA_FRAME_WORDS];
    struct fft128_dma_frame_extra extra;
};
#define FFT128_DMA_FRAME_RUN _IOWR('F', 0x18, struct fft128_dma_frame_header)
#endif
