# E11a — FFT당 Simple DMA 보드 측정

2026-11-16에 사용자 VM의 NFS 결과를 공유 폴더에서 회수해 독립 검증했다.
기존 산술·파이프라인·50 MHz·출력 2클록/sample·PS gather/scatter를 유지하고,
샘플 입출력을 MMIO에서 HP0 Simple DMA로 바꾼 실험이다.
한 ioctl에 FFT 하나, TX/RX 각 512 B, 프레임당 256 ioctl/512 DMA 채널 제출이다.
coherent bounce buffer를 사용하며 CPU 복사·ioctl·제출·완료 대기·FFT·전치를 모두 측정한다.

## 비계측 paired 비교

같은 보드·고정 Q15 입력·창 없음·1/16384 정규화·CPU0·단일 스레드다.
각 warmup 10/100회 × 3 trials이며 double → NEON → PL 순서를 매 trial 회전했다.
UDP/파일 입출력·양자화·할당·FFTW plan·검증은 제외했다.
NEON의 두 축에서 실제 NEON codelet을 확인했다. 시간은 FFT 두 축뿐인 `FFT only`가 아닌
복사·전치·정규화를 포함한 `fft_pipeline`이다.

| 경로 | 표본 | 평균 ms | 중앙값 ms | p05~p95 ms |
|---|---:|---:|---:|---:|
| PS double/FFTW | 300 | 5.737376 | 5.748489 | 5.677691~5.800609 |
| PS float+NEON/FFTW | 300 | 3.726932 | 3.715234 | 3.670984~3.796117 |
| PL DMA/50 MHz | 300 | 15.415091 | 15.411639 | 15.295845~15.547105 |

이번 paired 결과에서 PL은 PS double보다 약 2.68배, NEON보다 약 4.15배 느리다.
과거 E10 MMIO 중앙값 25.259173 ms와 비교하면 PL 경로는 약 1.639배 빨라지고
지연은 약 39.0% 줄었다. 이는 **과거 실행과의 비교**이며 이번 회차에 MMIO를 재측정하지 않았다.
PS01의 과거 NEON 3.615852 ms 대신 이번 paired NEON 3.715234 ms를 현재 비교에 사용했다.
PS 수치 차이를 DMA의 인과 효과로 단정하지 않는다.

## 정확도·신원

입력 SHA256은 `aa06ff124034310216693c1398f2f1061c9a6ce32e9ea6f5687675849934c976`이다.
보드의 DMA/PS artifact check, source manifest, 입력·scale·순서·반복 수·affinity·정규화를 확인했다.
PL 매 반복의 C 정수 모델 검증 로그와 마지막 출력 3개를 확인했고, 독립 Python Q15 모델과도
각 16,384 bin 전부 일치했다. 계측 실행의 마지막 출력도 동일하게 확인했다.

NumPy float64 기준 최대 복소 오차는 PS double 1.833145e-12 Q15 LSB,
NEON 0.000426808672 LSB, PL 8.749842363 LSB다.
PL 상대 L2는 0.0136102093(약 1.361%)이며 피크는 모두 (107,20)이다.
PL의 정수 모델 일치는 부동소수점과 오차가 없다는 뜻이 아니다. E10과 같은 Q15 오차를 유지한다.
IRQ67/68은 각각 CPU0에서 84,480회 증가했고 CPU1에서는 증가하지 않았다.
이는 330프레임(측정 300+warmup 30) × 256 FFT/프레임의 완료 횟수와 맞는다.

## 별도 프로파일

warmup 2/repeat 20의 계측 실행은 평균 18.136318 ms, 중앙값 18.129750 ms다.
비계측 300회 분포와 합치지 않는다. 두 실행의 차이를 모두 계측 오버헤드로 단정하지 않는다.

| 호스트의 겹치지 않는 구간 | 평균 ms |
|---|---:|
| 요청 입력 복사 | 0.529984 |
| ioctl 전체 | 15.199543 |
| 요청 출력 복사 | 0.722795 |
| PS gather + scatter | 1.002013 |
| 바깥 루프·타이머 등 잔여 | 0.681984 |
| 전체 | 18.136318 |

ioctl 내부는 kernel copy-in 0.283016 + submit/start 2.939423 + 완료 wait 9.406124 +
상태/카운터 check 0.654666 + copy-out 0.721195 + 잔여 1.195118 ms다.
submit은 채널 준비·제출·시작을, wait는 DMA 완료·IRQ·재스케줄링을 포함한다.
이 항목을 위 ioctl 전체와 다시 더하지 않는다. 각 프로파일 행의 계층 합과 유한값도 검사했다.

PL active 평균은 4.482577 ms다. 모든 행에서 active − input stall − output stall은
861 cycles/FFT로 같으며, 256회/50 MHz 환산은 4.408320 ms다.
추가 스트림 정지는 평균 약 0.074257 ms이고 output backpressure는 0이었다.
861사이클은 입력 LOAD/출력 staging을 포함한 코어 구간이며 순수 butterfly 계산만이 아니다.
PL active는 ioctl/wait와 겹친다. wait에서 PL active를 뺀 값을 정확한 IRQ 비용으로 해석하지 않는다.

## 해석과 다음 변경

샘플별 MMIO 병목은 줄었지만 작은 FFT마다 256번 반복하는 제출·완료 처리·소유권 전환 비용이
남아 있다. 스트림 정지의 규모는 작고 gather/scatter도 약 1 ms다. 현 단계에서는 코어를
여러 개로 늘리기 전에 **E11b: 제출 단위를 축당 128 FFT로 묶는 변경**을 분리 측정하는 근거가 된다.
한 ioctl만 묶고 내부에서 매 FFT의 DMA 제출/IRQ를 그대로 반복하면 고정 비용이 충분히 줄지
않을 수 있다. E11b는 ioctl 횟수와 DMA 제출/완료 단위를 각각 명시해 확인해야 한다.
코어·50 MHz·Q15·출력 2클록/sample은 유지하고, 외부 ping-pong·출력 스케줄 개선은 섞지 않는다.

고정 프레임의 warm-cache 지연이다. 연속 UDP 처리량이나 실시간 보장이 아니며,
현재 지연 15.412 ms는 명목 입력 프레임 간격 12.8 ms보다 길다.
기존 코어의 4.408320 ms 구간만으로도 PS NEON 전체 3.715234 ms보다 길므로 E11b만으로
PS를 이긴다고 예측하지 않는다. E12/E13 순서는 E11b 프로파일 후 결정한다.

## 원본과 재검증

전체 결과는 ignored `build/fft128_dma_measurements/{profile_e11a_01,results_e11a_01}`에 있다.
보고서에는 시간 CSV·프로파일 CSV·로그·wisdom·환경·artifact/source manifest를 보존했다.
큰 spectrum/input CSV는 build에 두고 `raw_artifact_sha256.json`에 전체 파일 해시를 남겼다.
`comparison.json`, `profile.summary.json`은 재계산 결과이며 분석 소스 해시는
`analysis_source_sha256.json`에 있다. 계측 결과의 비계측 혼입과 1 LSB PL 출력 변조를
거부하는 검사도 통과했다(`analysis_guards.json`).

```sh
python3 benchmarks/compare_dma_board.py build/fft128_dma_measurements/results_e11a_01
python3 src/PS/fft128/dma/analyze_profile.py build/fft128_dma_measurements/profile_e11a_01/pl.profile.csv
```

[Vivado 구현·DT v2 자체 검사와 최초 실패 기록](../2026-11-16-e11a-build/README.md),
[실험 일지](../../../docs/experiment_log.md).
