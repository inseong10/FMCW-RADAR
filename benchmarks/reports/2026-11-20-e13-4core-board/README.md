# E13-4core — 기존 FFT 코어4개 병렬 실행 보드 결과

2026-11-20. E13-4core의 RTL·ARM/Vivado·보드 자체 검사·전체 프레임·별도20회 profile·
각300회 paired 비교와 원본 독립 검증을 완료했다.
사용자 Ubuntu 수집75파일/9,270,583 B를 로컬 ignored build/로 복사하고 모든 SHA를 대조했다.
원본 derived JSON도 수정하지 않고, Windows 독립 재계산 결과를 별도 파일로 저장했다.

기존 fft128_pipeline4개/50 MHz/Q15/출력2clocks/sample을 사용한다.
입력을 lane0→1→2→3으로 분배하고 출력도 같은 순서로 배출한다.
네 결과를 모두 받은 뒤 다음 group을 시작하며 외부 버퍼·다음 group prefetch·E12 ping-pong,
E11c 출력 개선·버터플라이 확대·스트리밍 코어 교체는 적용하지 않았다.
HP0/64 KiB/axis/direction·2 ioctl/4채널·coherent 복사·PS gather/scatter는 고정했다.
ABI4의 input/output offset112/65648과 header112 B도2코어와 같고 추가 계측만 payload 뒤에 둔다.

## 비계측 paired 비교

128×128 고정 Q15 입력, 창 없음, 전체1/16384 정규화, CPU0/단일 스레드,
warmup10/repeat100×3 trials다. PS double→NEON→PL 실행 순서를 회전했다.
Q15 배열부터 원래 순서의 CPU 가용2D 출력까지 필요한 복사·DMA·완료 처리·전치를 포함한다.
UDP/파일 I/O·양자화·할당·검증·FFTW plan은 제외했다.

| 경로 | 표본 | 평균 ms | 중앙값 ms | p05–p95 ms | 최대 ms |
|---|---:|---:|---:|---:|---:|
| PS double/FFTW | 300 | 5.756946 | 5.767911 | 5.689833–5.830163 | 6.014286 |
| PS float+NEON/FFTW | 300 | 3.660238 | 3.649998 | 3.600946–3.724890 | 3.794346 |
| PL E13-4core/50 MHz | 300 | 4.203061 | 4.186353 | 4.134642–4.299017 | 4.525278 |

과거2코어 중앙값4.920621 ms 대비 **1.175396배 개선/지연14.922263% 감소**다.
과거 E11b 1코어6.433026 ms 대비 **1.536666배 개선/지연34.924047% 감소**다.
1/2코어를 이번에 교차 실행하지 않았으므로 과거 세션 비교로 구분한다.
이번 paired double보다 **1.377789배 빠르고**, NEON보다 **1.146947배(14.69%) 느리다**.
과거2코어 실행의 paired double5.767263/NEON3.646212 ms와 이번 PS 값은 비슷하지만,
세션 차이의 원인을 단정하거나 전체 시간 차이를 순수 코어 수만의 효과로 확정하지 않는다.

PL trial1/2/3 중앙값은4.175085/4.252101/4.160661 ms다. trial2가 상대적으로 느렸으며
원인을 식별하지 못했다. 이 차이와 최대4.525278 ms도 원시 분포에 보존했다.
CPU 주파수 sysfs는 unavailable이며 BogoMIPS를 실제 주파수로 사용하지 않았다.
부팅 식별자·IRQ 배치와 환경을 보존했다. 이번 부팅은2코어 측정과 다르다.

## 정확도·신원·실제 병렬성

- 모든 반복의 보드 정수 검사 PASS. 마지막3개 비계측 출력과 profile 출력의 각각16,384
  complex bins가 독립 Python Q15 모델과 허용 오차 없이 완전 일치한다. 피크는(107,20)이다.
  저장 입력의 Q15 양자화도 동일 fixture와 일치한다.
- PL NumPy 최대 복소 오차8.749842363 Q15 LSB/상대 L2 약1.361020928%로 기존 산술과 같다.
  PS double 최대 오차1.833145e-12 LSB, NEON 약0.000426809 LSB다.
  Ubuntu/Windows FFT 참조 끝자리 차이는 raw_validation.json에 보존했다.
  부동소수점 재계산 대조 허용치는 정수 oracle의 완전 일치 검사에 적용하지 않았다.
- DMA IRQ67/68은 CPU0 각각660회 증가/CPU1 증가0으로330프레임×2축과 일치한다.
  프레임2 ioctl/4채널/256 FFT/전체 payload262144 B다.
- artifact/source·입력·PS build/실제 NEON codelet/FFTW plan·회전 순서를 재검증했다.
  profile/비계측 bundle이 같고22개 artifact는 자체 검사 당시 SHA와 일치한다.
  빌드 소스 manifest는 현재 checkout raw SHA와 일치한다.
- 실제 routed hierarchy는 네 코어 각각DSP4개다. profile의 all-work5952cycles/frame에서
  초기 출력 읽기 비CALC 상한64cycles를 차감해도 실제4코어 동시 CALC 하한5888cycles가 남는다.
  multi-work38720cycles에서256을 차감한2개 이상 CALC 하한은38464cycles다.
  이 값들은20회 모두 같고 실제 DMA 병렬 계산을 확인한다.
