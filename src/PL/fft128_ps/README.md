# Zybo Z7-10: 128 samples × 128 chirps 기능 실험

## 범위와 현재 확인 상태

각 단계의 문제·변경·재검증·남은 항목은 [통합 실험 일지](../../../docs/experiment_log.md)에 기록합니다.
순차 20 MHz와 파이프라인 50 MHz의 보드·프로파일·비계측 비교까지 완료됐습니다.
새 중앙값 PS 5.557 ms / PL 25.259 ms이며 최신 결과는 통합 일지에 연결합니다.

[시간 분해와 파이프라인·50 MHz 실험 절차](../../../docs/fft128_optimization.md):
새 파이프라인은 RTL 검증에서 FFT당 861사이클이며 50 MHz Vivado 타이밍을 통과했습니다.
실제 보드 프레임 검사·861사이클 확인과 각 300회 PS–PL 비교·NumPy 검증도 완료됐습니다.
기본 `build.tcl`은 기존 순차 20 MHz, `build_fast.tcl`은 새 파이프라인 50 MHz를 선택합니다.

2026-11-16 E11a: `build_dma.tcl`과 control/AXIS 앞단을 추가했습니다. 기존 산술·50 MHz는
유지하고 샘플 입출력만 DMA로 바꿉니다. RTL 272벡터/34,816 bin과 스트림 정지·abort 검사는
통과했고 실제 Vivado 50 MHz 구현·보드 DMA ABI/4벡터 자체 검사도 통과했습니다.
전체 프레임·각 300회 비교도 완료했습니다. 중앙값은 PL DMA 15.412 ms / PS NEON 3.715 ms입니다.
[E11a 보드 결과](../../../benchmarks/reports/2026-11-16-e11a-board/README.md)를 참고하세요.
[DMA 드라이버·전용 배치·측정 순서](../../PS/fft128/dma/README.md)를 따릅니다.

PC RadarSimPy → UDP → PS → PL Range FFT → PS DDR 전치 → PL Doppler FFT → PS 저장입니다.
**FFT 두 축의 산술 연산은 PL**이 하고, PS는 수신·Q15 변환·전송·전치·검증을 합니다.
한 개의 128포인트 복소 FFT를 256회 재사용합니다. 프레임 크기는 고정 128×128입니다.

첫 실험은 AXI4-Lite 데이터 창과 `/dev/mem`으로 연동합니다. DMA·연속 프레임·CFAR·실시간
성능 검증은 다음 단계입니다. 기존 32포인트 GitHub 서브모듈과 검증된 비트스트림은 별개로 보존합니다.
보드용 기본 수신기는 **native C 실행 파일**이며 Python이 필요하지 않습니다.
Python 수신기와 NumPy 비교 도구는 PC 참조 또는 선택 실행 경로로 유지합니다.
이 코어는 사용자가 제공한 `Downloads/fmcw_fft/fmcw_fft`의 반복 butterfly 구조를 가져왔습니다.
원본 파일 해시는 `provenance.json`에 기록했습니다.

현재 보드 self-test, UDP 프레임 처리 및 동일 보드 PS–PL 반복 비교는 완료됐습니다.
최초 순차/20 MHz 결과는 PS C++/FFTW 중앙값 5.550 ms, PL MMIO 중앙값 81.460 ms(각 300회)입니다.
[최신 측정 보고서](../../../benchmarks/reports/2026-11-15-zybo128/README.md)를 참고하세요.
아래 날짜·버전별 기록에는 수정 전 실패와 당시의 미확인 상태도 포함됩니다.

2026-11-14 개발 PC 확인:

- Icarus RTL: 16개 스트림 벡터, 출력 backpressure·TLAST 오류·리셋 검사 통과.
- AXI RTL: 272 FFT, 복소수 34,816 bin이 정수 모델과 완전히 일치.
  AW/W 순서 변경, B/R 응답 지연, 잘못된 주소·strobe·busy 쓰기, 미초기화 시작, 리셋 검사 포함.
- 합성된 128×128 복소 tone 프레임: NumPy FFT와 최대 오차 약 5.11 Q15 LSB, 피크 (121,11).
- 실제 Windows RadarSimPy → localhost UDP → **소프트웨어 모델**: 128×128 수신·처리 통과.
  fs=1.6 MHz, 128패킷, 피크 (107,20), NumPy 최대 오차 약 8.75 Q15 LSB.
- 당시 확인 상태: 새 설계의 Vivado 구현·PetaLinux 레시피 빌드·실제 PS MMIO 실행은 미확인.

2026-11-15 최초 PS FCLK0 기반 설계의 Vivado 2022.1 빌드 확인:

