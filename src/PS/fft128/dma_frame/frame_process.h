#ifndef FFT128_FRAME_PROCESS_H
#define FFT128_FRAME_PROCESS_H
#include "../native_core.h"
int fft128_frame_transfer(const uint32_t *input,uint32_t *output,uint32_t timeout_ms,fft128_profile *profile);
int fft128_process_frame(const uint32_t *input,uint32_t *output,fft128_profile *profile);
int fft128_frame_selftest(void);
int fft128_frame_save_profiles(const char *prefix,unsigned repeat,uint32_t hz,
                              const fft128_profile *profiles,const double *times);
#endif
