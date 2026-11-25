# FMCW FFT 실험 일지

처리 로직·구조·클록·전송·정밀도·측정 범위를 바꾼 실험을 **질문 → 변경 → 검증 경과 → 결과 →
해석 → 다음**의 순서로 기록한다. 스크립트 문법·경로·배치·일반 환경 설정만 고친 작업은 기록하지 않는다.

- 날짜는 Asia/Seoul 기준이다. 일지는 2026-11-15에 처음 작성했고 그 이전 단계(E01~E05)는
  대화와 남은 결과 파일에서 복원했다. 원본이 없는 항목은 그 사실을 적었다.
- 과거 실측값·실패·철회한 결론은 지우지 않는다. 다음 실험에서 바뀐 판단은 새 항목에 적고 링크한다.
- 증거 종류를 구분한다: **보드 실측**(원시 파일 회수·독립 재계산), **사용자 콘솔**(콘솔 출력만 확인),
  **RTL/PC 시뮬레이션**, **사이클 환산·가설**. 가설로 실측을 채우지 않는다.
- 시스템 목표와 S 단계는 [시스템 목표와 단계 계획](system_goal_plan.md), FFT 가속 계획은 [단계별 가속 계획](fft128_dma_plan.md), 커밋 해시 대응표는
  [커밋 해시 대응표](commit_hash_map.md)에 있다.

## 현재 상태 (2026-11-25 기준)

- **최신 성능 검증 구성:** E14-frame / 단일 전용 DIT 7단계 FFT 재사용 / PL 전치·최종 배열 복원 / 50MHz·Q15 / 전체 프레임 HP0 Simple DMA.
- **최신 paired 비교(각 300회 중앙값):** PS double **5.706612 ms** / PS float+NEON **3.489441 ms** /
  PL **1.657914 ms**. 같은 회차 NEON 대비 2.104718배 빠르고 지연은 52.49% 짧다.
  [완료 보고서](../benchmarks/reports/2026-11-21-e14-frame-board/README.md).
- **E13 완료 범위:** 2·4코어 복제 → E12 입출력 겹치기 → 코어당 버터플라이 2개 → 전용 7단계 스트리밍을 각각 구현·측정했다.
  마지막 구성은 4코어에 스트리밍을 더한 것이 아니라 단일 7단계 파이프라인으로 교체한 구조다.
- **현재 비용:** 별도20회 계측 평균 전체1.700746ms, PL active1.038842ms (최종 배출0.327700ms 포함), 복사0.590928ms, CPU 전치0.
  PL active는 ioctl 대기와 겹치므로 호스트 단계에 더하지 않는다.
