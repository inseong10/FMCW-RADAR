# E13-bf2 — 코어당 버터플라이 두 개 보드 결과

2026-11-21. 코어당 버터플라이1→2 실험의 RTL·host35개·ARM/Vivado·보드 자체검사·전체frame·
별도20회profile·각300회paired와 원본 독립검증을 완료했다. 수집75파일/9,275,950B를
ignored `build/fft128_dma_bf2_measurements`에 공유원본과 byte-identical로 보존했다.
Ubuntu의 derived JSON은 바꾸지 않고 Windows 재계산을 별도기록했다.

## 변경과 고정 조건

E12의 FFT4코어·코어별입력/출력FIFO·독립스케줄을 유지하고 각코어의버터플라이를2개로 늘렸다.
stage당64 butterfly를32 pair로 발행하고 작업메모리를 even/odd true-dual-port bank로 나눈다.
4코어/총8 butterfly,7단계/Q15/반올림·포화/1/2스케일,50 MHz,코어출력2clocks/sample,
단일Simple DMA/HP0 64-bit/AXIS32-bit/축당64 KiB/2ioctl·4채널,coherent복사·PS전치를 유지한다.
병렬접근을 위한RAM분할·두twiddle ROM은이번변경에포함된다. E11c 출력 cadence,
E11d 복사/E14 PL전치/스트리밍 FFT는함께적용하지않았다.
ABI6은header112/input112/output65648을 유지하고 PROFILE에서만 뒤쪽56B 계측을추가한다.

## 비계측 paired 비교

128×128 고정 Q15 입력·창없음·전체1/16384정규화, CPU0,warmup10/repeat100×3 회전순서다.
Q15배열부터 CPU가용 2D출력까지 필요한복사/DMA/IRQ대기/전치/정규화를 포함한다.
UDP/파일IO·양자화·할당·검증·FFTW plan생성은 제외한다.

| 경로 | 표본 | 평균 ms | 중앙값 ms | p05–p95 ms | 최대 ms |
|---|---:|---:|---:|---:|---:|
| PS double/FFTW | 300 | 5.704126 | 5.708112 | 5.644648–5.763423 | 5.987916 |
| PS float+NEON/FFTW | 300 | 3.533247 | 3.520371 | 3.491979–3.593903 | 3.857718 |
| PL E13-bf2/50 MHz | 300 | 2.848580 | 2.841720 | 2.810154–2.905996 | 3.117978 |

이번paired double보다2.008682배,NEON보다1.238817배 빠르다.
NEON 대비전체시간19.277826%,double 대비50.216113% 짧다.

| 비교 범위 | 기준 E12-4core | E13-bf2 | 감소 |
|---|---:|---:|---:|
| 코어CALC/FFT |476cycles|252cycles|47.058824%|
| PL active, 별도profile평균 |1.124590ms|0.837903ms|25.492580%|
| 전체, 비계측300회중앙값 |3.129210ms|2.841720ms|9.187303%|

중앙값과profile평균은다른모집단이며 합치지않는다. 과거E12와이번BF2는다른부팅세션이며
이번에펌웨어를교차실행한비교가아니다. PS바이너리/라이브러리 artifact는 E12때와모두같지만
NEON은3.488904→3.520371ms,double은5.711883→5.708112ms로세션차이가있다.
전체시간변화를모두버터플라이만의효과로단정하지않는다. boot ID·wisdom/실제NEON plan·IRQ를보존했다.
CPU주파수sysfs는unavailable이며 BogoMIPS/BD설정을실측주파수로쓰지않는다.
PL trial1/2/3 중앙값2.824050/2.833440/2.853837ms와최대3.117978ms를그대로기록한다.

## 정확도·신원·실제 두연산기

- 매반복보드 정수검사와 저장3trial/profile의각16,384 complex bins가 독립Python Q15모델과완전일치한다.
  입력Q15도fixture와같고피크는(107,20)이다. 정수일치에는허용오차를두지않았다.
- PL NumPy최대복소오차8.749842363 Q15LSB,상대L2 1.361020928%로이전산술과같다.
  PS double/NEON도기존오차기준을통과했다. Ubuntu/Windows 참조계산끝자리차이는
  `raw_validation.json`에기록했고 정수oracle에는부동소수점재계산허용치를적용하지않았다.
- 비계측/profile은같은22 artifact SHA로보드자체검사번들과일치한다.
  수집PL/host/module source는현재checkout과일치한다. 실제구현은4코어각8DSP/총32DSP다.
- DMA IRQ67/68은CPU0각660회/CPU1증가0이며330프레임×2축과같다.
  256FFT/frame,2ioctl/4채널,입출력합262144B를유지한다.
