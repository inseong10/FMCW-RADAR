# E13-2core — 기존 FFT 코어2개 병렬 실행 보드 결과

2026-11-20. E13의 첫 실험인2코어 복제의 RTL·ARM/Vivado·보드 자체 검사·전체 프레임·
별도20회 profile·각300회 paired 비교와 원본 독립 검증을 완료했다.
사용자 Ubuntu 수집75파일/9,269,549 B를 Windows ignored build/로 복사하고 모든 SHA를 대조했다.

두 기존 fft128_pipeline/50 MHz/Q15/출력2clocks/sample을 사용한다.
공유 입력에 두 FFT를 순서대로 분배하고 두 출력이 모두 수락된 뒤 다음 pair를 시작한다.
코어 사이 LOAD/CALC·CALC/CALC 겹침은 포함하며 외부 버퍼·다음 pair prefetch·E12 ping-pong,
E11c 출력 개선·버터플라이 확대·스트리밍 코어 교체는 적용하지 않았다.
축당128 FFT/64 KiB, 프레임2 ioctl/4채널, HP0 coherent 복사와 PS gather/scatter를 유지했다.

## 비계측 paired 비교

128×128 고정 Q15 입력, 창 없음, 전체1/16384 정규화, CPU0/단일 스레드,
warmup10/repeat100×3 trials다. PS double→NEON→PL 실행 순서를 회전했다.
입력 Q15 배열부터 CPU에서 원래 순서로 읽을 수 있는2D FFT 출력까지, 필요한 복사·DMA·
완료 처리·전치를 포함한다. UDP/파일 I/O·양자화·할당·검증·FFTW plan은 제외했다.

| 경로 | 표본 | 평균 ms | 중앙값 ms | p05–p95 ms | 최대 ms |
|---|---:|---:|---:|---:|---:|
| PS double/FFTW | 300 | 5.757465 | 5.767263 | 5.696374–5.821721 | 6.088188 |
| PS float+NEON/FFTW | 300 | 3.655996 | 3.646212 | 3.599169–3.725552 | 3.785298 |
| PL E13-2core/50 MHz | 300 | 4.929082 | 4.920621 | 4.900664–4.987038 | 5.028390 |

과거 E11b 단일 코어 중앙값6.433026 ms 대비 **1.307361배 개선, 지연23.510009% 감소**다.
E11b를 이번 실행에 교차 배치하지 않았으므로 과거 세션 비교로 구분한다.
이번 paired PS double 대비 **1.172060배 빠르고**, NEON 대비 **1.349516배 느리다**.
PS 기준 자체도 과거 double5.717376/NEON3.558177 ms에서 변했다.
그 차이를 코어 복제의 인과 효과로 해석하지 않는다. CPU 주파수 sysfs는 unavailable이며
BogoMIPS를 실제 주파수로 사용하지 않았다. 부팅 식별자와 IRQ 배치를 보존했다.

## 정확도·신원·실제 병렬성

- 매 반복 보드 정수 검증 PASS. 마지막3개 비계측 출력과 profile 출력은 각각16,384 complex
  bins 모두 독립 Python Q15 모델과 완전 일치하며 피크는(107,20)이다.
  양자화된 입력도 같은 fixture와 일치한다.
- NumPy 대비 PL 최대 복소 오차8.749842363 Q15 LSB/상대 L2 약1.361020928%로 기존 Q15
  산술과 동일하다. PS double 최대 오차1.833145e-12 LSB, NEON 약0.000426809 LSB다.
  Ubuntu/Windows NumPy FFT 참조의 부동소수점 끝자리 차이는 raw_validation.json에
  보존했다. 정수 oracle 비교는 허용 오차 없이 수행했다.
- DMA IRQ67/68은 CPU0에서 각각660회 증가, CPU1 증가는0이다.
  330프레임(측정300+warmup30)×2축과 맞는다. 각 프레임2 ioctl/4채널/256 FFT,
  입력+출력 payload262144 B다.
- 원본 artifact/source/입력/PS build/NEON codelet·FFTW plan·회전 순서를 재검증했다.
  profile과 비계측 bundle이 같고22개 artifact SHA는 자체 검사 당시 번들과 일치한다.
  빌드 소스 manifest는 현재 checkout의 raw SHA와 일치한다.
- 구현 hierarchy에 core0/core1 각각DSP4개, 전체DSP8개가 있다. 별도20회 profile의
  both-work는 매 프레임44672cycles다. 초기 출력 RAM 읽기 겹침 상한128cycles를
  차감해도 실제 동시 CALC 하한44544cycles가 남는다. 실제 DMA 구동에서 병렬 계산을 확인했다.
  두 코어 busy합집합과 global의 차이는 매 프레임128cycles로 pair 시작 기포와 일치한다.
