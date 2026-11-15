// Portable framing and numeric reference, shared by the native PS receiver/tests.
#include "native_core.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

uint32_t fft128_pack(int real, int imag) {
    return ((uint32_t)real & 65535u) | (((uint32_t)imag & 65535u) << 16);
}
int fft128_real(uint32_t w) {
    int v = (int)(w & 65535u);
    return v >= 32768 ? v - 65536 : v;
}
int fft128_imag(uint32_t w) {
    int v = (int)(w >> 16);
    return v >= 32768 ? v - 65536 : v;
}
static int saturate(int64_t value) {
    // Defined floor division, including negative numbers; no signed shifts/overflow.
    int64_t q = value / 65536;
    if (value < 0 && value % 65536) --q;
    return q > 32767 ? 32767 : q < -32768 ? -32768 : (int)q;
}
int fft128_model(const uint32_t *input, uint32_t *output, void *context) {
    (void)context;
    uint32_t values[FFT128_N];
    int wr[64], wi[64];
    const double pi = 3.14159265358979323846;
    for (unsigned k = 0; k < 64; ++k) {
        long r = lrint(32768 * cos(-2*pi*k/FFT128_N));
        long i = lrint(32768 * sin(-2*pi*k/FFT128_N));
        wr[k] = r > 32767 ? 32767 : r < -32768 ? -32768 : (int)r;
        wi[k] = i > 32767 ? 32767 : i < -32768 ? -32768 : (int)i;
    }
    for (unsigned k = 0; k < FFT128_N; ++k) {
        unsigned reversed = 0;
        for (unsigned bit = 0; bit < 7; ++bit) reversed = (reversed << 1) | ((k >> bit) & 1);
        values[reversed] = input[k];
    }
    for (unsigned half = 1; half < FFT128_N; half *= 2) {
        for (unsigned base = 0; base < FFT128_N; base += 2*half) {
            for (unsigned j = 0; j < half; ++j) {
                uint32_t a = values[base+j], b = values[base+j+half];
                int64_t ar = fft128_real(a), ai = fft128_imag(a);
                int64_t br = fft128_real(b), bi = fft128_imag(b);
                unsigned tw = j*FFT128_N/(2*half);
                int64_t pr = br*wr[tw] - bi*wi[tw];
                int64_t pi_value = br*wi[tw] + bi*wr[tw];
                values[base+j] = fft128_pack(saturate(ar*32768+pr), saturate(ai*32768+pi_value));
                values[base+j+half] = fft128_pack(saturate(ar*32768-pr), saturate(ai*32768-pi_value));
            }
        }
    }
    memcpy(output, values, sizeof(values));
    return 0;
}
int fft128_quantize(const fft128_sample *frame, uint32_t *packed, double *scale) {
    double peak = 0;
    for (unsigned k = 0; k < FFT128_BINS; ++k) {
        if (!isfinite(frame[k].real) || !isfinite(frame[k].imag)) return -1;
        double magnitude = hypot(frame[k].real, frame[k].imag);
        if (!isfinite(magnitude)) return -1;
        if (magnitude > peak) peak = magnitude;
    }
    *scale = peak ? 16384/peak : 1;
    if (!isfinite(*scale)) return -1;
    for (unsigned k = 0; k < FFT128_BINS; ++k) {
        packed[k] = fft128_pack((int)lrint(frame[k].real * *scale),
                               (int)lrint(frame[k].imag * *scale));
    }
    return 0;
}
int fft128_process(const uint32_t *packed, uint32_t *spectrum,
                   fft128_transform transform, void *context) {
    uint32_t *ranged = malloc(FFT128_BINS*sizeof(*ranged));
    if (!ranged) return -1;
    int rc = fft128_process_workspace(packed,spectrum,ranged,transform,context);
    free(ranged);
    return rc;
}
int fft128_process_workspace(const uint32_t *packed, uint32_t *spectrum,
                             uint32_t *ranged, fft128_transform transform, void *context) {
    if (!packed || !spectrum || !ranged || !transform) return -1;
    uint32_t column[FFT128_N], result[FFT128_N];
    int rc = 0;
    for (unsigned ch = 0; ch < FFT128_N; ++ch) {
        rc = transform(packed+ch*FFT128_N, ranged+ch*FFT128_N, context);
        if (rc) goto finish;
    }
    for (unsigned r = 0; r < FFT128_N; ++r) {
        for (unsigned ch = 0; ch < FFT128_N; ++ch) column[ch] = ranged[ch*FFT128_N+r];
        rc = transform(column, result, context);
        if (rc) goto finish;
        for (unsigned d = 0; d < FFT128_N; ++d) spectrum[d*FFT128_N+r] = result[d];
    }
finish:
    return rc;
}
static uint32_t be32(const unsigned char *p) {
    return ((uint32_t)p[0]<<24) | ((uint32_t)p[1]<<16) | ((uint32_t)p[2]<<8) | p[3];
}
int fft128_decode(const unsigned char *p, size_t len, unsigned *channel,
                  unsigned *index, double *fs, fft128_sample *row) {
    if (sizeof(float) != 4 || sizeof(double) != 8 || len != 28+FFT128_N*8) return -1;
    if (memcmp(p,"RSPY",4) || p[4]!=1 || p[5]!=1 ||
        be32(p+12)!=FFT128_N || be32(p+16)!=FFT128_N || be32(p+8)>=FFT128_N) return -1;
    uint64_t bits = ((uint64_t)be32(p+20)<<32) | be32(p+24);
    memcpy(fs, &bits, sizeof(*fs));
    if (!isfinite(*fs) || *fs<=0) return -1;
    *channel = ((unsigned)p[6]<<8) | p[7];
    *index = be32(p+8);
    for (unsigned k = 0; k < FFT128_N; ++k) {
        uint32_t r = be32(p+28+k*8), i = be32(p+32+k*8);
        float real, imag;
        memcpy(&real, &r, 4); memcpy(&imag, &i, 4);
        if (!isfinite(real) || !isfinite(imag)) return -1;
        row[k].real = real; row[k].imag = imag;
    }
    return 0;
}
