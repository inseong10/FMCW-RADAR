# S3a-4 — 정사각 256×256 (주기 25.6ms) 처리 실시간, clock_errors 원인과 보정

- **날짜:** 2026-11-27
- **표기:** M(chirp)×N(샘플). 주기는 M×100µs = 25.6ms다.
- **질문:** 256×256에서 PS+PL이 처리 실시간을 만족하나(PS-only는 참고).
- **조건 (모든 런):**
  - PL 100MHz, 큐 4, partial 4, nfs, reanchor, chirp 100µs, 고정 1/1/2
  - 래퍼 v3, 에이전트 송신 v4
  - 10k마다 AC 전원 확인(BatteryStatus 2)
- **입력:** `benchmarks/fixtures/s3a/radarsimpy_256x256_sim_multi4_noise_adc16.rspb` `783fac6e…`(float 원본 `800bbb5f…`, 메타는 `fixture/`)
  - `make_s3a_fixture.py --check-128 --shape 256 256`. 128 재현(`d3d5160c…`)을 다시 확인했다.
  - 기준 model·ps 4/4, 오검출 0, 클리핑 0. peaks (21,10) (215,20) (8,37) (174,53).
  - host 루프백(25.6ms, 20프레임, receiver `7f4745ee…`): model 92429·ps 92430 4/4, 첫 프레임 전bin 일치(`host/prep/`). 처리량은 주장하지 않는다.
- **예측 (계산값, S3a-3b 단계 비용 × 셀 수 2):** PL 처리 ≈ prepare 2.6 + FFT 8.9 + CFAR 10.3 + flush 0.45 ≈ 22.3ms(주기의 87%).

## 번들 (모두 사용자 sudo 배포, 처리 소스 같음: stream_pipeline `103bf9a7…`)

| 번들 | stream_receiver.cpp | stream-receiver | 용도 |
|---|---|---|---|
| `s2a_int16_20261127_s3a4_m256n256` | `e09c1348…` (S3a-3b와 같음) | `3bc3c552…` | 첫 판정 |
| `s2a_int16_20261127_s3a4b_m256n256` | `8dc69e91…` (clock 진단 추가) | `735bdcd5…` | 원인 확인 |
| `s2a_int16_20261127_s3a4c_m256n256` | `e5792290…` (오프셋 재측정 보정) | `ebc3caaf…` | 보정 후 판정 |

- 세 번들 모두 shape.txt는 `56d63b89…`(pulses=256 samples=256)다. SHA와 prepare.log는 `bundles/`에 있다.

## 결과

| run | 번들 | 종류 | 송신 | 처리 | 판정 |
|---|---|---|---|---|---|
| 92431 | s3a4 | PL diag 20 | 무효(정확성 전용) | 전bin 65,536개 일치, 4/4, 카운터 0 | 정확성 통과 |
| 92432 | s3a4 | PL 200 예비 | 유효 (P99 8.44µs) | 처리 22.60ms, c2o P99 23.02ms, queue_full 0 | 예비 충족 |
| 92433 | s3a4 | PS 200 예비 | 유효 (P99 5.66µs) | 71/200, 처리 76.85ms (FFT 55.4) | 불합격 |
| 92434 | s3a4 | PL 10k | 유효 (P99 7.08µs, `4ea51b39…`) | 9997, queue_full 0, kernel_drops 167, c2o P99 23.15 | **무효** (clock_errors 2, 검산 거부) |
| 92435 | s3a4 | PL 10k | 유효 (P99 7.60µs, `94bf8ecd…`) | 9998, queue_full 0, kernel_drops 106, c2o P99 23.05 | **무효** (clock_errors 1) |
| 92436 | s3a4 | PL 10k | 유효 (P99 7.66µs, `c8816526…`) | 9994, queue_full 0, kernel_drops 277, c2o P99 23.27 | **무효** (clock_errors 2) |
| 92437 | s3a4b | PL diag 20 | 무효(정확성 전용) | 전bin 일치, 4/4, 카운터 0 | 정확성 통과 |
| 92438 | s3a4b | PL 10k | 유효 (P99 7.81µs, `02fd394e…`) | 9999, queue_full 0, kernel_drops 49, c2o P99 23.06 | **무효** (clock_errors 2, 원인 확인) |
| 92439 | s3a4c | PL diag 20 | 무효(정확성 전용) | 전bin 일치, 4/4, 카운터 0 | 정확성 통과 |
| **92440** | s3a4c | **PL 10k** | 유효 (P99 7.69µs, 정지 6, `f97b6ff6…`) | 9999, **queue_full 0**, kernel_drops 2 = 손실 패킷 2, clock_errors 0, 4/4·오검출 0 | **처리 실시간 충족, c2o P99 23.128ms** (주기의 90%) |

- c2o는 조립완료→CSV flush다.
- 92440에서 c2o가 25.6ms를 넘은 프레임은 21개(최대 41.47ms)다. 그래도 queue_full은 0이었다. 원인은 확인하지 않았다.
- PS-only 10k는 생략했다. 200 예비의 처리 76.85ms가 주기의 3배다.

### PL 단계 (ms, 중앙 / P99)

