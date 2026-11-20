# E12-4core — 입력·계산·출력 겹치기 보드 결과

2026-11-20. E12-4core의 RTL·ARM/Vivado·보드 자체 검사·전체프레임·별도20회 profile·
각300회 paired 비교와 원본 독립 검증을 완료했다. 수집75파일/9,274,768B를 ignored
`build/fft128_dma_overlap_measurements`에 복사하고 공유 원본과 모든 SHA를 대조했다.
Ubuntu의 원본 derived JSON도 수정하지 않고 Windows 독립 재계산을 별도 보존했다.

기존 FFT 산술4개/50 MHz/Q15/코어출력2clocks/sample을 유지하고, 코어별 입력/출력
동기 RAM FIFO8개와 독립 시작을 추가했다. 이전 group barrier를 없애고 다음벡터를
미리 받아 현재CALC/이전결과출력을 겹친다. 공유 입력/출력32-bit AXIS와 단일Simple DMA,
HP0 64-bit·축당64 KiB·2 ioctl/4채널·coherent 복사·PS gather/scatter는 유지한다.
FIFO는RAM256words+등록출력1word이며`external_buffers=true,buffering=per_lane_fifos`다.
E11c 코어출력1clock/sample·추가코어·버터플라이 확대·PL전치는 적용하지 않았다.
ABI5도header112/input112/output65648 배치를 유지하고추가profile만payload뒤40B다.

## 비계측 paired 비교

128×128 고정Q15입력, 창없음, 전체1/16384정규화, CPU0, warmup10/repeat100×3회다.
PS double→NEON→PL 순서를회전했다. Q15배열부터 원래순서의 CPU가용2D출력까지
필요한복사·DMA·완료대기·전치·정규화를 포함한다. UDP/파일IO·양자화·할당·검증·plan은 제외한다.

| 경로 | 표본 | 평균 ms | 중앙값 ms | p05–p95 ms | 최대 ms |
|---|---:|---:|---:|---:|---:|
| PS double/FFTW | 300 | 5.701312 | 5.711883 | 5.635739–5.757527 | 6.000126 |
| PS float+NEON/FFTW | 300 | 3.506025 | 3.488904 | 3.468139–3.569745 | 3.807486 |
| PL E12-4core/50 MHz | 300 | 3.138714 | 3.129210 | 3.089417–3.216747 | 3.483654 |

과거E13-4core 중앙값4.186353ms 대비 **1.337831배/지연25.252123% 감소**다.
이번paired double보다 **1.825343배**, NEON보다 **1.114947배** 빠르다.
NEON 대비지연은 **10.309656% 감소**다.
이제 이고정프레임/측정범위에서는 PL경로가 이번NEON기준을 넘어섰다.

| PL 구성 | 전체 중앙값 ms | 근거 |
|---|---:|---|
| E11b 1코어 |6.433026|과거세션|
| E13 2코어 |4.920621|과거세션|
| E13 4코어/group barrier |4.186353|과거세션|
| E12 4코어/FIFO overlap |3.129210|이번각300회|

E13과다른부팅이며 펌웨어를이번에교차실행한비교가아니다. PS바이너리/라이브러리 artifact는
E13때와같지만 이번paired PSdouble5.711883/NEON3.488904ms는이전5.767911/3.649998ms보다짧다.
세션/FFTW plan·캐시·OS실행차이의원인은특정하지않으며 전체시간차이를오직스케줄효과로단정하지않는다.
부팅ID·IRQ배치·wisdom/실제NEON codelet은보존했다. CPU주파수sysfs는unavailable이며
BogoMIPS나BD설정치를실측주파수로쓰지않는다.
PL trial1/2/3 중앙값3.096540/3.155397/3.125661ms와최대3.483654ms를그대로보존했다.

## 정확도·신원·실제 겹침

- 모든반복의보드정수검사PASS. 마지막3개비계측출력과profile출력의각16,384complex bins가
  독립Python Q15모델과허용오차없이완전일치한다. 저장입력Q15도fixture와같고피크는(107,20)이다.
- PL NumPy최대복소오차8.749842363 Q15LSB/상대L2 1.361020928%로기존산술과같다.
  PS double/NEON도기존정확도기준을통과했다. Ubuntu/Windows FFT참조끝자리차이는
  raw_validation.json에보존했고 정수oracle일치검사에는부동소수점재계산허용치를적용하지않았다.
- DMA IRQ67/68은CPU0각660회/CPU1증가0으로330프레임×2축과같다.
  256FFT/프레임,2ioctl/4채널,입출력합262144B다.
- 비계측/profile은같은bundle이고22artifact SHA는자체검사당시와같다. PL/host/module
  source manifest는현재checkout과같고실제구현4코어각DSP4/입출력FIFO각RAMB18를확인했다.
