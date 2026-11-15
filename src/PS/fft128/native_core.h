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
