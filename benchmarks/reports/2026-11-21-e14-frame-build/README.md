# E14-frame — Vivado/ARM 실제 빌드 검증

2026-11-21. **PL 전치·최종 배열 복원, 50MHz 타이밍, ARM32·보드 자체 검사 PASS. 이후 상세 계측·paired 원시 검증까지 완료했다.**
[최종 보드 결과](../2026-11-21-e14-frame-board/README.md): PL 중앙값1.657914ms, 같은 회차 NEON 대비2.104718배.

Run: `fft128_dma_e14_frame_20261121_020411`.
`implementation.json`은 이 run의 빌드 단계 상태이며 `board_verified:false`를 유지한다.
아래 빌드 단계 기록 이후 보드 모듈 등록·DMA 전송·정수 결과 일치가 사용자 콘솔에서 확인됐다.
이하 기록은 빌드·자체 검사 당시 상태이며 전체 프레임 wall time과 CPU 대비 최종 성능은 위 완료 보고서에 있다.

| 항목 | 실제 결과 |
|---|---:|
| LUT |6158 / 17600 (34.99%)|
| FF |6305 / 35200 (17.91%)|
| BRAM36 환산 |47 / 60 (78.33%)|
| DSP |28 / 80 (35.00%)|
| 50MHz setup WNS |10.166ns|
| hold WHS |0.020ns|

- setup/hold/pulse-width failing endpoints 0, no-clock·unconstrained internal endpoints 0,
  모든 사용자 타이밍 제약을 만족했다. 클록 보고서의 실제 제약은 20ns/50MHz다.
- 전용 FFT 7단계는 각각 DSP4/RAMB36 4개다. 기존 28개 stage RAM은 유지하고
  중간·최종 결과를 공유하는 행렬은 **RAMB36 16개**로 추론됐다.
  실제 core check도 `matrix_half_blocks=32; total_half_blocks=94`다. 행렬을 두 벌 만들지 않았다.
- 기준 E13-stream의 LUT6089/FF6259/BRAM31/DSP28 대비 LUT69·FF46·BRAM16이 늘고 DSP는 같다.
  이 자원 차이를 지연·처리량 증가/감소로 환산하지 않는다.
- 생성 BD에서 FFT 모듈을 제외한 PS7·DMA·clock/reset·interconnect·IRQ 컴포넌트와
  전체 interface/scalar ports/nets·addressing이 E13-stream과 동일하다.
  HP0 64-bit/AXIS32/Simple DMA/SG·DRE off/burst16/length17/F2P6·7을 유지했다.
- 실제 생성 reset IP simulation은 `done=1 passed=1`이며 ID·FFT 길이·ABI8·코어1·stage7·
  full-frame word count16384·초기 계측값·lock-loss recovery를 검사했다.
  생성 VHDL의 external active-low/aux active-high도 확인했다.
- PL·host·module source manifest는 현재 작업 파일과 공유 소스에 raw SHA가 일치한다.
  host/module artifact manifest를 재계산했고 XSA 내부 bitstream과 구현 run의 `.bit`도 일치했다.
- ARM32 static receiver/client와 `5.15.19-xilinx SMP preempt mod_unload modversions ARMv7 p2v8` 모듈 ELF를 확인했다.
  모듈의 compatible은 `fmcw,fft128-dma-frame-v8`다. 보드 `insmod`의 CRC 수용은 별도 확인이 필요하다.
- host의 dtc·기록 base-DT 대상 fdtoverlay/fdtget 검증을 통과했다. 독립 dtc 경고는 `host_dtc.log`에 보존한다.
  live overlay 적용이나 실제 DDR/DMA 검증을 대신하지 않는다.

51927 cycles/1.038540ms는 [앞선 RTL 모델](../2026-11-21-e14-frame-preparation/README.md)이며 보드 전체 시간이 아니다.
E14는 PL 배출 시간이 추가되지만 CPU 전치·중간 왕복을 없애는 데이터 경로 변경이다.
보드 전체 frame/profile/paired 성능을 측정하기 전에는 가속비를 제시하지 않는다.
대용량 bitstream/XSA/DCP/ARM 바이너리는 공유 `build/`에 유지하고 보고서에는 정확한 SHA와 작은 로그만 보존한다.

