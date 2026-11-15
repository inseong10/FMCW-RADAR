// Linux board executable; Windows supports the explicit model backend for tests.
#if defined(__linux__) && !defined(_GNU_SOURCE)
#define _GNU_SOURCE
#endif
#define _POSIX_C_SOURCE 200809L
#ifdef _WIN32
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
typedef SOCKET radar_socket;
typedef int radar_socklen;
#define BAD_SOCKET INVALID_SOCKET
#define close_socket closesocket
#else
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <time.h>
#include <unistd.h>
#if defined(__linux__)
#include <sched.h>
#endif
typedef int radar_socket;
typedef socklen_t radar_socklen;
#define BAD_SOCKET (-1)
#define close_socket close
#endif
#include "native_core.h"
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    const char *bind, *prefix, *input;
    unsigned port, channel, warmup, repeat;
    uint32_t base;
    double timeout;
    int model, self_test, cpu0, profile;
    uint32_t pl_clock_hz;
} options;

static double now(void) {
#ifdef _WIN32
    LARGE_INTEGER frequency, ticks;
    QueryPerformanceFrequency(&frequency); QueryPerformanceCounter(&ticks);
    return (double)ticks.QuadPart/(double)frequency.QuadPart;
#else
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) { perror("clock_gettime"); exit(1); }
    return ts.tv_sec+ts.tv_nsec/1e9;
