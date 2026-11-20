# E13-2core: 기존 FFT 코어 두 개 복제

상태(2026-11-20): RTL·호스트·ARM/Vivado·보드 자체 검사·전체 프레임·별도20회 profile·
각300회 paired 비교 및 원본 독립 검증 PASS. 실제2코어/DSP8개/동시 CALC와50 MHz를 확인했다.
중앙값 PL4.920621 ms/PS double5.767263 ms/NEON3.646212 ms이며 과거 E11b보다 지연23.51% 감소다.
PL active 평균2.857541 ms, 복사합1.320890 ms, PS 전치0.680213 ms다.
[최종 보드 결과·원본](../../../../benchmarks/reports/2026-11-20-e13-2core-board/README.md).

## 변경 범위

기존 `fft128_pipeline` 두 개를 50 MHz로 실행한다. Q15 연산, 버터플라이,
코어 내부 RAM·스케줄과 출력 2 clocks/sample은 E11b 그대로다.
공유 AXIS로 FFT 0을 코어0, FFT 1을 코어1에 입력한다. 코어0 계산과 코어1 입력이
겹치고 두 코어 계산도 겹친다. 출력은 코어0→코어1 순서로 배출한다.
두 출력이 모두 수락된 뒤 다음 두 FFT를 시작하는 pair barrier 구조다.
외부 분배 버퍼, 다음 pair prefetch, E12 ping-pong, E11c 출력 개선은 없다.

축당 128 FFT/64 KiB, 프레임당 2 ioctl/4 DMA 채널 제출, HP0 64-bit,
AXIS 32-bit, Simple DMA/SG off/DRE off/burst16/length17을 유지한다.
PS gather/scatter는 E11b의 `dma_batch/batch_process.c`를 그대로 사용한다.
사용자 cached 배열→커널 cached request→coherent DMA 버퍼 복사도 유지한다.

## 인터페이스·계측

별도 compatible `fmcw,fft128-dma-parallel-v3`, 장치 `/dev/fft128-dma-parallel`,
ID `0x46545082`, ABI3을 사용한다. 고정 크기 헤더112 B, 입력 offset112,
출력 offset65648, request131184 B다. 요청당 FFT 개수1..128과 홀수도 지원한다.

기존 레지스터 0x00..0x2c 뒤에 다음 레지스터를 추가했다.

| Offset | 의미 |
|---|---|
| 0x30 | 코어 수2 |
| 0x34/0x38 | 코어0/1 busy cycles |
| 0x3c | 두 코어 동시 busy cycles |
| 0x40 | 두 코어 동시 work-window cycles |
| 0x44 | 출력 차례를 기다리는 다른 코어의 valid cycles |

work-window는 마지막 입력 handshake 이후부터 첫 출력 valid 전까지다.
CALC와 첫 출력 RAM 읽기 지연을 포함하며 순수 버터플라이 시간은 아니다.
RTL 검증은 별도로 두 코어의 실제 CALC 상태를 직접 확인한다.
work-window와 실제 동시 CALC의 차이는 pair당 최대1cycle이다.
보드 검사는 프레임 work-window가128cycles를 넘어야 통과시켜 초기 출력 읽기
지연만으로 동시 계산을 입증했다고 판단하지 않는다.
global active와 각 코어 busy 합은 중첩되므로 더하지 않는다.
input/output starvation도 서로 다른 lane에서 겹칠 수 있어 합을 빼서
순수 연산 시간으로 부르지 않는다. full frame에서
`global - (core0 + core1 - both_busy) == 128`은 pair 시작 기포 검사다.

## 로컬 검증

저장소 루트에서 실행한다.

```text
python src/PL/fft128_ps/verify_dma_parallel.py
python src/PS/fft128/test_native.py
python src/PS/fft128/dma_batch/test_tools.py
python src/PS/fft128/dma_parallel/test_tools.py
```

272 독립 숫자 벡터/34,816 complex bins, 1/2/3/127/128 FFT 패킷,
AXI AW/W 분리·응답 정지, AXIS 공백·역압·정지 중 payload 안정성,
잘못된 TLAST/TKEEP, 부분 입력·계산·출력 정지 중 abort/recovery,
pair barrier 및 실제 동시 CALC를 검증했다.
숫자 회귀9개, E11b 도구3개, 새 profile export/음성 검증4개 PASS다.

