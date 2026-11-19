# E11b — 축당 128 FFT DMA 묶음 제출 보드 결과

2026-11-19. 사용자 Ubuntu NFS 결과를 공유 폴더로 회수한 뒤 Windows에서 원시 CSV·로그·
출력·신원·IRQ를 독립 재검증했다. E11b 구현·빌드·보드 자체 검사·전체 프레임·계측·각 300회
paired 비교를 완료했다. 같은 단일 fft128_pipeline/50 MHz/Q15/출력 2클록/sample을 유지했다.
사용자/커널 cached/coherent 복사 단계와 PS gather/scatter를 유지하고 전송 크기·요청 단위를 바꿨다.

## 비계측 paired 비교

128×128 고정 Q15 입력·창 없음·전체 1/16384 정규화·CPU0·단일 스레드다.
각 warmup10/repeat100×3 trials이며 double → NEON → PL 순서를 회전했다.
모든 복사·전송·완료 처리·두 축 FFT·전치를 포함하고 UDP/파일 I/O·할당·검증·plan은 제외했다.

| 경로 | 표본 | 평균 ms | 중앙값 ms | p05–p95 ms |
|---|---:|---:|---:|---:|
| PS double/FFTW | 300 | 5.710036 | 5.717376 | 5.649892–5.767121 |
| PS float+NEON/FFTW | 300 | 3.575637 | 3.558177 | 3.539030–3.634776 |
| PL E11b DMA/50 MHz | 300 | 6.432092 | 6.433026 | 6.396787–6.474537 |

E11a의 과거 중앙값 15.411639 ms보다 약 2.396배 빠르고 지연은 58.26% 줄었다.
E11a를 이번에 교차 실행하지 않았으므로 과거 실행과의 비교다. 이번 paired PS double보다
PL은 1.125배, NEON보다 1.808배 느리다. NEON은 이전 E11a의 3.715234 ms에서
이번 3.558177 ms로 달라졌으며 이 차이를 묶음 제출의 인과 효과로 단정하지 않는다.
CPU 주파수 sysfs는 unavailable로 기록됐고 BogoMIPS를 실제 주파수로 쓰지 않았다.

## 전송 단위·정확도·신원

- 한 축 128 FFT, 입력/출력 각 65,536 B; 프레임당 2 ioctl/4 DMA 채널 제출/FFT 256회.
  전체 payload는 기존과 같은 256 KiB다. 입력/출력 완료 IRQ67/68은 각각 CPU0에서
  660회 증가했고 CPU1 증가는 0이다. 330프레임(측정300+warmup30)×2축과 맞는다.
- 매 반복 보드 정수 검증 PASS. 마지막 출력 3개와 profile 출력도 독립 Python Q15 모델에
  16,384 bin 전부 일치한다. 피크는 모두 (107,20)이다.
- NumPy 대비 PL 최대 복소 오차 8.749842363 Q15 LSB, 상대 L2 1.361020928%로 기존 산술을
  유지한다. PS double 최대 오차 1.833145e-12 LSB, NEON 0.000426808672 LSB다.
- 입력 SHA는 `aa06ff124034310216693c1398f2f1061c9a6ce32e9ea6f5687675849934c976`이다.
  보드 artifact check·source manifest·회전 순서·FFTW plan/실제 NEON codelet·정규화를 확인했다.
  profile/비계측 bundle manifest가 같고 20개 artifact의 SHA가 빌드 검증 bundle과 일치한다.
- 원본 dma_config.json의 board_verified:false는 빌드 시점 상태다. 측정 bundle을 수정하지 않고
  이 검증한 해시 집합에만 적용되는 완료 상태를 board_verification.json에 남겼다.

## 별도 20회 프로파일

계측 평균 6.473645 ms, 중앙값 6.464940 ms다.
비계측 300회와 같은 모집단으로 합치지 않는다.

