# S3a-0 — PS 셀당 비용 감축 (prepare·CFAR), 2026-11-26

질문: 128×128에서 PS 쪽 prepare·CFAR의 셀당 비용을 결과를 바꾸지 않고 얼마나 줄일 수 있나?
목표는 256×256 확장을 위한 prepare+CFAR ≤ 0.2µs/셀이다([설계안](../../../docs/s3a_size_scaling_design.md) §6).

## 변경 (처리 로직, 사용자 승인 "ㄱㄱ")

원본 헤더는 `build/s3a0_pre_20261126/`에 백업했다.
- 기존 SHA: pipeline `c2f6f213…`, cfar `39cb5939…`, adc16 `ffae26d9…`
- 최종 SHA: `stream_pipeline.hpp` `e2c4779a…`, `cfar_ca.hpp` `ee12fba9…`, `stream_adc16.hpp` `ed6406a3…`

| 대상 | 기존 | 변경 |
|---|---|---|
| `Pipeline::detect` 전력 계산 | 셀마다 `backend=="ps"` 문자열을 비교하고 비인라인 `fft128_real/imag`를 호출했다 | ps는 같은 식을 인라인했다. pl/model은 Q15 워드를 인라인으로 풀어 uint32 전력(≤2^31, 정확)을 만든다. double 전력 배열은 `power()`를 호출할 때만 채운다 |
| CA-CFAR (pl/model) | double 2D prefix, 셀마다 isfinite 검사, 범위 경계 clamp | `detect_integer`: uint64 Doppler 열 합을 d 방향으로 이어 가며 갱신하고, 범위 방향은 행마다 1D prefix로 합한다. 내부 셀은 고정 오프셋을 쓰고, 비교는 정수로 한다. threshold = exact_double(total)·scale |
| CA-CFAR (ps) | 그대로 | 그대로 (`detect`, double) |
| `adc_window` | int64 곱과 분기가 있는 반올림이다. ARM에서 부호 분기와 스택 spill이 생겼다 | 부호 마스크와 32비트 조각만 쓰는 무분기 round-half-even이다 (같은 수식) |

**비트 동일 근거:**
- pl/model 전력은 정수 ≤2^31이다. 기존 double prefix 값은 (nd+2hd)·nr·2^31 미만, 즉 2^53 미만이어서 모두 정확하다.
- 그래서 기존 창 합은 정확한 정수이고, 정수 합과 같다. 합산 순서와 상관없이 total·scale이 같은 비트가 된다.
- 2^53 범위를 넘는 크기에서는 `detect_integer`가 예외를 던진다.

## 정확성 (모두 통과)

| 검사 | 범위 | 결과 |
|---|---|---|
| `adc_window_exhaustive` | 실제 Hann 가중치 2,017개 × int16 65,536값. 동점 0건이라 합성 가중치 20,221개도 검사했다(동점 73,727건) | host·보드 ARM 모두 기존 구현과 일치 |
| `cfar_integer_equiv` | 9개 크기 × 5개 입력 = 45건. 크기는 128², 256×128, 128×256, 256², 512², 래핑 반복이 생기는 16×8·5×40·3×3, 비대칭 파라미터다. 입력은 전범위, 전부 2^31, 0, 작은 값, 희소 피크다 | thresholds·peaks memcmp 일치 (host·ARM) |
| `bench_s3a0` 덤프 | 고정 입력 4종 + 무작위·포화·0·톤 4종에 대해 스펙트럼·전력·threshold 전체와 peaks를 비교했다 | 기존 대비 SHA 동일. model `c9123fbb…`, ps `7157b512…` (host·보드, 반복 2회씩) |
| 기존 테스트 | `test_cfar.py` 4건, prepare_adc16 host smoke (S2A 3건·ADC16 3건) | 통과 |
| 보드 10k 독립 검산 | 92354(10,000)·92355(9,994) | `ADC16_INDEPENDENT_CHECK_PASS`, 4/4 |

## 보드 마이크로벤치 (CPU1 고정, 500회 중앙값, multi4 입력, -O2 / NEON 없음)

| 단계 | 기존 | 최종(new5) | 셀당 기존 → 최종 |
|---|---|---|---|
| model prepare_adc16 | 2.168ms | 1.034ms | 0.132 → **0.063µs** |
| model detect (전력+CFAR) | 5.957ms | 2.148ms | 0.364 → **0.131µs** |
| **prepare+CFAR 합** | 8.13ms | 3.18ms | **0.496 → 0.194µs (≤0.2 목표 충족, 2.56×)** |
| ps detect | 5.010ms | 3.744ms | 0.306 → 0.229µs |
| ps prepare | 0.561ms | 0.561ms | 변화 없음 |

- 과정: new(초안) → new2(분리형 CFAR) → new3(루프 분리, ps 인라인) → new4(무분기 창) → new5(내부 고정 오프셋, 정수 비교). 실패하거나 중간인 단계도 `bench/board_results/res_board_0{1..5}`에 보존했다.
  - new2 ps detect는 5.52ms로 느려졌다(재현됨). new3에서 인라인해 해소했다.
- 후보 비교(`micro.txt`):
  - 기존 2D prefix를 정수화하면 2.64ms였고, 분리형 u64는 1.37ms(threshold만)였다.
  - 분리형 double은 1.74ms, double magic 반올림 창은 1.16ms(정수 1.30ms)였다.
  - 그래서 분리형 u64와 정수 창을 골랐다. 정수 창은 반올림 모드에 의존하지 않는다.