추가 stream 정지 없는 사이클 계산은 pair당1116, 축당71424,
프레임142848 cycles/50 MHz = 2.856960 ms다. E11b 4.408320 ms 대비
약1.543배의 PL 내부 개선 가설이며 전체 프레임·보드 실측값이 아니다.
AXI DMA IP·DDR·IRQ·커널은 로컬 RTL 검증에 포함하지 않는다.

## Vivado와 ARM 빌드

공유 저장소를 사용하는 Ubuntu Vivado Tcl 콘솔에서 실행한다.

```tcl
source /home/user/fmcw_share/FMCW-FFT-test/src/PL/fft128_ps/build_dma_parallel.tcl
```

스크립트는 ARM 수신기/모듈 빌드도 백그라운드로 시작한다.
기존 prepared kernel `/home/user/fft128_kernel_e11a/build`와 캡처한 DT를
사용하며 커널을 설치하거나 FPGA를 프로그래밍하지 않는다.
Vivado 완료 표시는 `FFT128_DMA_PARALLEL_BUILD_PASS`이고 별도 ARM 로그는
`build/fft128_dma_parallel_preparation/arm_build.log`의
`E13_2CORE_ARM_BUILD_PASS`다. 실제 생성 reset IP, setup/hold, 50 MHz와
DSP48E1 8개를 검사한다. 자원 전체는 구현 보고서에서 확인한다.

양쪽 빌드가 통과한 다음 Ubuntu 터미널에서 실행한다.

```bash
root="$HOME/fmcw_share/FMCW-FFT-test"
bash "$root/src/PS/fft128/dma_parallel/prepare_bundle.sh"
bash "$root/src/PS/fft128/dma_parallel/deploy.sh"
```

새 배포는 `/nfsroot/opt/fft128/e13_2core`, 보드에서는
`/opt/fft128/e13_2core`다. E11b 펌웨어·배포·결과는 별도 경로에 보존된다.

## 보드 검증과 측정

E11a/E11b 모듈 또는 이전 overlay가 활성화되어 있으면 보드를 재부팅한 뒤
실행한다. 로더가 활성 DMA/FFT 노드와 모듈을 검사한다. 모듈 CRC 불일치는
강제로 우회하지 않는다.

```sh
sudo sh /opt/fft128/e13_2core/load_board.sh
```

`DMA_E13_2CORE_SELFTEST_READY`까지 확인한다. 1 FFT와 반복128 FFT의
정수 결과, ABI·소유권 검사 및 `PARALLEL_OVERLAP_PASS`가 포함된다.
이후 보드에서 별도 profile과 비계측 paired 비교를 실행한다.

```sh
sudo sh /opt/fft128/e13_2core/profile_board.sh /opt/fft128/e13_2core/profile_e13_2core_01
sudo sh /opt/fft128/e13_2core/run_board.sh /opt/fft128/e13_2core/results_e13_2core_01
```

profile은 warmup2/repeat20, paired 비교는 CPU0/warmup10/repeat100×3,
PS double/NEON/PL 순서를 회전한다. 같은 입력·측정 경계를 유지한다.
paired 실행의 DMA IRQ는 각660회 증가가 기대된다.
각 실행 디렉터리는 새로 만들며 기존 원본을 덮어쓰지 않는다.

Ubuntu에서 회수·독립 검증한다.

```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/src/PS/fft128/dma_parallel/collect_results.sh"
```

정수·NumPy·artifact/source·PS plan·환경·IRQ 검증과 profile의 실제 계산 구간
겹침 검사를 통과한 뒤 성능 결과를 보고한다. 이전 E11b와의 비교는 과거
세션 비교이고, 같은 실행에서 다시 측정한 PS 기준과 구분한다.

[준비 근거](../../../../benchmarks/reports/2026-11-20-e13-2core-preparation/README.md),
[빌드 근거](../../../../benchmarks/reports/2026-11-20-e13-2core-build/README.md),
[실험 일지](../../../../docs/experiment_log.md).
