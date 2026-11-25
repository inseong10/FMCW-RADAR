# C++ UDP Radar Receiver

기존 RSPY v1 송신기와 호환되는 한 채널/한 프레임 수신기입니다.
C++17 / Linux 또는 macOS / FFTW3 배정밀도 런타임이 필요합니다.
Windows에서는 WSL Ubuntu를 사용하세요. 네이티브 Windows 빌드는 지원하지 않습니다.

## 빌드

아래 명령은 모두 저장소 루트에서 실행합니다. Python 코드에는 `requirements.txt`를 사용합니다.

```bash
python -m pip install -r requirements.txt
```

macOS에서는 `brew install cmake fftw`, Ubuntu/WSL에서는
`sudo apt install cmake g++ libfftw3-double3`로 빌드 도구와 런타임을 준비합니다.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
```

실행 파일은 `build/udp_radar_receiver`로 통일합니다. FFTW는 실행 시 동적으로 불러오므로
개발용 헤더는 필요하지 않습니다. 기본 경로에서 찾지 못한다면
`--fftw-lib /absolute/path/to/libfftw3.dylib` 또는
`--fftw-lib /absolute/path/to/libfftw3.so.3`을 추가하세요.

## 실행

먼저 수신기를 실행하세요.

```bash
./build/udp_radar_receiver --bind 127.0.0.1 --port 5000 --warmup 5 --repeat 100
```

그다음 별도 터미널의 저장소 루트에서 송신기를 실행하세요.
RadarSimPy의 운영체제별 외부 경로 설정은 [송신기 설명](../../../tools/sender/README.md)을 참고하세요.

```bash
python tools/sender/sender.py --ip 127.0.0.1 --port 5000 --pulses 160
```

`--repeat 100`은 수신한 동일 프레임의 처리를 100회 반복하여 단계별 평균을
표시합니다. 네트워크로 100프레임을 수신하는 옵션이 아닙니다.
기존 Python의 단일 처리 측정과 비교하려면 `--repeat 1`을 사용하세요.
반복 처리 수치는 캐시가 데워진 상태의 처리량에 가깝습니다.

```bash
./build/udp_radar_receiver --bind 127.0.0.1 --port 5000 --warmup 5 --repeat 1
```

더 많은 초기 계획 탐색을 허용하려면 `--measure-plan`을 추가하세요.
기본값은 FFTW_ESTIMATE이며, FFTW_MEASURE 모드는 시작 시 계획 생성에
더 오래 걸릴 수 있습니다. 계획 생성 시간은 따로 출력하고 처리 시간에서 제외합니다.

## FFTW wisdom으로 계획 고정

FFTW_MEASURE는 실행할 때마다 다른 계획을 고를 수 있습니다.
저장해 둔 wisdom을 쓰면 실행마다 같은 계획을 쓰고, 시작 시 측정도 하지 않습니다.

```bash
./build/udp_radar_receiver --wisdom-in build/wisdom/linux-armv7l/wisdom_160x160.wis --bind 127.0.0.1 --port 5000
```

wisdom 파일은 프레임 크기(`chirps x samples`)별로 하나씩 사용합니다.
적용되면 `FFTW WISDOM`으로 표시합니다. 파일에 해당 크기의 계획이 없으면 경고를 출력하고
`--measure-plan` 지정 여부에 따라 FFTW_MEASURE 또는 FFTW_ESTIMATE로 계획합니다.
파일을 읽을 수 없거나 FFTW 빌드와 맞지 않으면 오류로 종료합니다.

`select_wisdom.py`는 후보 wisdom을 만든 뒤 새 프로세스에서 다시 측정해 가장 빠른 것을 저장합니다.

```bash
python src/PS/receiver/select_wisdom.py --input benchmarks/data/frame.bin --candidates 10 --rounds 5
```

`wisdom/legacy-fftw-3.3.11/`의 기존 파일은 생성 CPU·OS 정보가 없어 참고용으로 보관합니다.
새 wisdom과 JSON 환경 정보는 `build/wisdom/<os>-<architecture>/`에 생성합니다.
위 `--wisdom-in` 경로는 해당 ARM 환경에서 직접 생성한 파일이 있을 때만 사용하세요.
PC나 FFTW 빌드, 프레임 크기가 바뀌면 다시 만드세요. [상세 기준](wisdom/README.md)

## 처리 구조와 비교 조건

- RSPY 헤더 28바이트 + big-endian float32 I/Q 데이터를 해석합니다.
- chirp index 순서로 재조립하고, 중복은 무시하며 누락은 timeout으로 알립니다.
- FFTW의 단일 스레드 배정밀도 복소수 FFT를 사용합니다. SIMD는 사용될 수 있습니다.
- Range: 길이 samples인 FFT를 pulses개 실행합니다.
- Doppler: 길이 pulses인 FFT를 samples개 실행합니다.
  Doppler 윈도우 단계에서 32×32 tile 단위로 전치하므로 각 FFT는 연속 메모리를 처리합니다.
  전치 비용은 `doppler_window`에 포함됩니다.
- 예: (160,160)이면 160점 FFT 320개입니다.
- FFT 버퍼와 계획은 반복 처리 동안 재사용합니다.
- Hann 윈도우를 기본으로 사용합니다. `--window none`으로 끌 수 있습니다.
- 기존 Python 코드는 complex64 프레임에 float64 윈도우를 곱해 complex128로
  연산하므로, 이 C++ 구현도 double로 계산합니다. UDP 원본 정밀도는 float32입니다.
- 피크 탐색은 fftshift 복사 없이 제곱 크기를 비교합니다.
- Python과 달리 전체 거리/속도 축 배열은 생성하지 않고 피크 좌표만 계산합니다.
  따라서 `axis_calculation`과 `postprocess`의 작업량은 Python과 다릅니다.
- 전체 처리 시간을 비교하면 언어, FFT 라이브러리, 버퍼 재사용, 후처리 변경의
  효과가 함께 포함됩니다. 동일한 PC에서 실행해 비교하세요.

## 시간 및 CPU 사용률

Wall avg(ms): 해당 단계의 누적 경과 시간 / 실행 횟수.
CPU avg(ms): 해당 단계의 누적 CPU 시간 / 실행 횟수.
CPU(%): 누적 CPU 시간 / 누적 경과 시간 × 100.

- 수신 표의 socket_wait/decode/reassembly는 **패킷당 평균**입니다.
  예전 Python 표의 수신 하위 단계는 160패킷의 합계였으므로 직접 비교하지 마세요.
  이 C++ 표에서 합계는 평균 × Calls입니다.
- 처리 표는 **프레임 처리 1회당 평균**입니다.
- 기본 CPU clock은 수신 프로세스 전체입니다.
  `--thread-cpu`를 사용하면 호출 스레드만 측정합니다.
- CPU 100%는 논리 코어 1개입니다. 시스템 전체 평균 사용률이 아닙니다.
- total 행은 하위 행과 중첩되므로 더하지 마세요.
- FFT only는 두 FFT 실행 구간의 합계이며, 윈도우 적용은 제외합니다.
- `fft_pipeline`은 입력 복사·Range FFT·타일 전치·Doppler FFT 및 선택적 정규화를 포함하며,
  피크 탐색과 좌표 계산은 제외합니다. PS/PL 처리 경로 비교에는 이 구간을 사용합니다.
- allocation, window 생성, 계획 생성, warmup, 출력, 파일 저장은 processing_total에서 제외합니다.
- receive_total에는 첫 패킷 대기가 포함됩니다.
- 매우 짧은 단계는 타이머 호출 비용 및 CPU clock 해상도의 영향을 받습니다.
  반복 횟수를 늘려도 개별 구간마다 계측하는 비용은 남습니다.
- process CPU time은 같은 PC의 별도 송신 프로세스 CPU 시간을 포함하지 않습니다.

## 옵션

```text
--bind 0.0.0.0         수신 인터페이스
--port 5000           수신 포트
--channel 0           수신 채널
--source-ip IP        송신 IPv4 필터
--timeout 15          수신 전체 제한 시간(초)
--max-frame-mb 128    재조립 프레임의 double complex 메모리 한도(MiB)
--warmup 5            처리 전 FFT 워밍업 횟수
--repeat 1            수신한 동일 프레임의 처리 반복 횟수
--window hann         hann 또는 none
--measure-plan        FFTW_MEASURE 계획 사용
--wisdom-in PATH      저장된 FFTW wisdom을 불러와 계획 고정
--wisdom-out PATH     계획 생성 후 FFTW wisdom 저장
--thread-cpu          현재 스레드 CPU clock 사용
--q15-input           측정 전 입력을 PL과 동일한 Q15 정수 값으로 양자화
--normalize-output    FFT 결과를 pulses×samples로 나눔; fft_pipeline 시간에 포함
--cpu0                Linux sched_setaffinity로 CPU 0에 고정; taskset 불필요
--plan-time-limit SEC FFTW 계획 탐색 시간의 대략적인 상한(계획별)
--fftw-lib PATH       FFTW 동적 라이브러리 경로
--bandwidth-mhz 100   주파수 스윕 대역폭
--chirp-us 80         chirp 길이
--prp-us 100          chirp 시작 간격
--fc-ghz 24.05        속도 환산 중심 주파수
--output spectrum.csv FFT 결과 CSV 저장
```

총 메모리는 프레임 외에 FFT 버퍼 4개 등이 추가로 필요합니다.
max-frame-mb는 전체 프로세스 메모리 제한이 아닙니다.
송신 헤더에는 PRP/대역폭/중심 주파수가 없으므로 송신기 설정이 바뀌면 옵션도 맞추세요.
거리 값은 Doppler 결합 보정 전의 겉보기 거리입니다.
속도 부호는 I/Q 규약에 따라 알려진 표적 방향과 대조하세요.
프로토콜에 frame ID가 없으므로 실행 중 여러 시뮬레이션을 겹쳐 보내지 마세요.
수신기는 완료 후 종료합니다. 한 번 실행할 때 채널 하나만 처리합니다.

## S1b CA-CFAR (보드 검증 전)

`--cfar ca`로 FFT 뒤에 2D CA-CFAR를 실행하고 `--detections detections.csv`로
최종 반복의 검출 목록을 저장합니다. 기본값은 `--cfar none`입니다.
S1a와 같은 guard=(2,2), train=(8,8), Pfa=1e-6, square-law,
Doppler 원형 경계·Range 가용 셀 평균·3×3 지역 최대를 사용합니다.
동일 전력 피크는 Doppler/Range 순서로 보고합니다. 창은 `--window`를 따릅니다.

```bash
./build/udp_radar_receiver --input benchmarks/fixtures/radarsimpy_128x128_sim_multi4_noise.rspb \
  --window hann --cfar ca --detections build/detections.csv --timings build/s1b.timings.csv
