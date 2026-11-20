#!/usr/bin/env python3
"""E13 seven-stage frame-streaming overlay; reuse recorded live-DT collision validation."""
import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('batch_overlay',Path(__file__).resolve().parent.parent/'dma_batch/make_overlay.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def make_overlay(archive):
    text,meta=m.make_overlay(archive)
    text=text.replace('e11b','e13_stream').replace('fmcw,fft128-dma-batch-v2','fmcw,fft128-dma-stream-v7')
    meta.update(**{'experiment': 'E13-stream', 'register_abi': 7, 'parallel_cores': 1, 'streaming_stages': 7, 'total_butterflies': 7, 'frame_initiation_interval': 128, 'group_barrier': False, 'next_group_prefetch': False, 'next_vector_prefetch': True, 'external_ping_pong': False, 'external_buffers': False, 'stage_frame_slots': True, 'buffering': 'per_stage_double_frame_slots'})
    return text,meta
if __name__=='__main__':
    text,meta=make_overlay(sys.argv[1]);p=Path(sys.argv[2]);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text,encoding='utf-8');p.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print('DMA_STREAM_OVERLAY_READY:',p)
