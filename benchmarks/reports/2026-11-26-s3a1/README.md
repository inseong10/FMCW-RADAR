# S3a-1 — 프레임 크기 일반화 (M×N), 128×128 무변경 확인

- **날짜:** 2026-11-26
- **범위:** 수신기·파이프라인·송신기·레코드 형식·기준 모델·검산기를 M∈{128,256,512} chirp × N∈{128,256} 샘플로 일반화했다.
  - 측정은 **128×128만 보드**에서 했다.
  - 256/512 크기는 **host 루프백(model·ps)만** 검증했다.
  - 보드 PL 분할 경로(E14 블록 + 결합)와 큰 크기의 보드 처리량은 **미측정**이다. 성능 주장은 하지 않는다.
- **표기:** 이 보고서는 **M(chirp)×N(샘플)**이다. [S3a 설계](../../../docs/s3a_size_scaling_design.md) §3·§6은 N×M으로 쓴다(설계 "D축 128×256" = 여기 256×128).
- **조건:** PL 100MHz(E14-clock, `load_board.sh` 재로드). 큐는 4로 그대로다. 약한 표적 주장은 없다.

## 변경 (원본 백업 `build/s3a1_pre_20261126/`)

| 파일 | 이전 → 이후 | 내용 |
|---|---|---|
| `src/PS/receiver/stream_protocol.hpp` | `e989ce3a…` → `971a370e…` | 패킷 헤더 pulses/samples 검증, 최대 256샘플 행·512 chirp, `adc_packet_size` |
| `src/PS/receiver/stream_pipeline.hpp` | `e2c4779a…` → `b07a6883…` | M×N 버퍼, FFTW M×N(/(M·N)), 방법 A(DIT 분할: 블록별 128×128 정수 FFT → 비트 역순 배치 → Doppler·range 나머지 단, 같은 Q15 버터플라이) |
| `src/PS/receiver/stream_adc16.hpp` | `ed6406a3…` → `597b26d6…` | `valid_shape`, `adc_hann_q15_table(L)` (128은 고정 표) |
| `src/PS/receiver/stream_receiver.cpp` | `ba167cd6…` → `e09c1348…` | `--pulses`/`--samples`(128 아닌 크기는 adc16 전용), environment.txt에 pulses/samples |
| `tools/sender/replay_stream.py` | `51ba255c…` → `291751e8…` | 헤더에 크기, chirp 간격 검사 (pulses−1) |
| `tools/sender/adc16_record.py` | `9ba984ec…` → `38cf32f9…` | RSPB0002 M×N 읽기·쓰기 (128×128 결과 사전 동일) |
| `tools/detection/adc16_reference.py` | `f70b31f7…` → `6095e437…` | 독립 NumPy 방법 A(`split_integer_spectrum`), 128은 기존 oracle |
| `tools/detection/analyze_stream.py` | `c9b500cd…` → `33c8b81c…` | 크기를 environment에서 읽음 (기본 128) |
| `tools/detection/check_adc16_stream.py` | `17747a1f…` → `28fbbf0a…` | 크기별 전bin·손실 패킷 회계, 레코드/수신기 크기 일치 검사 |
| `tools/detection/smoke_s2a.py` | `45c0d377…` → `d5224ed1…` | `case()` 선택 인자(기본값은 기존 동작 그대로) |
| `tools/detection/smoke_s3a1.py` | 신규 `101f3e06…` | 방법 A ≡ 128 oracle, 4개 크기 × model/ps 루프백 |

변경 없음: `cfar_ca.hpp` `ee12fba9…`(이미 크기 일반), `run_adc16_board.sh`, `verify_s1c.py`, `smoke_adc16.py`.

## 1. Host 검증 (`host/`, Ubuntu gcc 9.4.0, `build/s3a1_host_02` stream-receiver `3d0e4b47…`)

- 기존 테스트가 모두 통과했다.
  - `test_check_pacing` 15
  - `test_adc16` 13 (skip 1)
  - `test_s2a` 11 (skip 3)
  - `test_s1c` 3
  - `test_cfar` 4
  - `test_receiver` 12 (skip 4)
  - `test_reference_smoke` 1
  - smoke: `smoke_adc16` 3건, `smoke_s2a` 3건
