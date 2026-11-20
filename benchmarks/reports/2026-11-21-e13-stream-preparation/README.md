# E13-stream preparation — 2026-11-21

**7단계 프레임 스트리밍 구현·코어/전체RTL회귀·host43개 PASS. ARM/Vivado/보드 미검증.**

## 문제·구조·고정 조건

사용자는E13-bf2완료후여러chirp의FFT단계를겹치는스트리밍을요청했다.
기준bf2는FFT4코어각2butterfly,보드전체중앙값2.841720ms/별도PL active0.837903ms다.
이번에는단일FFT pipeline에7개DIT stage를전용butterfly하나씩으로펼친다.
각stage의입력2/출력2 frame slot(각128word TDP RAM)으로fill·CALC·drain을겹친다.
전용stage가다른FFT를동시에계산하며,stage0의bit-reverse입력후natural출력을유지한다.

각stage는완성128샘플블록을버퍼링하는frame pipeline이다. 단일sample SDF지연선설계로측정하지않는다.
4개기존FFT코어를고정한변경이아니며코어배치/버퍼/내부출력cadence가함께바뀌는구조비교다.
기존총8 butterfly에서전용7개로바뀐다. 합성전DSP상한28이며상수twiddle최적화후실제자원은미확인이다.
논리작업RAM28개/제어·버퍼소유권이필요하며실제BRAM/LUT/FF/50MHz타이밍은Vivado를기다린다.

butterfly_pipeline/fft128_twiddle/fft_working_ram/address_generator의소스는그대로다.
Q15반올림·포화·단계별1/2스케일/50MHz,단일Simple DMA·AXIS32/HP0 64/축128FFT·64KiB,
2ioctl·4채널/PS coherent복사·전치/전체측정경계를유지한다.
`external_buffers=false,stage_frame_slots=true,buffering=per_stage_double_frame_slots`로
이전외부laneFIFO와구분한다. PS복사최적화/PL전치/정밀도·클록변경은포함하지않는다.

## 검증 결과

- `core.log`:272벡터/34,816complex bins가독립정수oracle과완전일치한다.
  stage/FFT마다64issue/64retire/68CALC,메모리slot동시접근충돌0이다.
  272FFT연속출력의frame간격128clocks를직접assert했다. 8000clock출력정체/입력gap,
  stalled payload/TLAST 오류flag/활성부분pipeline reset후정수복구도PASS다.
- `dma.log`:272벡터,1/2/3/4/5/16/127/128부분·전체·반복축,입력starvation,
  8000clock출력정체,외부축TLAST/TKEEP 오류,독립AXI AW/W/응답정체·금지된주소/설정거부,
  출력이막힌부분pipeline abort/recovery를검사했다. 입력/출력순서는정확히보존한다.
- stage별8192issue/8192retire와CALC합60928/128FFT축을직접검증했다.
  무정체128FFT에서실제여러stage동시CALC16640cycles/여러in-flight frame17386cycles다.
  stage/프레임겹침을코어수나단순busy추정으로대체하지않는다.
- `baseline.log`:기존serial/pipeline/E11a/E11b/E13-2core/4core/E12/E13-bf2 전체RTL회귀PASS.
  `result.json`의baseline_rerun=true는최종전체실행이다.
- host43개: native9/E11b3/E13-2core4/E13-4core5/E12계측7/bf2계측7/stream계측8 PASS.
  실제C CSV/batch export와stage발행·완료보존/계측중첩/불가능한겹침·잘못된메타데이터거부다.
  최종stream8개는내부stage버퍼metadata와카운터상한추가후다시PASS(`dma_stream_tests_final.log`).
- Python compile/bash10 syntax/Tcl info-complete,기록live-DT overlay생성,
  이전ABI5/6 bundle과잘못된stage/core/II식별거부,빌드/번들보고서파일명일치PASS다.
  Linux userspace C구문/112B header·131272B request 검사는Windows host shim이며ARM빌드가아니다.

## 사이클 모델과 한계

