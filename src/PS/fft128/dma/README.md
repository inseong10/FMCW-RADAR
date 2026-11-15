# E11a — 512 B 단위 AXI DMA 경로

기존 E10의 `fft128_pipeline` 산술·RAM·출력 스케줄과 50 MHz를 유지하고,
샘플의 AXI4-Lite 입출력을 AXI DMA로 교체한다. 한 ioctl은 FFT 하나이며
입력 512 B, 출력 512 B다. 프레임당 FFT 256회, DMA 채널 제출 512회다.
묶음 제출·외부 ping-pong·코어 복제·출력 1 sample/clock은 포함하지 않는다.

현재 확인: RTL 앞단 272벡터/34,816 bin 일치, 기존 RTL 회귀 통과,
Ubuntu ARM32 정적 수신기 빌드 및 기록된 DT에 overlay 오프라인 적용 통과.
커널 모듈 ARM 빌드와 실제 보드의 대응 DT 없는 정상 load/unload·CRC 검사는 통과했다.
Vivado 통합/50 MHz 구현 타이밍도 통과했다(WNS 10.607 ns, WHS 0.021 ns).
DT v2 적용 후 실제 보드 DMA 드라이버 연결, ABI 검사와 4벡터/512 bin 자체 검사도 통과했다.
전체 128×128 프레임·독립 정수 검증과 각 300회 paired 비교도 완료했다.
중앙값은 PL DMA 15.411639 / PS double 5.748489 / PS NEON 3.715234 ms다.
[E11a 측정 보고서](../../../../benchmarks/reports/2026-11-16-e11a-board/README.md)에 원본과 해석을 보존한다.
최신 상태는 [E11a 구현·보드 보고서](../../../../benchmarks/reports/2026-11-16-e11a-build/README.md)를 따른다.

## 구성과 기존 경로 보존

```text
PS cached workspace → user/kernel copies → coherent TX in DDR
     → HP0 → AXI DMA MM2S → AXIS → unchanged FFT128 pipeline
     ← user/kernel copies ← coherent RX in DDR ← HP0 ← DMA S2MM ← AXIS
Range 128 FFT → PS cached gather/scatter → Doppler 128 FFT
```

MM2S는 HP0로 DDR을 읽어 FFT 스트림에 공급하고, S2MM는 FFT 스트림을 DDR로 쓴다.
두 채널의 메모리 버스는 64-bit, FFT 스트림은 32-bit다. GP0/AXI4-Lite는
FFT 시작·상태·사이클과 DMA 설정에 계속 사용한다. 샘플별 MMIO 창은 없다.

| 항목 | E11a 설정 |
|---|---|
| Vivado | `src/PL/fft128_ps/build_dma.tcl`, XC7Z010, 50 MHz |
| 클록/리셋 | K17 125 MHz → MMCM 50 MHz, 기존 V3 MMCM-lock 리셋, FCLK 의존 없음 |
| FFT 제어 | `0x43c60000`, 4 KiB, ID `0x46544480`, ABI 1 |
| DMA 제어 | `0x40400000`, 64 KiB, Simple DMA, SG/DRE 꺼짐 |
| 데이터 | HP0 64-bit, AXIS 32-bit, burst 16, length width 17 |
| IRQ | F2P[6]/[7], GIC IRQ67/68, DT SPI35/36 |
| CPU 버퍼 | 기존 cached 작업 배열에서 전치; coherent bounce buffer에는 복사만 수행 |
| 소유권 | 커널이 레지스터·채널·DMA 주소 관리, `/dev/fft128-dma` 단일 소유자 |
| 배치 경로 | `/opt/fft128/e11a`; 기존 `/opt/fft128/benchmark`·펌웨어 보존 |

