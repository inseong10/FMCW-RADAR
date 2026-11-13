# FMCW-RADAR

Zynq 기반 FMCW 레이더 신호처리 시스템. RadarSimPy I/Q 데이터를 Zybo Z7-10(Zynq-7010, PetaLinux)에서 받아 Range-Doppler 처리·타겟 검출 후 콘솔 출력함. 같은 FFT를 PS와 PL에서 각각 수행하고 측정 결과로 처리 분담을 정함.

## 목표

- **연속 프레임 처리**: P99 처리 시간 < 프레임 주기, 드랍 0, 큐 대기 시간 일정
- **정확성**: 검출한 거리·속도가 시뮬레이터 ground truth와 일치
- **측정 기반 파티셔닝**: 입력 크기(chirp·sample 수)별 PS/PL 성능 비교, 효율적인 구조를 정량 제시
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
