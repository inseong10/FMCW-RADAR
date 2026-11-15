# PS01: double / float scalar / float+NEON

상태: **2026-11-16 각 300회 원본·정확도·설정 검증 완료**.
전체 중앙값은 double 5.502540 / float scalar 4.341573 / float+NEON 3.615852 ms다.
[최종 보드 보고서](../reports/2026-11-15-ps01-board/README.md).
FPGA는 E10 그대로 둔다. 이 실험은 PL/MMIO를 접근하거나 bitstream을 만들지 않는다.
목표는 DMA 설계 전에 같은 Zybo의 PS 기준을 강화하는 것이다.

## 고정 조건과 변경

기존 `udp_radar_receiver.cpp`의 32×32 tiled transpose, contiguous Doppler,
단일 스레드, CPU0, preallocated FFTW 버퍼/plan을 유지한다. 같은 소스를 세 번 빌드한다.

| 변형 | 작업 버퍼/산술 | FFTW | 자동 벡터화 |
|---|---|---|---|
| double | float64 | 기존 libfftw3, ARMv7 double scalar | 기존 -O3 |
| float_scalar | float32 | libfftw3f, --disable-neon | 라이브러리·수신기 모두 끔 |
| float_neon | float32 | libfftw3f, --enable-neon | 라이브러리·수신기 모두 끔; FFTW의 명시적 NEON codelet 사용 |

