# E14-clock: 선택한100MHz와 같은 보드 비교

**현재 결과:** CPU 전후666.67MHz / PL100MHz, 원본83개·각300회 검증 완료.
PS double5.631855ms / PS NEON3.563415ms / PL1.124817ms, PL은 NEON보다3.167995배 빠르다.
[최종 보고서](../../benchmarks/reports/2026-11-26-e14-clock/README.md).
이는 offline FFT 전체 경로이며 UDP·CFAR 연속 처리는 다음 S2b/S2c에서 검증한다.

**11-26 사용자 결정: 추가 상한 탐색을 멈추고100MHz를 비교 클럭으로 선택했다.**
100MHz는타이밍통과값이며최대클럭으로확정한값은아니다.112.5MHz는실행하지않는다.
아래 빌드·번들·보드 절차는 재현용이다. 현재 offline 원본 검증은 완료했고 다음은 S2b/S2c 연속 검사다.

```sh
cd /home/user/fmcw_share/FMCW-FFT-test
bash tools/clock/prepare_e14_100.sh
```

기존100MHz 빌드를재사용해번들/NFS배포만수행한다.전체로그는파일에보존하고터미널에는요약만표시한다.
출력된새보드경로로새부팅후`load_board.sh`를실행한다.재빌드·FPGA프로그래밍·재부팅은이명령에포함하지않는다.

기존 50MHz E14 결과는 보존한다. CPU 설정은 사용자 콘솔에서 2026-11-26에
기준33,333,333Hz × ARM PLL40 ÷ CPU분주2 = 666,666,660Hz로 확인했다.
이 확인을 과거 회차의 CPU 주파수 측정으로 소급하지 않는다.

같은 E14 RTL·Q15·전용7단계·행렬RAM·HP0·DMA·ARM 바이너리를 유지하고 MMCM 출력만 바꾼다.
FFT와 연결된 AXI/DMA/interconnect도 같은 클럭이므로 FFT 내부만의 주파수 실험은 아니다.
정확히 같은 MHz로 CPU/PL을 맞추는 실험이 아니라 각 경로의 검증된 동작 클럭에서 비교한다.

## 1. Ubuntu에서 후보 하나 빌드

```sh
cd /home/user/fmcw_share/FMCW-FFT-test
bash tools/clock/build_e14_clock.sh 100
```

Vivado2022.1 실행 파일은 PATH 또는 `/tools/Xilinx/Vivado/2022.1/bin/vivado`에서 찾는다.
다른 설치 위치는 `FFT128_VIVADO`에 실행 파일 경로를 지정한다.
ARM 재빌드·NFS 배포·FPGA 프로그래밍은 하지 않는다. 기존 `fft128_dma_frame_latest.txt`도 보존한다.
후보별 프로젝트·launcher log·타이밍 실패·`clock_validation.json`은 새 `build/` 폴더에 남는다.
터미널에는 시작·로그 경로·성공/실패·타이밍 요약만 출력한다. 실패하면 마지막12줄도 표시한다.
전체 Vivado 출력과 JSON 해시는 파일에 보존하며 검증기의`--verbose`로 전체 JSON을 출력할 수 있다.
PASS 조건은 요청/실제 클럭 일치, routed setup/hold/pulse 검사, 미제약 경로0,
생성 reset/lock-loss simulation, E14 구조 검사, 소스·bitstream 신원 확인이다.
이는 보드 검증 PASS가 아니다.

처음100MHz가 통과하면125MHz 등 상위 후보를, 실패하면75MHz 등 하위 후보를 빌드한다.
통과/실패 경계를 좁혀 실제 MMCM이 생성 가능한 주파수에서 상한을 찾는다.
선택한 구현 전략·시험한 주파수와 인접 실패 후보를 기록하며,
처음100MHz가 통과했다는 이유만으로 최대 클럭이라고 쓰지 않는다.
RTL 구조/파이프라인 최적화는 이 탐색에 섞지 않는다.

## 2. 통과 후보의 번들 준비와 별도 경로 배포

