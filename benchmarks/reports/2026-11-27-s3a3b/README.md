# S3a-3b — R축 128×256 처리 시간 감축 (결과 비트 동일)

- **날짜:** 2026-11-27 (작업은 11-26 저녁에 시작)
- **표기:** M(chirp)×N(샘플)
- **문제:** S3a-3 92425(PL 128×256, 12.8ms)는 처리 13.761ms로 주기를 넘었다(queue_full 673). 여유까지 약 2ms를 줄여야 했다.
- **변경:** `src/PS/receiver/stream_pipeline.hpp` `2ba1c7f5…` → `103bf9a7…`. 원본은 `build/s3a3b_pre_20261126/`에 있다. 128×128 경로(`prepare` scalar 루프, `transform128`)는 그대로다.
  1. **N=256 저장 순서:** prepare가 각 행을 짝수 샘플 128개, 홀수 샘플 128개 순으로 쓴다(샘플 2k+q → q·128+k). 가중치도 생성자에서 같은 순서로 놓는다. range 블록 모으기가 strided에서 연속 복사로 바뀐다.
  2. **range 단계 결합:** Doppler 분할이 없으면(split_d=1, split_r=2) 블록 1을 배치하지 않고, E14(또는 model) 출력에서 바로 읽어 range 단계(L=256, twiddle j)를 계산한다.
  3. **NEON 결합 행:** 32비트 ARM에서 `Pipeline::butterfly`의 int32 식을 NEON 4레인으로 계산한다(`vmull_s16`, 시프트, 마스크, `vqmovn_s32`=sat16). Doppler 결합(`combine_const`)과 range 결합(`combine_tw`)에 쓴다.
  4. **NEON prepare:** 128×128보다 큰 크기에서 `adc_window`의 32비트 조각 식을 NEON으로 계산한다(`vmull_u32`, `vshrn_n_u64`, `vmovn_u64`).
  - NEON은 `#pragma GCC target("fpu=neon")`으로 이 커널 함수에만 켠다. 빌드 플래그(`build_s2a.sh` 기본 `-O2`)는 바꾸지 않았다. Cortex-A9(Zynq-7010)에는 NEON이 있다.
  - x86 host는 scalar 대체 경로를 쓴다. 그래서 host 덤프는 scalar 경로를, 보드 덤프는 NEON 경로를 확인한다.
- **테스트 추가:**
  - `tests/micro_s3a3b.cpp` `854100b2…`: 128×256 prepare, 모으기, 배치+결합의 이전 형태와 새 형태 비교
  - `tests/butterfly_s3a3b_neon_equiv.cpp` `2c3edc8a…`: NEON 결합과 scalar 버터플라이의 등가성
  - `tests/window_s3a3b_neon_equiv.cpp` `62200f90…`: NEON 윈도우와 `adc_window`의 등가성, 행 커널 비교
  - 세 테스트 모두 bench 사본에서만 클래스 접근을 열어 빌드한다(`bench/src_*`). window 등가성 테스트만 `-mfpu=neon`으로 빌드한다(main에서 NEON intrinsic을 부르기 때문).

## 정확성 (모두 통과)

- **NEON 결합 등가성 (보드):** 247,525,504건, twiddle 260개에서 scalar `butterfly`와 같았다. `combine_tw` 두 방식(fused bo≠bi, in-place bo=bi)과 `combine_const`를 모두 대조했다. new2와 new3 바이너리에서 각각 통과했다.
- **NEON 윈도우 등가성 (보드):** 205,232,624건, 사용 중인 Q30 가중치 64,895개에서 `adc_window`와 같았다.
  - 모든 int16 값 × 경계 가중치 64개
  - 사용 중인 가중치 × 경계 값 16개
  - 무작위 2억 건
  - 행 커널 `prepare_plain`과 `prepare_deint256`을 무작위 프레임 20개(1개는 −32768/32767 고정)에서 scalar 루프와 비교
- **분할 경로 덤프 (bench_s3a2, model):** 4개 크기 × hann/none × 입력 7종이 모두 `2e47b50b…`로 S3a-2b와 같았다.
  - host(scalar): old, new, new2, new3
  - 보드(NEON): new(res_01), new2(res_new2_01), new3(res_new3_01)
- **host 테스트와 smoke (`build/s3a3b_host_01`):** 모두 통과했다. host stream-receiver `7f4745ee…`, arm `3bc3c552…`.
  - test_check_pacing OK, test_adc16 OK(skip 1), test_s2a OK(skip 3), test_s1c OK
  - test_cfar OK, test_receiver OK(skip 4), test_reference_smoke OK
  - smoke_adc16, smoke_s2a, smoke_s3a1(8건) PASS
  - 콘솔 출력만 있고 파일 로그는 남기지 않았다. smoke 출력 디렉터리는 `host/`에 있다.
- **보드 PL diag 92427 (사용자 sudo):** 20/20, 카운터 0, `all_bins=True`, 4/4, 오검출 0. 송신은 무효(지터 P99 38.6µs)이고 정확성 전용이다. 보드에서 등가성 검사가 같이 돌고 있었다.

## 보드 micro (`micro_s3a3b`, CPU1, 200회 중앙값, μs, 128×256)

