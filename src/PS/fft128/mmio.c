// Build with the PetaLinux 2022.1 SDK ARM compiler, or GCC on the target.
// A single process owns the accelerator. AXI reads/writes must remain 32-bit.
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <time.h>
#include <stdio.h>
#include "native_core.h"

static volatile uint32_t *regs;
static int device_fd = -1;
static uint32_t read32(unsigned offset) {
    uint32_t v = regs[offset / 4];
    __sync_synchronize();
    return v;
}
static void write32(unsigned offset, uint32_t v) {
    __sync_synchronize();
    regs[offset / 4] = v;
    __sync_synchronize();
}
void fft128_close(void) {
    if (regs) munmap((void *)regs, 4096);
    if (device_fd >= 0) close(device_fd);
    regs = 0;
    device_fd = -1;
}
int fft128_open(uint32_t base) {
    if (regs || (base & 4095)) return -1;
    device_fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (device_fd < 0) return -2;
    void *p = mmap(0, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, device_fd, base);
    if (p == MAP_FAILED) { fft128_close(); return -3; }
    regs = (volatile uint32_t *)p;
    fprintf(stderr, "MMIO: reading ID at 0x%08x; waiting here means the AXI access has not returned\n", (unsigned)base);
    fflush(stderr);
    uint32_t id = read32(0);
    fprintf(stderr, "MMIO: ID=0x%08x; reading FFT length\n", (unsigned)id);
    fflush(stderr);
    if (id != 0x46543128) { fft128_close(); return -4; }
    uint32_t length = read32(12);
    fprintf(stderr, "MMIO: FFT length=%u; issuing soft reset\n", (unsigned)length);
    fflush(stderr);
    if (length != 128) { fft128_close(); return -4; }
    write32(4, 2);
    fprintf(stderr, "MMIO: initialization complete\n");
    fflush(stderr);
    return 0;
}
static uint64_t millis(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec*1000 + ts.tv_nsec/1000000;
}
int fft128_run(const uint32_t *input, uint32_t *output, uint32_t timeout_ms) {
    return fft128_run_profiled(input,output,timeout_ms,NULL);
}
int fft128_run_profiled(const uint32_t *input, uint32_t *output, uint32_t timeout_ms,
                       fft128_profile *profile) {
    if (!regs || !input || !output) return -1;
    uint64_t started=profile ? fft128_now_ns() : 0;
    if (read32(8) & 1) return -2;
    for (unsigned k=0; k<128; ++k) write32(0x100+4*k, input[k]);
    if(profile) { uint64_t end=fft128_now_ns(); profile->input_write_ns+=end-started; started=end; }
    write32(4, 1);
    uint64_t deadline = millis()+timeout_ms;
    for (;;) {
        uint32_t status = read32(8);
        if (status & 4) { write32(4, 2); return -3; }
        if ((status & 3) == 2) break;
        if (millis() >= deadline) { write32(4, 2); return -4; }
    }
    if(profile) {
        uint64_t end=fft128_now_ns();
        profile->start_wait_ns+=end-started; started=end;
        uint32_t cycles=read32(0x10);
        end=fft128_now_ns(); profile->counter_read_ns+=end-started; started=end;
        if(!profile->calls || cycles<profile->min_cycles) profile->min_cycles=cycles;
        if(cycles>profile->max_cycles) profile->max_cycles=cycles;
        profile->pl_cycles+=cycles; ++profile->calls;
    }
    for (unsigned k=0; k<128; ++k) output[k] = read32(0x800+4*k);
    if(profile) profile->output_read_ns+=fft128_now_ns()-started;
    return 0;
}
