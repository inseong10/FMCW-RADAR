# E13-bf2 Vivado/ARM build — 2026-11-21

**실제4코어/코어당2버터플라이, Vivado 구현·50 MHz 타이밍·ARM빌드 PASS. 보드 검증 대기.**

Run: `fft128_dma_e13_bf2_20261120_235235`.
현재checkout/공유소스와 PL·host·module source SHA가 모두 일치하며 host/module 산출물의
manifest를 독립 검증했다. XSA 내부bitstream도 구현run의bitstream과 SHA가 같다.

- 50 MHz: setup WNS5.405ns / hold WHS0.028ns, setup/hold/pulse-width failing endpoints0.
  no-clock register/latch0, maximum-delay unconstrained pin0, 모든 사용자 타이밍 제약 만족.
- LUT7428/17600(42.20%), FF6555/35200(18.62%), BRAM23/60(38.33%), DSP32/80(40%).
  기준E12는 LUT5311/FF5555/BRAM15/DSP16이며 이번증가는 LUT2117/FF1000/BRAM8/DSP16이다.
- 구현계층의 core0..3은 각각DSP8개, 그안의 butterfly0/1은 각각DSP4개다.
  각코어4개 작업RAM bank가 각각RAMB36 1개로 구현됐다(전체16개).
  기존입력/출력FIFO8개는 각각RAMB18 1개/DSP0을 유지한다.
- 생성BD의 FFT외 모든 PS7/DMA/clock/reset/interconnect/IRQ 컴포넌트와
  interface ports/nets, scalar ports/nets, addressing은 기준E12 BD와 완전히 같다.
  단일Simple DMA/AXIS32/HP0 64-bit/50MHz/F2P6·7, SG·DRE off를 유지한다.
- 실제생성 reset IP를 사용한 ID/length/ABI6/코어4/버터플라이2·카운터초기값/lock-loss recovery
  simulation은 done1/passed1이다. 생성 VHDL의 ext active-low/aux active-high도 확인했다.
- ARM32 EABI receiver/client static ELF와 module ELF가 정상빌드됐다.
  커널5.15.19-xilinx/SMP/preempt/modversions/ARMv7에 맞추어 빌드했다.
  정상보드 insmod의symbol CRC수용은 아직 확인하지 않았으며 force옵션은 사용하지 않는다.
- `prepare_host.sh`의 dtc 및 기록base-DT와 fdtoverlay/fdtget 검증이 완료됐다.
  dtc의독립 GIC phandle 경고는 `host_dtc.log`에 보존했다. 실제 live overlay 적용은 아직 전이다.

이는 구현·오프라인 검증이다. BIN변환/번들/배포와 실제보드 DMA·정수검사·두연산기 카운터,
전체frame/별도20회profile/각300회paired 성능은 남았다. 새보드 성능 수치는 없다.
앞선 RTL0.837200ms는 무정체PL사이클 모델이며 전체보드 지연이 아니다.

`implementation.json`에 정확한source/bitstream/XSA/DCP/host/module SHA·크기·경로와 확인범위를 기록했다.
큰바이너리는 공유 ignored `build/`에 유지하며 생성metadata의 `board_verified:false`도 보존한다.

Ubuntu에서 번들생성·배포:
```bash
P="$HOME/fmcw_share/FMCW-FFT-test"
bash "$P/src/PS/fft128/dma_bf2/prepare_bundle.sh" &&
bash "$P/src/PS/fft128/dma_bf2/deploy.sh"
```

배포성공후 기존E12 DMA모듈/overlay를 비우도록 보드를 재부팅하고 PetaLinux에서:
```sh
sudo sh /opt/fft128/e13_bf2/load_board.sh
```

`BF2_ARITHMETIC_PASS` 및 `DMA_E13_BF2_SELFTEST_READY` 뒤 frame/profile/paired로 이어간다.
기존E12 펌웨어와측정경로는 보존한다. [전체보드 절차](../../../src/PS/fft128/dma_bf2/README.md),
[로컬준비결과](../2026-11-20-e13-bf2-preparation/README.md),
[E12보드 기준](../2026-11-20-e12-4core-board/README.md).


## Board self-test follow-up — 2026-11-21

사용자 제공 PetaLinux 콘솔에서 BIN load62ms, live overlay/DMA/client probe,
정상 module load, 부분·전체·반복packet/receiver self-test까지 PASS다.
원본 줄바꿈을 포함한 콘솔은 `board_selftest_console.log`에 보존했다.
shared bundle22개 artifact SHA와 현재build/source·BIN변환 일치를 독립 확인했다.
보드 파일시스템을 직접 읽은 결과와 사용자 콘솔 증거를 구분한다.

128 FFT축에서 두연산기 issue/retire는 각각28672pair, CALC lane-cycles32256이다.
FFT당224pair/252cycles와 정확히 일치하며 코어내두버터플라이 동작의실제보드증거다.
CALC lane-cycles는 코어합이며 wall/active시간에 더하지 않는다.
외부IO동시13511, input/work16097, output/work16096, three-work13482cycles다.
첫출력RAM읽기의 비CALC상한128cycles/axis를 보수적으로 제외하면 실제입력·CALC·출력
동시수행은 최소13354cycles다. all-work0은 짧아진CALC로 예상한스케줄이며 두연산기검사실패가 아니다.

exclusive ownership/이전ABI·timeout·flags·count거부, 1/2/3/4/5/127/128/128 FFT packet,
receiver4벡터/512bin 및 `DMA_E13_BF2_SELFTEST_READY` PASS다.
overlay제거시 memory-leak/out-of-tree taint 경고가 있었으며 검사는 끝까지 완료됐다.
62ms는 FPGA프로그래밍시간이고 FFT처리성능이 아니다.

다음은 별도20회전체프레임profile, 각300회double/NEON/PL paired와원본수집·독립검증이다.
앞선 `implementation.json`의 board_verified:false는 빌드단계상태로 보존한다.
현재 증거범위/카운터/번들SHA는 `board_selftest.json`에 있다.


## Board measurement follow-up — 2026-11-21

Full-frame/profile20/paired300 and raw identity/accuracy/counters/IRQ validation now PASS.
PL median2.841720ms / paired NEON3.520371ms / double5.708112ms.
Profile PL active0.837903ms; two-butterfly issue/retire/CALC counts match exactly.
See [final board results](../2026-11-21-e13-bf2-board/README.md).
Earlier pending statements preserve the preparation/build stages.
