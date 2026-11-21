#!/usr/bin/env python3
"""E14 fixed full-frame overlay, retaining captured live-DT collision checks."""
import importlib.util
import json
from pathlib import Path
import sys
spec=importlib.util.spec_from_file_location('batch_overlay',Path(__file__).resolve().parent.parent/'dma_batch/make_overlay.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def make_overlay(archive):
    text,meta=m.make_overlay(archive)
    text=text.replace('e11b','e14_frame').replace('fmcw,fft128-dma-batch-v2','fmcw,fft128-dma-frame-v8')
    meta.update(experiment='E14-frame',register_abi=8,parallel_cores=1,streaming_stages=7,total_butterflies=7,
                frame_initiation_interval=128,fft_vector_initiation_interval=128,full_frame_overlap=False,
                frame_schedule='range_then_doppler_then_row_major_drain',group_barrier=False,next_group_prefetch=False,next_vector_prefetch=True,
                external_ping_pong=False,external_buffers=False,stage_frame_slots=True,
                buffering='per_stage_double_frame_slots_and_inplace_matrix',pl_transpose=True,pl_output_reorder=True,
                cpu_transpose=False,in_place_matrix=True,matrix_bytes=65536,fft_per_request=256,frame_words=16384,
                dma_requests_per_frame=1,dma_channel_submissions_per_frame=2,payload_bytes_per_frame=131072,
                output_order='doppler-major/range-minor')
    return text,meta

if __name__=='__main__':
    text,meta=make_overlay(sys.argv[1]);p=Path(sys.argv[2]);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text,encoding='utf-8');p.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print('DMA_FRAME_OVERLAY_READY:',p)
