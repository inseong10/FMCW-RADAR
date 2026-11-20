# E13-stream Vivado/ARM build — 2026-11-21

**전용7단계 프레임 스트리밍의 실제구현·50 MHz 타이밍·ARM빌드 PASS. 보드 검증 대기.**

Run: `fft128_dma_e13_stream_20261121_004729`.
PL/host/module source SHA는현재checkout·공유소스와일치하며 host/module artifact manifest도독립검증했다.
XSA의bitstream은구현run의bitstream과SHA가같다. source/binary/DCP신원은implementation.json에기록했다.

- 50 MHz setup WNS10.401ns / hold WHS0.024ns, setup/hold/pulse-width failing endpoints0.
  no-clock register/latch0, maximum-delay unconstrained pin0, 모든 사용자 타이밍 제약 만족.
- LUT6089/17600(34.60%), FF6259/35200(17.78%), BRAM31/60(51.67%), DSP28/80(35%).
  기준E13-bf2는LUT7428/FF6555/BRAM23/DSP32다. LUT1339/FF296/DSP4가줄고BRAM8이늘었다.
- 실제계층stage[0]..stage[6]은각각DSP4/RAMB36 4개다. butterfly가단계마다1개씩총7개,
  입력slot2개/출력slot2개×7단계의28개RAM은각각RAMB36 1개로구현됐다.
- 생성BD의FFT외 PS7/DMA/clock/reset/interconnect/IRQ 컴포넌트와전체interface/scalar
  ports/nets·addressing은기준E13-bf2와완전히같다. 50MHz/AXIS32/HP0 64/Simple DMA,
  SG·DRE off/burst16/length17/F2P6·7을유지한다.
- 실제생성reset IP의simulation done1/passed1이다. ID/FFT크기/ABI7/스트리밍코어1/stage7,
  초기계측값과lock-loss recovery를검사했다. 생성VHDL의external active-low/aux active-high도확인했다.
- ARM32 static receiver/client ELF와준비커널5.15.19-xilinx/SMP/preempt/modversions/ARMv7
  module ELF가빌드됐다. 정상보드insmod가symbol CRC를수용하는지는아직미확인이다.
- prepare_host의dtc와기록base-DT fdtoverlay/fdtget 검증이끝났다. 독립dtc GIC phandle경고는
  host_dtc.log에보존했다. live overlay 적용·실제DMA는아직전이다.

프레임간격II128과0.710800ms는앞선RTL모델로검증한값이며Vivado자원보고서로보드성능을추정하지않는다.
실제board stage issue/retire 보존·multi-stage CALC·in-flight vectors와전체frame/profile/paired는남았다.
큰bitstream/XSA/DCP/ARM바이너리는공유ignored build/에유지하며compact로그·정확한SHA만보존한다.
생성metadata board_verified:false와implementation.json의build-only범위도그대로보존한다.

Ubuntu번들생성·배포:
```bash
P="$HOME/fmcw_share/FMCW-FFT-test"
bash "$P/src/PS/fft128/dma_stream/prepare_bundle.sh" &&
bash "$P/src/PS/fft128/dma_stream/deploy.sh"
```

배포성공후기존E13-bf2 DMA모듈/overlay를비우도록보드를재부팅하고PetaLinux에서:
```sh
sudo sh /opt/fft128/e13_stream/load_board.sh
```

STREAM_STAGE_PASS/각stage STREAM_ARITHMETIC_PASS/DMA_E13_STREAM_SELFTEST_READY후
별도20회frame profile/각300회double·NEON·PL paired를진행한다.
[전체보드 절차](../../../src/PS/fft128/dma_stream/README.md),
[로컬준비 결과](../2026-11-21-e13-stream-preparation/README.md),
[기준bf2보드](../2026-11-21-e13-bf2-board/README.md).


## Board self-test follow-up — 2026-11-21

사용자가제공한부분PetaLinux콘솔에서 packet1/2/3/4/5/127/128/128 및소유권·ABI/timeout/flags/count거부,
receiver4벡터/512bin, DMA_E13_STREAM_SELFTEST_READY가PASS다.
제공콘솔은probe문장의중간부터시작하므로누락된programming시간/HP0/probe전문을추정해넣지않았다.
원본줄바꿈은board_selftest_console.log에보존한다. 정상insmod·장치bind의성공은
현재load_board.sh와그후client/self-test성공으로부터추론하며직접probe전문과구분한다.
공유bundle22 artifact SHA·현재build/source·BIN변환일치를독립확인했다.
직접보드파일시스템수집은아직전이며보드실행증거는사용자콘솔이다.

마지막128FFT축에서7단계각issue/retire8192회,CALC합60928cycles로
stage/FFT당64issue/64retire/68CALC와정확히일치한다.
여러stage의실제CALC동시16640cycles,여러in-flight FFT17386cycles로단계/프레임겹침을확인했다.
IO동시14998/input-CALC16191/output-CALC16191/세동작14998cycles도양수다.
새work_active는실제stage_calc의OR이므로이계측에는이전bf2의첫출력RAM읽기보정이필요없다.
stage CALC합을벽시간에더하지않고,위카운터를전체frame지연으로환산하지않는다.

다음은별도전체frame20회profile와각300회double·NEON·PL paired,원본수집·독립검증이다.
새전체성능은아직없으며build metadata와implementation.json의board_verified:false는빌드단계상태로보존한다.
카운터와번들신원은board_selftest.json에별도기록했다.


## Board measurement follow-up — 2026-11-21

Full-frame/profile20/paired300 and raw identity/accuracy/stage counters/IRQ validation now PASS.
PL median2.787411ms / paired NEON3.652869ms / double5.826396ms.
PL active0.711424ms (15.09% shorter than earlier bf2); whole median1.91% shorter across different boots.
Non-PL profile costs increased; preserve this limitation and the distinct timing populations.
See [final board results](../2026-11-21-e13-stream-board/README.md). Earlier pending statements preserve their original stages.
