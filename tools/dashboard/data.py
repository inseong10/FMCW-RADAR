"""Read-only adapters for the radar visualizer; never measure or drive a board."""
import csv
import hashlib
import importlib.util
import io
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'benchmarks/reports/2026-11-21-e14-frame-board'
RAW = ROOT / 'build/fft128_dma_frame_measurements'
N = 128
C = 299_792_458.0
DEFAULT_RADAR = dict(sample_rate_hz=1_600_000.0, bandwidth_mhz=100.0,
                     chirp_us=80.0, prp_us=100.0, fc_ghz=24.05)


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODEL = module_at('dashboard_q15', ROOT / 'src/PS/fft128/receiver.py')
REPLAY = module_at('dashboard_replay', ROOT / 'tools/sender/replay_udp.py')
SENDER = module_at('dashboard_sender', ROOT / 'tools/sender/sender.py')


def radar_settings(values):
    result = {}
    for key, default in DEFAULT_RADAR.items():
        value = float(values.get(key, default))
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f'{key}: 양의 유한한 값이 필요합니다.')
        result[key] = value
    if result['chirp_us'] > result['prp_us']:
        raise ValueError('Chirp 길이는 PRP보다 클 수 없습니다.')
    return result


def axes(radar):
    slope = radar['bandwidth_mhz'] * 1e6 / (radar['chirp_us'] * 1e-6)
    ranges = np.arange(N) * radar['sample_rate_hz'] / N * C / (2 * slope)
    velocities = np.fft.fftshift(np.fft.fftfreq(N, radar['prp_us'] * 1e-6)) * C / (2 * radar['fc_ghz'] * 1e9)
    return ranges, velocities


def q15_transform(frame):
    """Reuse the repository's exact rounding, saturation and stage scaling."""
    words, scale = MODEL.quantize(frame.tolist())
    rows = [MODEL.fft_q15(row) for row in words]
    cols = [MODEL.fft_q15([rows[ch][r] for ch in range(N)]) for r in range(N)]
    pl = np.array([[complex(*MODEL.unpack_iq(cols[r][d])) for r in range(N)] for d in range(N)])
    q = np.array([[complex(*MODEL.unpack_iq(word)) for word in row] for row in words])
    return np.fft.fft2(q) / (N * N), pl, q, scale


def read_csv(text, input_frame=False):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    fields = set(reader.fieldnames or [])
    row_key, col_key = ('chirp', 'sample') if input_frame else ('doppler_bin_unshifted', 'range_bin')
    if {row_key, col_key, 'real', 'imag'} <= fields:
        real_key, imag_key = 'real', 'imag'
    elif not input_frame and {row_key, col_key, 'real_q15', 'imag_q15'} <= fields:
        real_key, imag_key = 'real_q15', 'imag_q15'
    else:
        raise ValueError('CSV 열이 맞지 않습니다. README의 128×128 CSV 형식을 확인하세요.')
    result = np.zeros((N, N), dtype=complex)
    seen = set()
    for row in reader:
        r, c = int(row[row_key]), int(row[col_key])
        if not 0 <= r < N or not 0 <= c < N or (r, c) in seen:
            raise ValueError('CSV 인덱스 범위 오류 또는 중복 bin입니다.')
        value = complex(float(row[real_key]), float(row[imag_key]))
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise ValueError('CSV에 NaN 또는 Infinity가 있습니다.')
        seen.add((r, c))
        result[r, c] = value
    if len(seen) != N * N:
        raise ValueError(f'CSV는 16,384개 bin이 필요합니다. 현재 {len(seen):,}개입니다.')
    return result


def packed(array):
    return np.stack((array.real, array.imag), axis=-1).reshape(-1, 2).tolist()


