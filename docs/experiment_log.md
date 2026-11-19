# FMCW FFT 실험 일지

이 문서는 **관찰한 문제 → 가설 → 변경 → 검증 결과 → 해석 → 다음 실험**을 연결하는 기준 기록이다.
기록 대상은 처리 로직·구조·클록·전송·정밀도·측정 조건과 그 결과다. 실행 스크립트 문법·경로·
배치·일반 환경 설정만 바로잡는 수정은 실험 항목으로 기록하지 않는다.
날짜는 사용자 환경의 Asia/Seoul 기준이다. 최초 작성일은 2026-11-15이며, 이전 단계는 대화와
남아 있는 결과 파일에서 복원했다. 정확한 시각이나 원본 로그가 없는 항목은 확인 범위를 명시했다.

## 현재 위치

- 보드에서 검증된 구성: **순차/20 MHz MMIO, 파이프라인/50 MHz MMIO 및 E11a/E11b DMA, 128×128**.
- E08에서 같은 보드의 PS C++/FFTW와 비교 완료. E09에서 연산·전송·전치 분해 계측 완료.
- E10의 새 파이프라인은 **RTL·구현·보드 프로파일·각 300회 PS–PL 비교·NumPy 검증 완료**.
- 다음 단계: E10의 새 기준선을 보존하고 [단계별 가속 계획](fft128_dma_plan.md)에 따라
  PS01 float/NEON 기준 측정 → E11a DMA → E11b 묶음 제출을 진행한다. 독립 출력 개선 E11c와
  E12 겹치기/E13 연산 구조의 실행 순서는 E11b 프로파일로 정한다. E14 전치는 선택 사항이다.
  PS01 세 변형의 원본 수집·독립 검증도 완료했다(2026-11-16). 전체 중앙값은 double
  5.502540 / float scalar 4.341573 / float+NEON 3.615852 ms다.
  E11a 소스와 계측 도구를 구현하고 RTL·ARM 수신기·DT 오프라인 검증을 통과했다.
  ARM 모듈/실제 커널 CRC와 Vivado 통합·50 MHz 구현 타이밍까지 통과했다.
  E11a 보드 DMA 프레임·계측·각 300회 paired 비교도 완료했다. 중앙값은 PS double
  5.748489 / NEON 3.715234 / PL DMA 15.411639 ms다. [E11a 완료 보고서](../benchmarks/reports/2026-11-16-e11a-board/README.md).
- **E11b 완료:** 전체 프레임·별도 profile·각 300회 paired 비교·원본 신원/정확도/IRQ 독립 검증 PASS.
  중앙값 PS double 5.717376 / NEON 3.558177 / PL 6.433026 ms.
  [완료 보고서](../benchmarks/reports/2026-11-19-e11b-board/README.md).
  여러 FFT 코어·연속 프레임·크기 스윕은 아직 실시하지 않았다.

## 실험 색인

| ID | 날짜 | 질문/문제 | 주요 변경 | 확인 상태와 핵심 결과 |
|---|---|---|---|---|
| E01 | 11-13 | 기존 32-point 설계의 보드 이식·구현 실패 | 보드용 multiplier/adder/clock-capture 대체 | 최종 64/80 DSP; 세부 최초 place 실패 원인은 기록 부족 |
| E02 | 11-13 | 32-point 결과 81개 오류 | 마지막 FFT 단계 이후에 결과 캡처 | 최종 5벡터/160 bin 보드 PASS |
| E03 | 11-14 | 128×128가 작은 FPGA에 들어가는가 | 128-point 반복 코어 하나를 두 축에 재사용 | RTL 272 FFT/34,816 bin PASS; 보드 전 검증 |
| E05 | 11-15 | MMIO 첫 ID 읽기 정지 | 독립 보드 클록, reset 극성 명시, reset IP 사전 검사 | V3에서 ID·self-test 정상; 생성 IP로 리셋 원인 재현 |
| E06 | 11-15 | 시뮬레이터 입력 전체 경로가 맞는가 | RadarSimPy 기록 → UDP → PS → PL 두 축 | 16,384 bin 정수 모델 일치, 단일 약 82.024 ms |
| E07 | 11-15 | PC NumPy와 보드 시간을 비교해도 되는가 | 비교 해석 수정, 같은 보드 기준으로 변경 | 교차 장치 시간비 약 318은 보드 가속 결론에서 제외 |
| E08 | 11-15 | 최적화 PS 대비 현 PL은 빠른가 | 입력·정규화·측정 범위 정렬, CPU0, 반복 측정 | 중앙값 PS 5.550 ms / PL 81.460 ms; PL 경로가 14.677배 느림 |
| E09 | 11-15 | 81 ms 중 연산·전송·전치 비중은? | 0x010 사이클 읽기와 호스트 단계 계측 | 3,073 cycles/FFT; PL 내부 39.334 ms, 입출력 41.800 ms |
| E10 | 11-15 완료 | 순차 연산과 낮은 클록을 개선할 수 있는가 | 파이프라인·stage ping-pong RAM·50 MHz 빌드 | RTL 861 cycles/FFT; 50 MHz 타이밍·보드 프레임 PASS; 프로파일 평균 27.328 ms; 각 300회 중앙값 PS 5.557 / PL 25.259 ms; 기존 PL보다 3.225배 개선 |
| PS01 | 11-15~16 완료 | DMA 설계 전에 PS 목표 성능을 먼저 정할 수 있는가 | double/float scalar/float+NEON 변형, 같은 입력·전치·반복 검증 | 원본 검증 PASS; 각 300회 전체 중앙값 5.502540/4.341573/3.615852 ms; NEON 변형은 double 대비 1.522배 개선 |
| E11a | 11-16 완료 | FFT당 작은 DMA 제출의 전송/고정 비용은? | 산술/50 MHz 유지, Simple DMA/HP0·제어 앞단·coherent bounce·ioctl/계측 | 보드 프레임·독립 정수 검증 PASS; 각 300회 중앙값 PS double 5.748489 / NEON 3.715234 / PL DMA 15.411639 ms; 별도 계측 평균 18.136318 ms |
| E11b | 11-19 완료 | 256번의 작은 DMA 요청 비용을 줄일 수 있는가 | 축당 128 FFT/64 KiB, 2 ioctl/4 채널 제출 | 각 300회 중앙값 PS double 5.717376 / NEON 3.558177 / PL 6.433026 ms; 두 IRQ 각각660; [완료 보고서](../benchmarks/reports/2026-11-19-e11b-board/README.md) |

## 공통 조건과 해석 규칙

- 대상: Zybo Z7-10 / XC7Z010-1CLG400C, Vivado 2022.1, ARMv7 hard-float,
  PetaLinux kernel `5.15.19-xilinx`. Ubuntu 20.04.6은 빌드·TFTP·NFS 호스트다.
- 128×128 기준 입력: [RadarSimPy 기록](../benchmarks/fixtures/README.md),
  SHA256 `aa06ff124034310216693c1398f2f1061c9a6ce32e9ea6f5687675849934c976`,
  한 채널, fs 1.6 MHz, 표적 30 m / -10 m/s. 입력 기록에는 FFT 결과가 들어 있지 않다.