실제 BSP DT에 기존 VTC `0x43c00000`과 SPI29~34가 남아 있다. 충돌을 피하려고
새 주소/IRQ를 사용한다. 기존 MMIO 실행 파일은 새 펌웨어에서 실행하지 않는다.
overlay 생성기는 기록한 live DT의 GIC phandle·주소 cell을 읽고 주소/IRQ 중복을 거부한다.
현재 overlay는 이미 부팅 때 활성화된 `/amba_pl` 버스에 DMA/FFT를 직접 추가한다
(`overlay_layout=existing_amba_pl_v2`). 새 simple-bus를 동적으로 만든 최초 버전은
버스/클록 장치만 등록되고 하위 DMA/FFT가 생성되지 않아 보드 자체 검사 전에 중단됐다.
비트스트림·커널·FFT 산술은 유지하고 DT 등록 구조만 수정했다.
외부 GIC의 숫자 phandle은 독립 DT overlay 컴파일 시 경고가 날 수 있다.
`fdtoverlay`로 실제 기록 DT에 적용하는 검증이 별도로 필요하다.

## 빌드 순서 — Ubuntu에서 실행

```sh
P="$HOME/fmcw_share/FMCW-FFT-test"
bash "$P/src/PS/fft128/dma/prepare_host.sh"
bash "$P/src/PS/fft128/dma/build_kernel_reference.sh"
```

첫 스크립트는 ARM 수신기·보드 ABI 검사 실행 파일, overlay를 만든다.
두 번째는 BSP에 지정된 Digilent 5.15.19 소스의 고정 commit
`5e8c35eccbabeb08a63f55f18fec677a685c30b3`과 보드 `/proc/config.gz`로
별도 로컬 커널 빌드 트리를 생성하고 `Module.symvers`까지 빌드한다.
이 경로는 현재 설치된 ARM GCC를 사용한다. 보드 커널·TFTP·NFS는 변경하지 않는다.
빌드는 VM의 CPU/디스크에 따라 시간이 걸리며 로그는 `build/fft128_dma_kernel_reference/`에 남는다.

후보 트리의 릴리스 이름 일치는 필요조건이다. 원래 BSP가 AUTOREV를 사용했고 보드 커널에
사용자 모듈 설정도 있어, 같은 소스라고 확정하지 않는다. 컴파일러/설정 차이는
`config_delta.txt`에 남고 최종 호환성은 보드의 정상 `insmod` CRC 검사로 확인한다.
CRC/`module_layout` 오류가 나면 중단한다. `--force`, CRC 조작, vermagic 덮어쓰기는 사용하지 않는다.
그 경우 원래 커널 빌드 산출물을 확보하거나 일치하는 커널/모듈을 별도로 부팅하는 검토가 필요하다.

원래 커널 빌드 트리를 확보했다면 후보 커널 빌드 대신 다음 명령을 사용한다.

```sh
bash "$P/src/PS/fft128/dma/build_module.sh" /absolute/path/to/kernel/build
```

먼저 Ubuntu에서 모듈 호환 검사만 배치하고 보드에서 실행한다.
이 단계는 대응 DT 노드가 없음을 확인한 뒤 모듈을 정상 로드/언로드해 커널 CRC만 검사한다.
FPGA 레지스터를 읽거나 새 펌웨어를 적용하지 않는다.

```sh
# Ubuntu
bash "$P/src/PS/fft128/dma/deploy_module_probe.sh"
# PetaLinux
sudo sh /opt/fft128/e11a/module_probe/check_module_board.sh
```

`DMA_MODULE_CRC_PASS`를 확인한 다음 Vivado 통합 빌드를 한 번 실행한다.

```tcl
source [file join $env(HOME) fmcw_share FMCW-FFT-test src PL fft128_ps build_dma.tcl]
```

기존 산술 코어를 다시 작성하지 않는다. 실제 생성 reset IP 시뮬레이션, 합성/배치배선,
setup/hold 검사 후 비트스트림/XSA를 만든다. E11a 출력 포인터는
`build/fft128_dma_latest.txt`이며 기존 `fft128_latest.txt`를 바꾸지 않는다.