| 외부정체0/동일50MHz | E13-bf2 | E13-stream |
|---|---:|---:|
| 축당128FFT |20930cycles|17770cycles|
| 두축PL환산 |0.837200ms|0.710800ms|

PL모델은15.097946%단축이다. 입력valid를CONTROL 전에준비하고출력ready를유지해
input/output stall0 및17770cycles를직접assert했다. stall을빼서순수계산으로추정하지않았다.
단일FFT축은1514cycles이며첫결과지연은크다. 파이프라인이찬후지속II128과구분한다.
실제AXI DMA IP/DDR/IRQ·PS복사·전치·실제모듈·전체보드성능은이모델에없다.
이전보드0.837903ms와새모델을전체성능비로비교하지않으며전체가15.1%짧아진다고주장하지않는다.

## 초기 실패와 수정

첫core실험은정상272벡터·정체128벡터를통과했으나malformed TLAST뒤in-flight가1남아
empty검사에실패했다. counter가입력TLAST를그대로신뢰한것이원인이다.
128번째sample handshake로vector수를세도록바꾼뒤flag/empty·복구까지PASS했다.
`core_initial_malformed_counter_failure.log`를보존한다.

첫DMA bench는동시AXI write task두개가같은버스신호를구동해B응답검사에실패했다.
단일writer에서순서대로명령을발행하도록bench를고쳤고,AW/W별도지연과응답정체검사는유지했다.
`dma_initial_test_axi_driver_overlap.log`를보존한다. 최종기능/성능기준을완화하지않았다.

## ABI·다음 단계

ABI7/ID0x46545087/device`fft128-dma-stream`,header112/input112/output65648/extra131184/request131272B.
추가88B는PROFILE일때만복사한다. stage별issue/retire7개씩,stageCALC합/multi-stage CALC/
2개이상in-flight vectors 및실제입력·출력·CALC겹침을계측한다. stage합은벽시간과합산하지않는다.

Vivado2022.1 Tcl:
```tcl
source /home/user/fmcw_share/FMCW-FFT-test/src/PL/fft128_ps/build_dma_stream.tcl
```

ARM빌드를병행한다. 생성reset IP/ABI7/stage7/실제DSP·BRAM·LUT/50MHz setup·hold후
정상board insmod/self-test/frame20profile/각300회paired를별도경로로검증한다.
[빌드·배포·보드절차](../../../src/PS/fft128/dma_stream/README.md),
[기준bf2보드](../2026-11-21-e13-bf2-board/README.md),[실험 일지](../../../docs/experiment_log.md).

`intended_dma_config.json`/DTS/overlay metadata는의도/오프라인생성으로실제Vivado/보드가아니다.
source_sha256.json은현재구현/검증/도구, evidence_sha256.json은보존로그의신원이다.
raw는ignored `build/fft128_streaming_verify`/`build/fft128_dma_stream_preparation`에있다.
아직새bitstream·ARM산출물·보드성능은없다. 이전결과/펌웨어는덮어쓰지않는다.

재현:
```powershell
python src/PL/fft128_ps/verify_dma_stream.py
python src/PS/fft128/dma_stream/test_tools.py
```


## Build follow-up — 2026-11-21

Actual ARM32 receiver/client/module, generated reset IP/ABI7/stage7 and Vivado50MHz setup/hold now PASS.
Routed seven dedicated stages use28DSP/31BRAM tiles overall; WNS10.401/WHS0.024ns.
Sources/artifacts are independently verified; live-board self-test/performance remain pending.
See [build results](../2026-11-21-e13-stream-build/README.md). Earlier pending text preserves the preparation stage.


## Board measurement follow-up — 2026-11-21

Full-frame/profile20/paired300 and raw identity/accuracy/stage counters/IRQ validation now PASS.
PL median2.787411ms / paired NEON3.652869ms / double5.826396ms.
PL active0.711424ms (15.09% shorter than earlier bf2); whole median1.91% shorter across different boots.
Non-PL profile costs increased; preserve this limitation and the distinct timing populations.
See [final board results](../2026-11-21-e13-stream-board/README.md). Earlier pending statements preserve their original stages.
