# E11a DMA 전환 — 구현 및 사전 검증

기록 날짜: 2026-11-16, 개발 PC 기준. **보드 DMA 측정 보고서가 아니다.**
기존 [E10 pipeline/50 MHz](../2026-11-15-pipeline50-benchmark/README.md)와
[PS01](../2026-11-15-ps01-board/README.md)을 보존하고 샘플 전송만 변경한다.

## 질문과 변경

E10의 입력/출력 MMIO 평균 20.378 ms를 줄이기 위해 FFT당 512 B 양방향 Simple DMA를
준비한다. 한 번의 ioctl로 한 FFT, 프레임 256회다. 작은 전송의 드라이버 고정 비용도 측정한다.
기존 core/50 MHz/Q15/PS gather-scatter는 유지하며 E11b 묶음 제출은 포함하지 않는다.
기존 PL 내부 4.408320 ms가 PS01 전체 중앙값 3.615852 ms보다 길므로 DMA만으로
PS를 이긴다는 가설은 세우지 않는다.

- PL: control-only AXI-Lite + AXIS 앞단, AXI DMA 7.1 Simple, HP0 64-bit/stream 32-bit,
  burst 16, SG/DRE off, length width 17. 기존 보드 MMCM 50 MHz와 V3 reset을 유지한다.
- 제어/IRQ: FFT 0x43c60000 / ID 0x46544480 / ABI 1, DMA 0x40400000,
  F2P6/7 → DT SPI35/36. 기록 DT의 기존 VTC/영상 IRQ와 겹치지 않게 선택했다.
- 소프트웨어: DMAengine client가 coherent TX/RX bounce buffer를 소유한다.
  PS 전치는 cached 배열에서 하고, 필요한 user/kernel/coherent 복사는 전체 시간에 포함한다.
  1,096-byte 고정 폭·포인터 없는 ioctl, 단일 소유권, 완료/입출력 개수/오류 검사를 사용한다.
- 계측: host copy/ioctl/전치와 nested kernel copy/submit/wait/check를 구분한다.
  PL active 카운터는 스트림 정지를 포함하고 input/output stall을 별도 기록한다.
  kernel/PL 구간을 host ioctl에 다시 더하지 않는다.

## 증거와 확인 범위

| 항목 | 확인 결과 |
|---|---|
| 기존 처리 로직 | E10의 산술 RTL 5개 및 native_core.c와 LF 정규화 SHA256 동일 |
| 새 RTL 앞단 | 272 FFT/34,816 complex bin 정수 모델 일치 |
| 프로토콜 | AXIS input gaps/output backpressure·stalled payload 유지, TLAST/TKEEP 오류 flag, partial-load/compute abort 후 복구, 독립 AW/W와 B/R 응답 정지 PASS |
| 사이클 계측 | 지연 유무 모두 active − input stall − output stall = 861 cycles/FFT, RTL 확인 |
| 기존 RTL 회귀 | serial/pipeline stream/AXI PASS, 기준 cycle 3073/861 유지 |
| PC C 회귀 | 기존 9개 PASS, 새 CLI/DT/계측 분석기 11개 PASS |
| Ubuntu 초기 빌드 | ARMv7 hard-float 정적 DMA 수신기 빌드 PASS; 실제 DMA 실행 아님 |
| DT 오프라인 적용 | 기록한 running DT에 dtc/fdtoverlay 적용 및 새 노드 compatible 확인 PASS |
| 커널 | 후보 커널/ARM 모듈 빌드 PASS; 현재 보드 커널에서 대응 DT 없이 정상 load/unload 및 CRC 수락 PASS |
| Vivado reset | 실제 generated reset IP/AXI ID·length/lock-loss recovery PASS (done=1 passed=1) |
| Vivado/보드 DMA | 합성·route·타이밍·자원·보드 ABI/self-test/frame/profile/비계측 비교 미확인 |

`result.json`, `dma_ctrl_tb.log`, `baseline.log`, `compile.log`는 RTL 증거다.
`software_tests.json`은 개발 PC에서 실행한 검사 요약이다. 입력은 기존 pinned fixture이며
SHA256은 `aa06ff124034310216693c1398f2f1061c9a6ce32e9ea6f5687675849934c976`이다.
RTL tone 프레임의 NumPy 오차 약 5.11 LSB는 과거와 동일한 수치 회귀이며 새 보드 정확도가 아니다.

`board_probe.json`과 작은 조회 파일은 보드 설정 근거이며 전송 검증이 아니다.
조회 시 CMA total/free는 16,384/16,096 KiB, GIC phandle 4, root cells 1/1이다.
원래 커널은 GCC 11.2.0으로 빌드됐고 Ubuntu의 후보 빌드는 GCC 9.4.0이다.
BSP는 Digilent 브랜치/AUTOREV를 지정했으므로 원래 부팅 커널과 소스가 같다고 확정하지 않는다.
현재 보드의 정상 모듈 로딩은 CRC 검사를 통과했다(`module_crc_console.log`, 사용자 콘솔 근거).
이것은 모듈이 참조하는 커널 인터페이스 호환 확인이며 원래 커널 전체의 소스 provenance나 DMA 전송 증명은 아니다.

`ubuntu_initial_*`는 당시 수신기/overlay 빌드 artifact와 소스 신원이다.
이후 ABI 검사기/신원 검사를 포함한 최종 작은 빌드를 완료했다(`ubuntu_final_*`, `module_final_*`).
현재 체크아웃의 실제 파일 SHA를 두 source manifest와 대조해 일치함을 확인했다.
과거 binary 해시를 최신 소스 빌드 해시라고 대체하지 않는다.
단순 스크립트/설치 환경 오류는 이 실험 기록에 포함하지 않는다.

## 다음 확인 순서

1. **완료:** 후보 full kernel/Module.symvers 및 DMA 모듈 빌드.
2. **완료:** 대응 DT 없이 실제 보드 모듈 정상 로드/언로드·CRC 수락. FPGA 접근 없음.
3. **진행:** Vivado `build_dma.tcl`: 실제 generated reset IP → 합성/route → setup/hold/clock 확인 → bitstream/XSA.
4. 별도 E11a bundle 배치 후 firmware → overlay → module → ABI 검사/4벡터 self-test.
5. 실제 프레임 16,384-bin bit-exact → 별도 warmup 2/20회 profile →
   CPU0, warmup 10, PS double/NEON/PL 각 100회×3, 회전 순서로 비교한다.
6. 모든 반복 결과와 입력/소스/펌웨어/실행 파일 해시를 회수해 NumPy 정확도·중앙값/분위수를 검증한다.

현재 E11a의 latency·가속비·사용 자원·routed slack은 없다.
[실행 도구/측정 계약](../../../src/PS/fft128/dma/README.md),
[실험 일지](../../../docs/experiment_log.md), [계획과 예상 범위](../../../docs/fft128_dma_plan.md).

후속: [E11a 구현 보고서](../2026-11-16-e11a-build/README.md)에서 동일 50 MHz bitstream/XSA·타이밍·자원 검증을 완료했다. 위 합성/구현 대기 상태는 해소됐고 보드 DMA 측정은 남아 있다.