#endif
}
static int hardware(const uint32_t *in, uint32_t *out, void *context) {
    (void)context;
#ifdef _WIN32
    (void)in; (void)out;
    return -99;
#else
    return fft128_run_profiled(in, out, 1000, (fft128_profile *)context);
#endif
}
static unsigned number(const char *s, unsigned long limit) {
    char *end;
    errno = 0;
    unsigned long value = strtoul(s, &end, 0);
    if (!*s || *s=='-' || *end || errno || value>limit) {
        fprintf(stderr,"Invalid integer: %s\n",s); exit(2);
    }
    return (unsigned)value;
}
static void usage(const char *name) {
    printf("Usage: %s [--self-test] [--backend mmio|model] [--bind IPv4]\n"
           "  [--port 5000] [--channel 0] [--timeout 120] [--base 0x43c00000]\n"
           "  [--output /tmp/fft128_result] [--input frame.rspb] [--warmup 0] [--repeat 1]\n"
           "Fixed 128 samples x 128 chirps, one frame, no window, Q1.15.\n"
           "  [--cpu0] pins this Linux process to PS CPU0 without taskset.\n"
           "  [--profile-mmio --pl-clock-hz HZ] separate instrumented run; clock must match firmware.\n"
           "Default mmio accesses the FPGA; model is explicit software only.\n",name);
}
static options parse(int argc, char **argv) {
    options o = {"0.0.0.0","fft128_result",NULL,5000,0,0,1,0x43c00000,120,0,0,0,0,0};
    for (int k=1; k<argc; ++k) {
        const char *a = argv[k];
        if (!strcmp(a,"--help")) { usage(argv[0]); exit(0); }
        if (!strcmp(a,"--self-test")) { o.self_test=1; continue; }
        if (!strcmp(a,"--cpu0")) { o.cpu0=1; continue; }
        if (!strcmp(a,"--profile-mmio")) { o.profile=1; continue; }
        if (++k==argc) { fprintf(stderr,"Missing value: %s\n",a); exit(2); }
        const char *v=argv[k];
        if (!strcmp(a,"--backend")) {
            if (strcmp(v,"model") && strcmp(v,"mmio")) { fprintf(stderr,"Invalid backend\n"); exit(2); }
            o.model=!strcmp(v,"model");
        } else if (!strcmp(a,"--bind")) o.bind=v;
        else if (!strcmp(a,"--output")) o.prefix=v;
        else if (!strcmp(a,"--input")) o.input=v;
        else if (!strcmp(a,"--port")) o.port=number(v,65535);
        else if (!strcmp(a,"--channel")) o.channel=number(v,65535);
        else if (!strcmp(a,"--warmup")) o.warmup=number(v,100000);
        else if (!strcmp(a,"--repeat")) o.repeat=number(v,1000000);
        else if (!strcmp(a,"--base")) o.base=number(v,UINT32_MAX);
        else if (!strcmp(a,"--pl-clock-hz")) o.pl_clock_hz=number(v,1000000000);
        else if (!strcmp(a,"--timeout")) {
            char *end;
            o.timeout=strtod(v,&end);
            if (!*v || *end || !isfinite(o.timeout) || o.timeout<=0 || o.timeout>86400) {
                fprintf(stderr,"Invalid timeout\n"); exit(2);
            }
        } else { fprintf(stderr,"Unknown option: %s\n",a); exit(2); }
    }
    if (!o.port || !o.repeat || (o.base & 4095)) { fprintf(stderr,"Invalid port/repeat/base alignment\n"); exit(2); }
    if ((o.profile && (o.model || o.self_test || !o.pl_clock_hz)) || (!o.profile && o.pl_clock_hz)) {
        fprintf(stderr,"Profiling requires MMIO frame mode and explicit --pl-clock-hz matching firmware\n"); exit(2);
    }
    return o;
}
static int self_test(fft128_transform transform) {
    uint32_t in[128], out[128], expected[128];
    const double pi=3.14159265358979323846;
    for (unsigned t=0; t<4; ++t) {
        for (unsigned k=0; k<128; ++k) {
            if (t==0) in[k]=0;
            else if (t==1) in[k]=k ? 0 : fft128_pack(16384,-8192);
            else if (t==2) in[k]=fft128_pack(8192,-4096);
            else in[k]=fft128_pack((int)lrint(12000*cos(2*pi*11*k/128)),
                                   (int)lrint(12000*sin(2*pi*11*k/128)));
        }
        int rc=transform(in,out,NULL);
        if (rc) { fprintf(stderr,"SELFTEST_FAIL: FFT returned %d\n",rc); return -1; }
        fft128_model(in,expected,NULL);
        for (unsigned k=0; k<128; ++k) {
            if (out[k]!=expected[k]) {
                fprintf(stderr,"SELFTEST_FAIL vector=%u bin=%u actual=%08x expected=%08x\n",
                        t,k,(unsigned)out[k],(unsigned)expected[k]); return -1;
            }
        }
    }
    return 0;
}
typedef struct {
    unsigned char seen[128];
    unsigned count, dropped, duplicates;
    double fs;
    fft128_sample *frame;
} collector;
static int accept_packet(collector *c, const unsigned char *p, size_t len, unsigned selected) {
    unsigned channel,index;
    double fs;
    fft128_sample row[128];
    if (fft128_decode(p,len,&channel,&index,&fs,row) || channel!=selected) { ++c->dropped; return 0; }
    if (!c->count) c->fs=fs;
    else if (fs!=c->fs) { fprintf(stderr,"Sampling rate changed during frame\n"); return -1; }
    if (c->seen[index]) { ++c->duplicates; return 0; }
    memcpy(c->frame+index*128,row,sizeof(row));
    c->seen[index]=1; ++c->count;
    return 1;
}
static int offline(const options *o, collector *c) {
    FILE *f=fopen(o->input,"rb");
    if (!f) { perror(o->input); return -1; }
    unsigned char p[65535], header[8], size[4];
    int rc=-1;
    if (fread(header,1,8,f)!=8 || memcmp(header,"RSPB0001",8)) {
        fprintf(stderr,"Invalid replay header\n"); goto finish;
    }
    while (c->count<128) {
        size_t n=fread(size,1,4,f);
        if (!n && feof(f)) break;
        if (n!=4) { fprintf(stderr,"Truncated replay length\n"); goto finish; }
        uint32_t len=((uint32_t)size[0]<<24)|((uint32_t)size[1]<<16)|((uint32_t)size[2]<<8)|size[3];
        if (len>sizeof(p) || fread(p,1,len,f)!=len) { fprintf(stderr,"Truncated/oversize replay packet\n"); goto finish; }
        if (accept_packet(c,p,len,o->channel)<0) goto finish;
    }
    if (c->count!=128) { fprintf(stderr,"Incomplete frame: %u/128 chirps\n",c->count); goto finish; }
    rc=0;
finish:
    fclose(f); return rc;
}
static int receive(const options *o, collector *c) {
#ifdef _WIN32
    WSADATA data;
    if (WSAStartup(MAKEWORD(2,2),&data)) return -1;
#endif
    radar_socket s=socket(AF_INET,SOCK_DGRAM,0);
    if (s==BAD_SOCKET) { fprintf(stderr,"UDP socket failed\n"); return -1; }
    int buffer=1024*1024;
    setsockopt(s,SOL_SOCKET,SO_RCVBUF,(const char *)&buffer,sizeof(buffer));
    struct sockaddr_in local,peer;
    memset(&local,0,sizeof(local)); memset(&peer,0,sizeof(peer));
    local.sin_family=AF_INET; local.sin_port=htons((uint16_t)o->port);
    int rc=-1, locked=0;
    if (inet_pton(AF_INET,o->bind,&local.sin_addr)!=1 || bind(s,(struct sockaddr *)&local,sizeof(local))) {
        fprintf(stderr,"UDP bind failed: %s:%u\n",o->bind,o->port); goto finish;
    }
    printf("LISTENING %s:%u channel=%u 128x128\n",o->bind,o->port,o->channel); fflush(stdout);
    double deadline=now()+o->timeout;
    while (c->count<128) {
        double remaining=deadline-now();
        if (remaining<=0) { fprintf(stderr,"Incomplete frame: %u/128 chirps (timeout)\n",c->count); goto finish; }
        struct timeval tv;
        tv.tv_sec=(long)remaining; tv.tv_usec=(long)((remaining-tv.tv_sec)*1e6);
        fd_set rd;
#ifndef _WIN32
        if (s>=FD_SETSIZE) { fprintf(stderr,"UDP descriptor too large\n"); goto finish; }
#endif
        FD_ZERO(&rd); FD_SET(s,&rd);
#ifdef _WIN32
        int selected=select(0,&rd,NULL,NULL,&tv);
#else
        int selected=select(s+1,&rd,NULL,NULL,&tv);
#endif
        if (selected<0) {
#ifndef _WIN32
            if (errno==EINTR) continue;
#endif
            fprintf(stderr,"UDP select failed\n"); goto finish;
        }
        if (!selected) continue;
        unsigned char p[65535]; struct sockaddr_in source;
        radar_socklen source_len=sizeof(source);
        int len=(int)recvfrom(s,(char *)p,sizeof(p),0,(struct sockaddr *)&source,&source_len);
        if (len<0) { fprintf(stderr,"UDP receive failed\n"); goto finish; }
        if (locked && (source.sin_addr.s_addr!=peer.sin_addr.s_addr || source.sin_port!=peer.sin_port)) {
            ++c->dropped; continue;
        }
        int accepted=accept_packet(c,p,(size_t)len,o->channel);
        if (accepted<0) goto finish;
        if (accepted && !locked) { peer=source; locked=1; }
    }
    rc=0;
finish:
    close_socket(s);
#ifdef _WIN32
    WSACleanup();
#endif
    return rc;
}
static FILE *output_file(const char *prefix, const char *suffix) {
    char path[4096];
    int n=snprintf(path,sizeof(path),"%s%s",prefix,suffix);
    if (n<0 || (size_t)n>=sizeof(path)) { fprintf(stderr,"Output path too long\n"); return NULL; }
    FILE *f=fopen(path,"w");
    if (!f) perror(path);
    return f;
}
static int checked_close(FILE *f) {
    int failed=ferror(f);
    return fclose(f) || failed;
}
static int compare_double(const void *a, const void *b) {
    double x=*(const double *)a, y=*(const double *)b;
    return (x>y)-(x<y);
}
static int save(const options *o, const collector *c, const uint32_t *spectrum,
                 double scale, double elapsed, const char *label, const double *times) {
    FILE *f=output_file(o->prefix,".input.csv");
    if (!f) return -1;
    fprintf(f,"chirp,sample,real,imag\n");
    for (unsigned k=0;k<FFT128_BINS;++k)
        fprintf(f,"%u,%u,%.17g,%.17g\n",k/128,k%128,c->frame[k].real,c->frame[k].imag);
    if (checked_close(f)) return -1;
    f=output_file(o->prefix,".csv");
    if (!f) return -1;
    fprintf(f,"doppler_bin_unshifted,range_bin,real_q15,imag_q15\n");
    unsigned peak=0;
    double max_power=-1;
    for (unsigned k=0;k<FFT128_BINS;++k) {
        int r=fft128_real(spectrum[k]), i=fft128_imag(spectrum[k]);
        double power=(double)r*r+(double)i*i;
        if (power>max_power) { peak=k; max_power=power; }
        fprintf(f,"%u,%u,%d,%d\n",k/128,k%128,r,i);
    }
    if (checked_close(f)) return -1;
    f=output_file(o->prefix,".json");
    if (!f) return -1;
    fprintf(f,"{\n  \"backend\": \"%s\",\n  \"implementation\": \"native C\",\n"
              "  \"shape\": [128, 128],\n  \"fft_calls\": 256,\n"
              "  \"sample_rate_hz\": %.17g,\n  \"input_to_q15_scale\": %.17g,\n"
              "  \"window\": \"none\",\n  \"per_fft_normalization\": \"1/128\",\n"
              "  \"total_normalization\": \"1/16384\",\n"
              "  \"fft_and_transfer_seconds\": %.9g,\n  \"warmup\": %u,\n  \"repeats\": %u,\n  \"mismatched_complex_bins\": 0,\n"
              "  \"peak_unshifted\": [%u, %u],\n"
              "  \"dropped_packets\": %u,\n  \"duplicate_packets\": %u,\n"
              "  \"profiling\": %s,\n  \"pl_clock_hz_declared\": %u,\n"
              "  \"note\": \"Repeated same frame; average time includes MMIO, FFT, PS transpose; work buffers preallocated. Excludes input IO, quantization, validation, files. No DMA.\"\n}\n",
              label,c->fs,scale,elapsed,o->warmup,o->repeat,peak/128,peak%128,c->dropped,c->duplicates,
              o->profile ? "true" : "false",o->pl_clock_hz);
    if (checked_close(f)) return -1;
    f=output_file(o->prefix,".timings.csv");
    if (!f) return -1;
    fprintf(f,"stage,iteration,wall_ms\n");
    for (unsigned k=0;k<o->repeat;++k) fprintf(f,"fft_pipeline,%u,%.9g\n",k+1,times[k]*1000);
    if (checked_close(f)) return -1;
    printf("peak_unshifted=(%u,%u) fft_and_transfer_seconds=%.6f\n",peak/128,peak%128,elapsed);
    return 0;
}
static int save_profiles(const options *o, const fft128_profile *profiles, const double *times) {
    FILE *f=output_file(o->prefix,".profile.csv");
    if(!f) return -1;
    fprintf(f,"iteration,wall_ms,input_write_ms,start_wait_ms,counter_read_ms,output_read_ms,gather_ms,scatter_ms,pl_cycles,pl_internal_ms,fft_calls,min_cycles,max_cycles,pl_clock_hz_declared\n");
    double core_ms=0, write_ms=0, wait_ms=0, read_ms=0, transpose_ms=0;
    for(unsigned k=0;k<o->repeat;++k) {
        const fft128_profile *p=profiles+k;
        double internal=p->pl_cycles*1000.0/o->pl_clock_hz;
        fprintf(f,"%u,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%llu,%.9g,%u,%u,%u,%u\n",
                k+1,times[k]*1000,p->input_write_ns/1e6,p->start_wait_ns/1e6,
                p->counter_read_ns/1e6,p->output_read_ns/1e6,p->gather_ns/1e6,p->scatter_ns/1e6,
                (unsigned long long)p->pl_cycles,internal,p->calls,p->min_cycles,p->max_cycles,o->pl_clock_hz);
        core_ms+=internal; write_ms+=p->input_write_ns/1e6; wait_ms+=p->start_wait_ns/1e6;
        read_ms+=p->output_read_ns/1e6; transpose_ms+=(p->gather_ns+p->scatter_ns)/1e6;
    }
    if(checked_close(f)) return -1;
    printf("MMIO_PROFILE: write_ms=%.6f start_wait_ms=%.6f read_ms=%.6f gather_scatter_ms=%.6f pl_internal_ms=%.6f cycles_per_fft=%u..%u clock_hz_declared=%u\n",
           write_ms/o->repeat,wait_ms/o->repeat,read_ms/o->repeat,transpose_ms/o->repeat,
           core_ms/o->repeat,profiles[0].min_cycles,profiles[0].max_cycles,o->pl_clock_hz);
    printf("MMIO_PROFILE: PL internal time overlaps start_wait; do not add it to host stages. Instrumented timing is separate from baseline.\n");
    return 0;
}
int main(int argc, char **argv) {
    options o=parse(argc,argv);
    if(o.cpu0) {
#if defined(__linux__)
        cpu_set_t set; CPU_ZERO(&set); CPU_SET(0,&set);
        if(sched_setaffinity(0,sizeof(set),&set)) { perror("CPU0 affinity failed"); return 1; }
        printf("CPU_AFFINITY=0\n"); fflush(stdout);
#else
        fprintf(stderr,"--cpu0 requires Linux\n"); return 1;
#endif
    }
    const char *label=o.model ? "SOFTWARE_MODEL (no FPGA access)" : "PL_MMIO";
    fft128_transform transform=o.model ? fft128_model : hardware;
    int result=1, opened=0;
    fft128_sample *frame=NULL;
    uint32_t *packed=NULL, *spectrum=NULL, *expected=NULL;
    uint32_t *workspace=NULL;
    double *times=NULL;
    fft128_profile *profiles=NULL;
    if (!o.model) {
#ifdef _WIN32
        fprintf(stderr,"MMIO backend requires Linux on the board; no software fallback.\n"); return 1;
#else
        int rc=fft128_open(o.base);
        if (rc) { fprintf(stderr,"MMIO open failed (%d); verify bitstream, FCLK/reset and root access.\n",rc); return 1; }
        opened=1;
#endif
    }
    printf("BACKEND=%s implementation=native_C\n",label); fflush(stdout);
    if (o.self_test) {
        if (!self_test(transform)) { printf("SELFTEST_PASS backend=%s vectors=4 bins=512\n",label); result=0; }
        goto finish;
    }
    frame=calloc(FFT128_BINS,sizeof(*frame));
    packed=malloc(FFT128_BINS*sizeof(*packed));
    spectrum=malloc(FFT128_BINS*sizeof(*spectrum));
    expected=malloc(FFT128_BINS*sizeof(*expected));
    workspace=malloc(FFT128_BINS*sizeof(*workspace));
    times=malloc((size_t)o.repeat*sizeof(*times));
    if(o.profile) profiles=calloc(o.repeat,sizeof(*profiles));
    if (!frame || !packed || !spectrum || !expected || !workspace || !times || (o.profile && !profiles)) { fprintf(stderr,"Out of memory\n"); goto finish; }
    collector c={{0},0,0,0,0,frame};
    if ((o.input ? offline(&o,&c) : receive(&o,&c))) goto finish;
    double scale;
    if (fft128_quantize(frame,packed,&scale)) { fprintf(stderr,"Invalid input scale\n"); goto finish; }
    if (fft128_process(packed,expected,fft128_model,NULL)) goto finish;
    printf("BENCHMARK: warmup=%u repeat=%u preallocated buffers; data path=%s\n",o.warmup,o.repeat,label); fflush(stdout);
    double elapsed=0;
    for (unsigned k=0;k<o.warmup+o.repeat;++k) {
        fft128_profile current={0};
        fft128_profile *profile=o.profile ? &current : NULL;
        double started=now();
        int rc=fft128_process_profiled(packed,spectrum,workspace,transform,profile,profile);
        double duration=now()-started;
        if (rc) { fprintf(stderr,"FFT processing failed (%d); frame aborted\n",rc); goto finish; }
        if(profile && (current.calls!=256 || !current.min_cycles)) {
            fprintf(stderr,"Invalid hardware profile counter data\n"); goto finish;
        }
        unsigned errors=0;
        for (unsigned bin=0;bin<FFT128_BINS;++bin) if(spectrum[bin]!=expected[bin]) ++errors;
        if (errors) { fprintf(stderr,"BIT_EXACT_FAIL iteration=%u: %u/16384 complex bins\n",k,errors); goto finish; }
        if (k>=o.warmup) {
            times[k-o.warmup]=duration; elapsed+=duration;
            if(profiles) profiles[k-o.warmup]=current;
        }
    }
    elapsed/=o.repeat;
    if (save(&o,&c,spectrum,scale,elapsed,label,times)) { fprintf(stderr,"Output write failed\n"); goto finish; }
    if(profiles && save_profiles(&o,profiles,times)) { fprintf(stderr,"Profile output write failed\n"); goto finish; }
    qsort(times,o.repeat,sizeof(*times),compare_double);
    double median=o.repeat%2 ? times[o.repeat/2] : (times[o.repeat/2-1]+times[o.repeat/2])/2;
    printf("PIPELINE_TIMING backend=%s mean_ms=%.6f median_ms=%.6f min_ms=%.6f max_ms=%.6f repeats=%u\n",
           label,elapsed*1000,median*1000,times[0]*1000,times[o.repeat-1]*1000,o.repeat);
    printf("FRAME_PASS backend=%s bit_exact_bins=16384\n",label);
    result=0;
finish:
    free(frame); free(packed); free(spectrum); free(expected); free(workspace); free(times); free(profiles);
#ifndef _WIN32
    if (opened) fft128_close();
#else
    (void)opened;
#endif
    return result;
}
