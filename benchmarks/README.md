# 재현 가능한 벤치마크

실험의 문제·변경·결과 경과와 실패 기록은 [실험 일지](../docs/experiment_log.md)에 있다.
이 문서는 측정 도구의 위치와 실행 절차를 정리한다. 명령은 저장소 루트에서 실행한다.

## 측정 보고서와 재계산

| 실험 | 내용 | 보고서 | 원본 재계산 |
|---|---|---|---|
| E08 | PS double 대 순차 PL MMIO | [2026-11-15-zybo128](reports/2026-11-15-zybo128/README.md) | `python benchmarks/compare_board.py build/fft128_board_benchmark/results` |
| E10 | PS double 대 파이프라인 50 MHz MMIO | [2026-11-15-pipeline50-benchmark](reports/2026-11-15-pipeline50-benchmark/README.md) | 같은 분석기, `results_pipeline50` |
| PS01 | PS double / float scalar / float+NEON | [2026-11-15-ps01-board](reports/2026-11-15-ps01-board/README.md) | [PS01 절차](ps_precision/README.md) |
| E11a | FFT당 DMA | [2026-11-16-e11a-board](reports/2026-11-16-e11a-board/README.md) | `python3 benchmarks/compare_dma_board.py build/fft128_dma_measurements/results_e11a_01` |
| E11b | 축당 묶음 DMA | [2026-11-19-e11b-board](reports/2026-11-19-e11b-board/README.md) | `python benchmarks/compare_dma_batch_board.py build/fft128_dma_batch_measurements/results_e11b_01` |
| E13-2core | 기존 코어 2개, pair barrier | [완료 보고서](reports/2026-11-20-e13-2core-board/README.md) | `python benchmarks/compare_dma_parallel_board.py build/fft128_dma_parallel_measurements/results_e13_2core_01` |
| E13-4core | 기존 코어 4개, group barrier | [완료 보고서](reports/2026-11-20-e13-4core-board/README.md) | `python benchmarks/compare_dma_quad_board.py build/fft128_dma_quad_measurements/results_e13_4core_01` |
| E12-4core | 4코어, FIFO·독립 스케줄 | [완료 보고서](reports/2026-11-20-e12-4core-board/README.md) | `python benchmarks/compare_dma_overlap_board.py build/fft128_dma_overlap_measurements/results_e12_4core_01` |
| E13-bf2 | 4코어, 코어당 버터플라이 2개 | [완료 보고서](reports/2026-11-21-e13-bf2-board/README.md) | `python benchmarks/compare_dma_bf2_board.py build/fft128_dma_bf2_measurements/results_e13_bf2_01` |
| E13-stream | 전용 7단계 프레임 스트리밍 | [완료 보고서](reports/2026-11-21-e13-stream-board/README.md) | `python benchmarks/compare_dma_stream_board.py build/fft128_dma_stream_measurements/results_e13_stream_01` |
| E14-frame | PL 전치·최종 배열 복원, 전체 프레임 DMA | [완료 보고서](reports/2026-11-21-e14-frame-board/README.md) | `python benchmarks/compare_dma_frame_board.py build/fft128_dma_frame_measurements/results_e14_frame_01` |

- E14-frame은 자체 검사·20회 profile·각300회 paired와 원시 결과 검증을 완료했다. 중앙값1.657914ms, 같은 회차 NEON 대비2.104718배다.
- 각 DMA 구성의 빌드·배치·실행·회수는 `src/PS/fft128/dma_<구성>/README.md`에 있다. 최신 보드 검증 [전체 프레임 절차](../src/PS/fft128/dma_frame/README.md).
- 20회 계측 프로파일은 진단용이며 비계측 300회 표본에 합치지 않는다.
- 공유 절차와 스크립트는 Git으로 추적한다. `data/`(원시·패킷 입력)와 `results/`(CSV·그림)는 로컬 전용이다.
- 측정마다 OS, CPU, 컴파일러와 flags, FFTW 버전, 창, 크기, warmup, repeat 수, wisdom 사용 여부를 기록한다.
- MMIO 프로파일과 50 MHz 빌드 절차는 [FFT128 MMIO 절차](../docs/fft128_optimization.md)에 있다.