- 창 없음, 같은 Q15 양자화 입력, 전체 정규화 1/16384. PS FFTW는 double, PL은 고정소수점이다.
- 보드 CPU 주파수는 직접 확인되지 않았다. BogoMIPS에서 추정한 667 MHz를 실측값으로 쓰지 않는다.
- `SOFTWARE_MODEL` PASS, RTL PASS, bitstream 생성, FPGA Manager `operating`, 실제 보드
  `SELFTEST_PASS`/`FRAME_PASS`는 각각 다른 확인 단계다.
- 사이클/클록 환산은 PL 내부 구간이다. `start_wait`와 겹치므로 두 시간을 더하지 않는다.
- 프로파일링 실행은 추가 타이머·MMIO 읽기가 있다. 계측 없는 성능 비교와 같은 모집단으로 합치지 않는다.
- 같은 프레임 반복은 캐시가 데워진 오프라인 지연이다. 연속 UDP 처리량이나 실시간 보장을 뜻하지 않는다.

## E01–E02 — 기존 GitHub 32-point FFT 보드 검증

- **문제/관찰:** 초기 `place_design ERROR`와 이후 보드·RTL에서 `passed=1 errors=81`,
  `first=40 actual=0 expected=16777216`을 관찰했다. 시뮬레이터의 `first=28`은 16진 표기다.
  최초 배치 실패의 상세 원본 로그는 이 일지 작성 시 확보되지 않아 원인을 단정하지 않는다.
- **가설/변경:** 원본 서브모듈은 유지하고 보드 wrapper에서 곱셈 공유, 등록 출력 및 마지막 단계
  캡처 시점을 수정했다. `multiplier_zybo.v`, `adder3_zybo.v`, `clk_div_zybo.v`와 자체 검사 경로다.
- **재검증:** 캡처 스케줄 모델이 81개 오류를 재현했고 마지막 단계 캡처에서는 통과했다.
  multiplier 589,825 비교, RTL·합성 후 기능·배치배선 후 타이밍 시뮬레이션과 보드 VIO를 확인했다.
  최종 `done=1 passed=31 errors=0`, 5벡터/160 bin; setup 5.156 ns, hold 0.043 ns,
  DSP 64/80, LUT 7,691/17,600, FF 6,996/35,200.
- **해석:** 이 32-point 구조의 자원량으로 이후 단일 반복형 128-point 구조의 자원량을 판단하면 안 된다.
  실제 레이더·PS·UDP 연동을 검증한 실험도 아니다.
- **근거:** [32-point 설명](../src/PL/zybo_fft_test/README.md),
  [보존 결과](../benchmarks/reports/2026-11-13-fft32/README.md).

## E03 — 128 samples × 128 chirps 처리 구조 선정

- **문제:** 첫 Range–Doppler 실험 크기를 128×128로 고정하고 Z7-10에서 기능을 확인한다.
- **선정 이유/변경:** 사용자 제공 `fmcw_fft`의 반복 Butterfly 구조를 128-point로 조정해 한 코어로
  Range FFT 128회 → PS DDR 열 gather → Doppler FFT 128회를 순차 실행한다.
  기존 GitHub 32-point 코어와 출처·구조가 다르다. 최초 전송은 DMA 대신 AXI4-Lite다.
- **검증:** 순차 RTL 16 스트림 벡터와 AXI 272 FFT/34,816 bin이 정수 모델과 일치했다.
  AW/W 순서, 응답 지연, TLAST·리셋·오류 접근을 검사했다.
- **관찰:** 최초 128-point 구현의 DSP는 4/80으로, 기존 32-point 전체 병렬 구조보다 작았다.
  이는 기능 우선의 자원 절약 구조이며 가속 성능 확보를 뜻하지 않는다.
- **근거:** [출처와 원본 해시](../src/PL/fft128_ps/provenance.json),
  [기능 실험 설명](../src/PL/fft128_ps/README.md).

## E05 — MMIO 정지: 클록·리셋·실제 생성 IP 검증

- **관찰:** fpgautil 다운로드와 `operating`은 성공했으나 첫 ID 읽기가 반환되지 않고 Ctrl+C도
  처리되지 않았다. 수신기에 ID·길이·soft reset 진행 출력을 추가해 정지 위치를 좁혔다.
- **첫 가설/변경:** 기존 FCLK 설정과 reset 전달 의존성을 제거하려고 K17 125 MHz → MMCM
  20 MHz 클록과 독립 reset 구성을 사용했다. 클록 변경만으로는 정지가 해결되지 않았다.
- **확인된 원인:** 생성된 reset IP의 `C_AUX_RESET_HIGH=0`인데 `aux_reset_in=0`으로 묶여 있었다.
  실제 생성 netlist로 두 AXI reset이 계속 asserted임을 재현했고, 보조 reset 해제 시 ID가 응답했다.
- **수정:** V3는 `C_EXT_RESET_HIGH=0/ext_reset_in=1`, `C_AUX_RESET_HIGH=1/aux_reset_in=0`을
  명시한다. MMCM lock-loss 복구까지 실제 생성 IP로 검사한 뒤 합성하도록 했다.
- **재검증:** V3 run `fft128_ps_20261115_203251`, setup 32.177 ns, hold 0.052 ns;
  실제 보드 ID `0x46543128`, 길이 128, `SELFTEST_PASS ... vectors=4 bins=512`.
  firmware SHA256 `e1784f80c8f27225dded47749d0baa98a3d2cc9a108b0f7df2d86afb6239a5db`.
- **교훈/다음:** 다운로드 성공은 사용자 로직 정상 응답을 보장하지 않는다. IP 기본 극성을 추정하지
  않고 생성 결과와 reset 해제를 확인한다. 이후 프레임 전체를 E06에서 확인했다.
- **근거:** [reset 재현·최종 빌드·보드 근거](../benchmarks/reports/2026-11-15-bringup/README.md).

## E06 — 실제 RadarSimPy 입력의 전체 보드 처리

- **입력/실행:** 기록된 128×128 입력을 Ubuntu에서 UDP 128패킷으로 전송하고 보드 native C가
  PS 수신·Q15 변환·PL 두 축 FFT·전치·검증·CSV 저장을 수행했다.
- **결과:** `FRAME_PASS backend=PL_MMIO bit_exact_bins=16384`, 피크 (107,20), drop/duplicate 0.
  입력 IQ 16,384개가 원본과 같았다. NumPy 대비 최대 복소 오차 8.749842 Q15 정수 단위,
  RMS 1.734691, 상대 L2 1.361%로 검증 기준 최대 12 이내였다.
- **시간:** 단일 실행 82.024044 ms. 당시에는 전송·FFT·전치와 임시 작업 버퍼 할당이 포함됐다.
  UDP·양자화·정답 계산/검증·파일 저장은 제외했다.
- **해석/다음:** 단일 프레임 기능 통과다. 한 번의 시간으로 PS 대비 가속이나 연속 처리량을 주장하지
  않는다. 정확도 원본은 E05 보존 폴더, 반복 성능 비교는 E08로 이어진다.

## E07 — 잘못된 성능 비교 범위 교정

- **문제:** Windows PC NumPy 중앙값 0.257850 ms와 보드 단일 82.024044 ms의 시간비 약 318을
  제시했다. 서로 다른 CPU·환경·측정 범위여서 보드 내 PS–PL 가속비로 쓸 수 없었다.