`run`은 `E14_CLOCK_CANDIDATE_READY`에 출력된 실제 폴더로 지정한다.
`tag`는 예시이며 주파수·실행 시각별로 바꿔 기존 후보를 보존한다.

```sh
run=/실제/후보/빌드/폴더
tag=100mhz_$(date +%Y%m%d_%H%M%S)
bundle="$PWD/build/e14_clock_bundle_$tag"
bash tools/clock/prepare_e14_clock_bundle.sh "$run" "$bundle" &&
bash tools/clock/deploy_e14_clock.sh "$bundle"
```

기존 `/nfsroot/opt/fft128/e14_frame`의 SHA 검사된 ARM 실행 파일·모듈·fixture를 재사용한다.
새 이미지, 주파수가 일치하는 fixed-clock DT overlay, profile/benchmark 스크립트를 묶는다.
overlay는 캡처한 DT와 offline 병합 검증하며 live 적용을 대신하지 않는다.
배포 출력의 실제 보드 경로는 `/opt/fft128/e14_clock_<Hz>_<시각>`이다.

## 3. 보드 자체 검사와 비교

현재 E14 모듈/overlay가 로드된 상태에서는 프로그래밍하지 않는다.
새 보드 부팅 후 새 경로의 `load_board.sh`로 활성화하고 로그를 보존한다.
로더는 기존 모듈이 있으면 중단하며 직접 강제 제거하거나 진행하지 않는다.

```sh
B=/opt/fft128/실제_새_후보_경로
sudo sh "$B/load_board.sh" 2>&1 | sudo tee "$B/load_board.console.log"
```

`DMA_FRAME_CLIENT_PASS`와 `SELFTEST_PASS`를 확인한 뒤:

```sh
sudo sh "$B/profile_board.sh" "$B/profile_01" &&
sudo sh "$B/run_board.sh" "$B/paired_01"
```

profile은 별도20회, 같은 회차 paired는 PS double/NEON/PL 각300회다.
새 프로파일은 실제 선언 클럭으로 사이클을 환산한다.
CPU PLL·분주·기준 클럭을 비교 전후에 다시 읽고 결과와 함께 보존한다.
paired는 창 없음/Q15 입력의 FFT 경로 지연이며 UDP/CFAR 최대 FPS가 아니다.
Ubuntu 수집 후 분석기의 `--clock-hz`에 해당 후보의 실제Hz를 명시한다.

최종 시스템 비교는 기존 S2a-rxfix1 `stream-receiver`를 그대로 사용한다.
CPU0·Hann·multi4·CA·큐 크기·진단flag 해제 조건을 PS/PL에서 맞추고,
S2b 예비/장시간 검사 및 S2c 송신 주기 탐색으로 드랍0·P99·CPU/RSS·정확성을 검증한다.
첫 커널 패킷→출력과 프레임 완성→출력 지연을 모두 보고한다.
기존 PS stream은 double FFTW이며 offline NEON 결과와 같은 구현으로 취급하지 않는다.
최고 클럭이 최고 지속 FPS인지도 실측으로 확인한다.

## 현재 검증 범위

PC 타이밍 거부·클럭 환산·Tcl 입력/오류 정리 검사와 기존 E14 도구 회귀 검사를 수행한다.
100MHz 실제 Vivado 빌드와 공유 원본 독립 대조를 완료했다(WNS0.726ns/WHS0.023ns).
125MHz는setup WNS−0.727ns/321 endpoint 실패로bitstream 생성 전 중단했다.
사용자 결정으로100MHz를 선택하고 추가 탐색을 중단했다. 보드 자체 검사 사용자 콘솔 PASS를 확인했다.
CPU 클럭 전후 기록·별도20회 profile·PS double/NEON/PL 각300회 paired 실행 완료 콘솔을 확인했다.
원본 수집과 독립 검증을 완료했다. CPU 전후·부팅·30개 번들 신원·profile 및 paired IRQ·정확성이 일치한다.
새 주파수 CFAR·연속 처리 결과는 아직 없다.100MHz를 유지해 S2b/S2c로 진행한다.