- 공유 폴더 `build/vivado/fft128_ps_20261115_184515`에 `.bit`, `system.xsa` 생성 완료.
- 20 MHz에서 setup slack 31.981 ns, hold slack 0.049 ns, 타이밍 위반·미제약 내부 endpoint 없음.
- DSP 4/80, LUT 1,171/17,600, register 908/35,200, BRAM tile 1.5/60.
- 로그에 자식 Vivado 프로세스의 보드 정의 검색 경로 경고 `Board 49-67`과 RAMB 비동기 제어
  DRC 경고가 남아 있음. 실제 보드의 클록·리셋·반복 실행 검증은 아직 남아 있음.
- PetaLinux 레시피 빌드·실제 PS MMIO 검사는 아직 미확인.

이후 현재 보드의 FCLK0 분주 설정이 약 100 MHz이고 Linux FCLK 제어 인터페이스가 없는 것이
확인되어, **K17 보드 클록 125 MHz → Clocking Wizard 20 MHz**로 변경했습니다.
외부 클록 첫 버전 `fft128_ps_20261115_195400`의 빌드는 확인됐습니다.
setup slack 32.953 ns, hold slack 0.009 ns이며 자원은 위와 같습니다.
사용자 콘솔에서 FPGA Manager 다운로드 성공과 `operating`을 확인했으나,
실제 `--self-test`는 BACKEND 출력 전 MMIO 초기화 단계에서 멈췄습니다. **PL 검사는 미통과**입니다.

이 첫 외부 클록 버전은 리셋에 `FCLK_RESET0_N`을 사용한 결함이 있습니다.
[AMD UG585](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/PL-General-Purpose-User-Resets)에 따르면
PS 리셋이 PL로 전달되려면 해당 FCLK가 동작해야 합니다. `FPGA_RST_CTRL=0`만으로 PL 리셋
해제를 보장할 수 없습니다. 이것이 이번 정지의 유력한 원인이지만 실제 PL 신호 측정으로 확정하지는 않았습니다.

`build.tcl`의 V2는 FCLK 클록·리셋 포트를 모두 사용하지 않습니다.
외부 MMCM의 LOCKED와 proc_sys_reset의 초기화 시퀀스로 AXI·FFT 리셋을 해제하며,
active-low 외부 리셋 입력은 1에 고정합니다. PS의 FCLK reset 명령으로 이 설계의 PL 로직을
리셋할 수 없고, FFT 소프트 리셋은 AXI 제어 레지스터를 사용합니다.
V2 `fft128_ps_20261115_201257`의 Vivado 빌드 완료를 확인했습니다.
setup slack 32.177 ns, hold slack 0.052 ns로 타이밍을 통과했고, 생성된 BD netlist에서
외부 리셋 입력이 상수 1, `dcm_locked`가 MMCM LOCKED에 연결된 것도 확인했습니다.
V2 펌웨어 SHA256 `8eda79186efa499e3eb1ac720dc4c621fdda99ff53a4ca5bb25589a1bab4bbbb`와
진단 수신기 SHA256 `2a109f3864161dc5c82645a9caf362106350aa18f3d91bad7c665c0ea7852c4f`의
NFS 배치 및 사용자 보드 다운로드를 확인했습니다. 자체 검사는 첫 ID 읽기 `0x43c00000`에서
정지했습니다. **V2 PL 검사는 실패했습니다.**
수신기에는 ID 읽기·FFT 길이 읽기·소프트 리셋의 진행 출력을 추가했습니다.

생성된 `system_reset_0`의 실제 설정은 `C_AUX_RESET_HIGH=0`(active-low)인데
`aux_reset_in`이 상수 0에 연결돼 있었습니다. 이 때문에 AXI·FFT가 계속 리셋 상태였습니다.
실제 생성된 reset functional netlist와 Xilinx 공식 Unisim 셀로 PC에서 재현했습니다.
기존 연결은 `interconnect_aresetn=0`, `peripheral_aresetn=0`으로 고정됐고,
보조 리셋을 비활성화하면 ID·길이 읽기 및 lock-loss/reset 복구가 통과했습니다.
재현 로그: `build/fft128_reset_debug/old_wiring.log`, `old_ip_aux_released.log`.