- 원본 build metadata board_verified:false는 보존한다. 검증된 SHA 집합의 완료 상태는
  별도 board_verification.json에 기록했다. 계측 trial 혼입/1LSB 변조 출력을 거부하는 검사도 PASS다.

## 별도20회 profile

계측 평균4.222976 ms/중앙값4.220256 ms다. 비계측300회와 합치지 않는다.

| 겹치지 않는 host 구간 | 평균 ms |
|---|---:|
| 사용자 입력 복사 | 0.232855 |
| ioctl 전체 | 3.060724 |
| 사용자 출력 복사 | 0.234406 |
| PS gather/scatter | 0.685061 |
| host 잔여 | 0.009931 |
| 전체 | 4.222976 |

ioctl 내부는 커널 copy-in0.211416 + submit/start0.036209 + wait2.128747 +
check0.015439 + copy-out0.645398 + 잔여0.023514 ms다.
이 구간과 PL active는 ioctl에 중첩되므로 전체에 다시 더하지 않는다.
사용자+커널 복사합은 **1.324075 ms**, PS 전치는 **0.685061 ms**다.

PL active는 **2.081883 ms(전체49.30%)**로 과거2코어2.857541 ms 대비
**1.372575배 개선/27.14% 감소**다. LOAD/CALC/OUTPUT과 stream 정지를 포함한다.
무정지 RTL 모델104064cycles/frame/2.081280 ms에 근접하며 입력 starvation 평균30.15cycles,
외부 출력 stall0이다. 이 실행의 global−input_stall은 모든 행에서104064cycles였으나
병렬 실행에서 stall 합을 빼 순수 butterfly 시간으로 해석하지 않는다.

평균 core0/1/2/3 busy는55070.15/71390.15/87710.15/104030.15cycles,
any-busy104030.15/multi-busy87710.15/all-busy55070.15cycles다.
global−any-busy=64cycles/frame은 group 시작 기포와 일치한다.
work-window는 마지막 입력부터 첫 출력 valid 전까지이며 초기 RAM 읽기도 포함한다.
arbitration40704cycles는 차례가 아닌 코어에 출력 valid가 있는 시간으로,
외부 TREADY stall이나 그대로 회수 가능한 전체 지연을 뜻하지 않는다.

## 해석과 다음 판단

무정지 사이클 사전 모델2.081280 ms와 실제 active2.081883 ms가 근접한다.
코어 수2→4는 공유 입력/순서 보존 출력·group barrier 전체를 반감시키지 못해
내부 개선도 약1.373배이며, 전체 중앙값 개선은 약1.175배다.
계측 PL 밖 잔여 **2.141093 ms**가 남아 active 비중이 절반 이하가 됐다.

과거2코어 profile 전체4.974313→4.222976 ms로0.751337 ms 감소했고
PL active는0.775658 ms 감소했다. 잔여는2.116772→2.141093 ms,
복사합1.320890→1.324075 ms/전치0.680213→0.685061 ms로 약간 증가했다.
이 차이의 원인은 별도 실행의 캐시·스케줄링 등을 포함해 미확인이며,
잔여를 순수 CPU 실행 시간으로 부르지 않는다.

후속으로는 공유 출력의2clocks/sample을 개선하는 E11c를 우선 검토할 근거가 있다.
arbitration은2코어16256→4코어40704cycles/frame으로 늘었지만 이를 그대로 빼 절감량으로
예측하지 않는다. 출력 개선의 실제 절감·역압 안정성은 별도 RTL/보드 실험으로 검증해야 한다.
복사1.324 ms도 독립적인 E11d 후보이며8코어 확대와 함께 넣지 않는다.
이번 완료 범위는 E13-4core이고 E11c/E11d/E12/8코어 이상은 미실행이다.
고정 warm-cache 오프라인 지연이며 연속 UDP 처리량·최악 지연·드랍0/실시간 보장은 미검증이다.

## 구현·원본·재검증

50 MHz WNS9.982 ns/WHS0.024 ns, setup/hold 위반0,
LUT4868/17600·FF5169/35200·BRAM11/60·DSP16/80이다.
[빌드·자체 검사](../2026-11-20-e13-4core-build/README.md),
[RTL 준비](../2026-11-20-e13-4core-preparation/README.md),
[선행2코어](../2026-11-20-e13-2core-board/README.md).

전체 원본은 ignored `build/fft128_dma_quad_measurements/{results_e13_4core_01,profile_e13_4core_01}`에 있다.
보고서에는 시간/profile CSV·로그·환경·wisdom·manifest를 보존하고 큰 입력/출력 spectrum CSV의
경로·크기·SHA는 raw_artifact_sha256.json에 기록했다. 분석 소스와 추가 validation driver 원문도 보존한다.

```sh
python benchmarks/compare_dma_quad_board.py build/fft128_dma_quad_measurements/results_e13_4core_01
python src/PS/fft128/dma_quad/analyze_profile.py build/fft128_dma_quad_measurements/profile_e13_4core_01/pl.profile.csv
```