- 원본 dma_config.json의 board_verified:false는 빌드 시점 상태로 보존한다.
  검증한 artifact SHA 집합에 적용되는 완료 상태는 board_verification.json에 별도로 기록했다.

## 별도20회 profile

계측 평균4.974313 ms/중앙값4.963695 ms다. 비계측300회와 합치지 않는다.

| 겹치지 않는 host 구간 | 평균 ms |
|---|---:|
| 사용자 입력 복사 | 0.231647 |
| ioctl 전체 | 3.802151 |
| 사용자 출력 복사 | 0.250717 |
| PS gather/scatter | 0.680213 |
| host 잔여 | 0.009584 |
| 전체 | 4.974313 |

ioctl 내부는 커널 copy-in0.201872 + submit/start0.036765 + wait2.891536 +
check0.012146 + copy-out0.636653 + 잔여0.023179 ms다. ioctl 및 PL active와 겹치므로
전체에 다시 더하지 않는다. 사용자+커널 입력/출력 복사합은1.320890 ms다.

PL active 평균은 **2.857541 ms(전체57.45%)**로, 과거 E11b4.408947 ms 대비
**1.542916배 개선/35.19% 감소**다. 이 값은 LOAD/CALC/OUTPUT과 stream 정지를 포함한다.
no-stall RTL 모델2.856960 ms에 근접하며 입력 starvation 평균29.05cycles/frame,
외부 출력 정지0cycles다. 이 실행에서는 global−input_stall=142848cycles가 모든 행에서
관찰됐지만 일반적인 병렬 실행에서 stall 합을 빼 순수 계산 시간으로 해석하지 않는다.

평균 카운터는 core0 busy110109.05/core1 busy142749.05/both-busy110109.05,
both-work44672/arbitration16256cycles다. busy와 work-window는 중첩 구간이며 더하지 않는다.
work-window는 마지막 입력 handshake부터 첫 출력 valid 전까지로 순수 CALC만은 아니다.
arbitration은 차례가 아닌 코어에 출력 valid가 있는 시간으로 외부 TREADY 정지와 다르다.

## 가설과 실제값·다음 판단

초기 내부 전체 반감2.204160 ms 가설은 공유 순차 입력·출력과 pair barrier를 반영하지
못했다. 구현 전 RTL이 제시한2.856960 ms와 실제 PL active2.857541 ms는 일치하는 수준이다.
물리 코어 수2배가 전체 프레임2배 개선을 의미하지 않음을 수치로 확인했다.

계측 전체는 과거6.473645→4.974313 ms로1.499332 ms 감소했고 PL active는1.551406 ms
감소했다. PL active 밖의 벽시계 잔여는2.064698→2.116772 ms다.
복사합1.263008→1.320890 ms, PS 전치0.670374→0.680213 ms로 조금 증가했다.
복사 정책·단계는 같지만 실행 간 간격·캐시·스케줄링 조건이 영향을 줄 수 있으며
이 차이의 원인을 코어 복제로 단정하지 않는다. 잔여를 순수 CPU 실행 시간으로 부르지 않는다.

추가 코어만으로 전체 시간을 같은 비율로 줄일 수 없다. 후속 후보는 공유 출력/스케줄의
노출 구간 개선, 추가 코어 수 실험, 복사 정책 개선이다. 한 번에 하나를 바꾸고 같은 검증을
반복한다. 이번 완료 범위는 E13-2core이며 E11c/E11d/E12/4코어 이상은 미실행이다.
오프라인 warm-cache 지연이며 연속 UDP 처리량·최악 지연·드랍0/실시간 보장은 미검증이다.

## 구현·원본·재검증

50 MHz WNS9.292 ns/WHS0.029 ns, setup/hold 위반0.
LUT3818/17600·FF4460/35200·BRAM7/60·DSP8/80이다.
[실제 빌드·자체 검사](../2026-11-20-e13-2core-build/README.md),
[RTL 준비](../2026-11-20-e13-2core-preparation/README.md).

전체 입력/출력 spectrum을 포함한 원본은 ignored
`build/fft128_dma_parallel_measurements/{results_e13_2core_01,profile_e13_2core_01}`에 있다.
보고서에는 시간/profile CSV·로그·환경·wisdom·manifest를 보존하고 큰 spectrum/input CSV는
raw_artifact_sha256.json에 경로·크기·SHA를 기록했다. analysis_source_sha256.json은 분석 소스
신원이며 계측 trial 혼입/1LSB 변조 출력을 거부하는 검사도 통과했다.

```sh
python benchmarks/compare_dma_parallel_board.py build/fft128_dma_parallel_measurements/results_e13_2core_01
python src/PS/fft128/dma_parallel/analyze_profile.py build/fft128_dma_parallel_measurements/profile_e13_2core_01/pl.profile.csv
```
