#!/usr/bin/env python3
"""E13 two-butterfly four-core overlay; reuse recorded live-DT collision validation."""
import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('batch_overlay',Path(__file__).resolve().parent.parent/'dma_batch/make_overlay.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def make_overlay(archive):
    text,meta=m.make_overlay(archive)
    text=text.replace('e11b','e13_bf2').replace('fmcw,fft128-dma-batch-v2','fmcw,fft128-dma-bf2-v6')
    meta.update(experiment='E13-bf2',register_abi=6,parallel_cores=4,butterflies_per_core=2,total_butterflies=8,group_barrier=False,next_group_prefetch=True,external_ping_pong=False,external_buffers=True,buffering="per_lane_fifos")
    return text,meta
if __name__=='__main__':
    text,meta=make_overlay(sys.argv[1]);p=Path(sys.argv[2]);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text,encoding='utf-8');p.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print('DMA_BF2_OVERLAY_READY:',p)