| 겹치지 않는 host 구간 | 평균 ms |
|---|---:|
| 입력 사용자 복사 | 0.260192 |
| ioctl 전체 | 5.360488 |
| 출력 사용자 복사 | 0.173017 |
| PS gather/scatter | 0.670374 |
| host 잔여 | 0.009573 |
| 전체 | 6.473645 |

ioctl 내부는 copy-in 0.198589 + submit/start 0.035202 +
wait 4.461962 + check 0.010188 + copy-out 0.631210 +
잔여 0.023337 ms다. 이 구간을 ioctl 전체와 다시 더하지 않는다.
사용자+커널 입력/출력 복사 합은 1.263008 ms다.

PL active는 4.408947 ms로 같은 계측 전체의 68.1%다.
모든 행에서 active−input_stall−output_stall=861×256 cycles, nonstall 환산 4.408320 ms다.
입력 정지는 평균 31.35 cycles/frame(0.000627 ms), 출력 정지는 0이었다.
이 active 구간은 LOAD/CALC/OUTPUT을 포함하며 순수 butterfly 계산만이 아니다.
wait는 PL active와 겹치고 IRQ·스케줄링도 포함하므로 순수 버스 전송 시간으로 해석하지 않는다.

## 해석과 다음 선택

작은 FFT별 제출·완료 병목이 크게 줄었고 코어 LOAD/CALC/OUTPUT 구간이 가장 크다.
E11b의 약 8 ms 가설보다 실제값이 짧았다. 계측 복사 합은 E11a 2.256989 → E11b
1.263008 ms, PS gather/scatter는 1.002013 → 0.670374 ms로 관찰됐다.
정밀도·정책·복사 단계 수는 유지했지만 64 KiB 전송과 호출 간격 변화가 메모리 접근 패턴도
바꾸므로 이를 요청 횟수 감소만의 독립 효과라고 주장하지 않는다. 두 프로파일은 별도 실행이다.

다음 주 가속 후보는 E13의 연산 구조 확대다. E11c 출력 개선은 독립적으로 약 0.65 ms의
무정지 상한을 검증할 수 있다. E12는 외부 이중 버퍼로 LOAD/OUTPUT을 숨기는 별도 후보이며,
측정된 외부 stream stall 0.000627 ms만 보고 E12의 잠재 이득이 없다고 판단하지 않는다.
코어 내부 LOAD/OUTPUT과 겹칠 수 있는 구간을 별도로 설계·검증해야 한다.
복사 1.263 ms와 전치 0.670 ms도 남아 있어 코어 수를 늘린 만큼 전체가 빨라지지 않는다.
E11c/E11d/E12/E13 및 PS02는 아직 구현·측정하지 않았다.

중앙값과 이번 최대값 6.505416 ms는 명목 12.8 ms보다 짧지만, 같은 기록 프레임의 warm-cache
오프라인 지연이다. 연속 UDP 처리량·최악 지연·드랍 0·실시간 보장을 입증하지 않았다.

## 원본·재검증

전체 spectrum/input CSV를 포함한 원본은 ignored
`build/fft128_dma_batch_measurements/{results_e11b_01,profile_e11b_01}`에 보존했다.
보고서에는 시간/profile CSV·로그·환경·wisdom·manifest를 보관하고 큰 입력/출력은
raw_artifact_sha256.json에 경로·크기·SHA를 기록했다.
analysis_source_sha256.json은 독립 분석 소스 신원이다. 계측 trial 혼입과 1 LSB 변조 출력
거부 검사도 통과했다(analysis_guards.json).

```sh
python benchmarks/compare_dma_batch_board.py build/fft128_dma_batch_measurements/results_e11b_01
python src/PS/fft128/dma_batch/analyze_profile.py build/fft128_dma_batch_measurements/profile_e11b_01/pl.profile.csv
```

[빌드·보드 자체 검사](../2026-11-19-e11b-build/README.md),
[실험 일지](../../../docs/experiment_log.md), [후속 계획](../../../docs/fft128_dma_plan.md).
