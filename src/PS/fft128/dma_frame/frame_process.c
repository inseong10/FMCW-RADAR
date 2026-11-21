// E14 has one full-frame transfer; all matrix layout changes happen in PL.
#include <stdio.h>
#include <stdlib.h>
#include "frame_process.h"
int fft128_process_frame(const uint32_t *input,uint32_t *output,fft128_profile *p) {
    if(!input || !output) return -1;
    return fft128_frame_transfer(input,output,1000,p);
}
int fft128_frame_selftest(void) {
    static uint32_t input[FFT128_BINS],output[FFT128_BINS],expected[FFT128_BINS];
    for(unsigned trial=0;trial<4;++trial) {
        for(unsigned ch=0;ch<128;++ch) for(unsigned sample=0;sample<128;++sample) {
            unsigned k=ch*128+sample;
            input[k]=trial==0 ? 0 : trial==1 ? (k==17*128+93 ? fft128_pack(32767,-32768) : 0) :
                trial==2 ? fft128_pack(32767,32767) :
                fft128_pack((int)((ch*173+sample*79+ch*sample*11)%65536)-32768,
                            (int)((ch*31+sample*997+ch*sample*17)%65536)-32768);
        }
        if(fft128_process(input,expected,fft128_model,NULL) || fft128_process_frame(input,output,NULL)) return -1;
        for(unsigned k=0;k<FFT128_BINS;++k) if(output[k]!=expected[k]) {
            fprintf(stderr,"FRAME_SELFTEST_FAIL trial=%u bin=%u\n",trial,k);return -1;
        }
    }
    return 0;
}
int fft128_frame_save_profiles(const char *prefix,unsigned repeat,uint32_t hz,
                              const fft128_profile *profiles,const double *times) {
    if(!prefix || !repeat || !hz || !profiles || !times) return -1;
    size_t size=0;while(prefix[size]) ++size;
    char *path=malloc(size+13);
    if(!path) return -1;
    snprintf(path,size+13,"%s.profile.csv",prefix);
    FILE *f=fopen(path,"w");free(path);
    if(!f) return -1;
    fprintf(f,"iteration,wall_ms,host_input_copy_ms,ioctl_ms,host_output_copy_ms,gather_ms,scatter_ms,kernel_copy_in_ms,kernel_submit_ms,kernel_wait_ms,kernel_check_ms,kernel_copy_out_ms,pl_active_cycles,pl_active_ms,input_stall_cycles,output_stall_cycles,fft_calls,min_active_cycles,max_active_cycles,pl_clock_hz_declared,bytes_each_direction_per_fft,dma_requests,dma_channel_submissions,fft_per_request,bytes_each_direction_per_request,payload_bytes_per_frame,streaming_cores,streaming_stages,range_cycles,doppler_cycles,drain_cycles,matrix_reads,matrix_writes,range_outputs,doppler_inputs,doppler_outputs,overwrite_errors,io_overlap_cycles,matrix_words,stage_busy_cycles,multi_stage_cycles,vector_overlap_cycles");
    for(unsigned s=0;s<7;++s) fprintf(f,",stage%u_issue",s);
    for(unsigned s=0;s<7;++s) fprintf(f,",stage%u_retire",s);
    fprintf(f,"\n");
    for(unsigned k=0;k<repeat;++k) {
        const fft128_profile *p=profiles+k;
        fprintf(f,"%u,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%llu,%.9g,%llu,%llu,256,%u,%u,%u,0,%u,%u,256,65536,131072,1,7",
                k+1,times[k]*1000,p->input_write_ns/1e6,p->start_wait_ns/1e6,p->output_read_ns/1e6,p->gather_ns/1e6,p->scatter_ns/1e6,
                p->dma_copy_in_ns/1e6,p->dma_submit_ns/1e6,p->dma_wait_ns/1e6,p->dma_check_ns/1e6,p->dma_copy_out_ns/1e6,
                (unsigned long long)p->pl_cycles,p->pl_cycles*1000.0/hz,(unsigned long long)p->dma_input_stalls,(unsigned long long)p->dma_output_stalls,
                p->min_cycles,p->max_cycles,hz,p->calls,p->calls*2);
        const uint64_t fields[]={p->frame_range_cycles,p->frame_doppler_cycles,p->frame_drain_cycles,
            p->frame_matrix_reads,p->frame_matrix_writes,p->frame_range_outputs,p->frame_doppler_inputs,p->frame_doppler_outputs,
            p->frame_overwrite_errors,p->frame_io_overlap_cycles,p->frame_matrix_words,
            p->frame_stage_busy_cycles,p->frame_multi_stage_cycles,p->frame_vector_overlap_cycles};
        for(unsigned j=0;j<sizeof(fields)/sizeof(fields[0]);++j) fprintf(f,",%llu",(unsigned long long)fields[j]);
        for(unsigned s=0;s<7;++s) fprintf(f,",%llu",(unsigned long long)p->frame_issue_events[s]);
        for(unsigned s=0;s<7;++s) fprintf(f,",%llu",(unsigned long long)p->frame_retire_events[s]);
        fprintf(f,"\n");
    }
    int bad=ferror(f);
    if(fclose(f)) bad=1;
    printf("FRAME_PROFILE: one full-frame ioctl, PL Range/transpose/Doppler/reorder; nested PL/kernel times overlap ioctl, do not add to host stages.\n");
    return bad ? -1 : 0;
}
