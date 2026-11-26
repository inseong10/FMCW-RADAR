"""S2b-diag-out comparison: per-run drops, sender stalls, board-side spikes, counter deltas.

Run from the repo root: python benchmarks/reports/2026-11-26-s2b-pace/diag_out_compare.py
Reads recovered raws only; writes diag_out/diag_out_compare.json.
"""
import csv
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = [  # run_id, store, raw trace dir, sender JSON, snapshot dir
    (92348, 'nfs', 'build/s2a_int16_board_pace10_20261126_adc01/pl_pace_main_06', 'build/s2b_pace_sender_pl_main_06.json', None),
    (92349, 'ram', 'build/s2a_int16_board_diagout_20261126_adc01/pl_diag_out_ram_01', 'build/s2b_pace_sender_diag_out_ram_01.json', 'build/s2a_int16_board_diagout_20261126_adc01/agent_logs'),
    (92350, 'nfs', 'build/s2a_int16_board_diagout_20261126_adc01/pl_diag_out_nfs_01', 'build/s2b_pace_sender_diag_out_nfs_01.json', 'build/s2a_int16_board_diagout_20261126_adc01/agent_logs'),
    (92351, 'ram', 'build/s2a_int16_board_diagout_20261126_adc01/pl_diag_out_ram_02', 'build/s2b_pace_sender_diag_out_ram_02.json', 'build/s2a_int16_board_diagout_20261126_adc01/agent_logs'),
]


def snap(path):
    d = {}
    lines = Path(path).read_text().splitlines()
    udp = [l.split() for l in lines if l.startswith('Udp:')]
    if len(udp) >= 2:
        d.update({k: int(v) for k, v in zip(udp[0][1:], udp[1][1:])})
    for l in lines:
        if l.strip().startswith('eth0:'):
            f = l.split(':', 1)[1].split()
            d.update(eth0_rx_packets=int(f[1]), eth0_rx_drop=int(f[3]), eth0_rx_fifo=int(f[4]), eth0_tx_packets=int(f[9]))
        if l.startswith('rpc '):
            d['nfs_rpc_calls'] = int(l.split()[1])
        if l.startswith('cpu0 ') or l.startswith('cpu1 '):
            f = list(map(int, l.split()[1:]))
            d[l.split()[0]+'_softirq'] = f[6]
            d[l.split()[0]+'_busy'] = sum(f)-f[3]-f[4]
            d[l.split()[0]+'_total'] = sum(f)
    return d


