# E12-4core: 입력·계산·출력 겹치기

E13-4core의 그룹 장벽을 없애고, 기존 FFT 코어4개 각각에 입력/출력 FIFO를 추가한다.
공유 입력은 FFT 단위 round-robin으로 분배하고 공유 출력은 기존 FFT 순서를 보존한다.
각 코어는 입력128개와 출력128개 여유를 확보하면 다른 코어의 출력 완료를 기다리지 않고 시작한다.
FIFO는 동기 읽기 RAM256words와 등록 출력1word이며 출력은 한 번 막혀도 안정적으로 유지한다.
입력 FIFO 용량257words, 출력은 FFT 시작 시128words 예약해 최대256words로 제한한다.

50 MHz/Q15 산술, 코어당 DSP4개, 코어 내부 LOAD/CALC/OUTPUT 및2clocks/sample,
DMA32-bit stream/64-bit HP0, 축당64 KiB, coherent bounce copies와 PS 전치를 고정한다.
E11c의1clock/sample은 이 구성에 넣지 않았다. 이 단계는 공유 DMA 폭을 늘리지 않으며,
미래 입력/이전 결과를 저장해 세 동작을 겹치는 E12 실험이다.

## 상태와 ABI

로컬 RTL272벡터·실제 세동작 겹침·FIFO/중단복구와 host28개 회귀 PASS.
ARM 수신기/모듈·Vivado reset/50 MHz setup·hold·실제버퍼 구현 검증 PASS.
LUT5311/FF5555/BRAM15/DSP16, WNS8.709/WHS0.026 ns다. 보드 packet/수신기 자체검사·실제DMA IO/계산겹침도 사용자콘솔에서 PASS.
전체 프레임·20회 profile·각300회 paired 원본 검증도 PASS.
중앙값 PL3.129210/double5.711883/NEON3.488904 ms다. 과거 E13보다25.25%, 이번NEON보다10.31% 짧다.
실측 PL active1.124590 ms, 복사1.263426/PS전치0.674777 ms다.
[최종 보드 결과·원본](../../../../benchmarks/reports/2026-11-20-e12-4core-board/README.md).
[빌드 근거](../../../../benchmarks/reports/2026-11-20-e12-4core-build/README.md).
[준비 근거](../../../../benchmarks/reports/2026-11-20-e12-4core-preparation/README.md).
ID0x46545085/register ABI5, compatible `fmcw,fft128-dma-overlap-v5`,
모듈 `fft128_dma_overlap`, 장치 `/dev/fft128-dma-overlap`.
헤더112B, input112/output65648/extra131184, request131224B다.
메타/두 payload 복사량은 기존과 같으며 추가40B는 PROFILE에서만 반환한다.

기존0x00..0x58 카운터를 유지하되 그룹 시작 기포=64/frame 조건은 폐기한다.
`busy`는 산술 코어가 LOAD/CALC/OUTPUT인 시간이다. FIFO만 배출하는 시간은 포함하지 않는다.
`arbitration`은 선택되지 않은 출력 FIFO의 valid가 하나라도 있는 사이클이다.
따라서 arbitration이 any-busy보다 클 수 있으며 global active 이하로 검사한다.
work-window는 각 산술 코어의 마지막 입력 수신부터 첫 출력 valid까지다.
CALC와 첫 RAM 읽기를 포함하므로 순수 CALC가 아니다. multi/all-work에서256cycles/frame을
빼면 실제 CALC 겹침의 보수적 하한이다. 겹친 시간들은 합산하지 않는다.

| 레지스터 | 의미 |
|---|---|
|0x5c|외부 입력·출력 handshake 동시 발생|
|0x60|외부 입력 handshake와 하나 이상의 work-window 겹침|
|0x64|외부 출력 handshake와 하나 이상의 work-window 겹침|
|0x68|외부 입력·출력 handshake와 work-window 모두 겹침|

외부정체0 시뮬레이션은28098cycles/axis, 두축/50 MHz로1.123920 ms다.
이는 기존2.081280 ms 대비 약46.0% PL 내부 단축이다. 후속 보드 실측 active1.124590 ms와 근접한다.
전체 비계측 중앙값3.129210 ms와 내부 cycle 모델은 구분한다.

RTL은 공개 카운터와 별도로 실제 CALC 상태/AXIS handshake 및 FIFO 용량을 검사한다.
보드의 work 겹침에는 첫 RAM 읽기가 포함된다. 순수 CALC 겹침과 구분한다.

## 실행

Windows 로컬:
```powershell
python src/PL/fft128_ps/verify_dma_overlap.py
python src/PS/fft128/dma_overlap/test_tools.py
```

Vivado 2022.1 Tcl 콘솔:
```tcl
source /home/user/fmcw_share/FMCW-FFT-test/src/PL/fft128_ps/build_dma_overlap.tcl
```
`FFT128_DMA_OVERLAP_BUILD_PASS`와 ARM 로그의`E12_4CORE_ARM_BUILD_PASS`를 확인한다.
빌드는 실제 생성 reset IP/ABI5, DSP16개 및50 MHz setup/hold를 검사한다.

Ubuntu:
```bash
P="$HOME/fmcw_share/FMCW-FFT-test"
bash "$P/src/PS/fft128/dma_overlap/prepare_bundle.sh" &&
bash "$P/src/PS/fft128/dma_overlap/deploy.sh"
```

현재 E13 모듈/overlay가 활성화되어 있으면 보드를 재부팅한 뒤:
```sh
sudo sh /opt/fft128/e12_4core/load_board.sh
```
자체 검사가 통과한 뒤 별도20회 profile과각300회 paired 측정:
```sh
B=/opt/fft128/e12_4core
sudo sh "$B/profile_board.sh" "$B/profile_e12_4core_01" &&
sudo sh "$B/run_board.sh" "$B/results_e12_4core_01"
```
Ubuntu 수집/검증:
```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/src/PS/fft128/dma_overlap/collect_results.sh"
```
기존 E13 소스·빌드·배포·측정은 보존한다. 새 경로는 모두`dma_overlap`/`e12_4core`다.