## 개발 PC: 합성 프레임으로 수신기 실행

Linux/macOS/WSL에서 C++ 수신기를 빌드한 뒤 실행한다.

```bash
python benchmarks/make_frame.py --pulses 160 --samples 160
mkdir -p benchmarks/results
./build/udp_radar_receiver --input benchmarks/data/frame.bin --warmup 5 --repeat 100 --timings benchmarks/results/timings.csv --output benchmarks/results/spectrum.csv
python src/PS/receiver/select_wisdom.py --input benchmarks/data/frame.bin
```

- `make_frame.py`는 NumPy만 필요하다. range bin 3, Doppler bin -2(크기에 대한 나머지)의 합성 톤을 만든다.
  물리적인 레이더 표적을 시뮬레이션하지 않는다.
- 패킷 컨테이너는 `RSPB0001` 뒤에 big-endian uint32 패킷 길이와 RSPY UDP 패킷 전체가 반복된다.
  오프라인 재생은 같은 프레임을 반복하므로 처리·재생 비용을 재며 연속 UDP 성능이 아니다.
- PC 실시간 확인은 [송신기 안내](../tools/sender/README.md)의 Windows 시뮬레이터와 `receiver_numpy.py`를 쓴다.
  시나리오 파라미터를 기록하고 검출한 거리·속도를 ground truth와 비교한다.

## Zybo Z7-10: 최적화 PS FFTW 대 128×128 PL (MMIO)

E08/E10의 절차다. 검증된 V3 bitstream을 쓰므로 Vivado 재빌드가 필요 없다. 두 프로그램 모두 같은 보드에서
같은 RadarSimPy 기록 프레임을 처리한다. PS는 기존 `udp_radar_receiver.cpp`(32×32 타일 전치, 연속 Doppler FFT,
재사용 FFTW 버퍼·plan), PL은 AXI4-Lite MMIO(DMA 아님)다. 입력 fixture는 `benchmarks/fixtures/`에 추적되어
배치가 `build/`의 미추적 기록에 의존하지 않는다.

**공통 조건:** 같은 Q15 양자화 입력, 창 없음, 전체 1/16384 정규화. FFTW는 double, PL은 Q15로 계산한다.
PS 출력은 내부적으로 range-major, PL 출력은 row-major이며 두 CSV는 타이머 밖에서 같은 논리 행렬로 저장된다.
정밀도가 다른 구현 비교이며 같은 부동소수점 하드웨어를 주장하지 않는다.

**측정 구간(`fft_pipeline`):** PS는 입력 복사·Range FFT·타일 전치·Doppler FFT·출력 정규화,
PL은 MMIO 전송·두 축 FFT·PS gather/scatter. 두 경로 모두 작업 버퍼를 미리 할당하고
UDP/파일 입력·양자화·plan 생성·워밍업·정확도 검사·피크/축 계산·파일 출력을 제외한다.
PS 단계 프로파일은 파이프라인 안에 타이머 bookkeeping을 더한다.

1. **대상 확인 (Ubuntu):** NFS rootfs와 컴파일러를 확인한다.

   ```bash
   bash "$HOME/fmcw_share/FMCW-FFT-test/benchmarks/check_target.sh"
   ```

   C++ 프로그램은 ARM32 Linux loader/libc와 호환되는 double FFTW 런타임 `libfftw3.so.3`이 필요하다.
   C++/GCC 런타임은 빌드 스크립트가 정적으로 링크한다. 부동소수점 ABI와 libc를 맞추고, Ubuntu x86 FFTW를
   보드 rootfs에 설치하지 않는다. 이 보드는 ARMv7 ELF32 hard-float(`/lib/ld-linux-armhf.so.3`)이며
   FFTW와 taskset이 없었다. Ubuntu에는 ARM GCC 9.4가 있지만 ARM C++ 컴파일러가 필요하다.

   ```bash
   sudo apt update
   sudo apt install g++-arm-linux-gnueabihf make curl
   ```