- **수정:** 그 시간비를 보드 가속 결론에서 철회하고 PC NumPy는 정확도 참조·별도 참고값으로 남겼다.
  사용자가 지적한 기존 최적화 C++/FFTW를 동일 보드 PS 기준선으로 선택했다.
- **다음 조건:** 같은 입력·정규화·측정 경계를 맞추고, 양쪽 작업 버퍼를 사전 할당하며 계획 생성과
  워밍업을 제외한다. 모든 후속 보고서는 E08의 동일 보드 값부터 사용한다.

## E08 — 동일 보드 PS C++/FFTW 대 순차 PL, 비계측 기준선

- **변경:** ARM FFTW double을 별도 경로에 빌드하고 보드에서 wisdom 생성. 기존 32×32 타일 전치와
  연속 Doppler FFT를 유지했다. 두 호스트 프로그램 CPU0 고정, 각 trial 워밍업 10회/측정 100회,
  PS–PL 3쌍으로 각 방식 300회. PL 검증은 매 반복 타이머 밖에서 수행했다.
- **범위:** 이미 준비된 입력부터 PS에서 결과 사용 가능까지의 `fft_pipeline`.
  PS는 복사·두 축 FFT·타일 전치·정규화, PL은 MMIO·두 축 FFT·gather/scatter를 포함한다.
  UDP·파일 I/O·할당·양자화·plan 생성·정답 검증·후처리는 제외한다.

| 지표 | PS double FFTW | 순차 PL 20 MHz |
|---|---:|---:|
| 중앙값 | 5.550039 ms | 81.460246 ms |
| 평균 | 5.542663 ms | 81.525070 ms |
| 5~95 백분위수 | 5.489259~5.597602 ms | 81.421093~81.724731 ms |

- **관찰:** 현재 PL 경로가 PS보다 14.677배 느리다. PL 내부 연산과 전송·전치의 비중을 이 데이터만으로
  분리할 수 없었다. 서로 다른 산술 정밀도, PS 내부 단계 타이머 비용, 고정 크기·warm-cache 한계가 있다.
- **의사결정:** DMA나 클록을 먼저 바꾸기 전에 이미 존재하는 사이클 레지스터를 사용해 E09에서
  시간 구조를 확인한다.
- **근거:** [300회씩의 CSV·보고서](../benchmarks/reports/2026-11-15-zybo128/README.md).
  기준선 코드와 보고서는 원격 커밋 `ebcbfd2`, `ab8cd05`, `14e8cb1`에 보존됐다.

## E09 — 순차 20 MHz의 병목 분해, 계측 실행

- **가설:** PL 순차 처리와 워드 MMIO가 모두 크다. 기존 0x010 카운터로 내부 처리 구간을 확인할 수 있다.
- **변경 위치:** `mmio.c`에 입력 쓰기·시작/대기·카운터 읽기·출력 읽기 타이머,
  `native_core.c`에 gather/scatter 타이머를 추가했다. `native_receiver.c`는 256 FFT의
  카운터 합·최솟값·최댓값과 프레임별 CSV를 저장한다. 명시적 클록 인자와 별도 프로파일 모드를 쓴다.
- **실행:** `sudo sh /opt/fft128/benchmark/profile_board.sh 20000000`, CPU0,
  워밍업 2회/측정 20회. 사용자가 제공한 보드 콘솔로 아래 값을 확인했다.

| 구간 | 20회 평균 | 범위/중복 주의 |
|---|---:|---|
| 입력 쓰기 | 23.429884 ms | idle 확인 및 입력 MMIO |
| 시작·대기 | 39.927098 ms | 아래 PL 내부 처리와 겹침 |
| 출력 읽기 | 18.370430 ms | 결과 MMIO와 작은 계측 bookkeeping |
| gather/scatter | 0.947203 ms | PS 열 접근·결과 배치 |
| 카운터 읽기와 기타 잔여 | 1.019642 ms | 콘솔 합계 차이로 역산; 둘을 따로 측정한 값은 아님 |
| 전체 | 83.694257 ms | 계측 실행 평균; 중앙값 83.623717 ms |
| PL 내부 | 39.334400 ms | **시작·대기 안에 포함; 별도로 더하지 않음** |

- **보드 확인:** FFT당 min=max=3,073사이클, 정수 모델 16,384 bin 일치, 피크 (107,20).
  39.3344 ms = 3,073 × 256 / 20 MHz. 이 내부 구간에는 내부 입력 적재·출력 저장도 포함된다.
- **결론:** 입력+출력 MMIO 41.800314 ms와 PL 내부 39.3344 ms가 모두 큰 비중이다.
  PS 전치 0.947 ms는 상대적으로 작다. 83.694 ms와 E08의 81.460 ms를 직접 성능 회귀로
  비교하지 않는다. 계측 비용과 실험 횟수가 다르다.
- **근거:** [콘솔과 수치](../benchmarks/reports/2026-11-15-serial20-profile/README.md).
  이후 프레임별 원본 CSV를 수집해 20프레임과 각 256 FFT의 사이클을 확인했다.
  입력·출력이 새 pipeline 결과와 같았고, 원본 기반 분석 JSON·해시를 같은 폴더에 추가했다.
  카운터 읽기 평균 0.4310505 ms, 기타 미분류 호스트 시간 0.5885925 ms로 잔여도 분리했다.
- **시각 주의:** 파일명의 `20180309_150010`은 보드 wall clock이다. 대화 기준 실험일은
  2026-11-15이며, 지연은 monotonic clock으로 계측하므로 그 파일명으로 연대순을 정하지 않는다.
- **다음 결정:** E10에서 코어 파이프라인과 50 MHz를 적용한다. DMA·PS 전치 최적화는 별도 단계다.

## E10 — 파이프라인과 50 MHz: 보드 비교 검증 완료

- **해결할 문제:** 순차 코어는 448 Butterfly를 각각 6사이클에 처리하며 데이터 이동과 겹치지 않는다.
- **RTL 변경:** `butterfly_pipeline.v`에서 곱셈 → 합/차 → 정규화를 등록 단계로 나누고,
  `fft128_pipeline.v`의 두 RAM bank를 stage별 source/destination으로 교대한다.
  서로 다른 Butterfly의 읽기·연산·쓰기를 겹쳐 stage 내부에서 매 클록 한 개씩 발행한다.
  FFT 코어 여러 개를 복제하거나 호스트 MMIO와 연산을 겹친 구조는 아니다.
- **선택·클록 변경:** `fft128_axi.v`의 `PIPELINED=0` 기본값은 기존 경로다.
  `build_fast.tcl`은 pipeline/50 MHz를 선택하고 reset V3를 유지한다.
  `build.tcl`은 생성 클록 주기와 routed setup/hold를 검사해 실패 시 bitstream 출력을 중단한다.
- **검증:** 두 RTL 경로 각각 272 FFT/34,816 bin, 스트림 backpressure/TLAST, AXI 지연과
  계산 중 abort 후 재실행을 확인했다. 순차 3,073 / 파이프라인 861사이클이 정확히 검증됐다.
  C·참조 테스트 12개와 프로파일 분석 테스트 4개 통과. 이는 새 pipeline의 보드 검증을 뜻하지 않는다.

