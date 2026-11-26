# E14-clock — 100MHz 보드 비교 완료

2026-11-26. **CPU 약666.67MHz / PL100MHz, 같은 회차 각300회 원본 검증 완료.**
PL은 같은 회차 PS float+NEON보다 **3.167995배**, PS double보다 **5.006908배** 빠르다.
사용자가100MHz를 선택해 추가 클럭 탐색을 중단했다.100MHz를 최대 클럭으로 확정하지 않는다.

| 구성 | 반복 수 | 중앙값 | 평균 | 최소 / 최대 |
|---|---:|---:|---:|---:|
| PS double |300|5.631855ms|5.630928ms|5.553846 / 5.978268ms|
| PS float+NEON |300|3.563415ms|3.576935ms|3.431382 / 3.838056ms|
| PL100MHz |300|1.124817ms|1.125910ms|1.104408 / 1.210825ms|

**측정 범위:** 같은128×128 Q15 양자화 입력, 창 없음,1/16384 정규화, CPU0,
warmup10·100회×3회차, 회차별 실행 순서 회전. 두 축FFT·필요한 사용자/커널 복사·DMA·IRQ 대기·
PL 전치/출력 배열 복원을 포함한다. 입력I/O·양자화·할당·FFTW 계획·반복 검증·파일 출력은 제외한다.
**UDP 수신·Hann·CFAR·연속 FPS 비교는 이 결과에 포함하지 않는다.**

[최종 원본 감사](board_measurements.json), [paired 전체 통계·정확성](comparison.json),
[별도 profile20회](profile_summary.json), [83개 원본 SHA](raw_artifact_sha256.json).

## 원본·정확성·클럭 검증

- 원본: 보드 `/opt/fft128/e14_clock_100000000_20261126_095418/compare_100mhz_01`.
  Ubuntu 공유 수집 `build/e14_clock_100_results_20261126_100907`을 로컬 ignored `build/`에 복제하고
  83개/9,268,101byte를 SHA로 대조했다. 큰 spectrum/input CSV는 ignored `build/`에 유지한다.
  작은 로그·metadata·시각CSV·환경·IRQ·클럭은 [raw_compact](raw_compact/)에 보존했다.
- CPU 전후 레지스터와 DT 기준 클럭이 같다:33,333,333Hz × ARM PLL40 ÷ CPU분주2 =666,666,660Hz.
  boot ID `87d0bd24-5ffa-435e-8919-fee083d76b6f`가 전후·profile·paired에서 같다.
  CPU 주파수 카운터 실측은 아니며, 과거 회차의 CPU 주파수를 소급 확인하지 않는다.
- 선택한 번들30개 SHA가 보드 load/profile/paired 검사와 같다. PL14·ARM host12·module3개 소스도
  공유 소스의 원시 바이트 SHA와 같다. [번들 manifest](bundle_artifacts.sha256).
- PL은 매 반복16,384 bin의 C 정수 모델 검증을 통과했다. 저장된3개 전체 출력도 독립Python 정수
  oracle과 정확히 같다. PS double/NEON은 각 반복 검증 및 저장된 출력의 NumPy 허용오차 검사를 통과했다.
  PL/PS는 서로 다른 정밀도이며 PL의 부동소수점 기준 상대L2 오차는 약1.361%로 기존Q15와 같다.
- paired DMA IRQ67/68은 각각CPU0 330회/CPU1 0회(측정300+warmup30),
  profile은 각각CPU0 22회/CPU1 0회(측정20+warmup2)다.
- profile20행 모두1 ioctl/프레임·2채널·각64KiB·256FFT, matrix 및7단계 issue/retire 보존식,
  overwrite0·CPU transpose0·phase cycle 합계·100MHz 시간 환산을 검증했다.

## 별도 프로파일과 과거50MHz 비교

계측20회 평균: 전체1.154095ms, PL active0.519439ms, 사용자 input/output 복사0.112839/0.074130ms,
커널 input/output 복사0.086194/0.301514ms다. kernel wait0.540782ms와PL active는ioctl에 포함되므로
전체 시간에 다시 더하지 않는다. 비계측 결과는 위 각300회 표를 사용한다.

과거50MHz PL 중앙값1.657914ms 대비 이번100MHz는 관측상1.473941배 빠르고32.154684% 짧다.
**서로 다른 회차·부팅이며 과거 CPU 주파수 기록이 없어, 클럭만 바꾼 같은 회차 A/B 효과로 단정하지 않는다.**
과거50MHz 데이터와 실패 기록은 그대로 보존한다.

## 빌드 탐색·선택 이력

| 후보 | setup WNS | hold WHS | pulse WPWS | 상태 |
|---|---:|---:|---:|---|
|100MHz|0.726ns|0.023ns|2.000ns|Vivado·보드 자체 검사·20회 profile·각300회 paired 검증 완료|
|125MHz|−0.727ns|0.052ns|2.000ns|setup321 endpoint 실패, bitstream 생성 전 중단|

100MHz run: `fft128_dma_e14_clock_100p000mhz_20261126_092439_245`.
[빌드 원본 대조](100mhz_092439/independent_readback.json): artifact11개·소스14개 SHA 일치.
125MHz run: `fft128_dma_e14_clock_125p000mhz_20261126_093810_96`.
[실패 원본](125mhz_093810/independent_readback.json): setup TNS−87.975ns, 소스14개 SHA 일치, bitstream 없음.
사용자가100MHz를 선택했으며112.5MHz는 실행하지 않았다.

자체 검사 최초 사용자 콘솔은 [발췌](board_selftest_console.txt), [당시 확인 범위](board_selftest.json),
측정 완료 콘솔은 [당시 수치](measurement_console.json)로 보존한다. 이후 회수한 완전한 load log는
[raw_compact/load_board.console.log](raw_compact/load_board.console.log)에 있다.

## 재계산과 다음 단계

저장한 raw 폴더에 대해 repo root에서 실행한다. 원본 수집기는 새 출력 폴더만 허용한다.

```sh
python benchmarks/compare_dma_frame_board.py build/e14_clock_100_results_20261126_100907/paired --clock-hz 100000000
python src/PS/fft128/dma_frame/analyze_profile.py build/e14_clock_100_results_20261126_100907/profile/pl.profile.csv --clock-hz 100000000
```

추가 CPU·신원·원본 감사 코드는 [measurement_validation_driver.py.txt](measurement_validation_driver.py.txt),
실행한 분석기의 사본·SHA도 함께 보존했다. 드라이버의 `--source-tree`와 `--bundle`은 실제 공유 소스와
`build/e14_clock/prepare_100mhz_nioFaI/bundle` 위치를 지정한다.

다음은100MHz를 유지한 S2b/S2c의 UDP→FFT→CFAR→출력 연속 측정이다.
기존 stream PS는 double FFTW이므로 위 offline NEON 구현과 구분한다.
[실행 절차](../../../tools/clock/README.md), [실험 일지](../../../docs/experiment_log.md#e14-clock--최대-동작-클럭-탐색과-비교-준비).
