# FFT128 MMIO 경로: 시간 분해, 파이프라인 코어, 50 MHz 빌드 절차

E09(순차 20 MHz 병목 분해)와 E10(파이프라인 코어·50 MHz)의 **실행 절차**다.
결과와 해석은 [실험 일지](experiment_log.md)의 E09·E10 항목에, 이후 DMA 단계는
[단계별 가속 계획](fft128_dma_plan.md)에 있다.

| 구성 | 비계측 각 300회 중앙값 | 보고서 |
|---|---|---|
| 순차 / 20 MHz / MMIO | PS 5.550 ms, PL 81.460 ms | [E08](../benchmarks/reports/2026-11-15-zybo128/README.md) |
| 순차 / 20 MHz 프로파일 | 계측 평균 83.694257 ms, 3,073 cycles/FFT | [E09](../benchmarks/reports/2026-11-15-serial20-profile/README.md) |
| 파이프라인 / 50 MHz / MMIO | PS 5.557368 ms, PL 25.2591725 ms | [E10 비교](../benchmarks/reports/2026-11-15-pipeline50-benchmark/README.md), [구현](../benchmarks/reports/2026-11-15-pipeline50-build/README.md), [프로파일](../benchmarks/reports/2026-11-15-pipeline50-profile/README.md) |

아래 표의 사이클 환산값은 PL 내부 구간이며 보드 전체 지연으로 쓰지 않는다.

## 1. 기존 펌웨어로 먼저 측정 (FPGA 재빌드 없음)

새 수신기는 기존 순차 펌웨어와 호환된다. Ubuntu 호스트에서 HGFS를 마운트한 사용자로 빌드·배치한다.

```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/benchmarks/build_arm.sh"
bash "$HOME/fmcw_share/FMCW-FFT-test/benchmarks/deploy_board.sh"
```

검증된 순차 20 MHz 펌웨어가 올라가 있는 상태에서 보드에서 실행한다.

```sh
sudo sh /opt/fft128/benchmark/profile_board.sh 20000000
```

워밍업 2회, 계측 프레임 20회를 정수 모델 검증과 함께 실행하고 프레임마다 `.profile.csv`를 남긴다.

| 필드 | 의미 |
|---|---|
| `wall_ms` | 계측된 FFT·전송·전치 전체 |
| `input_write_ms` | idle 확인과 입력 MMIO store 128회, 256 FFT 합 |
| `start_wait_ms` | 시작 명령, 마감 시각 설정, 완료 polling |
| `counter_read_ms` | 프로파일링으로 추가된 사이클 레지스터 읽기 |
| `output_read_ms` | 출력 MMIO 읽기와 작은 계측 bookkeeping |
| `gather_ms`, `scatter_ms` | PS 열 gather와 결과 scatter |
| `pl_cycles` | 256 FFT의 레지스터 0x010 합 |
| `pl_internal_ms` | `pl_cycles * 1000 / declared_clock_hz` |
| `min_cycles`, `max_cycles` | FFT별 카운터 최솟값·최댓값 |

- 하드웨어 카운터는 start가 받아들여진 순간부터 마지막 내부 출력 샘플 저장까지 센다. 입력 적재,
  butterfly 스케줄, 출력 staging을 포함하고 호스트 MMIO는 제외한다. 순수 곱셈·덧셈 시간이 아니다.
- PL 내부 시간은 `start_wait_ms`와 겹치므로 호스트 단계에 다시 더하지 않는다. polling 중 CPU 활동이
  PL 실행과 동시에 일어나므로, 전체에서 PL 내부를 뺀 나머지가 순수 AXI 전송 시간도 아니다.
- 클록 인자는 필수이며 올라간 펌웨어와 같아야 한다. 선언값일 뿐 독립적으로 잰 클록이 아니다.
- 프로파일은 타임스탬프와 MMIO 읽기를 추가한다. PS/PL 성능 비교는 별도 비계측 실행으로 한다.
  비교 분석기는 계측된 PL 실행을 거부한다.

Ubuntu NFS root를 통해 프로파일을 가져온다.

```bash
cp -r /nfsroot/opt/fft128/benchmark/profiles "$HOME/fmcw_share/FMCW-FFT-test/build/fft128_board_benchmark/"
```

개발 PC에서 CSV 하나를 분석한다.