- profile20행모두외부입력·출력동시22830cycles/frame, input-work32194/output-work32192,
  three-work22772, multi-work38720/all-work5952다. work-window에는첫RAM읽기1clock이포함된다.
  축당128FFT씩 독립lane에서최대256비CALC clocks/frame을보수적으로제외하면
  실제4-CALC하한5696, 입력·실제CALC·출력하한22516cycles/frame이남는다.
  이값은전체시간이나그대로회수가능한절감량이아니며겹치는카운터를합산하지않는다.
- 계측trial혼입/1LSB출력변조를거부하는독립negative guard도PASS다.
  원래build metadata의board_verified:false는보존하고검증된22SHA범위의완료는
  board_verification.json에따로기록했다.

## 별도20회 profile

계측평균 **3.200291ms**, 중앙값 **3.183387ms**다. 비계측300회와합치지않는다.

| 겹치지않는host구간 | 평균 ms |
|---|---:|
| 사용자입력복사 |0.249494|
| ioctl전체 |2.088512|
| 사용자출력복사 |0.177117|
| PS gather/scatter |0.674777|
| host잔여 |0.010391|
| 전체 |3.200291|

ioctl내부는kernel copy-in0.206793+submit0.040759+
wait1.170026+check0.017940+copy-out0.630022+
잔여0.022972ms다. 이구간과PL active는ioctl에중첩되므로전체에다시더하지않는다.
사용자+커널복사합은 **1.263426ms**, PS전치는 **0.674777ms**다.

| 같은종류의profile평균 | E13-4core | E12-4core |
|---|---:|---:|
| 전체벽시계 ms |4.222976|3.200291|
| PL active ms |2.081883|1.124590|
| PL밖잔여 ms |2.141093|2.075701|
| 사용자+커널복사 ms |1.324075|1.263426|
| PS전치 ms |0.685061|0.674777|

PL active는 **45.982075% 감소**, 전체profile은1.022685ms감소했다.
그중PL구간은0.957293ms/그밖잔여는0.065392ms줄었다. 잔여는순수CPU실행시간이아니다.
무정지RTL56196cycles/frame=1.123920ms와실제1.124590ms가근접한다.
입력starvation평균33.5cycles/frame, 외부출력stall0이다. 모든행의global−input_stall은56196이지만
이관찰을일반적인순수CALC측정법으로쓰지않는다.
네산술코어busy는각55040cycles,any55932/multi55420/all53900cycles/frame이다.
FIFO만배출할때는산술busy가아닐수있고과거group-start64/frame조건도적용하지않는다.

## 해석과남은비용

코어수와산술을유지해도입출력FIFO/독립스케줄로이전의출력차례대기와그룹장벽을숨기면
PL내부가약46%줄어드는것을보드에서도확인했다. E12의시뮬레이션개선이실제DMA에서도재현됐다.
다만현재PL active는계측전체의약35.14%이고,
복사1.263426ms/전치0.674777ms/그밖비용이남는다.
다음개선은이비용과코어출력2clocks/sample의남은노출구간을독립적으로비교해서선택한다.
E11c를적용할때과거단일코어의절감상한을이번전체에그대로대입하지않는다.
연속UDP입력·최악지연·프레임누락/실시간보장은미검증이다.

## 구현·원본·재현

50MHz WNS8.709/WHS0.026ns, LUT5311/17600·FF5555/35200·BRAM15/60·DSP16/80이다.
[빌드·자체검사](../2026-11-20-e12-4core-build/README.md),
[RTL준비](../2026-11-20-e12-4core-preparation/README.md),
[이전E13](../2026-11-20-e13-4core-board/README.md).

전체75원본은ignored`build/fft128_dma_overlap_measurements`에byte-identical로보존했다.
보고서raw_compact에는로그/시간CSV/profile/metadata/환경/wisdom/manifest를보존하고,
큰spectrum/input CSV는제외하되raw_artifact_sha256.json에경로·크기·SHA를기록했다.
validation_driver.py.txt와분석소스SHA도보존했다.

수집시comparator의limitation설명한줄에이전E13의group barrier설명이남아있어현재구조로바로잡았다.
정수/신원/계측판정·통계계산은변경하지않았고Ubuntu원본JSON과구설명은그대로보존했다.
독립재계산JSON은새설명을사용하며raw_validation에이차이를명시했다.

```sh
python benchmarks/compare_dma_overlap_board.py build/fft128_dma_overlap_measurements/results_e12_4core_01
python src/PS/fft128/dma_overlap/analyze_profile.py build/fft128_dma_overlap_measurements/profile_e12_4core_01/pl.profile.csv
python build/validate_e12_measurements.py
```
위CLI는derived JSON을재생성하므로보존된raw의원본을유지하려면분석함수를호출해별도출력경로에쓴다.
이번독립검증은그방식으로수행했다.
