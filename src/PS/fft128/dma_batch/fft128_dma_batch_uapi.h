/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef FFT128_DMA_BATCH_UAPI_H
#define FFT128_DMA_BATCH_UAPI_H
#include <linux/ioctl.h>
#include <linux/types.h>
#define FFT128_DMA_BATCH_ABI 2
#define FFT128_DMA_BATCH_PROFILE 1
#define FFT128_DMA_BATCH_WORDS 16384
/* Fixed-width, pointer-free header. ioctl encodes ONLY this 88-byte header:
 * the complete argument is fft128_dma_batch_request (131160 bytes), exceeding
 * the ioctl size field. Payload offsets/capacity are fixed on ARM32 and host64.
 * fft_count is 1..128; only its fft_count*128 words are copied in each direction.
 */
struct fft128_dma_batch_header {
    __u32 abi, flags, timeout_ms, fft_count;
    __u32 active_cycles, input_stalls, output_stalls, status;
    __u32 input_count, output_count, completed_ffts, reserved;
    __aligned_u64 copy_in_ns, submit_ns, wait_ns, check_ns, copy_out_ns;
};
struct fft128_dma_batch_request {
    struct fft128_dma_batch_header meta;
    __u32 input[FFT128_DMA_BATCH_WORDS];
    __u32 output[FFT128_DMA_BATCH_WORDS];
};
#define FFT128_DMA_BATCH_RUN _IOWR('F', 0x12, struct fft128_dma_batch_header)
#endif
