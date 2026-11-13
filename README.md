# FMCW-RADAR

Zynq 기반 FMCW 레이더 신호처리 시스템. RadarSimPy I/Q 데이터를 Zybo Z7-10(Zynq-7010, PetaLinux)에서 받아 Range-Doppler 처리·타겟 검출 후 콘솔 출력함. 같은 FFT를 PS와 PL에서 각각 수행하고 측정 결과로 처리 분담을 정함.

## 핵심 포인트

### 1. PS-PL 연동

PS 소프트웨어와 PL FFT를 AXI 버스로 연결하고, 두 경로를 런타임에 전환함.

- **데이터 경로**: DDR 프레임 버퍼 → AXI DMA(MM2S) → AXI4-Stream → PL FFT → S2MM → DDR
- **제어 경로**: AXI4-Lite 레지스터로 N_CHIRPS·N_SAMPLES 설정. 비트스트림 재합성 없이 크기 변경
- **흐름 제어**: `TREADY` backpressure, PL 처리 중 프레임은 대기 또는 드랍·기록
- **경로 전환**: 같은 입력을 PS-only / PS+PL로 처리해 결과·성능 비교

### 2. 실험 기반 트레이드오프 조율

감이 아닌 측정으로 PS/PL 분담과 설정을 결정함.

| 트레이드오프 | 변수 | 판단 지표 |
|---|---|---|
| PS vs PL 처리 | 입력 크기(chirp·sample 수) | 처리 시간, 최대 프레임률, CPU 사용률, 교차점 |
| DMA 오버헤드 vs PL 연산 이득 | 프레임 크기, 전송 방식 | end-to-end 지연, 전송 시간 비중 |
| 정밀도 vs 정확도 | int16 스케일 계수 S, 고정소수점 | 검출 거리·속도 오차, 포화 비율 |
| PL 자원 vs 지원 크기 | 최대 N_CHIRPS·N_SAMPLES | LUT·BRAM·DSP 사용량, 타이밍 |
| 실시간성 vs 부하 | 프레임 주기, 부하 주입 | P99 지연, 드랍율, 큐 대기 |

예비 실험(개발 PC): PS Doppler FFT에서 메모리 배치를 바꿔 같은 FFTW plan 기준 512 chirp 이상 약 3.2배, 전체 처리 시간 약 1.7~1.8배 단축 확인. 보드에서 재측정 예정.

## 목표

- **연속 프레임 처리**: P99 처리 시간 < 프레임 주기, 드랍 0, 큐 대기 시간 일정
- **정확성**: 검출한 거리·속도가 시뮬레이터 ground truth와 일치
- **관측 가능성**: 드랍율, CPU·메모리, 지연 상시 계측·기록

## 시스템 구성

```text
PC (tools/sender)  ──UDP──▶  PS (src/PS)  ──AXI DMA──▶  PL (src/PL)
RadarSimPy 시뮬·송신         수신, FFT, CFAR, 계측, 출력   FFT
```

| 경로 | 내용 |
|---|---|
| `tools/sender` | RadarSimPy 시뮬레이션 + UDP 송신 (PC) |
| `src/PS/receiver` | C++ UDP 수신, Range-Doppler FFT(FFTW), wisdom |
| `src/PS/receiver/reference` | Python 참조 수신기 (결과 비교용) |
| `src/PL/fft32-dit-butterfly` | 32-point DIT FFT Verilog (외부 저장소 서브모듈, 참고용) |

## 인터페이스

### PC → PS (UDP)

chirp 1개 = 데이터그램 1개. 헤더 28바이트 + payload, 모두 big-endian.

| 필드 | 형식 | 값 |
|---|---|---|
| magic / version / type | 4s / u8 / u8 | `RSPY` / 1 / 1 |
| channel | u16 | 채널 번호 |
| chirp index / count | u32 / u32 | chirp 번호 / 프레임의 chirp 수 |
| sample count | u32 | chirp당 샘플 수 |
| sample rate | f64 | Hz |
| payload | f32 × 2 × samples | I, Q 교차 |

frame ID 없음. 한 번에 프레임 하나만 보냄.

### PS → PL (AXI4-Stream, 초안)

| 항목 | 규칙 |
|---|---|
| 데이터 | 32비트, 1 beat = 복소 샘플 1개. `[15:0]` I, `[31:16]` Q, int16 2의 보수 |
| 변환 | PS가 계수 S 곱한 뒤 반올림·int16 포화. 창함수·정규화 없음 |
| 순서 | chirp 우선. `TLAST`는 프레임 마지막 beat에서만 1 |
| 크기 | N_CHIRPS × N_SAMPLES beat. 프레임당 AXI DMA(MM2S) 1회 |
| 가변 크기 | AXI4-Lite 레지스터로 전달, 다음 프레임부터 적용. 재합성 없이 변경 가능해야 함 |
| 흐름 제어 | `TREADY` backpressure 허용. PL 처리 중이면 PS가 대기 또는 드랍·기록 |
| 미정 | 2의 거듭제곱 아닌 크기(N_SAMPLES = 160)의 zero-padding 위치 (OPEN-02) |

PL 내부 처리·출력 포맷·레지스터 맵은 PL 담당이 정함.
