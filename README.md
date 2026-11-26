# FMCW RADAR

Zynq 기반 FMCW 레이더 신호처리 시스템. RadarSimPy I/Q 데이터를 Zybo Z7-10(Zynq-7010, PetaLinux)에서 받아 Range-Doppler 처리·타겟 검출 후 콘솔 출력함. 같은 FFT를 PS와 PL에서 각각 수행하고 측정 결과로 처리 분담을 정함.

## 핵심 포인트

### 1. PS-PL 연동

128×128 고정 크기의 PS C++/FFTW와 PS 구동 PL FFT를 보드에서 비교함.
최신 PL 구성은 단일 DMA와 전용 7단계 스트리밍 FFT를 재사용하며, 두 축 사이 전치와 최종 배열 복원을 PL에서 처리함.
초기 MMIO 기준선은 PS DDR → AXI4-Lite MMIO → PL FFT → MMIO → PS DDR로 이동하고,
두 FFT 축 사이의 전치/gather는 PS에서 처리함. 단일 128-point 코어를 재사용함.

**E12·E13 완료:** 2·4코어 복제, 코어별 FIFO 입출력 겹치기, 코어당 버터플라이 2개,
전용 7단계 프레임 스트리밍을 순서대로 구현하고 보드 원본 검증을 마침.
**E14 완료:** 64KiB in-place 행렬로 중간 결과를 PL에 보관해 CPU 전치와 중간 DDR 왕복을 제거함.
프레임당 1 ioctl·2채널·입출력 합128KiB이며 최초 입력·최종 출력의 coherent 복사는 유지함.
최신 구성의 각300회 중앙값은 PL **1.658ms** / 같은 회차 PS double **5.707ms** /
NEON **3.489ms**로, NEON 대비 지연이 **52.49% 짧음**(2.105배).
RTL·host53개·ARM/Vivado·보드 자체 검사·20회 profile·paired 원시 검증을 완료함.
가변 크기·연속 UDP 처리량은 아직 검증하지 않음.
[최신 결과·정확도·시간 분해](benchmarks/reports/2026-11-21-e14-frame-board/README.md),
[빌드·보드 실행](src/PS/fft128/dma_frame/README.md), [단계별 이력](docs/experiment_log.md).

- **데이터 경로**: DDR 프레임 버퍼 → AXI DMA(MM2S) → AXI4-Stream → PL FFT → S2MM → DDR
- **제어 경로 목표**: AXI4-Lite 레지스터로 N_CHIRPS·N_SAMPLES 설정. 비트스트림 재합성 없이 크기 변경
- **흐름 제어**: `TREADY` backpressure, PL 처리 중 프레임은 대기 또는 드랍·기록
- **경로 전환**: 같은 입력을 PS-only / PS+PL로 처리해 결과·성능 비교

### 2. 실험 기반 트레이드오프 조율

측정으로 PS/PL 분담과 설정을 결정

| 트레이드오프 | 변수 | 판단 지표 |
|---|---|---|
| PS vs PL 처리 | 입력 크기(chirp·sample 수) | 처리 시간, 최대 프레임률, CPU 사용률, 교차점 |
| DMA 오버헤드 vs PL 연산 이득 | 프레임 크기, 전송 방식 | end-to-end 지연, 전송 시간 비중 |
| 정밀도 vs 정확도 | ADC16 고정 스케일 S=1,600,000 codes/unit(profile1), 고정소수점 | 검출 거리·속도 오차, 포화 비율 |
| PL 자원 vs 지원 크기 | 최대 N_CHIRPS·N_SAMPLES | LUT·BRAM·DSP 사용량, 타이밍 |
| 실시간성 vs 부하 | 프레임 주기, 부하 주입 | P99 지연, 드랍율, 큐 대기 |

새 시스템 입력은 ADC 모사 고정 이득 int16 IQ다. ADC 변환은 측정 밖, Hann과 PS int16→double 변환은 수신기 안이다.
기존 float 입력 실험은 보존하며, [S2a-int16 검증](benchmarks/reports/2026-11-26-s2a-int16/README.md)과
[Ubuntu·보드 실행 순서](docs/adc16_runbook.md)를 별도 기록한다. 스케일 스윕은 후속 실험으로 분리한다.


## 목표

- **연속 프레임 처리**: P99 처리 시간 < 프레임 주기, 드랍 0, 큐 대기 시간 일정
- **정확성**: 검출한 거리·속도가 시뮬레이터 ground truth와 일치
- **관측 가능성**: 드랍율, CPU·메모리, 지연 상시 계측·기록

## 시스템 구성

UDP 수신까지 검증한 기존 MMIO 경로:

```text
PC (tools/sender)  ──UDP──▶  PS (src/PS)  ──AXI4-Lite──▶  PL (src/PL)
RadarSimPy 시뮬·송신         수신, 전치, 검증, 계측, 출력  FFT
```

E11b에서는 같은 기록 프레임을 보드에서 읽어 다음 경로를 검증·측정함. DMA 경로의 연속 UDP 처리는 아직 미검증임.

```text
PS cached frame → coherent TX → HP0/AXI DMA → PL FFT → DMA/coherent RX → PS
Range FFT 128개 묶음 → PS gather/scatter → Doppler FFT 128개 묶음
제어: GP0/AXI4-Lite, 축당 ioctl 하나 (프레임당 2회)
```