모든 빌드가 통과한 후 Ubuntu에서 준비·배치한다.

```sh
bash "$P/src/PS/fft128/dma/prepare_bundle.sh"
bash "$P/src/PS/fft128/dma/deploy.sh"
```

`deploy.sh`는 HGFS 파일을 일반 사용자 소유 로컬 폴더로 먼저 복사한 뒤 sudo install한다.
준비 도구는 FPGA를 자동으로 프로그램하지 않는다. 불완전한 bundle이나 기존 bundle 덮어쓰기는 거부한다.

## 보드 기능 확인 → 계측 → 비계측 비교

기존 FFT 프로세스를 종료한 상태에서 PetaLinux에서 실행한다.

```sh
sudo sh /opt/fft128/e11a/load_board.sh
sudo sh /opt/fft128/e11a/profile_board.sh /opt/fft128/e11a/profile_e11a_01
sudo sh /opt/fft128/e11a/run_board.sh /opt/fft128/e11a/results_e11a_01
```

활성화 도구는 artifact 해시·커널 릴리스·GIC phandle·HP0 폭을 확인한 후 새 펌웨어 →
overlay → 모듈 순서로 적용한다. HP0 read/write 폭 설정은 64-bit여야 한다.
bitstream만으로 PS7 초기화 설정이 적용되지는 않으므로 기존 부팅 설정이 다르면 중단한다.
HP 설정을 실행 중에 임의로 바꾸지 않는다. ABI 거부/단일 소유권 검사와 impulse 비교,
기존 4벡터 self-test를 통과해야 전체 프레임 검사로 진행한다.

기존 BSP의 영상/XADC 등 DT 노드는 새 펌웨어에 대응하지 않는다. 새 실험 동안 해당 장치를
사용하지 않는다. 기존 DT 전체를 새 설계에 맞추는 부팅 통합은 별도 단계다.
DMA 모듈/overlay가 연결된 상태로 이전 펌웨어를 다운로드하지 않는다. E10 복구는
보드 재부팅으로 E11a 동적 overlay/모듈을 제거한 다음 기존 펌웨어를 적용하는 절차를 쓴다.

## 커널 버퍼와 오류 처리

`fft128_dma.c`는 DMAengine 채널의 실제 DMA device에 coherent 버퍼를 한 번 할당한다.
사용자 가상 주소를 DMA 물리 주소로 사용하지 않는다. HP0는 소프트웨어 일관성 경로이고,
coherent 할당 API가 CPU/DMA 메모리 속성을 제공한다. 이 구성에는 streaming `dma_sync_*`가 없다.
CPU↔coherent 복사와 필요한 메모리 배리어가 실제 경로에 포함된다.

RX를 먼저 준비하고 두 DMA 채널을 제출한 뒤 FFT를 시작한다. 완료 대기는 신호로 중단할 수
있고 요청 timeout은 최대 1초다. 오류·시간초과에는 양쪽 채널을 동기 종료하고 FFT를 reset한다.
출력은 완료·DMA 상태·입출력 128개·FFT 오류 확인 뒤에만 사용자에게 전달한다.
소프트웨어 timeout은 클록이 끊긴 AXI 레지스터 접근 자체의 버스 정지를 해결하지 못한다.
그래서 기존 MMCM/reset 검증과 실제 Vivado 타이밍 검사를 유지한다.

## 계측 의미

- **주 시간:** 같은 Q15 프레임, CPU0, warmup 10/100회×3 trial. double/NEON/PL 순서를 회전한다.
  PS01의 실행 파일·라이브러리·기준 CSV를 사용하고 입력 해시가 같아야 한다.
  할당·파일/UDP·양자화·계획·검증은 제외하고, 모든 복사·ioctl·DMA·FFT·PS 전치를 포함한다.
  매 PL 반복 뒤 16,384 bin을 정수 모델과 비교한다. 결과는 새 디렉터리에 저장한다.