현재 **V3**는 `C_EXT_RESET_HIGH=0`, `ext_reset_in=1`, `C_AUX_RESET_HIGH=1`,
`aux_reset_in=0`으로 두 리셋 극성과 비활성 입력을 모두 명시합니다.
`reset_axi_tb.v`가 실제 생성된 reset IP와 FFT AXI 레지스터를 연결해 초기 리셋 해제,
ID/길이 읽기, MMCM lock-loss 시 리셋과 재해제를 검사합니다.
Vivado `build.tcl`은 이 시뮬레이션이 통과해야 합성·구현을 시작합니다.
V3 `fft128_ps_20261115_203251`의 시뮬레이션 소스 등록을 수정한 후 빌드가 완료됐습니다.
`reset_simulation.txt`에서 `done=1 passed=1`(실제 생성 reset IP, AXI ID/length,
lock-loss recovery)을 확인했습니다. setup slack 32.177 ns, hold slack 0.052 ns이며
`BOARD_MMCM_LOCK_V3_AUX_HIGH` 표식과 새 bitstream 생성도 확인했습니다.
**V3 실제 보드 MMIO 자체 검사 통과**를 사용자 콘솔 출력으로 확인했습니다.
FPGA Manager 다운로드 성공(70 ms), ID `0x46543128`, FFT 길이 128, soft reset 완료 후
`SELFTEST_PASS backend=PL_MMIO vectors=4 bins=512`가 출력됐습니다.
실제 배치 firmware SHA256은 `e1784f80c8f27225dded47749d0baa98a3d2cc9a108b0f7df2d86afb6239a5db`입니다.
이 결과는 네 개의 128포인트 FFT 자체 검사입니다.
콘솔 근거를 `build/fft128_pl_integration/board_selftest.json`에 기록했습니다.

이후 **실제 보드 128×128 Range–Doppler 프레임 검사도 통과**했습니다.
Windows RadarSimPy 입력 기록을 Ubuntu에서 UDP로 128개 패킷(134,656 bytes) 전송했고,
보드에서 `FRAME_PASS backend=PL_MMIO bit_exact_bins=16384`를 확인했습니다.
한 개의 PL 128포인트 코어를 256회 호출해 두 축을 처리하며 16,384 complex bin이
PS 정수 기준값과 모두 일치했습니다. 피크는 unshifted (Doppler, Range) = (107,20)입니다.
PS–PL 전송·FFT·전치 시간은 단일 실행에서 0.082024초였습니다.
UDP 수신, Q15 변환, 소프트웨어 기준값 계산·비교 및 파일 저장 시간은 이 수치에 포함되지 않습니다.
DMA·연속 프레임 처리량은 측정하지 않았습니다.
콘솔 근거는 `build/fft128_pl_integration/board_frame_console_result.json`에 기록했습니다.
보드 `/opt/fft128/rd128.{input.csv,csv,json}`은 Ubuntu의 `/nfsroot/opt/fft128/`에 있으며,
실제 출력 CSV·JSON을 수집해 **독립적인 NumPy 비교도 통과**했습니다.
보드가 받은 16,384개 complex IQ 입력은 원본 RadarSimPy 기록과 정확히 일치했습니다.
`np.fft.fft2(Q15_input)/16384` 대비 최대 complex 오차 8.749842 Q15 LSB,
RMS 오차 1.734691 Q15 LSB이며 기존 최대 오차 기준 12 이내입니다.
NumPy 피크도 (107,20)으로 같고 packet drop·duplicate는 모두 0입니다.
검증 결과와 실제 파일 SHA256은 `build/fft128_pl_integration/board_numpy_validation.json`,
로그는 `board_numpy_validation.log`, 비교 그림은 `range_doppler_validation.png`에 저장했습니다.
이번 128×128 단일 프레임 기능 검증은 완료됐습니다.

같은 Q15 입력을 Windows PC의 NumPy 2.5.0 `complex128` FFT2와 비교한 시간도 기록했습니다.
CPU는 Intel Core i7-1165G7이며, 100회 warm-up 후 1,000회 측정한
`np.fft.fft2(input)/16384`의 중앙값은 0.257850 ms, 평균은 0.261660 ms입니다.
5~95 percentile은 0.204495~0.373760 ms였습니다. 이 PC 측정은 참고용 기록이며
**같은 보드의 PS NumPy 대비 PL 가속비로 사용하지 않습니다.** 이전에 제시한 318배 비교는
보드 내 가속 효과 결론에서 제외했습니다. **PS NumPy 시간과 같은 보드 기준 가속비는 미측정**입니다.
PC는 FFT·정규화·출력 배열 할당을, 보드는 PL FFT·PS–PL 전송·PS 전치·임시 메모리 할당을
측정했으므로 순수 PL 산술 가속비 또는 동일 CPU 기준 비교로 해석하지 않습니다.
현재는 20 MHz, 반복형 FFT 코어 1개, AXI4-Lite 워드 전송 방식입니다.
이 최초 비교 당시에는 PL 내부와 MMIO 시간을 분리하지 않았습니다. 이후 E09에서 분리 계측했고,
PL 내부 39.3344 ms, 입력·출력 MMIO 합 41.800314 ms를 확인했습니다. DMA 성능은 아직 미측정입니다.
전체 출력의 상대 L2 오차는 약 1.361%, 피크 진폭 오차는 약 -0.00646%입니다.
측정 조건과 정확도 지표는 `build/fft128_pl_integration/numpy_timing_comparison.json`에 저장했습니다.

