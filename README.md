# FMCW-RADAR

Zynq 기반 FMCW 레이더 신호처리 시스템. RadarSimPy I/Q 데이터를 Zybo Z7-10(Zynq-7010, PetaLinux)에서 받아 Range-Doppler 처리·타겟 검출 후 콘솔 출력함. 같은 FFT를 PS와 PL에서 각각 수행하고 측정 결과로 처리 분담을 정함.

## 핵심 포인트

### 1. PS-PL 연동

현재 128×128 고정 크기의 PS C++/FFTW 경로와 PS 구동 PL MMIO 경로를 각각 실행해 비교함.
아래 DMA·가변 크기·통합 경로 전환은 다음 단계의 목표임.

- **데이터 경로**: DDR 프레임 버퍼 → AXI DMA(MM2S) → AXI4-Stream → PL FFT → S2MM → DDR
- **제어 경로**: AXI4-Lite 레지스터로 N_CHIRPS·N_SAMPLES 설정. 비트스트림 재합성 없이 크기 변경
- **흐름 제어**: `TREADY` backpressure, PL 처리 중 프레임은 대기 또는 드랍·기록
- **경로 전환**: 같은 입력을 PS-only / PS+PL로 처리해 결과·성능 비교

### 2. 실험 기반 트레이드오프 조율

측정으로 PS/PL 분담과 설정을 결정

| 트레이드오프 | 변수 | 판단 지표 |
|---|---|---|
| PS vs PL 처리 | 입력 크기(chirp·sample 수) | 처리 시간, 최대 프레임률, CPU 사용률, 교차점 |
| DMA 오버헤드 vs PL 연산 이득 | 프레임 크기, 전송 방식 | end-to-end 지연, 전송 시간 비중 |
| 정밀도 vs 정확도 | int16 스케일 계수 S, 고정소수점 | 검출 거리·속도 오차, 포화 비율 |
| PL 자원 vs 지원 크기 | 최대 N_CHIRPS·N_SAMPLES | LUT·BRAM·DSP 사용량, 타이밍 |
| 실시간성 vs 부하 | 프레임 주기, 부하 주입 | P99 지연, 드랍율, 큐 대기 |


## 목표

- **연속 프레임 처리**: P99 처리 시간 < 프레임 주기, 드랍 0, 큐 대기 시간 일정
- **정확성**: 검출한 거리·속도가 시뮬레이터 ground truth와 일치
- **관측 가능성**: 드랍율, CPU·메모리, 지연 상시 계측·기록

## 시스템 구성

```text
PC (tools/sender)  ──UDP──▶  PS (src/PS)  ──AXI4-Lite──▶  PL (src/PL)
RadarSimPy 시뮬·송신         수신, 전치, 검증, 계측, 출력  FFT
```