float 두 변형의 차이는 FFTW NEON codelet의 활성화다. 수신기 자동 벡터화까지 동시에
바꾸지 않는다. 따라서 이번 float_neon이 가능한 모든 PS 최적화의 최종 한계라는 뜻은 아니다.
FFTW 3.3.11의 같은 pinned source, Cortex-A9 hard-float flags, no fast-math를 쓴다.
기존 double FFTW 빌드/실행 명령의 기본값은 유지한다.
[FFTW single/NEON 공식 설명](https://www.fftw.org/fftw3_doc/Installation-on-Unix.html).

정확한 [고정 입력](../fixtures/README.md)을 float64로 복원한 뒤 기존과 동일한 Q15
양자화를 한다. Q15 정수는 float32에도 정확히 표현된다. 창 없음, 전체 정규화 1/16384다.
작업 버퍼·전치·정규화는 선택한 정밀도를 사용하고, 양자화 스케일과 기준 검증은 double이다.

## Ubuntu에서 빌드·배치

HGFS를 마운트한 일반 사용자로 실행한다. ARM g++/gcc, make, Python3+NumPy가 필요하다.
세 FFTW 라이브러리를 처음 빌드하는 작업은 시간이 걸릴 수 있다. FPGA 합성은 하지 않는다.

```bash
P="$HOME/fmcw_share/FMCW-FFT-test"
bash "$P/benchmarks/ps_precision/build_arm.sh"
bash "$P/benchmarks/ps_precision/deploy.sh"
```

첫 줄 성공 표시 `PS_PRECISION_BUILD_PASS`를 확인한 뒤 배치한다.
빌드는 `build/fft128_ps_precision/`에만, 배치는 별도
`/nfsroot/opt/fft128/ps_precision/`에 한다. 기존 benchmark·펌웨어·실행 파일은 보존한다.
coherent 버퍼나 DMA 드라이버는 이 단계에서 필요하지 않다.

## PetaLinux 보드에서 측정

아래는 보드 명령이다. `/opt` 아래 새 결과 디렉터리를 만들기 위해 sudo를 쓴다.
이미 존재하는 결과 디렉터리는 덮어쓰지 않는다. 재실행 때 새 이름을 지정한다.

```sh
sudo sh /opt/fft128/ps_precision/run_board.sh /opt/fft128/ps_precision/results_ps01
```

기본 워밍업 10회/측정 100회/3 trial이다. trial마다
double→scalar→NEON / scalar→NEON→double / NEON→double→scalar 순서로 바뀐다.
각 변형의 MEASURE wisdom은 보드에서 별도로 만들며 계획 생성은 측정 밖이다.
NEON plan이 실제 선택되지 않거나 수치 검증에 실패하면 즉시 중단한다.

성능과 별개로 빠른 진단만 하려면 새 결과 이름으로 아래를 쓸 수 있다.

```sh
sudo env FFT128_REPEAT=2 FFT128_WARMUP=1 FFT128_TRIALS=1 sh /opt/fft128/ps_precision/run_board.sh /opt/fft128/ps_precision/smoke_ps01
```

이 결과는 300회 성능 결과로 해석하지 않으며 분석 때 `--smoke`가 필요하다.
보드에는 Python이나 시스템 FFTW 설치가 필요 없다.

## 측정 범위·정확도

- 비교할 항목은 CSV의 **fft_pipeline**이다. 입력 작업 버퍼 복사, 두 축 FFT,
  전치, 정규화를 포함한다. 기존 내부 단계 타이머 bookkeeping도 포함한다.
- UDP·파일 I/O·입력 양자화·할당·계획·워밍업·축/피크 계산·수치 검증은 제외한다.
  콘솔의 `FFT only`는 두 축 FFT만의 진단값이며 주 비교값으로 쓰지 않는다.
- PC에서 NumPy float64 기준을 만들고, 보드 C++가 **매 측정 반복 후 16,384 bins**를
  비교한다. float64는 최대 복소 오차 ≤1e-7 Q15 LSB 및 상대 L2 ≤1e-12,
  float32는 각각 ≤0.01 Q15 LSB 및 ≤1e-5로 측정 전에 고정했다.
  PL의 단계별 정수 정규화와 float FFT는 서로 bit-exact를 요구하지 않는다.
- 마지막 출력 CSV도 PC에서 독립적으로 NumPy와 비교하고 피크를 확인한다.
  `PS_VERIFY_PASS`는 반복 수·전체 bin 수·최악 오차를 기록한다.
- 매 반복 검증은 타이밍 밖이지만 캐시 상태에 영향을 줄 수 있으므로 **새 double도 함께
  재측정**한다. float의 가속비를 과거 E10 double 시간만으로 계산하지 않는다.
- sha256 manifest를 배치 전후와 보드 실행 전에 검증한다. 결과에는 실행 파일·라이브러리·
  입력·기준 해시, 컴파일 flags, 실제 FFTW plan, wisdom, CPU 정보와 원시 시간이 남는다.

## Ubuntu에서 결과 수집·분석

```bash
P="$HOME/fmcw_share/FMCW-FFT-test"
cp -r /nfsroot/opt/fft128/ps_precision/results_ps01 "$P/build/fft128_ps_precision/"
python3 "$P/benchmarks/ps_precision/analyze.py" "$P/build/fft128_ps_precision/results_ps01"
```

`comparison.json`에 각 300회 통계와 double/NEON, scalar/NEON 중앙값 비율을 저장한다.
입력·정확도·CPU affinity·wisdom·반복 수·NEON plan·manifest가 맞지 않으면 성공 보고서를
만들지 않는다. 복사 경로가 읽기 제한인 경우 기존처럼 로컬 폴더에 먼저 수집한다.
정식 원본이 수집되기 전에는 보드 성능 수치를 채워 넣지 않는다.

로컬 검증:

```bash
python3 -m unittest discover -s benchmarks/ps_precision -p test_precision.py -v
```

NumPy oracle·분석기의 잘못된 입력/누락 검출과 실제 C++ 수치 검증기를 두 정밀도로
검사한다. Windows의 이 검증은 Linux 전체 실행 파일이나 ARM NEON 실행 검증을 대신하지 않는다.

추가 Windows 수치 smoke는 `host_smoke.py`로 실제 수신기의 FFTW ABI·오프라인 복원·
처리·검증 코드를 추출해 실행한다. 공식 FFTW 3.3.5 DLL을 쓰는 별도 검사이며,
ARM용 3.3.11·NEON·소켓·CPU affinity 검증이 아니다. DLL과 생성 실행 파일은 ignored build에
두고 수치 결과만 [준비 기록](../reports/2026-11-15-ps01-preparation/README.md)에 보존한다.