def dataset(name, kind, spectra, labels, radar, truth=None, frame=None, **extra):
    ranges, velocities = axes(radar)
    reference = spectra['double']
    norm = float(np.linalg.norm(reference))
    peaks, errors = {}, {}
    for key, values in spectra.items():
        d, r = map(int, np.unravel_index(np.argmax(abs(values)), values.shape))
        shifted_d = (d + N // 2) % N
        delta = abs(values - reference)
        peaks[key] = dict(doppler_bin=d, range_bin=r, shifted_doppler_bin=shifted_d,
                          range_m=float(ranges[r]), velocity_mps=float(velocities[shifted_d]),
                          magnitude=float(abs(values[d, r])))
        errors[key] = dict(relative_l2=float(np.linalg.norm(delta) / norm) if norm else None,
                           max_complex_q15_lsb=float(delta.max()),
                           rms_q15_lsb=float(np.sqrt(np.mean(delta ** 2))))
    normalization = extra.pop('normalization', '1/16384 · 창 없음 · Q15 입력 단위')
    return dict(name=name, kind=kind, shape=[N, N], radar=radar, truth=truth, labels=labels,
                normalization=normalization,
                axes=dict(range_m=ranges.tolist(), velocity_mps=velocities.tolist()),
                spectra={k: packed(v) for k, v in spectra.items()}, peaks=peaks, errors=errors,
                input_iq=packed(frame) if frame is not None else None, **extra)


def board_baseline():
    return dict(comparison=json.loads((REPORT / 'comparison.json').read_text()),
                profile=json.loads((REPORT / 'profile.summary.json').read_text()),
                progression=json.loads((REPORT / 'progression.json').read_text()),
                source='benchmarks/reports/2026-11-21-e14-frame-board',
                scope='128×128 · Q15 · 창 없음 · CPU0 · warmup 10 · 각 300회 · 오프라인 반복',
                excluded='UDP·파일 I/O·양자화·할당·검증·계획 생성 제외')


@lru_cache(maxsize=1)
def recording():
    fixture = ROOT / 'benchmarks/fixtures/radarsimpy_128x128.rspb'
    meta = json.loads((fixture.parent / 'input_metadata.json').read_text())
    if hashlib.sha256(fixture.read_bytes()).hexdigest() != meta['record_sha256']:
        raise ValueError('기준 입력 프레임 SHA-256이 기록과 다릅니다.')
    packets, fs = REPLAY.read_frame(fixture)
    frame = np.empty((N, N), dtype=complex)
    for packet in packets:
        _, index, _, row = MODEL.decode_packet(packet)
        frame[index] = row
    double, pl, q, scale = q15_transform(frame)
    spectra = dict(double=double, pl=pl)
    labels = dict(double='NumPy double 참조 · PC 재계산', pl='PL Q15 소프트웨어 모델 · PC 재계산')
    sources = ['benchmarks/fixtures/radarsimpy_128x128.rspb']
    manifest = json.loads((REPORT / 'raw_artifact_sha256.json').read_text())
    for key in ('double', 'float_neon', 'pl'):
        relative = f'results_e14_frame_01/{key}/trial_1.csv'
        path = RAW / relative
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != manifest[relative]['sha256']:
                raise ValueError(f'보드 원시 결과 SHA-256 불일치: {relative}')
            spectra[key] = read_csv(path.read_text())
            labels[key] = dict(double='PS double · 보드 저장 결과', float_neon='PS NEON · 보드 저장 결과',
                               pl='PL E14 · 보드 저장 결과')[key]
            sources.append('build/fft128_dma_frame_measurements/' + relative)
    radar = dict(DEFAULT_RADAR, sample_rate_hz=fs)
    return dataset('RadarSimPy · 30 m / −10 m/s', 'recording', spectra, labels, radar,
                   truth=dict(range_m=meta['target_range_m'], velocity_mps=meta['target_speed_mps']),
                   frame=q, scale=scale, sources=sources, fixture_sha256=meta['record_sha256'])


def simulate(values):
    radar = radar_settings(values)
    distance, velocity, snr = (float(values.get(k, v)) for k, v in
                               [('range_m', 30), ('velocity_mps', -10), ('snr_db', 35)])
    if not all(map(math.isfinite, (distance, velocity, snr))) or not 0 <= distance <= 180 or not -30 <= velocity <= 30 or not 0 <= snr <= 80:
        raise ValueError('거리 0–180 m, 속도 −30–30 m/s, SNR 0–80 dB를 사용하세요.')
    engine = values.get('engine', 'tone')
    if engine not in ('tone', 'radarsimpy'):
        raise ValueError('지원하지 않는 시뮬레이션 엔진입니다.')
    ranges, velocities = axes(radar)
    slope = radar['bandwidth_mhz'] * 1e6 / (radar['chirp_us'] * 1e-6)
    fd = 2 * velocity * radar['fc_ghz'] * 1e9 / C
    beat = 2 * slope * distance / C + fd
    if not 0 <= beat < radar['sample_rate_hz'] or not velocities[0] <= velocity < -velocities[0]:
        raise ValueError('표적이 현재 설정의 비모호 거리·속도 범위를 벗어납니다.')
    if engine == 'radarsimpy':
        if radar != DEFAULT_RADAR:
            raise ValueError('RadarSimPy 모드는 기존 sender의 고정 레이더 설정을 사용합니다.')
        baseband, fs = SENDER.simulate(N, distance, velocity, samples=N)
        # Match the existing sender's float32 I/Q transport precision.
        frame = np.asarray(baseband[0], dtype=np.complex64).astype(np.complex128)
        if frame.shape != (N, N) or not np.isfinite(frame).all():
            raise ValueError('RadarSimPy가 유효한 128×128 프레임을 반환하지 않았습니다.')
        radar['sample_rate_hz'] = fs
    else:
        fast = np.arange(N) / radar['sample_rate_hz']
        slow = np.arange(N) * radar['prp_us'] * 1e-6
        phase = 2 * np.pi * (fd * slow[:, None] + beat * fast[None, :])
        rng = np.random.default_rng(42)
        noise = (rng.normal(size=(N, N)) + 1j * rng.normal(size=(N, N))) / np.sqrt(2)
        frame = np.exp(1j * phase) + 10 ** (-snr / 20) * noise
    double, pl, q, scale = q15_transform(frame)
    title = 'RadarSimPy 새 프레임' if engine == 'radarsimpy' else '합성 표적'
    return dataset(f'{title} · {distance:g} m / {velocity:g} m/s', 'simulation',
                   dict(double=double, pl=pl),
                   dict(double='NumPy double · 소프트웨어', pl='PL Q15 모델 · 소프트웨어'), radar,
                   truth=dict(range_m=distance, velocity_mps=velocity), frame=q, scale=scale, engine=engine,
                   sources=['tools/sender/sender.py · 실제 RadarSimPy 실행 · PL은 소프트웨어 모델 · 보드 실행 없음'] if engine == 'radarsimpy'
                   else ['결정적 복소 beat-tone + AWGN · RadarSimPy/RF/보드 실행 아님'])


def import_spectra(values):
    radar = radar_settings(values.get('radar', {}))
    spectra = dict(double=read_csv(values['ps_csv']), pl=read_csv(values['pl_csv']))
    frame = read_csv(values['input_csv'], input_frame=True) if values.get('input_csv') else None
    return dataset('가져온 PS / PL 결과', 'import', spectra,
                   dict(double='PS CSV · 사용자 제공', pl='PL CSV · 사용자 제공'), radar,
                   frame=frame, sources=['사용자 CSV · 동일 입력·정규화 여부는 사용자 확인'],
                   normalization='사용자 확인: 양쪽 모두 Q15 입력 단위 · 1/16384 · 창 없음')
