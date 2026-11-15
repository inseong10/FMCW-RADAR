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

감이 아닌 측정으로 PS/PL 분담과 설정을 결정함.

| 트레이드오프 | 변수 | 판단 지표 |
|---|---|---|
| PS vs PL 처리 | 입력 크기(chirp·sample 수) | 처리 시간, 최대 프레임률, CPU 사용률, 교차점 |
| DMA 오버헤드 vs PL 연산 이득 | 프레임 크기, 전송 방식 | end-to-end 지연, 전송 시간 비중 |
| 정밀도 vs 정확도 | int16 스케일 계수 S, 고정소수점 | 검출 거리·속도 오차, 포화 비율 |
| PL 자원 vs 지원 크기 | 최대 N_CHIRPS·N_SAMPLES | LUT·BRAM·DSP 사용량, 타이밍 |
| 실시간성 vs 부하 | 프레임 주기, 부하 주입 | P99 지연, 드랍율, 큐 대기 |

예비 실험(개발 PC): PS Doppler FFT에서 메모리 배치를 바꿔 같은 FFTW plan 기준 512 chirp 이상 약 3.2배, 전체 처리 시간 약 1.7~1.8배 단축 확인. 보드에서 재측정 예정.

## 현재 확인 상태

128 samples × 128 chirps의 PS/PL 기능 실험은
[실행 절차](src/PL/fft128_ps/README.md)를 참고합니다. 단일 128포인트 복소 FFT를 재사용하고,
PS DDR에서 전치하며 AXI4-Lite로 전송합니다. RTL·PC UDP 모델 검증,
Vivado bitstream 생성·20 MHz 타이밍 검사와 실제 Zybo 보드 검증을 완료했습니다.
보드용 수신기는 C 실행 파일로 제공하며 Python 없이 기존 TFTP·NFS 부팅 환경에 배치할 수 있습니다.

2026-11-15 동일 보드·동일 입력 비교(각 방식 300회)에서 최적화된 PS C++/FFTW의
중앙값은 **5.550 ms**, PL MMIO 경로는 **81.460 ms**였습니다. 현재 PL 경로가 약 14.68배
느리며, DMA는 아직 사용하지 않습니다. 측정에는 FFT 두 축과 전치·전송을 포함하고
UDP·파일 입출력·할당·검증을 제외했습니다. PL은 정수 모델과 모든 bin이 일치했고,
NumPy 대비 상대 L2 오차는 1.361%였습니다. PS는 double, PL은 Q15 연산입니다.
[측정 조건과 원시 시간 기록](benchmarks/reports/2026-11-15-zybo128/README.md),
[재현 절차](benchmarks/README.md)를 참고하세요.


## 목표

- **연속 프레임 처리**: P99 처리 시간 < 프레임 주기, 드랍 0, 큐 대기 시간 일정
- **정확성**: 검출한 거리·속도가 시뮬레이터 ground truth와 일치
- **관측 가능성**: 드랍율, CPU·메모리, 지연 상시 계측·기록

## 시스템 구성

```text
PC (tools/sender)  ──UDP──▶  PS (src/PS)  ──AXI4-Lite──▶  PL (src/PL)
RadarSimPy 시뮬·송신         수신, 전치, 검증, 계측, 출력  FFT
```

| 경로 | 내용 |
|---|---|
| `tools/sender` | RadarSimPy 시뮬레이션 + UDP 송신 (PC) |
| `src/PS/receiver` | C++ UDP 수신, Range-Doppler FFT(FFTW), wisdom |
| `src/PS/fft128` | native C 수신기, MMIO, 반복 측정, 정수 기준 모델 |
| `src/PL/fft128_ps` | 검증된 128-point RTL, Vivado 빌드, 클록·리셋, 테스트벤치 |
| `src/PL/zybo_fft_test` | 이전 32-point 보드 자체 검사 |
| `benchmarks` | ARM 빌드·보드 배치·실행·분석, 입력 fixture, 측정 보고서 |
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

### PS → PL (AXI4-Stream, 향후 DMA 초안)

현재 검증된 AXI4-Lite 경로는 [128-point 레지스터 계약](src/PL/fft128_ps/README.md)을 사용하며,
FFT당 128개 샘플을 전송하고 PS가 전치함. 아래 전체 프레임 계약과 구분함.

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


## 빠른 시작 (개발 PC)

서브모듈까지 받으려면 다음처럼 클론합니다.

```bash
git clone --recurse-submodules https://github.com/inseong10/FMCW-RADAR.git
```

아래 명령은 저장소 루트에서 실행합니다. Python 의존성을 먼저 설치합니다.

```bash
python -m pip install -r requirements.txt
```

Linux/macOS/WSL에서는 CMake와 C++17 컴파일러, FFTW3 배정밀도 런타임으로 C++ 수신기를 실행합니다.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
./build/udp_radar_receiver --bind 127.0.0.1 --port 5000
```

Windows 네이티브 환경에서는 Python 참조 수신기를 사용할 수 있습니다.

```powershell
python src/PS/receiver/reference/receiver_numpy.py --bind 127.0.0.1 --port 5000 --warmup 0 --repeat 1
```

송신기는 [tools/sender/README.md](tools/sender/README.md)를 따라 운영체제와 Python 버전에 맞는
RadarSimPy 패키지를 `tools/radarsimpy/`에 둡니다. `--check-simulator`로 로드를 확인할 수 있습니다.

다른 터미널의 저장소 루트에서 송신기를 실행합니다.

```bash
python tools/sender/sender.py --ip 127.0.0.1 --port 5000 --pulses 160
```

빌드 옵션과 계측 항목, wisdom 사용법은 [src/PS/receiver/README.md](src/PS/receiver/README.md)를 참고하세요.


## 외부 구성요소

- **RadarSimPy:** 로컬 패키지는 `tools/radarsimpy/`에 두며 바이너리는 Git에서 제외합니다. 다른 경로는 `--radarsimpy-path`, `RADARSIMPY_PATH` 또는 `tools/sender/radarsimpy.local.json`으로 지정할 수 있습니다. 개발에는 15.5.0을 사용했습니다.
- **FFTW 3:** 수신기가 실행 시 동적으로 불러옵니다.
- **32-point FFT Verilog:** [AhmedAalaaa/32-point-FFT-Verilog-design-based-DIT-butterfly-algorithm](https://github.com/AhmedAalaaa/32-point-FFT-Verilog-design-based-DIT-butterfly-algorithm)을 서브모듈로 참조합니다.
  32점 고정 크기 설계라서, 런타임에 크기를 바꾸는 이 저장소의 PS-PL 입력 명세를 그대로 만족하지는 않습니다.

## 검증과 실험

```bash
python -m unittest discover -s src/PS/receiver/tests -v
```

Python 검증에는 RadarSimPy가 필요하지 않습니다. `build/udp_radar_receiver`가 있으면
C++ 오프라인 재생 결과도 NumPy와 비교하며, 없으면 해당 검증만 skip됩니다.
참조 수신기 자체는 자동 테스트가 아닙니다. 실험 절차는 [benchmarks/README.md](benchmarks/README.md)를 참고하세요.

## 한계

- 실제 RF 하드웨어가 아닌 시뮬레이션 입력을 사용하며, Linux 위의 soft real-time 처리입니다.
- 입력부만 교체하면 실제 센서로 확장할 수 있는 구조를 목표로 합니다.