| 구성 | 보드 전체 시간 | PL 내부 구간 |
|---|---|---|
| serial/20 MHz | E08·E09에서 측정 | E09에서 39.3344 ms 확인 |
| pipeline/20 MHz | 미측정 | **예상** 861×256/20 MHz = 11.0208 ms |
| serial/50 MHz | 미측정 | **예상** 3,073×256/50 MHz = 15.73376 ms |
| pipeline/50 MHz | 비계측 300회 중앙값 25.2591725 ms; 프로파일 평균 27.327809 ms | 보드 861 cycles 확인, 4.408320 ms |

- **구현 완료:** `fft128_ps_pipeline_20261115_224343`의 bitstream·XSA·보고서를 공유 폴더에서
  확인했다. pipeline=1, 50 MHz, reset 사전 검사 PASS; setup WNS 9.807 ns, hold WHS 0.034 ns,
  setup/hold 위반 endpoint 0. DSP 4/80, LUT 1,364/17,600, FF 1,048/35,200,
  BRAM tile 2.5/60이다. 기존 순차 자원량과 비교하면 DSP는 유지하고 LUT·FF·RAM이 늘었다.
  [원본 구현 보고서와 artifact 해시](../benchmarks/reports/2026-11-15-pipeline50-build/README.md)를 보존했다.
- **보드 자체 검사:** 사용자 콘솔에서 ID `0x46543128`, 길이 128, soft reset 완료 및
  `SELFTEST_PASS backend=PL_MMIO vectors=4 bins=512`를 확인했다.
  [보드 근거](../benchmarks/reports/2026-11-15-pipeline50-build/board_selftest.json)를 보존했다.
  생성된 raw BIN SHA256은 `c0f3a5614eb3ec3b86d3775d51b3ae0b854fdeb23a592f29e35e9cc6c520c27c`이다.
  보드에서 배치 파일 해시를 다시 받은 것은 아니므로 펌웨어 식별은 앞선 배치 흐름에 근거한다.
- **보드 프레임 프로파일:** CPU0, 워밍업 2회/측정 20회에서 `FRAME_PASS ... bit_exact_bins=16384`,
  피크 (107,20), FFT당 min=max=861사이클을 사용자 콘솔에서 확인했다. PL 내부 4.408320 ms,
  입력 쓰기 11.526609 ms, 시작·대기 5.054848 ms, 출력 읽기 8.850965 ms,
  gather/scatter 0.946476 ms. 전체 평균 27.327809 ms, 중앙값 27.329907 ms,
  최소 27.291030 ms, 최대 27.403428 ms다. PL 내부는 시작·대기와 겹친다.
- **전후 해석:** E09 계측 평균 83.694257 → 27.327809 ms로 약 3.063배 개선,
  PL 내부는 39.3344 → 4.40832 ms로 약 8.923배 감소했다. 입력+출력 MMIO는
  41.800314 → 20.377574 ms로 줄었고 이제 전체의 약 74.6%다. 전치는 약 0.947 ms로 비슷하다.
  파이프라인과 클록 상향을 함께 변경한 결합 효과이며 MMIO 개선에는 AXI 클록 변경도 포함된다.
- **다음 판단:** 우선 계측 없는 PS–PL 비교로 새 성능 기준선을 확정하고, 그 뒤 지배적인 MMIO
  경로의 DMA·버퍼 교대 등 전송 개선을 검토한다. 아직 DMA 효과를 측정한 것은 아니다.
- **비계측 반복 실행:** 사용자 보드 콘솔에서 PS/PL 3쌍, 각 워밍업 10회·측정 100회 완료를 확인했다.
  PL 세트별 평균은 25.260099 / 25.260553 / 25.263327 ms, 중앙값은
  25.256604 / 25.259575 / 25.260438 ms이고 세 세트 모두 16,384 bin 정수 모델과 일치했다.
  각 세트 표본 수가 같으므로 표시된 평균의 전체 평균은 약 25.261326 ms이며, 기존 E08 PL
  평균 81.525070 ms보다 약 3.227배 짧다. 통합 중앙값은 세트 중앙값을 평균내서 만들지 않는다.
  [콘솔 근거](../benchmarks/reports/2026-11-15-pipeline50-benchmark/README.md)를 보존했다.
- **원본 수집 후 최종 분석:** 각 300회 통합 중앙값은 새 PS 5.557368 ms / PL 25.2591725 ms,
  평균은 5.547364537 / 25.261326367 ms다. PL p05~p95는 25.2371262~25.2841369 ms,
  PS는 5.4931185~5.6052552 ms다. PL은 기존 중앙값 81.460246 ms보다 3.224977배 개선됐고,
  현재 PS보다 4.545168배 느리다. 새 실행에서 PS도 직접 측정한 값으로 비교했다.
- **정확도 재검증:** 세 trial의 입력 해시가 기존과 같고, 새 PL의 저장 출력 모두가 기존 순차 PL
  출력과 비트 단위로 동일했다. NumPy 대비 PL 최대 복소 오차 8.749842 Q15 정수 단위,
  RMS 1.734691, 상대 L2 1.361021%; PS 최대 오차 1.833e-12다. 두 경로 피크는 (107,20).
  전후 프로파일 원본도 수집했으며, 새 counter 읽기 0.3580974 ms / 미분류 호스트 0.5908137 ms다.
- **완료 범위와 한계:** 고정 128×128·warm-cache·오프라인 비교다. DMA·연속 처리·크기 스윕은
  미실시이며, 파이프라인과 클록 상승의 독립 효과를 분리한 보드 실험도 아직 없다.
  원본 전체는 `build/fft128_board_benchmark/results_pipeline50/`와 `profiles/`에 보존하고,
  재계산용 시간 CSV·검증 요약·환경·로그·해시는 보고서 폴더에 보존했다.
  [프로파일 콘솔과 수치](../benchmarks/reports/2026-11-15-pipeline50-profile/README.md)를 보존했다.
  보드 파일명 `profile_20180309_152650.profile.csv`는 보드 시계이고 실제 기록일과 구분한다.
- **혼동 변수:** 다음 빌드는 파이프라인과 클록을 함께 바꾼다. 결과는 결합 효과이며 각 개선의
  독립 효과라고 주장하지 않는다. AXI도 20→50 MHz로 바뀌므로 기존 MMIO 41.8 ms가 그대로
  유지된다고 예측하지 않는다. 독립 기여도가 필요하면 위 4개 구성의 보드 실험을 추가한다.
- **근거:** [RTL 로그·소스 스냅샷](../benchmarks/reports/2026-11-15-pipeline-rtl/README.md),
  [빌드·배치·실행 절차](fft128_optimization.md). 소스는 기준 커밋 이후 작업 트리 변경이며
  해당 시점의 파일 SHA256을 스냅샷으로 보존했다.

## PS01 — PS 정밀도·NEON 기준선: 원본 분석 완료 (2026-11-16)

- **선행 관찰/가설:** E10 PL 25.259 ms는 PS double 5.557 ms보다 느리다. 하드웨어를 더
  바꾸기 전에 float·NEON을 쓰는 PS 기준을 측정해 목표를 정한다. 2~3 ms는 미검증 예시이며
  보드 수치로 취급하지 않는다. 기존 double 결과와 E10 펌웨어는 보존한다.
