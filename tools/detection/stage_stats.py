"""Stage statistics from a recovered frames.csv (reference only; acceptance is check_adc16_stream.py).

Same computation as build/s3a0_stage_stats.py (S3a-0..S3a-4, SHA eb6bc3a4...). Optional PERIOD_MS adds
c2o_over_period (frames whose assembly-complete -> CSV flush exceeds the period).
Usage: stage_stats.py FRAMES_CSV [PERIOD_MS]
"""
import csv, json, sys
import numpy as np
rows=[r for r in csv.DictReader(open(sys.argv[1])) if r['status']=='processed']
g=lambda r,k:int(r[k])
def s(a,b):
    v=np.array([(g(r,b)-g(r,a))/1e6 for r in rows]);return {'median':round(float(np.median(v)),3),'p99':round(float(np.percentile(v,99)),3),'max':round(float(v.max()),3)}
out={'processed':len(rows),'queue_wait':s('complete_ns','process_start_ns'),'prepare':s('process_start_ns','prepared_ns'),
     'fft':s('prepared_ns','fft_done_ns'),'cfar':s('fft_done_ns','cfar_done_ns'),'flush':s('cfar_done_ns','output_done_ns'),
     'process_total':s('process_start_ns','output_done_ns'),'complete_to_output':s('complete_ns','output_done_ns')}
c2o=np.array([(g(r,'output_done_ns')-g(r,'complete_ns'))/1e6 for r in rows]);out['c2o_over_12p8']=int((c2o>12.8).sum())
if len(sys.argv)>2:
    period=float(sys.argv[2]);out['period_ms']=period;out['c2o_over_period']=int((c2o>period).sum())
print(json.dumps(out,indent=1))
