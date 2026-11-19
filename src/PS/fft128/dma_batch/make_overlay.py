#!/usr/bin/env python3
"""E11b overlay; reuse live-DT resource validation, distinct compatible/clock."""
import importlib.util
import json
from pathlib import Path
import sys
spec=importlib.util.spec_from_file_location('e11a_overlay',Path(__file__).resolve().parent.parent/'dma/make_overlay.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def make_overlay(archive):
    text,meta=m.make_overlay(archive)
    text=text.replace('e11a','e11b').replace('fmcw,fft128-dma-v1','fmcw,fft128-dma-batch-v2')
    meta.update(experiment='E11b',register_abi=2,fft_per_request=128,bytes_per_direction=65536)
    return text,meta
if __name__=='__main__':
    text,meta=make_overlay(sys.argv[1]);p=Path(sys.argv[2]);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text);p.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('DMA_BATCH_OVERLAY_READY:',p)