def main():
    root = HERE.parents[2]
    out = []
    for rid, store, raw, sender, snaps in RUNS:
        raw, sender = root/raw, root/sender
        cnt = dict(l.split('=', 1) for l in (raw/'trace/counters.txt').read_text().split() if '=' in l)
        s = json.loads(sender.read_text())
        c = s['chirp_pacing']; sd = {x['frame_id']: x for x in s['schedule']}
        rows = {int(r['frame_id']): r for r in csv.DictReader(open(raw/'trace/frames.csv'))}
        g = lambda r, k: int(r[k])
        pr = [r for r in rows.values() if r['status'] == 'processed']
        c2o = np.array([(g(r, 'output_done_ns')-g(r, 'complete_ns'))/1e6 for r in pr])
        cfar = np.array([(g(r, 'cfar_done_ns')-g(r, 'fft_done_ns'))/1e6 for r in pr])
        flush = np.array([(g(r, 'output_done_ns')-g(r, 'cfar_done_ns'))/1e6 for r in pr])
        asm = {int(r['frame_id']): (g(r, 'complete_ns')-g(r, 'first_kernel_ns'))/1e6 for r in pr}
        stall_frames = sorted(f for f, x in sd.items() if x['stall_max_ns'] >= 1_280_000)
        bad = []
        for f, r in sorted(rows.items()):
            if r['status'] == 'processed':
                continue
            near = [x for x in stall_frames if f-10 <= x <= f]
            prev = rows.get(f-2)
            bad.append({'frame': f, 'status': r['status'], 'packets': int(r['packets']),
                        'sender_stall_within_10_frames_before': [(x, round(sd[x]['stall_max_ns']/1e6, 2)) for x in near],
                        'assembly_ms_prev2_prev1': [round(asm[k], 2) if k in asm else None for k in (f-2, f-1)],
                        'cfar_flush_ms_prev2': (None if not prev or prev['status'] != 'processed' else
                                                [round((g(prev, 'cfar_done_ns')-g(prev, 'fft_done_ns'))/1e6, 2),
                                                 round((g(prev, 'output_done_ns')-g(prev, 'cfar_done_ns'))/1e6, 2)])})
        short_asm = sum(v < 12.0 for v in asm.values())
        r = {'run_id': rid, 'store': store, 'exit': (raw/'receiver_exit.txt').read_text().strip(),
             'kernel_drops': int(cnt['kernel_drops']), 'clock_errors': int(cnt['clock_errors']),
             'received_packets': int(cnt['received_packets']),
             'status_counts': {k: sum(1 for x in rows.values() if x['status'] == k) for k in {x['status'] for x in rows.values()}},
             'sender': {k: c[k] for k in ('late_p99_ms', 'stall_frames', 'stall_max_ms', 'min_chirp_spacing_us',
                                          'min_frame_spacing_ms', 'effective_period_ms', 'valid')},
             'sender_stall_frames': [(x, round(sd[x]['stall_max_ns']/1e6, 2)) for x in stall_frames],
             'c2o_ms': {'median': float(np.median(c2o)), 'p99': float(np.percentile(c2o, 99)), 'max': float(c2o.max()),
                        'over_12p8': int((c2o > 12.8).sum())},
             'cfar_over_8ms': int((cfar > 8).sum()), 'flush_over_4ms': int((flush > 4).sum()),
             'flush_max_ms': float(flush.max()), 'assembly_under_12ms_frames': int(short_asm),
             'bad_frames': bad}
        if snaps:
            b = snap(root/snaps/f'snap_{rid}_before.txt'); a = snap(root/snaps/f'snap_{rid}_after.txt')
            r['board_counter_delta'] = {k: a[k]-b[k] for k in a if k in b}
            ub = (root/snaps/f's2b_diag_out_ubuntu_snap_{rid}_before.txt').read_text().splitlines()
            ua = (root/snaps/f's2b_diag_out_ubuntu_snap_{rid}_after.txt').read_text().splitlines()
            io = lambda L: [int(x) for x in next(l for l in L if l.startswith('io ')).split()[1:]]
            r['ubuntu_nfsd_io_delta_bytes'] = [y-x for x, y in zip(io(ub), io(ua))]
        out.append(r)
    (HERE/'diag_out'/'diag_out_compare.json').write_text(json.dumps(out, indent=1)+'\n', encoding='utf-8')
    for r in out:
        d = r.get('board_counter_delta', {})
        print(r['run_id'], r['store'], 'drops', r['kernel_drops'], 'RcvbufErr+', d.get('RcvbufErrors'), 'clockerr', r['clock_errors'],
              'stalls', len(r['sender_stall_frames']), 'stallmax', r['sender']['stall_max_ms'],
              'c2o p99', round(r['c2o_ms']['p99'], 3), '>12.8', r['c2o_ms']['over_12p8'],
              'cfar>8', r['cfar_over_8ms'], 'flush>4', r['flush_over_4ms'], 'asm<12', r['assembly_under_12ms_frames'],
              'nfs_rpc+', d.get('nfs_rpc_calls'), 'nfsd_io+', r.get('ubuntu_nfsd_io_delta_bytes'),
              'softirq0+', d.get('cpu0_softirq'))
        for b in r['bad_frames']:
            print('   ', b)


if __name__ == '__main__':
    main()
