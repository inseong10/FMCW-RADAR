# E13-stream — 7단계 프레임 스트리밍 FFT

E13-bf2의 보드 결과(전체중앙값2.841720ms/profile PL0.837903ms)를 보존하고,
반복형4코어를 전용7단계 DIT 파이프라인 하나로 교체하는 별도 실험이다.
각 단계는128샘플 프레임을 버퍼링하며 다른 chirp가 앞뒤 단계에서 동시에 계산된다.
블록버퍼를 사용하는 frame pipeline이며, 개별sample의SDF지연선 구조로 측정하지 않는다.

## 구조와 비교 범위

```text
단일 DMA MM2S → stage0 → stage1 → … → stage6 → 단일 DMA S2MM
               입력/출력 각각 두128word frame slot / 단계당 butterfly 하나
```

stage0이입력을 bit-reversed 주소로저장하고 이후단계와출력은 natural index순서다.
모든 stage의 butterfly_pipeline/twiddle/Q15/포화·단계별1/2스케일은 기존파일을사용한다.
각 stage는 input slot 두개/output slot 두개로 fill·CALC·drain을겹친다.
한 frame의64 butterfly를1pair/clock으로발행하고68 CALC clocks를사용한다.
완성출력slot만읽고마지막출력handshake후소유권을해제하므로backpressure에서도보존된다.
전단ready에대기가전파되고RAM내용을reset할필요없이소유권·valid만초기화한다.

하나의파이프라인에7개전용버터플라이가있다. 기존4개코어의2연산기를그대로두고추가하는실험은아니다.
코어배치/버퍼/내부출력cadence도함께바뀌는구조비교로기록한다.
외부AXIS32/HP0 64-bit/단일Simple DMA,50 MHz,축당128 FFT/64 KiB,
PS coherent복사·전치·정규화·전체측정경계는유지한다.
FIFO lane8개대신각stage4개작업RAM,전체28RAM을사용한다.
합성전상한은DSP28개이며상수twiddle최적화후실제개수와BRAM/LUT·50 MHz타이밍은Vivado에서확인한다.

## 로컬 검증

272벡터/34,816 complex bins가 독립정수모델과완전히일치한다.
각stage/FFT issue64/retire64/CALC68,메모리slot접근충돌0,지속 frame II128clocks를검사했다.
부분/전체/반복packet,입력정체/8000클록출력정체,stalled payload,
malformed TLAST/TKEEP,독립AW/W·AXI응답정체,blocked partial pipeline abort/recovery도PASS다.
기존serial/pipeline/E11a/E11b/E13-2core/4core/E12/E13-bf2 전체RTL회귀도재실행PASS다.
host43개회귀 PASS다.
Linux userspace구문/고정ABI배치는Windows shim검사이며실제ARM모듈빌드와는별개다.

무정체RTL축당17770cycles/두축35540cycles/50 MHz=0.710800ms다.
E13-bf2의동일모델0.837200ms보다15.097946% 짧다. 실제전체보드성능은아직미측정이다.
한FFT의축처리1514cycles로첫결과지연은커진다. 파이프라인이찬후FFT마다128cycles간격이다.
첫결과와연속처리량을구분하고부팅/바이너리/메타데이터·실제stage카운터를보드에서다시검증한다.

## ABI7과 계측

ID0x46545087/register ABI7,compatible`fmcw,fft128-dma-stream-v7`,
module`fft128_dma_stream`,device`/dev/fft128-dma-stream`,ioctl0x17이다.
112B header/input112/output65648/extra131184/request131272B다.
추가88B는PROFILE일때만복사하며비계측header/payload복사량은기준과같다.

| 주소 | 의미 |
|---|---|
|0x30|스트리밍 FFT pipeline수1|
|0x34/0x44|pipeline occupied clocks/동일union값|
|0x38..0x58|이전multi-lane계측용예약값0|
|0x5c|외부입력·출력동시handshake|
|0x60/0x64/0x68|입력·CALC/출력·CALC/세동작동시(clocks)|
|0x6c|전용stage수7|
|0x70|모든stage의CALC clocks합|
|0x74|2개이상stage에서동시에실제CALC|
|0x78|완료입력FFT−완료출력FFT가2이상인clocks|
|0x80..0x98|stage0..6의실제issue횟수|
|0xa0..0xb8|stage0..6의실제retire횟수|

128FFT축에서stage별issue/retire8192,stageCALC합60928이다.
두축frame은각stage16384/총CALC121856이다. stage합은벽시간에더하지않는다.
잘못된TLAST가in-flight개수를바꾸지않도록샘플handshake128개단위로벡터수를계산한다.

## 빌드와 보드 실행

```powershell
python src/PL/fft128_ps/verify_dma_stream.py
python src/PS/fft128/dma_stream/test_tools.py
```

Vivado2022.1 Tcl:
```tcl
source /home/user/fmcw_share/FMCW-FFT-test/src/PL/fft128_ps/build_dma_stream.tcl
```

`FFT128_DMA_STREAM_BUILD_PASS`,ARM로그`E13_STREAM_ARM_BUILD_PASS`를확인한다.
생성reset IP/ID/ABI7/7stage,실제DSP/BRAM및50 MHz setup/hold를검증한뒤Ubuntu에서:
```bash
P="$HOME/fmcw_share/FMCW-FFT-test"
bash "$P/src/PS/fft128/dma_stream/prepare_bundle.sh" &&
bash "$P/src/PS/fft128/dma_stream/deploy.sh"
```

기존bf2드라이버/overlay가있으면보드를재부팅한뒤PetaLinux에서:
```sh
sudo sh /opt/fft128/e13_stream/load_board.sh
```
`STREAM_STAGE_PASS`/각stage`STREAM_ARITHMETIC_PASS`/`DMA_E13_STREAM_SELFTEST_READY`를확인한뒤:
```sh
B=/opt/fft128/e13_stream
sudo sh "$B/profile_board.sh" "$B/profile_e13_stream_01" &&
sudo sh "$B/run_board.sh" "$B/results_e13_stream_01"
```
Ubuntu수집:
```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/src/PS/fft128/dma_stream/collect_results.sh"
```
20회별도profile/CPU0/warmup10/각300회double·NEON·PL회전비교다.
이전결과·펌웨어는새경로로보존하며연속UDP/최악지연/드랍0은별도검증한다.
[기준bf2결과](../../../../benchmarks/reports/2026-11-21-e13-bf2-board/README.md).

[로컬 준비·원본로그·소스SHA](../../../../benchmarks/reports/2026-11-21-e13-stream-preparation/README.md).


## Build follow-up — 2026-11-21

Actual ARM32 receiver/client/module, generated reset IP/ABI7/stage7 and Vivado50MHz setup/hold now PASS.
Routed seven dedicated stages use28DSP/31BRAM tiles overall; WNS10.401/WHS0.024ns.
Sources/artifacts are independently verified; live-board self-test/performance remain pending.
See [build results](../../../../benchmarks/reports/2026-11-21-e13-stream-build/README.md). Earlier pending text preserves the preparation stage.


## Board measurement follow-up — 2026-11-21

Full-frame/profile20/paired300 and raw identity/accuracy/stage counters/IRQ validation now PASS.
PL median2.787411ms / paired NEON3.652869ms / double5.826396ms.
PL active0.711424ms (15.09% shorter than earlier bf2); whole median1.91% shorter across different boots.
Non-PL profile costs increased; preserve this limitation and the distinct timing populations.
See [final board results](../../../../benchmarks/reports/2026-11-21-e13-stream-board/README.md). Earlier pending statements preserve their original stages.