- **처리 변경:** `udp_radar_receiver.cpp`는 compile-time Real로 float64/float32를 선택한다.
  작업 버퍼·창/전치·정규화가 선택한 정밀도를 사용하며 Q15 스케일 산정은 double로 유지한다.
  원래 32×32 전치·contiguous Doppler·단일 스레드·CPU0·계측 범위는 유지한다.
- **변형 분리:** `build_fftw_arm.sh`의 기본 double 경로를 유지하고 single scalar/NEON을
  추가했다. float 두 라이브러리·수신기는 compiler 자동 벡터화를 모두 끄고 FFTW의 명시적
  NEON codelet만 달리한다. 세 변형은 별도 라이브러리·실행 파일·보드 wisdom을 쓴다.
- **측정 계약:** [PS01 절차](../benchmarks/ps_precision/README.md)의 별도 빌드/배치/실행 도구.
  워밍업 10회, 100회씩 3 trial, 순서를 회전한다. 주 비교는 fft_pipeline이며 UDP/파일/할당/
  양자화/계획/수치 검증은 제외한다. 검증이 캐시에 미치는 영향을 맞추려고 새 double도 재측정한다.
- **정확도:** pinned RadarSimPy 프레임의 NumPy 기준을 PC에서 생성하고 매 반복 C++에서
  16,384 bin을 비교한다. 최대 복소 오차/상대 L2 허용값은 double 1e-7/1e-12,
  float 0.01/1e-5다. 단위는 정규화된 Q15 LSB이며 PL과 float의 bit-exact는 요구하지 않는다.
  검증 실패·NEON plan 미선택·입력/실행 artifact 불일치 시 비교를 중단한다.
- **로컬 확인:** oracle이 기존 보드 double 출력과 일치함을 확인했고, 분석기의 누락·틀린
  NEON 표시·변경 metadata 거부, 실제 C++ 검증기의 float/double·오류·NaN·잘못된 bin 처리를
  포함한 7개 테스트가 통과했다. 이는 ARM FFTW의 수치/성능 검증을 뜻하지 않는다.
- **실제 처리 코드의 추가 수치 확인:** 별도 Windows harness에서 실제 수신기의 FFTW ABI·
  replay·전치·FFT·검증 코드를 사용했다. 공식 FFTW 3.3.5 DLL의 double/float 출력이 NumPy
  기준을 통과했고 MEASURE wisdom 저장·재사용도 확인했다. 최대 복소 오차는 각각
  1.874971e-12 / 0.000426809 Q15 LSB, 상대 L2는 2.943384e-16 / 1.083102e-7이다.
  소켓·CPU affinity와 ARM용 FFTW 3.3.11/NEON은 검증하지 않았고 PC 시간을 보드와 비교하지 않는다.
- **미확인/다음:** Ubuntu ARM 전체 빌드 → 보드 preflight/세 변형 반복 측정 → 원본 회수 후
  분석이 남았다. PL/DMA·클록 변경은 없고 아직 PS01 속도·새 가속비는 없다.
  [준비 단계 근거](../benchmarks/reports/2026-11-15-ps01-preparation/README.md).
- **후속 보드 확인:** 사용자 콘솔에서 preflight 3개, 순서를 회전한 3 trial, 각 100회 및
  `PS_PRECISION_COMPLETE`를 확인했다. 각 변형 300회 모두 16,384 bin 정확도 PASS다.
  최대 복소 오차는 double 1.83315e-12 / float scalar 0.000470413 / NEON 0.000426809,
  상대 L2는 각각 2.9e-16 / 1.1532413e-7 / 1.0831023e-7이다.
- **콘솔 시간의 범위:** FFT only의 300회 평균은 double 3.361187757 / float scalar
  2.721217800 / NEON 1.998061230 ms다. FFT 두 축만의 NEON 개선은 double 대비
  약 1.682배, scalar 대비 약 1.362배다. 전치·복사·정규화 포함 시간이 아니므로
  PS 전체가 2 ms라는 결론이나 E10 PL 전체 시간과의 가속비를 만들지 않는다.
- **빌드 확인·남은 작업:** 공유 폴더의 16개 artifact 해시와 source identity를 대조했다.
  ARM 빌드·보드 실행은 진행됐으며 현재 남은 것은 결과 폴더 회수와 전체 fft_pipeline
  분포·정확도·plan·환경·보드 artifact check의 독립 확인이다. 원시 표본이 없으므로
  중앙값·분위수는 미확인이다. [보드 콘솔 근거](../benchmarks/reports/2026-11-15-ps01-board/README.md).
- **원본 수집 후 최종값:** 각 300회 전체 fft_pipeline 중앙값은 double 5.502540 / scalar
  4.341573 / NEON 3.615852 ms, 평균은 5.498577 / 4.350084 / 3.622898 ms다.
  p05~p95는 double 5.442966~5.566529 / scalar 4.293004~4.409682 /
  NEON 3.563816~3.691539 ms다. 새 double 대비 NEON 변형은 중앙값 1.521782배,
  scalar 대비 1.200705배 빠르다. 기존 E10 double을 이번 비교의 분모로 쓰지 않았다.
- **독립 정확도·설정 확인:** 출력 CSV 9개를 pinned 입력의 NumPy 기준과 비교했다.
  최대 복소 오차는 double 1.833145e-12 / scalar 0.000470412707 / NEON 0.000426808672,
  상대 L2는 2.907011e-16 / 1.1532413e-7 / 1.0831023e-7이며 피크는 모두 (107,20)이다.
  매 반복 로그·전체 표본 수·CPU0·정규화·scale·회전 순서·wisdom과 보드 artifact 16개 OK를
  확인했다. NEON의 preflight/모든 trial 두 축에 실제 NEON codelet이 있고 scalar에는 없다.
- **시간 분해:** NEON 평균은 FFT 두 축 1.998061 + 입력 복사 0.339761 + 전치 0.705625 +
  정규화 0.547702 + 내부 타이머 bookkeeping 약 0.031748 = 3.622898 ms다.
  float 정규화는 double 0.288676 ms보다 길게 관찰됐지만 원인은 아직 분리하지 않았다.
  double→float는 정밀도·버퍼 폭·compiler 자동 벡터화 정책 차이가 포함된 결과다.
- **다음 목표 갱신:** PS 기준은 중앙값 3.615852 ms다. 기존 PL 내부 4.408320 ms만으로도
  이보다 0.792468 ms 길다. 코어/50 MHz/256회 순차 실행을 유지하는 E11 DMA는 전송 비용
  검증 단계이며, PS를 이기려면 이후 연산 또는 겹치기 개선이 필요하다. E10 PL을 이번에
  교차 실행한 것은 아니므로 과거 PL 대비 비율을 새 paired benchmark로 주장하지 않는다.
- **원본 보존:** 전체 결과는 `build/fft128_ps_precision/results_ps01/`, 시간 CSV·로그·wisdom·
  환경·검증 요약·전체 파일 해시는 [완료 보고서](../benchmarks/reports/2026-11-15-ps01-board/README.md)에
  보존했다. 앞선 미확인/대기 문구는 당시 상태이며 이번 분석으로 해소했다. FPGA 변경은 없다.

## E11a — FFT당 Simple DMA 전환 준비

- **질문/관찰:** E10 프로파일의 샘플 MMIO 입출력은 평균 20.377574 ms로 전체의 약 75%다.
  PS01 NEON 목표는 전체 중앙값 3.615852 ms이며, 기존 PL 내부 4.408320 ms보다 짧다.
  DMA만으로 PS를 이긴다고 가정하지 않고 FFT당 DMA 고정 비용과 병목 이동을 먼저 측정한다.