후속 가속은 [단계별 가속 계획](docs/fft128_dma_plan.md)을 따름.
PS float/NEON 기준과 DMA 전환·묶음 제출을 측정했고, 출력 개선은 분리함.
전송/연산 겹치기와 연산 병렬화 순서는 DMA 프로파일 결과로 선택함.
[PS01](benchmarks/reports/2026-11-15-ps01-board/README.md)의 각 300회 원본 검증을 완료함.
복사·전치·정규화를 포함한 전체 중앙값은 double **5.503 ms** / float scalar **4.342 ms** /
float+NEON **3.616 ms**임. NEON 변형은 새 double보다 1.522배 빠르고 정확도 기준을 통과함.

## 현재 측정 결과

Zybo Z7-10에서 같은 128×128 Q15 입력, CPU0, 비계측 각 300회 FFT 전체 경로 중앙값임.
FFT 두 축·필요한 복사·전송·전치·배열 복원을 포함하고 UDP·파일 I/O·할당·검증은 제외함.

| 구성 | PS C++/FFTW double | PS float+NEON | PL 경로 |
|---|---:|---:|---:|
| 순차/20 MHz + MMIO | 5.550 ms | — | 81.460 ms |
| 파이프라인/50 MHz + MMIO | 5.557 ms | — | 25.259 ms |
| E11a 파이프라인/50 MHz + DMA | 5.748 ms | 3.715 ms | 15.412 ms |
| E11b 파이프라인/50 MHz + 축당 DMA | 5.717 ms | 3.558 ms | 6.433 ms |
| E13-2core/50 MHz + 축당 DMA | 5.767 ms | 3.646 ms | 4.921 ms |
| E13-4core/50 MHz + 축당 DMA | 5.768 ms | 3.650 ms | 4.186 ms |
| E12-4core/50 MHz + FIFO overlap | 5.712 ms | 3.489 ms | 3.129 ms |
| E13-bf2/50 MHz + 코어당2 butterfly | 5.708 ms | 3.520 ms | 2.842 ms |
| E13-stream/50 MHz + 전용7단계 | 5.826 ms | 3.653 ms | 2.787 ms |
| E14-frame/50 MHz + PL 전치·최종 배열 복원 | 5.707 ms | 3.489 ms | **1.658 ms** |
| E14-clock/100 MHz + 같은 E14 회로 | 5.632 ms | 3.563 ms | **1.125 ms** |

최신100MHz 회차에서 CPU 설정은 전후 약666.67MHz로 같았으며 PL은 NEON 대비 **3.168배** 빠름.
원본83개·반복별 정확성·배포 신원·IRQ·클럭을 검증함.100MHz는 사용자가 선택한 비교 클럭임.

E10에서 PL은 이전보다 3.225배 개선됐지만 당시 PS double보다 4.545배 느렸음. 매 반복 16,384 bin이
정수 모델과 일치했고, 저장 출력의 NumPy 대비 상대 L2 오차는 1.361%임.
[E10 결과](benchmarks/reports/2026-11-15-pipeline50-benchmark/README.md),
[최신100MHz 결과·조건·원시 시간 CSV](benchmarks/reports/2026-11-26-e14-clock/README.md),
[기존50MHz 결과](benchmarks/reports/2026-11-21-e14-frame-board/README.md),
[변경 이유와 실험 일지](docs/experiment_log.md), [벤치마크 재현 절차](benchmarks/README.md)를 참고함.

## 코드와 실행 안내

### PS / PL 시각화 대시보드

`python tools/dashboard/server.py --open` 또는 Windows의
`tools/dashboard/run_dashboard.bat`로 로컬 대시보드를 실행합니다.
기준 프레임의 PS·PL 히트맵과 오차, 단계별 처리 구조, 기존 보드 성능 기록을 볼 수 있습니다.
합성 표적 / 프로젝트 RadarSimPy 입력 생성과 PS·PL CSV 가져오기도 지원합니다.
새 입력의 PL 결과는 소프트웨어 모델이며 보드 실측과 구분합니다.
[실행·데이터 출처·CSV 형식](tools/dashboard/README.md).

| 경로 | 내용 |
|---|---|
| [tools/sender](tools/sender/README.md) | PC RadarSimPy 입력 생성·UDP 송신/재생 |
| [src/PS/receiver](src/PS/receiver/README.md) | C++/FFTW 수신기·전치 최적화·개발 PC 실행 |
| [src/PS/fft128](src/PS/fft128/) | 보드용 native C 수신기·MMIO·정수 모델 |
| [src/PL/fft128_ps](src/PL/fft128_ps/README.md) | 128-point RTL·Vivado 빌드·보드 실행 |
| [benchmarks](benchmarks/README.md) | ARM 빌드·배치·측정·검증·보고서 |

UDP는 chirp당 데이터그램 하나, big-endian 28-byte 헤더와 float32 I/Q payload임.
frame ID가 없어 현재는 한 번에 한 프레임만 보냄.
현재 MMIO·DMA 계약과 향후 가변 크기 초안은 [인터페이스 문서](docs/interfaces.md)를 참고함.

검증 범위는 시뮬레이션 입력·고정 128×128·캐시가 데워진 오프라인 반복 지연임.
실제 RF, 연속 프레임 처리량·실시간 보장, ACP, 가변 크기는 아직 검증하지 않음.
PS float/NEON의 전체 경로 통계·정확도·실제 NEON plan은 독립 검증했으며,
E11a/E11b에서 PL과 같은 실행 조건의 paired 비교도 완료함.