| | prepare | FFT | CFAR | flush | 처리 합계 | c2o |
|---|---|---|---|---|---|---|
| 예측 | 2.6 | 8.9 | 10.3 | 0.45 | 22.3 | — |
| 92432 (200) | 3.171 / 3.278 | 9.025 / 9.281 | 10.209 / 10.444 | 0.219 / 0.309 | 22.604 / 22.941 | 22.708 / 23.019 |
| **92440 (10k)** | 3.138 / 3.302 | 9.119 / 9.347 | 10.168 / 10.402 | 0.219 / 0.281 | **22.654 / 22.977** | 22.777 / **23.128** |

- prepare는 예측보다 약 0.5ms 길다. 같은 셀 수당 비용이 S3a-3b(128×256 1.53ms)의 2배보다 크고, 원인은 확인하지 않았다.
- 무효 런 92434~92436·92438의 단계 시간도 92440과 같은 범위다(raw의 stage_stats). 다만 판정에는 쓰지 않는다.

## clock_errors 원인과 보정

- **정의:** receiver는 패킷마다 `before=MONOTONIC, real=REALTIME, after=MONOTONIC`을 읽어 오프셋 = real − (before+after)/2를 구한다. 이 오프셋으로 커널 수신 시각(REALTIME)을 MONOTONIC으로 바꾼다.
  - 오프셋이 첫 값에서 2ms 넘게 벗어나면 `clock_errors`가 오른다.
  - 변환한 커널 시각이 사용자 수신보다 1ms 넘게 늦어도 오른다.
  - 0이 아니면 검산기가 trace를 거부한다.
- **처음 본 것:** 92434~92436이 연속으로 무효였다.
  - 이전 10k급 raw 23개 중 오류가 난 런은 5개(약 22%)였다.
  - CPU1 처리 부하(41~113%)와 첫 패킷 수신 지연은 오류와 상관이 없었다. CPU0 부하는 기록이 없어 보지 못했다.
- **진단 (s3a4b, 92438):** `clock_diag.txt` 기준이다.
  - offset_errors 1, kernel_errors 1이 모두 **같은 패킷 하나**(103,044번, frame 403, chirp 131)에서 났다.
  - 그 측정의 span(after−before)은 **6.40ms**, 오프셋 편차는 **−3.198ms**(≈ −span/2)였다.
  - 즉 수신 스레드가 세 시계 호출 사이에 밀려 중간값 추정이 틀린 것이고, 같은 틀린 오프셋으로 커널 시각 오류가 하나 더 세어졌다.
  - 전체 256만 패킷 중 span 20µs 초과는 37,377개, 1ms 초과는 35개였다. 그 밖의 오프셋 편차는 2ms를 넘지 않았다.
- **보정 (s3a4c, 사용자 승인):** span이 20µs를 넘으면 최대 3번 다시 재고 span이 가장 짧은 값을 쓴다.
  - 2ms·1ms 기준과 무효 규칙은 그대로다. 진짜 시계 점프는 여전히 센다.
  - **92440 결과:** 첫 측정 span 20µs 초과 39,581개(최대 1.48ms)를 모두 다시 쟀고, unresolved 0, 실제로 쓴 span 최대 17.6µs, 오프셋 편차 최대 6.96µs, clock_errors 0.
- **확인하지 않은 것:** 92434~92436의 오류도 같은 원인인지는 그 런에 진단 기록이 없어 확인할 수 없다(추정).
- **변경 파일:** `src/PS/receiver/stream_receiver.cpp` `e09c1348…` → `8dc69e91…`(진단) → `e5792290…`(보정). 이전판은 `build/s3a4b_pre_20261127/`, `build/s3a4c_pre_20261127/`에 있다. `counters.txt` 형식과 종료 코드는 그대로다.
- **host 테스트:** test_check_pacing, test_adc16, test_s2a, test_s1c, test_cfar, test_receiver, test_reference_smoke와 smoke_adc16·smoke_s2a·smoke_s3a1이 진단판(`build/s3a4b_host_02`)과 보정판(`build/s3a4c_host_01`) 모두에서 통과했다.
  - 진단판 첫 빌드(`build/s3a4b_host_01`)는 편집 실수(문자열 줄바꿈)로 컴파일에 실패했다. 기록으로 남긴다.

## 해석

- 256×256 PS+PL은 처리 실시간을 충족했다(92440, P99 23.13ms, 여유 약 2.5ms). PS-only는 불합격이다.
- 결과 정확성은 diag 3회(92431·92437·92439) 모두 하드웨어 전bin 일치로 확인했다.
- 이제 CFAR(10.2ms)이 가장 큰 단계이고, prepare는 예측보다 0.5ms 길다.
- 보정 전 런(S3a-0~S3a-3b)의 판정은 바꾸지 않는다. 보정은 이후 번들에만 적용된다.

## 파일

- `regression/`
  - 런 10개 raw(`*_raw`), 송신 JSON, 검산 출력(무효 런은 거부 traceback), 단계 통계, pin 기록
  - `agent_logs/`: 에이전트 로그와 Ubuntu 스냅샷
- `bundles/`: 세 번들의 SHA, shape.txt, build_environment, prepare.log
- `host/`: host 루프백(`prep/`), 진단판·보정판 host 빌드 환경과 receiver SHA
- `fixture/`: 고정 입력 메타
- 회수 원본은 공유 폴더 `build/s3a4_evidence_20261127_01`에 있다.