## 번들·배포와 보드 확인

### 보드 자체 검사 후속 확인 — 2026-11-21

- [사용자 제공 콘솔](board_selftest_console.log)에서 FPGA Manager 프로그래밍 57ms,
  E14 드라이버 등록, 클라이언트 4프레임 각각 256 FFT/16,384 bin 정수 일치,
  수신기 4프레임/65,536 bin 자체 검사 PASS를 확인했다.
- 계측한 클라이언트 3회 모두 행렬 읽기·쓰기 각각 32,768회, Range 출력·Doppler 입력·출력 각각
  16,384회, overwrite_errors=0이다. 단계별 issue/retire 수치는 콘솔에 직접 출력되지 않았으며
  해당 값의 검사는 동일 SHA 클라이언트의 `DMA_FRAME_CLIENT_PASS`로 확인한다.
- 공유 번들의 [22개 artifact SHA](bundle_artifacts.sha256), 빌드 당시 소스와 현재 로컬·공유 소스,
  host/module 바이너리 일치를 독립 확인했다. 구현 bitstream payload의 32-bit byte swap과
  Bootgen NOOP padding을 계산해 번들 BIN과도 대조했다. 보드 파일 자체의 해시는 아직 회수하지 않았다.
- phase 합계는 51,943/51,941/51,941 cycles다. 선언된 50MHz로 환산하면
  1.038860/1.038820/1.038820ms이며 **자체 검사 중 PL 구간**이다. CPU 복사·ioctl 등을 포함한
  전체 프레임 시간이나 paired 성능 결과로 사용하지 않는다.
- [확인 범위·정확한 신원](board_selftest.json), [재검산 코드](selftest_validation_driver.py.txt).
  원래 `implementation.json`의 빌드 시점 상태는 보존한다.

현재 보드는 로드와 자체 검사가 끝났다. 재부팅·재프로그래밍 없이 다음을 PetaLinux에서 실행한다.

```sh
sudo sh /opt/fft128/e14_frame/profile_board.sh /opt/fft128/e14_frame/profile_e14_frame_01 &&
sudo sh /opt/fft128/e14_frame/run_board.sh /opt/fft128/e14_frame/results_e14_frame_01
```

프로파일 20회와 double/NEON/PL 각각 300회 비교 후 Ubuntu에서 수집한다.

```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/src/PS/fft128/dma_frame/collect_results.sh"
```

### 최초 번들·배포 절차 (이미 완료)

Ubuntu에서 다음 순서로 실행한다. 번들 생성·NFS 배포와 FPGA 프로그래밍은 별도 단계다.

```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/src/PS/fft128/dma_frame/prepare_bundle.sh" &&
bash "$HOME/fmcw_share/FMCW-FFT-test/src/PS/fft128/dma_frame/deploy.sh"
```

배포 성공 뒤 PetaLinux에서:

```sh
sudo sh /opt/fft128/e14_frame/load_board.sh
```

이전 E13 드라이버/overlay가 활성 상태면 load script가 중단한다. 다른 ABI 펌웨어를 사용 중인 드라이버에
올리지 않도록 기존 결과를 보존하고 새로 부팅한 상태에서 실행한다. 빌드·번들·배포 스크립트는 보드를 재부팅하지 않는다.

`FRAME_MATRIX_PASS`, `DMA_FRAME_CLIENT_PASS`, `SELFTEST_PASS backend=PL_DMA_FRAME`,
`DMA_E14_FRAME_SELFTEST_READY` 이후 별도 20회 frame profile와 각300회 PS double/NEON/PL 비교를 진행한다.
[전체 실행·수집 절차](../../../src/PS/fft128/dma_frame/README.md), [E14 실행 기록](../../../docs/experiment_log.md#e14-frame--pl-전치와-전체-프레임-dma-진행-중).