| 단계 | S3a-2b 형태 | 1판 (순서·결합) | 2판 (+NEON 결합) | **3판 (+NEON prepare, 채택)** |
|---|---|---|---|---|
| prepare | 1,904 | 2,012 | 2,033 | **1,281–1,295** |
| 모으기 | 608–626 | 322–350 | 352–359 | 348–358 |
| 배치+결합 | 2,002–2,011 | 1,838–1,853 | 677 | **693–695** |

- 이전 형태 값은 같은 실행 안의 old 루프(또는 old 헤더 빌드)다. 각 판을 두 번씩 측정했다.
- 1판은 prepare가 두 갈래로 쓰면서 +0.1ms 늘어, 합계 감축이 약 0.34ms에 그쳤다. 그래서 2판과 3판을 진행했다.
- 참고: 256×128 Doppler 단계(`combine_const`)는 573–586μs로, S3a-2b의 1,591μs보다 짧다.

## 10k (PL, 128×256, 12.8ms)

- **번들:** `s2a_int16_20261127_s3a3b_n256` (사용자 sudo 배포)
  - stream-receiver `3bc3c552…`, source.sha256 `6b5660a7…`(stream_pipeline `103bf9a7…`), shape.txt `47243607…`
- **실행 조건:** 래퍼 v3, 에이전트 송신 v4, nfs, reanchor, chirp 100µs, 고정 1/1/2, PL 100MHz, 큐 4. AC 전원 확인(BatteryStatus 2).
- **입력:** `radarsimpy_128x256_sim_multi4_noise_adc16.rspb` `58ab27b7…`

| run | 송신 | 처리 | 판정 |
|---|---|---|---|
| 92427 | 무효 (P99 38.6µs, diag 전용) | 20/20, 카운터 0, 전bin 일치 | 정확성 통과 |
| **92428** | 유효 (P99 5.56µs, 정지 7, `8629038e…`) | 9992, **queue_full 0**, kernel_drops 401 = 손실 패킷 401, 4/4·오검출 0 | **처리 실시간 충족, 조립완료→출력 P99 10.99ms** (주기의 86%) |

- 그 밖의 카운터는 모두 0이다(clock_errors 0 포함). 독립 검산 `--network-loss-ok`는 PASS다.
- 92425와 마찬가지로 receiver 종료 코드는 2이고, 10k 검산의 `all_bins=False`는 정상이다(전bin 비교는 diag에서 한다).

단계 시간(ms, 중앙 / P99)은 다음과 같다.

| | prepare | FFT | CFAR | flush | 처리 합계 | 조립완료→출력 |
|---|---|---|---|---|---|---|
| S3a-3 92425 | 2.382 / 2.474 | 6.045 / 6.220 | 5.107 / 5.253 | 0.226 / 0.290 | 13.761 / 14.013 | — (불합격) |
| **S3a-3b 92428** | **1.530 / 1.645** | **3.688 / 3.860** | 5.158 / 5.307 | 0.223 / 0.289 | **10.609 / 10.848** | 10.712 / **10.990** |

- prepare는 −0.85ms, FFT는 −2.36ms 줄었다. 처리 합계는 −3.15ms다.
- 조립완료→출력이 12.8ms를 넘은 프레임은 23개(최대 30.26ms)다. 그래도 queue_full은 0이었다. 이 지연의 원인(큐 대기 최대 17.9ms)은 확인하지 않았다.
- CFAR(5.16ms)은 바꾸지 않았다. 같은 셀 수의 256×128보다 약 +9% 긴 원인은 여전히 미확인이다.

## 해석

- 결과는 그대로이고, 128×256 PL은 처리 실시간을 충족했다(P99 10.99ms, 여유 약 1.8ms).
- 확인하지 않은 것:
  - 이 번들의 256×128(D축)이나 128×128 성능은 재측정하지 않았다. 128×128 경로는 코드가 그대로이고, 256×128은 NEON Doppler 결합과 prepare를 쓴다.
  - PS-only 128×256은 이번 변경과 무관하므로 측정하지 않았다(S3a-3에서 불합격).
- **실패와 무효 기록:**
  - 첫 bench 빌드 `out_fail_access_01`: new 헤더 사본의 클래스 접근을 열지 않아 컴파일이 실패했다. 고쳐서 `out`으로 다시 빌드했다.
  - 92427은 송신이 무효라 시간 판정에서 뺐다(정확성 전용).

## 파일

- `bench/`
  - 빌드 스크립트 `build.sh`(old/new), `build_new2.sh`, `build_new3.sh`
  - 소스 `src_old`(=`2ba1c7f5`, 접근만 열림), `src_new`, `src_new2`, `src_new3`(=`103bf9a7`, 접근만 열림)
  - `host/out*`: 결과 txt, source·binary SHA, 덤프 SHA
  - `board/res_01`, `res_new2_01`, `res_new3_01`: 등가성, 덤프 SHA, micro
- `regression/`
  - 92427·92428 raw
  - 송신 JSON, 검산 출력, 단계 통계
  - pin 기록, 에이전트 로그, Ubuntu 스냅샷(`agent_logs/`)
  - 번들 SHA, shape.txt, prepare.log
- `host/`: smoke 출력, host·arm receiver SHA, 빌드 환경
- 회수 원본은 공유 폴더 `build/s3a3b_evidence_20261127_01`, bench 작업공간은 `build/s3a3b_bench_20261127`에 있다.