```

`cfar` 시간에는 전력 맵 생성·배열 배치 변환·임계값·피크 묶기·정렬이 포함되고
`processing_total`에도 포함됩니다. `fft_pipeline` 범위는 기존과 같습니다.
CFAR 버퍼 할당·계수 준비·CSV 저장은 측정 밖입니다.
검출 CSV 열은 `doppler_bin_unshifted,range_bin,power,threshold,range_m,velocity_mps`입니다.
거리 열은 S1a의 unsigned Range bin 규약을, 속도는 signed Doppler 규약을 사용합니다.

Linux PC에서 잡음 기록 3개 × 창 2개를 FFT·검출 목록·시간 표본까지 검증합니다.

```bash
bash tools/detection/build_s1b.sh host build/s1b_host_build_01
python tools/detection/verify_receiver.py --binary build/s1b_host_build_01/receiver --out build/s1b_host_01
```

ARM Linux 빌드는 Ubuntu에서 `bash tools/detection/build_s1b.sh arm build/s1b_arm_build_01`로
별도 생성합니다. 기본 컴파일러는 `arm-linux-gnueabihf-g++`이며 `S1B_CXX`로 바꿀 수 있습니다.
보드의 glibc·libstdc++ 및 FFTW3와 호환되는 툴체인이 필요합니다.

보드에 Python이 없으면 PC에서 번들을 준비합니다. `run_board.sh`에는 CPU0 고정이 포함됩니다.
새 수신기 실행 파일과 FFTW 라이브러리는 따로 빌드/확보해야 합니다.

```bash
python tools/detection/verify_receiver.py --prepare-only --out build/s1b_board_01 --warmup 10 --repeat 100
# 번들 디렉터리를 보드에 복사한 뒤 보드에서 실행:
sh run_board.sh /absolute/path/to/new/receiver /absolute/path/to/libfftw3.so.3
# 실행 결과를 PC에 회수한 뒤:
python tools/detection/verify_receiver.py --check-only --out build/s1b_board_01
```

원본 IQ·배정밀도 경로를 S1b 기준으로 비교합니다. 현재 S1a `quantize_q15`는
최대 I/Q 성분→32767, 보드/수신기는 최대 복소수 크기→16384로 양자화 규칙이 다릅니다.
Q15 및 Hann의 PL 적용은 S1c에서 맞춰 검증해야 합니다.
이 실행은 같은 프레임 반복이며 S2 연속 UDP 처리량이나 P99 합격 검사가 아닙니다.
S1b 완료 판정에는 보드에서 실제 UDP 수신으로도 같은 검출이 나오는지 확인해야 합니다.

## CSV 출력

```bash
./build/udp_radar_receiver --bind 127.0.0.1 --output spectrum.csv
```

CSV 열: `doppler_bin_unshifted,range_bin,real,imag`
내부 Doppler 버퍼는 전치되어 있지만 CSV는 기존과 같은 chirp 우선 순서로 저장합니다.
FFTW forward FFT의 정규화 없는 복소수 출력이며 Doppler 축은 fftshift 이전 순서입니다.
`--normalize-output`을 지정한 경우에는 pulses×samples로 정규화된 출력입니다.
`--q15-input`은 입력 준비만 Q15로 맞추며 FFTW 산술은 여전히 double입니다.
Python에서 다음처럼 읽습니다.

```python
import numpy as np
rows = np.loadtxt('spectrum.csv', delimiter=',', skiprows=1)
pulses = int(rows[:, 0].max()) + 1
samples = int(rows[:, 1].max()) + 1
rd = (rows[:, 2] + 1j*rows[:, 3]).reshape(pulses, samples)
rd_shifted = np.fft.fftshift(rd, axes=0)
```

## Python 참조 수신기

`reference/receiver_numpy.py`는 UDP 프레임을 받아 NumPy로 처리하는 실행 프로그램입니다.
Windows 네이티브에서도 사용할 수 있으며 C++ 실행 파일이나 RadarSimPy는 필요하지 않습니다.
송신기는 별도 터미널에서 실행하세요. `--plot`을 쓸 때는 matplotlib도 설치합니다.

```bash
python src/PS/receiver/reference/receiver_numpy.py --bind 127.0.0.1 --warmup 0 --repeat 1
```

## 자동 검증

```bash
python -m unittest discover -s src/PS/receiver/tests -v
```

기본 검증은 송신 패킷의 I/Q·엔디언 round-trip, 잘못된 패킷 거부,
알려진 tone의 거리/Doppler bin과 작은 배열의 직접 DFT 비교입니다.
C++ 실행 파일이 있으면 160×160과 홀수 배열, Hann/none 및 ESTIMATE/MEASURE의
오프라인 재생 결과를 NumPy와 비교합니다. 없으면 C++ 검증만 skip됩니다.
실제 UDP 전송, 시뮬레이터 라이선스, 보드 성능은 이 테스트와 별도로 확인해야 합니다.
다른 위치의 C++ 실행 파일은 `RADAR_RECEIVER_BINARY` 환경변수로 지정합니다.

FFTW API 참고: https://www.fftw.org/doc/Advanced-Complex-DFTs.html