- **프로파일:** warmup 2/20회, host 입력 복사/ioctl/출력 복사/전치와 ioctl 내부의
  kernel copy-in/submit/wait/check/copy-out을 기록한다. 내부 구간은 ioctl과 겹쳐 합산하지 않는다.
  커널 header copy/lock/요청 초기화/마지막 metadata copy 등은 host 잔여 비용에 남는다.
- **PL `0x010`:** FFT 시작 후 마지막 AXIS 출력 수락까지의 active 사이클이다.
  입력 starvation/출력 backpressure를 포함한다. `0x020/0x024`에 해당 정지 사이클을 별도로 기록한다.
  기존 MMIO 861사이클과 동일 의미의 순수 계산 카운터라고 해석하지 않는다.
  RTL에서 active − input stall − output stall = 861 cycles/FFT를 확인했다.
  새 profile 분석기는 이 관계도 검사한다. 이 구간은 LOAD/OUTPUT을 포함한다.
  두 DMA 채널의 완료 대기는 순수 전송 시간도 아니다. IRQ/작업 재스케줄링도 포함한다.
- **추정과 측정:** 기존 내부 4.408320 ms만으로 PS01 전체 중앙값 3.615852 ms보다 길다.
  E11a는 DMA 고정 비용/전송 병목을 확인하는 단계다. 완료값은 위 보고서에 있으며,
  계측 평균 18.136318 ms와 비계측 중앙값 15.411639 ms를 구분한다.

## 레지스터 계약

모든 레지스터는 32-bit 정렬 접근이다. 제어 쓰기는 full-word 또는 zero-strobe NOP이며
기존 입력/출력 sample window 접근은 SLVERR다.

| 오프셋 | 의미 |
|---|---|
| 0x000 | ID 0x46544480 |
| 0x004 | write 1=start, 2=reset/abort; busy 중 start는 SLVERR |
| 0x008 | bit0 running, bit1 completed, bit2 failed |
| 0x00c | FFT length 128 |
| 0x010 | active cycles, DMA 스트림 정지 포함 |
| 0x014 | register ABI 1 |
| 0x018 / 0x01c | 입력/출력 handshake 개수 |
| 0x020 / 0x024 | 입력 starvation / 출력 backpressure 사이클 |

UAPI는 고정 폭/포인터 없는 1,096-byte 요청이다. ABI/flags/timeout/reserved를 검사한다.
새 모듈과 새 수신기는 함께 배포한다. 모델 backend로 자동 대체하지 않는다.

프로파일 원본을 공유 폴더의 새 `build/` 디렉터리로 회수한 뒤 PC/Ubuntu에서 분석한다.

```sh
python3 "$P/src/PS/fft128/dma/analyze_profile.py" /absolute/path/to/pl.profile.csv
```

근거: [Linux 5.15 DMAengine client API](https://www.kernel.org/doc/html/v5.15/driver-api/dmaengine/client.html),
[Xilinx 2022.1 DMA 드라이버](https://github.com/Xilinx/linux-xlnx/blob/xlnx_rebase_v5.15_LTS_2022.1/drivers/dma/xilinx/xilinx_dma.c),
[Zynq HP/ACP 일관성 설명](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842418/Linux+DMA+From+User+Space),
[HP0 폭 레지스터](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/Register-AFI_RDCHAN_CTRL-Details).

최초 overlay 실패 상태의 복구는 Ubuntu `repair_overlay_host.sh`로 별도 v2 bundle을 만든 뒤,
보드 `sudo sh /opt/fft128/e11a/retry_overlay_board.sh`로 수행한다. 최초 bundle을 보존하고
새 raw firmware가 같은지 비교한다. 복구 도구는 `/dev/fft128-dma`가 없고 최초 버스만 있는
실패 상태를 확인한 경우에만 미연결 모듈과 해당 overlay를 제거한다. 작동 중인 DMA는 제거하지 않는다.
