# E13-bf2: 코어당 버터플라이 두 개

E12-4core 완료 구성을 고정하고 각 FFT 코어의 버터플라이를1→2개로 늘리는 실험이다.
전체 FFT 코어4개/버터플라이8개다. 스트리밍 FFT는 이 결과를 확인한 뒤 별도 실험으로 진행한다.

## 구조와 고정 조건

128-point radix-2 DIT의 stage당64 butterfly를32 pair로 발행한다.
각 ping-pong 작업메모리를 짝수/홀수 주소의64word dual-port RAM으로 나누어
매클록4 sample read/4 sample write를 지원한다. stage0은 A0/A1→even,B0/B1→odd,
stage1..6은 butterfly0→even,butterfly1→odd로 라우팅한다.
기존 butterfly_pipeline의 곱셈 정밀도·포화·stage별1/2스케일을 그대로 사용한다.

4코어/E12 입력·출력 FIFO 및독립스케줄,50 MHz,코어출력2clocks/sample,
단일Simple DMA/HP0 64-bit/AXIS32-bit,축당64 KiB/coherent복사/PS전치/측정경계를 유지한다.
연산기 확대를 지원하는RAM분할과twiddle ROM두개는 이번변경의 일부다.
E11c cadence/E11d복사/E14전치/스트리밍은 함께 적용하지 않는다.

## 검증 상태

코어 단독272벡터/34,816complex bins가 기존코어와 독립정수oracle 모두에 완전 일치한다.
stage별32pair발행·32pairretire와메모리충돌0을 검사했다.
CALC는기존476→252cycles/FFT다. 코어출력과LOAD시간은 그대로다.
DMA앞단 전체검증도부분배치/오류/정체/중단복구/실제두버터플라이 PASS다.
기존 serial/pipeline/E11a/E11b/E13/E12 RTL회귀와host35개도 PASS다.
ARM/Vivado/보드 검증은 아직 전이다.
[검증 로그·소스 신원](../../../../benchmarks/reports/2026-11-20-e13-bf2-preparation/README.md).

외부정체0 RTL구성은20930cycles/axis,두축/50 MHz로0.837200ms다.
E12 모델1.123920ms 대비약25.5% 내부단축이며 전체보드성능은 미측정이다.
빨라진 CALC로4개 FFT의계산창이동시에겹치지않아도정상이다.
대신 코어별두버터플라이의발행/retire와CALC시간을직접계측한다.

## ABI와 계측

ID0x46545086/register ABI6,compatible`fmcw,fft128-dma-bf2-v6`,
모듈`fft128_dma_bf2`,장치`/dev/fft128-dma-bf2`다.
header112/input112/output65648/extra131184/request131240B다.
추가56B는PROFILE에서만 반환하며 비계측payload·header복사량은 기준과같다.
기존0x00..0x68 카운터는 E12 의미를 유지한다.

| 레지스터 | 의미 |
|---|---|
|0x6c|코어당 버터플라이 수2|
|0x70|모든코어의 dual-issue pair 횟수 합|
|0x74|모든코어의 dual-retire pair 횟수 합|
|0x78|모든코어의 실제 CALC 상태 사이클 합|

FFT하나당 issue/retire224pair,실제CALC252cycles다.
128FFT축은각28672pair/32256CALC lane-cycles,
두축프레임은각57344pair/64512CALC lane-cycles다.
이카운터는코어별값의합이므로벽시계cycles를넘을수있고global active에더하지않는다.
all-work0도허용하며work-window에는첫RAM출력읽기1clock이포함된다.

## 실행

Windows:
```powershell
python src/PL/fft128_ps/verify_dma_bf2.py
python src/PS/fft128/dma_bf2/test_tools.py
```
Vivado Tcl:
```tcl
source /home/user/fmcw_share/FMCW-FFT-test/src/PL/fft128_ps/build_dma_bf2.tcl
```
`FFT128_DMA_BF2_BUILD_PASS`와 ARM로그`E13_BF2_ARM_BUILD_PASS`를확인한다.
생성reset IP/ID/ABI6/버터플라이2개레지스터·실제DSP32개·50 MHz setup/hold를검사한다.
기존펌웨어·측정은보존하며새경로는모두`dma_bf2`/`e13_bf2`다.

Ubuntu 빌드 후:
```bash
P="$HOME/fmcw_share/FMCW-FFT-test"
bash "$P/src/PS/fft128/dma_bf2/prepare_bundle.sh" &&
bash "$P/src/PS/fft128/dma_bf2/deploy.sh"
```
기존E12모듈/overlay가있으면보드를재부팅한후 PetaLinux에서:
```sh
sudo sh /opt/fft128/e13_bf2/load_board.sh
```
`BF2_ARITHMETIC_PASS`와`DMA_E13_BF2_SELFTEST_READY`까지확인한다.
그다음 PetaLinux:
```sh
B=/opt/fft128/e13_bf2
sudo sh "$B/profile_board.sh" "$B/profile_e13_bf2_01" &&
sudo sh "$B/run_board.sh" "$B/results_e13_bf2_01"
```
Ubuntu 수집:
```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/src/PS/fft128/dma_bf2/collect_results.sh"
```
측정계약은기존과같은20회profile/CPU0/warmup10/repeat100×3회전PSdouble·NEON·PL이다.
E12와보드세션이달라지므로PS기준도다시측정한다.연속UDP처리량은이실험밖이다.


## Board measurement follow-up — 2026-11-21

Full-frame/profile20/paired300 and raw identity/accuracy/counters/IRQ validation now PASS.
PL median2.841720ms / paired NEON3.520371ms / double5.708112ms.
Profile PL active0.837903ms; two-butterfly issue/retire/CALC counts match exactly.
See [final board results](../../../../benchmarks/reports/2026-11-21-e13-bf2-board/README.md).
Earlier pending statements preserve the preparation/build stages.
