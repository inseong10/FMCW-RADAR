# FMCW-RADAR

Zynq 기반 FMCW 레이더 신호처리 시스템: 시뮬레이터 입력 실시간 파이프라인과 PS/PL 파티셔닝 최적화

RadarSimPy로 생성한 I/Q raw 데이터를 Zybo Z7-10(Zynq-7010, PetaLinux)에서 받아 Range-Doppler 처리와
타겟 검출을 수행하고, 결과를 프레임 주기에 맞춰 콘솔에 출력하는 시스템을 만듭니다.
같은 FFT를 PS(ARM)와 PL(FPGA)에서 각각 수행하고, 측정 결과로 처리 분담을 결정합니다.

- **PS**: 소프트웨어 전체 (데이터 수신, DMA 제어, PS FFT, CFAR, 성능 계측, 콘솔 출력)
- **PL**: FFT 구현. PS와의 경계는 PS-PL 입력 인터페이스 명세로 합의합니다.

## 목표

1. **연속 프레임 처리**: 프레임이 큐에 쌓이지 않고 프레임 주기 안에 처리됩니다.
   P99 처리 시간 < 프레임 주기, 드랍 0, 장시간 실행에서 큐 대기 시간이 일정해야 합니다.
2. **정확성**: 검출한 타겟의 거리·속도가 시뮬레이터 ground truth와 일치해야 합니다.
3. **측정 기반 파티셔닝**: 입력 크기(chirp·sample 수)를 바꿔 가며 PS/PL 처리 성능을 비교하고,
   어떤 조건에서 어떤 구조가 효율적인지 정량적으로 제시합니다.
4. **관측 가능한 시스템**: 드랍율, CPU·메모리 사용량, 지연을 상시 계측하고 기록합니다.

## 시스템 구성

```text
 PC                         Zybo Z7-10 (Zynq-7010)
┌──────────────────┐  UDP  ┌───────────────────────────────┐ AXI DMA ┌──────────────┐
│ tools/sender     │ ────▶ │ PS (ARM, PetaLinux)           │ ──────▶ │ PL (FPGA)    │
│ RadarSimPy 시뮬  │       │ 수신 → Range/Doppler FFT      │ ◀────── │ FFT          │
│ I/Q 프레임 송신  │       │ → 검출 → 콘솔 출력, 성능 계측 │         │              │
└──────────────────┘       └───────────────────────────────┘         └──────────────┘
```

## 저장소 구조

```text
src/
  PS/
    receiver/              C++ UDP 수신기와 Range-Doppler 처리 (FFTW)
      reference/           같은 처리를 하는 Python 참조 수신기 (결과 비교용)
      wisdom/              프레임 크기별 FFTW wisdom
  PL/
    fft32-dit-butterfly/   32-point radix-2 DIT FFT Verilog 설계 (서브모듈, 참고용)
tools/
  sender/                  RadarSimPy 시뮬레이션 + UDP 송신기 (PC에서 실행)
```

## 진행 상황

| 단계 | 내용 | 상태 |
|---|---|---|
| M0 계측 기반 | PetaLinux 측정 도구 확인, 드랍율·CPU·메모리 모니터링(FrameMonitor, ResourceSampler), 타임스탬프 CSV 기록 | 예정 |
| M1 PS-only 파이프라인 | PC→보드 프레임 수신, PS FFT(Range·Doppler), CFAR, 콘솔 출력까지 end-to-end | 진행 중: 단일 프레임 UDP 수신과 Range-Doppler FFT, 피크 검출을 개발 PC에서 동작 확인. 연속 프레임, CFAR, 보드 이식은 남음 |
| M2 병목 분석 | 단계별 처리 시간, 큐 대기, 자원 사용 측정. PS FFT 최적화(NEON, 고정소수점) | 진행 중: 단계별 처리 시간 계측과 Doppler 메모리 배치 최적화 완료(개발 PC 기준). NEON·고정소수점은 남음 |
| M3 PL 통합 | PS-PL 인터페이스 명세 합의, AXI DMA 경로, PL FFT 연동, PS/PL 경로 전환 | 인터페이스 초안 작성. PL FFT는 참고 설계만 연결 |
| M4 비교·정리 | 입력 크기 스윕, 프레임 주기 스윕, 부하 주입 실험, 전/후 비교와 문서화 | 예정 |

검증은 RadarSimPy 시나리오의 ground truth와 검출 결과 비교(정확성), 프레임 주기 대비 지연·드랍·데드라인 미스
측정(연속 처리)으로 수행합니다.

## 인터페이스

### PC → PS: UDP 프레임 (현재 구현)

chirp 1개를 UDP 데이터그램 1개로 보냅니다.

