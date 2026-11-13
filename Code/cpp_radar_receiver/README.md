# C++ UDP Radar Receiver

기존 RSPY v1 송신기와 호환되는 한 채널/한 프레임 수신기입니다.
C++17 / Linux 또는 macOS / FFTW3 배정밀도 런타임이 필요합니다.
Windows에서는 WSL Ubuntu를 사용하세요. 네이티브 Windows 빌드는 지원하지 않습니다.

## 빌드

### macOS

```bash
brew install fftw
clang++ -O3 -std=c++17 -Wall -Wextra udp_radar_receiver.cpp -o udp_radar_receiver
```

### Ubuntu / Debian / WSL

```bash
sudo apt update
sudo apt install g++ libfftw3-double3
 g++ -O3 -std=c++17 -Wall -Wextra udp_radar_receiver.cpp -o udp_radar_receiver -ldl
```

FFTW는 실행 시 동적으로 불러옵니다. 개발용 헤더는 필요하지 않습니다.
기본 경로에서 찾지 못한다면 `--fftw-lib /absolute/path/to/libfftw3.dylib`
또는 `--fftw-lib /absolute/path/to/libfftw3.so.3`을 추가하세요.
FFTW 자체는 패키지 관리자로 설치하며 이 압축 파일에 포함되지 않습니다.

## 실행

먼저 수신기를 실행하세요.

```bash
./udp_radar_receiver --bind 127.0.0.1 --port 5000 --warmup 5 --repeat 100
```

그다음 별도 터미널에서 기존 송신기를 실행하세요.

```bash
python radarsimpy/udp_radar_sender.py --ip 127.0.0.1 --port 5000 --pulses 160
```

`--repeat 100`은 수신한 동일 프레임의 처리를 100회 반복하여 단계별 평균을
표시합니다. 네트워크로 100프레임을 수신하는 옵션이 아닙니다.
기존 Python의 단일 처리 측정과 비교하려면 `--repeat 1`을 사용하세요.
반복 처리 수치는 캐시가 데워진 상태의 처리량에 가깝습니다.

```bash
./udp_radar_receiver --bind 127.0.0.1 --port 5000 --warmup 5 --repeat 1
```

더 많은 초기 계획 탐색을 허용하려면 `--measure-plan`을 추가하세요.
기본값은 FFTW_ESTIMATE이며, FFTW_MEASURE 모드는 시작 시 계획 생성에
더 오래 걸릴 수 있습니다. 계획 생성 시간은 따로 출력하고 처리 시간에서 제외합니다.

## FFTW wisdom으로 계획 고정

FFTW_MEASURE는 실행할 때마다 다른 계획을 고를 수 있습니다.
저장해 둔 wisdom을 쓰면 실행마다 같은 계획을 쓰고, 시작 시 측정도 하지 않습니다.

```bash
./receiver_cpp --wisdom-in wisdom/wisdom_160x160.wis --bind 127.0.0.1 --port 5000
```

wisdom 파일은 프레임 크기(`chirps x samples`)별로 하나씩 사용합니다.
적용되면 `FFTW WISDOM`으로 표시합니다. 파일에 해당 크기의 계획이 없으면 경고를 출력하고
`--measure-plan` 지정 여부에 따라 FFTW_MEASURE 또는 FFTW_ESTIMATE로 계획합니다.
파일을 읽을 수 없거나 FFTW 빌드와 맞지 않으면 오류로 종료합니다.

`select_wisdom.py`는 후보 wisdom을 만든 뒤 새 프로세스에서 다시 측정해 가장 빠른 것을 저장합니다.

```bash
python select_wisdom.py --input frame.bin --candidates 10 --rounds 5
```

`wisdom/`의 파일은 이 PC의 FFTW 3.3.11로 만들었습니다.
PC나 FFTW 빌드, 프레임 크기가 바뀌면 다시 만드세요.

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

## CSV 출력

```bash
./udp_radar_receiver --bind 127.0.0.1 --output spectrum.csv
```

CSV 열: `doppler_bin_unshifted,range_bin,real,imag`
내부 Doppler 버퍼는 전치되어 있지만 CSV는 기존과 같은 chirp 우선 순서로 저장합니다.
FFTW forward FFT의 정규화 없는 복소수 출력이며 Doppler 축은 fftshift 이전 순서입니다.
Python에서 다음처럼 읽습니다.

```python
import numpy as np
rows = np.loadtxt('spectrum.csv', delimiter=',', skiprows=1)
pulses = int(rows[:, 0].max()) + 1
samples = int(rows[:, 1].max()) + 1
rd = (rows[:, 2] + 1j*rows[:, 3]).reshape(pulses, samples)
rd_shifted = np.fft.fftshift(rd, axes=0)
```

## 검증

빌드 후 실행하세요. RadarSimPy는 필요하지 않습니다.

```bash
pip install numpy
python test_receiver.py
```

검증 범위: 160×160과 홀수 크기 배열의 전체 FFT 결과 NumPy 비교,
Hann/none, FFTW_ESTIMATE/MEASURE, 패킷 재정렬·중복·잘못된 데이터·다른 채널,
알려진 거리/Doppler bin, 누락 timeout.
이 결과는 정확성 검증이며 다른 PC의 NumPy 실행보다 빠르다는 보장은 아닙니다.

FFTW API 참고: https://www.fftw.org/doc/Advanced-Complex-DFTs.html