- **E14 완료:** PL 중간 결과 보관·전치·최종 배열 순서 복원, RTL·host53개·ARM/Vivado·보드 자체 검사·20회profile·각300회paired·원시82파일 독립 검증 완료. 연속 프레임 검증은 별도다.
- **S1a(PC):** 고정 입력이 무잡음임을 확인, 잡음 포함 시나리오에서 hann+CA 잠정 기준. [S1a](#s1a--cfar-기준-모델과-ground-truth).
- **S1b 완료:** 보드 기록 재생6구성·각100회와 실제 UDP Hann 4표적 한 프레임을 원본 독립 검증했다.
  UDP 검출4/4·오검출0, FFT와 검출 CSV는 같은 조건의 보드 기록 재생과 같다.
- **S1c 완료:** 실제 E14 잡음 기록6구성·각100회에서 정수 FFT 모든 bin과 CFAR가 독립 기준에 일치했다.
  검출 목록은 float와 같고 근접 약표적1/3 한계도 유지된다. 다음은 S2a 통합 연속 처리 계측이다.
- **S2a 준비:** 별도 통합 수신기·RSPY v2 프레임 ID·수신/처리 큐·커널 시각·CPU/RSS 기록을 구현했다.
  초기 PC 검사7개와 Ubuntu 스모크3개·ARM 빌드는 통과했지만 첫 보드 PS는2560패킷 전부 거부했다.
  S2a-rxfix1의 PC8검사·수정 Ubuntu3스모크·ARM 빌드 통과.사용자 보드 진단으로36B 버퍼의
  control truncation을 확인했다. 이후 보드 PS/PL 각각20프레임·각4/4검출/오검출0·드랍0 원본 독립 검증 완료다.
  S2a 완료, 다음 S2b는 진단을 끈12.8ms/200프레임 예비 검사 후10,000프레임 본검사다.
- **미실시:** PS02, 독립 E11c·E11d, 연속 프레임/UDP 처리량·최악 지연·누락, 크기 스윕, PL 결과 기반 CFAR.
- **후속 순서 (11-25 갱신):** [시스템 계획](system_goal_plan.md)의 S1 → S2 → S3. [E15-memory](#e15-memory--메모리-계층별-크기-비교-계획)는 S3b에서 utilization 점검 → BRAM·OCM → DDR 타일 전치 순으로 검토한다. 기존 자료 점검 완료, 새 구현·보드 측정 미실시.

### PL 경로 성능 추이 (비계측, 각 300회 중앙값, 같은 보드·같은 입력)

| 실험 | PL 구성 | 같은 회차 PS double | 같은 회차 PS NEON | PL 경로 |
|---|---|---:|---:|---:|
| E08 | 순차 / 20 MHz / MMIO | 5.550039 ms | — | 81.460246 ms |
| E10 | 파이프라인 / 50 MHz / MMIO | 5.557368 ms | — | 25.2591725 ms |
| PS01 | (PL 미실행) | 5.502540 ms | 3.615852 ms | — |
| E11a | 파이프라인 / 50 MHz / FFT당 DMA | 5.748489 ms | 3.715234 ms | 15.411639 ms |
| E11b | 파이프라인 / 50 MHz / 축당 묶음 DMA | 5.717376 ms | 3.558177 ms | 6.433026 ms |
| E13-2core | 기존 코어 2개, pair barrier / 50 MHz | 5.767263 ms | 3.646212 ms | 4.920621 ms |
| E13-4core | 기존 코어 4개, group barrier / 50 MHz | 5.767911 ms | 3.649998 ms | 4.186353 ms |
| E12-4core | 4코어, FIFO·독립 스케줄 / 50 MHz | 5.711883 ms | 3.488904 ms | 3.129210 ms |
| E13-bf2 | 4코어, 코어당 버터플라이 2개 / 50 MHz | 5.708112 ms | 3.520371 ms | 2.841720 ms |
| E13-stream | 전용 7단계 프레임 스트리밍 / 50 MHz | 5.826396 ms | 3.652869 ms | 2.787411 ms |
| E14-frame | PL 전치·최종 배열 복원 / 50 MHz | 5.706612 ms | 3.489441 ms | 1.657914 ms |

실험 사이의 PL 비율은 서로 다른 회차의 비교다. 같은 회차 PS 값도 회차마다 달라졌으며 원인은 확인하지 않았다.

## 실험 색인

| ID | 날짜 | 질문 | 주요 변경 | 상태와 핵심 결과 |
|---|---|---|---|---|
| [E01–E02](#e01e02--기존-32-point-fft-보드-이식) | 11-13 | 기존 32-point 설계가 보드에서 동작하는가 | 보드용 multiplier/adder/clock 대체, 마지막 단계 이후 캡처 | 완료. 5벡터/160 bin 보드 PASS, DSP 64/80 |
| [E03](#e03--128128-처리-구조-선정) | 11-14 | 128×128이 작은 FPGA에 들어가는가 | 128-point 반복 코어 하나를 두 축에 재사용 | RTL 272 FFT/34,816 bin PASS |
| E04 | — | — | — | 번호만 비어 있고 기록 없음 |
| [E05](#e05--mmio-정지-reset-ip-극성) | 11-15 | MMIO 첫 ID 읽기가 왜 멈추는가 | 독립 보드 클록, reset 극성 명시, 생성 IP 사전 검사 | 원인 확인·수정. ID·self-test 정상 |
| [E06](#e06--radarsimpy-입력의-전체-보드-처리) | 11-15 | 시뮬레이터 입력 전체 경로가 맞는가 | RadarSimPy → UDP → PS → PL 두 축 | 16,384 bin 정수 모델 일치, 단일 82.024044 ms |
| [E07](#e07--잘못된-성능-비교-철회) | 11-15 | PC NumPy와 보드 시간을 비교해도 되는가 | 비교 기준을 같은 보드 PS로 변경 | 시간비 약 318 **철회** |
| [E08](#e08--같은-보드-ps-대-순차-pl-기준선) | 11-15 | 최적화 PS 대비 PL은 빠른가 | 입력·정규화·측정 범위 정렬, CPU0, 반복 측정 | PS 5.550 / PL 81.460 ms, PL이 14.677배 느림 |
| [E09](#e09--순차-20-mhz-병목-분해) | 11-15 | 81 ms 중 연산·전송·전치 비중은 | 사이클 카운터와 호스트 단계 계측 | 3,073 cycles/FFT, PL 내부 39.334 / MMIO 41.800 ms |
| [E10](#e10--파이프라인-코어와-50-mhz) | 11-15 | 순차 연산과 낮은 클록을 개선할 수 있는가 | 파이프라인 butterfly, stage ping-pong RAM, 50 MHz | 861 cycles/FFT, PL 25.259 ms (3.225배 개선) |
| [PS01](#ps01--ps-정밀도neon-기준선) | 11-15~16 | PS 목표 성능은 어디인가 | double / float scalar / float+NEON | NEON 3.615852 ms, double 대비 1.522배 |
| [E11a](#e11a--fft당-simple-dma) | 11-16 | FFT당 작은 DMA의 고정 비용은 | MMIO payload → HP0 Simple DMA, FFT당 ioctl | PL 15.411639 ms, 계측 평균 18.136318 ms |
| [E11b](#e11b--축당-128-fft-묶음-제출) | 11-19 | 256번의 작은 DMA 요청 비용을 줄일 수 있는가 | 축당 128 FFT/64 KiB, 프레임당 2 ioctl·4 채널 제출 | PL 6.433026 ms (E11a 대비 2.396배), IRQ 각 660회 |
| [E13-2core](#e13-2core--2코어-병렬-실행) | 11-20 | 두 코어를 겹치면 얼마나 빨라지는가 | 기존 코어 2개, pair barrier | 완료. PL 4.920621 ms, 계측 active 2.857541 ms ([보고서](../benchmarks/reports/2026-11-20-e13-2core-board/README.md)) |
| [E13-4core](#e13-4core--4코어-확장) | 11-20 | 코어 수를 두 배로 늘린 효과는 | 기존 코어 4개, group barrier | 완료. PL 4.186353 ms, 계측 active 2.081883 ms ([보고서](../benchmarks/reports/2026-11-20-e13-4core-board/README.md)) |
| [E12-4core](#e12-4core--입출력계산-겹치기) | 11-20 | 공유 입출력·장벽 비용을 숨길 수 있는가 | 4코어, FIFO·독립 스케줄 | 완료. PL 3.129210 ms, 계측 active 1.124590 ms ([보고서](../benchmarks/reports/2026-11-20-e12-4core-board/README.md)) |
| [E13-bf2](#e13-bf2--버터플라이-확대) | 11-21 | 코어 내부 CALC를 줄일 수 있는가 | 4코어, 코어당 버터플라이 2개 | 완료. PL 2.841720 ms, 계측 active 0.837903 ms ([보고서](../benchmarks/reports/2026-11-21-e13-bf2-board/README.md)) |
| [E13-stream](#e13-stream--프레임-스트리밍) | 11-21 | 벡터의 단계 처리를 겹칠 수 있는가 | 전용 7단계 프레임 스트리밍 | 완료. PL 2.787411 ms, 계측 active 0.711424 ms ([보고서](../benchmarks/reports/2026-11-21-e13-stream-board/README.md)) |
| [E14-frame](#e14-frame--pl-전치와-전체-프레임-dma-진행-중) | 11-21 | 중간 왕복·CPU 전치를 없앨 수 있는가 | 같은 FFT 재사용·64KiB in-place 행렬·1요청/프레임 | 완료. PL1.657914ms/NEON 대비2.104718배, profile active1.038842ms·복사0.590928ms·CPU 전치0 ([보드 결과](../benchmarks/reports/2026-11-21-e14-frame-board/README.md)) |
| [S1a](#s1a--cfar-기준-모델과-ground-truth) | 11-25 | CFAR 기준 모델이 ground truth를 찾는가 | 목표 재정의, PC CA/OS CFAR 모델, 잡음 포함 시나리오 | PC 완료. 고정 기록은 무잡음으로 확인. hann+CA 잡음 4표적 4/4·오검출0, 근접 약표적은 CA masking, 잡음 기록 3개 생성 ([보고서](../benchmarks/reports/2026-11-25-s1a-pc/README.md))
| [E15-memory](#e15-memory--메모리-계층별-크기-비교-계획) | 11-21 | 크기별 메모리 배치의 자원·성능 경계는 | utilization 점검 → BRAM·OCM → DDR 타일 전치 | 계획. 기존 E14 RAM 구조 확인, 새 변형 구현·측정 미실시 |
| [S1b](#s1b--ps-수신기-ca-cfar-구현pc-커널-검증) | 11-25 | PS 수신기 CA-CFAR가 S1a와 같은가 | C++ summed-area CA-CFAR·검출 CSV·단계 시간·검증 번들 | 완료. 기록 재생6구성·각100회 및 실제 UDP Hann 4표적4/4·오검출0 원본 독립 검증. CFAR 반복 중앙값3.690945ms·UDP1회3.890856ms |
| [S1c](#s1c--pl-q15-출력의-cfar-비교-준비) | 11-25 | PL 단계별 Q15 스케일·포화 후에도 검출이 같은가 | 기존 E14 출력 → 같은 C++ CA-CFAR, Hann 선적용 입력 | 완료. 실제 PL 6구성·각100회 모든 정수 bin·CFAR 독립 검증, float 검출과 일치. 성분별 시간만 측정 |
| [S2a](#s2a--통합-연속-수신과-프레임자원-계측-준비) | 11-25 | 연속 처리의 지연·드랍·CPU를 관측할 수 있는가 | 별도 PS/E14 통합 프로세스·v2 프레임 ID·유한 큐·타임스탬프·CPU/RSS | 완료. 보드 PS/PL 각각20프레임·각4/4검출·오검출0·드랍0·trace 원본 독립 검증. 진단 실행이며 S2b 합격 주장은 없음 |
| [S2a-rxfix1](#s2a-rxfix1--arm32-수신-보조-데이터-호환거부-진단) | 11-25 | 보드의2560패킷 전부 거부 원인은 | 보조 버퍼512B·time32/time64·거부별 계수·구버퍼 peek·idle 종료 수정 | 완료. 구버퍼 원인 확인, 수정 후 PC8·Ubuntu3·ARM·보드 PS/PL 각각20프레임 원본 독립 검증 통과 |
| [S2b](#s2b--128ms-연속-부하-검사-준비) | 11-25 | 12.8ms 주기에서 드랍0·P99 목표를 지키는가 | 같은 binary에서 진단flag 해제·50ms→12.8ms, 먼저200프레임 | 준비. 예비 검사 및10,000프레임 본검사 실측 전 |

## 공통 조건과 해석 규칙

- **보드·도구:** Zybo Z7-10 / XC7Z010-1CLG400C, Vivado 2022.1, ARMv7 hard-float,
  PetaLinux kernel `5.15.19-xilinx`. Ubuntu 20.04.6은 빌드·TFTP·NFS 호스트다.
- **입력:** [RadarSimPy 기록](../benchmarks/fixtures/README.md) 128×128, SHA256
  `aa06ff124034310216693c1398f2f1061c9a6ce32e9ea6f5687675849934c976`,
  한 채널, fs 1.6 MHz, 표적 30 m / -10 m/s. 입력 기록에는 FFT 결과가 들어 있지 않다.
- **처리:** 창 없음, 같은 Q15 양자화 입력, 전체 정규화 1/16384. PS FFTW는 double(PS01부터 float 변형 추가), PL은 Q15 고정소수점.
- **CPU 주파수:** 직접 확인하지 못했다. BogoMIPS에서 추정한 667 MHz를 실측값으로 쓰지 않는다.
- **검증 단계 구분:** `SOFTWARE_MODEL` PASS, RTL PASS, bitstream 생성, FPGA Manager `operating`,
  실제 보드 `SELFTEST_PASS`/`FRAME_PASS`는 서로 다른 확인 단계다.
- **중복 금지:** 사이클 환산 PL 내부 구간은 호스트의 시작·대기(또는 ioctl wait) 구간과 겹치므로 더하지 않는다.
- **계측 분리:** 프로파일 실행은 타이머·레지스터 읽기가 추가된다. 비계측 성능 비교와 같은 모집단으로 합치지 않는다.
- **범위:** 같은 프레임 반복은 캐시가 데워진 오프라인 지연이다. 연속 UDP 처리량이나 실시간 보장을 뜻하지 않는다.

---

## E01–E02 — 기존 32-point FFT 보드 이식

- **질문:** GitHub 32-point DIT FFT 설계(서브모듈)를 Zybo에 올려 동작시킬 수 있는가.
- **관찰:** 최초 `place_design ERROR`. 이후 보드·RTL에서 `passed=1 errors=81`,
  `first=40 actual=0 expected=16777216`(시뮬레이터의 `first=28`은 16진 표기).
  최초 배치 실패의 원본 로그는 확보하지 못해 원인을 단정하지 않는다.
- **변경:** 원본 서브모듈은 유지하고 보드 wrapper에서 곱셈 공유, 등록 출력, 마지막 단계 캡처 시점을 수정했다.
  `multiplier_zybo.v`, `adder3_zybo.v`, `clk_div_zybo.v`와 자체 검사 경로.
- **검증:** 캡처 스케줄 모델이 81개 오류를 재현했고 마지막 단계 이후 캡처에서 통과했다.
  multiplier 589,825 비교, RTL·합성 후 기능·배치배선 후 타이밍 시뮬레이션, 보드 VIO를 확인했다.
- **결과:** `done=1 passed=31 errors=0`, 5벡터/160 bin. setup 5.156 ns, hold 0.043 ns,
  DSP 64/80, LUT 7,691/17,600, FF 6,996/35,200.
- **해석:** 이 32-point 전체 병렬 구조의 자원량으로 이후 128-point 반복 구조의 자원량을 판단하지 않는다.
  레이더·PS·UDP 연동을 검증한 실험이 아니다.
- **근거:** [32-point 설명](../src/PL/zybo_fft_test/README.md), [보존 결과](../benchmarks/reports/2026-11-13-fft32/README.md).

## E03 — 128×128 처리 구조 선정

- **질문:** 첫 Range-Doppler 크기를 128×128로 고정하고 Z7-10에서 기능을 확인한다.
- **변경:** 사용자 제공 `fmcw_fft`의 반복 butterfly 구조를 128-point로 조정했다. 코어 하나로
  Range FFT 128회 → PS DDR 열 gather → Doppler FFT 128회를 순차 실행한다.
  E01의 32-point 코어와 출처·구조가 다르다. 최초 전송은 DMA가 아닌 AXI4-Lite다.
- **검증(RTL):** 순차 RTL 16 스트림 벡터와 AXI 272 FFT/34,816 bin이 정수 모델과 일치했다.
  AW/W 순서, 응답 지연, TLAST·리셋·오류 접근을 검사했다.
- **결과:** DSP 4/80. 기능 우선의 자원 절약 구조이며 가속 성능을 뜻하지 않는다.
- **근거:** [출처와 원본 해시](../src/PL/fft128_ps/provenance.json), [기능 실험 설명](../src/PL/fft128_ps/README.md).

## E05 — MMIO 정지: reset IP 극성

- **관찰:** `fpgautil` 다운로드와 `operating`은 성공했으나 첫 ID 읽기가 반환되지 않고 Ctrl+C도 처리되지 않았다.
  수신기에 ID·길이·soft reset 진행 출력을 추가해 정지 위치를 좁혔다.
- **첫 가설(실패):** FCLK 설정과 reset 전달 의존성이 원인이라고 보고 K17 125 MHz → MMCM 20 MHz
  클록과 독립 reset 구성으로 바꿨다. 클록 변경만으로는 정지가 해결되지 않았다.
- **확인된 원인:** 생성된 reset IP가 `C_AUX_RESET_HIGH=0`인데 `aux_reset_in=0`으로 묶여 있었다.
  실제 생성 netlist로 두 AXI reset이 계속 asserted임을 재현했고, 보조 reset 해제 시 ID가 응답했다.
- **수정(V3):** `C_EXT_RESET_HIGH=0/ext_reset_in=1`, `C_AUX_RESET_HIGH=1/aux_reset_in=0`을 명시하고,
  MMCM lock-loss 복구까지 생성 IP로 검사한 뒤 합성하도록 했다.
- **결과:** run `fft128_ps_20261115_203251`, setup 32.177 ns, hold 0.052 ns.
  보드 ID `0x46543128`, 길이 128, `SELFTEST_PASS ... vectors=4 bins=512`.
  firmware SHA256 `e1784f80c8f27225dded47749d0baa98a3d2cc9a108b0f7df2d86afb6239a5db`.
- **교훈:** 다운로드 성공은 사용자 로직의 정상 응답을 보장하지 않는다. IP 기본 극성을 추정하지 않고
  생성 결과와 reset 해제를 확인한다.
- **근거:** [reset 재현·최종 빌드·보드 근거](../benchmarks/reports/2026-11-15-bringup/README.md).

## E06 — RadarSimPy 입력의 전체 보드 처리

- **실행:** 기록된 128×128 입력을 Ubuntu에서 UDP 128패킷으로 전송하고, 보드 native C가
  수신·Q15 변환·PL 두 축 FFT·전치·검증·CSV 저장을 수행했다.
- **결과(보드):** `FRAME_PASS backend=PL_MMIO bit_exact_bins=16384`, 피크 (107,20), drop/duplicate 0.
  입력 IQ 16,384개가 원본과 같았다. NumPy 대비 최대 복소 오차 8.749842 Q15 LSB,
  RMS 1.734691, 상대 L2 1.361%로 검증 기준(최대 12) 이내다.
- **시간:** 단일 실행 82.024044 ms. 전송·FFT·전치와 임시 버퍼 할당이 포함되고,
  UDP·양자화·정답 계산·검증·파일 저장은 제외했다.
- **해석:** 단일 프레임 기능 통과다. 한 번의 시간으로 가속이나 연속 처리량을 주장하지 않는다.
  정확도 원본은 E05 보존 폴더에 있고, 반복 성능 비교는 E08에서 했다.

## E07 — 잘못된 성능 비교 철회

- **문제:** Windows PC NumPy 중앙값 0.257850 ms와 보드 단일 82.024044 ms의 시간비 약 318을 제시했다.
  CPU·환경·측정 범위가 달라 보드 PS-PL 가속비로 쓸 수 없다.
- **조치:** 그 시간비를 **철회**했다. PC NumPy는 정확도 참조로만 남기고, 기존 최적화 C++/FFTW를
  같은 보드 PS 기준선으로 정했다(사용자 지적).
- **이후 규칙:** 같은 입력·정규화·측정 경계를 맞추고, 작업 버퍼를 사전 할당하며, plan 생성과
  워밍업을 제외한다. 이후 보고서는 E08의 같은 보드 값부터 사용한다.

## E08 — 같은 보드 PS 대 순차 PL 기준선

- **변경:** ARM FFTW double을 별도 경로에 빌드하고 보드에서 wisdom을 생성했다. 기존 32×32 타일 전치와
  연속 Doppler FFT를 유지했다. 두 프로그램 모두 CPU0 고정, trial마다 워밍업 10회/측정 100회,
  PS-PL 3쌍으로 각 300회. PL 검증은 매 반복 타이머 밖에서 했다.
- **측정 범위(`fft_pipeline`):** 준비된 입력부터 PS에서 결과를 쓸 수 있을 때까지.
  PS는 복사·두 축 FFT·타일 전치·정규화, PL은 MMIO·두 축 FFT·gather/scatter를 포함한다.
  UDP·파일 I/O·할당·양자화·plan 생성·검증·후처리는 제외한다.

| 지표 | PS double FFTW | 순차 PL 20 MHz |
|---|---:|---:|
| 중앙값 | 5.550039 ms | 81.460246 ms |
| 평균 | 5.542663 ms | 81.525070 ms |
| p05~p95 | 5.489259~5.597602 ms | 81.421093~81.724731 ms |

- **해석:** PL 경로가 PS보다 14.677배 느리다. 이 데이터만으로 PL 연산과 전송·전치를 분리할 수 없다.
  산술 정밀도가 다르고, PS 내부 단계 타이머 비용과 고정 크기·warm-cache 한계가 있다.
- **다음:** DMA나 클록을 바꾸기 전에 기존 사이클 레지스터로 시간 구조를 확인한다(E09).
- **근거:** [300회씩의 CSV·보고서](../benchmarks/reports/2026-11-15-zybo128/README.md).
  기준선 코드와 보고서는 커밋 `14e8ca5`, `aaf3bf6`, `f5c0f18`(재작성 전 `ebcbfd2`, `ab8cd05`, `14e8cb1`)에 있다.

## E09 — 순차 20 MHz 병목 분해

- **가설:** PL 순차 처리와 워드 단위 MMIO가 모두 크다. 기존 0x010 카운터로 PL 내부 구간을 확인할 수 있다.
- **변경:** `mmio.c`에 입력 쓰기·시작/대기·카운터 읽기·출력 읽기 타이머, `native_core.c`에
  gather/scatter 타이머를 추가했다. `native_receiver.c`는 256 FFT의 카운터 합·최솟값·최댓값과
  프레임별 CSV를 저장한다. 클록 인자를 명시하고 별도 프로파일 모드를 쓴다.
- **실행:** `sudo sh /opt/fft128/benchmark/profile_board.sh 20000000`, CPU0, 워밍업 2회/측정 20회.

| 구간 | 20회 평균 | 주의 |
|---|---:|---|
| 입력 쓰기 | 23.429884 ms | idle 확인 + 입력 MMIO |
| 시작·대기 | 39.927098 ms | 아래 PL 내부와 겹침 |
| 출력 읽기 | 18.370430 ms | 결과 MMIO + 작은 계측 bookkeeping |
| gather/scatter | 0.947203 ms | PS 열 접근·결과 배치 |
| 카운터 읽기·기타 잔여 | 1.019642 ms | 콘솔 합계 차이로 역산 |
| 전체 | 83.694257 ms | 계측 실행 평균, 중앙값 83.623717 ms |
| PL 내부 | 39.334400 ms | **시작·대기 안에 포함, 더하지 않음** |

- **결과(보드):** FFT당 min=max=3,073사이클, 16,384 bin 정수 모델 일치, 피크 (107,20).
  39.3344 ms = 3,073 × 256 / 20 MHz이며 내부 입력 적재·출력 저장도 포함한다.
  이후 원본 CSV를 회수해 잔여를 카운터 읽기 0.4310505 ms + 미분류 호스트 0.5885925 ms로 분리했다.
- **해석:** 입력+출력 MMIO 41.800314 ms와 PL 내부 39.3344 ms가 모두 크다. PS 전치 0.947 ms는 작다.
  계측 비용과 횟수가 달라 83.694 ms와 E08의 81.460 ms를 회귀로 비교하지 않는다.
- **주의:** 파일명의 `20180309_150010`은 보드 wall clock이다. 실제 실험일은 2026-11-15이고
  지연은 monotonic clock으로 쟀다.
- **다음:** E10에서 코어 파이프라인과 50 MHz를 적용한다. DMA·PS 전치 최적화는 별도 단계다.
- **근거:** [콘솔·원본 분석](../benchmarks/reports/2026-11-15-serial20-profile/README.md).

## E10 — 파이프라인 코어와 50 MHz

- **문제:** 순차 코어는 butterfly 448개를 각각 6사이클에 처리하고 데이터 이동과 겹치지 않는다.
- **변경:**
  - `butterfly_pipeline.v`: 곱셈 → 합/차 → 정규화를 등록 단계로 분리.
  - `fft128_pipeline.v`: 두 RAM bank를 stage마다 source/destination으로 교대해, 서로 다른 butterfly의
    읽기·연산·쓰기를 겹쳐 매 클록 한 개씩 발행. 코어 복제나 MMIO-연산 겹치기는 아니다.
  - `fft128_axi.v`의 `PIPELINED=0` 기본값은 기존 경로. `build_fast.tcl`이 pipeline/50 MHz를 선택하고
    reset V3를 유지한다. `build.tcl`은 생성 클록 주기와 routed setup/hold를 검사해 실패 시 중단한다.
- **혼동 변수:** 파이프라인과 클록(AXI 포함 20→50 MHz)을 함께 바꿨다. 결과는 결합 효과다.
- **검증 경과:**
  1. **RTL:** 두 경로 각각 272 FFT/34,816 bin, backpressure/TLAST, AXI 지연, 계산 중 abort 후 재실행.
     순차 3,073 / 파이프라인 861사이클 확인. C·참조 테스트 12개, 프로파일 분석 테스트 4개 통과.
  2. **구현:** run `fft128_ps_pipeline_20261115_224343`. setup WNS 9.807 ns, hold WHS 0.034 ns, 위반 0.
     DSP 4/80, LUT 1,364/17,600, FF 1,048/35,200, BRAM tile 2.5/60.
     raw BIN SHA256 `c0f3a5614eb3ec3b86d3775d51b3ae0b854fdeb23a592f29e35e9cc6c520c27c`.
     보드에서 배치 파일 해시를 다시 받지는 않았다.
  3. **보드 자체 검사(콘솔):** ID `0x46543128`, 길이 128, `SELFTEST_PASS backend=PL_MMIO vectors=4 bins=512`.
  4. **보드 프로파일(콘솔·원본):** CPU0, 워밍업 2/측정 20. `FRAME_PASS`, 피크 (107,20), FFT당 861사이클.
  5. **비계측 비교(원본):** PS/PL 3쌍, 각 워밍업 10/측정 100.

| 구성 | 보드 전체 시간 | PL 내부 구간 |
|---|---|---|
| serial / 20 MHz | E08·E09에서 측정 | 39.3344 ms (E09 보드) |
| pipeline / 20 MHz | 미측정 | **환산** 861×256/20 MHz = 11.0208 ms |
| serial / 50 MHz | 미측정 | **환산** 3,073×256/50 MHz = 15.73376 ms |
| pipeline / 50 MHz | 비계측 중앙값 25.2591725 ms, 프로파일 평균 27.327809 ms | 4.408320 ms (보드 861 cycles) |

- **프로파일 결과(20회 평균):** 입력 쓰기 11.526609, 시작·대기 5.054848, 출력 읽기 8.850965,
  gather/scatter 0.946476 ms. 전체 평균 27.327809 / 중앙값 27.329907 / 최소 27.291030 / 최대 27.403428 ms.
  카운터 읽기 0.3580974 ms, 미분류 호스트 0.5908137 ms.
- **비계측 결과(각 300회):** 중앙값 PS 5.557368 / PL 25.2591725 ms, 평균 5.547364537 / 25.261326367 ms.
  p05~p95 PL 25.2371262~25.2841369, PS 5.4931185~5.6052552 ms.
  trial별 PL 평균 25.260099 / 25.260553 / 25.263327 ms, 중앙값 25.256604 / 25.259575 / 25.260438 ms.
  표본 수가 같아 trial 평균의 평균은 약 25.261326 ms이며 E08 PL 평균 81.525070 ms보다 약 3.227배 짧다.
- **정확도:** 입력 해시가 기존과 같고, 새 PL 출력이 순차 PL 출력과 비트 단위로 같다.
  NumPy 대비 PL 최대 8.749842 LSB, RMS 1.734691, 상대 L2 1.361021%; PS 최대 1.833e-12.
- **해석:**
  - PL은 순차 기준 81.460246 ms보다 3.224977배 빨라졌지만 PS보다 4.545168배 느리다.
  - 계측 실행 기준 전체 83.694257 → 27.327809 ms(약 3.063배), PL 내부 39.3344 → 4.40832 ms(약 8.923배).
  - 입력+출력 MMIO는 41.800314 → 20.377574 ms로 줄었지만 이제 전체의 약 74.6%다.
  - 파이프라인과 클록 각각의 독립 효과는 분리하지 않았다(위 표의 미측정 두 구성).
- **다음:** 지배적인 MMIO 전송을 DMA로 바꾸기 전에 PS 목표선을 먼저 정한다(PS01 → E11a).
- **근거:** [RTL·소스 스냅샷](../benchmarks/reports/2026-11-15-pipeline-rtl/README.md),
  [구현 보고서](../benchmarks/reports/2026-11-15-pipeline50-build/README.md),
  [보드 자체 검사](../benchmarks/reports/2026-11-15-pipeline50-build/board_selftest.json),
  [프로파일](../benchmarks/reports/2026-11-15-pipeline50-profile/README.md),
  [비계측 비교](../benchmarks/reports/2026-11-15-pipeline50-benchmark/README.md),
  [빌드·실행 절차](fft128_optimization.md). 원본 전체는 `build/fft128_board_benchmark/`에 있다.
  소스는 기준 커밋 이후의 작업 트리 변경이었으므로 당시 파일 SHA256을 스냅샷으로 보존했다.
  보드 파일명 `profile_20180309_152650.profile.csv`의 시각은 보드 시계이며 실제 기록일과 다르다.

## PS01 — PS 정밀도·NEON 기준선

- **질문:** 하드웨어를 더 바꾸기 전에 float·NEON PS가 얼마나 빠른지 재서 PL의 목표선을 정한다.
  사전 가설 2~3 ms는 미검증 예시였다(아래 결과로 대체).
- **변경:**
  - `udp_radar_receiver.cpp`: compile-time Real로 float64/float32 선택. 작업 버퍼·창/전치·정규화가
    선택한 정밀도를 쓰고, Q15 스케일 산정은 double로 유지. 32×32 전치·contiguous Doppler·단일 스레드·CPU0 유지.
  - `build_fftw_arm.sh`: 기존 double 경로 유지, single scalar / single NEON 추가. float 두 변형은
    compiler 자동 벡터화를 끄고 FFTW의 명시적 NEON codelet 여부만 다르다. 변형마다 라이브러리·실행 파일·wisdom 분리.
- **측정 계약:** [PS01 절차](../benchmarks/ps_precision/README.md). 워밍업 10회, 100회 × 3 trial, 순서 회전.
  주 비교는 `fft_pipeline`. 검증 위치가 캐시에 미치는 영향을 맞추려고 double도 다시 쟀다.
- **정확도 기준:** PC에서 만든 NumPy 기준과 매 반복 16,384 bin 비교. 최대 복소 오차/상대 L2 허용값은
  double 1e-7/1e-12, float 0.01/1e-5(정규화된 Q15 LSB). 실패·NEON plan 미선택·artifact 불일치 시 중단.
- **검증 경과:**
  1. **PC:** oracle이 기존 보드 double 출력과 일치. 분석기·C++ 검증기 테스트 7개 통과.
     Windows harness에서 FFTW 3.3.5 DLL로 실제 수신기 코드 검증: 최대 오차 double 1.874971e-12 /
     float 0.000426809 LSB, 상대 L2 2.943384e-16 / 1.083102e-7. ARM·NEON·PC 시간은 이 단계 범위 밖.
  2. **보드(콘솔):** preflight 3개, 회전 trial 3개, `PS_PRECISION_COMPLETE`. 각 300회 정확도 PASS.
     콘솔 최대 복소 오차 double 1.83315e-12 / scalar 0.000470413 / NEON 0.000426809 LSB.
     콘솔의 FFT 두 축만 평균: double 3.361187757 / scalar 2.721217800 / NEON 1.998061230 ms
     (FFT만의 NEON 개선은 double 대비 약 1.682배, scalar 대비 약 1.362배).
  3. **원본 회수 후 독립 검증:** 16개 artifact 해시·source identity 대조, 출력 CSV 9개 NumPy 비교,
     CPU0·정규화·scale·회전 순서·wisdom 확인. NEON은 preflight와 모든 trial 두 축에 실제 NEON codelet이 있고 scalar에는 없다.

| 변형 (각 300회) | 중앙값 | 평균 | p05~p95 | 최대 복소 오차 (LSB) | 상대 L2 |
|---|---:|---:|---:|---:|---:|
| double | 5.502540 ms | 5.498577 ms | 5.442966~5.566529 | 1.833145e-12 | 2.907011e-16 |
| float scalar | 4.341573 ms | 4.350084 ms | 4.293004~4.409682 | 0.000470412707 | 1.1532413e-7 |
| float + NEON | 3.615852 ms | 3.622898 ms | 3.563816~3.691539 | 0.000426808672 | 1.0831023e-7 |

- **시간 분해(NEON 평균):** FFT 두 축 1.998061 + 입력 복사 0.339761 + 전치 0.705625 + 정규화 0.547702 +
  타이머 bookkeeping 약 0.031748 = 3.622898 ms. float 정규화가 double(0.288676 ms)보다 길지만 원인은 분리하지 않았다.
- **해석:**
  - NEON은 새 double 대비 중앙값 1.521782배, scalar 대비 1.200705배 빠르다.
  - FFT만의 1.998 ms를 PS 전체 시간으로 쓰지 않는다. 사전 가설 2~3 ms에는 이르지 못했다.
  - E10 PL 내부 4.408320 ms만으로도 NEON 전체보다 0.792468 ms 길다. DMA만으로는 PS를 이길 수 없고,
    이후 연산 또는 겹치기 개선이 필요하다.
  - double→float에는 정밀도·버퍼 폭·자동 벡터화 정책 차이가 함께 들어 있다. FPGA 변경은 없다.
- **근거:** [준비 단계](../benchmarks/reports/2026-11-15-ps01-preparation/README.md),
  [완료 보고서](../benchmarks/reports/2026-11-15-ps01-board/README.md). 원본은 `build/fft128_ps_precision/results_ps01/`.

## E11a — FFT당 Simple DMA

- **질문:** E10 프로파일의 샘플 MMIO(20.377574 ms, 약 75%)를 DMA로 바꾸면 FFT당 DMA 고정 비용은 얼마이고
  병목은 어디로 옮겨 가는가. DMA만으로 PS를 이긴다고 가정하지 않는다.
- **고정:** 단일 `fft128_pipeline`과 butterfly/RAM/주소/ROM, Q15 산술·포화·정규화, 50 MHz,
  출력 2클록/sample, FFT당 순차 처리, PS cached gather/scatter. 코어 파일 SHA를 E10 소스와 대조했다.
- **변경:**
  - `fft128_dma_ctrl.v`, `build_dma.tcl`: Simple AXI DMA(MM2S/S2MM)를 HP0 64-bit에, 32-bit AXIS를 FFT에 연결.
    SG/DRE off, burst 16, length width 17. 제어 MMIO는 유지하고 payload 창은 제거.
  - 주소: FFT `0x43c60000`/ID `0x46544480`, DMA `0x40400000`, IRQ F2P[6:7]/SPI35:36 (기존 BSP와 겹치지 않게).
  - `src/PS/fft128/dma/fft128_dma.c`: DMAengine 채널과 coherent 512 B TX/RX bounce buffer 소유.
    ioctl 1회 = FFT 1개, 프레임당 256회, 양방향 총 256 KiB. 포인터 없는 고정 폭 ABI, 단일 소유권,
    완료·개수·오류 검사, 중단 시 동기 종료. 기존 MMIO 경로·펌웨어는 보존.
  - PL `cycles`를 DMA 정지를 포함한 active 구간으로 정의하고 input/output stall 카운터를 추가.
- **측정 범위:** 준비된 Q15 입력부터 CPU에서 두 축 결과를 쓸 수 있을 때까지. 복사·ioctl·DMA·FFT·PS 전치 포함,
  할당·UDP/파일·양자화·검증 제외. 별도 계측은 host copy/ioctl/전치와 kernel copy/submit/wait/check를 기록한다.
- **검증 경과:**
  1. **RTL:** `verify_dma.py` 272벡터/34,816 bin 일치, 입력 공백·출력 backpressure, 잘못된 TLAST/TKEEP,
     부분 입력·계산 중 abort 후 복구, AW/W 순서·응답 지연 통과. active − stream stall = 861 cycles/FFT. 기존 회귀 통과.
  2. **PC 소프트웨어:** native 회귀 9개 + CLI/DT 충돌·계측 분석 검사 11개 통과. Ubuntu ARM 정적 수신기 빌드,
     `dtc`/`fdtoverlay` 적용 통과.
  3. **커널 조회(보드):** DMAengine/Xilinx DMA/CMA, 모듈·심볼 CRC, OF configfs overlay 활성. CMA 총 16 MiB,
     조회 시 free 16,096 KiB. 일치하는 커널 빌드 산출물이 없어 BSP 지정 Digilent 5.15.19 소스와 기록 설정으로
     후보 빌드 트리를 만들었다(원래 커널 소스의 정확한 provenance는 미확인). 이 커널은 설치하지 않았고,
     보드에서 DT 없이 모듈 로드/언로드와 실제 CRC 수락을 확인했다.
  4. **구현:** run `fft128_dma_e11a_20261116_005936`. 생성 reset IP 검사 PASS. 50 MHz WNS 10.607 ns / WHS 0.021 ns,
     위반·미제약 내부 endpoint 0. LUT 3,210/17,600, FF 3,987/35,200, BRAM tile 5/60, DSP 4/80.
     BD의 HP0/DDR·AXIS·주소·IRQ·DMA 설정과 PL/host/module 소스 SHA를 대조했다.
  5. **보드 1차 적용 (실패):** manifest 20개 OK, HP0 64-bit, BIN 로드(51 ms)는 됐지만 overlay/module 뒤
     DMA client가 bind하지 않아 자체 검사 전에 중단했다. `fft128-e11a-bus`, `fft128-e11a-clock`만 있고
     DMA/FFT platform device가 없었다. 현재 커널의 동적 OF 알림은 부모가 OF_POPULATED_BUS인 장치만
     생성하는데, 새 simple-bus 아래 자식은 생성되지 않는 구조였다.
  6. **수정 (overlay v2):** 기존 `/amba_pl` 아래에 DMA/FFT를 직접 추가. 클록·주소·IRQ·DMA 파라미터·
     firmware·모듈은 그대로. PC 검사 12개 통과, raw BIN이 최초 bundle과 같아야 배치하도록 했다.
  7. **보드 2차 적용(콘솔):** artifact 21개 OK, AXI DMA·FFT client probe, `DMA_CLIENT_PASS`,
     `PL_DMA` 4벡터/512 bin `SELFTEST_PASS`. v2 DT 외 파일은 최초 bundle과 byte 단위로 같다. FPGA 로드 49 ms는 FFT 시간이 아니다.
  8. **프레임 프로파일(콘솔·원본):** `profile_e11a_01`, CPU0, 워밍업 2/측정 20. 16,384 bin 정수 검증, 피크 (107,20).
     콘솔 보고 평균 18.136317 ms, kernel 복사 합 1.004211 ms.
  9. **비계측 비교(원본):** CPU0, 워밍업 10/100회 × 3 회전 trial. 원시 CSV·로그·artifact·입력 신원 확인.

| 경로 (각 300회) | 중앙값 | 평균 |
|---|---:|---:|
| PS double | 5.748489 ms | 5.737376 ms |
| PS float + NEON | 3.715234 ms | 3.726932 ms |
| PL DMA / 50 MHz | 15.411639 ms | 15.415091 ms |

- **정확도:** 매 반복 보드 정수 검증 PASS. 마지막 출력 3개와 profile 출력이 독립 Python Q15 모델과 전부 일치.
  PL NumPy 최대 8.749842363 LSB, 상대 L2 1.361%. IRQ 두 개가 CPU0에서 각 84,480회 증가(330프레임 × 256).
- **프로파일(20회 평균):** 전체 18.136318 ms(중앙값 18.129750, 최소 18.071028, 최대 18.224922).

| 호스트 구간 (겹치지 않음) | 평균 | ioctl 내부 (겹침, 다시 더하지 않음) | 평균 |
|---|---:|---|---:|
| 입력 사용자 복사 | 0.529984 ms | kernel copy-in | 0.283016 ms |
| ioctl 전체 | 15.199543 ms | submit/start | 2.939423 ms |
| 출력 사용자 복사 | 0.722795 ms | wait | 9.406124 ms |
| gather/scatter | 1.002013 ms | check | 0.654666 ms |
| 잔여 | 0.681984 ms | kernel copy-out | 0.721195 ms |
| | | ioctl 잔여 | 1.195118 ms |

  PL active 4.482577 ms = nonstall 4.408320 ms(861 cycles × 256) + stream stall 0.074257 ms. output stall 0.
- **해석:**
  - 과거 E10 MMIO 25.259173 ms 대비 약 1.639배 빨라졌다(지연 39.0% 감소, 과거 실행과의 비교).
  - 같은 회차 NEON보다 약 4.15배 느리다. PS01의 과거 NEON 대신 같은 회차 값을 분모로 썼다.
  - ioctl 59.37 us/FFT와 PL active 17.51 us/FFT의 차이 약 41.86 us는 계측 실행의 **비코어 잔여 벽시계 시간**이다.
    wait와 PL active가 겹치므로 wait − active를 IRQ·깨우기 비용으로 확정하지 않는다.
  - 계측 실행의 복사 합 2.256989 ms는 전체의 약 12.4%다. 이를 비계측 15.411639 ms에 그대로 대입하지 않는다.
- **다음 (E11b 준비 시 갱신한 가설, 측정 아님):** nonstall 4.408320 + stall 0.074257 + 복사 2.256989 +
  전치 1.002013 = 7.741579 ms에 축당 제출 비용이 더해진다고 보고, 초기 가설 5.5~6 ms를 **약 8 ms** 작업 가설로 바꿨다.
  E11b에서는 coherent/cached 정책을 고정하고 TLAST를 축 경계로 변환한다. ioctl만 묶고 내부 DMA/IRQ 횟수를
  그대로 두는 구현과 구분한다.
- **근거:** [준비 보고서](../benchmarks/reports/2026-11-16-e11a-preparation/README.md),
  [구현 보고서](../benchmarks/reports/2026-11-16-e11a-build/README.md),
  [v2 보드 콘솔](../benchmarks/reports/2026-11-16-e11a-build/dt_v2_selftest_console.log),
  [최초 프레임 콘솔](../benchmarks/reports/2026-11-16-e11a-build/first_frame_profile_console.log),
  [완료 보고서](../benchmarks/reports/2026-11-16-e11a-board/README.md),
  [검증 상태 기록](../benchmarks/reports/2026-11-16-e11a-board/board_verification.json)
  (빌드 원본의 `board_verified=false`는 유지하고, 검증한 artifact 해시별 완료 상태를 따로 적었다).

## E11b — 축당 128 FFT 묶음 제출

- **질문:** E11a의 프레임당 256 ioctl / 512 DMA 채널 제출을 축당 하나로 줄이면 고정 비용이 얼마나 줄어드는가.
  작업 가설은 약 8 ms(측정 아님).
- **고정:** 단일 `fft128_pipeline` / 50 MHz / Q15 / 출력 2클록/sample, cached PS 전치, 사용자·커널·coherent 복사 단계.
  전송/연산 겹치기, 새 버퍼 정책, PS02는 섞지 않는다.
- **변경:** 별도 `fft128_dma_batch_ctrl`·빌드, DMA batch ABI2·드라이버·수신기·배치 경로.
  프레임당 2 ioctl / 4 DMA 채널 제출 / FFT 256회, 축당 방향별 64 KiB.
  외부 TLAST는 축 마지막에만 내보내고 내부 FFT별 경계는 어댑터가 생성한다.
- **검증 경과:**
  1. **RTL:** `verify_dma_batch.py` PASS. 272 독립 벡터, 1/2/128 FFT 패킷, backpressure·입력 공백·
     오류 TLAST/TKEEP·abort/recovery, E11a 회귀. active − stream stall = 861 × 128 cycles/axis, 전송/연산 비겹침 확인.
  2. **구현:** run `fft128_dma_e11b_20261119_232506`. 생성 reset IP/AXI ID·ABI·batch 검사, bitstream/XSA,
     ARM 정적 수신기·ABI 검사기·모듈 빌드 PASS. 50 MHz WNS 10.618 ns / WHS 0.016 ns, 위반·미제약 내부 endpoint 0.
     LUT 3,243 / FF 4,017 / BRAM tile 5 / DSP 4. BD의 HP0/AXIS/주소/IRQ/길이 폭과 소스 SHA, ARM manifest 대조.
  3. **보드 자체 검사(콘솔):** HP0 read/write `0x00000000/0x00000F00`, BIN 로드, AXI DMA probe, client bind, 모듈 로드.
     1 FFT/512 B와 두 차례 128 FFT/65,536 B 패킷 모두 완료 개수·정수 모델 PASS. 독점 소유, 잘못된
     ABI/timeout/flags/count 거부, 4벡터/512 bin 자체 검사 PASS, `DMA_E11B_SELFTEST_READY`.
     bundle 20개 artifact 해시 확인. FPGA 로드 63 ms는 FFT 시간이 아니다.
  4. **비계측 비교·프로파일(원본):** Ubuntu 수집 폴더를 복사해 독립 재계산.

| 경로 (각 300회) | 중앙값 | 평균 | p05~p95 |
|---|---:|---:|---:|
| PS double | 5.717376 ms | 5.710036 ms | 5.649892~5.767121 |
| PS float + NEON | 3.558177 ms | 3.575637 ms | 3.539030~3.634776 |
| PL E11b DMA / 50 MHz | 6.433026 ms | 6.432092 ms | 6.396787~6.474537 (최대 6.505416) |

- **정확도:** 모든 반복 보드 정수 검증 PASS. 마지막 출력 3개와 profile 출력이 독립 Python 정수 모델과 일치.
  NumPy 상대 L2 1.361020928%, 피크 (107,20). artifact·소스·입력·NEON plan 확인.
  계측 trial 혼입과 1 LSB 변조 출력 거부 검사도 통과했다.
- **IRQ:** DMA 완료 IRQ 두 개(GIC 67/68)가 CPU0에서 각 660회 증가(330프레임 × 2축), CPU1 증가 0.
- **프로파일(20회 평균):** 전체 6.473645 ms(중앙값 6.464940).

| 호스트 구간 (겹치지 않음) | 평균 | ioctl 내부 (겹침, 다시 더하지 않음) | 평균 |
|---|---:|---|---:|
| 입력 사용자 복사 | 0.260192 ms | kernel copy-in | 0.198589 ms |
| ioctl 전체 | 5.360488 ms | submit/start | 0.035202 ms |
| 출력 사용자 복사 | 0.173017 ms | wait | 4.461962 ms |
| gather/scatter | 0.670374 ms | check | 0.010188 ms |
| 잔여 | 0.009573 ms | kernel copy-out | 0.631210 ms |
| | | ioctl 잔여 | 0.023337 ms |

  PL active 4.408947 ms(68.1%) = nonstall 4.408320 + 입력 stream stall 0.000627 ms, 출력 stall 0.
  사용자+커널 복사 합 1.263008 ms.
- **해석:**
  - E11a 15.411639 ms 대비 2.395706배 빨라졌다(지연 58.258651% 감소, 과거 실행과의 비교).
  - 같은 회차 NEON보다 1.807956배, double보다 1.125171배 느리다.
  - submit/start가 2.939423 → 0.035202 ms로 줄고 wait가 PL active와 거의 같아졌다. 요청·완료 고정 비용이 크게 줄고
    코어 LOAD/CALC/OUTPUT 구간이 가장 큰 비용이 됐다.
  - 묶음 크기가 메모리 접근 간격도 바꾸어 복사(2.256989 → 1.263008 ms)·전치(1.002013 → 0.670374 ms)도 달라졌다.
    전체 개선을 ioctl 횟수 감소만의 효과로 단정하지 않는다. 전송 크기 스윕은 하지 않았다.
  - 약 8 ms 작업 가설보다 짧았다. 가설은 그대로 남기고 차이를 기록한다.
  - 12.8 ms보다 짧지만 오프라인 지연일 뿐이다. 연속 UDP·최악 지연·실시간 보장은 검증하지 않았다.
- **다음:** E13(연산 구조 확대)을 주 가속 후보로 둔다. E11c(출력 개선, 무정지 상한 약 0.65 ms)는 독립 검증한다.
  E12는 코어 내부 LOAD/OUTPUT을 숨길 여지가 있어, 외부 stream stall이 작다는 이유만으로 배제하지 않는다.
  복사 1.263 ms와 전치 0.670 ms가 남아 코어 수만큼 전체가 빨라지지는 않는다. 새 단계는 아직 실행하지 않았다.
- **근거:** [준비·검증 기록](../benchmarks/reports/2026-11-19-e11b-preparation/README.md),
  [빌드·보드 자체 검사](../benchmarks/reports/2026-11-19-e11b-build/README.md),
  [보드 콘솔](../benchmarks/reports/2026-11-19-e11b-build/board_selftest.json),
  [완료 보고서](../benchmarks/reports/2026-11-19-e11b-board/README.md).
  측정 bundle의 `board_verified:false`는 유지하고 검증된 해시별 상태는 `board_verification.json`에 적었다.

---

## E13-2core — 2코어 병렬 실행

- **날짜·선행:** 2026-11-20, E11b.
- **질문:** PL active가 계측 전체의 약 68%인 상황에서 코어 복제가 얼마나 줄여 주는가.
- **가설:** 내부 전체가 이상적으로 반감되면 2.204160 ms지만, 공유 직렬 입출력 때문에 달성하기 어렵다.
  구현 전 pair 스케줄 모델은 두 축 2.856960 ms를 예상했다. 둘 다 보드 전체 지연 예측은 아니다.
- **변경:** 기존 `fft128_pipeline` 2개, pair barrier, ABI3. 입력을 두 코어에 분배하고 두 결과를 배출한 뒤 다음 pair를 시작한다.
  공유 DMA·50 MHz·Q15·2 clocks/sample 출력·coherent 복사·PS 전치를 유지한다. 다음 pair prefetch나 외부 FIFO는 넣지 않았다.
  PL `build_dma_parallel.tcl`·`fft128_dma_parallel_ctrl.v`, PS `dma_parallel/`, 공통 native 수신기와 분석기를 추가했다.
- **검증 경과:** RTL 272벡터/34,816 bin, ARM 수신기·모듈, Vivado 구현·reset·타이밍, 보드 packet/self-test를 통과했다.
  전체 프레임·별도 20회 profile·각 300회 paired 원본 75파일을 회수하고 정확도·source/artifact SHA·IRQ를 독립 검증했다.
  `python src/PL/fft128_ps/verify_dma_parallel.py`, 보드·수집 명령은 [실행 절차](../src/PS/fft128/dma_parallel/README.md).
- **결과:** 중앙값 PS double 5.767263 / NEON 3.646212 / PL 4.920621 ms. 계측 평균 전체 4.974313 / PL active 2.857541 ms.
  각 저장 출력 16,384 bin이 정수 모델과 완전 일치하고 DMA IRQ는 각각 660회다. 실제 동시 CALC 하한은 44,544 cycles/frame이다.
  routed DSP 8 / BRAM 7, 50 MHz setup·hold PASS.
- **해석:** 과거 E11b 대비 전체 지연 23.51% 감소. 이번 double보다 1.172배 빠르지만 NEON보다 1.350배 느리다.
  내부가 이상적으로 반감되지는 않았고 구현 전 공유 I/O 스케줄 모델과 일치했다. 서로 다른 회차의 전체 차이를 순수 코어 복제 효과로 확정하지 않는다.
- **다음:** 4코어에서 공유 I/O와 group barrier의 영향을 비교한다. 이후 완료 결과는 E13-4core에 기록했다.
- **근거:** [준비·RTL·소스](../benchmarks/reports/2026-11-20-e13-2core-preparation/README.md),
  [실제 빌드·보드 콘솔](../benchmarks/reports/2026-11-20-e13-2core-build/README.md),
  [원본 검증·분포·시간 분해](../benchmarks/reports/2026-11-20-e13-2core-board/README.md).

---

## E13-4core — 4코어 확장

- **날짜·선행:** 2026-11-20, E13-2core.
- **질문:** 기존 코어 수를 2→4개로 늘리면 내부·전체 지연이 얼마나 줄어드는가.
- **가설·변경:** 코어 4개, group barrier, ABI4로 확장했다. 한 그룹은 128샘플 FFT 4개이며 한 축에 32그룹이다.
  계산은 겹치지만 입력·출력은 공유 경로에서 순서대로 처리한다. 다음 그룹은 네 결과 배출 후 시작한다.
  무정지 스케줄 모델은 두 축 2.081280 ms다. 기존 산술·클록·출력 cadence·DMA·복사·전치는 유지한다.
  PL `build_dma_quad.tcl`·`fft128_dma_quad_ctrl.v`, PS `dma_quad/`, native 수신기·분석기를 확장했다.
- **검증 경과:** RTL 272벡터, host 21개, ARM/Vivado, 보드 자체 검사·전체 프레임·별도 20회 profile·각 300회 paired를 통과했다.
  75파일의 원본·정수 정확도·입력/소스/artifact·IRQ를 독립 검증했다. 계측 trial 혼입·1 LSB 출력 변조도 거부했다.
  `python src/PL/fft128_ps/verify_dma_quad.py`, [보드·회수 절차](../src/PS/fft128/dma_quad/README.md).
- **결과:** 중앙값 double 5.767911 / NEON 3.649998 / PL 4.186353 ms. 계측 평균 전체 4.222976 / PL active 2.081883 ms.
  실제 4코어 동시 CALC 하한 5,888 cycles/frame, 저장 출력 정수 모델 완전 일치, IRQ 각각 660회다.
  routed DSP 16 / BRAM 11, 50 MHz setup·hold PASS.
- **해석:** 과거 2코어 대비 전체 14.92%, PL active 27.14% 감소다. 공유 직렬 입출력·group barrier와 비PL 비용 때문에 코어 수에 비례하지 않는다.
  코어를 직렬로 계산한 결과가 아니다. 이번 double보다 1.378배 빠르고 NEON보다 1.147배 느리다.
  trial 2의 지연 증가·다른 부팅은 보존하고 원인을 단정하지 않는다. 겹치는 카운터를 합산하거나 모두 순수 연산 시간으로 쓰지 않는다.
- **다음:** 코어별 FIFO·독립 스케줄로 그룹 장벽을 없애는 E12를 진행한다. 당시 미실행이었던 결과는 다음 항목에 기록했다.
- **근거:** [준비·RTL](../benchmarks/reports/2026-11-20-e13-4core-preparation/README.md),
  [구현·보드 콘솔](../benchmarks/reports/2026-11-20-e13-4core-build/README.md),
  [원본·시간 분해·해석](../benchmarks/reports/2026-11-20-e13-4core-board/README.md).

---

## E12-4core — 입출력·계산 겹치기

- **날짜·선행:** 2026-11-20, E13-4core.
- **질문:** 네 코어가 계산 중이어도 남는 공유 I/O·group barrier 비용을 숨길 수 있는가.
- **가설·변경:** 각 기존 코어 앞뒤에 동기 RAM FIFO(256 words + 등록 출력 1 word)를 두고 독립적으로 시작한다.
  다음 벡터 입력·현재 CALC·이전 결과 출력을 겹치며 group barrier를 제거한다. 단일 DMA와 공유 32-bit 외부 스트림은 유지한다.
  4개 결과를 외부로 동시에 4샘플/clock 보내는 구조는 아니다. Q15·50 MHz·기존 산술·2 clocks/sample 코어 출력·복사·PS 전치를 유지한다.
  `fft128_buffered_lane.v`·`fft128_stream_fifo.v`·`fft128_dma_overlap_ctrl.v`·`build_dma_overlap.tcl`, PS `dma_overlap/`, ABI5를 추가했다.
- **검증 경과:** RTL·host 28개·ARM/Vivado·보드 packet/self-test·전체 프레임·별도 20회 profile·각 300회 paired를 통과했다.
  `python src/PL/fft128_ps/verify_dma_overlap.py`, [실행·수집 절차](../src/PS/fft128/dma_overlap/README.md).
  원본 75파일의 SHA·정수 정확도·IRQ·bundle 신원을 독립 검증했다. 이전 분석기의 알려진 설명 문자열 차이는 원본을 고치지 않고 기록했다.
- **결과:** 중앙값 double 5.711883 / NEON 3.488904 / PL 3.129210 ms. 계측 평균 전체 3.200291 / active 1.124590 ms.
  복사 1.263426 / PS 전치 0.674777 ms가 남는다. 실제 입력·CALC·출력 동시 수행 하한 22,516 cycles/frame이다.
  정수 모델 완전 일치, IRQ 각각 660회, DSP 16 / BRAM 15, 50 MHz setup·hold PASS.
- **해석:** 과거 E13-4core 대비 전체 25.25% 감소, 이번 NEON 대비 10.31% 감소다. 이 고정 프레임의 오프라인 경로에서 NEON보다 빨라졌다.
  외부 output stall 0은 내부 직렬 I/O 비용이 없다는 뜻이 아니다. 다른 부팅의 PS 기준도 달라 전체 차이를 모두 스케줄 효과로 단정하지 않는다.
  work-window의 초기 출력 RAM 읽기를 제외한 보수적 실제 CALC 하한을 사용하며 겹치는 카운터는 더하지 않는다.
- **다음:** 코어당 버터플라이 확대와 스트리밍을 별도 실험으로 비교한다. 독립 E11c·E11d·PL 전치는 포함하지 않았다.
- **근거:** [준비·RTL](../benchmarks/reports/2026-11-20-e12-4core-preparation/README.md),
  [구현·콘솔](../benchmarks/reports/2026-11-20-e12-4core-build/README.md),
  [원본·정확도·분해](../benchmarks/reports/2026-11-20-e12-4core-board/README.md).

---

## E13-bf2 — 버터플라이 확대

- **날짜·선행:** 준비 2026-11-20, 보드 검증 2026-11-21, E12-4core.
- **질문·가설:** 코어당 버터플라이를 1→2개로 늘리면 stage당 발행이 64→32 pair가 되고 CALC가 476→252 cycles/FFT로 줄어드는가.
- **변경:** 4코어 × 2버터플라이, even/odd true-dual-port RAM bank·twiddle ROM 2개, ABI6.
  E12 FIFO·독립 스케줄·50 MHz·Q15 반올림/포화/단계별 1/2 스케일·출력 cadence·DMA·복사·PS 전치를 유지한다.
  `fft128_bf2.v`·`fft128_buffered_bf2_lane.v`·`fft128_dma_bf2_ctrl.v`·`build_dma_bf2.tcl`, PS `dma_bf2/`를 추가했다.
- **검증 경과:** RTL 272벡터·host 35개·ARM/Vivado·보드 packet/self-test·전체 frame·20회 profile·각 300회 paired PASS.
  `python src/PL/fft128_ps/verify_dma_bf2.py`, [보드·회수 명령](../src/PS/fft128/dma_bf2/README.md).
  75파일의 입력·정수 정확도·source/artifact·IRQ를 독립 검증했다. 계측 trial·1 LSB 변조·dual-retire 1회 누락을 거부했다.
- **결과:** 중앙값 double 5.708112 / NEON 3.520371 / PL 2.841720 ms. CALC 252 cycles/FFT로 가설과 일치했다.
  계측 전체 평균 2.885369 / active 0.837903 / 복사 1.247281 / 전치 0.671572 ms.
  모든 20행에서 dual issue/retire 각각 57,344 pair/frame, CALC lane 합 64,512 cycles다. 정수 모델 완전 일치·IRQ 각각 660회.
  DSP 32 / BRAM 23, 50 MHz WNS 5.405 ns / WHS 0.028 ns PASS.
- **해석:** 과거 E12보다 전체 9.19%·active 25.49% 감소, 이번 NEON보다 전체 19.28% 짧다.
  CALC가 빨라져 네 코어의 CALC가 모두 겹치지 않는 all-work=0은 예상 결과다. 코어별 두 연산기는 직접 issue/retire로 검증했다.
  복사·전치가 남고 다른 부팅 세션이므로 전체 개선을 버터플라이 하나의 인과 효과로 확정하지 않는다.
- **다음:** 요청한 전용 단계 스트리밍을 별도 구성·측정한다.
- **근거:** [준비·정수 RTL](../benchmarks/reports/2026-11-20-e13-bf2-preparation/README.md),
  [구현·콘솔](../benchmarks/reports/2026-11-21-e13-bf2-build/README.md),
  [원본·분포·분해](../benchmarks/reports/2026-11-21-e13-bf2-board/README.md).

---

## E13-stream — 프레임 스트리밍

- **날짜·선행:** 2026-11-21, E13-bf2.
- **질문·가설:** 7개 FFT 단계를 전용 연산기로 펼쳐 서로 다른 chirp를 겹치면 정상상태에서 128 clocks/FFT를 달성하는가.
- **변경:** 반복형 4코어/총 8버터플라이를 전용 DIT 7단계/총 7버터플라이의 단일 파이프라인으로 교체했다.
  단계마다 입력 2개·출력 2개의 128-word frame slot을 사용한다. 완성 블록을 넘기는 프레임 파이프라인이며 sample-delay SDF는 아니다.
  코어 배치·버퍼·내부 출력 cadence도 바뀌는 구조 비교다. 기존 butterfly/Q15/twiddle·50 MHz·단일 DMA/HP0/AXIS32·복사·PS 전치는 고정했다.
  `fft128_stream_stage.v`·`fft128_streaming.v`·`fft128_dma_stream_ctrl.v`·`build_dma_stream.tcl`, PS `dma_stream/`, ABI7을 추가했다.
- **실패·수정:** 초기 malformed TLAST 테스트는 정수 결과가 맞아도 in-flight가 1 남아 empty 검사에 실패했다.
  TLAST가 아니라 128번째 샘플 handshake에서 벡터 수를 올리도록 수정했다. 테스트벤치의 동시 AXI writer 두 개가 같은 신호를 구동한 실패는
  단일 writer로 고쳤으며 독립 AW/W 지연 검사는 유지했다. 원래 실패 로그와 경과는 준비 보고서에 보존했다.
- **검증 경과:** 전체 RTL 회귀·272벡터 정수 일치·host 43개·ARM/Vivado·보드 자체 검사·전체 frame·별도 20회 profile·각 300회 paired PASS.
  `python src/PL/fft128_ps/verify_dma_stream.py`, [빌드·실행·회수](../src/PS/fft128/dma_stream/README.md).
  RTL 정상상태 II 128 clocks, 첫 패킷 지연 1,514 cycles로 초기 지연은 늘었다. no-slot-conflict를 확인했다.
  사용자 자체 검사 콘솔은 probe 중간부터라 programming 시간은 미확보다. 회수 75파일/9,274,530 B는 공유 원본과 byte-identical이다.
- **결과:** 중앙값 double 5.826396 / NEON 3.652869 / PL 2.787411 ms. 같은 회차 NEON 대비 1.310488배·23.69% 짧다.
  계측 평균 전체 2.880577 / PL active 0.711424 / 복사 1.352026 / PS 전치 0.687152 ms.
  모든 20행에서 단계별 issue/retire 각각 16,384회, multi-stage 33,280 / vector-overlap 34,772 cycles/frame이다.
  저장 출력 정수 모델 완전 일치, NumPy 상대 L2 1.361020928%, IRQ 각각 660회, 검증된 22 artifact SHA 동일.
  계측 trial 혼입·1 LSB 출력 변조·stage6 retire 1회 누락을 거부했다. Ubuntu JSON 끝자리 차이는 별도 대조에만 허용하며 정수 일치에는 허용치를 두지 않는다.
  DSP 28 / BRAM 31, 50 MHz WNS 10.401 ns / WHS 0.024 ns, 무클록·무제약 경로 0.
- **해석:** 과거 bf2 대비 active 15.09% 감소지만 전체 중앙값은 1.91% 감소다. 별도 profile에서 비PL 비용은
  2.047466→2.169153 ms로 늘어 active 절감 0.126479 ms를 거의 상쇄했다. 증가 원인은 분리하지 않았다.
  부팅이 다르고 paired PS double +2.07% / NEON +3.76%도 관찰되어 전체 1.9%를 순수 스트리밍 효과로 단정하지 않는다.
  32-bit/50 MHz 공유 출력의 두 축 payload 하한은 0.655360 ms다. 현 active와의 차이 0.056064 ms는 이론적 여지이며 실현 가능한 절감 예측이 아니다.
- **다음·범위:** 요청한 E13 코어 복제·버터플라이 확대·스트리밍의 구현/보드 검증은 완료했다. 다음 후보는 복사 정책(E11d) 또는 PL 전치(E14)다.
  연속 UDP·최악 지연·무손실 실시간, 크기 스윕, PS02는 미검증이다. 기존 build metadata의 미검증 상태는 보존하고 완료는 artifact SHA별로 기록했다.
- **근거:** [준비·초기 실패·RTL](../benchmarks/reports/2026-11-21-e13-stream-preparation/README.md),
  [실제 구현·콘솔](../benchmarks/reports/2026-11-21-e13-stream-build/README.md),
  [원본·정확도·분포·분해·한계](../benchmarks/reports/2026-11-21-e13-stream-board/README.md).

---

## E14-frame — PL 전치와 전체 프레임 DMA (진행 중)

- **날짜·선행:** 2026-11-21, E13-stream. 사용자가 E14 진행을 요청했다.
- **질문:** Range 결과의 PS 회수·전치·Doppler 재제출을 없애 전체 지연을 줄일 수 있는가.
  E13-stream 별도 profile 평균은 전체 2.880577 / PL active 0.711424 / 복사 1.352026 / 전치 0.687152 ms다.
- **가설·설계:** 기존 단일 7단계 FFT를 두 축에 재사용한다. Range 출력을 16,384×32-bit RAM에 저장하고
  열 방향으로 읽어 Doppler에 공급한다. 한 열의 입력을 모두 소비한 뒤 같은 열에 결과를 덮어쓰고,
  완성 행렬을 Doppler-major/range-minor 순서로 배출한다. RAM 내용은 reset하지 않고 유효 상태만 초기화한다.
  중간·최종 행렬에 같은 64KiB를 사용해 추가 BRAM을 제한한다. E13의 BRAM 31/60에 행렬 약 16개가 더해지는
  자원 예산이며 합성·배치 실측은 아직 없다. 새 전체 프레임 ABI8·별도 backend를 사용한다.
- **유지:** Q15 butterfly/twiddle·반올림/포화·단계별 1/2 스케일, 50 MHz, HP0/64-bit·AXIS32,
  Simple DMA·coherent bounce·CPU0·측정 경계. 기존 E13 소스와 보고서를 보존한다.
- **변경 범위:** PS gather/scatter와 중간 host 왕복 제거, 1 ioctl·2채널 제출·64KiB/방향/프레임.
  CPU↔요청↔coherent 버퍼의 최초 입력·최종 출력 복사는 유지한다. 출력 순서 복원은 PL RAM에서 수행한다.
  새 `dma_frame` backend·드라이버·빌드/배치/수집/분석과 `fft128_dma_frame_ctrl`을 별도로 추가한다.
- **예상·위험:** 최종 행렬 배출 약 16,384클록이 새로 필요하므로 PL active 자체는 E13-stream보다 늘 수 있다.
  복사 반감과 전치 제거의 전체 효과는 cache·IRQ·DDR·새 스케줄에 따라 달라지며 실측으로 채우지 않는다.
  in-place 덮어쓰기의 read-before-write, 동기 RAM prefetch, backpressure, 오류/abort 이후 재실행을 직접 검증한다.
- **통과 조건:** 여러 전체 128×128 입력의 독립 정수 모델 일치, 두 축 각 128 FFT·단계별 발행/완료 보존,
  배열 순서·임의 TREADY·입력 starvation·잘못된 TLAST/TKEEP·AXI AW/W·각 phase abort/recovery,
  실제 Vivado RAM 추론·자원·50 MHz setup/hold·ARM 모듈/클라이언트, 보드 자체 검사 후 별도 frame/profile/paired.
- **로컬 검증 결과:** 6종 전체 128×128 입력을 사용한 18개 완성 프레임/294,912 complex bins가 정수 모델과 완전 일치했다.
  중간 결과 소비 scoreboard, read/write 충돌 없음, 정상 행렬 read/write 각32768, 단계별 issue/retire 각16384를 확인했다.
  이른 결과 fault injection은 실제 write 차단·오류 계수를 확인했다. 입력 지연·출력 정지·잘못된 TLAST/TKEEP·독립 AW/W·
  각 phase soft/hard abort 후 전체 재계산과 별도 reset 없는 반복 요청도 통과했다.
  기존 E11~E13 RTL 전체 회귀와 host53개(기존43+E14 10), C export/ABI shim·설정/overlay·스크립트 검사 PASS.
- **사이클 모델:** Range17771 + Doppler17771 + drain16385 = 51927 cycles, 50MHz 환산1.038540 ms.
  과거 E13-stream의 RTL35540cycles보다 PL 구간은 늘지만 PS 전치·중간 복사 절감은 별도로 기대한다.
  이 값은 보드 전체 시간이나 보장된 성능 예측이 아니다.
- **현재 상태/다음:** 로컬 구현·검증과 Vivado/ARM 빌드 준비 완료. ARM 실제 빌드·생성 reset IP·합성/배치 자원·50MHz 타이밍·
  보드 자체 검사/프레임/profile/paired는 아직 미확인이다.
  [정확한 소스·RTL·host 근거](../benchmarks/reports/2026-11-21-e14-frame-preparation/README.md),
  [빌드·배포·계측 절차](../src/PS/fft128/dma_frame/README.md).

---

### E14-frame 실제 빌드 확인 — 2026-11-21

- 사용자 비트스트림 생성 알림 이후 공유 run `fft128_dma_e14_frame_20261121_020411`을 독립 확인했다.
  ARM receiver/client·모듈 빌드와 기록 base-DT overlay 검증도 성공했다.
- PL/host/module source SHA는 현재 작업 파일·공유 소스와 일치한다. host/module artifact, ARM32 static ELF·
  모듈 vermagic, XSA와 구현 bitstream 일치를 확인했다. 보드 symbol CRC 수용은 아직 확인하지 않았다.
- 실제 routed LUT6158/17600, FF6305/35200, BRAM47/60, DSP28/80이며 행렬은 RAMB36 16개다.
  FFT는 기존 전용7단계/각4DSP·4RAMB36을 유지한다. 기준 E13-stream보다 BRAM16개가 늘고 DSP는 같다.
- 50MHz setup WNS10.166ns/hold WHS0.020ns, setup·hold·pulse failing endpoint0, no-clock·unconstrained0.
  생성 reset IP ID/ABI8/full-frame16384/초기계측/lock-loss simulation done1/passed1이다.
- FFT 외의 생성 BD PS7/DMA/clock/reset/IRQ·포트/연결/주소는 E13-stream과 동일하다.
  자원·타이밍으로 보드 전체 지연을 추정하지 않는다. 번들 생성·NFS 배포 후 보드 자체검사/frame/profile/paired를 진행한다.
- [실제 구현·ARM 로그·정확한 SHA](../benchmarks/reports/2026-11-21-e14-frame-build/README.md).
  초기 준비 기록과 빌드 metadata의 `board_verified:false`는 해당 단계 상태로 보존한다.

---

### E14-frame 사용자 보드 자체 검사 — 2026-11-21

- **증거 종류:** 사용자 제공 콘솔과 공유 번들 독립 SHA 대조. 보드 원시 profile·paired 파일은 아직 회수하지 않았다.
- FPGA Manager BIN 로드 57ms, E14 드라이버 정상 등록. 클라이언트 반복 4프레임 각각 256 FFT/16,384 bin 정수 일치,
  수신기 자체 검사 4프레임/65,536 bin PASS다.
- 계측한 클라이언트 3회 모두 matrix reads/writes 각각32,768, range/doppler_in/doppler_out 각각16,384,
  overwrite_errors=0. stage 수치 자체는 콘솔에 없고 동일 SHA 클라이언트의 검사를 통과했다.
- Range/Doppler/drain phase 합계51,943/51,941/51,941 cycles이며 50MHz 환산1.038860/1.038820/1.038820ms다.
  자체 검사 PL 구간 환산이며 CPU 복사 등을 포함한 전체 프레임 시간으로 해석하지 않는다.
- 번들22개 artifact와 기존 host/module 빌드 SHA, 현재 로컬·공유 compiled sources를 확인했다.
  구현 bitstream payload의 byte swap·Bootgen NOOP padding도 번들 BIN과 일치한다. 보드 파일 SHA는 아직 미회수다.
- **다음:** 현재 로드 상태에서 profile20회, CPU double/NEON/PL 각각300회 paired 측정 후 Ubuntu 수집·독립 재검산.
  [정확한 콘솔·신원·명령](../benchmarks/reports/2026-11-21-e14-frame-build/README.md). E14 성능 완료로 표시하지 않는다.

---

### E14-frame 원시 결과 독립 검증 완료 — 2026-11-21

- **증거:** 공유 수집82파일/9,290,439B를 ignored `build/fft128_dma_frame_measurements`에 SHA 동일하게 회수했다.
  Ubuntu 요약은 보존하고 Windows에서 paired/profile·입력Q15·정수 모델·소스·artifact·IRQ를 독립 재계산했다.
- **측정:** 고정128×128 입력, CPU0·warmup10/repeat100×3 회전, 창없음·전체1/16384 정규화.
  Q15 입력부터 CPU 가용2D 출력까지 필요한 복사/DMA/대기/전치·재배열을 포함하며 IO·양자화·할당·검증·plan 생성은 제외한다.
- **paired 중앙값:** double5.706612/NEON3.489441/PL1.657914ms. PL은 같은 회차 NEON보다2.104718배,
  double보다3.442043배 빠르다. PL p05/p95=1.649642/1.694033ms, 최대1.821228ms다.
- **별도20회 profile 평균:** 전체1.700746, PL active1.038842, 복사합0.590928, PS gather/scatter0ms.
  Range0.355722/Doppler0.355420/drain0.327700ms 합계가 PL active다. kernel/PL은 ioctl 내부라 전체에 중복 합산하지 않는다.
- **해석:** 과거 E13-stream의 전체중앙값2.787411→1.657914ms (40.521366% 감소), profile 복사1.352026→0.590928,
  CPU 전치0.687152→0ms. PL active는 최종 배출 추가로0.711424→1.038842ms로 늘어도 전체가 줄었다.
  1 ioctl/2채널/128KiB로 제출·외부 payload를 절반으로 줄였다.
  E13과 다른 부팅이며 PS기준도NEON4.47%/double2.06% 짧아져 차이 전체를 순수한 한 변수 효과로 단정하지 않는다.
- **정확도/신원:** 저장3trial/profile 각16,384 bin이 정수 oracle과 완전일치하고 peak(107,20), 기존 NumPy 상대L2오차1.361020928% 유지.
  번들22개와 수집/빌드/현재 로컬·공유 소스 SHA가 일치하며 profile/paired는 같은 부팅·bundle이다.
  IRQ67/68은 paired CPU0각330, profile각22회/CPU1증가0. 모든20행의 matrix reads/writes32768,
  range/doppler_in/doppler_out16384,overwrite_errors0,stage issue/retire각16384·CALC합121856이다.
- **완료/다음:** E14 고정 크기 오프라인 가속 검증 완료. 남은 복사(E11d)와 PL 배출/프레임 구조는 별도 최적화 후보이며
  연속 UDP 처리량·최악 지연·누락은 아직 검증하지 않았다.
  [전체 결과·원본 SHA·재계산 코드](../benchmarks/reports/2026-11-21-e14-frame-board/README.md).
  초기 준비/빌드/자체 검사 당시의 미확인 상태 기록은 그대로 보존한다.

---

## S1a — CFAR 기준 모델과 ground truth

- **배경:** E14까지 단일 FFT 지연만 줄였고, PS·PL 모두 12.8 ms 프레임 간격 안이다. 목표를
  [시스템 목표](system_goal_plan.md)의 end-to-end 최대 프레임률과 검출 정확성으로 재정의했다(2026-11-25).
- **질문:** PC 2D CFAR 기준 모델이 고정 입력과 추가 시나리오의 모든 표적을 ±1 bin 안에서 찾는가.
  보드에 올릴 CFAR 방식·파라미터는 무엇으로 고정하는가.
- **변경:** 새 `tools/detection/cfar_reference.py`(CA·OS 2D CFAR, 피크 묶기, 기대 bin 비교),
  `tools/detection/s1a_scenarios.json`. 처리 코드·보드·RTL 변경 없음.
- **조건:** 128×128, 창 none/hann, 입력 float/Q15 양자화, guard (2,2) train (8,8) Pfa 1e-6, OS k=0.75N.
  기대 bin은 [계획 3절](system_goal_plan.md#3-현재-입력의-기대-검출-위치-계산값-미검증)의 식.
- **검증 경과 (막힌 지점과 해결):**
  1. 첫 실행에서 무잡음 맵에 오검출이 많았다(hann CA 16개). 원인을 찾다가 **고정 기록에 수신 잡음이 없음**을 확인했다.
     RadarSimPy는 `baseband`(무잡음)와 `noise`를 따로 반환하고 `sender.py`는 `baseband`만 보낸다.
     신호 RMS 9.874e-4, 잡음 RMS 약 1.79e-3. 무잡음 맵은 피크 대비 바닥이 78 dB(none)~178 dB(hann)이고
     CFAR이 창 sidelobe를 잡음으로 보지 못해 Pfa가 의미를 잃는다. → 잡음 포함 시나리오를 추가했다.
  2. 무료판이 한 장면에 표적 2개까지만 허용해 4표적 실행이 실패했다(`Maximum 2 targets`).
     → 점 표적은 선형으로 더해지므로 표적별로 따로 시뮬레이션해 합쳤다.
  3. 같은 명령을 다시 돌리자 잡음 시나리오 검출 셀 수가 달라졌다(예: 20 → 19).
     확인 결과 `seed=42`에서도 RadarSimPy `noise`가 프로세스마다 달랐다(`baseband`는 동일).
     → 잡음을 NumPy `default_rng(42)` 복소 가우시안(RMS 1.79e-3, RadarSimPy 두 실행 1.7982e-3/1.7890e-3)으로 바꾸고,
     두 번 실행해 콘솔·프레임 SHA256 일치를 확인했다.
- **결과 (float 입력, PC 시뮬레이션):**

| 시나리오 | none·CA | none·OS | hann·CA | hann·OS |
|---|---|---|---|---|
| fixture_single (무잡음) | 1/1, 오검출 1 | 1/1, 1 | 1/1, 16 | 1/1, 30 |
| sim_multi4 (무잡음) | 4/4, 3 | 4/4, 8 | 4/4, 14 | 4/4, 49 |
| sim_close_weak (무잡음) | 2/3, 1 | 3/3, 1 | 2/3, 23 | 3/3, 53 |
| sim_single_noise | 1/1, 0 | 1/1, 0 | 1/1, 0 | 1/1, 0 |
| sim_multi4_noise | 4/4, 1 | 4/4, 7 | **4/4, 0** | 4/4, 0 |
| sim_close_weak_noise | 1/3, 0 | 2/3, 0 | 1/3, 0 | 2/3, 0 |

  - 고정 기록의 표적은 (Doppler 107, Range 20)에서 검출됐고 계산값 (-20.54 → 107.46, 20.01)과 일치한다.
    고정 기록과 같은 조건의 재시뮬레이션은 float32 전송 반올림으로 프레임 해시가 다르지만 모든 검출 결과는 같다.
  - Q15 입력 양자화는 잡음 포함 시나리오에서 float와 검출 결과가 모두 같았다. 무잡음 hann에서만 오검출 수가 달랐다
    (양자화 잡음이 바닥 역할). PL의 단계별 스케일·포화는 이 모델에 없다(S1c 범위).
  - sim_multi4_noise의 none 창 오검출 1개 (37,10)은 15 m 표적의 Doppler sidelobe이며 hann에서 사라졌다.
  - sim_close_weak_noise: 34.5 m/rcs 0 표적(피크/중앙값 18.7 dB, 30 m 표적과 Range 3 bin 차)은 CA가 놓치고 OS가 찾았다.
    무잡음에서도 같은 차이라서 **CA의 강한 표적 masking**으로 판단한다. 60 m/rcs -10 표적은 7.9 dB로 모든 방식이 놓쳤다.
- **해석:**
  - 고정 기록은 무잡음이라 FFT 타이밍·수치 검증에는 문제가 없지만 CFAR·검출 정확성 평가에는 쓸 수 없다.
    이후 검출 평가는 잡음 포함 입력을 기준으로 한다. 보드 연속 처리(S2)에도 잡음 포함 기록이 필요하다.
  - 잠정 기준: **hann + CA**(오검출 0, 4/4). 근접 강·약 표적은 OS가 낫지만 none 창에서 오검출이 늘고
    셀마다 정렬이 필요해 보드 비용이 크다. 기준 CFAR 결정은 보드 비용(S1b)을 잰 뒤 확정한다.
  - 현재 PS·PL 경로는 창 없음이다. hann을 쓰면 PS·PL 처리 경로가 바뀌므로 S1b·S1c에서 함께 결정·기록한다.
  - 표본은 시나리오당 한 실현이다. Pfa·검출 확률 통계는 아직 없다.
- **근거:** [S1a 보고서](../benchmarks/reports/2026-11-25-s1a-pc/README.md) (summary·콘솔·소스 SHA256).
- **추가 (같은 날): 잡음 포함 고정 기록 생성**
  - `tools/detection/make_fixture.py`가 `sender.py`의 `build_packet`으로 같은 RSPB0001 기록을 쓴다.
    잡음 시나리오 3개를 `benchmarks/fixtures/`에 저장했다(SHA256은 [fixtures README](../benchmarks/fixtures/README.md)).
  - 기록 도구 검증: 무잡음 고정 기록을 macOS에서 재생성하자 바이트가 달랐다(2,528번째 바이트부터).
    헤더는 같고 값 차이는 상대 L2 3.3e-9, 값의 0.32%가 float32 반올림 수준이다. Windows 원본과의 플랫폼 차이로 보고,
    커밋한 기록을 기준으로 삼는다.
  - 같은 기기에서 두 번 생성해 세 파일 모두 바이트 일치, `replay_udp.read_frame` 검사 통과(128 chirp, 1.6 MHz).
  - 저장한 기록(float32)으로 CFAR를 다시 돌린 결과가 float64 메모리 프레임의 결과(위 표)와 12개 조합 모두 같았다.
    보드 UDP 재생은 아직 하지 않았다.
- **다음:** 여러 잡음 실현으로 오검출률 확인, S1b(보드 PS에서 잡음 기록 수신·CFAR·시간 측정).

---

## E15-memory — 메모리 계층별 크기 비교 (계획)

- **날짜/선행:** 2026-11-21 / E14-frame. 사용자 제안에 따라 다음 실험 순서를 구체화했다.
- **관찰:** E14 hierarchical utilization의 BRAM36 환산 47/60 중 FFT 단계 28개, 행렬 16개,
  DMA 3개다. 단계별 128×32-bit RAM 4개는 원시 RAMB36 비트 용량 활용률이 약 11.1%다.
  용량 비효율은 확인했으나 포트·동시성 요구를 유지한 절감 가능량은 미확인이다.
- **가설/순서:** E15a 작은 RAM 배치 효율 확인 → E15b ≤256×128에서 실제 용량에 맞춰 BRAM·OCM 비교
  → E15c 큰 크기의 DDR 타일 전치. 같은 크기에서 배치를 비교하는 표본을 두어 크기 효과를 분리한다.
- **변경:** `docs/fft128_dma_plan.md`, 이 일지. RTL·드라이버·클록·펌웨어는 변경하지 않았다.
  [용량 계산·선행 확장·측정 계약](fft128_dma_plan.md#e15-memory--utilization-점검--bramocm--ddr-타일-전치-계획).
- **검증/결과:** 기존 routed 리포트와 RAM 선언을 대조했다. 새 빌드·RTL 실행·보드 측정은 없고 성능 수치도 없다.
- **다음:** E15a에서 128×128 산술·50MHz·인터페이스를 유지한 RAM 배치 후보를 검증한다.
  크기 확장에는 256-point 코어/주소/ABI·정수 모델 및 DMA length17 한도 처리가 선행된다.
  OCM은 물리 256KiB와 현재 OS에서 확보 가능한 용량을 구분한다.

---

## S1b — PS 수신기 CA-CFAR 구현·PC 커널 검증

- **날짜/선행:** 2026-11-25 / S1a. 진행 중이며 보드 완료를 뜻하지 않는다.
- **질문/가설:** S1a의 square-law CA-CFAR를 C++ 수신기에 추가해 같은 잡음 기록의 검출 목록을
  재현하고 CFAR 비용을 측정할 수 있는가. 합산 영역 테이블로 훈련 셀 합산을 줄이되 경계·피크 규약은 유지한다.
- **변경:** `src/PS/receiver/cfar_ca.hpp`, 수신기 `--cfar ca`·`--detections`, `cfar` 계측,
  portable C++ 드라이버/NumPy 대조 테스트, `tools/detection/build_s1b.sh`·`verify_receiver.py`.
  CFAR 기본값은 꺼짐이고 활성화한 경우 전력 맵 생성·배열 변환·임계값·피크 묶기·정렬을
  `cfar`와 `processing_total`에 포함한다. 버퍼 준비·CSV 저장은 측정 밖이다.
- **조건:** 원본 IQ·double FFTW를 S1b 비교 기준으로 사용한다. guard=(2,2), train=(8,8), Pfa=1e-6,
  Doppler wrap·Range 가용 셀 평균·3×3 지역 최대·전력 내림차순(동률은 bin 순서).
  잡음 기록 3개에 none/hann을 각각 적용한다. RTL·드라이버·클록·보드 펌웨어는 변경하지 않았다.
- **검증 경과:** 원격 `f884812`를 fast-forward하고 기존 E15·대시보드 로컬 작업을 보존했다.
  실험 일지의 S1a/E15 추가 위치 충돌은 두 기록을 모두 유지해 해결했다. E15의 시스템상 실행 위치는 S3b로 정리했다.
  Windows의 native g++로 공유 CFAR 헤더를 컴파일해 S1a의 독립 NumPy 셀 합산과 대조했다.
  무작위 직사각형/작은 원형 배열·0 입력·동률 피크·잘못된 파라미터 및 잡음 기록 6구성을 확인했다.
- **명령:** `python -m unittest discover -s src/PS/receiver/tests -v`.
  보드 번들 준비는 `python tools/detection/verify_receiver.py --prepare-only --out build/s1b_board_20261125_01 --warmup 10 --repeat 100`.
  [PC 근거](../benchmarks/reports/2026-11-25-s1b-host/README.md)에 콘솔·검출 목록·소스 SHA를 남긴다.
- **결과/범위:** portable CFAR 커널의 임계값(부동소수 누적 순서 허용 오차)과 검출 목록은 S1a와 일치한다.
  수신기 전체 Linux/ARM 빌드 및 FFTW 통합 검사는 미실시이며 관련 테스트는 skip이다.
  보드 프레임 수신·CFAR 시간·UDP·PL 검출·지속 처리량 측정값은 없다.
- **막힌 지점:** WSL 배포판 없음. VMware Ubuntu/Vivado와 터미널 화면은 Computer Use로 확인했으나,
  세션 재초기화·창 재선택 이후에도 문자/Enter 및 메뉴 클릭의 실행 결과를 확인하지 못했다.
  시리얼 COM4는 최초 조회 후 사라졌다. 기존 임시 SSH 등록은 11-17 만료로 기록돼 있다.
- **추가 발견:** S1a `quantize_q15`의 최대 I/Q 성분→32767과 실제 보드/수신기의
  최대 복소수 크기→16384 규칙이 다르다. 현재 PC float 기준 검증과 분리하고 S1c에서 규칙·스케일·포화를 맞춰야 한다.
- **해석/다음:** 커널 PC 검증만 통과했다. VM 입력 복구 후 host 전체 빌드/6구성 대조,
  호환 ARM 빌드·보드 같은 기록 대조와 CFAR 시간 측정, 실제 UDP 수신 검증을 완료해야 S1b를 완료로 표시한다.
  그 뒤 S1c → S2로 진행하며 기존 S1a의 근접 약표적 미검출을 실패 이력으로 유지한다.
- **후속 검증 (같은 날 19:25):** 위의 초기 미실시 상태에서 진전했다. 사용자가 기존 VMware
  공유 `share-2`를 `/home/user/fmcw_share`에 연결하고 Ubuntu g++ 9.4.0/x86_64로 전체 수신기 빌드를 완료했다.
  최초 실행은 FFTW3 동적 라이브러리를 찾지 못해 중단했다(`initial_missing_fftw.log`).
  런타임 설치 안내 후 재실행한 콘솔은 6구성 모두 PASS였다. 패키지 설치 콘솔 자체는 회수하지 않았다.
  공유 폴더에서 소스 SHA 4개·빌드 환경·실행 파일 SHA·6구성 전체 스펙트럼/검출/시간 원본을 회수하고
  Windows에서 독립 재계산해 FFT 복소수 값·검출 bin/전력/임계값·각 단계 3개 시간 표본을 확인했다.
  [Ubuntu 근거](../benchmarks/reports/2026-11-25-s1b-ubuntu/README.md).
  hann 다중 표적은 4/4·오검출 0, 근접 약표적은 1/3·오검출 0으로 S1a와 같다.
  warmup 2/repeat 3의 Ubuntu PC 기능 확인이며 보드 지연·P99·드랍·지속 처리량 근거로 쓰지 않는다.
  **현재 다음 단계는 ARM 빌드 → 보드 재생/CFAR 시간 → 실제 UDP 수신 검증**이다.
- **ARM 후속 (같은 날 19:27):** 사용자 콘솔의 `S1B_BUILD_PASS target=arm` 이후 공유 폴더에서
  실행 파일·빌드 환경·SHA를 회수했다. arm-linux-gnueabihf-g++ 9.4.0으로 빌드했고
  독립 확인한 ELF는 ARM32 little-endian, hard-float, flags `0x5000400`이다.
  수신기/헤더 소스 SHA 2개와 작업 사본이 일치하고 실행 파일 SHA도 일치했다.
  [ARM 근거](../benchmarks/reports/2026-11-25-s1b-arm/README.md). 보드에서의 로더/FFTW 실행은 아직 미검증이다.
  현재 다음 단계는 새 S1b 경로에 배포해 보드 기록 재생·CFAR 시간을 확인하는 것이다.
- **보드 기록 재생 후속 (같은 날):** `/opt/fft128/s1b_20261125_192718`에 별도 배포한
  ARM 실행 파일과 기존 PS01 double FFTW를 사용했다. 사용자 콘솔의 `S1B_RUN_COMPLETE` 이후
  환경·artifact check·실행 파일/라이브러리 SHA·6구성 로그/전체 스펙트럼/검출/시간 CSV를 회수했다.
  CPU0·single-thread double·원본 IQ·warmup 10/repeat 100, 각 구성은 같은 기록 프레임 반복이다.
  모든 artifact SHA와 소스 SHA 4개를 대조하고 Windows에서 FFT·임계값·검출·시간 표본을 독립 재검증했다.
  [보드 근거](../benchmarks/reports/2026-11-25-s1b-board/README.md).
  Hann 4표적은 4/4·오검출0, 중앙값 FFT5.514525ms/CFAR3.690945ms/processing_total10.206336ms,
  processing_total P99 10.30867179ms·최대10.328154ms다. 근접 약표적은 여전히 1/3 검출이다.
  `processing_total`은 UDP·파일 읽기·할당·계획·워밍업·CSV 저장을 제외한다.
  이 100개 표본의 P99를 end-to-end 연속 입력의 합격 근거로 쓰지 않는다.
  보드에서 CFAR 비용과 기준 검출 재현은 확인했으며 **실제 UDP 한 프레임 수신 검증**이 다음이다.
- **UDP 후속 (사용자 콘솔):** 초기 수신 대기는 사용자가 Ctrl+C로 중단했고, 같은 출력 폴더를
  재사용한 명령은 mkdir에서 중단했다. 새 출력 폴더의 재실행은 송신자 `10.0.0.2:41915`로부터
  128×128/fs1.6MHz 프레임을 받아 완료했다. duplicates/invalid/ignored는 모두0, Hann CA 피크4,
  CPU0·double·warmup0/repeat1이었다. 콘솔상 FFT5.964432ms/CFAR3.890856ms/processing_total10.884054ms.
  첫~마지막 패킷335.079279ms는 간격을 둔 한 프레임 전송이고, receive_total에는 첫 패킷 대기도 들어간다.
  [콘솔 근거](../benchmarks/reports/2026-11-25-s1b-udp/console_summary.json).
  보드 시계 기반 폴더명은 `udp_multi4_hann_20180309_135527`이며 실제 기록 날짜는 사용자 세션의2026-11-25로 구분한다.
  전체 검출 bin·스펙트럼·시간 CSV 원본은 아직 회수하지 않았으므로 UDP 정확성의 최종 판정은 보류한다.
  1회 처리 시간과 간격을 둔 송신으로 연속12.8ms 합격·드랍0·P99를 주장하지 않는다.
- **UDP 원본 최종 확인/완료:** 공유 폴더에 회수된 로그·전체 FFT·검출·시간 CSV4파일을
  `build/s1b_udp_multi4_hann_20261125_01/`에 보존하고 독립 재계산했다.
  모든16384개 FFT bin이 NumPy와 일치했다(최대 복소 오차1.9860273225978185e-15, 상대L2 4.695164787484549e-16).
  기존 Hann 4표적의 보드 기록 재생과 FFT 수치 배열이 정확히 일치했고 검출 CSV는 바이트 단위로 같았다.
  검출 bin은(Doppler,Range)=(10,10),(107,20),(4,37),(87,53), 정답4/4·오검출0이었다.
  전력·임계값·거리/속도 환산, decode/reassembly 각128개 표본과 처리 단계 각1개 표본도 확인했다.
  [최종 근거](../benchmarks/reports/2026-11-25-s1b-udp/independent_validation.json).
  **S1b는 기준 검출 재현·CFAR 비용·실제 UDP 한 프레임 경로 범위에서 완료**다.
  CA의 근접 약표적 미검출과 연속 운용 검증은 남는다. 다음 S1c에서는 E14 PL 출력에 같은 CFAR를 적용하며
  Q15 양자화 규칙·Hann 적용 위치·스케일/포화 및 측정 범위를 먼저 확정한다.

---

## S1c — PL Q15 출력의 CFAR 비교 준비

- **날짜/선행:** 2026-11-25 / S1b 완료. 아래 초기 준비 기록 뒤에 보드 완료 후속을 덧붙였다.
- **질문/가설:** 기존 E14의 단계별 Q15 floor·포화·1/16384 스케일을 거친 출력에서도
  S1b CA-CFAR의 피크 목록이 유지되는가. FFT 정수 오차와 검출 변화는 분리해 기록한다.
- **변경:** `tools/detection/cfar_spectrum.cpp`는 S1b의 `cfar_ca.hpp`를 공유해 E14 정수 CSV를 처리한다.
  `build_s1c.sh`, `verify_s1c.py`, `test_s1c.py`에 보드 CFAR 빌드·입력/정수 oracle 준비·검증을 추가했다.
  기존 RTL·펌웨어·DMA 드라이버·E14 실행 파일·S1b 수신기는 변경하지 않았다.
- **입력/수치 계약:** 커밋된 잡음 기록3개 × none/hann. Hann은 PC에서 원본 IQ에 대칭 창을 곱한 뒤
  float32 RSPB로 저장한다. 보드 E14는 이를 다시 window하지 않고 최대 복소수 크기→16384,
  ties-to-even으로 양자화한다. 이 규칙은 실제 `native_core.c`를 따르며 S1a의 최대 I/Q→32767과 구분한다.
  Python 독립 정수 모델이 7단계 floor·포화를 두 축에 적용하고 NumPy 이상 FFT·float 검출과 대조한다.
  E14 메타데이터의 window=none은 준비된 입력에 추가 창을 적용하지 않았다는 뜻이다.
- **측정 범위:** E14 실행 파일이 PL FFT를 내보내고 별도 C++ 프로세스가 CSV를 읽어 CFAR를 실행한다.
  두 프로세스 사이 파일 IO·입력 Hann 준비는 각각의 처리 시간 밖이다.
  PL 전달/FFT 시간과 CFAR 전력/임계값/피크/정렬 시간은 **성분별 시간**이며 합산해 종단 지연으로 쓰지 않는다.
  S2에는 입력 준비·CFAR·출력을 한 연속 경로에 연결하는 작업이 남는다.
- **PC 검증:** native C 정수 모델 실행 파일과 C++ CFAR를 Windows g++/gcc로 컴파일해
  Python 정수 oracle 및 NumPy CA-CFAR와 6구성을 대조했다. warmup1/repeat3, FPGA 없음.
  6구성 모두 정수 FFT의 모든16384개 bin과 검출 목록/전력/임계값이 일치하고 S1b float 피크 목록과 같았다.
  별도3테스트로 실제 보드 양자화 규칙·0입력·CSV 경계/정수 범위/누락/잘못된 값을 확인했다.
  모델 출력은 hardware check에서 거부되는 것도 확인했다.
- **명령/근거:** `python -m unittest discover -s tools/detection -p test_s1c.py -v`.
  `python tools/detection/verify_s1c.py --model-binary build/s1c_host_validation/model.exe --cfar-binary build/s1c_host_validation/cfar-spectrum.exe --out build/s1c_pc_20261125_03 --warmup 1 --repeat 3`.
  [PC 근거](../benchmarks/reports/2026-11-25-s1c-pc/README.md). 실행 파일은 ignored build에 둔다.
- **보드 준비 (사용자 콘솔):** 기존 `/opt/fft128/e14_frame/load_board.sh`가 artifact/HP0 검사를 통과하고
  E14 FPGA·overlay·모듈을 올렸다. packet/matrix/client 검사·native 4프레임 자체 검사가 통과했고
  `/dev/fft128-dma-frame`이 생겼다. 이는 기존 E14 자체 검사이며 새 잡음/Hann S1c 검출 결과는 아니다.
- **다음:** Ubuntu에서 새 CFAR를 ARM 빌드하고 새 번들 경로에 배포한다.
  보드6구성 정수 FFT·CFAR를 실행한 뒤 원본을 회수해 모델/float 검출과 대조한다.
- **ARM 준비 후속 (19:52):** Ubuntu의 ARM CFAR 빌드와 준비된6구성 번들을 공유 폴더에서 확인했다.
  ELF32 ARM hard-float flags0x5000400, 실행 파일 SHA
  `84ca32add47553c9d492746092aa308e41daee930470f786fcdd52cdc3f641a4`가 일치했다.
  manifest의 소스8개와 번들 artifact 전체 해시도 대조했다.
  [빌드/준비 근거](../benchmarks/reports/2026-11-25-s1c-pc/arm_preparation.json).
  새 S1c 보드 실행·정수 출력/CFAR 원본 회수는 아직 하지 않았다.
- **보드 완료 후속:** `/opt/fft128/s1c_20261125_195231/run_board.sh` 실행 후 원본을
  `build/s1c_board_results_20261125_195231/`로 회수했다. Ubuntu check에 이어 Windows에서
  독립 재검산했고 `S1C_RECORDED_CHECK_PASS cases=6 hardware=True`를 확인했다.
  artifact·소스8개 SHA, CPU0·ABI8·hardware 메타데이터 및 구성별100개 시간 표본을 확인했다.
  6구성의 모든16384개 정수 bin·CFAR 피크 순서/전력/임계값이 독립 기준과 같고 float 검출 목록과 일치했다.
  Hann 4표적4/4·오검출0, 근접 약표적1/3이다. multi4 Hann 중앙값은 PL1.670298ms,
  CFAR3.533088ms이며 두 성분을 합산해 종단 지연으로 해석하지 않는다.
  [보드 원본·독립 검증 근거](../benchmarks/reports/2026-11-25-s1c-board/README.md).
  **S1c 완료**, 다음 S2a에서는 수신·Hann/양자화·FFT·CFAR·출력을 한 프로세스로 연결하고
  프레임 ID·타임스탬프·드랍·CPU/메모리를 기록한다.

---

## S2a — 통합 연속 수신과 프레임·자원 계측 준비

- **날짜/선행:** 2026-11-25 / S1c 보드 검증 완료. 구현/PC 검사 단계, 보드 측정 전이다.
- **질문/가설:** 수신·입력 준비·FFT·CFAR·출력을 한 프로세스에 연결하고 프레임 ID로
  누락과 큐 드랍을 구분하면, 성분별 반복 시간 대신 실제 연속 경로 지연을 관측할 수 있는가.
- **변경:** `stream_receiver.cpp`, `stream_protocol.hpp`, `stream_pipeline.hpp`를 추가했다.
  기존 S1b/S1c 실행 파일·소스·RTL/드라이버는 보존한다. 공유 CA-CFAR와 native 양자화/정수 모델을 재사용한다.
  `replay_stream.py`는 v1 기록의 원래 float32 IQ payload에 v2 run/frame ID·송신 monotonic 시각을 붙인다.
  `build_s2a.sh`, `smoke_s2a.py`, `analyze_stream.py`, `test_s2a.py`, portable `stream_driver.cpp`를 추가했다.
- **구조/조건:** 수신 스레드의 partial 최대4, 완료 큐 최대4, 처리 스레드1개다.
  partial이 차면 가장 작은 ID를 버리고, 완료 큐가 차면 새 완료 프레임을 버린다.
  예상 ID1..N 모두 trace에 남긴다. 커널 수신 시각(SO_TIMESTAMPNS), 사용자 수신/조립 완료,
  처리 시작·준비/FFT/CFAR/CSV flush 완료를 기록한다. 커널 overflow 통지와 시계 변동도 기록한다.
  200ms 자원 표본은 process CPU(한 코어100%)·시스템 CPU·RSS다. `--cpu0`는 모든 스레드에 적용된다.
- **수치/비교 조건 변화:** PS는 double FFTW 2D ESTIMATE plan을 지속 재사용하는 새 기준이다.
  기존 S1b의 축별 FFT/전치 구현이나 최적화 NEON과 동일한 성능 조건이라고 주장하지 않는다.
  PL은 E14 ABI8 요청을 지속 재사용하며 Hann→float32 반올림→최대 복소수 크기16384 양자화를
  **수신기 안에서** 수행한다. S1c PC 준비/CSV 연결과 달리 이 비용이 프레임 측정에 포함된다.
  `model`은 명시적인 소프트웨어 경로이며 PL 실패 시 대체하지 않는다.
- **측정 범위:** 첫 커널 패킷→검출 CSV flush는 획득·소켓·조립·큐·준비를 포함한다.
  조립 완료→출력, 각 내부 구간도 따로 기록한다. 두 호스트의 시각은 빼지 않는다.
  flush는 fsync/표시/출력 소비자의 완료가 아니며 저장 위치(NFS/로컬)를 조건으로 기록해야 한다.
  trace 파일은 drain 후 기록하며, 자원 샘플링·검출 IO는 운용 중 실행한다.
  프레임 burst와 chirp100us 간격은 다른 부하이므로 송신 JSON에 구분한다.
- **PC 검증/결과:** Windows GCC/G++에서 생산 pipeline 헤더를 직접 컴파일했다.
  PS double FFTW와 C 정수 모델 각각 잡음3입력×none/hann의 모든 복소수16384 bin·전력·CFAR를
  독립 NumPy/Python 모델과 대조했다. 역순·중복 chirp도 검증했다. 누락·잘림·NaN·프레임 정보 혼합은 거부했다.
  실제 localhost UDP 송신 검사로 run/frame ID 및 의도한 chirp1개 누락(3프레임383패킷)을 확인했다.
  합성 trace에서 ID 누락·역전 시각 거부, partial 드랍 집계, kernel drop 발생 시 결과 무효화를 확인했다.
  총7개 unittest 통과. **생산 Linux socket/thread 코드 실행과 실제 FPGA 검증은 포함하지 않는다.**
  [PC 근거](../benchmarks/reports/2026-11-25-s2a-pc/README.md).
- **검증 중 수정:** 정수 전력 기대값을 `abs(z)**2`로 계산한 첫 검사는 sqrt/제곱 반올림 때문에
  최대7.45e-9 차이를 보고했다. oracle을 정수 실수부²+허수부²로 고치고 복소수 bin 자체의 정확 일치를
  추가해 통과했다. 계산 허용치를 느슨하게 해서 통과시킨 것이 아니다.
- **다음:** Ubuntu에서 host 빌드와3개 스모크(PS/model 정상 각20프레임, 의도한 누락1프레임)를
  실행하고 ARM 빌드한다. 새 보드 배포 경로에서 PS·PL 각각50ms 주기20프레임을 먼저 검증한다.
  이 단계는 계측 검증이며 12.8ms/10,000프레임·최대 지속 fps 합격은 이후 S2b/S2c에서 판정한다.
  [실행 절차·측정 계약](../tools/detection/S2A.md).
- **Ubuntu/ARM 후속 (20:18):** 사용자 실행 결과에 이어 공유 폴더의 host/ARM 빌드 및
  `build/s2a_smoke_20261125_201834/` 원본을 회수·독립 재검산했다.
  PS/model 각각20프레임 모두 검출 목록·프레임 trace·자원 표본이 유효하고 드랍0이다.
  의도한 frame2 chirp 누락은 정확히19처리·1 partial_evicted로 기록됐다.
  모든 검사에서 invalid·kernel drop·clock error·실행 오류0, 자원 표본은 각6개다.
  host는 cpu0=0인 Ubuntu VM localhost 검사이며 보드 성능으로 해석하지 않는다.
  두 빌드의 소스7개 및 검사/송신 도구5개가 로컬 소스와 같고 ELF/실행 파일 SHA도 대조했다.
  ARM ELF32 hard-float flags0x5000400, SHA
  `21548ffb2ed04c89e271f4dd1a952eafabfd58d5c8e64c6cb895d9b855438371`.
  [Ubuntu/ARM 원본·독립 검증 근거](../benchmarks/reports/2026-11-25-s2a-ubuntu/README.md).
  다음은 새 `/opt/fft128/s2a_20261125_201834/` 경로에서 PS·E14 각각20프레임/50ms 보드 검사다.

---

## S2a-rxfix1 — ARM32 수신 보조 데이터 호환·거부 진단

- **날짜/선행:** 2026-11-25 / S2a 초기 Ubuntu 스모크·ARM 빌드 후 보드 PS 실패.
- **실패 근거 (사용자 콘솔):** run92002, `ps_02/counters.txt`의 invalid=2560, 나머지 제시 계수0,
  검출 CSV는 헤더1줄이다. 송신 JSON은20프레임×128패킷·overrun0, Ubuntu 경로는ens33/src10.0.0.2,
  ping2/2성공이다. 유효 패킷을 전혀 받아들이지 않아 초기5분 대기까지 유지됐다.
  원래 invalid는 MSG_TRUNC·MSG_CTRUNC·decode 예외를 합친 값이므로 원인을 확정할 수 없다.
  보드 전체 원본은 아직 회수 전이며 콘솔·송신 JSON을 근거로 구분 보존한다.
- **가설:** ARM32의 원래 control 버퍼는36B(old timestamp20+overflow16)다.
  glibc가 time64 timestamp28B를 덧붙이면 공간이 모자랄 수 있다.
  [glibc 공식 수정 이력](https://sourceware.org/pipermail/glibc-cvs/2022q1/076544.html)은
  32bit time_t 프로그램에서도 변환/MSG_CTRUNC가 발생한 사례를 설명한다.
  이는 현재 증상과 일치하는 가설이며 실제 보드 msg_flags/controllen으로 아직 확인하지 않았다.
- **변경:** `stream_receiver.cpp`와 새 `stream_timestamp.hpp`에512B aligned control 버퍼,
  time32 8B/time64 16B 시각 해석, payload/control/decode별 계수·첫 거부 로그를 추가했다.
  잘린 데이터는 계속 거부한다. 수신된 모든 datagram이 idle 시각을 갱신하게 해 all-invalid 입력도
  마지막 패킷 뒤2초(기본값)에 종료한다. 입력이 전혀 없는 초기 대기는 별도 start deadline이다.
  `--diagnose-first-packet`는 구버퍼 MSG_PEEK 후 확대 버퍼로 같은 패킷을 수신하여
  구버퍼 truncation 여부·실제 cmsg형식·첫 유효 ID를 기록한다. 시각/버퍼 sizeof와 진단 flag도 저장한다.
  `build_s2a.sh`의 소스 식별8개, `analyze_stream.py`의 진단 flag, `smoke_s2a.py`의 model probe 검사를 갱신했다.
  새 `rebuild_s2a_rxfix1.sh`는 실패 원본을 회수하고 host smoke→ARM build→새 보드 경로 배포를 수행한다.
- **측정 범위/보존:** peek·첫 패킷 콘솔 IO는 진단 flag를 켠 실행의 첫 프레임 지연에 포함된다.
  해당 실행은 처리량 합격 근거로 쓰지 않는다. 원래 binary/7개 compiled source snapshot 및
  초기 Ubuntu 합격 결과는 그대로 보존하며 새 빌드/배포/출력 경로를 쓴다.
- **PC 검증:** 기존 PS/model6구성 FFT 모든 복소수 bin·CFAR 및 패킷/trace 검사에
  time32/time64·2038년 이후·잘못된 시각/길이·ARM32 dual timestamp 공간 검사를 추가해8개 unittest 통과.
  실제 recvmsg 및 수정된 host/ARM 빌드는 아직 실행하지 않았다.
  [실패·PC 검사·소스 근거](../benchmarks/reports/2026-11-25-s2a-rxfix1/README.md).
- **다음:** 새 host3스모크와ARM 빌드 후 보드20프레임 진단. 구버퍼 control_truncated가1이고
  확대 버퍼에서는0이며 정상 처리되면 가설을 보드에서 확인한 것으로 기록한다.
  그렇지 않으면 새 payload/control/decode 계수와 첫 로그로 다음 원인을 판단한다.
- **수정 Ubuntu/ARM 후속:** `s2a_smoke_20261125_rxfix1` 원본과 host/ARM 빌드를 회수했다.
  3개 스모크의 trace·피크·요약을 독립 재계산해 통과했고 model 정상 검사는 구버퍼 peek도 실행했다.
  Ubuntu64에서는 구버퍼56B/flags0, 확대 버퍼도 flags0이다. 이는 ARM32 현상의 재현 근거가 아니다.
  소스8개 SHA와 새 binary SHA가 일치하며 ARM SHA는
  `e221f04d232780c9193ca7f8c03df253e9fdba533d2bf7305e0da7c5cd508387`이다.
  초기 실패 `ps_02` 원본도 회수해 invalid2560·20개 missing ID·헤더뿐인 검출 CSV를 확인했다.
  [새 Ubuntu/ARM 근거](../benchmarks/reports/2026-11-25-s2a-rxfix1/ubuntu/independent_summary.json).
  이후 보드 run92003은 READY→processed0으로 끝났다고 사용자가 보고했다. 첫 패킷 로그가 없으며
  지정된 `s2a_sender_ps_rxfix1_01.json`은 공유 폴더에 없다. 새 board counters 원본은 회수 전이다.
  수신 대기 만료가 유력하나 계측 오류 가능성까지 현재 콘솔만으로 배제하지 않는다.
  다음은 별도 Ubuntu 송신 터미널을 먼저 준비하고 보드 READY 뒤 송신하는 동기화 재실행이다.
- **보드 원인 확인 후속 (사용자 콘솔):** 이전 run92003의 counters는 received_packets=0·failed0·
  interrupted0으로 입력 없이 끝났음을 확인했다. 다음 run92004/ps_02를 송신과 동기화하니
  구버퍼 MSG_PEEK는 bytes1076/flags8/control_truncated1/capacity36/controllen20,
  확대 버퍼의 같은 패킷 수신은 flags0/controllen48/cmsg `1:35:20;1:64:28;`이었다.
  첫 유효 run92004/frame1 후 `S2A_RECORDED processed=20 expected=20`을 출력했다.
  **ARM32에서 구버퍼가 time32+time64 보조 데이터를 담지 못한 원인을 확인했다.**
  [사용자 콘솔·송신 기록](../benchmarks/reports/2026-11-25-s2a-rxfix1/board_probe_console.txt).
  송신 JSON은50ms/20프레임·overrun0이며 전체 PS trace·검출·자원 원본은 회수 전이다.
  진단 IO를 포함한 시간은 성능 합격에 쓰지 않는다. 다음은 원본 검산 후 같은 입력의 PL 검사다.
- **PS 원본 완료 후속:** 보드 배포 디렉터리와 run92004의 frames/detections/resources/counters,
  사용자 Ubuntu summary 및 sender JSON을 회수했다. Windows에서 독립 재계산한 summary가 정확히 같고
  20/20처리·2560수신·드랍0·invalid/kernel/clock/worker 오류0이다. 모든 프레임의4개 검출 위치 및
  전력/임계값이 NumPy FFT/CA-CFAR와 일치한다. 각 프레임은4/4정답·오검출0이다.
  CPU0·time_t4B/timespec8B·소스8개·binary/artifacts SHA도 확인했다.
  진단 관측값은 첫 커널패킷→flush 중앙값22.4006925ms/P9924.7878909ms,
  조립완료→flush 중앙값13.662444ms/P9914.19137802ms다. 진단 실행이므로 성능 합격에 쓰지 않는다.
  자원22구간 중 활성 프레임과 겹치는 구간6개, 최대RSS5410816B다.
  [실제 보드 원본·독립 검산](../benchmarks/reports/2026-11-25-s2a-board/README.md).
  **S2a PS 계측/정확성 스모크 통과**, 다음은 같은50ms/20프레임·진단 설정의 PL 스모크다.
- **PL 실행 후속 (사용자 콘솔):** E14 디바이스가 있는 상태에서 run92005/PL/pl_01이
  구버퍼truncation·확대 버퍼flags0/48B·첫 유효 frame1을 기록하고20/20처리를 마쳤다.
  [콘솔](../benchmarks/reports/2026-11-25-s2a-board/pl_user_console.txt).
  PL 프레임별 검출/전력/임계값·trace/counters 원본은 아직 회수 전이므로 S2a 최종 완료 판정은 보류한다.
- **PL 원본 완료 후속:** run92005/pl_01의 전체 원본을 회수하고 Windows에서 독립 재계산했다.
  summary는 Ubuntu 결과와 같고20/20처리·2560수신·드랍0·모든 invalid/kernel/clock/worker 계수0이다.
  Hann→float32 반올림→실제16384 양자화→Python 단계별 정수 FFT로 기준을 만들었으며,
  모든 프레임의4개 검출 위치·80개 전력 값이 정수 기준과 정확히 같고 임계값도 NumPy와 일치한다.
  각 프레임4/4정답·오검출0이다. CPU0/hardware=true·소스8개·binary/artifacts SHA도 확인했다.
  [원본·독립 PL 검증](../benchmarks/reports/2026-11-25-s2a-board/pl_identity_and_correctness.json).
  진단 관측은 조립완료→출력 중앙값18.5183285ms/P9918.65466576ms,
  준비10.150683ms·FFT전달1.756872ms·전력/CFAR6.251232ms 각 중앙값이다.
  PS의 준비2.350314ms·FFT5.22195ms·조립완료→출력13.662444ms와 비교하면
  현재 PL 경로는 빠른 FFT에도 불구하고 입력 준비 추가 비용이 크다. 성분별 중앙값을 합산해 종단값으로 쓰지 않는다.
  두 실행 모두 진단 조건이므로 처리량 합격 판정은 하지 않는다.
  **S2a 완료:** PS/PL 통합 경로의 프레임ID·수신/준비/FFT/CFAR/출력 시각·드랍·CPU/RSS를 확인했다.
  다음 S2b에서 진단flag를 끄고12.8ms 입력을 측정한다.

---

## S2b — 12.8ms 연속 부하 검사 준비

- **날짜/선행:** 2026-11-25 / S2a PS/PL 계측·검출 원본 검증 완료.
- **질문:** 입력을50ms에서12.8ms 주기로 높였을 때 같은 통합 수신기가 프레임 누락 없이 처리하는가.
- **변경/조건:** 실행 파일은 rxfix1 SHA
  `e221f04d232780c9193ca7f8c03df253e9fdba533d2bf7305e0da7c5cd508387`을 그대로 쓴다.
  diagnostic flag를 끄고 같은128x128 multi4 noise/Hann·CPU0·warmup10·queue4/partial4·NFS 출력으로
  PS200프레임 예비 부하를 실행할 준비를 했다. sender는 chirp gap0/burst, period12.8ms다.
  input preparation·수신/reassembly·큐·CFAR·출력은 실제 경로 안에 유지한다.
- **예비 명령:** 보드 `stream-receiver --cpu0 --backend ps --fftw-lib /opt/fft128/s1b_20261125_192718/libfftw3.so.3 --start-ms 120000 --run-id 92101 --frames 200 --out /opt/fft128/s2a_20261125_rxfix1/s2b_ps_200_01`.
  Ubuntu `replay_stream.py ...multi4_noise.rspb --ip 10.0.0.3 --run-id 92101 --frames 200 --period-ms 12.8 --out build/s2b_sender_ps_200_01.json`.
- **검증 범위:** 우선200프레임의 처리/누락 분류·유효 송신 부하·원본 검출·자원 기록을 확인한다.
  첫 커널패킷→출력 및 조립완료→출력 P99를 모두 유지하고 서로 바꾸어 쓰지 않는다.
  200프레임은10,000프레임 합격 근거가 아니며 본검사를 대체하지 않는다.
- **현재 결과:** 준비만 완료, 아직 실측 없음. 과부하가 나타나면 실패 원본을 보존하고
  입력 준비·수신/처리 CPU·큐 등 관측된 병목을 다음 단계의 검증 근거로 사용한다.

---

## 새 실험 기록 양식

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
해석: 확인한 것 / 확인하지 못한 것 / 여러 변경의 혼동 변수:
다음 조치 / 보류 항목:
원본 파일 경로 / 보고서 경로 / 증거 종류(보드·콘솔·시뮬레이션·환산):
```

원본은 `benchmarks/reports/<날짜>-<실험>/`에 작은 텍스트·JSON·CSV로 보존한다. 대용량 프로젝트·바이너리는
`build/`에 두고 경로·해시를 기록한다. 재계산에 필요한 원본이 없으면 그 사실을 적는다.