| 필드 | 형식 | 내용 |
|---|---|---|
| magic | 4 bytes | `RSPY` |
| version | uint8 | 1 |
| message type | uint8 | 1 (baseband) |
| channel | uint16 | 채널 번호 |
| chirp index | uint32 | 프레임 안에서 chirp 번호 |
| chirp count | uint32 | 프레임의 chirp 수 |
| sample count | uint32 | chirp당 샘플 수 |
| sample rate | float64 | 샘플링 주파수 (Hz) |
| payload | float32 × 2 × sample count | I, Q 순서로 교차 배치 |

헤더는 28바이트이고, 헤더와 payload 모두 big-endian입니다.
프로토콜에 frame ID가 없으므로 한 번에 프레임 하나만 보냅니다.

### PS → PL: AXI4-Stream 입력 (명세 초안)

- **형식:** AXI4-Stream 32비트, 1 beat = 복소 샘플 1개입니다. `TDATA[15:0]`는 I, `TDATA[31:16]`은 Q이고, 각각 int16 2의 보수입니다.
- **정수 변환:** PS가 고정 계수 S를 곱하고 반올림한 뒤 int16 범위로 포화합니다. 창함수나 정규화는 PS가 적용하지 않습니다.
- **순서:** chirp 우선입니다. chirp 0의 sample 0부터 N_SAMPLES−1까지 보낸 뒤 chirp 1을 보냅니다. `TLAST`는 프레임의 마지막 beat에서만 1입니다.
- **프레임 크기:** N_CHIRPS × N_SAMPLES beat, 즉 4 × N_CHIRPS × N_SAMPLES 바이트입니다. DDR 버퍼 1개를 AXI DMA(MM2S) 전송 1회로 보냅니다.
- **가변 크기:** N_CHIRPS와 N_SAMPLES는 프레임 사이에서만 바뀝니다. PS가 AXI4-Lite 설정 레지스터에 쓰면 다음 프레임부터 적용되며, 비트스트림 재합성 없이 바꿀 수 있어야 합니다.
- **흐름 제어:** PL은 `TREADY`로 backpressure를 걸 수 있습니다. PL이 이전 프레임을 처리 중이면 PS가 대기하거나 드랍하고 드랍 수를 기록합니다.
- **미정 사항(OPEN-02):** N_SAMPLES = 160처럼 2의 거듭제곱이 아닌 크기를 어느 쪽에서 zero-padding할지 협의가 필요합니다.

PL 내부 처리, 출력 포맷, 레지스터 맵 세부는 PL 담당이 정합니다.

## 빠른 시작 (개발 PC)

서브모듈까지 받으려면 다음처럼 클론합니다.

```bash
git clone --recurse-submodules https://github.com/inseong10/FMCW-RADAR.git
```

수신기를 빌드하고 실행합니다. FFTW3 배정밀도 런타임이 필요합니다.

```bash
cd src/PS/receiver
clang++ -O3 -std=c++17 -Wall -Wextra udp_radar_receiver.cpp -o receiver_cpp
./receiver_cpp --bind 127.0.0.1 --port 5000 --wisdom-in wisdom/wisdom_160x160.wis
```

다른 터미널의 저장소 루트에서 송신기를 실행합니다.

```bash
python tools/sender/sender.py --ip 127.0.0.1 --port 5000 --pulses 160
```

빌드 옵션과 계측 항목, wisdom 사용법은 [src/PS/receiver/README.md](src/PS/receiver/README.md)를 참고하세요.

### 시뮬레이션 조건 (송신기 기본값)

| 항목 | 값 |
|---|---|
| 주파수 스윕 | 24.0 → 24.1 GHz (대역폭 100 MHz) |
| chirp 길이 / PRP | 80 µs / 100 µs |
| 샘플링 주파수 | 2 MHz (chirp당 160 샘플) |
| chirp 수 | 160 (`--pulses`로 변경) |
| 타겟 | 30 m, -10 m/s, RCS 10 dBsm |

## 외부 구성요소

- **RadarSimPy:** 독점 라이선스라 저장소에 포함하지 않습니다. `tools/sender/radarsimpy/`에 두거나 설치해서 사용합니다. 개발에는 15.5.0을 사용했습니다.
- **FFTW 3:** 수신기가 실행 시 동적으로 불러옵니다.
- **32-point FFT Verilog:** [AhmedAalaaa/32-point-FFT-Verilog-design-based-DIT-butterfly-algorithm](https://github.com/AhmedAalaaa/32-point-FFT-Verilog-design-based-DIT-butterfly-algorithm)을 서브모듈로 참조합니다.
  32점 고정 크기 설계라서, 런타임에 크기를 바꾸는 이 저장소의 PS-PL 입력 명세를 그대로 만족하지는 않습니다.

## 한계

- 실제 RF 하드웨어가 아닌 시뮬레이션 입력을 사용하며, Linux 위의 soft real-time 처리입니다.
- 입력부만 교체하면 실제 센서로 확장할 수 있는 구조를 목표로 합니다.