- 벤치 바이너리와 소스 SHA는 `bench/build/*/`·`bench/board_results/board_binaries.sha256`에 있다.
  - 덤프는 크기 때문에 SHA만 남겼다(`dumps.sha256`).
  - `bench_s3a0.cpp`는 `cfar` 내부에 접근하려고 벤치 사본에서만 `class Pipeline { public:`로 바꿨다. 기존·신규 사본에 같은 변환을 적용했다.

## 10,000프레임 회귀 (PL, nfs, reanchor, 에이전트·래퍼 v3, 번들 `s2a_int16_20261126_s3a0_01`)

번들:
- stream-receiver `ef01f150…`, source.sha256 `7ab92b1e…`
- run_board.sh `b8eb507f…`, FFTW `182f6f53…`
- 래퍼 `run_pinned3.sh` `eb928df4…`. 번들을 인자로 받고, 루트 소유·쓰기 권한·artifacts SHA를 검사한다.

| run | 송신 | 처리 | 카운터 | 조립완료→출력 중앙/P99/최대 | 판정 |
|---|---|---|---|---|---|
| 92348 (기준, 기존 번들) | 유효 | 9996 | kernel_drops108 | 10.934 / 11.099 / – ms | 충족 |
| 92353 | **무효** (지터 P99 28.2µs, 최대 26.6ms) | 9997 | kernel_drops99, **clock_errors1** | 5.364 / 5.513 / 22.3ms | 무효 (검산기 거부) |
| 92354 | **무효** (지터 P99 34.2µs, 최대 6.6ms) | **10000** | **모두 0** | 5.354 / **5.504** / 26.0ms | 미충족 (송신 무효만 원인), 검산 PASS |
| 92355 | **무효** (지터 P99 29.9µs, 최대 16.7ms) | 9994 | kernel_drops158 | 5.360 / 5.511 / 24.0ms | 미충족 (송신 무효), 검산 PASS |

단계 중앙값 (92354 대 92348):

| 단계 | 92354 | 92348 |
|---|---|---|
| prepare | 1.196ms | 2.537ms |
| FFT | 1.459ms | 1.553ms |
| CFAR | 2.380ms | 6.542ms |
| flush | 0.226ms | 0.218ms |
| 처리 합계 | 5.277ms | 10.854ms |

처리 합계는 주기의 41%다(기존 85%). 12.8ms를 넘은 프레임은 92354에서 4개, 92348에서 22개다.

- 오전 실행들(92348·92352)은 송신 지터 P99가 4.7~5.1µs였다. 이번 세 번은 28~34µs로 모두 송신 무효다.
  - Ubuntu는 유휴 상태였다(load 0.9).
  - Windows 호스트에서는 vmware-vmx 외에 ChatGPT 등 다른 앱이 실행 중이었다. 호스트 경합 때문으로 보이지만 확인하지 못했다.
  - 송신기·수신기 코드는 오전과 같다. 지터는 수신기 변경과 무관하다.
- **92356 (PL 10k 재실행, 호스트 앱 정리 후):** 송신 유효(지터 P99 7.42µs, 정지 37, 최대 189.5ms, 송신 JSON `f8466281…`).
  - 실행 중 **보드가 비정상 재부팅**했다. 재부팅 후 uptime 0분이었고, dmesg에 FAT 비정상 언마운트·ext4 recovery가 있었다. 마지막 출력은 프레임 8839이고, frames.csv·counters·exit는 기록되지 않았다.
  - 재부팅 후 `/dev/fft128-dma-frame`이 없다(PL 장치 재설정 필요).
  - 원인(전원·패닉·워치독)은 이전 부팅 로그가 휘발성이라 미확인이다. 부분 raw는 `regression/pl_s3a0_main_04_partial_raw`에 있다. 판정에서 제외한다.
### 재실행 (호스트 앱 정리, PL 재로드 후)

| run | 송신 | 처리 | 카운터 | 조립완료→출력 중앙/P99/최대 | 판정 |
|---|---|---|---|---|---|
| **92357 PL** | 유효 (P99 5.89µs) | 9995 | kernel_drops 251 = 손실 패킷 251, 그 외 0 | 5.341 / **5.527** / 24.9ms | **처리 실시간 충족**, 검산 PASS 4/4 |
| **92358 PS-only** | 유효 (P99 7.14µs) | 9991 | kernel_drops 441 = 손실 패킷 441, 그 외 0 | 11.182 / **11.451** / 32.3ms | **처리 실시간 충족**, 검산 PASS 4/4 |
| 92352 PS (기준, 기존 번들) | 유효 | 9994 | kernel_drops 232, clock_errors 3 | 12.444 / 23.837 ms | 불합격 |

92358 단계 중앙은 prepare 0.623 · FFT 5.949 · CFAR 4.307 · flush 0.234ms다(92352 CFAR 5.578).

검산기 `check_adc16_stream.py` `17747a1f…`: 패킷 0개인 `missing` 프레임도 네트워크 손실로 인정한다. 단, 비처리 프레임의 손실 패킷 수가 kernel_drops와 정확히 같을 때만이다. 92357에 missing 1프레임이 있었다.

**결론:** S3a-0 합격 조건(결과 동일, 128×128 10k 처리 실시간 유지, 셀당 비용 측정)을 충족한다. PS-only 128×128도 처음으로 충족했다.

## 파일

- `bench/`: 마이크로벤치 원본 출력, 빌드 스크립트, 소스·바이너리 SHA
- `regression/`: 92353–92355·92357·92358 raw, 92356 부분 raw(`*_raw`, 92354·92355는 `adc16_verified.json` 포함), 송신 JSON, 에이전트 로그·스냅샷, 번들 신원
- `s3a0_stage_stats.py`: 단계 통계 스크립트(참고용). `regression/stage_stats_*.json`을 만든다.