- `test_s2a.py`는 공유 폴더본이 repo보다 예전 판이었다.
  - 공유본은 `build/s3a1_pre_20261126/test_s2a.share_old.py`로 보존했다.
  - repo판과, 공유 폴더에 없던 `timestamp_driver.cpp`를 복사했다.
- **smoke_s3a1:**
  - 방법 A 정수 스펙트럼이 128×128 oracle과 **10건 모두 같았다**(ADC 고정 입력 4종 + 경계값 × hann/none, `oracle_128_equivalence.json`).
  - 256×128, 128×256, 256×256, 512×128 × model/ps 8건이 모두 4/4 검출, 오검출 0이었다(`smoke_s3a1_summary.json`).
    - 루프백 run 92391–92398, 5프레임, 주기 M·0.1+10ms, chirp 간격 100µs.
    - 첫 프레임은 전bin을 비교했다. model은 정확히 같았고, ps는 허용오차 1e-9 안이었다.
    - 따라서 C++ Hann 표·twiddle은 큰 크기에서도 Python 기준과 같다.
  - 입력은 시드 고정 합성 4톤 + 잡음이다(radarsimpy 시나리오가 아니다). 레코드 SHA는 `synthetic_*.json`에 있고, 레코드 자체는 시드로 재생성할 수 있다.
- **첫 빌드 실패(기록):** `-Werror=misleading-indentation`(한 줄 람다). 줄을 나눠 해결했고 `s3a1_host_01`에 남아 있다.

## 2. 128×128 비트 동일·속도 (`bench/`, S3a-0 `bench_s3a0`을 새 헤더로 다시 빌드)

빌드 방식은 S3a-0과 같다(`build_iter.sh`, bench 사본만 `class Pipeline { public:`). 보드는 CPU1, 500회 중앙값, 기존 바이너리와 번갈아 2회씩 실행했다.

| 판 | 덤프 (model / ps) | 보드 model prepare | model detect | ps prepare | ps detect |
|---|---|---|---|---|---|
| S3a-0 new5 (기준) | `c9123fbb…` / `7157b512…` | 1.034ms | 2.148 | 0.561 | 3.744 |
| **s3a1a** | 동일 / 동일 | 1.113 (+8%) | 2.162 | 0.564 | **4.649 (+24%)** |
| **s3a1b** (최종) | 동일 / 동일 | 1.031 | 2.171 (+1%) | 0.560 | 3.802 (+1.5%) |

- **s3a1a 회귀 원인:**
  - ps 정규화가 상수 `/16384`에서 런타임 `/norm`으로 바뀌었다. 그래서 ARM에서 셀마다 실제 나눗셈 2회가 일어났다.
  - model prepare는 `std::array` 고정 루프가 `vector`·`packed.size()` 루프로 바뀐 영향이었다.
- **s3a1b 수정:**
  - `*(1/cells)`로 바꿨다. cells가 2의 거듭제곱이라 나눗셈과 정확히 같다.
  - prepare 루프는 지역 포인터·개수로 바꿨다.
  - 덤프는 host·보드 모두 그대로였다.
- **보드 재부팅(기록):** s3a1a 보드 bench 직후 보드가 재부팅됐다(uptime 0분, 원인 미확인). bench 결과는 완결돼 있었다. 사용자가 PL을 재로드했다.

## 3. 10k 회귀 (`regression/`, 번들 `s2a_int16_20261126_s3a1_01`)

- **번들:** stream-receiver `f5aafa2e…`, libfftw3 `182f6f53…`, run_board.sh `b8eb507f…`, `source.sha256` `8e07838c…`.
- **실행 조건:** 에이전트·래퍼 v3 `run_pinned3.sh` `eb928df4…`, nfs, reanchor, 12.8ms, chirp 100µs, 고정 1/1/2.
- **검산:** `check_adc16_stream.py --network-loss-ok`.

