# E13-bf2 preparation — 2026-11-20

**코어당 버터플라이2개 구현, 코어/전체RTL회귀·host35개 PASS. ARM/Vivado/보드 미검증.**

## 변경과 고정 조건

E12-4core의 FFT4개·독립 입력/출력 FIFO·스케줄을 유지하고 코어당 butterfly_pipeline을1→2개로 늘렸다.
각 stage의64 butterfly를32 pair로 발행한다. 동시4 read/4 write를 위해 ping-pong 작업RAM을
짝수/홀수64word true-dual-port bank로 나눈다. stage0은 A0/A1→even,B0/B1→odd,
stage1..6은 BF0→even,BF1→odd다. butterfly_pipeline과twiddle 값은 기존 파일을 그대로 사용한다.

50 MHz/Q15/단계별1/2스케일·포화/출력순서/코어출력2clocks/sample, 4개FFT코어,
단일 AXIS32 DMA/HP0 64-bit/축당64KiB, coherent복사/PS전치/측정경계는 같다.
RAM분할·두twiddle ROM은 연산기 병렬 접근을 위한 변경에 포함된다.
E11c 출력 cadence/E11d 복사/E14 PL전치/스트리밍 FFT는 함께 적용하지 않았다.

## 검증 근거

- `bf2_core_tb.log`:272벡터/34,816 complex bins가 기존 코어 및 독립 정수 oracle과 완전 일치한다.
  stage당32 issue/retire pair, FFT당224 pair, 메모리 접근 충돌0, 두연산기 valid 정렬을 검사했다.
  입력gap/출력정체·stalled payload·잘못된 TLAST도 포함한다.
- `dma_bf2_ctrl_tb.log`:272벡터, 1/2/3/4/5/6/7/127/128 FFT 배치, 전체·반복축,
  TLAST/TKEEP 오류, AXI AW/W 독립성과 응답정체, 금지된접근, 중단복구 PASS다.
  8000cycles 출력정체 후128 FFT 전량배출, FIFO용량·전체FFT 출력예약을 매클록 검사했다.
  입력/계산/정체출력/full-buffer abort/recovery, source-starved 완료도 포함한다.
- `baseline.log`: serial/pipeline/E11a/E11b/E13-2core/E13-4core/E12 기준선을 모두 재실행했다.
  최종 `result.json`의 `baseline_rerun=true`는 이번 전체 실행을 나타낸다.
  상속된 `serial_cycles=3073`/`pipeline_cycles=861`은 원래 단일코어 기준값이며 bf2값이 아니다.
- host35개(native9/E11b3/E13-2core4/E13-4core5/E12계측7/bf2계측7): 실제 C profile CSV/batch JSON,
  all-work=0 허용, 정확한 두연산기 issue/retire/CALC 값 및 불가능한카운터 거부 PASS다.
- Python compile/bash10 syntax/Tcl `info complete`, 기록 live-DT overlay 생성,
  기존E12 bundle/잘못된연산기수·ABI 거부, bundle의보고서경로와Tcl출력일치 PASS다.
  Linux userspace C구문/112B헤더·131240B요청 배치는 Windows host shim으로 검사했다.
  ARM 컴파일·실제DT적용·Vivado Tcl 실행을 대신하지 않는다.
- `local_checks.json`에 고정한 산술/FIFO/기존코어/전치소스의 E12대비SHA 일치를 기록했다.
  컴파일로그의 경고는 기존RTL에 명시적 time unit이 없는 경우이며 테스트벤치에는 timescale이 있다.

## 사이클 결과와 한계

| 동일 범위 | E12-4core | E13-bf2 |
|---|---:|---:|
| 코어CALC/FFT |476cycles|252cycles|
| 128 FFT축, 외부정체0 |28098cycles|20930cycles|
| 두축/50 MHz 환산 |1.123920ms|0.837200ms|

CALC는47.06%, PL 두축모델은25.51% 단축됐다. zero-stall 테스트는 CONTROL 전에 입력valid를 준비하고
출력ready를 유지해 input/output stall0과20930cycles를 직접 assert한다. 카운터를 빼서 추정하지 않았다.
별도21cycles 초기대기가 있는 fixture는20951cycles이며 같은 값으로 혼동하지 않는다.

CALC가짧아져 해당무정체fixture의 동시FFT CALC는최대2개/all-work0이다. 이것을 실패로 취급하거나
4개FFT 동시CALC를 강제하지 않는다. 각코어에서 두butterfly의 issue/retire를 직접 관측한다.
입력·실제CALC·출력 동시13453cycles와 next-vector prefetch도 확인했다.
느린source fixture에서는 동시CALC가1개여도 결과가 정확히 끝나야 한다.

ABI6/ID0x46545086은 butterflies_per_core=2, 집계issue/retire/CALC lane-cycles를 추가한다.
FFT당224pair(448butterfly)/252CALCcycles, 두축57344pair/64512CALC lane-cycles다.
코어별시간의 합은 벽시간을 넘을 수 있으며 active시간과 합산하지 않는다.
요청131240B 중 추가계측56B는 PROFILE에서만 복사하며 비계측복사경로는 유지한다.

실제 보드의 새 전체성능은 미측정이다. 기준E12 중앙값3.129210ms/별도profile active1.124590ms를
새0.837200ms와 직접 전체성능비로 비교하지 않는다. 실제DMA/DDR/IRQ/PS복사·전치는 모델에 없다.
DSP목표32개이며 실제 DSP/BRAM/LUT/FF·50MHz setup/hold·생성reset IP·ARM모듈·보드 검증은 남았다.

## 재현과 다음 단계

```powershell
python src/PL/fft128_ps/verify_dma_bf2.py
python src/PS/fft128/dma_bf2/test_tools.py
```

Vivado2022.1 Tcl:
```tcl
source /home/user/fmcw_share/FMCW-FFT-test/src/PL/fft128_ps/build_dma_bf2.tcl
```

ARM빌드를 병행하며 `FFT128_DMA_BF2_BUILD_PASS`/`E13_BF2_ARM_BUILD_PASS`를 확인한다.
[번들·보드·수집 절차](../../../src/PS/fft128/dma_bf2/README.md)에 따라 자체검사,
20회profile/각300회double·NEON·PL paired 결과를 별도경로에 보존한다.
이 결과를 확인한 뒤 사용자가 요청한 스트리밍 FFT를 별도 실험으로 진행한다.

`intended_dma_config.json`과DTS/metadata는 의도설정/오프라인생성이며 실제Vivado/보드상태가 아니다.
`source_sha256.json`은 현재구현·도구·검증소스, `evidence_sha256.json`은 보존로그의 신원이다.
ignored raw build는 `build/fft128_dma_bf2_verify`/`build/fft128_dma_bf2_preparation`에 있다.
펌웨어 바이너리는 아직 없다. [실험 일지](../../../docs/experiment_log.md),
[기준E12실측](../2026-11-20-e12-4core-board/README.md).


## Board measurement follow-up — 2026-11-21

Full-frame/profile20/paired300 and raw identity/accuracy/counters/IRQ validation now PASS.
PL median2.841720ms / paired NEON3.520371ms / double5.708112ms.
Profile PL active0.837903ms; two-butterfly issue/retire/CALC counts match exactly.
See [final board results](../2026-11-21-e13-bf2-board/README.md).
Earlier pending statements preserve the preparation/build stages.
