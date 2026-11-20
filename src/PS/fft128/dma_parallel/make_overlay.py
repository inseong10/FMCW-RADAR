#!/usr/bin/env python3
"""E13 two-core overlay; reuse recorded live-DT collision validation."""
import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('batch_overlay',Path(__file__).resolve().parent.parent/'dma_batch/make_overlay.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def make_overlay(archive):
    text,meta=m.make_overlay(archive)
    text=text.replace('e11b','e13_2core').replace('fmcw,fft128-dma-batch-v2','fmcw,fft128-dma-parallel-v3')
    meta.update(experiment='E13-2core',register_abi=3,parallel_cores=2,pair_barrier=True,next_pair_prefetch=False,external_ping_pong=False)
    return text,meta
if __name__=='__main__':
    text,meta=make_overlay(sys.argv[1]);p=Path(sys.argv[2]);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text,encoding='utf-8');p.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print('DMA_PARALLEL_OVERLAY_READY:',p)
