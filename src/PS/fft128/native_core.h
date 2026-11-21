#ifndef FFT128_NATIVE_CORE_H
#define FFT128_NATIVE_CORE_H
#include <stddef.h>
#include <stdint.h>
#define FFT128_N 128
#define FFT128_BINS (FFT128_N * FFT128_N)
typedef struct { double real, imag; } fft128_sample;
typedef int (*fft128_transform)(const uint32_t *, uint32_t *, void *);
typedef struct {
    uint64_t input_write_ns, start_wait_ns, counter_read_ns, output_read_ns;
    uint64_t gather_ns, scatter_ns, pl_cycles;
    uint32_t calls, min_cycles, max_cycles;
    /* E11a nested ioctl stages; not additive to start_wait_ns. */
    uint64_t dma_copy_in_ns, dma_submit_ns, dma_wait_ns, dma_check_ns, dma_copy_out_ns;
    uint64_t dma_input_stalls, dma_output_stalls;
#ifdef FFT128_DMA_FRAME_BACKEND
    uint64_t frame_range_cycles, frame_doppler_cycles, frame_drain_cycles;
    uint64_t frame_matrix_reads, frame_matrix_writes;
    uint64_t frame_range_outputs, frame_doppler_inputs, frame_doppler_outputs;
    uint64_t frame_overwrite_errors, frame_io_overlap_cycles, frame_matrix_words;
    uint64_t frame_stage_busy_cycles, frame_multi_stage_cycles, frame_vector_overlap_cycles;
    uint64_t frame_issue_events[7], frame_retire_events[7];
#endif
#ifdef FFT128_DMA_PARALLEL_BACKEND
    uint64_t parallel_core0_cycles, parallel_core1_cycles;
    uint64_t parallel_both_busy_cycles, parallel_both_work_cycles, parallel_arbitration_stalls;
#endif
#if defined(FFT128_DMA_QUAD_BACKEND) || defined(FFT128_DMA_OVERLAP_BACKEND) || defined(FFT128_DMA_BF2_BACKEND)
    uint64_t quad_core0_cycles, quad_core1_cycles, quad_core2_cycles, quad_core3_cycles;
    uint64_t quad_any_busy_cycles, quad_multi_busy_cycles, quad_all_busy_cycles;
    uint64_t quad_multi_work_cycles, quad_all_work_cycles, quad_arbitration_stalls;
#endif
#if defined(FFT128_DMA_OVERLAP_BACKEND) || defined(FFT128_DMA_BF2_BACKEND)
    uint64_t overlap_io_cycles, overlap_input_work_cycles, overlap_output_work_cycles, overlap_three_cycles;
#endif
#ifdef FFT128_DMA_BF2_BACKEND
    uint64_t bf2_dual_issue_events, bf2_dual_retire_events, bf2_calc_lane_cycles;
#endif
#ifdef FFT128_DMA_STREAM_BACKEND
    uint64_t stream_stage_busy_cycles, stream_multi_stage_cycles, stream_vector_overlap_cycles;
    uint64_t stream_issue_events[7], stream_retire_events[7];
    uint64_t stream_io_cycles, stream_input_calc_cycles, stream_output_calc_cycles, stream_three_cycles;
#endif
} fft128_profile;
uint64_t fft128_now_ns(void);
uint32_t fft128_pack(int real, int imag);
int fft128_real(uint32_t word);
int fft128_imag(uint32_t word);
int fft128_model(const uint32_t *input, uint32_t *output, void *context);
int fft128_quantize(const fft128_sample *frame, uint32_t *packed, double *scale);
int fft128_process(const uint32_t *packed, uint32_t *spectrum,
                   fft128_transform transform, void *context);
int fft128_process_workspace(const uint32_t *packed, uint32_t *spectrum,
                             uint32_t *ranged, fft128_transform transform, void *context);
int fft128_process_profiled(const uint32_t *packed, uint32_t *spectrum,
                           uint32_t *ranged, fft128_transform transform,
                           void *context, fft128_profile *profile);
int fft128_decode(const unsigned char *packet, size_t length, unsigned *channel,
                  unsigned *index, double *fs, fft128_sample *row);
int fft128_open(uint32_t base);
int fft128_run(const uint32_t *input, uint32_t *output, uint32_t timeout_ms);
int fft128_run_profiled(const uint32_t *input, uint32_t *output, uint32_t timeout_ms,
                       fft128_profile *profile);
void fft128_close(void);
#endif