성능 비교의 기준은 같은 Zybo의 PS Cortex-A9에서 실행한 기존 최적화
`udp_radar_receiver.cpp`의 C++/FFTW와 PS가 구동하는 PL 경로입니다.
실행 절차는 `benchmarks/README.md`의 same-board 128×128 절차를 따릅니다.
현재 추가된 소프트웨어 계측은 PL 작업 버퍼 사전 할당·warmup/repeat·각 반복의 정답 검증과,
C++ 타일 전치 유지·동일 Q15 입력 준비·정규화 및 `fft_pipeline` 전용 구간을 지원합니다.
검증된 bitstream을 유지하고 ARM 빌드와 실제 반복 측정을 완료했습니다. E08의 각 300회 기준으로
PS 중앙값은 5.550039 ms, PL은 81.460246 ms입니다. 개별 기록은 통합 실험 일지에서 연결합니다.
동일한 128×128 입력이 DDR에 준비된 시점부터, 결과가 PS 메모리에서 사용 가능한 시점까지
측정합니다. PS C++/FFTW는 두 축 FFT·복사·타일 전치·정규화, PL 경로는 양방향 데이터 전송·전치·두 축 FFT를
포함합니다. 양쪽 모두 UDP·시뮬레이터·파일 IO·검증·공통 입력 준비는 제외합니다.
최초 단일 실행 82.024044 ms에는 임시 작업 버퍼 할당도 포함됐습니다. E08은 버퍼를 사전 할당하고
워밍업 후 반복 측정했으며 CPU0 고정을 확인했습니다. CPU 주파수는 직접 확인하지 못했습니다.
현재 데이터 경로는 AXI4-Lite MMIO이며 **DMA는 아직 구현하지 않았습니다**.
DMA를 추가하면 제출·완료 대기와 필요한 cache 정합성 처리를 포함하되, DMA 측정에 포함된
AXI 데이터 이동 시간을 별도로 더해 중복 계산하지 않습니다.
[reset 입력 극성 설명(PG164)](https://docs.amd.com/v/u/en-US/pg164-proc-sys-reset).

V3 `fft128_ps_20261115_203251`은 사전 시뮬레이션 elaboration에서 멈췄고 합성은 시작하지 않았습니다.
BD 자식 IP를 검사 top에서 직접 참조할 때 Vivado가 해당 IP의 VHDL 소스를 자동 포함하지 않아
`system_reset_0 not found`가 발생했습니다. 생성된 VHDL에서는 보조 리셋 극성 수정이 확인됐습니다.
`reset_sim_sources.tcl`은 실제 생성된 CDC·reset 구현·IP wrapper를 simulation fileset에
복사·등록하고 각 VHDL library를 지정합니다. `build.tcl`에 반영돼 있습니다.
이 오류가 난 기존 프로젝트를 열어 둔 상태에서는 다음으로 검사와 빌드를 이어갑니다.

```tcl
source [file join $env(HOME) fmcw_share FMCW-FFT-test src PL fft128_ps resume_build.tcl]
```

`resume_build.tcl`은 현재 프로젝트 디렉토리와 생성된 V3 IP를 재사용합니다.
리셋 검사 통과 후 합성·구현·bitstream 생성으로 이어가며 기존 프로젝트를 재생성하지 않습니다.

2026-11-15 native C 수신기 추가 확인:

- GCC `-Wall -Wextra -Werror` 빌드와 C 수신기 테스트 6개 통과 (Windows PC).
- 정수 FFT가 기존 RTL 검사 벡터의 복소수 34,816 bin과 일치.
- 저장된 실제 RadarSimPy 프레임의 localhost UDP 수신, 송신자 구분, 재정렬·중복·오류 패킷 처리,
  128×128 FFT 결과를 Python 정수 모델 및 NumPy와 비교해 통과.
- 누락 프레임·샘플링 주파수 변경·손상된 replay 거부 및 FFT 호출 실패 전파 확인.
- ARM32 정적 ELF 생성 확인. 보드에서 `--backend model --self-test` 실행 결과
  `SELFTEST_PASS ... vectors=4 bins=512`를 사용자 콘솔 출력으로 확인함.
  이는 PS의 C 실행 환경·소프트웨어 검사 결과이며 실제 PL MMIO 검사는 아직 남아 있음.

결과는 저장소의 `build/fft128_verify/`, `build/fft128_udp/`에 생성됩니다.
Windows에서 재검사:

```powershell
python src/PL/fft128_ps/verify.py
python -m unittest discover -s src/PS/fft128 -p test_receiver.py -v
python -m unittest discover -s src/PS/fft128 -p test_native.py -v
```

`verify.py`는 PC NumPy 및 Icarus가 필요합니다. 다른 설치 위치는 `--iverilog`, `--vvp`로 지정합니다.

## 1. Vivado 2022.1에서 새 하드웨어 생성

Ubuntu 공유 폴더가 `$HOME/fmcw_share`에 마운트된 환경의 Vivado **Tcl Console**:

```tcl
source [file join $env(HOME) fmcw_share FMCW-FFT-test src PL fft128_ps build.tcl]
```

마운트가 사라졌다면 먼저 다음을 실행합니다. 이미 마운트되어 있으면 반복하지 않습니다.

```tcl
file mkdir [file join $env(HOME) fmcw_share]
exec /usr/bin/vmhgfs-fuse .host:/share-2 [file join $env(HOME) fmcw_share]
```

스크립트는 열려 있는 프로젝트를 닫고 새 timestamp 디렉토리에 생성합니다.
저장할 기존 편집이 있으면 먼저 저장합니다. `FFT128_BUILD_PASS: ...`가 완료 표식입니다.
실패하면 그 디렉토리의 `error.txt`와 Vivado Messages에서 원인을 확인합니다.

생성 구조:

```text
Zynq PS7 (Digilent Zybo Z7-10 DDR/MIO preset)
  M_AXI_GP0 → AXI Interconnect → fft128_axi → fft128_stream
  K17 SYSCLK 125 MHz → Clocking Wizard 20 MHz → PS GP0 ACLK·AXI·FFT
  Clocking Wizard LOCKED → Processor System Reset
  외부 리셋 입력 = 1 (active-low 해제), PS FCLK 리셋 미사용
  MMCM LOCKED → Processor System Reset 초기화 → AXI·FFT 리셋 해제
  DDR/FIXED_IO → 보드 PS 핀
```

새 `.bit`, `system.xsa`, `utilization.rpt`, `timing.rpt`가
`build/vivado/fft128_ps_날짜_시간/`에 생성됩니다. 최신 성공 경로는 `build/fft128_latest.txt`입니다.
스크립트는 실제 reset IP 시뮬레이션에서 `FFT128_RESET_SIM_PASS`를 확인한 뒤 합성하며,
setup/hold slack을 검사합니다. reset 결과는 `reset_simulation.txt`에 기록합니다.
**JTAG 다운로드나 SD 쓰기는 하지 않습니다**.
보드의 80 DSP·17,600 LUT·60 RAMB36 안에 실제로 맞는지는 이 보고서로 확인합니다.

## 2. 현재 TFTP·NFS 부팅 환경과 연동

2026-11-15 사용자가 제공한 설정에서 확인한 구성:

| 항목 | 값 |
|---|---|
| Ubuntu VM / NFS 서버 | `10.0.0.2` |
| Zybo 보드 | `10.0.0.3` |
| Ubuntu TFTP 제공 경로 | `/tftpboot` |
| Ubuntu NFS export | `/nfsroot` |
| 보드 rootfs | `root=/dev/nfs`, `nfsroot=10.0.0.2:/nfsroot,tcp,vers=3` |

이 네트워크 부팅 구성을 유지합니다. Ubuntu의 `/nfsroot/opt/fft128`에 파일을 배치하면
보드에서는 `/opt/fft128`로 접근합니다. 호스트 Ubuntu의 `python3`와 보드의 `python3`는
별도 실행 환경이며, MMIO helper는 보드의 ARM ABI·libc에 맞게 빌드해야 합니다.

진행 순서는 새 Vivado 하드웨어 빌드 → Ubuntu에서 ARM Linux C 수신기 빌드·NFS 배치 →
보드 실행 확인 → 현재 FSBL/PL 클록·리셋과 새 설계의 호환성 확인 → 실제 MMIO 검사입니다.
`/dev/mem` 지원도 확인합니다. 보드에 Python이나 컴파일러가 없어도 됩니다.
기존 커널과 NFS rootfs가 필요한 기능을 제공하면 해당 부분을 재사용합니다.
새 프로젝트 생성이나 전체 Linux 재빌드 필요 여부는 이 확인 후 결정합니다.

`fft128_ps_20261115_184515`는 최초 FCLK0 버전이고, `fft128_ps_20261115_195400`은
리셋에 FCLK 의존성이 남은 첫 외부 클록 버전입니다. V2 `fft128_ps_20261115_201257`도
보조 리셋 극성 오류가 있으므로 이 세 버전 모두 현재 배포 대상으로 사용하지 않습니다.
1절의 Vivado `build.tcl`을 다시 실행해 V3를 생성합니다. 완료 디렉토리의 `clock_source.txt`에
`FCLK0 not used`와 `RESET_SCHEME=BOARD_MMCM_LOCK_V3_AUX_HIGH`가 모두 기록되어야 합니다.
`prepare_firmware.sh`는 V3 표식이 없는 기존 bitstream의 변환을 거부합니다.
AXI/FFT는 보드 입력으로 20 MHz를 생성하며 PS FCLK 클록·리셋에 의존하지 않습니다.
새 bitstream·클록·리셋이 준비된 뒤 `0x43C00000`를 읽습니다.

MMIO 접근이 멈춘 후 minicom만 다시 열어도 보드와 이전 프로세스는 초기화되지 않습니다.
미완료 AXI 트랜잭션이 있을 수 있으므로 이 상태에서 다시 다운로드하거나 MMIO 검사를 반복하지 않습니다.
새 V3 펌웨어를 배치하고 보드를 정상 재부팅한 뒤 다운로드·검사합니다. 재부팅 명령에도 응답이
없으면 보드 전원을 다시 켜야 할 수 있습니다. 다운로드 후의 `operating`만으로 PL FFT 통과를 판단하지 않습니다.

사용자 제공 PS 레지스터 값: `IO_PLL_CTRL=0x0001E000`, `FPGA0_CLK_CTRL=0x00200500`,
`FPGA_RST_CTRL=0x00000000`, `LVL_SHFTR_EN=0x0000000F`.
I/O PLL 30배, FCLK0 5×2 분주이므로 보드의 33.333 MHz 기준 설정은 약 100 MHz입니다.
게이트 활성 상태는 이 분주 레지스터만으로 판단하지 않습니다. 리셋은 해제되고 레벨 시프터는 활성화돼 있습니다.
새 외부 클록 버전에서는 이 문제를 해결하기 위해 PS PLL·FCLK 분주 레지스터나 `clk_ignore_unused`
부팅 인수를 수정할 필요가 없습니다. Linux의 NFS root·IP·console 인수를 유지합니다.

### Ubuntu에서 ARM 실행 파일 빌드·NFS 배치

공유 폴더가 마운트된 Ubuntu 터미널에서 실행합니다.
SDK 환경의 ARM Linux `CC`가 설정되어 있으면 우선 사용하고, 그렇지 않으면 Vitis 2022.1의
ARM32 Linux GCC 또는 PATH의 ARM Linux GCC를 찾습니다. 컴파일러를 명시하려면
`FFT128_CC=/absolute/path/to/arm-linux-gnueabihf-gcc`를 지정합니다.
ARM bare-metal·ARM64·x86 컴파일러는 사용하지 않습니다.

```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/src/PS/fft128/build_native.sh"
```

기본값은 정적 링크입니다. `NATIVE_BUILD_PASS`와 ARM ELF 결과를 확인한 뒤 배치합니다.
컴파일러나 정적 라이브러리를 찾지 못하면 표시된 오류를 확인하고 빌드 환경을 맞춥니다.
자동으로 다른 backend나 다른 아키텍처로 전환하지 않습니다.
일치하는 SDK/sysroot로 동적 링크가 필요한 경우에만 `FFT128_STATIC=0`으로 빌드하고,
그 실행 파일이 요구하는 ARM 라이브러리·로더가 현재 NFS rootfs에 있는지 확인합니다.

```bash
mkdir -p "$HOME/fft128_deploy"
cp "$HOME/fmcw_share/FMCW-FFT-test/build/fft128_native/fft128-receiver" \
  "$HOME/fft128_deploy/fft128-receiver"
sudo install -D -m 0755 \
  "$HOME/fft128_deploy/fft128-receiver" \
  /nfsroot/opt/fft128/fft128-receiver
```

`cp`는 공유 폴더를 마운트한 일반 사용자로 실행합니다. 사용자 FUSE 마운트는 기본적으로
root의 파일 접근도 제한하므로, 공유 폴더의 파일을 바로 `sudo install`하면
`cannot stat ... Permission denied`가 발생할 수 있습니다. Ubuntu 로컬 폴더에 먼저
복사한 뒤 그 복사본을 root 권한으로 설치합니다.

보드에서 실행 파일의 동작을 먼저 확인합니다. **아래 `model` 검사는 FPGA에 접근하지 않습니다.**

```sh
/opt/fft128/fft128-receiver --backend model --self-test
ls -l /dev/mem
```

`SELFTEST_PASS backend=SOFTWARE_MODEL (no FPGA access)`는 C 실행 파일의 보드 실행 확인입니다.
실제 FPGA 검사는 3절에서 `PL_MMIO` 결과를 확인해야 합니다.
프로그램은 단일 프레임을 처리하며 창함수·양자화·출력 계약은 Python 참조 경로와 같습니다.
`--input frame.rspb`로 기존 `RSPB0001` 패킷 replay 파일도 처리할 수 있습니다.

관련 공식 문서:
[Vitis 2022.1 ARM 크로스 컴파일](https://docs.amd.com/r/2022.1-English/ug1393-vitis-application-acceleration/Compiling-and-Linking-for-Arm).

### Ubuntu에서 FPGA Manager용 bitstream 준비

외부 클록 버전의 `FFT128_BUILD_PASS` 이후 Ubuntu 터미널에서 실행합니다.

```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/src/PL/fft128_ps/prepare_firmware.sh"
```

스크립트는 최신 빌드의 `clock_source.txt`를 확인한 뒤 Bootgen의 `-arch zynq -process_bitstream bin`
옵션으로 FPGA Manager용 raw 파일을 생성합니다. `FIRMWARE_READY` 경로를 `BIN`에 넣고 배치합니다.

```bash
BIN=/absolute/path/printed/by/FIRMWARE_READY/fft128.bin
cp "$BIN" "$HOME/fft128_deploy/fft128.bin"
sudo install -D -m 0644 "$HOME/fft128_deploy/fft128.bin" /nfsroot/opt/fft128/fft128.bin
```

기존 ARM 수신기는 그대로 사용합니다. FPGA 로딩과 실제 검사는 보드 터미널에서 수행합니다.
현재 보드 계정은 `/dev/mem` 접근에 관리자 권한이 필요하므로 `sudo`를 붙입니다.

```sh
sudo fpgautil -b /opt/fft128/fft128.bin
cat /sys/class/fpga_manager/fpga0/state
sudo /opt/fft128/fft128-receiver --self-test
```

`operating`만으로는 FFT 검사 성공을 의미하지 않습니다.
`SELFTEST_PASS backend=PL_MMIO vectors=4 bins=512`가 실제 PL 자체 검사 성공 표식입니다.

## 2A. 커널·rootfs 재빌드가 필요한 경우: PetaLinux 2022.1 반영

아래는 **Ubuntu 터미널**에서 실행합니다. 보드 BusyBox 쉘이나 Vivado Tcl 명령이 아닙니다.
PetaLinux 2022.1 `settings.sh`를 source한 뒤, Zybo 프로젝트를 사용합니다.
설치 경로는 `/tools/Xilinx/petalinux/settings.sh`, BSP는
`/tools/Xilinx/bsp/Zybo-Z7-10-Petalinux-2022-1.bsp`로 확인되었습니다.
프로젝트가 필요하면 이 BSP에서 생성합니다. 현재 부팅에 사용하는 TFTP 파일과 NFS rootfs를
보존한 상태에서 필요한 변경을 빌드합니다.

```bash
# 실제 PetaLinux 프로젝트의 절대경로로 지정
PLNX=/absolute/path/to/existing-zybo-project
SHARE="$HOME/fmcw_share/FMCW-FFT-test"
HW=$(cat "$SHARE/build/fft128_latest.txt")

python3 "$SHARE/src/PS/fft128/install_recipe.py" "$PLNX"
cd "$PLNX"
petalinux-config --get-hw-description="$HW"
petalinux-config -c rootfs
```

rootfs 메뉴의 user packages에서 `fft128`을 활성화하고 저장합니다.
제공 레시피는 native C 실행 파일 `/usr/bin/fft128-receiver`를 설치합니다.
보드에 Python·RadarSimPy·NumPy·FFTW를 설치할 필요는 없습니다.

외부 클록 버전은 Clocking Wizard 출력으로 AXI·FFT를 구동하므로 FCLK0 유지용 부팅 인수가
필요하지 않습니다. 향후 PS FCLK를 쓰는 버전으로 바꾸면 클록 소비 드라이버 및 device tree를
그에 맞게 구성합니다.
커널의 `CONFIG_DEVMEM=y`도 확인합니다. 기존 NFS 부팅의 root·console·네트워크 설정을 유지합니다.

```bash
petalinux-build
petalinux-package --boot --fsbl images/linux/zynq_fsbl.elf --fpga --u-boot --force
```

FSBL·bitstream·DT/kernel/rootfs의 하드웨어 설정이 서로 맞아야 합니다.
현재 구성에서는 실제 U-Boot 부팅 명령을 확인해 새 커널/DTB 또는 FIT 이미지를 `/tftpboot`에
배치하고, 프로그램·의존성은 `/nfsroot`에 반영합니다. FSBL/bitstream을 어디서 로드하는지는
TFTP와 NFS 경로만으로 확인되지 않으므로, U-Boot 환경을 확인한 뒤 해당 파일을 갱신합니다.
기존 32포인트 VIO bitstream을 올린 상태로 아래 MMIO 주소를 읽지 않습니다.

이번 데이터 경로에는 DMA 노드·DMA 드라이버·DMA 버퍼 예약이 필요하지 않습니다.
device tree는 새 XSA를 기준으로 재생성하고 `0x43c00000`에 다른 장치가 겹치지 않는지 확인합니다.
현재 PL 클록은 보드의 125 MHz 입력에서 Clocking Wizard로 20 MHz를 생성합니다.
PS–PL 레벨 시프터·PS 출력 리셋은 올바르게 준비돼 있어야 합니다.

관련 공식 문서:
[2022.1 XSA 반영](https://docs.amd.com/r/2022.1-English/ug1144-petalinux-tools-reference-guide/Steps-to-Import-Hardware-Configuration),
[2022.1 bitstream 포함 부팅 이미지](https://docs.amd.com/r/2022.1-English/ug1144-petalinux-tools-reference-guide/Bitstream-is-not-included-default-in-BOOT.BIN),
[Linux 5.15 clk_ignore_unused](https://github.com/torvalds/linux/blob/v5.15/Documentation/admin-guide/kernel-parameters.txt).

## 3. 보드 자체 검사 → 시뮬레이터 연동

하드웨어와 PS 실행 환경을 준비한 보드의 root 쉘 (아래 명령은 NFS 직접 배치 기준):

```sh
cat /proc/cmdline
sudo /opt/fft128/fft128-receiver --self-test
```

`SELFTEST_PASS backend=PL_MMIO vectors=4 bins=512`를 확인한 다음:

```sh
sudo /opt/fft128/fft128-receiver --port 5000 --timeout 120 --output /tmp/fft128_result
```

PC의 저장소 루트에서 보드 IP를 넣어 전송합니다.

```powershell
python tools/sender/sender.py --ip BOARD_IP --port 5000 --pulses 128 --samples 128
```

`--samples 128`은 80 us chirp의 fs를 1.6 MHz로 바꿉니다. 160개에서 일부를 잘라내지 않습니다.
송신 패킷은 1,052바이트이고, 한 번에 한 프레임만 보냅니다.
레시피 설치를 사용했다면 `/opt/fft128/fft128-receiver` 대신 PATH의 `fft128-receiver`를 실행합니다.

보드 성공 표식은 `FRAME_PASS backend=PL_MMIO bit_exact_bins=16384`입니다.
CSV·입력 CSV·JSON을 PC로 가져와 추가 비교합니다.

```powershell
python src/PS/fft128/verify_result.py path/to/fft128_result
```

CSV 순서는 Doppler unshifted bin 0..127, 각 행 Range bin 0..127입니다.
창함수는 none이고 FFT마다 1/128, 2D 전체는 1/16384 스케일입니다.
복원하려면 Q15 정수 결과를 `input_to_q15_scale`로 나누고 16,384를 곱합니다.
각 단계의 절삭 때문에 정확히 부동소수점 결과로 복원되지는 않습니다.

`fft_and_transfer_seconds`는 256회 FFT와 PS 전송·전치 비용을 포함하고,
UDP 수신·후속 정수 검증·파일 저장은 제외합니다. 이 값으로 DMA 성능 향상을 주장하지 않습니다.
native C 반복 벤치마크는 작업 버퍼를 미리 할당하고 평균 시간을 기록합니다.
선택적인 Python 수신기를 실행하면 그 프로그램의 Python 제어 비용도 포함됩니다.

PC에서 하드웨어 없이 수신 프로그램만 확인하려면:

```powershell
python src/PS/fft128/receiver.py --backend model --bind 127.0.0.1 --port 5000
```

이 경로는 항상 `SOFTWARE_MODEL (no FPGA access)`로 표시됩니다.

## 레지스터 계약

기본 주소 `0x43C00000`, 범위 4 KiB. little-endian 32비트 정렬 접근만 사용합니다.

| Offset | 접근 | 내용 |
|---|---|---|
| 0x000 | R | ID `0x46543128` |
| 0x004 | W | 1=start, 2=soft reset/abort |
| 0x008 | R | bit0 busy, bit1 done(sticky), bit2 FFT error |
| 0x00C | R | 128 |
| 0x010 | R | 마지막/현재 FFT의 클록 수 |
| 0x100..0x2FC | W | 128개 입력: real low16, imag high16, signed Q1.15 |
| 0x800..0x9FC | R | 128개 출력, 자연 bin 순서; done 상태에서만 유효 |

모든 입력을 한 번 이상 쓴 뒤 start합니다. soft reset은 입력 초기화 표시도 지웁니다.
busy 상태의 입력 덮어쓰기·중복 start·잘못된 주소·비정렬/부분 쓰기는 AXI SLVERR입니다.
WSTRB=0은 부작용 없는 성공 응답입니다. MMIO helper는 volatile 32비트 접근과 메모리 배리어를 사용합니다.
별도 커널 드라이버가 없으므로 한 프로세스만 장치를 소유해야 합니다.

내부 AXI-Stream에서는 **128번째 beat마다 TLAST**입니다. 저장소의 전체 프레임 DMA 초안과 다릅니다.
이 차이는 이번 기능 검증용 계약이며, 향후 DMA 프런트엔드를 만들 때 명시적으로 맞춰야 합니다.
