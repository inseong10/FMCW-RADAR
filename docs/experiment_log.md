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

## 현재 상태 (2026-11-26 기준)

- **현재 작업 S2a-int16:** 사용자 결정으로 시스템 입력을 ADC 모사 고정 스케일 int16 IQ로 바꾼다.
  Hann은 수신기 내부, PS int16→double 변환도 측정 내부다. 기본16비트/S=1,600,000, 프레임 정규화 없음.
  기존 float 원본/측정/실행 파일은 보존한다. PC int16 13개·float 회귀11개와 공유본 int16 13개 검사가 통과했다.
  Ubuntu host/ARM 빌드와 float/ADC 스모크 각3개 원본도 회수·독립 검증했다.
  **S2a-int16 완료:** PS92301·PL92302 보드 원본을 회수해 각각20/20·드랍/오류0·검출4/4·오검출0을 독립 확인했다.
  첫 프레임 전16384 complex bin도 PS NumPy/PL 정수 모델과 일치했다. 준비 중앙값은PS0.556071ms/PL2.460540ms다.
  다음은 진단을 끈12.8ms/200 예비 검사이며,10,000프레임 연속 합격은 아직 검증하지 않았다.
  **S2b-int16 예비(92311/92312, 12.8ms/200) 원본 검증:** PS는194/200(queue_full6, exit2, 송신overrun1)로 불합격,
  PL은200/200·오류0·4/4지만 첫커널패킷→출력P99 19.135ms>12.8ms로 지연 불합격이다.
  12.8ms 본검사(92321/92322)는 실행하지 않고 경로별 주기 조정 예비 검사로 넘어간다.
  **S2b-pace(진행 중):** 사용자 결정으로 실시간 기준을 조립완료→출력P99<주기로 바꾸고 송신에 chirp 간격100µs를 적용한다.
  송신기 chirp별 지각 기록을 추가했다. VM probe92330은 chirp 99%가4.1µs 안이지만 최대0.713ms 정지가 있어 초기 10µs 규칙으로 무효였다.
  사용자 승인으로 유효 조건을 P99<10µs·총지각최대<주기10%로 바꿨고 92330은 새 규칙에서 유효, 92335(고정+FIFO)는 무효다.
  보드 예비 PS92331/PL92332는 송신 부하 무효(판정 불가). PS는 처리≈16.9ms로 12.8ms 처리량 부족이다.
  PL 재실행92336은 송신 유효지만 프레임28부터 CPU 단계가 약1.38배 느려져 드랍18·P99 73.1ms로 불합격이다. 수신 종료 후 즉시 회복해 스레드/IRQ CPU 공유를 의심한다.
  pin-tid로 worker를 CPU1, main·sampler를 CPU0에 고정한 PL 92340은 200/200·조립완료→출력P99 10.911ms로 예비 조건을 충족했다. 고정 채택 여부는 사용자 결정 대기.
- **최상위 목표 변경(사용자, 11-26):** "최대 프레임률·교차점"에서 **입력 크기를 늘리며 실시간 조건 만족**으로 바꾼다.
  PS-only·PS+PL은 조건을 나눠 각각 측정한다. 이전 목표 문구와 S2c 계획은 [목표 문서](system_goal_plan.md)에 보존했다.
  크기 축·크기별 주기 규칙은 미정이다.
- **스레드 고정 채택(사용자, 11-26):** 정식 측정은 PS-only·PS+PL 모두 main·sampler→CPU0, worker→CPU1(pin-tid, 실행 직후 1회).
  다음 실행: PS 92341(12.8ms/200 예비, `ps_pace_prelim_02`), PL 92342(12.8ms/10,000 본검사, `pl_pace_main_01`).
- **무효 PS 92341 / PL 92342 (사용자 회수본 검사):** PS는 보드 수신 출력이 없고(미실행 추정) 송신 JSON만 남았다(지터P99 28.34µs로 부하도 무효).
  PL은 `interrupted=1`·exit2로 1670 processed/1 partial/8329 missing에서 중단, 송신 JSON과 고정 기록이 없어 고정 적용을 확인할 수 없다.
  처리분1670프레임의 조립완료→출력 P99 10.956ms는 참고값이며 판정에 쓰지 않는다. 원본 보존, 재실행은 PS 92343·PL 92344.
- **PS 92343 / PL 92344 (고정 정식 조건, 사용자 회수본 검사):** 두 실행 모두 mask 1/1/2 고정 확인.
  PS 92343(200 예비): 송신 유효(지터P99 5.19µs), 200/200·4/4·독립 검산 PASS, 조립완료→출력 P99 12.572ms<12.8 → 예비 충족(여유0.23ms).
  PL 92344(10,000 본검사): **불합격·무효.** kernel_drops277(빠진 패킷 전부), 9992 processed·3 partial·5 evicted, exit2.
  송신도 무효였다(지터P99 42.5µs, 총지각최대122ms; VM 정지 뒤 프레임 시작 지각이 회복 안 됨). 드랍은 송신 정지13·26ms 직후와 겹치지만 원인은 미확정이다.
  처리분 조립완료→출력 P99 11.114ms, 단계 시간은 92340과 같다(참고값). 10,000프레임 합격은 아직 없다.
- **재고정 송신·정지 허용 규칙 채택(사용자, 11-26):** 송신기 `--schedule reanchor`(SHA `51ba255c…f5452d`, 시험15개 통과)를 쓴다.
  지각>10µs면 실제 시각으로 시간표를 다시 맞추고 몰아 보내지 않는다. 유효 조건: P99<10µs, 최소 chirp 간격≥90µs,
  최소 프레임 간격≥주기−10µs, 정지 프레임(≥1.28ms)≤1%. 총 지각 최대는 보고값으로 바뀐다. analyze_stream `c9b500cd…`, checker `d26ff935…`.
  다음 실행: PL 92345(12.8ms/10,000 본검사, `pl_pace_main_03`).
- **PL 92345 (재고정 송신, 10,000): 무효·불합격.** 고정 기록이 0바이트라 고정 적용을 확인할 수 없고, clock_errors=1로 trace도 무효다.
  송신은 새 규칙에서 유효했다(P99 4.26µs, 정지 11프레임, 최대 2.77ms, 최소 간격 90.155µs/12.8002ms, 실효 주기 12.831ms).
  수신 1,280,000/1,280,000, kernel_drops0, 9327 processed·673 queue_full. 단계 시간이 정상(CFAR6.55ms)과 1.37배 감속(9.05ms)을 오갔다(92336 고정 없음과 같은 비율).
  다음: PL 92346, 송신 전에 고정 기록을 확인한다.
- **무효 92346(송신 없음, 고정은 적용)·92347(에이전트 PATH에 /sbin 없음 → devmem 없음, 수신기 미실행).** 92345 고정 기록이 빈 이유는 백그라운드 sudo 정지로 보인다(pid 10725, T 상태).
- **에이전트 실행 경로(사용자 승인, 11-26):** SSH 키 `fmcw_agent`(Windows→Ubuntu→보드), 보드 root 소유 래퍼 `/opt/fft128/agent_20261126_01/run_pinned.sh`(SHA `4e4cdf3c…`)만 NOPASSWD.
- **PL 92348 (에이전트, 고정 확인, 재고정 송신, 10,000): 불합격.** 송신 유효(P99 4.70µs, 정지 5프레임, 최대 8.2ms). kernel_drops108(그 밖의 카운터 0), 9996 processed·3 partial·1 evicted.
  처리분 조립완료→출력 P99 11.099ms, 지속 감속 없음. 드랍은 송신 정지 직후의 도착 압축(조립 7.89ms)과 보드 전체 단발 지연(4904 CFAR14.9+flush10.1ms) 뒤에 났다. 원인 미확정.
- **진단 설계 S2b-diag-out(사용자 승인, 미실행):** 출력 위치만 바꾼다(보드 tmpfs vs NFS). 92349 ram → 92350 nfs → 92351 ram.
  래퍼 v2 `run_pinned2.sh`(`2b06ecfd…`)가 실행 전후에 Udp RcvbufErrors·eth0·NFS rpc·cpu 스냅숏을 1회씩 남긴다. 해석 규칙은 [보고서](../benchmarks/reports/2026-11-26-s2b-pace/README.md)에 미리 고정했다.
- **S2b-diag-out 결과(진단, 92349 ram/92350 nfs/92351 ram):** 드랍 12/20/151로 ram에서도 드랍이 났다 → NFS 출력은 단독 원인이 아니다.
  보드 단발 지연(CFAR>8·flush>4ms)은 ram 0건, nfs 1~4건이다. 드랍은 조립 20~39ms 지연 뒤 압축 도착(7~8ms) 부근에서 났다.
  92350 4363·92351 7700은 송신 측 정지 기록 없이 조립이 늘어 VM 밖 경로 지연을 의심한다(미확인). 다음: 선로 도착 기록.
- **판정 기준 분리(사용자 결정, 11-26):** 실제 입력은 네트워크를 거치지 않으므로 UDP kernel_drops는 시험 경로 손실로 보고만 하고 처리 판정에서 뺀다.
  처리 실시간 조건: 연속 10,000프레임에서 조립완료→출력 P99<12.8ms, queue_full 0, 송신 유효, kernel_drops 외 카운터 0, 독립 검산 통과. checker `--network-loss-ok`(`13ab3a37…`).
  **재판정: PL 128×128 처리 실시간 충족 — 92348(정식 조건, nfs) P99 11.099ms·9996/10000 처리(손실 4프레임)·4/4.** 진단 92349·92351(ram)도 충족, 92350은 clock_errors로 무효.
  PS-only 10,000프레임은 미측정. 선로 도착 기록 진단은 필수에서 선택으로 바뀐다.
- **PS 92352 (PS-only 10,000, 정식 조건): 처리 실시간 불합격(참고).** 송신 유효. kernel_drops232, clock_errors3으로 trace 무효, 검산 거부.
  조립완료→출력 중앙12.444/P99 23.837ms(12.8 초과 234). 처리 중앙이 주기의 97%라 단발 지연 뒤 큐 회복이 느리다. 밀림 없는 구간 P99는 약12.6ms.