| run | 백엔드 | 송신 | 처리 | 판정 |
|---|---|---|---|---|
| 92401 | PL | **무효** (지터 P99 117µs, overrun 9601, 최대 67ms) | 10000/10000, 카운터 전부 0 | 무효 (송신) |
| 92403 | PL | **무효** (P99 123µs, overrun 9648) | 9993, kernel_drops 145 | 무효 (송신) |
| **92404** | PL | 유효 (P99 5.53µs, 정지 7, `b4ca6b64…`) | 9996, kernel_drops 169 = 손실 패킷 169, queue_full 0, 4/4·오검출 0 | **충족 P99 5.449ms** |
| 92405 | PS | **무효** (P99 22.6µs, 정지 18) | 9998, kernel_drops 57 | 무효 (송신) |
| **92406** | PS | 유효 (P99 6.23µs, 정지 14, `c0237d8e…`) | 9998, kernel_drops 18 = 손실 패킷 18, queue_full 0, 4/4·오검출 0 | **충족 P99 11.635ms** |

- **92401·92403 송신 무효 원인:** Windows 노트북이 **배터리 전원**이었다(BatteryStatus=1). 그래서 CPU 성능이 약 50%로 제한됐다. AC 연결 뒤 92404부터 유효했다.
- **92405:** AC 연결 직후였고 원인은 미확인이다. 기준은 완화하지 않고 재실행했다.
- **92404 손실:** 프레임 2294(partial_evicted 4패킷), 2295, 2296, 2300.
- **92406 손실:** 2457, 9117.

단계 중앙값(ms, `stage_stats_*.json`)을 S3a-0과 비교하면 다음과 같다.

| | prepare | FFT | CFAR | flush | 처리 합계 | 조립완료→출력 P99 | 12.8 초과 |
|---|---|---|---|---|---|---|---|
| PL S3a-0 92357 | 1.197 | 1.449 | 2.380 | 0.224 | 5.265 | 5.527 | 6 |
| **PL S3a-1 92404** | 1.110 | 1.400 | 2.390 | 0.222 | 5.149 | **5.449** | 5 |
| PS S3a-0 92358 | 0.623 | 5.949 | 4.307 | 0.234 | 11.104 | 11.451 | 21 |
| **PS S3a-1 92406** | 0.635 | 5.969 | 4.457 | 0.229 | 11.290 | **11.635** | 38 |

PS-only는 CFAR 단계가 +0.15ms(+3.5%), P99가 +0.18ms다. bench 차이(+0.06ms)보다 크고, 한 번 실행이라 변동인지 회귀인지 구분하지 못했다. 여유는 1.17ms(주기의 9%)다.

## 해석

- 128×128의 수치 결과는 바뀌지 않았다(덤프 SHA, host·보드).
- 10k 처리 실시간은 PL·PS-only 모두 유지됐다.
- 큰 크기는 host 루프백에서 기능과 정확성만 확인했다.
  - 보드 실행에는 래퍼(`run_pinned3.sh`)가 `--pulses/--samples`를 넘겨야 한다. 이는 sudo가 필요한 루트 소유 파일 변경이다.
  - PL 분할 경로는 E14 하드웨어에서 아직 실행하지 않았다.
- N=512는 1 패킷 MTU를 넘으므로 지원하지 않는다(`valid_shape`).

## 파일

- `host/`: smoke 요약·oracle 동등성·합성 레코드 메타, host 바이너리 SHA·빌드 환경.
- `bench/`: s3a1a/s3a1b 소스(`src_*`), host·보드 결과 텍스트와 덤프 SHA, 빌드·보드 스크립트.
- `regression/`
  - 런 5개 raw: trace, adc16_verified.json, summary.json
  - 송신 JSON 5개, 검산 출력(`s3a1_check_*.json`), 단계 통계
  - pin 기록, 에이전트 로그, Ubuntu 스냅샷
  - 번들 SHA, prepare.log
- 회수 원본은 공유 폴더 `build/s3a1_evidence_20261126_01`에 있다.