- **선택/고정:** 단일 `fft128_pipeline`과 butterfly/RAM/주소/ROM, Q15 산술·포화·정규화,
  50 MHz, 출력 2클록/sample, FFT당 순차 처리, PS cached gather/scatter를 그대로 둔다.
  코어 파일의 LF 정규화 SHA를 E10 보드 검증 소스와 대조한다.
- **변경:** `fft128_dma_ctrl.v`, `build_dma.tcl`은 Simple AXI DMA(MM2S/S2MM)를 HP0 64-bit에,
  32-bit AXIS를 기존 FFT에 연결한다. SG/DRE off, burst 16, length width 17이다.
  제어 MMIO는 유지하고 payload 창은 제거한다. 기존 BSP의 영상 주소/IRQ와 겹치지 않게
  FFT `0x43c60000`/ID `0x46544480`, DMA `0x40400000`, F2P[6:7]/SPI35:36을 사용한다.
- **버퍼/호출:** `src/PS/fft128/dma/fft128_dma.c`가 DMAengine 채널과 coherent 512 B TX/RX
  bounce buffer를 소유한다. 한 ioctl에 FFT 하나, 프레임 256회/양방향 총 256 KiB다.
  전치는 기존 cached 배열에서 수행하고 추가 CPU↔coherent 복사를 시간에 포함한다.
  포인터 없는 고정 폭 ABI, 단일 소유권, 완료/개수/오류 검사와 중단 시 동기 종료를 둔다.
- **기존 경로 보존:** 기존 MMIO frontend/펌웨어·배치 경로는 유지한다. DMA 빌드/수신기·
  커널 모듈·DT·배치와 결과 디렉터리를 분리한다. 모델 fallback은 없다.
- **측정 범위:** 준비된 Q15 입력부터 CPU에서 두 축 결과를 사용할 때까지 복사·ioctl·
  DMA·FFT·PS 전치를 포함한다. 할당·UDP/파일·양자화·검증은 제외한다. 별도 계측은 host
  copy/ioctl/전치와 nested kernel copy/submit/wait/check를 기록한다. 내부 시간은 중복 합산하지 않는다.
  `cycles`는 DMA 정지를 포함하는 active 구간으로 정의하고 input/output stall 카운터를 추가한다.
- **로컬 RTL 확인:** `python src/PL/fft128_ps/verify_dma.py` 및 추가 counter 검사에서
  272벡터/34,816 bin 정수 모델 일치, 입력 공백/출력 backpressure, payload 유지,
  잘못된 TLAST/TKEEP, 부분 입력·계산 중 abort 후 복구, AW/W 순서·응답 지연이 통과했다.
  active에서 스트림 정지를 빼면 **861 cycles/FFT**로 일정했다. 이는 RTL 확인이며 보드 실측이 아니다.
  기존 serial/pipeline 회귀도 통과했고 산술 코어를 바꾸지 않았다.
- **소프트웨어 확인:** 기존 native 회귀 9개와 새 CLI/DT 충돌·nested 계측 분석 검사 11개가
  개발 PC에서 통과했다. 사용자 Ubuntu의 ARM hard-float 정적 수신기 빌드 및
  `dtc`/`fdtoverlay`의 기록 DT 적용도 통과했다. 새 보드 ABI 검사기는 실제 실행 전이다.
- **보드 조회 근거:** 현재 5.15.19-xilinx는 DMAengine/Xilinx DMA/CMA, 모듈/심볼 CRC,
  OF configfs overlay가 활성화돼 있다. CMA 총 16 MiB, 조회 시 free 16,096 KiB다.
  이 조회는 버퍼 할당·DMA 전송 PASS를 뜻하지 않는다. 일치하는 커널 빌드 산출물이 없어
  BSP가 지정한 Digilent 5.15.19 소스와 기록 설정으로 후보 빌드 트리를 준비한다.
  원래 커널 소스의 정확한 provenance는 미확인이며 정상 모듈 로딩의 CRC 수락이 필요하다.
  후보 full kernel/Module.symvers 및 ARM 모듈 빌드는 완료했다. 이 커널을 설치하지 않았고
  사용자 보드 콘솔에서 대응 DT 없는 정상 로드/언로드 및 실제 CRC 수락을 확인했다.
  FPGA 레지스터 접근이나 DMA 전송은 이 검사에서 수행하지 않았다.
  새 Vivado run `fft128_dma_e11a_20261116_005936`의 실제 generated reset IP 검사에서도
  ID/length·lock-loss recovery가 done=1 passed=1로 통과했다. 합성/route 결과는 대기 중이다.
  이후 같은 run의 bitstream/XSA 생성과 post-route 보고서를 확인했다. 50 MHz에서
  WNS 10.607 ns/WHS 0.021 ns, setup/hold 위반 및 미제약 내부 endpoint는 0이다.
  LUT 3,210/17,600, FF 3,987/35,200, BRAM tile 5/60, DSP 4/80이다.
  실제 BD의 HP0/DDR·AXIS·제어 주소·F2P6/7 IRQ와 DMA 설정을 대조했고 PL/host/module
  source SHA가 현재 공유 소스와 일치했다. 이전 대기 문구는 이 확인으로 해소됐다.
  [구현 보고서와 원본/해시](../benchmarks/reports/2026-11-16-e11a-build/README.md).
  보드 DMA 자체 검사·전체 프레임·새 시간 측정은 아직 남아 있다.
  최초 보드 적용에서 manifest 20개 OK, HP0 read/write 64-bit와 BIN 로드(51 ms)는
  확인했지만 overlay/module 뒤 DMA client가 bind하지 않아 자체 검사 전에 중단했다.
  원인은 아직 미확인이다. 이 실패를 보존하고 platform device/커널 로그를 확인한다.
  FPGA Manager 로드 성공을 DMA 검증 PASS로 취급하지 않는다.
  후속 사용자 조회에서 `fft128-e11a-bus`, `fft128-e11a-clock`만 있고 DMA/FFT platform
  device가 없음을 확인했다. 현재 커널의 동적 OF 알림은 부모가 OF_POPULATED_BUS인
  장치를 생성하는데 새 simple-bus 아래 자식은 생성되지 않는 구조였다. 기존 `/amba_pl`
  아래 DMA/FFT를 직접 추가하는 overlay v2로 수정했다. 클록·주소·IRQ·DMA 파라미터·
  FPGA firmware·커널 모듈은 그대로 유지한다. PC 검사 12개가 통과했고 새 bundle의
  raw BIN이 최초 bundle과 같아야 배치하도록 했다. 보드 재적용·DMA 자체 검사는 대기 중이다.
  이후 사용자 보드 재적용 콘솔에서 21개 artifact OK, AXI DMA 및 FFT client probe,
  `DMA_CLIENT_PASS`와 실제 `PL_DMA` 4벡터/512 bin `SELFTEST_PASS`를 확인했다.
  v2 DT 외 BIN·모듈·수신기·ABI 검사기는 최초 bundle과 byte 단위로 같았다.
  앞선 등록·자체 검사 대기는 해소됐다. FPGA 로드 49 ms는 FFT 측정이 아니다.
  전체 128×128 프레임·20회 profile·비계측 paired 비교는 아직 남아 있다.
  [v2 보드 근거](../benchmarks/reports/2026-11-16-e11a-build/dt_v2_selftest_console.log).
  이어 `profile_e11a_01` 사용자 콘솔에서 CPU0/warmup 2/repeat 20, 실제 PL_DMA의
  16,384 bin 정수 모델 검증과 peak (107,20)을 확인했다. 계측 포함 평균 18.136317 ms,
  중앙값 18.129750 ms, 최소 18.071028/최대 18.224922 ms다.
  host ioctl 15.199543 ms 안에 kernel copies 1.004211 ms와 wait 9.406124 ms가 포함된다.
  PS gather/scatter 1.002013 ms, 스트림 정지를 포함한 PL active 4.482577 ms다.
  중첩 구간은 합산하지 않으며 wait를 순수 DMA 전송 시간으로 보지 않는다.
  [최초 프레임 콘솔](../benchmarks/reports/2026-11-16-e11a-build/first_frame_profile_console.log).
  원시 CSV·카운터 관계 확인과 별도 비계측 PS double/NEON/PL 각 300회 비교는 대기 중이다.
  **원본 회수 후 완료:** CPU0/warmup 10/100회×3 회전 trial의 원시 CSV·로그·artifact/입력
  신원을 확인했다. 전체 중앙값은 double 5.748489 / NEON 3.715234 / PL DMA 15.411639 ms,
  평균은 5.737376 / 3.726932 / 15.415091 ms다. PL은 이번 NEON보다 약 4.15배 느리다.
  과거 E10 MMIO 중앙값 25.259173 ms 대비 약 1.639배 개선/지연 39.0% 감소지만 과거 실행과의
  비교임을 구분한다. 이번 PS 대신 PS01 과거 시간을 분모로 사용하지 않는다.
  PL 마지막 출력 3개와 profile 출력은 독립 Python Q15 모델에 전부 일치했고 매 반복 보드
  정수 검증도 통과했다. PL NumPy 최대 오차 8.749842363 LSB/상대 L2 1.361%로 기존 산술을 유지했다.
  두 DMA IRQ는 CPU0에서 각각 84,480회 증가해 330프레임×256회와 맞았다.
  원시 profile 20행 모두 active−input/output stall=861 cycles/FFT이며, PL nonstall 환산
  4.408320 ms와 stream stall 평균 0.074257 ms를 확인했다. output stall은 0이다.
  ioctl 내부 submit/start 2.939423 / wait 9.406124 / copy 합 1.004211 / check 0.654666 /
  잔여 1.195118 ms다. wait와 PL active는 중첩되며 순수 DMA 전송 시간으로 보지 않는다.
  다음은 E11b에서 코어·클록·출력 스케줄을 유지한 채 제출/완료 단위를 묶어 고정 비용을 줄이는
  실험이다. 단순히 ioctl만 묶고 내부 DMA/IRQ 횟수를 유지하는 구현과 구분해야 한다.
  [원시 시간·프로파일·해시·분석 보고서](../benchmarks/reports/2026-11-16-e11a-board/README.md).