```bash
python benchmarks/analyze_profile.py path/to/profile_YYYYMMDD_HHMMSS.profile.csv
```

## 2. 파이프라인 연산과 stage ping-pong RAM

- `fft128_axi`의 기본값은 `PIPELINED=0`(기존 순차)이다. `PIPELINED=1`은 `fft128_pipeline.v`와
  `butterfly_pipeline.v`를 선택한다. 레지스터 프로토콜, Q15 비트 배치, stage별 /2 절단과 포화는 같다.
- butterfly 데이터 경로는 여전히 하나(실수 곱셈기 4개 병렬)다. 서로 다른 butterfly의 동기 메모리 읽기,
  곱셈, 합/차, 양자화, 목적지 쓰기를 겹친다.
- 두 dual-port bank가 stage마다 source/destination을 교대한다. stage마다 butterfly 64개를 매 클록 하나씩
  발행하고 파이프라인을 비운 뒤 bank를 바꾼다. stage 경계에서 모든 쓰기가 끝난 뒤 다음 stage가 읽는다.
- FFT 여러 개를 동시에 돌리거나 PS MMIO 전송과 연산을 겹치지는 않는다.

PC RTL 테스트는 변형마다 같은 272벡터의 출력 bin 일치, AXI AW/W 독립 타이밍, 응답 지연,
출력 backpressure, 잘못된 TLAST, 계산 중 abort 후 재계산을 확인한다. 카운터 값은 정확히 일치한다.

| 변형 | FFT당 사이클 | 256 FFT @ 20 MHz | 256 FFT @ 50 MHz |
|---|---:|---:|---:|
| 순차 | 3,073 | 39.3344 ms | 15.73376 ms |
| 파이프라인 | 861 | 11.0208 ms | 4.40832 ms |

PL 내부 구간만의 환산이며 호스트 전송·전치 시간은 따로 남는다.

## 3. 50 MHz 파이프라인 빌드

순차 프로파일을 회수한 뒤 Vivado 2022.1 Tcl Console에서 한 번 실행한다.

```tcl
source [file join $env(HOME) fmcw_share FMCW-FFT-test src PL fft128_ps build_fast.tcl]
```

- 파이프라인 코어와 50 MHz MMCM 출력을 선택한다. reset은 검증된 보드 클록/MMCM lock V3 방식을 유지한다.
- 생성 reset IP, routed setup/hold slack, 실제 생성 클록 주기를 검사한 뒤 bitstream을 만든다.
  실패하면 중단하며 타이밍을 무시하고 진행하지 않는다.
- 개발 PC는 Vivado를 실행하지 않는다. PC RTL 통과만으로 50 MHz 구현이나 보드 동작을 보장하지 않는다.

`build.tcl`만 실행하면 순차/20 MHz를 빌드한다. 효과를 분리하려면 Tcl 설정으로 순차/50 MHz,
파이프라인/20 MHz도 만들 수 있다.

```tcl
set ::fft128_build_core serial
set ::fft128_build_mhz 50.0
source [file join $env(HOME) fmcw_share FMCW-FFT-test src PL fft128_ps build.tcl]
unset ::fft128_build_core ::fft128_build_mhz
```

run 디렉터리는 구성마다 분리한다. `clock_source.txt`와 `build_config.json`이 완료된 빌드와 타이밍 제약에서
확인한 주파수를 식별한다.

`FFT128_BUILD_PASS` 뒤에는 기존 `prepare_firmware.sh`와 마운트 사용자 복사 → 로컬 staging → `sudo install`
절차로 새 `.bin`을 `/nfsroot/opt/fft128`에 둔다. 검증된 순차 펌웨어는 별도 파일로 보존한다.
보드에 새 펌웨어를 올리고 하드웨어 자체 검사를 한 뒤 **50000000** Hz로 프로파일한다.
기존 20 MHz 펌웨어에 50 MHz 값을 쓰지 않는다.

마지막으로 비계측 벤치마크를 별도 디렉터리에 실행한다.

```sh
sudo sh /opt/fft128/benchmark/run_board.sh /opt/fft128/benchmark/results_pipeline50
```

디렉터리 전체를 회수해 `compare_board.py`를 다시 실행한다. 순차/20 MHz 보고서와 파이프라인/50 MHz 보고서는
따로 보존하고, 측정값을 사이클 환산값으로 대체하지 않는다.
