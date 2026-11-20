# FFT128 단계별 가속 계획

128 samples × 128 chirps FFT 경로를 한 번에 한 가지씩 바꾸고 측정하는 계획이다.
완료한 단계의 상세 결과는 [실험 일지](experiment_log.md)와 각 보고서에 있고, 이 문서에는
**목표, 단계별 상태, 남은 단계의 설계·가설·통과 조건**만 둔다. 아래의 모든 예상 수치는 측정값이 아니다.

- 계획 수립 2026-11-15, PS 목표 갱신 2026-11-16, E11b 결과 반영 2026-11-19, E12·E13 완료 반영 2026-11-21.
- 최신 보드 검증 구성: E13-stream (전용 7단계 프레임 스트리밍 / 50 MHz / Q15 / 축당 HP0 Simple DMA).
  각 300회 중앙값 PL **2.787411 ms**, 같은 회차 NEON **3.652869 ms** / double **5.826396 ms**.
  [최신 결과](../benchmarks/reports/2026-11-21-e13-stream-board/README.md).

## 1. 목표

1. **프레임 간격 12.8 ms 처리:** 현재 입력의 128 chirps × PRP 100 us. 오프라인 지연과 별도로 연속 입력의
   처리량·최악 지연·누락을 검증해야 한다.
2. **같은 조건의 PS보다 빠른 전체 FFT 경로:** 비교 대상은 같은 회차에 다시 잰 PS float+NEON이다.
   double은 이력 비교용으로 계속 함께 잰다.

공통 조건: 같은 Q15 입력, 창 없음, 전체 1/16384 정규화, CPU0, 단일 스레드.

## 2. 단계와 상태

| 단계 | 한 번에 바꿀 것 | 유지할 것 | 상태 | 결과 (paired 중앙값) |
|---|---|---|---|---|
| PS01 | PS float scalar, float+NEON 추가 | FPGA·입력·전치·CPU0·측정 범위 | **완료** 11-16 | NEON 3.615852 ms ([보고서](../benchmarks/reports/2026-11-15-ps01-board/README.md)) |
| E11a | FFT 입출력 MMIO → DMA (FFT당 ioctl) | 단일 코어·50 MHz·FFT당 순차 호출·PS 전치 | **완료** 11-16 | PL 15.411639 ms ([보고서](../benchmarks/reports/2026-11-16-e11a-board/README.md)) |
| E11b | 축당 128 FFT 묶음 제출 | 코어·클록·산술, 전송/연산 비겹침 | **완료** 11-19 | PL 6.433026 ms ([보고서](../benchmarks/reports/2026-11-19-e11b-board/README.md)) |
| PS02 | NEON 경로에서 전치와 정규화 결합 | PS01 보존, 정밀도·FFTW·자동 벡터화 정책 | 계획 | — |
| E11c | 출력 RAM prefetch로 1 sample/clock | 산술·코어 수·50 MHz·DMA 설정 | 계획 | — |
| E11d (선택) | 버퍼 정책 하나만 변경 (mmap / streaming / ACP 중 하나) | 코어·클록·제출 단위, 기존 coherent 경로 보존 | 계획 | — |
| E12-4core | 코어별 FIFO·독립 스케줄로 입출력·CALC 겹치기 | 기존 4코어 산술·50 MHz·Q15·단일 DMA | **완료** 11-20 | PL 3.129210 ms ([보고서](../benchmarks/reports/2026-11-20-e12-4core-board/README.md)) |
| E13-2core / 4core | 기존 코어 2개 → 4개 복제, 별도 측정 | 산술·50 MHz·공유 I/O·group barrier | **완료** 11-20 | PL 4.920621 → 4.186353 ms |
| E13-bf2 | 기존 4코어 각각 버터플라이 1→2개 | E12 FIFO·스케줄·Q15·50 MHz·전송 | **완료** 11-21 | PL 2.841720 ms ([보고서](../benchmarks/reports/2026-11-21-e13-bf2-board/README.md)) |
| E13-stream | 반복형 4코어 → 전용 DIT 7단계 단일 파이프라인 | Q15·50 MHz·단일 DMA·복사·PS 전치 | **완료** 11-21 | PL 2.787411 ms ([보고서](../benchmarks/reports/2026-11-21-e13-stream-board/README.md)) |
| E14 (선택) | PL 내부 중간 결과 보관과 전치 | 수학적 결과·외부 출력 배열 | 계획 | — |
| 분리 실험 (선택) | serial/pipeline × 20/50 MHz 4구성 | 입력·측정 조건 | 계획 | E10의 결합 효과를 나눌 때만 |

