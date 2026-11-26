"""S3a-3 host loopback: frozen RadarSimPy 128x256 fixture at the production period (12.8 ms, chirp 100us)."""
import json, sys
from pathlib import Path
root = Path(sys.argv[1]); out = Path(sys.argv[2]); binary = Path(sys.argv[3])
sys.path.insert(0, str(root/'tools/detection'))
import smoke_s2a, check_adc16_stream
record = root/'benchmarks/fixtures/s3a/radarsimpy_128x256_sim_multi4_noise_adc16.rspb'
out.mkdir(parents=True, exist_ok=False)
rows = []
for run, backend in ((92421, "model"), (92422, "ps")):
    sub = out/backend; sub.mkdir()
    smoke_s2a.case(binary.resolve(), sub, backend, run, diagnostic=True, adc16=True, record=record,
                   shape=(128, 256), period_ms=12.8, frames=20, chirp_gap_us=100)
    folder = sub/(backend+'_normal')
    v = check_adc16_stream.check(folder, sub/(folder.name+'_sender.json'), record=record, require_board=False)
    a = v['accuracy']
    assert v['first_frame_all_bins_checked'] and a['hits'] == 4 and a['false'] == 0, (backend, a['hits'], a['false'])
    rows.append({'run_id': run, 'backend': backend, 'frames_checked': v['processed_frames_checked'],
                 'hits': a['hits'], 'false': a['false'], 'peaks': a['peaks'], 'all_bins': True,
                 'complete_to_output_p99_ms': v['realtime_criterion']['complete_to_output_p99_ms']})
    print('S3A3_HOST_PASS', json.dumps(rows[-1]), flush=True)
(out/'host_s3a3_summary.json').write_text(json.dumps(rows, indent=1)+'\n', encoding='utf-8')