- 20profile행모두 dual issue/retire각57344pair/frame,CALC lane-cycles64512다.
  FFT당224pair(448butterfly)/252cycles로두연산기발행·완료가실제보드에서일치했다.
  코어별시간합은벽시간과달라global active에더하지않는다.
- IO동시27022,input-work32194/output-work32192/three-work26964cycles/frame이다.
  work-window에첫출력RAM읽기가있으므로비CALC상한256cycles/frame을빼면
  실제입력·CALC·출력동시수행하한26708cycles가남는다. multi-work24000/all-work0이며
  빨라진CALC로4개FFT계산창이겹치지않는것은예상과같다. 각코어내두연산기검사는직접수행한다.
- 계측trial혼입/1LSB출력변조/dual-retire1회누락을거부하는negative guard도PASS다.
  빌드metadata의board_verified:false는원래빌드단계상태로보존했다.
  완료판정은검증한22개SHA범위로 `board_verification.json`에별도기록했다.

## 별도20회 profile과 병목 이동

계측평균2.885369ms/중앙값2.864250ms다. 비계측300회와합치지않는다.

| 겹치지않는host구간 | 평균 ms |
|---|---:|
| 사용자입력복사 |0.240485|
| ioctl전체 |1.790156|
| 사용자출력복사 |0.172988|
| PS gather/scatter |0.671572|
| host잔여 |0.010168|
| 전체 |2.885369|

ioctl내부는kernel copy-in0.192323+submit0.034262+wait0.878750+check0.020546+
copy-out0.641485+잔여0.022791ms다. PL active0.837903ms와이구간은ioctl에중첩되어
전체에다시더하지않는다. 사용자+커널복사합1.247281ms,PS전치0.671572ms다.

| 같은종류의profile평균 | E12-4core | E13-bf2 |
|---|---:|---:|
| 전체 ms |3.200291|2.885369|
| PL active ms |1.124590|0.837903|
| PL밖잔여 ms |2.075701|2.047466|
| 사용자+커널복사 ms |1.263426|1.247281|
| PS전치 ms |0.674777|0.671572|

전체profile감소0.314923ms중 PL구간0.286687ms/그밖잔여0.028236ms가줄었다.
비PL잔여는순수CPU실행시간이아니다. PL active는현재전체의29.039719%다.
무정지RTL41860cycles/frame=0.837200ms와실제0.837903ms가가깝다.
입력starvation평균35.15cycles/frame/외부출력stall0이며 global−input_stall41860은이번관찰이다.
공유AXIS의stall카운터합을일반적인순수CALC시간으로빼는방법은사용하지않는다.
core0..3 busy각40704/any41596/multi41084/all39564cycles/frame이다.

## 해석과 다음 단계

두연산기가CALC를약47%줄이는효과가실제보드에서도확인됐지만 LOAD/코어출력/DMA는고정이다.
따라서 PL active감소는약25.5%,전체중앙값감소는약9.2%다. 남은복사·전치가전체이득을제한한다.

사용자가요청한다음실험은스트리밍 FFT이며 E13-bf2결과를보존한뒤별도로비교한다.
고정32-bit/50MHz출력에서축당16384샘플×두축의전송만으로최소32768cycles=0.655360ms가필요하다.
입력과출력은겹칠수있어양방향바이트를직렬전송으로더하지않는다.
이것은고정경로의하한이며스트리밍예상시간이나달성성능이아니다. 현PL active0.837903ms를
스트리밍만으로0으로없앨수는없으며 전체가다시2배빨라진다고예측하지않는다.
연속UDP·최악지연·드랍0/실시간보장은미검증이다.

## 구현·원본·재현

50MHz WNS5.405/WHS0.028ns, LUT7428/17600·FF6555/35200·BRAM23/60·DSP32/80이다.
[실제빌드·자체검사](../2026-11-21-e13-bf2-build/README.md),
[RTL준비](../2026-11-20-e13-bf2-preparation/README.md),
[기준E12보드](../2026-11-20-e12-4core-board/README.md).

전체75원본은ignored `build/fft128_dma_bf2_measurements`에byte-identical로보존했다.
`raw_compact`에는로그/시간CSV/profile/metadata/환경/wisdom/manifest를보존하고,
큰spectrum/input CSV는제외하되`raw_artifact_sha256.json`에모든경로·크기·SHA를기록했다.
`validation_driver.py.txt`와분석소스SHA도보존했다. 분석은원본을수정하지않으며
`comparison.json`/`profile.summary.json`은직접함수호출로독립재계산한결과다.

재현:
```powershell
python build/validate_e13_bf2_measurements.py
```
이 driver는재현할때 `validation_driver.py.txt`를repo의`build/validate_e13_bf2_measurements.py`로복사한다.
공유·로컬수집원본75파일이필요하다. [실험 일지](../../../docs/experiment_log.md).