- **미확인/다음:** 모듈 빌드 → 대응 DT 없이 모듈 로드/언로드로 CRC 확인 →
  Vivado 통합/생성 reset IP·route 타이밍/자원 → 새 펌웨어/overlay 적용·ABI/self-test →
  전체 프레임 → 별도 20회 profile → PS double/NEON/PL 각 300회 비교다.
  이 순서의 검증을 모두 완료했다. 앞선 처리 시간·가속비 대기는 이후 원본 분석으로
  해소됐다. 다음은 E11b이며 묶음 제출은 아직 적용하지 않았다.
- **원본/신원:** [E11a 준비 보고서](../benchmarks/reports/2026-11-16-e11a-preparation/README.md)에
  소스 SHA, 입력/조회 근거 SHA와 RTL·테스트 결과를 보존한다. 큰 빌드/펌웨어는 `build/`에 둔다.
- **후속 검토 반영(계획, 새 측정 아님):** E11a 계측에서 복사 합은 2.256989 ms다.
  nonstall 4.408320 + stream stall 0.074257 + 복사 + 전치 1.002013의 단순 합은
  7.741579 ms이며, E11b의 초기 5.5~6 ms 가설보다 큰 비용을 관찰했다.
  새 예산은 약 8 ms 수준의 조건부 가설로 갱신하고 실제 64 KiB 복사·제출을 다시 잰다.
  E11b에서는 coherent/cached 정책을 고정하고 TLAST를 축 경계로 변환한다.
  약 41.86 us/FFT 잔여를 순수 SW/IRQ 비용으로 단정하지 않는다. E11c 출력 개선과
  E11d 버퍼 정책을 분리하고 E12/E13 순서는 E11b 프로파일 후 정한다.
  PS02 전치·정규화 결합은 별도 계획이다. PS01 평균에서 정규화만 제거한 계산은
  3.075196 ms이며 2.7~3.0 ms는 추가 개선 목표다. 기존 PS01을 함께 재측정한다.
  빌드 원본의 board_verified=false는 유지하고 실제 검증한 artifact 해시별 완료 상태를
  [별도 검증 기록](../benchmarks/reports/2026-11-16-e11a-board/board_verification.json)으로 명시했다.

## E11b — 축당 128 FFT 묶음 제출 (2026-11-19)

- **문제/가설:** E11a의 프레임당 256 ioctl/512 DMA 채널 제출 비용을 축당 하나로 줄인다.
  약 8 ms는 작업 가설이며 아직 측정값이 아니다.
- **고정:** 단일 fft128_pipeline/50 MHz/Q15/출력 2클록/sample, cached PS 전치 및
  사용자·커널·coherent 복사 단계. 전송/연산 겹치기·새 버퍼 정책·PS02는 섞지 않는다.
- **변경:** 별도 fft128_dma_batch_ctrl/빌드, DMA batch ABI2/드라이버/수신기/배치 경로.
  프레임당 2 ioctl/4 DMA 채널 제출, 축당 방향별 64 KiB, FFT 256회다.
  외부 TLAST는 축 마지막에만 내보내고 내부 FFT별 경계를 생성한다.
- **로컬 검증:** verify_dma_batch.py PASS. 272 독립 벡터와 1/2/128 FFT 패킷,
  backpressure·입력 공백·오류 TLAST/TKEEP·abort/recovery 및 E11a 회귀 확인.
  active−stream_stalls = 861*128 cycles/axis. 코어 및 전송/연산 비겹침을 확인했다.
- **미확인:** ARM 모듈·수신기 빌드, Vivado reset/IP/route/timing, 실제 보드 ABI/전송,
  full frame/profile/각 300회 paired 비교. 새 속도·자원·보드 PASS는 아직 없다.
- [준비·검증 기록](../benchmarks/reports/2026-11-19-e11b-preparation/README.md).