2. **빌드·배치 (Ubuntu, HGFS 마운트 사용자):**

   ```bash
   bash "$HOME/fmcw_share/FMCW-FFT-test/benchmarks/build_arm.sh"
   bash "$HOME/fmcw_share/FMCW-FFT-test/benchmarks/deploy_board.sh"
   ```

   - 검증된 펌웨어와 수신기는 `/opt/fft128/`에 그대로 두고 벤치마크 파일은 `/opt/fft128/benchmark/`에 둔다.
   - `build_arm.sh`는 `build_fftw_arm.sh`를 호출한다. `build/third_party`의 공식 FFTW 3.3.11 압축 파일을
     SHA256으로 확인하고(없으면 fftw.org에서 받아 확인), ARMv7 hard-float double 단일 스레드 FFTW를
     `$HOME/fft128_fftw_arm`에 빌드해 `lib/libfftw3.so.3`을 준비한다.
   - 배치는 이 라이브러리를 벤치마크 디렉터리에 설치하며 시스템 `/lib`, `/usr/lib`는 건드리지 않는다.
     C++ 프로그램은 `--fftw-lib` 경로로 연다. 컴파일러 flags, 소스 SHA256, 라이브러리 ABI·심볼을 기록한다.
   - `--with-slow-timer`는 ARM PMU 접근을 가정하지 않는 plan 측정용이며 벤치마크 측정 구간에는 영향이 없다.
     ARMv7 NEON은 double SIMD가 없어 이 double 빌드에서는 NEON codelet을 켜지 않는다(float NEON은 PS01).
   - 공식 자료: [FFTW 다운로드](https://www.fftw.org/download.html), [빌드 옵션](https://www.fftw.org/fftw3_doc/Installation-on-Unix.html).

3. **보드 실행 (V3 펌웨어가 올라간 상태):**

   ```bash
   sudo sh /opt/fft128/benchmark/run_board.sh
   ```

   - CPU preflight가 이 보드에서 128×128 FFTW MEASURE wisdom을 만들고, 이후 모든 PS trial이 이를 쓴다.
     plan마다 약 10초 제한이 있으며 plan 생성은 측정 밖이다.
   - 두 프로그램 모두 `sched_setaffinity`(`--cpu0`)로 CPU0에 고정하므로 taskset이 필요 없다. 고정에 실패하면 종료한다.
   - 기본값: warmup 10, repeat 100, PS/PL 3쌍, 같은 프레임. PL은 매 반복 타이머 밖에서 정수 모델과 비교한다.
   - CPU 주파수/governor는 읽을 수 있을 때 기록하며 바꾸지 않는다. 다시 실행하면 같은 결과 이름을 덮어쓴다.

4. **회수·분석:** Ubuntu에서 NFS root를 통해 회수한다.

   ```bash
   mkdir -p "$HOME/fmcw_share/FMCW-FFT-test/build/fft128_board_benchmark/results"
   cp -r /nfsroot/opt/fft128/benchmark/results/. "$HOME/fmcw_share/FMCW-FFT-test/build/fft128_board_benchmark/results/"
   ```

   개발 PC(NumPy 필요)에서 분석한다.

   ```bash
   python benchmarks/compare_board.py build/fft128_board_benchmark/results
   ```

   분석기는 모든 출력 bin을 NumPy와 비교하고, 입력 설정 일치와 실제 PL_MMIO 증거를 확인한 뒤
   중앙값·평균·p05·p95를 계산한다. 가속비는 PS 중앙값 / PL 중앙값이며 1보다 작으면 PL이 느리다는 뜻이다.
   불완전하거나 소프트웨어 모델뿐인 PL 결과는 거부한다. 같은 프레임 반복 지연은 연속 UDP 처리량과 다르다.
