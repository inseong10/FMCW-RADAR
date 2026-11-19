#ifndef FFT128_BATCH_PROCESS_H
#define FFT128_BATCH_PROCESS_H
#include "../native_core.h"
int fft128_batch_axis(const uint32_t *, uint32_t *, unsigned, uint32_t, fft128_profile *);
int fft128_process_batch(const uint32_t *,uint32_t *,uint32_t *,uint32_t *,uint32_t *,fft128_profile *);
#endif