E11c 이후 번호는 변경 종류의 ID이며 실행 순서가 아니다. 순서는 [5절](#5-실행-순서-결정-규칙)로 정한다.

## 3. 완료 단계 요약

| 단계 | 사전 가설 | 실제 결과 | 남긴 교훈 |
|---|---|---|---|
| PS01 | PS 전체 2~3 ms | 전체 3.615852 ms, FFT 두 축만 1.998061 ms | 비FFT 평균 약 1.625 ms가 있어 2~3 ms에 이르지 못함 |
| E11a | `B + 256h + C + S`, h=20/50/100 us면 10.475/18.155/30.955 ms + C + S | 15.411639 ms (계측 18.136318 ms) | 느려도 기능 실패가 아님. 비코어 잔여 약 41.86 us/FFT |
| E11b | 초기 `B + 2H + C + S`의 추가 비용 0.145~0.645 ms 조건에서 5.5~6 ms → E11a 복사 실측 반영 후 약 8 ms | 6.433026 ms (계측 6.473645 ms) | submit 2.939 → 0.035 ms, wait ≈ PL active. 병목이 코어로 이동 |
| E13-2core / 4core | 코어 복제로 병렬화 가능한 구간 감소 | PL 4.920621 / 4.186353 ms, active 2.857541 / 2.081883 ms | 공유 I/O·그룹 장벽 때문에 코어 수만큼 빨라지지 않음 |
| E12-4core | FIFO로 LOAD/CALC/OUTPUT 겹치기 | PL 3.129210 ms, active 1.124590 ms | 실제 I/O·CALC 겹침 확인, 같은 회차 NEON보다 10.31% 짧음 |
| E13-bf2 | CALC 476→252 cycles/FFT | 가설 일치, PL 2.841720 ms / active 0.837903 ms | active 절감보다 전체 절감이 작음 |
| E13-stream | 전용 단계로 정상상태 II 128 clocks/FFT | RTL II 128, PL 2.787411 ms / active 0.711424 ms | 초기 지연 증가, 복사·전치가 전체 병목 |

- E10 double 기준에서는 PL 내부 4.408320 ms를 뺀 예산이 약 1.149 ms였지만, PS01 NEON 목표는 PL 내부보다
  이미 0.792468 ms 짧았다. 그래서 E11 DMA만으로 PS를 이긴다고 예측하지 않았다.
- E10의 입력+출력 MMIO는 FFT당 약 79.600 us였다.
- 32-bit × 50 MHz = 200 MB/s는 한 방향 스트림 peak다. 256 KiB / 200 MB/s = 1.310720 ms는 양방향 payload를
  차례로 보낸 등가 시간이며 보편적 하한이 아니다. LOAD/OUTPUT이 861사이클에 포함되므로 4.408320 ms에 다시 더하지 않는다.

`B = 4.408320 + 0.946476 = 5.354796 ms`(E10 PL 내부 + gather/scatter)는 사고 모델이며 하한이 아니다.
`C`는 추가 복사·cache 관리, `S`는 추가 backpressure·DDR 정지·드라이버 잔여 비용, `h`/`H`는 코어와 겹치지 않는
FFT당/축당 고정 host 비용이다. E11a의 h 값은 실측이 아니라 제출 빈도 민감도 예시였다.

### 당시 기준 (E11b 계측 실행, 20회 평균)

| 항목 | 값 | 비고 |
|---|---:|---|
| 전체 | 6.473645 ms | 비계측 중앙값은 6.433026 ms |
| PL active | 4.408947 ms | nonstall 4.408320 = 861 cycles × 256 / 50 MHz |
| 사용자 + 커널 복사 | 1.263008 ms | coherent bounce |
| PS gather/scatter | 0.670374 ms | cached 전치 |
| submit + check + 잔여 | 약 0.08 ms | |
| 비교 대상 PS NEON | 3.558177 ms | 같은 회차 paired 중앙값 |

코어 밖 비용이 약 2.06 ms로 그대로라면 코어가 약 1.5 ms 이하여야 NEON보다 빠르다(단순 차감, 추정).

### 최신 기준 (E13-stream 계측 실행, 별도 20회 평균)

| 항목 | 값 | 해석 |
|---|---:|---|
| 전체 | 2.880577 ms | 비계측 300회 중앙값 2.787411 ms와 별도 모집단 |
| PL active | 0.711424 ms | ioctl 대기와 겹침, 합산하지 않음 |
| 사용자 + 커널 복사 | 1.352026 ms | coherent bounce 경로 |
| PS gather/scatter | 0.687152 ms | 중간 전치는 여전히 PS |
| 같은 회차 PS NEON | 3.652869 ms | 비계측 중앙값, PL보다 1.310488배 긴 시간 |

과거 bf2 대비 active는 15.09%, 전체 중앙값은 1.91% 감소했다. 다른 부팅의 PS 기준 변화와
profile 비PL 비용 증가를 보존하며 차이를 순수 스트리밍 효과로 단정하지 않는다.
32-bit/50 MHz 출력 payload 하한은 0.655360 ms이나 active와의 차이를 보장된 절감량으로 쓰지 않는다.
다음 구조 변경은 복사 정책(E11d)과 PL 전치(E14)의 비용·자원·cache 소유권을 먼저 비교해 선택한다.

## 4. 후속 단계와 완료 범위

### PS02 — 전치와 정규화 결합

- PS01 NEON을 보존하고, 별도 변형에서 Doppler 입력 전치에 1/16384 정규화를 합쳐 출력 배열 순회 한 번을 없앤다.
- 정밀도·자동 벡터화 정책·FFTW·plan·입력·CPU affinity는 바꾸지 않는다. 매 반복 같은 NumPy 기준으로 검증한다.
- **가설:** PS01 NEON 평균 3.622898 ms에서 정규화 0.547702 ms를 단순 제거하면 3.075196 ms.
  검토에서 제안한 2.7~3.0 ms는 추가 최적화가 필요한 목표이며 보장값이 아니다.
- float 정규화가 double보다 느린 원인은 아직 분리하지 않았다. 결합으로 순회를 없애도 그 원인을 설명한 것은 아니다.
- PS 목표선이 내려가므로 이후 PL 단계 비교에는 PS01·PS02를 함께 다시 잰다.

### E11c — 출력 1 sample/clock (독립 실험 미실시)

- `fft128_pipeline.v`의 `OUT_REQ` ↔ `OUT_SEND` 교대만 바꾸는 독립 실험이다. DMA·코어 수와 동시에 바꾸지 않는다.
- **당시 가설:** 기존 단일 반복 코어에서 FFT당 약 127~128사이클, 256 FFT/50 MHz에서 약 **0.650~0.655 ms** 감소가 무정지 상한.
  최신 스트리밍은 출력 cadence도 바뀌었으므로 이 예산을 현재 구성에 다시 적용하지 않는다.
- prefetch/보관 레지스터를 설계하고, 임의 길이의 `TREADY=0`에서도 valid/data/TLAST가 유지되고
  샘플 누락·중복이 없는지 RTL에서 검증한다. 새 사이클 수는 RTL에서 다시 확인한 뒤 기대값을 확정한다.

### E11d (선택) — 버퍼 정책

- 최신 계측 1.352026 ms(당시 E11b 1.263008 ms)인 복사를 줄이는 후보. mmap, streaming mapping, ACP 중 **하나만** 고른다.
- 복사 절감과 CPU 접근·cache·소유권 비용을 모두 포함해 비교한다. 세부 위험은 [6절](#6-캐시버퍼-정책-위험).

### E12 — 전송과 연산 겹치기 (완료)

- 초기 계획은 단일 코어 외부 ping-pong 버퍼였다. 실제 실행에서는 E13-4core 다음에 코어별 입력·출력 FIFO와 독립 스케줄을 적용했다.
  다음 벡터 입력·현재 CALC·이전 출력이 겹치며 group barrier가 없다. 외부 32-bit 스트림·단일 DMA는 공유한다.
- 초기 단일 코어 LOAD/OUTPUT 숨김 예산 1.966080 ms는 당시 가설이다. 실제 4코어 결과와 직접 차감하지 않는다.
- RTL·구현·보드 동시 수행 카운터·전체 frame/profile/paired 원본 검증 완료.
  [완료 보고서](../benchmarks/reports/2026-11-20-e12-4core-board/README.md), [실행 절차](../src/PS/fft128/dma_overlap/README.md).
- 같은 프레임 안의 벡터 겹치기만 확인했다. 서로 다른 프레임·연속 UDP 운용은 별도 검증이다.

### E13 — 연산 구조 확대 (요청 범위 완료)

- 실행 순서는 2코어 → 4코어 → E12 FIFO 겹치기 → 코어당 버터플라이 2개 → 전용 7단계 스트리밍이다. 각 구성을 별도로 검증했다.
- 초기 2코어 내부 반감 2.204160 ms 가설과 달리 실제 active는 2.857541 ms였다. 공유 입력·출력·장벽이 남기 때문이다.
  [2코어 결과](../benchmarks/reports/2026-11-20-e13-2core-board/README.md), [4코어 결과](../benchmarks/reports/2026-11-20-e13-4core-board/README.md).
- bf2는 4코어 각각 두 버터플라이, stream은 전용 7단계의 단일 프레임 파이프라인이다.
  후자는 코어 배치·버퍼·출력 cadence도 바뀌며 4코어에 스트리밍만 더한 한 변수 비교가 아니다. sample-delay SDF 구현도 아니다.
- Q15 산술·50 MHz·단일 HP0 DMA·복사·PS 전치를 유지하고 정수 모델 일치·자원·routed 타이밍을 확인했다.
  [bf2](../benchmarks/reports/2026-11-21-e13-bf2-board/README.md), [stream](../benchmarks/reports/2026-11-21-e13-stream-board/README.md).
- 독립 E11c 출력 실험은 하지 않았다. stream 내부 출력 cadence 변경 효과도 구조 비교에 포함한다.

### E14 (선택) — PL 전치

- 현재 CPU gather/scatter(E13-stream 0.687152 ms, 과거 E11b 0.670374 ms)와 중간 DDR 왕복 128 KiB가 제거 후보다.
  PL 전치·저장·출력 배열 복원 비용을 차감해야 한다.
- PL에서 전치한 뒤 중간 데이터를 다시 PS로 보내면 왕복은 없어지지 않는다. BRAM 포트·용량·주소 생성을 확인한다.

### 연속 운용

- 오프라인 비교와 별도로 정상상태 frame/s, 프레임별 지연, backlog, 누락·오류를 잰다.
- 현재 UDP에는 frame ID가 없으므로 연속 송신 전에 프레임 구분부터 해결한다.

## 5. 실행 순서 결정 규칙

변경 직전에 관찰·선택 이유·예상 절감을 일지에 먼저 적는다. 같은 프로파일에서 다음 규칙으로 고른다.

- **코어 active가 지배적이면 E13 먼저:** 복제 가능한 구간의 예상 절감 `T_parallelizable × (1 - 1/k)`와
  메모리·자원 비용을 계산해 E12의 숨길 수 있는 시간과 비교한다. 코어 복제에 필요한 최소 분배 버퍼는
  기록하되 ping-pong 겹치기를 동시에 넣지 않는다.
- **노출된 LOAD/OUTPUT·외부 전송 정지가 크면 E12 먼저:** handshake·상태 카운터로 실제 숨길 수 있는 구간을 찾는다.
  DMA 요청~완료 전체나 내부 4.4 ms 전체를 숨길 수 있는 시간으로 잡지 않는다.
- **CPU 전치·coherent 버퍼 접근·cache sync가 지배적이면 버퍼 정책 먼저(E11d):** 코어를 늘리기 전에 원인을 분리한다.

E11b에서는 첫 번째 경우에 따라 E13을 먼저 실행했고 이후 E12·bf2·stream을 완료했다. 현재는 복사·전치가 지배적이다.
E11c는 독립 측정이 남아 있고, 다음 단계는 최신 프로파일로 선택한다.

## 6. 캐시·버퍼 정책 위험

- **HP + coherent (현재):** 이 ARMv7 비일관성 경로에서 CPU 쪽 DMA 매핑은 non-cacheable일 수 있다.
  DMA 버퍼에서 직접 전치하면 cached 전치 시간을 유지한다는 가정이 깨질 수 있다.
  현재는 cacheable 작업 버퍼에서 전치하고 복사 비용을 포함해 잰다.
- **HP + streaming mapping:** 입력은 device 소유권, 출력은 CPU 소유권으로 돌려주는 시점의 map/sync/unmap을 기록한다.
  256 KiB는 양방향 payload 합계이며 매번 전부 flush·invalidate한다는 뜻은 아니다. 바이트 수만으로 시간을 정하지 않는다.
- **ACP (별도 실험):** HP가 검증된 뒤 같은 코어·클록·전송 단위로 비교한다. AXI 속성·CPU 매핑·Linux 장치의 일관성 설정을
  함께 확인한다. 포트만 옮기거나 DT에 `dma-coherent`만 적는다고 일관성이 보장되지 않는다. CPU와 캐시를 공유하므로
  경쟁과 캐시 오염도 잰다.
- 버퍼 정책·HP/ACP·IRQ/polling 변경은 각각 구성 이름과 결과를 따로 둔다.

## 7. 매 단계의 측정 계약

- **주 비교:** 같은 프레임, CPU0, PS double·NEON(PS02 후에는 PS02도)을 같은 회차에 함께 측정.
  워밍업 10회 후 100회씩 3 trial, 순서 회전. 각 300개 원시 표본의 중앙값·평균·p05/p95·최소/최대와 자원·타이밍 기록.
- **시작/끝:** 준비된 Q15 프레임에서 DMA 버퍼 복사·소유권 전환 직전부터 두 축 결과가 CPU에서 기존 배열 순서로
  준비될 때까지. 제출·완료 처리, 캐시 관리, PS 전치, 추가 복사·배열 복원 포함.
  UDP·파일 I/O·일회성 할당·plan/wisdom 생성·입력 양자화·결과 검증 제외. 한 경로의 필요 비용을 측정 밖으로 옮기지 않는다.
- **정확도:** 매 반복 종료 후 타이밍 밖에서 16,384 bin을 정수 모델과 비교. NumPy 오차·피크도 독립 확인.
- **별도 프로파일:** 워밍업 2회 / 20회. 복사, map/sync, 제출, 완료 대기, PS 전치, PL 사이클, TREADY 정지, 전송량 구분.
  DMA 요청~완료 호스트 구간은 순수 버스 전송 시간이 아니다.
- **중복:** E12부터 겹친 전송·계산 구간은 합산하지 않는다. 벽시계 전체와 단계별 구간·겹침을 함께 제시한다.
  PL 사이클 레지스터 의미가 바뀌면 함께 버전 관리한다.
- **환경:** 회차 간 PS double 중앙값이 약 +4.5%(PS01 → E11a) 달라진 원인은 미확인이다. cpufreq governor·주파수를
  읽을 수 있으면 저장하고, 부팅 식별자·IRQ 배치·주파수 정보 제공 여부를 명시한다. BogoMIPS를 클록으로 쓰지 않는다.
- **보존:** 결과는 새 디렉터리에 저장하고 입력·소스·bitstream·실행 파일 해시, 버퍼 정책, DMA 설정, 코어 수,
  제약 클록, setup/hold, 자원량을 함께 남긴다. 실패하면 그 단계에서 원인을 찾고 다음 기능을 더하지 않는다.

## 8. E11 구현 결정 기록

E11a/E11b에서 확정한 인터페이스다. 상세 근거는 실험 일지의 E11a·E11b 항목에 있다.

```text
PS DDR → AXI DMA MM2S (HP0 64-bit) → 스트림 어댑터 → FFT128 pipeline
       ← AXI DMA S2MM              ← 스트림 어댑터 ←
제어: GP0 / AXI4-Lite (FFT 0x43c60000, DMA 0x40400000), IRQ F2P[6:7]
```

| 구간 | E10 (MMIO) | E11a/E11b (DMA) |
|---|---|---|
| FFT 입력 128 samples | CPU 128회 MMIO store | MM2S가 DDR → AXI4-Stream |
| FFT 출력 128 samples | CPU 128회 MMIO load | S2MM이 AXI4-Stream → DDR |
| FFT 설정·시작·상태·cycle counter | AXI4-Lite | AXI4-Lite 유지 (payload 없음) |
| DMA 주소·길이·시작·상태 | 없음 | 커널 DMA 드라이버가 관리 |
| 두 축 사이 전치 | PS | PS (복사·소유권 전환 포함 측정) |

- 샘플은 32-bit(I 하위 16비트, Q 상위 16비트). FFT 하나 512 B, 한 축 128 FFT 65,536 B,
  프레임당 양방향 payload 262,144 B(256 KiB). Simple DMA 길이 필드 17비트(최대 131,071 B).
- E11b 어댑터: 코어의 FFT별 TLAST(매 128 샘플)를 외부로 내보내지 않고 축 마지막(16,384번째)에만 assert한다.
  MM2S 쪽은 축 마지막 TLAST와 코어의 FFT별 입력 경계를 구분한다.
- 커널(2026-11-16 조회): `5.15.19-xilinx`, `CONFIG_DMA_ENGINE=y`, `CONFIG_XILINX_DMA=y`, `CONFIG_CMA=y`,
  `CONFIG_DMA_CMA=y`, `CONFIG_OF_OVERLAY=y`, `CONFIG_CMA_SIZE_MBYTES=16`. 보드에 모듈 빌드 트리가 없어
  같은 커널 소스로 Ubuntu에서 후보 트리를 만들고 CRC 수락을 확인했다. 부팅 커널은 교체하지 않았다.
- 사용자 가상 주소를 DMA 주소로 넘기거나 임의 DDR 영역을 덮는 방식은 쓰지 않는다.
- [전체 프레임 인터페이스 초안](interfaces.md)의 가변 크기 지원은 E11 범위 밖이다.
- 실행 절차: [E11a](../src/PS/fft128/dma/README.md), [E11b](../src/PS/fft128/dma_batch/README.md).

## 참고 문서

- [FFTW 빌드 설명](https://www.fftw.org/fftw3_doc/Installation-on-Unix.html)
- [AMD PG021 AXI DMA (Direct Register Mode)](https://docs.amd.com/r/en-US/pg021_axi_dma/Direct-Register-Mode-Simple-DMA),
  [PDF v7.1, 2022-04-27](https://www.amd.com/content/dam/xilinx/support/documents/ip_documentation/axi_dma/v7_1/pg021_axi_dma.pdf)
- [Linux 5.15 DMAengine 클라이언트](https://www.kernel.org/doc/html/v5.15/driver-api/dmaengine/client.html),
  [Linux DMA API](https://docs.kernel.org/core-api/dma-api-howto.html)
- [Zynq-7000 TRM: ACP DMA](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/PL-DMA-via-AXI-ACP)