- **빌드 확인:** 사용자 완료 후 실제 Vivado run `fft128_dma_e11b_20261119_232506`를 확인했다.
  generated reset IP/AXI ID·ABI·batch 검사, bitstream/XSA, ARM 정적 수신기·ABI 검사기·모듈 빌드 PASS.
  50 MHz WNS 10.618 ns/WHS 0.016 ns, setup/hold 위반·미제약 내부 endpoint 0.
  LUT 3,243/FF 4,017/BRAM tile 5/DSP 4. 실제 BD의 HP0/AXIS/주소/IRQ/길이폭을 확인했다.
  PL/host/module build 소스와 현재 checkout SHA, ARM artifact manifest를 독립 대조했다.
  앞선 빌드 미확인 상태는 해소됐고 보드 CRC/자체 검사/프레임/profile/paired 비교는 남아 있다.
  [빌드 원본·해시](../benchmarks/reports/2026-11-19-e11b-build/README.md).

- **보드 자체 검사 확인:** 사용자 PetaLinux 콘솔에서 HP0 read/write `0x00000000/0x00000F00`,
  FPGA Manager BIN 로드, AXI DMA probe, E11b client bind와 정상 모듈 로드를 확인했다.
  1 FFT/512 B와 두 차례 128 FFT/65,536 B 패킷 모두 완료 개수 및 정수 모델 비교 PASS,
  독점 소유·잘못된 ABI/timeout/flags/count 거부 검사와 4벡터/512 bin 수신기 자체 검사도 PASS다.
  `DMA_E11B_SELFTEST_READY`까지 도달했으며 로컬 bundle 20개 artifact 해시를 독립 확인했다.
  FPGA 로드 63 ms는 FFT 성능이 아니다. full frame/profile/각 300회 비교는 남아 있다.
  [보드 콘솔·검증 범위](../benchmarks/reports/2026-11-19-e11b-build/board_selftest.json).

- **원본 회수 후 완료:** 사용자 Ubuntu 수집 폴더를 복사해 독립 재계산했다.
  CPU0/warmup10/repeat100×3 회전 trial 각 300회 중앙값은 double 5.717376 / NEON 3.558177 /
  PL 6.433026 ms, PL p05/p95 6.396787/6.474537 ms, 최대 6.505416 ms다.
  과거 E11a 15.411639 ms 대비 2.395706배 개선·지연58.258651% 감소이며 과거 실행과의 비교다.
  이번 paired NEON보다 1.807956배, double보다 1.125171배 느리다.
  모든 반복 보드 정수 검증과 마지막 출력3개/profile 출력의 독립 Python 정수 일치,
  NumPy 상대 L2 1.361020928%·피크(107,20), artifact/source/입력/NEON plan을 확인했다.
  IRQ67/68은 CPU0에서 각각660회 증가해 330프레임×2축과 맞았고 CPU1 증가는0이다.
- **프로파일/해석:** 별도20회 평균6.473645 ms. PL active4.408947 ms(68.1%), nonstall4.408320 ms,
  입력 stream stall0.000627 ms/출력stall0, 사용자+커널 복사합1.263008 ms, 전치0.670374 ms다.
  ioctl5.360488 ms 내부 wait4.461962 ms는 PL active와 겹치므로 합산하지 않는다.
  submit/start0.035202 ms로 요청·완료 비용은 줄고 내부 LOAD/CALC/OUTPUT 구간이 가장 크다.
  코어·정밀도·복사단계는 유지했지만 묶음 크기가 메모리 접근 간격도 바꾸어 복사·전치 시간도
  달라졌다. 과거 프로파일과의 차이를 ioctl 횟수 감소만의 독립 효과로 단정하지 않는다.
  약8 ms 작업 가설보다 짧았으며, 원시값으로 가설을 대체하지 않고 차이를 보존한다.
- **후속 선택/범위:** E13 연산 구조 확대를 주 가속 후보로 검토한다. E11c 출력개선은 별도
  무정지 약0.65 ms 상한을 확인할 수 있다. E12는 내부 LOAD/OUTPUT 겹치기 여지가 있으므로
  외부stream stall이 작다는 이유만으로 배제하지 않는다. 새 단계는 아직 실행하지 않았다.
  12.8 ms 미만은 오프라인 지연만이며 연속 UDP/실시간 보장은 미검증이다.
- **근거:** [E11b 완료·원시 시간·해시·분석](../benchmarks/reports/2026-11-19-e11b-board/README.md).
  계측trial 혼입/1LSB 변조 출력 거부도 확인했다. 측정 bundle의 board_verified:false를
  보존하고 검증된 해시별 완료 상태를 별도 board_verification.json에 기록했다.

## 이후 기록할 실험

1. **E10 완료값 보존:** E08/E09 원본을 유지하고 새 구현·프로파일·비계측 비교 결과를 기준선으로 삼는다.
2. **클록/구조 분리 실험:** 필요 시 serial/pipeline × 20/50 MHz, 같은 입력·동일 측정 조건.
3. **PS01 선행 계획:** 하드웨어 변경 전 double/float scalar/float+NEON을 같은 보드에서
   비교 완료했다. 원본·정확도·설정 검증 PASS이며 목표는 NEON 전체 중앙값 3.615852 ms다.
4. **E11~E14 계획:** [단계별 가속 계획](fft128_dma_plan.md)에 전송 단위·버퍼/cache 위험,
   ACP 별도 비교, 측정 경계·통과 조건·사전 수치 가설을 명시했다. E11a는 기존 코어/50 MHz와
   FFT당 순차 호출을 유지한 DMA 전환, E11b는 축당 묶음 제출이다. E11c는 2사이클 출력의
   독립 개선으로 이상적 절감 약 0.65 ms이며, E12/E13 순서는 E11b 병목으로 선택한다.
   E11b의 5.5~6 ms는 추가 비용이 작은 조건의 가설이며 실측값이 아니다.
   계획서 작성 당시 E11 이후는 전부 계획 상태였다. 2026-11-16에는 E11a 소스 구현과
   FPGA 통합과 보드 DMA 자체 검사까지 진행했고 상세는 위 E11a 항목에 기록했다.
   이후 E11a 및 E11b 보드 프레임 성능·원본 검증도 완료했다. E11c~E14는 계획이며 실행 환경 수정은 실험으로 기록하지 않는다.

## 다음 실험에 사용할 기록 양식

```text
ID / 날짜 / 선행 실험:
질문과 변경 전 관찰:
가설 / 변경 선택 이유:
변경 파일 / Git commit 또는 소스 SHA / RTL·클록·버퍼·전송 설정:
입력 파일 SHA / 프레임 크기 / 창·양자화·정규화:
보드·OS·컴파일러·flags·FFTW·CPU affinity·확인된 주파수:
실행 명령 / Vivado run / firmware 및 실행 파일 SHA:
시간 측정 시작·종료 / 포함·제외 / 중복 구간 / 계측 overhead:
warmup / repeats / trial 순서:
결과: 실패 로그 또는 정확도·시간 분포·자원·setup/hold:
해석: 이번에 확인된 것 / 확인하지 못한 것 / 여러 변경의 혼동 변수:
다음 조치 / 보류 항목:
원본 파일 경로 / 보고서 경로 / 증거 종류(보드·콘솔·시뮬레이션·예상):
```

원본 기록은 `benchmarks/reports/<날짜>-<실험>/`에 작은 텍스트·JSON·CSV로 보존한다.
대용량 프로젝트·바이너리는 `build/`에 두고 경로·해시를 기록한다. 통계 재계산에 필요한 원본이
없으면 그 사실을 표시한다. 후속 기록은 이전 결론을 삭제하지 않고 교정 사유와 함께 추가한다.
