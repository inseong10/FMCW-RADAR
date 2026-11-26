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


NETWORK_LOSS_STATUSES={'processed','partial','partial_evicted','missing'}


def lost_packets(trace,pulses=128):
    """Packets absent from non-processed frames (pulses chirps per frame)."""
    rows=csv.DictReader((Path(trace)/'frames.csv').open(newline=''))
    return sum(pulses-int(r['packets']) for r in rows if r['status']!='processed')


def check(out,sender,record=DEFAULT,require_board=True,allow_loss=False,network_loss_ok=False):
    out,sender,record=Path(out),Path(sender),Path(record)
    trace=out/'trace' if (out/'trace').is_dir() else out
    env=analyze_stream.fields(trace/'environment.txt')
    sent=json.loads(sender.read_text(encoding='utf-8'))
    summary=analyze_stream.analyze(trace,sender)
    M,N=int(env.get('pulses',128)),int(env.get('samples',128))  # S3a-1 frame shape
    if env.get('input_format')!='adc16' or int(env.get('adc_bits',0))!=16 or float(env.get('adc_scale',0))!=1600000:
        raise ValueError('Not frozen ADC profile1')
    if sent['record_sha256']!=sha(record):raise ValueError('Sender input SHA differs from checked ADC record')
    # network_loss_ok (user decision 2026-11-26): UDP socket loss (kernel_drops) is a test-path property,
    # reported but not a processing failure. Every other invalidating counter and queue_full still fail.
    # S3a-0 (2026-11-26): a fully 'missing' frame is also network loss, but only when every absent packet
    # is accounted for by kernel_drops (lost packets == kernel_drops exactly).
    net_only=(network_loss_ok and set(summary['invalidating_counters'])<={'kernel_drops'} and
              set(summary['status_counts'])<=NETWORK_LOSS_STATUSES and
              lost_packets(trace,M)==int(summary['counters']['kernel_drops']))
    if not (summary['trace_valid'] or net_only) or (not allow_loss and not net_only and not summary['zero_drops']):
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
        if not allow_loss and not net_only and (out/'receiver_exit.txt').read_text().strip()!='0':
            raise ValueError('Board receiver did not exit successfully')
    expected,threshold,peaks,accuracy=adc.accuracy(record,env['backend'],env['window'])
    if expected.shape!=(M,N):raise ValueError('Record shape differs from receiver shape')
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
        if bins.shape!=(M*N,5) or len(set(bins[:,0]))!=1 or int(bins[0,0]) not in grouped:
            raise ValueError('Invalid full spectrum diagnostic')
        d,r=np.indices((M,N))
        np.testing.assert_array_equal(bins[:,1:3],np.column_stack((d.ravel(),r.ravel())))
        actual=(bins[:,3]+1j*bins[:,4]).reshape(M,N)
        if env['backend'] in ('pl','model'):np.testing.assert_array_equal(actual,expected)
        else:np.testing.assert_allclose(actual,expected,rtol=1e-9,atol=1e-9)
        full_bins=True
    if summary['diagnostic_probe'] and not full_bins:raise ValueError('Diagnostic requires all-bin output')
    identity={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and
              p.name not in ('summary.json','adc16_verified.json')}
    period=float(sent['period_ms'])
    c2o=summary['metrics']['complete_to_output']['p99_ms']
    f2o=summary['metrics']['first_kernel_to_output']['p99_ms']
    realtime={'definition':'P99(receiver assembly complete of frame N -> frame N CSV flush) < period; '
                           'equivalently frame N output before frame N+1 assembly completes (user decision 2026-11-26)',
              'start':'complete_ns = receiver user-space time after the last chirp is assembled (not a kernel timestamp)',
              'period_ms':period,'sender_pacing':('chirp gap %gus, %s schedule'%(sent['chirp_gap_us'],sent.get('chirp_pacing',{}).get('schedule','absolute'))
                                                    if sent.get('chirp_gap_us') else 'burst'),
              'period_basis':'nominal period_ms; a reanchor schedule only lengthens intervals, so this is the stricter bound',
              'complete_to_output_p99_ms':c2o,'meets':c2o<period,
              'secondary_first_kernel_to_output_p99_ms':f2o,'secondary_first_kernel_meets':f2o<period,
              'note':'200-frame or lossy runs are preliminary; acceptance needs 10,000 frames'}
    result={'experiment':'S2a-int16','pulses':M,'samples':N,'evidence':'board raw independently recomputed' if require_board else 'PC loopback',
            'backend':env['backend'],'hardware':env['backend']=='pl','record_sha256':sha(record),
            'sender_sha256':sha(sender),'processed_frames_checked':len(grouped),'accuracy':accuracy,
            'first_frame_all_bins_checked':full_bins,'trace_valid':summary['trace_valid'],
            'zero_drops':summary['zero_drops'],'offered_load_valid':summary['offered_load_valid'],
            'diagnostic_only':summary['diagnostic_probe'],'metrics':summary['metrics'],
            'sender':summary.get('sender'),'realtime_criterion':realtime,
            'raw_sha256':identity,'acceptance_10000_frames':False}
    if network_loss_ok:
        lost=sorted(int(r['frame_id']) for r in csv.DictReader((trace/'frames.csv').open(newline='')) if r['status']!='processed')
        frames=int(summary['expected'])
        result['processing_realtime']={
            'definition':'user decision 2026-11-26: continuous run of the expected frames; P99(assembly complete -> CSV flush) < period; '
                         'no queue_full; valid offered load; all counters other than kernel_drops zero. UDP network loss '
                         '(kernel_drops and the partial/evicted/missing frames it causes, lost packets == kernel_drops) is reported, not a processing failure',
            'frames_expected':frames,'frames_processed':len(grouped),'network_lost_frames':lost,
            'kernel_drops':int(summary['counters']['kernel_drops']),'lost_packets':lost_packets(trace,M),'queue_full':summary['status_counts'].get('queue_full',0),
            'complete_to_output_p99_ms':c2o,'period_ms':period,
            'meets':bool(net_only and c2o<period and summary['offered_load_valid'] and frames>=10000)}

    (out/'adc16_verified.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('out',type=Path)
    p.add_argument('--sender',type=Path,required=True)
    p.add_argument('--record',type=Path,default=DEFAULT)
    p.add_argument('--allow-loss',action='store_true',help='Analyze preliminary failures; never an acceptance pass')
    p.add_argument('--network-loss-ok',action='store_true',help='Report UDP kernel_drops as test-path loss (2026-11-26 rule)')
    a=p.parse_args()
    result=check(a.out,a.sender,a.record,allow_loss=a.allow_loss,network_loss_ok=a.network_loss_ok)
    print('ADC16_INDEPENDENT_CHECK_PASS backend='+result['backend']+
          ' frames='+str(result['processed_frames_checked'])+' all_bins='+str(result['first_frame_all_bins_checked']))
    print(json.dumps({'accuracy':result['accuracy'],'preparation':result['metrics']['preparation'],
                      'zero_drops':result['zero_drops'],'offered_load_valid':result['offered_load_valid'],
                      'realtime_criterion':result['realtime_criterion'],
                      'processing_realtime':result.get('processing_realtime')},indent=2))