- **S3a-0 (PS 셀당 비용 감축, 11-26): 보드 prepare+CFAR 0.496→0.194µs/셀(목표≤0.2 충족), 결과 비트 동일.** 전력 루프 인라인, 정수 분리형 CA-CFAR, 무분기 창.
  **10k 처리 실시간: PL 92357 충족(P99 5.527ms, 92348 11.099), PS-only 92358 충족(P99 11.451ms, 92352 23.837 불합격)** — 둘 다 송신 유효·검산 PASS 4/4.
  92353–92355는 송신 무효(호스트 경합 추정), 92356은 실행 중 보드 비정상 재부팅으로 무효. [S3a-0](#s3a-0--ps-셀당-비용-감축-preparecfar)
- **S3a-1 (크기 일반화 M×N, 11-26): M∈{128,256,512}×N∈{128,256}, 128×128 결과 비트 동일(덤프 SHA, host·보드).** 방법 A(DIT 분할) 정수 경로, FFTW M×N.
  **10k 처리 실시간 유지: PL 92404 충족(P99 5.449ms), PS-only 92406 충족(P99 11.635ms)** — 송신 유효·검산 PASS 4/4. 큰 크기는 host 루프백만(8건 4/4), 보드 미측정.
  92401·92403(노트북 배터리 전원으로 송신 무효), 92405(송신 무효)는 판정 제외. [S3a-1](#s3a-1--프레임-크기-일반화-mn)
- **S3a-2 (D축 256×128, 25.6ms, 11-26): PL 92415 처리 실시간 충족(P99 17.558ms, 주기의 69%), PS-only 92416 불합격(처리 26.04ms > 주기, queue_full 153).** PL 분할 경로는 보드 diag 92417에서 전bin 일치. PL FFT 9.95ms 중 약 7ms가 결합 단(최적화 후보). [S3a-2](#s3a-2--d축-256128-m256-chirp-256ms-처리-실시간)
- **S3a-2b (결합 단계 감축, 11-26): 결과 비트 동일, 보드 결합 256×128 5.43→1.59ms.** int32 버터플라이, PL 블록 직접 DMA 버퍼 사용.
  **PL 256×128 10k 92419 충족 P99 12.569ms(주기의 49%, S3a-2 17.558)**, FFT 9.953→4.862ms. 92418은 clock_errors 1로 무효. diag 92420 전bin 일치. [S3a-2b](#s3a-2b--분할-경로-결합-단계-감축-결과-비트-동일)
- **S3a-3 (R축 128×256, 12.8ms, 11-26): PL 10k 92425 불합격 — 처리 13.761ms > 주기(queue_full 673).** PS 200 예비 26.39ms 불합격. range 결합은 diag 92426에서 하드웨어 전bin 일치. 약 2ms 감축 필요. [S3a-3](#s3a-3--r축-128256-n256-샘플-128ms-처리-실시간)
- **S3a-3b (R축 처리 감축, 11-27): 결과 비트 동일, PL 128×256 10k 92428 충족 — 조립완료→출력 P99 10.99ms(주기의 86%), queue_full 0.**
  N=256 짝/홀 저장 순서, range 단계 결합, NEON 결합·prepare(커널만 fpu=neon). 처리 13.761→10.609ms(prepare 1.53, FFT 3.69). NEON 등가성 결합 247.5M·윈도우 205.2M건, 덤프 동일(host·보드). diag 92427 전bin 일치. [S3a-3b](#s3a-3b--r축-128256-처리-시간-감축-결과-비트-동일)
- **S3a-4 (정사각 256×256, 25.6ms, 11-27): PL 10k 92440 충족 — 조립완료→출력 P99 23.128ms(주기의 90%), queue_full 0.** PS 200 92433 불합격(처리 76.85ms).
  보정 전 10k 92434–92436·92438은 clock_errors로 무효다. 원인은 오프셋 측정 중 스레드 선점(span 6.4ms → 편차 −3.2ms)이었고, 재측정 보정(receiver `e5792290`, 기준 불변) 후 clock_errors 0. diag 3회 전bin 일치. [S3a-4](#s3a-4--정사각-256256-주기-256ms-처리-실시간과-clock_errors-보정)

- **최신 성능 검증 구성:** E14-clock / 같은 E14 전용7단계 FFT·PL 전치/배열 복원 / 100MHz·Q15 / 전체 프레임 HP0 Simple DMA.
- **E14-clock 완료(11-26):** 원본83개·CPU 전후·번들30개·PL14/host12/module3 소스 신원·
  profile20회·paired 각300회·정확성·IRQ를 독립 검증했다. CPU는 전후666,666,660Hz 설정으로 같다.
  125MHz setup−0.727ns/321 endpoint 실패는 보존하고 사용자 선택100MHz에서 탐색을 종료했다.
  100MHz를 최대 클럭으로 확정하거나 과거 CPU 주파수를 소급 확인하지 않는다.
- **최신 paired 비교(각300회 중앙값):** PS double **5.631855ms** / PS float+NEON **3.563415ms** /
  PL **1.124817ms**. 같은 회차 NEON 대비 **3.167995배** 빠르고 지연은 **68.43%** 짧다.
  [완료 보고서](../benchmarks/reports/2026-11-26-e14-clock/README.md).
- **E13 완료 범위:** 2·4코어 복제 → E12 입출력 겹치기 → 코어당 버터플라이 2개 → 전용 7단계 스트리밍을 각각 구현·측정했다.
  마지막 구성은 4코어에 스트리밍을 더한 것이 아니라 단일 7단계 파이프라인으로 교체한 구조다.
- **현재 비용:** 100MHz 별도20회 계측 평균 전체1.154095ms, PL active0.519439ms,
  사용자 input/output 복사0.112839/0.074130ms, 커널 input/output 복사0.086194/0.301514ms, CPU 전치0.
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
  S2a 완료. S2b run92111 원본에서PS91/200·완성 큐 초과52·kernel패킷 손실3806·시각 오류4를 확인했다.
  처리91개는 모두4/4·오검출0이나 sender overrun32로 부하도 무효다. 이후 사용자 자원 활용 지시에 따라
  두 코어run92121 원본150/200·CPU135%·큐 초과35·미수신207패킷을 확인했으나 sender 부하는 무효다.
  VM deadline 진단과송신 spin 옵션PC8검사 후실제run92122 sender 원본에서overrun0·최대지각0.051748ms로
  유효부하에서PS179/200·PL123/200 원본을검증했고미처리는모두처리큐 초과21/77이다.
  입력/시각오류0·처리분정확성통과, CPU작업14.46/22.21ms 병목으로 opt1 후보PC11검사 후 ARM/보드 준비 중이다.
  10,000프레임 본검사는 아직 미실시다.
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
| E14-clock | 같은 E14 / 100 MHz | 5.631855 ms | 3.563415 ms | 1.124817 ms |

실험 사이의 PL 비율은 서로 다른 회차의 비교다. 같은 회차 PS 값도 회차마다 달라졌으며 원인은 확인하지 않았다.

## 실험 색인

| ID | 날짜 | 질문 | 주요 변경 | 상태와 핵심 결과 |
|---|---|---|---|---|
| [S3a-4](#s3a-4--정사각-256256-주기-256ms-처리-실시간과-clock_errors-보정) | 11-27 | 256×256(25.6ms)에서 PS+PL 처리 실시간인가 | RadarSimPy 256×256 고정 입력; receiver clock 진단 추가 후 오프셋 재측정 보정(span>20µs, 기준 불변) | **PL 10k 92440 충족 P99 23.128ms**(처리 22.654: prepare 3.14·FFT 9.12·CFAR 10.17); 보정 전 92434–92436·92438 clock_errors 무효(원인: 측정 중 선점, 92438 확인); PS 200 92433 불합격 76.85ms; diag 92431·92437·92439 전bin 일치 |
| [S3a-3b](#s3a-3b--r축-128256-처리-시간-감축-결과-비트-동일) | 11-27 | 128×256 처리를 결과 변경 없이 주기 안으로 줄일 수 있나 | N=256 짝/홀 저장 순서·연속 모으기, range 단계 결합, NEON 결합·prepare(pragma로 커널만) | 등가성 결합 247.5M·윈도우 205.2M건, 덤프 `2e47b50b` 동일(host·보드); **PL 10k 92428 충족 P99 10.99ms**(처리 10.609ms, FFT 6.045→3.688, prepare 2.382→1.530); diag 92427 전bin 일치 |
| [S3a-3](#s3a-3--r축-128256-n256-샘플-128ms-처리-실시간) | 11-26 | 128×256(N=256, 12.8ms)에서 PS+PL 처리 실시간인가 | RadarSimPy 128×256 고정 입력, 번들 shape 128x256(S3a-2b 소스) | **PL 10k 92425 불합격**(처리 13.761ms > 12.8, queue_full 673); PS 200 92424 불합격(26.39ms); diag 92426 range 결합 하드웨어 전bin 일치; 예측 13.3ms |
| [S3a-2b](#s3a-2b--분할-경로-결합-단계-감축-결과-비트-동일) | 11-26 | 분할 경로 결합 비용을 결과 변경 없이 줄일 수 있나 | int32 버터플라이(int64 /·% 제거), 인라인 디코드·팩, PL 블록 DMA 버퍼 직접 사용 | 등가성 247.5M건·덤프 동일(host·보드); 결합 256×128 5.43→1.59ms; **PL 92419 P99 12.569ms 충족**(FFT 4.862ms); 92418 clock_errors 무효; diag 92420 전bin 일치 |
| [S3a-2](#s3a-2--d축-256128-m256-chirp-256ms-처리-실시간) | 11-26 | 256×128(25.6ms)에서 PS+PL / PS-only 처리 실시간인가 | RadarSimPy 256×128 고정 입력(128 재현 확인), 번들 shape.txt, prepare 크기 인자 | **PL 92415 충족 P99 17.558ms**(FFT 9.95ms 중 결합 약 7ms); **PS-only 92416 불합격**(처리 26.04ms>주기, queue_full 153); PL diag 92417 하드웨어 전bin 일치 |
| [S3a-1](#s3a-1--프레임-크기-일반화-mn) | 11-26 | 수신·처리·송신·검산을 M×N으로 일반화해도 128×128이 그대로인가 | 프로토콜 크기 필드, 파이프라인 M×N·방법 A, 레코드 M×N, NumPy 방법 A 기준, smoke_s3a1 | 128×128 덤프 SHA 동일(host·보드); s3a1a 보드 ps detect +24% 회귀 → s3a1b에서 해소(+1.5%); host 4개 크기×model/ps 8건 4/4; **PL 92404 P99 5.449ms, PS-only 92406 P99 11.635ms 충족**; 92401·92403·92405 송신 무효(배터리 전원 등); 큰 크기 보드 미측정 |
| [S3a-0](#s3a-0--ps-셀당-비용-감축-preparecfar) | 11-26 | 128×128에서 prepare·CFAR 셀당 비용을 결과 변경 없이 줄일 수 있나 | 전력 인라인, `CaCfar::detect_integer`(uint64 분리형), 무분기 `adc_window`, 래퍼 v3 | 비트 동일(전수·45형상·덤프 SHA); 보드 0.496→0.194µs/셀; **PL 92357 처리 실시간 충족 P99 5.527ms, PS-only 92358 충족 P99 11.451ms**; 92353–92355 송신 무효, 92356 보드 재부팅 무효; 검산기 missing 손실 회계 추가 |
| [S2b-pace](#s2b-pace--실제-chirp-간격-송신과-조립완료-기준) | 11-26 | VM이 chirp 100µs 간격으로 송신하고 조립완료 기준을 만족하는가 | 기준 변경, 송신기 chirp별 지각 기록·판정, checker 기준 필드 | probe92330 새 규칙 유효; 보드 PS92331/PL92332 송신 무효(지터P99 13/31µs, 최대1.7/1.9ms). PS 처리≈16.9ms>주기·드랍39; PL 재실행92336 송신 유효·드랍18·P99 73.1ms(프레임28부터 지속 감속) → 12.8ms 불합격; 92337 스레드 기록이 CPU0 공유 가설 부분 지지; 92338 고정 실패(taskset 없음)·P99 46.7ms; 92339 고정 시 지속 감속 소멸(1회)·단발 지연은 진단 반복 기록 주기와 일치, trace는 clock_errors1로 무효; **92340 고정·반복 없음: 200/200·조립완료→출력P99 10.91ms <12.8 (예비 충족)**; 92341/92342 무효; 고정 정식 PS92343 예비 충족(P99 12.57ms); **PL92344 10,000 본검사 불합격·무효(kernel_drops277, 송신 지각 최대122ms)**; reanchor PL92345 송신 유효·kernel_drops0이지만 고정 기록 없음·clock_errors1·queue_full673으로 무효; **에이전트 PL92348 고정·송신 유효·P99 11.10ms, kernel_drops108**; 출력 위치 진단 92349–92351(ram에서도 드랍 → NFS 단독 원인 아님); **기준 분리(네트워크 손실 제외) 후 PL 92348 처리 실시간 충족**; PS 92352 10,000은 P99 23.8ms로 불합격(참고, clock_errors3) |
| [S2b-int16](#s2b-int16--adc-입력-연속-처리-예비-검사) | 11-26 | ADC 입력에서 12.8ms 연속 처리가 가능한가 | 변경 없음(S2a-int16 번들), measure 모드200프레임 | PS 드랍6·P99 71.1ms 불합격, PL 드랍0·P99 19.1ms>12.8 지연 불합격; 주기 조정 대기 |
| [S2a-int16](#s2a-int16--adc-모사-정수-입력-경계) | 11-26 | ADC 정수 입력에서 PS/PL 정확성과 준비 비용은 | 고정 스케일 int16·v3 프로토콜·수신기 내부 Hann | PC·Ubuntu·ARM·보드20/20 원본 PASS, 준비PS0.556/PL2.461ms; S2b 대기 |
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
| [S2b](#s2b--128ms-연속-부하-검사-준비) | 11-25~26 | 12.8ms 주기에서 드랍0·P99 목표를 지키는가 | 두 코어·spin 송신·CPU 처리 최적화 준비 | 유효부하PS179/200·PL123/200 원본/처리분정확성 검증, 미처리는큐 초과21/77. opt1 후보PC11검사 후 ARM/보드 대기 |
| [E14-clock](#e14-clock--최대-동작-클럭-탐색과-비교-준비) | 11-26 | CPU 정격/선택한 PL 클럭에서 비교하는가 | 같은 E14 RTL·ARM 바이너리, MMCM 출력 및 연결 AXI/DMA 클럭 변경 | 완료.100MHz PL1.124817ms/같은 회차 NEON 대비3.167995배. 원본83개·CPU 전후·각300회 검증,125MHz 실패 보존 |

## 공통 조건과 해석 규칙

- **보드·도구:** Zybo Z7-10 / XC7Z010-1CLG400C, Vivado 2022.1, ARMv7 hard-float,
  PetaLinux kernel `5.15.19-xilinx`. Ubuntu 20.04.6은 빌드·TFTP·NFS 호스트다.
- **입력:** [RadarSimPy 기록](../benchmarks/fixtures/README.md) 128×128, SHA256
  `aa06ff124034310216693c1398f2f1061c9a6ce32e9ea6f5687675849934c976`,
  한 채널, fs 1.6 MHz, 표적 30 m / -10 m/s. 입력 기록에는 FFT 결과가 들어 있지 않다.
- **처리:** 창 없음, 같은 Q15 양자화 입력, 전체 정규화 1/16384. PS FFTW는 double(PS01부터 float 변형 추가), PL은 Q15 고정소수점.
- **CPU 주파수:** 과거 회차는 직접 확인하지 못했다. BogoMIPS에서 추정한667MHz를 실측값으로 쓰지 않는다.
  11-26에는 사용자 콘솔의 기준33,333,333Hz·ARM PLL40·CPU분주2로 현재설정666,666,660Hz를 확인했다.
  물리 주파수 카운터 측정이나 과거 회차의 주파수 확인을 뜻하지 않는다([E14-clock](#e14-clock--최대-동작-클럭-탐색과-비교-준비)).
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

### S2b / 11-26 run92111 PS 예비 실패·송신 부하 무효

- **질문/조건:** E14-clock100MHz offline 비교 후 기존 S2b 계획을 재개했다.
  PS double FFTW 통합 수신기 rxfix1을 재사용하고 CPU0·Hann·warmup10·queue4/partial4,
  진단 끔·start120000ms·idle2000ms·200프레임·주기12.8ms·chirp gap0/burst로 실행했다.
  PS backend는 FPGA를 실행하지 않는다. 이 회차의 클럭/실행 파일 신원 원본은 아직 회수 전이다.
- **명령/경로:** board `/opt/fft128/s2a_20261125_rxfix1/stream-receiver --cpu0 --backend ps --window hann --warmup 10 --fftw-lib /opt/fft128/s1b_20261125_192718/libfftw3.so.3 --start-ms 120000 --idle-ms 2000 --run-id 92111 --frames 200 --out /opt/fft128/s2a_20261125_rxfix1/s2b_ps_100mhz_200_01`.
  sender `tools/sender/replay_stream.py benchmarks/fixtures/radarsimpy_128x128_sim_multi4_noise.rspb --ip 10.0.0.3 --run-id 92111 --frames 200 --period-ms 12.8 --out build/s2b_sender_ps_100mhz_200_01.json`.
- **사용자 콘솔:** receiver `processed=91 expected=200`, sender `overruns=32`.
  미처리109개는 아직 missing/partial/queue_full 등으로 분류하지 않았다. 지연·CPU·정확성도 미확인이다.
- **독립 송신 원본 검증:** 공유 JSON을 보존하고200개 ID·timestamp에서 overrun32와
  최대 start lateness14.697306ms를 재계산했다. 실제 프레임 시작 간격은2.263128~26.108878ms다.
  zero overrun·최대 지각<주기10% 조건을 만족하지 않아 offered load는 무효다.
- **해석/다음:** 이번 예비 시도는 합격하지 못했다. PS의 정규12.8ms 처리 한계나 PS/PL 성능비로 단정하지 않는다.
  수신 원본을 회수해109개 미처리 분류·kernel/큐·두 지연 기준·자원을 확인하고 송신 스케줄 원인을 점검한다.
  반복은 새 ID/경로에서 수행하며 이 실패와 최초 준비 상태를 보존한다.
- **근거:** [S2b 보고서·송신 원본·콘솔](../benchmarks/reports/2026-11-26-s2b/README.md).

### S2b / run92111 보드 원본 회수·실패 분류 완료

- **원본/검증:** 공유 `build/s2b_ps_100mhz_200_01`의5개/49,040byte 원본을 로컬 ignored build에 복제하고
  각각SHA를 대조했다. [보고서](../benchmarks/reports/2026-11-26-s2b/README.md)에 원본5개와
  재현 분석 코드·기준 모델·trace 요약·독립 검증 JSON을 보존했다. 위 콘솔 단계 기록은 이력으로 유지한다.
- **누락 분류:** processed91, queue_full52, partial_evicted50, partial3, missing4로200개 ID를 전부 설명한다.
  received21794 + kernel_drops3806 = expected25600 패킷이며 frame별 수신 수 합계도21794다.
  실제SO_RCVBUF360448byte, invalid/decode/metadata/truncation/worker/interrupted 오류0이다.
- **정확성:** 처리91개 모두4/4·오검출0,364개 peak power/threshold가 정규화한 독립 NumPy FFT/CA와 일치한다.
  최대 상대오차는각4.06e-16/9.82e-14다. 누락109개와 전체FFT bin 정확성 검증을 주장하지 않는다.
- **관측 지연:** 처리 프레임의 queue wait 중앙값101.381077ms, worker start→flush29.069874ms,
  FFT12.713731ms, power/CFAR13.284504ms다. worker wall은 수신과 CPU0 경쟁·선점을 포함한 경과 시간이다.
  첫 kernel packet→flush 중앙값142.090342/P99167.2789714ms,
  complete→flush 중앙값131.645827/P99149.4763043ms를 원값으로 보존한다.
  clock_errors4가 있어 kernel 시각 기반 합격 근거로 쓰지 않으며 처리된 프레임만의 진단 통계다.
- **자원:** 활성 구간과 겹치는13개 전체 sample interval을 기간 가중한 process CPU는한코어 기준94.02%,
  system CPU50.19%, 최대RSS7335936byte다. 경계 sample 여백이 포함된다.
- **해석:** 수신 socket/kernel 손실과 완성 큐 초과를 모두 확인했다. 송신 지각도 동반돼 정규12.8ms 지속 한계로
  단정하지 않는다. clock error의 원시 calibration sample이 없어 원인은 미확정이다.
  이번 실행의 binary/주파수 캡처도 없으며 과거100MHz 검증을 이번 회차 실측으로 대체하지 않는다.
- **다음:** 같은 binary·CPU0·큐·fixture·Hann/CFAR에서진단 끔50ms/200프레임 baseline을 새run으로 실행한다.
  낮은 부하에서 sender validity·드랍0·시각 오류0를 먼저 확인한 뒤 PL과 주기 스윕을 진행한다.
  12.8ms 합격 목표는 유지하고 큐 확장이나 core 배치 변경을 이 baseline에 섞지 않는다.

### S2b-2core / 사용자 결정: 최종 비교에 두 CPU 코어 활용

- **날짜/질문:** 2026-11-26. 사용자가 보드 자원을 최대한 활용한 비교를 요구했다.
  CPU0로 수신·처리·계측을 모두 제한한 run92111은 진단 기준값이며 최종 PS 성능으로 쓰지 않는다.
- **변경/가설:** 기존 rxfix1의 `--cpu0` 옵션을 제거한다. 소스에서 이 옵션이 있을 때만
  `sched_setaffinity`를 CPU0로 설정하고 그 뒤 worker/sampler를 생성함을 확인했다.
  옵션 없이 실행하면 상속 affinity 내에서 스레드가 동작한다. 두 CPU가 online이고0-1 affinity가
  허용되는지 확인한다. 수신과 작업 스레드의 CPU 경쟁을 줄일 수 있다는 가설이며 아직 성능은 미측정이다.
- **다음 실행:** 새run92121 PS, `s2b_ps_2core_12p8ms_200_01`, 같은 multi4 noise/Hann·warmup10·queue4/partial4·
  진단 끔·period12.8ms·200프레임·chirp gap0·NFS 출력. 기존 binary와FFT/CFAR/버퍼는 유지한다.
  이후 PL도 같은 두 코어 허용 조건으로 비교하며PL100MHz는 유지한다.
  앞서 제안한CPU0/50ms run92112는 실행 여부가 아직 확인되지 않았으며, 결과가 있으면 별도 보존한다.
- **유효성:** sender zero overrun·최대지각<주기10%, receiver 시각/오류·드랍·정확성 검사를 그대로 적용한다.
  CPU 배치 변경으로 송신 지각이나 clock_errors가 해결됐다고 가정하지 않는다. 유효 부하가 확보되지 않으면
  낮은 부하/송신기 점검으로 진행하며 이번 run을 최종 처리량 비교로 쓰지 않는다.
- **후속 최적화:** 현재 stream PS는double FFTW ESTIMATE·단일 처리 worker다.
  unpin을FFT/CFAR 내부 병렬화나최적 PS 완성으로 부르지 않는다. 각 경로에두코어를 허용하고
  관측된 병목에따라NEON/FFTW계획·CFAR 병렬화·수신 배치를 검토하며 정확성을 재검증한다.
  CPU를100% 채우는 대신 드랍0·P99·정확성 아래 최대 지속 처리량을 목표로 한다.
- **결과/근거:** 실행 조건/계획 수정과 기존 소스 확인만 완료. 새보드 측정·가속비는 아직 없다.
  [S2b 보고서](../benchmarks/reports/2026-11-26-s2b/README.md)에 기존 실패와 변경 의도를 분리 기록한다.

### S2b-2core / run92121 콘솔150/200·송신 부하 재실패

- **조건:** 기존 rxfix1 PS binary·Hann·warmup10·queue4/partial4·12.8ms/200프레임·burst·진단 끔을 유지하고
  `--cpu0`만 제거한 run92121. 사용자 콘솔에서150/200 처리, sender overrun35를 확인했다.
  online CPU/allowed affinity 출력은 제공되지 않았고 수신 raw는 아직 회수 전이다.
- **독립 송신 검증:** `build/s2b_sender_ps_2core_12p8ms_200_01.json`의200 ID/시각에서overrun35와
  최대지각16.692511ms를 재계산했다. 송신 duration 중앙값3.0403965ms/최대6.881976ms,
  프레임 시작 간격 중앙값14.425804ms/최소2.588512ms/최대28.919078ms다. 부하 유효 조건 미충족이다.
- **해석:** 처리 개수는run92111의91보다 늘었으나150/91을유효한성능비로쓰지 않는다.
  이번 회차 CPU 활용률·시각 오류·누락50개 분류·지연은 아직 알 수 없다.
- **다음:** 수신 raw회수와 함께S2b-pacing에서Ubuntu VM의deadline wakeup을 먼저 점검한다.
  PS/PL 비교 전에 유효한 송신 부하를 확보해야 한다. 같은 실패 조건의 반복으로 최종 한계를 확정하지 않는다.
- **근거:** [S2b 원본 sender·사용자 콘솔·검증](../benchmarks/reports/2026-11-26-s2b/README.md).

### S2b-pacing / VM 대기 방식 진단 준비

- **질문/가설:** 두 번의12.8ms 검사에서송신35/32 overrun과14~17ms최대지각이 반복됐다.
  `time.sleep` wakeup 지연/VM 스케줄링이 기여할 수 있다. 원인이VM timer라고확정하지않는다.
- **변경:** `tools/sender/check_pacing.py`는 네트워크 없이sleep/spin 각각200×12.8ms 절대deadline을
  기록한다. mode별원시시각·최대/중앙 지각·주기10%이상지각수·process CPU·Python/platform/affinity를 저장한다.
  실제sender기본동작과보드binary·버퍼·알고리즘은그대로다. spin구간약2.56초는Ubuntu VM의CPU를사용한다.
- **PC 검증:** 결정적가짜시계3검사로sleep초과와catch-up보존·절대시각spin·지난deadline무대기를확인했다.
  `python -m unittest discover -s tools/sender -p test_check_pacing.py -v` PASS.
  VM실행/네트워크부하검증은아직없다. wakeup진단이통과해도실제UDP송신유효성은별도측정한다.
- **실행 예정:** Ubuntu `python3 tools/sender/check_pacing.py --period-ms 12.8 --frames 200 --out build/s2b_pacing_12p8ms_01.json`.
  수신기는실행하지않아도된다. VM원본결과에따라sender대기방식/환경을조정하고새ID에서실제부하를재검증한다.
- **근거:** [PC 검사·소스 SHA](../benchmarks/reports/2026-11-26-s2b/pacing_pc_validation.json).

### S2b-2core / run92121 원본150/200·정확성·두 코어 사용 확인

- **원본:** 공유 `build/s2b_ps_2core_12p8ms_200_01`의5개/66353byte 원본 SHA를 대조하고
  [보고서](../benchmarks/reports/2026-11-26-s2b/README.md)의`ps_92121_raw`와분석JSON/드라이버에보존했다.
- **분류/패킷:** processed150, queue_full35, partial_evicted11, partial4. frame별packets합계는received25393과같다.
  expected25600 대비미수신207개중기록kernel_drops는192이며15개위치는미확정이다.192를전체손실로쓰지않는다.
  clock/metadata/decode/truncation/worker오류는0이다.
- **정확성/자원:** 처리150개모두4/4·오검출0,600개power/threshold가독립NumPy모델과일치한다.
  활성영역과겹치는14개전체sampleinterval의기간가중process CPU는한코어기준134.6725%, system68.6313%,
  최대RSS7380992byte다.상속affinitymask는없으나한코어를넘는process CPU소비로멀티코어실행을확인했다.
- **관측:** first kernel→flush 중앙값81.847453/P9995.54649946ms, complete→flush75.547510/P9988.44221914ms,
  queue wait57.5811215ms, worker16.389597ms, FFT5.409438ms, power/CFAR5.570661ms중앙값이다.
  송신부하무효/드랍동반·처리프레임만의진단통계이며단일코어와정밀한성능비로쓰지않는다.

### S2b-pacing / Ubuntu VM 원본 검증 완료

- `build/s2b_pacing_12p8ms_01.json`의sleep/spin각200개절대시각·최대/중앙지각·주기10%초과수를독립재계산했다.
  파일의source SHA는보존된진단스크립트와같다. Ubuntu Python3.8.10·VM4CPU/affinity0-3조건이다.
- **sleep:** 중앙지각4.881992ms, 최대15.732412ms, 1.28ms이상169회, process CPU0.3784%.
  **spin:** 중앙지각0.000404ms, 최대0.010425ms, 기준초과0회, process CPU99.9727%.
- 대기방식이이VM의deadline wakeup에영향을줌을확인했다. VM/host의세부원인을확정하거나
  네트워크를포함한송신부하통과로확대하지않는다. [원본·검증](../benchmarks/reports/2026-11-26-s2b/pacing_vm_verified.json).

### S2b-spin / 실제송신기 대기 옵션 준비

- **변경/가설:** `tools/sender/replay_stream.py`에명시옵션`--wait-mode spin`을추가했다.
  기본sleep은유지하며frame/chirp절대deadline을동일하게적용한다. 지각/overrun을보정하거나숨기지않는다.
  wire·입력·128chirp burst·수신기·코어허용·버퍼·알고리즘은유지한다.
  sender JSON에wait mode/CPU/Python/source SHA를추가하고콘솔에는최대지각을함께표시한다.
- **PC 검증:** 가짜시계6검사와실제loopback sleep/spin 각각wire/ID/의도적손실2검사, 총8개PASS.
  관련Python4개파일의3.8문법검사도PASS다. 보드성능시험을대신하지않는다.
  소스SHA와당시sender사본을[PC검증](../benchmarks/reports/2026-11-26-s2b/sender_spin_pc_checks.json)에보존했다.
- **공유 반영:** 알려진구버전SHA를확인하고기존파일을백업한뒤sender/진단/관련테스트3개만반영했다.
  공유폴더의별도수정된수신기테스트는보존했다. 보드재빌드/재프로그램은필요없다.
- **다음:** 새PS run92122, two-core 허용·12.8ms/200·Hann·warmup10·queue4/partial4와
  sender`--wait-mode spin`을사용한다.실제송신/보드결과는아직없다.유효부하·드랍·시각·정확성을재검증하고
  다음PL비교또는확인된worker병목최적화로진행한다.이전실패원본은모두유지한다.

### S2b-spin / run92122 실제송신 유효·PS콘솔179/200

- **조건:** 기존rxfix1 PS·두코어허용·Hann·warmup10·queue4/partial4·진단끔·12.8ms/200프레임·burst·NFS출력을
  유지하고명시sender`--wait-mode spin`을사용했다. 사용자콘솔은179/200처리를보고했다.
- **독립sender원본검증:** `build/s2b_sender_ps_2core_spin_12p8ms_200_01.json`을보존하고200개ID·프레임별
  128*1076byte·소스SHA·절대시각을확인했다. overrun0·최대지각0.051748ms<1.28ms로기존부하유효조건을통과한다.
  실제frame-start간격은최소12.749686/중앙12.800001/최대12.850493ms, 송신duration중앙2.700363ms,
  VM process CPU99.4241%다. 저장된source SHA는현재검증된sender사본과같다.
- **판정/한계:** 수신누락21개가있어드랍0조건은실패했다. 누락분류·kernel/clock오류·지연·정확성·자원은
  수신raw회수전이므로아직확정하지않는다.179를지속FPS나최종PS상한으로환산하지않는다.
- **다음:** 이PS수신raw를회수하고동일spin송신/두코어허용12.8ms/200의PL run92123을측정한다.
  선택PL100MHz와기존binary/버퍼/CFAR를유지하며재빌드/재프로그램하지않는다.
  양쪽baseline원본을비교해관측된병목을최적화하며이단계를최적PS/PL완성으로부르지않는다.
- **근거:** [송신원본·검증·사용자콘솔](../benchmarks/reports/2026-11-26-s2b/README.md).

### S2b-spin / PS92122·PL92123 유효부하 원본 검증 완료

- **원본/조건:** 동일12.8ms/200프레임·spin·두코어허용·Hann/CA·warmup10·queue4/partial4·NFS출력이다.
  PS/PL sender최대지각0.051748/0.041537ms·overrun0, sourceSHA와전송byte수를독립검증했다.
  수신원본각5개를공유/로컬SHA대조후[보고서](../benchmarks/reports/2026-11-26-s2b/README.md)에보존했다.
- **분류/정확성:** 두경로모두25600패킷전부수신·kernel/clock/decode/worker오류0이다.
  PS179처리/21queue_full, PL123처리/77queue_full로200개ID를모두설명한다.
  PS716개peak는정규화NumPy power/CA와일치, PL492개peak power는Q15정수모델과정확히같고threshold도기준에일치한다.
  처리분모두4/4·오검출0이며누락프레임정확성/전체FFT spectrum을추가검증했다고쓰지않는다.
- **구간별중앙값ms(각구간별통계,합산금지):** PS준비2.413164/FFT5.751816/powerCFAR6.014754/worker14.463708/queue50.525185.
  PL준비12.114900/FFT1.265694/powerCFAR8.596980/worker22.209787/queue79.073491.
  first kernel→flush P99는PS81.90911946/PL114.00777688ms,
  complete→flush P99는PS73.21141944/PL107.04353932ms다.처리된프레임만의분포다.
- **자원/판정:** 기간가중process CPU한코어기준PS141.5339%/PL135.4104%, 최대RSS6656000/5357568byte.
  둘다드랍0·P99목표실패다.프레임개수를최대지속FPS로환산하지않는다.현재회차의클럭/실행파일캡처는없다.
  PL FFT는빠르지만준비·후처리가전체경로를지배한다.수신버퍼/큐를키워서비스시간병목해결로취급하지않는다.
- **다음:** 아래opt1의CPU후보를검증하고PL준비/정수출력후처리비용도별도정확성검사와함께줄인다.

### S2b-opt1 / float FFT·측정 계획·A9/LTO CPU 후보

- **질문/가설:** 유효부하에서worker중앙값PS14.46/PL22.21ms가12.8ms입력보다길다.
  PSdouble ESTIMATE를float/NEON계획으로바꾸고CPU빌드를최적화해작업시간을줄일수있는가.
- **변경:** `stream_pipeline.hpp`의명시`FFT128_SINGLE`로float FFTW를선택하고double기본값은유지한다.
  FFTW정렬버퍼를사용하며PL의미사용FFTW버퍼는할당하지않는다. `--measure-plan`은2초계획시간힌트를주고
  warmup/READY전에실행한다. `--require-neon`은실제Linuxplan문자열의NEON을확인하고없으면실패한다.
  계획과precision/NEON여부를별도파일/환경에남긴다. PS의창입력은float로반올림되나power/CA는double이다.
- **빌드/범위:** `build_s2a.sh`의선택변수`S2A_PRECISION=float S2A_TUNED=1`은O3/LTO·ARM A9/NEON/hardfloat를사용한다.
  fast-math는없다.기존double/O2기본값은유지한다. 정밀도·정렬·계획·컴파일을함께바꾼후보이며효과를NEON하나에귀속하지않는다.
  PL100MHz/Q15양자화·wire·큐·CFAR조건은그대로다.선택float정밀도는PS FFT에만사용된다.
- **PC 검증:** portable검사11개통과: 정수6구성/double6구성/float6구성×ESTIMATE·MEASURE,
  전FFT bin/power오차·검출목록·wire재정렬/중복/오류·timestamp·NEON필수거부·sender/trace검사를포함한다.
  float상대L2<2e-6·최대complex오차/피크<2e-6·power상대L2<5e-6이며6개float입력모델검출목록은원래double모델과도같다.
  PC는x86DLL이며ARM/NEON성능근거가아니다. 초기PC검사에서진단문자열해제방식문제를잡아수정한뒤전부통과했으며
  통과전보드배포는없었다. 당시소스/런타임SHA와검사로그를[opt1보고서](../benchmarks/reports/2026-11-26-s2b-opt1/README.md)에보존했다.
- **실행준비:** `prepare_s2b_opt1.sh`는새label경로에서tuned double host3스모크→float ARM빌드→기존검증NEON라이브러리SHA검사→
  새NFS6파일번들배포를수행한다. 큰로그는파일로저장한다. `run_s2b_opt1.sh`는두CPU허용·artifact/NEON검사와
  전후boot/CPU·DT클럭/IRQ·runtime SHA·실제receiver종료값을보존한다. 출력원본은새container의`trace/`에있다.
- **현재결과/다음:** PC검사·shell문법통과, 소스6개공유반영완료. Ubuntu host스모크/ARM빌드·보드NEON·정확성/성능은미검증이다.
  Ubuntu `bash tools/detection/prepare_s2b_opt1.sh 20261126_01` 이후새PS92201 spin12.8ms/200을검증한다.
  보드재프로그램/기존결과덮어쓰기는없으며후보성공이나최대처리량을미리주장하지않는다.

## E14-clock — 최대 동작 클럭 탐색과 비교 준비

- **날짜·선행:** 2026-11-26, E14-frame·S2a-rxfix1. 사용자가 CPU/FPGA 최대 클럭 비교를 요청해 S2b 전에 우선한다.
- **질문·관찰:** CPU는 현재 설정약667MHz인데 PL은50MHz 고정이다. 기존 E14 routed WNS10.166ns는
  여유의 근거지만 새100MHz 구현·보드 동작을 보장하지 않는다. 현재 비교는50MHz 조건의 결과로 유지한다.
- **현재 CPU 근거(사용자 콘솔):** ARM PLL`0x00028000`, CPU제어`0x1F000200`, PLL상태`0x0000003F`.
  DT기준클럭 octal`001 374 240 125`=33,333,333Hz. 배수40/분주2로 설정666,666,660Hz다.
  별도 주파수 카운터 실측이 아니며 과거 회차를 소급 확정하지 않는다. debugfs 경로가 없어 조회가 안 됐고
  BusyBox의`od -An -t x1` 미지원 후`od -b`로 확인했다.
- **가설·통제:** 같은 E14 RTL·Q15·전용7단계·행렬RAM·ABI8·HP0·DMA·ARM 실행 파일을 유지하고,
  MMCM 출력과 연결된 FFT/AXI/DMA 클럭만 올린다. PS 설정은 약667MHz·CPU0로 유지한다.
  FIFO/연산 구조나 입력 준비 최적화를 섞지 않는다. 첫100MHz 뒤 통과/실패 상하 경계를 탐색한다.
- **변경:** `build_dma_frame.tcl`의 기본50MHz는 유지하고 명시 후보만 별도프로젝트/latest로 분리했다.
  새`build_dma_frame_clock.tcl`, `tools/clock/build_e14_clock.sh`와`validate_clock.py`는
  routed setup/hold/pulse·미제약경로·생성클럭·reset·구조·신원을 확인하고 실패를 보존한다.
  새 번들 도구는 검증된 기존ARM 바이너리를 재사용하고 주파수가 일치하는 DT overlay를 offline 병합 검사한다.
  배포는 새 경로, 활성화는 기존 모듈이 없는 새 부팅이다. 아직 실제 배포/활성화를 하지 않았다.
  profile/run 스크립트와 분석기는 주파수를 명시해 읽으며 기존50MHz 기본 검사는 유지한다.
- **PC 검증:** 클럭 도구7검사 PASS(기존실제50MHz 타이밍/오류 주입·잘못된주파수·미제약경로·
  명시100MHz 사이클환산·Tcl입력/오류정리·실제Tcl JSON주파수 치환).
  기존 E14 C export/보존식/번들/분석기10검사 PASS. shell5파일 문법 및`git diff --check` PASS.
  테스트의100MHz 변형 데이터는 오류 검사용이며 새로운 하드웨어 측정으로 사용하지 않는다.
- **현재 결과·제한:** PC 준비 완료. 이 Windows 환경에는 Vivado 실행 파일이 없으며,
  새 주파수 Vivado·보드 자체검사·CFAR·paired·연속 FPS 원본은 아직 없다. 최대클럭/가속비를 선언하지 않는다.
- **다음 명령:** Ubuntu 공유소스에서`bash tools/clock/build_e14_clock.sh 100`.
  후보가 통과해도 상한 탐색 후 보드 정확성·장시간 검증이 필요하다. offline paired와 S2b/S2c
  전체 UDP→FFT→CFAR→출력의 지연·드랍·최대지속FPS를 구분하고 둘 다 비교한다.
- **근거:** [E14-clock 보고서](../benchmarks/reports/2026-11-26-e14-clock/README.md),
  [실행 절차](../tools/clock/README.md). 큰 프로젝트/bitstream은 후보별 ignored`build/`에 보존한다.

### E14-clock / 100MHz 첫 후보 실제 빌드 후속

- Ubuntu run:`fft128_dma_e14_clock_100p000mhz_20261126_092439_245`, Vivado 종료0.
  생성 클럭10ns/100MHz, routed setup WNS0.726ns/hold WHS0.023ns/pulse WPWS2.000ns,
  setup·hold·pulse 실패0, 미제약 내부경로0, 생성 reset/lock-loss simulation PASS.
- 사용자 콘솔의 PASS에 더해 공유폴더 원본을 독립 읽어 timing/config·artifact11개
  (bitstream/XSA 포함)·소스14개 SHA를 재계산했다. 저장된`clock_validation.json`과 완전히 같다.
  빌드 당시 launcher/검증기 사본도 보존했다. 보드 활성화/정확성/처리량 검증은 아직 없다.
- [100MHz 원본·독립 검증](../benchmarks/reports/2026-11-26-e14-clock/100mhz_092439/independent_readback.json).
  다음 후보는125MHz다.100MHz를 최대 클럭으로 확정하지 않는다.

### E14-clock / 125MHz 후보 타이밍 실패 후속

- Ubuntu run:`fft128_dma_e14_clock_125p000mhz_20261126_093810_96`, Vivado 종료1.
  생성 클럭8ns/125MHz에서setup WNS−0.727ns/TNS−87.975ns/실패321 endpoint다.
  hold WHS0.052ns와pulse WPWS2.000ns는통과했다. `finish_build`의타이밍검사에서 중단해bitstream이 없다.
- 공유 원본 timing/error/request를 독립 읽고 소스14개SHA를 대조했다.
  [실패 원본·검증](../benchmarks/reports/2026-11-26-e14-clock/125mhz_093810/independent_readback.json)을
  보존했다. 이 후보는배포하지 않는다.100MHz 통과/125MHz 실패 사이의112.5MHz를다음후보로 정한다.
  이 경계는현재구현전략에서의탐색결과이며보드최대동작클럭의확정이아니다.

### E14-clock / 사용자 결정:100MHz 비교 구성 선택

- 사용자가100MHz로진행하도록지시해추가클럭탐색을중단했다.112.5MHz후보는실행하지않는다.
  100MHz를선택한동작클럭으로기록하며최대클럭으로확정하지않는다.100PASS/125실패원본은보존한다.
- 이미검증한`fft128_dma_e14_clock_100p000mhz_20261126_092439_245`를재사용한다.
  `prepare_e14_100.sh`는번들검사·새NFS경로배포를수행하고상세출력은로그파일에저장한다.
  FPGA프로그래밍이나재부팅을자동실행하지않는다.새보드부팅후자체검사→profile/paired→S2b/S2c순서다.
- CPU약667MHz/CPU0, PL100MHz로비교하며기존RTL·정밀도·ARM바이너리를유지한다.
  현재보드100MHz정확성·성능결과는아직없다.보드실행후원본을수집해검증한다.

### E14-clock / 100MHz 보드 자체 검사 사용자 콘솔 PASS

- 새 부팅 후 `/opt/fft128/e14_clock_100000000_20261126_095418/load_board.sh` 실행 결과,
  FPGA Manager 로드·DMA 등록·ABI8 E14 client 준비 및 자체 검사 PASS를 사용자 콘솔에서 확인했다.
  client4회 각각16,384 bin 일치, 계측3회 matrix overwrite 오류0,
  phase cycles17788/17771/16385,17789/17771/16385,17786/17771/16385다.
  수신기 자체 검사는4프레임/65,536 bin 일치다. 이 자체 검사 값을 성능 지연으로 사용하지 않는다.
- [콘솔 원문 발췌·확인 범위](../benchmarks/reports/2026-11-26-e14-clock/board_selftest.json)를 보존했다.
  완전한 보드 raw log·boot ID·재부팅 후 CPU 주파수는 아직 회수하지 않았다.
  앞서 공유 번들30개 SHA와 DTBO/병합 DT의100MHz 선언을 독립 확인했으며 ARM 수신기·모듈 SHA는 기존과 같다.
- 다음은 새 `compare_100mhz_01` 디렉터리에서 CPU PLL·분주·DT 기준 클럭·boot ID를 전후 기록하고,
  별도20회 profile 및 PS double/NEON/PL 각300회(3×100) paired를 수행한다.
  기존 원본을 덮어쓰지 않으며, 상세 출력은 파일로 보존한다. 이후 원본을 수집해 독립 검증한다.

### E14-clock / profile·paired 실행 완료 콘솔 확인

- `compare_100mhz_01/profile`에서20회 profile 완료, PL 경로 mean1.154095ms/median1.146114ms,
  min1.130040ms/max1.230546ms 및16,384 bin 일치를 사용자 콘솔에서 확인했다.
  `compare_100mhz_01/paired`의 benchmark 완료 marker와 마지막PS100회 수치 검증도 표시됐다.
- [콘솔 수치](../benchmarks/reports/2026-11-26-e14-clock/measurement_console.json)를 보존했다.
  아직 raw CSV·CPU 클럭 전후·boot ID를 회수하지 않았다. profile 중앙값을 비계측 paired 값으로 쓰지 않으며
  전체300회 PS/NEON/PL 통계·가속비는 원본 검증 후 확정한다. 연속 UDP 처리량은 별도다.
- Ubuntu에서 `bash tools/clock/collect_e14_100.sh`로 원본을 새 공유 `build/` 디렉터리에 수집한다.
  이후 CPU 클럭/boot·artifact·반복별 정수/부동소수점 정확성·IRQ·profile 중복 구간을 독립 검증한다.

### E14-clock / 100MHz 원본83개 독립 검증 완료

- **원본:** 공유 수집 `build/e14_clock_100_results_20261126_100907`을 로컬 ignored`build/`에 복제하고
  원본83개/9,268,101byte의 SHA를 대조했다. 작은 원본69개/447,556byte와 전체83개 SHA를
  [보고서](../benchmarks/reports/2026-11-26-e14-clock/README.md)에 보존했다. 큰 spectrum/input CSV는 ignored`build/`에 있다.
- **조건:** 같은128×128 Q15 입력, 창 없음,1/16384 정규화, CPU0, warmup10·100회×3회차 순서 회전.
  FFT 두 축·사용자/커널 복사·DMA·IRQ 대기·PL 전치/최종 배열 복원 포함.
  입력I/O·양자화·할당·FFTW 계획·반복 검증·파일 출력·UDP·CFAR는 제외한다.
- **비계측 각300회 중앙값:** double5.631855ms / float+NEON3.563415ms / PL1.124817ms.
  같은 회차 double/PL5.006908배, NEON/PL3.167995배이며 NEON 대비 지연68.434297% 감소다.
- **전후 CPU·부팅:** 기준33,333,333Hz·ARM PLL40·CPU분주2 =666,666,660Hz 설정이 같다.
  boot ID`87d0bd24-5ffa-435e-8919-fee083d76b6f`가 clock/profile/paired에서 같다.
  CPU 주파수 카운터 실측은 아니다. PL100MHz는 타이밍·선택한 번들 및 DT 선언으로 확인했다.
- **정확성·신원:** PL은 매 반복16,384 bin C 정수 모델 일치, 저장된3개 전체 출력도 독립Python 정수 모델과 같다.
  PS double/NEON은 각 반복·저장 출력의 NumPy 허용오차 검사를 통과했다. PL의 float 대비 상대L2 오차약1.361%는 기존Q15와 같다.
  번들30개 SHA가 host/load/profile/paired에서 같고 PL14·host12·module3 소스가 공유 원시 SHA와 같다.
  paired IRQ67/68 각각CPU0 330/CPU1 0, profile은각CPU0 22/CPU1 0이다.
- **별도20회 profile:** mean전체1.1540949ms, median1.146114ms, PL active평균0.5194385ms.
  모든 matrix/7단계 issue·retire/phase cycle 보존식·overwrite0·CPU전치0·100MHz 시간 환산을 검증했다.
  kernel wait와PL active는ioctl에 포함되므로 호스트 단계에 더하지 않는다.
  비계측 PL JSON의`pl_clock_hz_declared:0`은 사이클 환산을 사용하지 않았다는 표시이며,
  비계측 지연은 wall clock으로 측정했다. 실제 비교 구성은 검증한100MHz 번들/DT로 확인한다.
- **해석:** 과거50MHz PL1.657914ms 대비 이번 값은 관측상1.473941배/32.154684% 감소다.
  회차·boot가 다르고 과거 CPU 클럭 원본이 없어 클럭만 바꾼 같은 회차 A/B 효과라고 단정하지 않는다.
  현재100MHz paired의 PS/PL 비교는 같은 회차·CPU 클럭에서 확인했다.
- **다음:**100MHz를 유지해 S2b/S2c의 UDP→FFT→CFAR→출력 연속 검증을 진행한다.
  이 offline 결과로 지속FPS·드랍0·12.8ms P99 합격을 주장하지 않는다. stream PS는 double FFTW이며 offline NEON과 구분한다.

---

## S2a-int16 — ADC 모사 정수 입력 경계

- **질문/결정:** 실제 ADC 출력에서 연산 분담을 비교하기 위해 시스템 경계를 고정 스케일 int16 IQ로 옮긴다.
  ADC 모사는 송신 이전 외부 작업, Hann·PS int16→double·PL 정수 창/패킹·DMA·CFAR는 시스템 내부다.
  프레임 최대값 정규화는 없앤다. 기존 float 실험과 실행 파일은 보존한다.
- **기본 profile1:** ADC16비트, S=1,600,000 codes/unit, gain 고정, 최근접 짝수 반올림 후[-32768,32767]포화.
  네 기존 fixture의 최대 복소 진폭0.009593515132970855를 사전 calibration 근거로 삼아 약6.59dB 여유를 둔다.
  이는 매 프레임 gain 재계산이 아니다. 설정 잡음 complex RMS0.00179는입력2864LSB, 성분별표준편차약2025LSB에대응한다.
  위값은입력/모델계산이며보드시간측정이아니다.16비트는저장/E14폭과같아추가시프트가필요없고스케일스윕은분리한다.
- **수치/ABI 확인:** E14 ABI8의word는real하위16/imag상위16 signed two's complement다.
  twiddle은Q15, butterfly의전체정수곱/합을산술우측16비트시프트해단계별/2·음수floor·signed16포화한다.
  두축각7단계로총1/16384다. ADC code를추가시프트없이E14 code에대응시키고PS도1/16384로정규화한다.
  PL정수Hann은Q15계수의2D Q30곱에최근접짝수반올림을한번적용한다. Python 정수모델로별도검증한다.
- **함께 바뀐 요인:** payload128KiB→64KiB, protocol/수신 조립·raw버퍼 크기, 고정ADC스케일,
  PL정수Hann, prepare내backend문자열분기밖으로이동. 경계변경하나만의성능효과로귀속하지않는다.
  기본double/O2를사용해보드미실행opt1 NEON후보와분리하고queue4/partial4는유지한다.
  작업본에 이미 있던 FFTW 정렬 버퍼 할당과 PL 미사용 FFTW 버퍼 비할당도 새 바이너리에 포함된다.
  기존 rxfix1 대비 plan/cache/메모리 영향이 있는 추가 혼동 변수이며, float/MEASURE/NEON 강제/O3·LTO는 끈다.
  실제 PS 계획은 `fftw_plan.txt`로 보존한다.
- **검증 순서:** PC fixture/프로토콜/전bin정수모델·CA/±1bin·오검출/약표적비교 → Ubuntu host스모크/ARM빌드 →
  사용자보드PS/PL50ms/20진단원본독립검증 → 진단끔12.8ms/200 →10,000프레임S2b.
  준비단계시간은PS/PL각각보고한다. 현재새조건보드측정은없다.
- **소스 보존:** 변경전float/opt1작업본은ignored`build/pre_adc_float_20261126`에SHA와함께복제했다.
  `git pull --ff-only`로5b5123f에갱신하고README로컬변경을백업/병합해보존했다.커밋/푸시는하지않았다.
- **PC 결과:** 새 기록4개 모두 클리핑0이다. ADC PS double과 PL 정수 모델의 잡음 포함6개 조합에서
  전16384 complex bin과 CA-CFAR를 독립 NumPy/Python 모델로 비교해 통과했다. 검출 bin은 원본 float와 전부 같다.
  single은1/1·오검출0, multi4 none은4/4·오검출1/Hann은4/4·오검출0,
  close_weak는none/Hann 모두 기존1/3·오검출0을 유지한다. 약표적 문제를 해결했다고 해석하지 않는다.
  int16 전용13개·기존 float 회귀11개가 통과했으며, 공유 폴더의 사용자 변경 테스트를 보존한 채
  공유본 int16 13개 검사도 통과했다. PC 바이너리는 `build/adc16_pc_20261126_final/binaries`에 두고 SHA를 보고서에 기록했다.
- **실행 준비/제한:** 공유 소스29개를 백업/SHA 확인 후 반영했다. Ubuntu의 `prepare_adc16.sh`는
  host float/ADC 스모크 → ARM double/O2 빌드 → 새 NFS 번들 배포를 수행한다. 사용자 실행 결과 대기다.
  보드 PS/PL20프레임의 첫 프레임 전bin과 전체 검출·시간·카운터를 원본으로 검산하는 checker 및
  진단을 끈200프레임 예비 명령을 [실행 문서](adc16_runbook.md)에 준비했다.
  보드 준비 시간은 미측정이며 Windows PC 검사로 Linux/ARM 빌드 성공이나 보드 성능을 주장하지 않는다.
- **근거:** [새 보고서](../benchmarks/reports/2026-11-26-s2a-int16/README.md). 후속 원본/검증결과를여기에연결한다.
- **Ubuntu 빌드 후속 검증(동일 ID):** 사용자 `ADC16_DEPLOY_READY` 콘솔을 확인한 뒤 공유 원본을
  `build/s2a_int16_ubuntu_20261126_adc01`에 회수했다. float/model·PS·손실 스모크3개와
  ADC/model·PS·손실 스모크3개를 독립 재검산했다. 정상 ADC 두 실행은20/20·검출4/4·오검출0,
  첫 프레임16384 complex bin 일치이며 의도 손실은19처리/1partial로 기록됐다.
  소스19개 SHA, 번들5개 SHA, host x86-64 ELF와 ARM32 ELF, double/O2 설정을 확인했다.
  ARM 바이너리 SHA는 `72396cb0c1abcf6f831d5d00a0fc7d75618c2e8333d2ff99402b3163ca8d28f0`이다.
  `/opt/fft128/s2a_int16_20261126_adc01` 배포는 사용자 콘솔 증거이며 보드에서의 실행·정확도·준비 시간은 아직 미측정이다.
  [Ubuntu 원본 독립 검증](../benchmarks/reports/2026-11-26-s2a-int16/ubuntu_build_validation.json).
- **보드 PS 진단 사용자 콘솔(92301):** 새 ADC 번들 `ps_diag_01`에서20/20처리·exit0,
  실제 패킷568바이트·flags0·run92301/frame1을 보고했다. 옛 control-buffer probe의flags8은
  진단용MSG_PEEK 결과이며 실제 수신 오류로 계산하지 않는다. 송신 JSON 원본을 회수해
  v3/profile1·동일 입력SHA·20프레임·프레임당72704바이트·overrun0을 확인했다.
  수신 원본은 아직 공유 폴더에 회수되지 않아 보드 정확도·전bin·오류카운터·prepare 시간은 미검증이다.
  함께 붙여 넣은92122/92123 콘솔은 과거 float 조건이며 새 ADC 결과에 포함하지 않는다.
- **보드 원본 독립 검증 완료(92301/92302):** 공유 폴더 회수본을
  `build/s2a_int16_board_diag_20261126_adc01`에 원본SHA 확인 후 복사했다. 같은 ARM 바이너리·소스19개·번들5개,
  ADC16/profile1/S=1,600,000·Hann·warmup10·queue4/partial4·두CPU허용·50ms/20·spin 조건을 확인했다.
  양쪽 모두2560패킷/20처리·드랍0·전체 오류카운터0·exit0이고,20프레임 각각 표적4/4·오검출0이다.
  첫 프레임16384 complex bin은PS double NumPy 허용오차 내, PL은 독립 정수 Hann/FFT 모델과 bit-exact다.
  모든 프레임의 검출 bin·power·threshold도 독립 CA 기준과 일치한다. 송신 overrun0·유효부하도 확인했다.
  CPU 설정666,666,660Hz와 PL DT선언100MHz·boot ID가 양 실행 전후에 같고 이전100MHz 검증 세션과 같다.
  주파수 카운터에 의한 실측이나 최대 클럭 확인은 아니다.
- **새 보드 진단 시간(ms, 중앙값 / P99):** prepare PS0.556071/0.58497822, PL2.460540/2.68009422;
  FFT/전송 PS5.259570/5.38718490, PL1.197597/1.25885730;
  power+CFAR PS5.095404/5.16172632, PL6.098832/6.20870952;
  조립완료→출력 PS11.243868/11.38683954, PL10.086009/10.17951474;
  첫커널패킷→출력 PS15.873876/24.20294763, PL14.696664/16.88978187.
  출력은프레임별CSV flush이며fsync없음. 진단 spectrum 복사는출력시각뒤·CSV저장은종료후지만 후속프레임에영향을줄수있다.
  옛 float 진단/200프레임은 보존하고 입력폭·창수치·정규화·buffer/분기·FFTW정렬·affinity/clock 차이를 함께 고려한다.
  이20프레임으로 최대FPS나12.8ms/10,000 합격을 주장하지 않는다. 다음200프레임은진단끔·동일queue/partial로실행한다.
  [보드 원본 검증](../benchmarks/reports/2026-11-26-s2a-int16/board_diag_validation.json),
  [클럭 설정 문맥](../benchmarks/reports/2026-11-26-s2a-int16/board_clock_context.json).
  후속 연속 처리 예비 검사는 [S2b-int16](#s2b-int16--adc-입력-연속-처리-예비-검사)에 기록한다.

## S2b-int16 — ADC 입력 연속 처리 예비 검사

- **질문:** S2a-int16 번들 그대로(처리 로직·RTL·드라이버 변경 없음) 12.8ms 주기에서 드랍0과
  첫 커널 패킷→CSV flush P99<주기를 PS/PL 각각 유지하는가. 200프레임 예비이며 합격 판정 실행이 아니다.
- **조건:** 바이너리SHA `72396cb0…28f0`(artifact_check 5개 OK), 입력SHA `d3d5160c…b6b91cf`,
  ADC16/profile1/S=1,600,000·Hann 수신기 내부·warmup10·queue4/partial4·CPU0-1·`--cpu0` 없음, wrapper measure 모드
  (probe·spectrum 진단 끔). PS double/O2/ESTIMATE, PL E14 ABI8·100MHz 번들. 송신 12.8ms·spin·chirp gap0.
  clock_before/after가 S2a-int16 진단과 바이트 동일(같은 boot ID, 설정값 문맥이며 주파수 실측 아님).
- **실행:** PS `run_board.sh ps 92311 200 $B/ps_prelim_01 measure`, PL `… pl 92312 200 $B/pl_prelim_01 measure`,
  각 sender `--run-id 9231x --frames 200 --period-ms 12.8 --wait-mode spin`. 사용자 보드 실행·회수 후
  Windows `build/s2a_int16_board_prelim_20261126_adc01`(공유본과 diff 동일)에서 `check_adc16_stream.py`로 독립 재계산했다
  (PS는 `--allow-loss`, zero_drops=false 보존).
- **결과(보드 원본):**
  PS92311 — exit2, 194/200 처리, queue_full6(69,92,114,133,153,179), 패킷25600·오류카운터 전부0,
  송신overrun1·최대지연5.042ms(offered_load_valid=false), 처리194프레임 4/4·오검출0. 큐 깊이3이146회,
  큐대기 중앙/P99 43.530/53.119ms, 첫커널패킷→출력 중앙/P99 61.575/**71.097ms**.
  prepare0.556/2.835, FFT6.162/7.900, power+CFAR5.077/7.799 (중앙/P99 ms). CPU 활성 중앙136%(한 코어 기준), RSS최대5.21MiB.
  PL92312 — exit0, 200/200, 패킷25600·오류0, overrun0·최대지연0.008ms, 4/4·오검출0, 큐깊이 항상0,
  큐대기 중앙/P99 0.099/1.535ms, 첫커널패킷→출력 중앙/P99 17.235/**19.135ms**(200프레임 전부>12.8ms),
  조립완료→출력P99 14.024ms. prepare2.423/2.505, FFT/전송1.214/1.381, power+CFAR **8.368**/9.103ms. CPU 중앙127%, RSS3.90MiB.
- **판정:** PS 12.8ms 불합격(드랍·큐 포화·지연 누적, 송신 overrun1도 존재). PL 12.8ms는 처리량은 유지했지만
  지연 기준 불합격. 12.8ms/10,000 본검사(92321/92322 예약)는 실행하지 않는다. 200프레임 결과로 최대FPS를 추정하지 않는다.
- **관찰/가설(미검증):** PL power+CFAR가 50ms 진단보다 약2.27ms 길다. 199프레임은 CFAR 구간이 다음 프레임 수신과 겹쳤고
  (중앙8.369ms), 겹치지 않은1프레임은6.033ms다. PS도 겹침83/비겹침111프레임 중앙7.367/5.014ms다.
  수신 스레드와의 CPU/메모리 경합 가설이며 원인 확인 전에는 처리 로직을 바꾸지 않는다.
  지연에는 첫패킷→조립완료 약4.75ms(송신 burst)가 포함된다. 경합이 적은 50ms 진단 P99(PS24.203/PL16.890ms)는
  그보다 짧은 주기의 합격이 불가능하다는 하한으로만 사용한다.
- **다음:** 같은 번들·queue4/partial4·measure 모드로 경로별 주기를 늘린 새 ID 200프레임 예비 검사 후,
  유효 구간에서10,000프레임 본검사.
- **근거:** [보고서](../benchmarks/reports/2026-11-26-s2b-int16/README.md),
  [PS 검증](../benchmarks/reports/2026-11-26-s2b-int16/ps_prelim_01_verified.json),
  [PL 검증](../benchmarks/reports/2026-11-26-s2b-int16/pl_prelim_01_verified.json),
  [보조 분석](../benchmarks/reports/2026-11-26-s2b-int16/prelim_supplement.json).
- **새 기준 병기(같은 원본, 재측정 아님):** 조립완료→출력P99는 PS66.415ms·PL14.024ms로 12.8ms에 둘 다 미달이다.
  기준 변경 후속은 [S2b-pace](#s2b-pace--실제-chirp-간격-송신과-조립완료-기준)에 기록한다.

## S2b-pace — 실제 chirp 간격 송신과 조립완료 기준

- **결정(사용자, 11-26):** 12.8ms는 시뮬레이터 획득 주기(128×PRP100µs)다. 실제 획득에서는 첫 패킷 기준 지연이
  정의상 주기를 넘으므로 실시간 판정을 **P99(조립완료→CSV flush)<주기**로 바꾸고, 송신도 chirp 간격100µs로 바꾼다.
  드랍0·오류0·정확도·큐 안정·유효 부하는 유지, 첫 커널 패킷→출력은 보조 지표다.
  시작점 `complete_ns`는 수신기 사용자 공간의 마지막 chirp 조립 직후 시각이며 마지막 패킷 커널 시각이 아니다.
- **변경 전 관찰:** 기존 송신기에도 `--chirp-gap-us`가 있었지만 프레임별 첫/마지막 송신 시각만 기록해 chirp 간격을 검증할 수 없었다.
  VM에서 패킷 없는 spin 대기 지각은 최대10.4µs(S2b), burst 실제 송신은 chirp당 약37µs(92312 첫패킷→조립완료4.756ms/128)였다.
- **변경:** `tools/sender/replay_stream.py` — gap>0일 때만 새 경로: 패킷을 마감 전에 만들고 `first+i·gap` 절대 마감까지 대기 후
  `sendto` 직전 시각으로 chirp별 지각을 기록한다. 프레임별 최대 지각·한도초과 수·`sendto` 최대 시간,
  전체 중앙/P99/최대·`valid`(한도초과0)를 `chirp_pacing`에 저장한다. `--chirp-late-limit-us`(기본10, 사용자 승인 초기값),
  `--chirp-detail`(chirp별 배열 저장). gap0 burst 경로 코드·JSON 필드는 그대로다.
  `tools/detection/analyze_stream.py` — 간격 송신 JSON에 chirp 증거가 없으면 거절, 한도초과가 있으면 offered_load_valid=false.
  `tools/detection/check_adc16_stream.py` — `realtime_criterion`(조립완료 기준 P99·판정, 첫패킷 기준 보조)과 sender 요약을 출력.
  수신기·RTL·드라이버·처리 로직 변경 없음. 기존 overrun 정의(마지막 송신≥시작예정+주기)는 유지하며 간격 송신에서는 여유가 약0.1ms다.
- **소스 SHA:** 변경 전 `replay_stream.py` `798375e7…fd11e`(92311/92312 송신과 동일), analyze_stream `60c286eb…d11e`,
  check_adc16_stream `967ad9f9…f93d618`; 변경 후 `f3806e43…0a37`, `a353d532…b9`, `9aaf70ab…c88`, test_check_pacing `a1877f55…c488`.
  변경 전 사본은 ignored `build/sender_chirp_pace_pre_20261126`, 공유 폴더 이전본은 공유 `build/sender_chirp_pace_backup_20261126`.
- **PC 검사(Windows, 타이밍 주장 아님):** `test_check_pacing` 10개 통과(신규 4: burst JSON 불변, 간격 송신 chirp별 기록·순서·
  절대 마감, drop-frame·한도 검증, 한도 초과 시 invalid). 92311/92312 원본에 새 checker를 다시 적용해 이전 지표와 같고
  기준 필드가 PS66.415/PL14.024ms·미달로 나오는 것을 확인했다. `test_adc16`/`test_s2a`의 model/C++ 파이프라인 13개는
  이 PC 세션에서 네이티브 프로그램이0xC0000005로 종료해 실패했으며, 변경 전 Python 원본으로도 같은 실패가 재현되어
  이번 변경과 무관한 환경 문제로 분리한다(원인 미확인, 이전 13/11 통과 기록은 유지).
- **다음:** Ubuntu에서 수신기 없이 100µs 간격 송신 probe(92330) → 유효하면 보드 PS92331/PL92332 12.8ms/200 간격 송신 예비.
  VM 가상 NIC의 묶음 송신 여부는 송신 측 기록으로 알 수 없으며 보드 첫패킷→조립완료(기대 약12.7ms)로만 간접 확인한다.
- **Probe 92330 (사용자 Ubuntu 콘솔 + 송신 JSON 회수, 수신기 없음):** Ubuntu `test_check_pacing` 10개 통과, 송신기SHA `f3806e43…0a37` 일치.
  12.8ms/200·간격100µs·spin에서 chirp 지각 중앙0.141/P99 4.141/P99.9 160.8/최대713.3µs, 10µs 이상151/25,600 chirp(58프레임),
  지연 사건111건 중100µs 이상8건(최대0.713ms), `sendto` 최대0.621ms, overrun1(프레임83), 프레임 송신 길이 중앙12.707ms.
  **valid=false**이므로 보드 92331/92332는 실행하지 않는다. 원인(vCPU 선점/커널·가상NIC)은 미확인이며 송신 측 기록만으로 선로 간격은 알 수 없다.
  [probe 보고서](../benchmarks/reports/2026-11-26-s2b-pace/README.md).
- **Probe 92335 (CPU3 고정+SCHED_FIFO50, 사용자 콘솔+JSON 회수):** chirp P99 4.69µs로 비슷하지만 프레임135에서 36.9ms 단일 정지,
  이후 따라잡기로 overrun66·프레임 시작 지각 최대31.92ms. RT throttling 가설(미확인). 부하 왜곡이 커서 이 설정은 폐기한다.
- **유효 규칙 변경(사용자 승인 11-26):** 초기 규칙은 짧은 VM 정지까지 무효로 처리해 실제 지터를 반영하지 못했다. 새 규칙은
  chirp 지터 P99(프레임 첫 송신 기준) < 10µs, 총 지각 최대(프레임 시작 지각+chirp 지각) < 주기10%, 프레임 시작 지각 < 주기10%다.
  간격 송신에서 프레임 경계 overrun(마지막 송신≥다음 프레임 예정)은 여유가 약0.1ms라 판정에서 빼고 보고만 한다.
  burst 송신 판정(overrun0·시작지각<10%)은 그대로다. 100µs 이상 chirp 수·P99.9·`sendto` 최대도 보고한다.
  변경: `replay_stream.py` `--chirp-late-limit-us`→`--chirp-late-p99-limit-us`(기본10), 프레임별 `chirp_late_total_max_ns`·
  `chirp_late_ge_100us`, 요약 `late_p99_9_ms`·`late_total_max_ms`·`frame_boundary_overruns`·`rule`; `analyze_stream.py` 간격 송신 판정 교체.
  SHA: replay_stream `8ccccc52…5ce0`(직전 `f3806e43` 사본은 `build/sender_chirp_pace_pre_20261126/replay_stream_f3806e43.py`),
  analyze_stream `410cdcce…4f4e`, test_check_pacing `fb3123c8…b210`, check_adc16_stream `9aaf70ab…c88`(변경 없음).
  공유 폴더 직전본은 공유 `build/sender_chirp_pace_backup2_20261126`. PC `test_check_pacing` 11개 통과(신규: 3ms 인위 정지 무효),
  analyze_stream 간격 판정 분기(증거 없음/구형식 거절, overrun만 있음 유효, 1.3ms 정지·P99 12µs 무효, burst 불변)를 PL92312 trace 사본으로 확인.
  기존 probe 재판정(Windows, chirp 배열에서 재계산): 92330 P99 4.141µs·총최대0.713ms → **유효**, 92335 총최대36.94ms → 무효
  ([재판정](../benchmarks/reports/2026-11-26-s2b-pace/probe_rejudge_new_rule.json)). 두 probe 원본 JSON은 이전 규칙 필드를 그대로 보존한다.
  200프레임 probe 결과이며 10,000프레임에서 더 큰 정지가 나오면 그 실행은 무효로 남긴다.
- **보드 예비 PS92331/PL92332 (12.8ms/200·간격100µs, 보드 원본 독립 검산):** 수신기 SHA·clock 문맥 동일, 패킷25600·오류0·처리분4/4·오검출0.
  **송신 부하는 둘 다 무효**(지터P99 13.25/30.87µs, 총지각최대1.722/1.895ms)라 합격 판정에 쓰지 않는다. 수신기 없는 probe92330만 유효였다.
  첫커널패킷→조립완료 중앙12.871/12.876ms로 간격 송신이 보드 도착에 반영됐다(burst 4.75ms; VM 대규모 묶음 없음의 간접 증거).
  PS: exit2·161/200(queue_full39)·큐깊이3 137회, 조립완료→출력P99 87.08ms. 처리 합계 중앙 약16.9ms(prepare0.847·FFT8.086·CFAR7.591)로
  burst(FFT6.162·CFAR5.077)보다 길다 — 주기 내내 수신/IRQ가 CPU를 나눠 쓴다는 가설(미확인). PS는 12.8ms 간격 송신에서 처리량 부족.
  PL: exit0·200/200, 조립완료→출력 중앙10.946/P99 20.812ms. 정상 구간(1~15, 84~200) 중앙10.75/10.84ms(CFAR6.45~6.49ms, burst 8.37보다 짧음).
  프레임16~83에서 prepare2.52→3.11·CFAR6.45→7.99ms(약24%↑, FFT/DMA 불변)로 처리 합계가 주기를 넘어 큐가 최대7.96ms 쌓였다가 회복했다.
  12.8ms 이상 66프레임이 모두 이 구간이며 송신 정지 프레임·타 프로세스 CPU와 일치하지 않는다. 원인 미확인.
  [보고서](../benchmarks/reports/2026-11-26-s2b-pace/README.md), [보조 분석](../benchmarks/reports/2026-11-26-s2b-pace/pace_prelim_supplement.json).
- **PL 재실행 92336 (동일 조건, 보드 원본 독립 검산):** 송신 부하 **유효**(지터P99 6.16µs·총지각최대0.666ms). exit2·182/200(queue_full18, 약8프레임 간격),
  오류0·4/4·오검출0, 조립완료→출력P99 **73.11ms** → PL 12.8ms 간격 송신 **불합격(200프레임 예비)**.
  프레임1~27 중앙 prepare2.544·FFT1.433·CFAR6.539·조립완료→출력10.956ms, 프레임28부터 수신 종료까지 3.495·1.731·9.051ms(약1.38/1.21배)로
  처리 합계≈14.3ms>주기, 수신 종료 후 처리된4프레임은 2.424·1.212·6.058ms로 즉시 회복. 92332의16~83 감속(약1.24배)과 같은 유형이다.
  가설(미검증): 미고정 처리 스레드가 수신 스레드/eth0 IRQ(CPU0)·softirq와 같은 CPU를 나눠 쓰는 시간대가 생긴다. 스레드별 CPU 기록이 없어 확인 불가.
  [92336 분석](../benchmarks/reports/2026-11-26-s2b-pace/pace_prelim_02_supplement.json).
- **진단 PL 92337 (스레드 CPU 기록, 진단 전용):** 보드 셸 반복문(약0.19s)으로 `/proc/PID/task/*/stat` processor·utime·stime과 cpu0/1 `/proc/stat` 기록
  (사용자 실행, 원본 회수 SHA `167f24e4…d954`). trace는 `clock_errors=1`로 무효, 송신 지터P99 14.92µs로 부하 무효, 178/200(queue_full22). 성능 판정 제외.
  스레드(소스 생성 순서): main=수신 1171, sampler 1177, worker 1178. worker·수신 스레드가 약0.2s 단위로 CPU를 자주 옮겼다.
  처리 속도는 CFAR≈6.7ms/prepare≈2.6ms와 ≈9.0–9.4/3.5–3.75ms 두 상태로 나뉘었다. 양 끝 샘플 모두 worker CPU1인 2구간은 빠르고,
  모두 CPU0인 1구간은 느렸다(eth0 IRQ·softirq는 CPU0, softirq 비율16–75%). 가설을 부분 지지하지만 샘플이 순간값·소수라 확정 못 함.
  [스레드 정렬](../benchmarks/reports/2026-11-26-s2b-pace/pl_pace_prelim_03_thread_alignment.json).
- **PL 92338 (고정 시도 실패 → 고정 없는 반복):** 보드에 `taskset`이 없어 고정이 적용되지 않았다(사용자 콘솔·기록 회수).
  송신 부하 유효(지터P99 7.54µs·총지각최대0.757ms), 200/200·드랍0·오류0·4/4. 조립완료→출력 중앙13.05/P99 **46.66ms** → 12.8ms 불합격.
  지속 감속(프레임1–5, 53–58, 179–196: prepare≈3.5·FFT≈1.7·CFAR≈9.2, 합계≈14.7ms)과 단발 지연(한 단계가 최대 8.9/5.3/13.7ms)이 겹쳤고,
  정상 상태 합계는≈10.8ms다. 정상 상태만으로는 주기 안이지만 두 현상 때문에 큐가 쌓인다.
- **고정 도구 준비(코드: 진단 도구만, 수신기 불변):** `tools/affinity/pin_tid.c`(sched_setaffinity로 TID별 마스크 설정·재확인 출력)와
  `tools/affinity/build_pin_tid.sh`(Ubuntu host self-test 후 ARM 정적 빌드, 새 NFS 경로 배포). SHA `5c2c303a…cb963`, `c52c9053…72115`.
  Windows에는 Linux 스케줄러 API가 없어 문법 검사만 시도했고(API 미존재 오류만), 실제 빌드·검증은 Ubuntu에서 한다. 다음 진단은 PL 92339.
- **PL 92339 (pin-tid 고정: main·sampler CPU0, worker CPU1; 진단):** Ubuntu 빌드 host self-test 통과, ARM 정적 바이너리 SHA `1a9d19d1…bbd9`,
  보드 기록상 mask 1/1/2 적용, 종료 직전 worker processor=1. 200/200·드랍0·4/4·오검출0, 송신 부하 유효(지터P99 9.89µs·총지각최대0.741ms).
  단 `clock_errors=1`로 exit2·trace 무효(checker 거절; 정확도는 scratch 사본에서 trace 유효성만 무시하고 검산). 판정 불가.
  조립완료→출력 중앙10.84/P99 26.02ms. 20프레임 구간 중앙은 모두 정상 상태(CFAR6.53–6.69ms)로 **지속 감속 상태가 사라졌다**(1회).
  남은 12.8ms 초과46프레임은 단발 지연 뒤 큐 회복 구간이다. 단발 지연 묶음은 92339·92338(보드 셸0.5s 반복 기록 있음)에서 4회씩
  약0.59–0.65s 간격, 92336·92332(반복 없음)에서는0회 → 진단 반복 기록의 부작용 가능성이 높다(기록 시각과 직접 대조는 안 함).
  다음: 같은 고정을 적용하되 반복 기록 없이(고정 직후 스크립트 종료) PL 92340.
- **PL 92340 (pin-tid 고정, 반복 기록 없음; 보드 원본 독립 검산 PASS):** mask 1/1/2 적용(사용자 기록 회수). exit0·200/200·드랍0·카운터 전부0,
  200프레임 4/4·오검출0, 송신 부하 유효(지터P99 5.42µs·총지각최대0.682ms; 보고 100µs이상42·경계overrun2).
  첫커널패킷→조립완료 중앙12.869ms, **조립완료→출력 중앙10.757/P99 10.911/최대11.162ms**(12.8ms 이상 0), 큐대기 P99 0.161ms,
  prepare2.546·FFT1.403·CFAR6.497·flush0.225ms(중앙), CPU 중앙136.7%(한 코어 기준)·RSS3.90MiB. 20프레임 구간 모두 정상 상태.
  **200프레임 예비 기준 새 실시간 조건 충족**(10,000프레임 합격 아님). 92339와 함께 지속 감속=CPU0 공유, 단발 지연=진단 반복 기록이라는
  해석을 지지한다(각1–2회). 스레드 고정은 기존 "고정 없음" 조건과 다르므로 정식 조건 채택·PS 적용은 사용자 결정이다.
  [보고서](../benchmarks/reports/2026-11-26-s2b-pace/README.md).
- **무효 PS 92341 / PL 92342:** 상태 요약과 [보고서](../benchmarks/reports/2026-11-26-s2b-pace/README.md) 참조(미실행·중단).
- **PS 92343 (고정 정식 조건, 12.8ms/200 예비; 보드 원본 독립 검산 PASS):** 수신기 `72396cb0…`, 송신기 `8ccccc52…`, mask 1/1/2.
  송신 유효(지터P99 5.19µs·총지각최대0.705ms). 200/200·카운터0·4/4·오검출0. **조립완료→출력 중앙12.427/P99 12.572/최대12.780ms**,
  prepare0.626·FFT5.929·CFAR5.571·flush0.227ms(중앙), CPU 중앙155.5%·RSS4.88MiB. 예비 충족(10,000 합격 아님, 여유 0.23ms).
- **PL 92344 (고정 정식 조건, 12.8ms/10,000 본검사): 불합격·무효.** exit2, kernel_drops277(=1,280,000−수신1,279,723),
  9992 processed·3 partial·5 partial_evicted, 그 밖의 카운터0·clock 같음. trace 무효라 독립 검산 불가(수신 summary·CSV로 분석).
  송신 무효: 지터P99 42.5µs, chirp 지각 최대34.3ms, 총지각최대122.4ms, 프레임 시작 지각이 쌓여 최대118.4ms
  (chirp128×100µs=12.7ms라 주기 여유0.1ms로 회복 불가). evicted 1370–1376·4048/4049는 송신 chirp 지각13.0·25.9ms 직후이고 partial 5888·8445는 송신 지각이 작다.
  처리분 조립완료→출력 중앙10.910/P99 11.114/최대31.656ms, 12.8 초과45(큐대기≥4ms 28: 정지 뒤 조립 간격 압축, flush≥4ms 3: NFS 출력 가설).
  단계 중앙 prepare2.542·FFT1.423·CFAR6.605ms로 지속 감속 없음. 드랍 원인(송신 몰림/보드 수신 지연)은 선 위 도착 기록이 없어 미확정.
- **송신기 재고정 모드 추가(11-26, 사용자 승인):** `replay_stream.py` `8ccccc52…`→`51ba255c…`(사본 `build/sender_reanchor_pre_20261126/`).
  absolute 경로와 burst 경로는 바꾸지 않았다. reanchor에서는 chirp 지각>10µs면 chirp 시간표를, 프레임 시작 지각>10µs거나
  이전 프레임 마지막 chirp+100µs가 다음 시작보다 늦으면 프레임 시간표를 실제 시각으로 옮긴다. 프레임별로 재고정 횟수·정지 최대·
  최소 chirp 간격·프레임 간격을 기록한다. 루프백 시험: 중간 정지3ms 뒤 최소 간격≥90µs(몰아 보내기 없음), 시작 정지 뒤 다음 프레임 지각 회복.
  Windows 시험은 구조 확인이며 VM 시간 주장이 아니다. analyze_stream은 reanchor JSON에 새 규칙을 적용한다(absolute는 기존 규칙).
  Ubuntu 첫 시험(사용자 콘솔): 15개 중 1개 실패. 3프레임 루프백 수신 333/384였다. 송신 후에 읽는 시험 구조에서 Linux `rmem_max`가
  수신 버퍼를 제한한 것으로 보고, 시험 판정을 송신 JSON의 chirp/바이트 수로 바꿨다. 송신기 변경은 없다.
  test SHA `d6cd3f3f…`→`4dd8b6ca…`(배포 전 사본 `build/sender_reanchor_pre_20261126/test_check_pacing_deployed1.py`).
- **PL 92345 (`--schedule reanchor`, 12.8ms/10,000; 회수본 `build/s2a_int16_board_pace9_20261126_adc01`):** 무효·불합격.
  수신기 `72396cb0…`, 송신 JSON `28f82a0a…`. **고정 기록 0바이트**(pid 줄 없음)라 정식 조건을 확인할 수 없다. clock_errors=1로 trace도 무효다.
  송신 유효(새 규칙): P99 4.26µs, 정지 11/10,000(최대 2.77ms), 최소 chirp 90.155µs, 최소 프레임 12.8002ms, 실효 주기 12.831ms(+0.24%).
  재고정은 chirp 4793회, 프레임 9999회(작은 밀림이 프레임 끝에 쌓임). 수신 패킷 전부, kernel_drops0, 9327 processed·673 queue_full(전 구간).
  500프레임 구간 중앙값이 정상(prepare2.55·CFAR6.55ms)과 감속(3.45·9.05ms, ×1.37)을 오갔고 CFAR>8ms가 57%다. 92336과 같은 비율이라 고정 미적용과 맞지만 확인하지는 못했다.
  처리분 조립완료→출력 P99 73.2ms. kernel_drops0은 조건이 달라 92344 드랍 원인 판정에 쓰지 않는다.
- **무효 PL 92346 / 92347:** 92346은 사용자 실행으로 고정 1/1/2가 적용됐지만(보드 /tmp 기록 회수) 송신 없이 processed0·exit2로 끝났다.
  남아 있던 92345 고정 스크립트(sudo, pid 10725)가 T(정지) 상태였다. 92345 고정 기록이 빈 원인은 백그라운드 sudo의 비밀번호 대기로 보인다.
  92347은 에이전트 첫 실행이다. 비대화형 SSH PATH에 /sbin이 없어 run_board.sh가 devmem 단계(status127)에서 끝났고, 수신기·송신 모두 없었다.
  원본은 `benchmarks/reports/2026-11-26-s2b-pace/invalid_92346_92347/`.
- **PL 92348 (12.8ms/10,000, 에이전트 실행; 회수본 `build/s2a_int16_board_pace10_20261126_adc01`): 불합격.**
  경로: Windows 키 `fmcw_agent` → Ubuntu → 보드 SSH, root 소유 래퍼 `run_pinned.sh`(`4e4cdf3c…`, 이것만 NOPASSWD). READY와 mask 1/1/2를 확인한 뒤 송신했다.
  수신기 `72396cb0…`, 송신기 `51ba255c…` reanchor, 송신 JSON `ab51e78e…`. 송신 유효: P99 4.70µs, 정지 5/10,000(최대 8.22ms), 최소 90.135µs/12.8002ms, 실효 주기 12.835ms.
  수신: exit2, kernel_drops108(=1,280,000−1,279,892), 그 밖의 카운터 0, clock 같음. 9996 processed·3 partial(5458·5459·5463)·1 evicted(4906).
  처리분 조립완료→출력 중앙10.934/P99 11.099/최대29.6ms(초과22), 단계 중앙 prepare2.537·FFT1.553·CFAR6.542·flush0.218ms, CFAR>8ms 0.03%, CPU139.1%·RSS5.21MiB.
  5458~5463은 송신 정지 5451~5457 직후다. 5456 조립 7.89ms<12.7ms이고 송신 측 최소 간격은 ≥90µs라 VM→선로 도착 압축을 의심한다.
  4906은 송신 정지가 없고, 4904에서 CFAR14.9·flush10.1ms, 4905에서 조립29.4ms로 보드 전체 지연 뒤다. 재고정 송신 뒤에도 드랍이 남아 92344 드랍이 송신 몰아 보내기만의 결과는 아니다.
  원인 구분(도착 압축/보드 지연)은 선로·소켓 큐 기록이 없어 미확정.
- **S2b-diag-out (진단 전용, 출력 위치 A/B; 회수본 `build/s2a_int16_board_diagout_20261126_adc01`):** 래퍼 v2 `2b06ecfd…`, 92348과 같은 조건에서 출력 위치만 바꿨다.
  92349 ram: 드랍12, 정지17(최대26.3ms), P99 10.943. 92350 nfs: 드랍20, clock_errors1, P99 10.948. 92351 ram: 드랍151, 정지7(최대3.0ms), P99 10.960.
  세 번 모두 kernel_drops = 보드 Udp RcvbufErrors 증가분이고, eth0 rx drop은 없었다. 세 번 모두 고정 1/1/2와 송신 유효를 확인했다.
  CFAR>8ms·flush>4ms는 ram 0/0, nfs 4/1(92348 3/3)로 보드 단발 지연은 NFS 출력과 맞는다. 드랍은 출력 위치와 상관없이 조립 지연(20~39ms) 뒤 압축 도착 부근에서 났다.
  92350 4363·92351 7700은 송신 측 정지가 없어 VM 밖 경로 지연을 의심한다(선로 기록 없음, 미확인). [비교](../benchmarks/reports/2026-11-26-s2b-pace/diag_out/diag_out_compare.json).
- **판정 기준 분리 후 재판정(사용자 결정 11-26, checker `--network-loss-ok` `13ab3a37…`):** 92348(nfs, 정식) 처리 실시간 충족 — 9996 처리, 손실 4프레임, P99 11.099ms, 4/4·오검출0.
  진단 92349(ram) 9998·P99 10.943, 92351(ram) 9996·P99 10.960도 충족. 92350은 clock_errors1로 무효.
- **PS 92352 (ps, 12.8ms/10,000, 에이전트 실행·고정 1/1/2·reanchor, nfs; 회수본 `build/s2a_int16_board_psmain_20261126_adc01`):** 처리 실시간 불합격(참고), trace 무효.
  송신 `ddf909d9…` 유효(P99 5.11µs, 정지 3, 최대 27.1ms). exit2, kernel_drops232, clock_errors3(수신 스레드 수 ms 정지 시 생길 수 있음, 추정). 9994 processed, 손실 6608–6611·8863–8864.
  조립완료→출력 중앙12.444/P99 23.837/최대53.5ms, 초과234. 단계 중앙 prepare0.627·FFT5.930·CFAR5.578·flush0.228ms, 큐대기 P99 11.08ms. 1000프레임 구간 P99 12.58~47.6ms.
  처리 중앙이 주기의 97%라 회복 여유가 0.36ms/프레임뿐이다. 92343(200)과 단계 시간이 같아 여유 부족은 측정 오류로 보기 어렵다. CPU156%·RSS6.56MiB.

## S3a-0 — PS 셀당 비용 감축 (prepare·CFAR)

- **문제:** [S3a 설계](s3a_size_scaling_design.md)에서 PS+PL의 병목은 PS prepare·CFAR였다(128×128 셀당 약 0.555µs). 256×256(25.6ms)에서 실시간을 만족하려면 ≤0.2µs/셀이 필요하다(계산값).
- **가설:** 결과를 바꾸지 않고 줄일 수 있다.
  - 정수 경로(pl/model) 전력은 ≤2^31 정수이고 기존 double prefix 값은 2^53 미만이라 모두 정확하다.
  - 그래서 정수 합으로 바꿔도 threshold가 비트 단위로 같다.
- **변경 (사용자 승인 11-26 "ㄱㄱ"):** 원본은 `build/s3a0_pre_20261126/`에 백업했다.
  - `stream_pipeline.hpp` `c2f6f213…`→`e2c4779a…`: detect 전력 인라인, ps 식 유지, pl/model은 uint32 전력, `power()`는 지연 채움.
  - `cfar_ca.hpp` `39cb5939…`→`ee12fba9…`: `detect_integer`(uint64 Doppler 열 합 갱신 + 행별 1D prefix, 내부 고정 오프셋, 정수 비교). ps는 기존 `detect` 그대로.
  - `stream_adc16.hpp` `ffae26d9…`→`ed6406a3…`: 무분기 32비트 round-half-even.
  - 테스트 추가: `tests/adc_window_exhaustive.cpp` `74fdeb4d…`, `cfar_integer_equiv.cpp` `70b2af34…`, `bench_s3a0.cpp` `a6a5b20f…`, `micro_s3a0.cpp` `57ea3580…`.
  - 빌드 플래그는 그대로다(-O2, NEON 없음, gcc 9.4.0).
- **정확성 (모두 통과):**
  - 창: Hann 2,017 가중치 × 65,536값을 전수 검사했다. Hann에는 동점이 없어 합성 가중치 20,221개(동점 73,727)도 검사했다.
  - CFAR: 45건(9개 크기 × 5개 입력, 래핑 반복·256²·512² 포함)에서 memcmp가 일치했다.
  - 덤프: 입력 8종의 스펙트럼·전력·threshold 전체와 peaks가 기존과 SHA 동일하다(model `c9123fbb…`, ps `7157b512…`, host·보드).
  - 기존 `test_cfar.py` 4건과 host smoke 6건도 통과했다.
- **보드 마이크로벤치 (CPU1, 500회 중앙값, 기존·신규를 번갈아 2회씩):**
  - model prepare 2.168→1.034ms, detect 5.957→2.148ms → **0.496→0.194µs/셀**.
  - ps detect 5.010→3.744ms, ps prepare는 변화 없다.
  - 기존 detect의 약 3ms는 CFAR이 아니라 셀마다 문자열 비교와 함수 호출을 하던 전력 루프였다(micro: 기존 CFAR만 2.87ms).
  - 중간 단계 new2는 ps detect가 5.52ms로 느려졌고(재현), new3에서 해소했다. 기록은 보존했다.
- **10k 회귀 (PL, nfs, reanchor, 고정 1/1/2, 에이전트·래퍼 v3 `run_pinned3.sh` `eb928df4…`; 번들 `s2a_int16_20261126_s3a0_01` stream-receiver `ef01f150…`):**
  - **92354:** 10000/10000 처리, kernel_drops 0, clock_errors 0, 검산 PASS 4/4.
    - 조립완료→출력 중앙 5.354 / **P99 5.504** / 최대 26.0ms (12.8 초과 4).
    - 단계 중앙 prepare 1.196 · FFT 1.459 · CFAR 2.380 · flush 0.226ms. 처리 합계 5.277ms로 주기의 41%다(92348은 10.854ms, 85%).
    - **송신 무효**(지터 P99 34.2µs > 10, 최대 6.6ms, 정지 26)라 처리 실시간 `meets=false`다.
  - **92353:** 송신 무효(P99 28.2µs), kernel_drops 99, **clock_errors 1** → trace 무효, 검산기 거부. P99 5.513ms(참고).
  - **92355:** 송신 무효(P99 29.9µs), kernel_drops 158, 9994 처리, 검산 PASS, P99 5.511ms(참고).
  - 송신 JSON: `65fc6f84…`·`339ee9ba…`·`d4ab9b79…`.
- **92356 (PL 10k 재실행, 호스트 앱 정리 후):** 송신 유효(지터 P99 7.42µs, 정지 37, 최대 189.5ms, 송신 JSON `f8466281…`).
  - 실행 중 **보드가 비정상 재부팅**했다. 재부팅 후 uptime 0분이었고, dmesg에 FAT 비정상 언마운트·ext4 recovery가 있었다. 마지막 출력은 프레임 8839이고, frames.csv·counters·exit는 기록되지 않았다.
  - 재부팅 후 `/dev/fft128-dma-frame`이 없다(PL 장치 재설정 필요).
  - 원인(전원·패닉·워치독)은 이전 부팅 로그가 휘발성이라 미확인이다. 부분 raw는 `regression/pl_s3a0_main_04_partial_raw`에 있다. 판정에서 제외한다.
- **92357 (PL 10k, PL 재로드 후):** 처리 실시간 **충족**.
  - 송신 유효(P99 5.89µs, 정지 12, 송신 JSON `69d67b3b…`). kernel_drops 251, 그 외 카운터 0, queue_full 0.
  - 9995 처리. 손실 8623·8624·8626(missing)·8627·8630, 손실 패킷 251 = kernel_drops. 검산 PASS 4/4·오검출 0.
  - 조립완료→출력 중앙 5.341 / **P99 5.527** / 최대 24.9ms. 단계 중앙 prepare 1.197 · FFT 1.449 · CFAR 2.380 · flush 0.224ms.
- **92358 (PS-only 10k):** 처리 실시간 **충족 (128×128 PS-only 첫 충족)**.
  - 송신 유효(P99 7.14µs, 정지 7, `2ac302ce…`). kernel_drops 441, 그 외 0, 9991 처리. 손실 9프레임, 손실 패킷 441 = kernel_drops. 검산 PASS 4/4.
  - 조립완료→출력 중앙 11.182 / **P99 11.451** / 최대 32.3ms (12.8 초과 21). 92352는 P99 23.837, 초과 234였다.
  - 단계 중앙 prepare 0.623 · FFT 5.949 · CFAR 4.307(92352 5.578) · flush 0.234ms. 처리 합계 11.104ms로 주기의 87%(92352 97%). CPU 평균 147%.
- **검산기 변경 (`check_adc16_stream.py` `13ab3a37…`→`17747a1f…`, 이전본 `build/s3a0_pre_20261126/check_adc16_stream_pre_missing.py`):**
  - 92357에서 패킷 0개인 `missing` 프레임 때문에 거부됐다.
  - 사용자 규칙("kernel_drops와 그로 인한 프레임 손실은 보고만")에 맞춰 `missing`도 네트워크 손실로 인정한다. 단, **비처리 프레임의 손실 패킷 수가 kernel_drops와 정확히 같을 때만** 인정한다(더 엄격한 조건).
  - `processing_realtime`에 lost_packets를 추가했다.
- **해석:**
  - 셀당 목표는 충족했다(보드 마이크로벤치).
  - 10k 처리 시간은 92348의 절반이고 세 번 모두 일관된다.
  - 오전 송신은 지터 P99 4.7~5.1µs였는데, 이번에는 세 번 연속 28~34µs였다. Ubuntu는 유휴였고 Windows 호스트에서는 다른 앱이 실행 중이었다. 호스트 경합으로 보지만 확인하지 못했다.
  - 기준은 완화하지 않았다. 호스트 앱을 정리한 뒤 송신이 유효해졌고, **92357(PL)과 92358(PS-only)이 처리 실시간을 충족했다.**
  - S3a-0 합격 조건(검출·수치 동일, 128×128 10k 처리 실시간 유지, 셀당 비용 측정)을 모두 충족한다.
  - 92356 보드 재부팅 원인은 미확인이다. 재로드 후 두 번 실행에서는 재발하지 않았다.
- **증거:** [보고서](../benchmarks/reports/2026-11-26-s3a0/README.md). bench 원본·SHA, regression raw 3개, 송신 JSON, 에이전트 로그가 있다. 회수본은 `build/s2a_int16_board_s3a0main_20261126_01`(공유 폴더)에 있다.
- **다음:** S3a-1(크기 일반화, 128×128에서 결과 무변경 확인). 송신 전에 호스트의 다른 앱을 정리한다(지터 P99 10µs 미만 유지).

## S3a-1 — 프레임 크기 일반화 (M×N)

- **표기:** 이 절은 M(chirp)×N(샘플)이다. [S3a 설계](s3a_size_scaling_design.md) §3·§6은 N×M으로 쓴다(설계 "D축 128×256" = 여기 256×128).
- **문제:** S3a 크기 확장을 하려면 128×128 고정 가정(패킷·조립·FFT·CFAR·레코드·검산)을 없애야 한다. 이 변경이 128×128 결과와 실시간 성능을 바꾸면 안 된다.
- **가설:** 크기를 인자로 바꾸고 128×128은 기존 경로를 그대로 쓰면, 결과는 비트 동일하고 처리 시간도 같다.
  - 큰 크기의 정수 경로는 방법 A로 E14 128×128 블록을 재사용할 수 있다.
  - 방법 A: chirp d%split_d, 샘플 r%split_r로 블록을 나눈다. 블록마다 128×128 FFT를 하고 비트 역순 위치에 놓는다. 그다음 남은 Doppler·range DIT 단을 같은 Q15 버터플라이(floor /65536 + 포화)로 계산한다.
- **변경 (사용자 "S3a-1 시작"; 설계 §7 결정은 권장안으로 가정):** 원본은 `build/s3a1_pre_20261126/`에 백업했다. 파일별 SHA는 [보고서](../benchmarks/reports/2026-11-26-s3a1/README.md)에 있다.
  - 수신기:
    - `stream_protocol.hpp` `e989ce3a…`→`971a370e…`
    - `stream_pipeline.hpp` `e2c4779a…`→`b07a6883…`
    - `stream_adc16.hpp` `ed6406a3…`→`597b26d6…`
    - `stream_receiver.cpp` `ba167cd6…`→`e09c1348…` (`--pulses`/`--samples`, 128 아닌 크기는 adc16 전용)
  - 송신·레코드: `replay_stream.py` `291751e8…`, `adc16_record.py` `38cf32f9…`.
  - 기준·검산:
    - `adc16_reference.py` `6095e437…`: 독립 NumPy 방법 A. 128은 기존 oracle.
    - `check_adc16_stream.py` `17747a1f…`→`28fbbf0a…`
    - `analyze_stream.py` `33c8b81c…`
    - `smoke_s2a.py` `d5224ed1…`: 선택 인자. 기본은 기존 동작.
    - 신규 `smoke_s3a1.py` `101f3e06…`
  - 지원 크기: M∈{128,256,512}, N∈{128,256}. N=512는 한 패킷 MTU를 넘어 제외했다.
- **Host 검증 (Ubuntu, `build/s3a1_host_02` `3d0e4b47…`):**
  - 기존 테스트·smoke가 모두 통과했다.
  - 방법 A ≡ 128 oracle 10건이 통과했다.
  - 256×128·128×256·256×256·512×128 × model/ps 루프백 8건이 모두 4/4·오검출 0이었다(run 92391–92398, 5프레임). 첫 프레임 전bin에서 model은 정확히 같았고, ps는 1e-9 안이었다.
  - 입력은 시드 고정 합성 4톤 + 잡음이다(radarsimpy 아님).
  - 첫 빌드는 `-Werror=misleading-indentation`으로 실패해 수정했다(`s3a1_host_01`).
- **128×128 비트 동일·속도 (`bench_s3a0` 재빌드, 보드 CPU1 500회 중앙):**
  - 덤프가 model `c9123fbb…`, ps `7157b512…`로 S3a-0과 같다(host·보드, 각 2회).
  - **s3a1a 회귀(보존):** ps detect 3.744→4.649ms(+24%), model prepare 1.034→1.113ms.
    - 원인: 정규화가 상수 `/16384`에서 런타임 `/norm`이 되어 ARM에서 실제 나눗셈이 생겼다. prepare는 vector 루프로 바뀐 영향이다.
  - **s3a1b:**
    - `*(1/cells)`로 바꿨다(2의 거듭제곱이라 정확히 같다). prepare는 지역 포인터 루프로 바꿨다.
    - 결과: model prepare 1.031, detect 2.171, ps detect 3.802ms. 덤프는 그대로다.
  - s3a1a bench 직후 보드가 재부팅됐다(원인 미확인, 결과는 완결). 사용자가 PL을 재로드했다.
- **10k 회귀:**
  - 번들 `s2a_int16_20261126_s3a1_01`(stream-receiver `f5aafa2e…`), 래퍼 v3, nfs, reanchor, 12.8ms, chirp 100µs.
  - **92401·92403 (PL):** 송신 무효(지터 P99 117/123µs, overrun 9601/9648). 노트북이 **배터리 전원**(CPU 성능 약 50%)이었다. 수신 측: 92401은 10000/10000·카운터 0, 92403은 9993·drops 145(참고).
  - **92404 (PL, AC 연결 후):** 처리 실시간 **충족**.
    - 송신 유효(P99 5.53µs, 정지 7).
    - 9996 처리, kernel_drops 169 = 손실 패킷, queue_full 0, 4/4·오검출 0.
    - P99 5.449ms(S3a-0 92357 5.527). 단계 중앙: prepare 1.110 · FFT 1.400 · CFAR 2.390 · flush 0.222ms.
  - **92405 (PS):** 송신 무효(P99 22.6µs). 9998 처리, drops 57(참고).
  - **92406 (PS-only):** 처리 실시간 **충족**.
    - 송신 유효(P99 6.23µs, 정지 14).
    - 9998 처리, kernel_drops 18 = 손실 패킷, queue_full 0, 4/4.
    - P99 11.635ms(S3a-0 92358 11.451). 단계 중앙: prepare 0.635 · FFT 5.969 · CFAR 4.457(S3a-0 4.307) · flush 0.229ms. 12.8 초과 38(S3a-0 21).
- **해석:**
  - 128×128 수치 결과는 바뀌지 않았고 10k 처리 실시간도 유지됐다.
  - PS-only CFAR 단계 +0.15ms는 bench 차이(+0.06ms)보다 크다. 실행이 1회라 변동과 회귀를 구분하지 못했다. 여유는 1.17ms다.
  - 큰 크기는 기능과 정확성만 확인했다(host). 보드 PL 분할 경로와 큰 크기 처리량은 미측정이다.
  - 송신 유효성은 호스트 전원 상태에 민감하다. 측정 전에 AC 연결을 확인한다.
- **증거:** [보고서](../benchmarks/reports/2026-11-26-s3a1/README.md). 회수 원본은 공유 폴더 `build/s3a1_evidence_20261126_01`에 있다.
- **다음:**
  - 큰 크기 보드 실행: 래퍼에 `--pulses/--samples` 전달이 필요하다(루트 소유 파일이라 사용자 sudo).
  - 이어서 256×128 등에서 PL 분할 경로 정확성을 확인하고 S3a 크기별 처리 시간을 측정한다.

## S3a-2 — D축 256×128 (M=256 chirp, 25.6ms) 처리 실시간

- **표기:** M(chirp)×N(샘플). 설계 §6의 "D축 128×256"과 같다.
- **질문:** 주기 25.6ms에서 256×128 PS+PL / PS-only가 처리 실시간을 만족하나.
- **준비 (11-26, 측정 아님):**
  - 고정 입력 `benchmarks/fixtures/s3a/radarsimpy_256x128_sim_multi4_noise_adc16.rspb` `d5ffcbc9…`
    - float 원본 `…_noise.rspb` `8cc1cf79…`
    - 생성기 `tools/detection/make_s3a_fixture.py` `321f0e1c…`. 128×128 고정 입력과 같은 사슬이다(RadarSimPy 15.5.0 표적별 합 + NumPy seed42 잡음 → float RSPB0001 → 고정 이득 양자화).
    - `--check-128`이 기존 `radarsimpy_128x128_sim_multi4_noise_adc16.rspb` `d3d5160c…`를 바이트 단위로 재현한다.
    - 재현은 첫 시도에 실패했다. float 파일을 거치지 않으면 2개 코드가 1 LSB 다르다. 그래서 float 파일 경유로 수정했다.
    - 기준 모델 model·ps 4/4, 오검출 0, 클리핑 0. peaks (21,10) (215,20) (8,37) (174,53).
  - 보드 크기 전달: 래퍼 v3와 sudoers는 바꾸지 않는다.
    - 번들의 `shape.txt`("pulses=M samples=N")를 `run_board.sh`가 읽는다(`run_adc16_board.sh` `b8eb507f…`→`9a675c96…`). `artifacts.sha256`에 있어야 한다. 없으면 128×128로 기존과 같다.
    - 파싱은 Ubuntu에서 4경우(없음·미등록·등록·잘못된 값)로 시험했다.
  - `prepare_adc16.sh` `055fb4c0…`→`67bed923…`: 선택 인자 `MxN`. shape.txt를 만들고 smoke_s3a1을 추가로 실행한다. source.sha256에 smoke_s3a1·make_s3a_fixture를 추가했다.
  - Host 루프백(25.6ms, chirp 100µs, 20프레임, 전bin): model 92411·ps 92412 모두 4/4·오검출 0, 첫 프레임 전bin 일치(`build/s3a2_prep_20261126/host_loopback_01`, 처리량 주장 없음).
  - 에이전트 송신 스크립트 v4(고정 입력·주기·프레임 인자): 공유 폴더 `build/s3a2_prep_20261126/agent_run4.sh`.
- **번들 (사용자 sudo 배포):** `s2a_int16_20261126_s3a2_m256`
  - stream-receiver `f5aafa2e…`(S3a-1과 같은 소스), shape.txt `9f38ba1b…`, source.sha256 `19c43303…`
  - prepare.log: host smoke와 smoke_s3a1 통과.
  - 실행 조건: 래퍼 v3, nfs, reanchor, 25.6ms, chirp 100µs, 고정 1/1/2.
- **200 예비:**
  - PL 92413: 200/200, P99 17.493ms, 4/4.
  - PS 92414: 200/200, 처리 26.10ms > 주기라 P99 115.6ms. 예비 불합격.
  - 두 런 모두 송신 유효.
- **92415 (PL 10k):** 처리 실시간 **충족**.
  - 송신 유효(P99 5.17µs, 정지 7).
  - 9993 처리, kernel_drops 737 = 손실 패킷, queue_full 0, 검산 4/4·오검출 0.
  - 조립완료→출력 중앙 17.213 / **P99 17.558ms**(주기의 69%).
  - 단계 중앙: prepare 2.259 · **FFT 9.953** · CFAR 4.714 · flush 0.225ms.
- **92416 (PS-only 10k):** **불합격**.
  - 송신 유효(P99 5.10µs, 정지 0).
  - 처리 중앙 26.044ms > 25.6ms. FFTW 15.583 · CFAR 8.976ms다.
  - 큐가 차서 queue_full 153이고 9841 처리, P99 130ms. 검산기가 거부했다.
- **92417 (PL diag 20, 사용자가 보드에서 sudo로 직접 실행):**
  - 첫 프레임 전bin 32,768개가 독립 NumPy 방법 A와 **정확히 일치**했다. 20/20 4/4, 카운터 0.
  - 송신 지터 P99 28.3µs로 무효다. 정확성 전용이라 판정에는 쓰지 않는다.
- **해석:**
  - 셀 수가 2배일 때 prepare·CFAR은 ×2.0으로 비례했다.
  - PL FFT는 ×7.1이다. E14 두 번을 뺀 약 7ms가 재배치와 결합 단이다.
    - 결합 버터플라이는 비인라인 `fft128_real/imag/pack` 6회와 int64 나눗셈 4회를 쓴다(코드 확인, 단계 내부는 미계측).
    - 결과를 바꾸지 않고 줄일 여지가 있다.
  - PS-only는 FFTW만으로 주기의 61%라 현재 구현으로는 불가하다.
- **증거:** [보고서](../benchmarks/reports/2026-11-26-s3a2/README.md). 회수 원본은 공유 폴더 `build/s3a2_evidence_20261126_01`에 있다.
- **다음 후보:**
  - 결합 단계를 비트 동일로 최적화한다(인라인 디코드, 산술 시프트 floor). 그다음 S3a-3 R축(N=256, 12.8ms)으로 간다.
  - R축은 같은 셀 수를 12.8ms 안에 처리해야 한다. 지금 PL 처리 17.1ms로는 불합격으로 예상한다(계산값).

## S3a-2b — 분할 경로 결합 단계 감축 (결과 비트 동일)

- **문제:** S3a-2 PL 256×128 FFT 9.953ms 중 E14 두 번(약 2.8ms)을 뺀 약 7ms가 방법 A의 재배치와 결합이었다.
  - 결합 버터플라이는 비인라인 `fft128_real/imag/pack` 6회와 int64 `/`·`%` 4회(ARM32 라이브러리 호출)를 썼다.
- **가설:** 같은 floor·포화를 int32 비트 연산으로 계산하면 결과는 같고 결합 시간은 크게 준다.
- **변경 (사용자 "결합 최적화"):** `stream_pipeline.hpp` `b07a6883…`→`2ba1c7f5…`. 원본은 `build/s3a2b_pre_20261126/`에 있다. 분할 경로만 바꿨다.
  - P = 2^15·h + l이면 a = (A+h)>>1, b = (A−h−(l≠0))>>1이다. 포화는 기존과 같다.
  - PL은 블록을 E14 요청 버퍼에 직접 모으고 꺼낸다.
  - 중간판(int64 시프트 floor)도 측정해 보존했다.
  - 테스트 추가: `bench_s3a2.cpp` `e5b9f508…`, `micro_s3a2.cpp` `63ee6656…`, `butterfly_s3a2_equiv.cpp` `a1be217b…`.
- **정확성:**
  - 버터플라이 등가성 247,525,504건(경계 전수, 실사용 twiddle 260개, 무작위 2억)이 S3a-1 int64 식과 같았다(host·보드).
  - 분할 경로 덤프(4개 크기 × hann/none × 7종 입력)는 `2e47b50b…`로 같았다(host·보드).
  - host 테스트·smoke 전부 통과(`e7ceb48d…`).
  - 보드 PL diag 92420(사용자 sudo): 첫 프레임 전bin 32,768개 일치, 20/20 4/4.
- **보드 결합 단계 (micro, 100회 중앙):**
  - 256×128: 5.428→**1.591ms**
  - 128×256: 6.108→2.246ms
  - 256×256: 23.140→7.715ms
  - 중간판 int64 시프트: 2.402 / 2.867 / 10.458ms
- **10k (번들 `s2a_int16_20261126_s3a2b_m256` `c9a6564b…`, 256×128, 25.6ms):**
  - **92418:** 송신 유효, 9999 처리. **clock_errors 1로 trace 무효**, 검산 거부. FFT 4.866ms(참고).
  - **92419:** 처리 실시간 **충족**.
    - 송신 유효(P99 6.77µs, 정지 12).
    - 9997 처리, kernel_drops 171 = 손실 패킷, queue_full 0, 4/4·오검출 0.
    - 조립완료→출력 P99 **12.569ms**(92415 17.558). 처리 합계 중앙 12.199ms(17.129).
    - 단계 중앙: prepare 2.375 · **FFT 4.862**(9.953) · CFAR 4.722 · flush 0.218ms.
- **해석:**
  - 결과 변경 없이 256×128 처리 시간이 주기의 67%→48%가 됐다.
  - prepare +5%(2.26→2.38ms)는 코드를 바꾸지 않았는데 두 번 재현됐다. 원인은 미확인이다.
  - R축 N=256(12.8ms)은 결합과 strided 모으기가 더 커서, 지금 처리 합계로는 경계 또는 초과로 예상한다(계산값).
- **증거:** [보고서](../benchmarks/reports/2026-11-26-s3a2b/README.md). 공유 폴더 `build/s3a2b_evidence_20261126_01`, `build/s3a2b_bench_20261126`.
- **다음:** S3a-3 R축 128×256(N=256, 12.8ms) PL. 번들 `prepare_adc16.sh <label> 128x256`, 고정 입력 `make_s3a_fixture.py --shape 128 256`.

## S3a-3 — R축 128×256 (N=256 샘플, 12.8ms) 처리 실시간

- **표기:** M(chirp)×N(샘플). 설계 §6의 "R축 256×128"과 같다.
- **질문:** 주기 12.8ms에서 128×256 PS+PL이 처리 실시간을 만족하나.
  - PS-only는 같은 셀 수의 S3a-2에서 처리 26ms였으므로 불합격으로 예상한다(계산값). 참고로만 측정한다.
- **예측 (계산값, S3a-2b 실측 단계 비용 기준):** PL 처리 ≈ prepare 2.4 + FFT ≈6.0 + CFAR 4.7 + flush 0.2 ≈ 13.3ms로 경계다.
  - FFT ≈6.0 = E14 2회 ≈2.6 + range 결합 2.25 + strided 모으기 0.88 + 배치 0.24.
- **준비 (11-26, 측정 아님):**
  - 고정 입력 `benchmarks/fixtures/s3a/radarsimpy_128x256_sim_multi4_noise_adc16.rspb` `58ab27b7…`
    - float 원본 `d350dcb9…`
    - `make_s3a_fixture.py --check-128 --shape 128 256`. 128 재현을 다시 확인했다.
    - 기준 model·ps 4/4, 오검출 0, 클리핑 0. peaks (10,10) (107,20) (4,37) (87,53). fs가 N에 비례해 range bin은 128×128과 같다.
  - Host 루프백(12.8ms, chirp 100µs, 20프레임, 전bin): model 92421·ps 92422 모두 4/4·오검출 0, 첫 프레임 전bin 일치(`build/s3a3_prep_20261126/host_loopback_01`, receiver `e7ceb48d…`, 처리량 주장 없음).
- **번들 (사용자 sudo 배포):** `s2a_int16_20261126_s3a3_n256`, stream-receiver `c9a6564b…`, shape.txt `47243607…`.
  - 실행 조건: 래퍼 v3, nfs, reanchor, 12.8ms, chirp 100µs, 고정 1/1/2.
- **200 예비:**
  - PL 92423: 처리 13.82ms > 주기, queue_full 9. 송신도 무효(P99 18.7µs).
  - PS 92424: 처리 26.39ms, queue_full 99. 송신 유효.
- **92425 (PL 10k):** **불합격**.
  - 송신 유효(P99 5.69µs, 정지 10).
  - 처리 중앙 **13.761ms > 12.8**: prepare 2.382 · FFT 6.045 · CFAR 5.107 · flush 0.226.
  - queue_full 673, 9310 처리, 검산 거부. kernel_drops 673은 처리 지연에 따른 버퍼 넘침으로 보인다(미확인).
- **92426 (PL diag 20, 사용자 sudo):** range 결합 하드웨어 전bin 32,768개 일치, 20/20 4/4. 송신 무효(정확성 전용).
- **PS-only 10k:** 생략했다(S3a-2 92416과 같은 셀 수로 이미 불합격, 92424 26.39ms).
- **해석:**
  - FFT는 예측(≈6.0ms)과 맞았다.
  - CFAR은 같은 셀 수의 256×128보다 +8%(5.11 대 4.72ms)다. 원인은 미확인이다.
  - 주기 대비 약 1.0ms 초과라 여유까지 약 2ms를 줄여야 한다.
  - 결과 불변 후보(미측정): prepare가 블록 순서로 직접 쓰기(strided 모으기 약 0.9ms), range 결합과 배치 합치기, N=256 CFAR 증가 원인 확인.
- **증거:** [보고서](../benchmarks/reports/2026-11-26-s3a3/README.md). 회수 원본은 공유 폴더 `build/s3a3_evidence_20261126_01`.
- **후속:** S3a-3b에서 결과를 바꾸지 않고 처리를 줄여 92428로 충족했다.

## S3a-3b — R축 128×256 처리 시간 감축 (결과 비트 동일)

- **선행:** S3a-3 92425 불합격(처리 13.761ms > 12.8ms).
- **변경:** `src/PS/receiver/stream_pipeline.hpp` `2ba1c7f5…` → `103bf9a7…`(원본 `build/s3a3b_pre_20261126/`). 128×128 경로는 그대로다.
  - N=256 행을 짝수 샘플 128개, 홀수 샘플 128개 순으로 저장한다(가중치도 같은 순서). range 블록 모으기가 연속 복사가 된다.
  - split_d=1이면 블록 1을 배치하지 않고 블록 출력에서 바로 range 단계를 계산한다.
  - 32비트 ARM에서 결합 버터플라이(int32 식)와 큰 크기의 `adc_window`를 NEON 4레인으로 계산한다. `#pragma GCC target("fpu=neon")`으로 커널에만 켰고 빌드 플래그는 그대로다. x86 host는 scalar 경로를 쓴다.
  - 테스트 추가: `micro_s3a3b.cpp` `854100b2…`, `butterfly_s3a3b_neon_equiv.cpp` `2c3edc8a…`, `window_s3a3b_neon_equiv.cpp` `62200f90…`.
- **정확성:**
  - 보드 NEON 결합 등가성 247,525,504건, 윈도우 등가성 205,232,624건(가중치 64,895개), 행 커널 프레임 20개가 모두 같았다.
  - 분할 경로 덤프 `2e47b50b…`가 host(scalar)와 보드(NEON) 모두 S3a-2b와 같았다.
  - host 테스트 7종과 smoke 3종이 통과했다(`build/s3a3b_host_01`).
  - diag 92427(사용자 sudo)은 20/20, 카운터 0, `all_bins=True`, 4/4. 송신은 무효(P99 38.6µs, 정확성 전용).
- **보드 micro (128×256, μs 중앙값):**
  - prepare 1,904 → 1,281–1,295
  - 모으기 608–626 → 348–358
  - 배치+결합 2,002–2,011 → 693–695
  - 1판(순서·결합만)은 prepare가 +0.1ms 늘어 순감이 약 0.34ms였다. 그래서 NEON을 추가했다.
- **번들:** `s2a_int16_20261127_s3a3b_n256`(사용자 sudo 배포), stream-receiver `3bc3c552…`, source.sha256 `6b5660a7…`, shape.txt `47243607…`.
  - 조건: 래퍼 v3, 에이전트 송신 v4, nfs, reanchor, 12.8ms, chirp 100µs, 고정 1/1/2, AC 전원 확인.
- **92428 (PL 10k):** **충족**.
  - 송신 유효(P99 5.56µs, 정지 7, `8629038e…`).
  - 9992 처리, queue_full 0, kernel_drops 401 = 손실 패킷 401, 그 밖의 카운터 0. 검산 PASS 4/4, 오검출 0.
  - 처리 중앙 10.609ms(P99 10.848): prepare 1.530 · FFT 3.688 · CFAR 5.158 · flush 0.223.
  - **조립완료→출력 P99 10.990ms.** 12.8ms를 넘은 프레임이 23개(최대 30.26ms) 있었지만 원인은 확인하지 않았다.
- **확인하지 않은 것:**
  - 이 번들의 256×128(NEON Doppler 결합·prepare 사용)과 128×128 성능은 재측정하지 않았다.
  - N=256 CFAR이 같은 셀 수의 256×128보다 긴 원인도 아직 모른다.
- **실패 기록:** 첫 bench 빌드 `out_fail_access_01`은 사본의 클래스 접근을 열지 않아 컴파일이 실패했다. 고쳐서 다시 빌드했다.
- **증거:** [보고서](../benchmarks/reports/2026-11-27-s3a3b/README.md). 회수 원본은 공유 폴더 `build/s3a3b_evidence_20261127_01`, bench는 `build/s3a3b_bench_20261127`.

## S3a-4 — 정사각 256×256 (주기 25.6ms) 처리 실시간과 clock_errors 보정

- **질문:** 256×256(M=256 → 주기 25.6ms)에서 PS+PL이 처리 실시간을 만족하나. PS-only는 참고로만 본다.
- **예측 (계산값):** S3a-3b 단계 비용 × 셀 수 2로 PL 처리 ≈ 22.3ms(주기의 87%).
- **준비:**
  - 고정 입력 `radarsimpy_256x256_sim_multi4_noise_adc16.rspb` `783fac6e…`(float `800bbb5f…`, `--check-128 --shape 256 256`). 기준 model·ps 4/4, 클리핑 0.
  - host 루프백 model 92429·ps 92430 4/4, 전bin 일치(receiver `7f4745ee…`, 처리량 주장 없음).
- **번들 (사용자 sudo 배포, 처리 소스 stream_pipeline `103bf9a7…`):**
  - `s3a4_m256n256`: receiver `3bc3c552…`
  - `s3a4b_m256n256`: clock 진단판 `735bdcd5…`
  - `s3a4c_m256n256`: 보정판 `ebc3caaf…`
  - 모두 `s2a_int16_20261127_` 접두사, shape.txt `56d63b89…`.
- **조건:** 래퍼 v3, 에이전트 송신 v4, nfs, reanchor, chirp 100µs, 고정 1/1/2, PL 100MHz, AC 전원 확인.
- **예비와 diag:**
  - PL 200 92432 예비 충족(처리 22.60ms, P99 23.02ms).
  - PS 200 92433 불합격(처리 76.85ms, FFT 55.4ms).
  - diag 92431·92437·92439 모두 전bin 65,536개 일치, 4/4(송신 무효, 정확성 전용).
- **첫 10k 92434·92435·92436: 무효.**
  - 송신 유효, queue_full 0, c2o P99 23.05–23.27ms였다.
  - 그러나 clock_errors 2/1/2로 검산이 거부했다.
- **원인 조사:**
  - 이전 10k급 raw 23개 중 clock_errors가 난 런은 5개였다.
  - CPU1 처리 부하·첫 패킷 수신 지연과는 상관이 없었다.
  - receiver에 진단(`clock_diag.txt`, `stream_receiver.cpp` `e09c1348…`→`8dc69e91…`)을 넣고 92438(10k, 무효)을 돌렸다.
  - 두 오류가 같은 패킷 하나에서 났다. 오프셋 측정 span 6.40ms, 편차 −3.198ms(≈−span/2)로, 측정 중 스레드 선점이다.
  - 92434–92436도 같은 원인인지는 진단 기록이 없어 미확인이다.
- **보정 (사용자 승인, `8dc69e91…`→`e5792290…`):**
  - span이 20µs를 넘으면 최대 3회 재측정하고 가장 짧은 값을 쓴다.
  - 2ms·1ms 기준과 무효 규칙은 그대로다.
  - host 테스트 7종과 smoke 3종이 통과했다. 진단판 첫 빌드 `s3a4b_host_01`은 편집 실수로 컴파일 실패해 기록으로 남긴다.
- **92440 (PL 10k, 보정판): 충족.**
  - 송신 유효(P99 7.69µs, 정지 6, `f97b6ff6…`).
  - 9999 처리, queue_full 0, kernel_drops 2 = 손실 패킷 2, clock_errors 0. 검산 PASS 4/4, 오검출 0.
  - 처리 중앙 22.654ms: prepare 3.138 · FFT 9.119 · CFAR 10.168 · flush 0.219.
  - **c2o P99 23.128ms.** 25.6ms를 넘은 프레임이 21개(최대 41.47ms) 있었고 원인은 미확인이다.
  - 재측정 39,581회, unresolved 0, 실제로 쓴 span 최대 17.6µs.
- **해석:**
  - 256×256 PS+PL은 처리 실시간을 충족했다. 가장 큰 단계는 CFAR(10.2ms)이다.
  - prepare가 예측보다 0.5ms 길었고 원인은 미확인이다.
  - 보정 전 실험의 판정은 바꾸지 않는다.
- **증거:** [보고서](../benchmarks/reports/2026-11-27-s3a4/README.md). 회수 원본은 공유 폴더 `build/s3a4_evidence_20261127_01`.

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
