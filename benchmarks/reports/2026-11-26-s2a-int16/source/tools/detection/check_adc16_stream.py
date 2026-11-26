"""Recompute ADC FFT/CFAR independently from raw sender/receiver files."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import adc16_reference as adc
import analyze_stream

DEFAULT=adc.ref.ROOT/'benchmarks/fixtures/adc16/radarsimpy_128x128_sim_multi4_noise_adc16.rspb'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(out,sender,record=DEFAULT,require_board=True,allow_loss=False):
    out,sender,record=Path(out),Path(sender),Path(record)
    trace=out/'trace' if (out/'trace').is_dir() else out
    env=analyze_stream.fields(trace/'environment.txt')
    sent=json.loads(sender.read_text(encoding='utf-8'))
    summary=analyze_stream.analyze(trace,sender)
    if env.get('input_format')!='adc16' or int(env.get('adc_bits',0))!=16 or float(env.get('adc_scale',0))!=1600000:
        raise ValueError('Not frozen ADC profile1')
    if sent['record_sha256']!=sha(record):raise ValueError('Sender input SHA differs from checked ADC record')
    if not summary['trace_valid'] or (not allow_loss and not summary['zero_drops']):
        raise ValueError('Invalid trace or dropped frames; raw summary retained')
    if require_board:
        if env['backend'] not in ('ps','pl') or not (out/'runtime.txt').is_file():
            raise ValueError('Missing physical board context')
        runtime=(out/'runtime.txt').read_text()
        if 'armv7' not in runtime.lower():raise ValueError('Expected ARM board runtime')
        bundle=out.parent
        for line in (bundle/'artifacts.sha256').read_text().splitlines():
            digest,name=line.split(None,1);name=name.strip()
            if Path(name).is_absolute() or '..' in Path(name).parts or sha(bundle/name)!=digest:
                raise ValueError('Bundle artifact SHA mismatch')
        for name in ('clock_before.txt','clock_after.txt','receiver_exit.txt','artifact_check.txt'):
            if not (out/name).is_file():raise ValueError('Missing runtime evidence '+name)
        for name in ('artifacts.sha256','source.sha256','build_environment.txt'):
            if (out/name).read_bytes()!=(bundle/name).read_bytes():
                raise ValueError('Runtime and bundle identity differ')
        if sha(bundle/'stream-receiver') not in runtime or sha(bundle/'libfftw3.so.3') not in runtime:
            raise ValueError('Runtime binary/library SHA differs from verified bundle')
        if not allow_loss and (out/'receiver_exit.txt').read_text().strip()!='0':
            raise ValueError('Board receiver did not exit successfully')
    expected,threshold,peaks,accuracy=adc.accuracy(record,env['backend'],env['window'])
    power=expected.real**2+expected.imag**2
    with (trace/'detections.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    grouped=defaultdict(list)
    for row in rows:grouped[int(row['frame_id'])].append(row)
    for frame, detections in grouped.items():
        actual=[(int(row['doppler_bin']),int(row['range_bin'])) for row in detections]
        if not peaks:
            if actual!=[(-1,-1)]:raise ValueError('Expected empty-output sentinel')
            continue
        if actual!=peaks:raise ValueError(f'Independent CFAR bins differ at frame {frame}')
        for row,peak in zip(detections,peaks):
            np.testing.assert_allclose(float(row['power']),power[peak],rtol=1e-9,atol=1e-7)
            np.testing.assert_allclose(float(row['threshold']),threshold[peak],rtol=1e-9,atol=1e-7)
    full_bins=False
    diagnostic=trace/'diagnostic_spectrum.csv'
    if env.get('diagnostic_spectrum')=='1':
        bins=np.loadtxt(diagnostic,delimiter=',',skiprows=1)
        if bins.shape!=(16384,5) or len(set(bins[:,0]))!=1 or int(bins[0,0]) not in grouped:
            raise ValueError('Invalid full spectrum diagnostic')
        d,r=np.indices((128,128))
        np.testing.assert_array_equal(bins[:,1:3],np.column_stack((d.ravel(),r.ravel())))
        actual=(bins[:,3]+1j*bins[:,4]).reshape(128,128)
        if env['backend'] in ('pl','model'):np.testing.assert_array_equal(actual,expected)
        else:np.testing.assert_allclose(actual,expected,rtol=1e-9,atol=1e-9)
        full_bins=True
    if summary['diagnostic_probe'] and not full_bins:raise ValueError('Diagnostic requires all-bin output')
    identity={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and
              p.name not in ('summary.json','adc16_verified.json')}
    result={'experiment':'S2a-int16','evidence':'board raw independently recomputed' if require_board else 'PC loopback',
            'backend':env['backend'],'hardware':env['backend']=='pl','record_sha256':sha(record),
            'sender_sha256':sha(sender),'processed_frames_checked':len(grouped),'accuracy':accuracy,
            'first_frame_all_bins_checked':full_bins,'trace_valid':summary['trace_valid'],
            'zero_drops':summary['zero_drops'],'offered_load_valid':summary['offered_load_valid'],
            'diagnostic_only':summary['diagnostic_probe'],'metrics':summary['metrics'],
            'raw_sha256':identity,'acceptance_10000_frames':False}
    (out/'adc16_verified.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('out',type=Path)
    p.add_argument('--sender',type=Path,required=True)
    p.add_argument('--record',type=Path,default=DEFAULT)
    p.add_argument('--allow-loss',action='store_true',help='Analyze preliminary failures; never an acceptance pass')
    a=p.parse_args()
    result=check(a.out,a.sender,a.record,allow_loss=a.allow_loss)
    print('ADC16_INDEPENDENT_CHECK_PASS backend='+result['backend']+
          ' frames='+str(result['processed_frames_checked'])+' all_bins='+str(result['first_frame_all_bins_checked']))
    print(json.dumps({'accuracy':result['accuracy'],'preparation':result['metrics']['preparation'],
                      'zero_drops':result['zero_drops'],'offered_load_valid':result['offered_load_valid']},indent=2))
