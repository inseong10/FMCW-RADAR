# E13-stream — 7단계 프레임 스트리밍 보드 결과

2026-11-21. E13-stream의 RTL·host43개·ARM/Vivado·보드자체검사·전체frame·별도20회profile·
각300회paired와원본독립검증을완료했다. 공유수집75파일/9,274,530B를 ignored
`build/fft128_dma_stream_measurements`에byte-identical로보존했다.
Ubuntu derived JSON은바꾸지않고Windows독립재계산을별도보존했다.

## 변경과 고정 조건

E13-bf2의반복형4코어/총8 butterfly를,7개전용DIT stage를연결한단일frame-streaming pipeline으로교체했다.
각stage는입력2/출력2 frame slot(각128word RAM)을사용하며서로다른chirp의stage계산을겹친다.
stage0은bit-reverse입력이고나머지입출력은natural index순서다. 완성128샘플블록단위로버퍼링하는
frame pipeline이며단일sample SDF지연선구현으로측정하지않는다.
코어배치/버퍼/내부출력cadence도함께바뀌는구조비교다. 기존4코어를유지한한변수실험으로해석하지않는다.

butterfly_pipeline/twiddle/Q15포화·단계별1/2스케일,50MHz,단일Simple DMA/AXIS32/HP0 64,
축128FFT·64KiB/2ioctl·4채널,coherent복사/PS전치/정규화·측정경계는고정했다.
external_buffers=false/stage_frame_slots=true/buffering=per_stage_double_frame_slots로식별한다.
ABI7은header112/input112/output65648을유지하고PROFILE일때추가88B를반환한다.
PS복사최적화/PL전치/클록·정밀도변경은포함하지않았다.

## 비계측 paired 비교

128×128 고정Q15입력·창없음·전체1/16384정규화,CPU0,warmup10/repeat100×3회전순서다.
Q15배열부터CPU가용2D출력까지필요한복사/DMA/IRQ대기/전치·정규화를포함한다.
UDP/파일IO·양자화·할당·검증·FFTW plan생성은제외한다.

| 경로 | 표본 | 평균 ms | 중앙값 ms | p05–p95 ms | 최대 ms |
|---|---:|---:|---:|---:|---:|
| PS double/FFTW | 300 | 5.816576 | 5.826396 | 5.752816–5.878260 | 6.073872 |
| PS float+NEON/FFTW | 300 | 3.662854 | 3.652869 | 3.609486–3.733483 | 3.793140 |
| PL E13-stream/50 MHz | 300 | 2.800575 | 2.787411 | 2.768887–2.858631 | 3.072570 |

이번paired double보다2.090254배,NEON보다1.310488배빠르다.
NEON대비전체시간23.692555%,double대비52.158916%짧다.

| 동일종류 측정 | 과거 E13-bf2 | E13-stream | 감소 |
|---|---:|---:|---:|
| 전체, 비계측300회중앙값 |2.841720ms|2.787411ms|1.911131%|
| PL active, 별도profile평균 |0.837903ms|0.711424ms|15.094707%|
| profile전체평균 |2.885369ms|2.880577ms|0.166067%|

프로파일평균과비계측중앙값은다른모집단이다. 둘을빼서CPU단계의시간변화로쓰지않는다.
과거bf2와이번stream은다른부팅이며이번에펌웨어를교차실행한비교가아니다.
PS artifact는모두같지만double5.708112→5.826396ms(+2.07%),NEON3.520371→3.652869ms(+3.76%)로
이번세션의PS기준도늘었다. plan/wisdom·캐시·스케줄·시스템실행차이의원인은분리하지않았다.
전체중앙값의1.9%차이를스트리밍만의순수효과로단정하지않는다.
부팅ID·IRQ·실제NEON plan·wisdom은보존했다. CPU주파수sysfs는unavailable이며
BogoMIPS나BD설정을실측CPU주파수로사용하지않는다.
PL trial1/2/3 중앙값2.792034/2.780235/2.786172ms,최대3.072570ms를그대로기록한다.

## 정확도·신원·실제 단계/프레임 겹침

- 매반복보드정수검사PASS. 저장3trial/profile각16,384 complex bins가독립Python Q15모델과
  허용오차없이완전일치한다. 입력Q15도fixture와같고피크는(107,20)이다.
- PL NumPy최대복소오차8.749842363 Q15LSB/상대L2 1.361020928%로이전산술과같다.
  PS double/NEON도각기정한정확도기준을통과했다. Ubuntu/Windows 참조계산의끝자리차이18필드는
  raw_validation.json에보존했으며정수oracle일치에는부동소수점재계산허용치를적용하지않았다.
- 비계측/profile은같은22 artifact SHA로자체검사번들과일치한다. 수집PL/host/module source는
  현재checkout과같다. 실제구현7stage/각4DSP·4RAMB36은빌드보고서로확인했다.
- DMA IRQ67/68은CPU0각660회/CPU1증가0으로330프레임×2축과같다.
  256FFT/frame,2ioctl/4채널,입출력합262144B를유지한다.
- 모든20profile행의각stage issue/retire는16384/16384회다. 각stage64pair/FFT에맞고
  stage CALC합121856=256FFT×7×68이다. 이는여러stage의누적시간으로벽시간에더하지않는다.
  bf2의2butterfly CALC합64512와다른연산기배치의누적량이므로이값만으로성능을비교하지않는다.
- multi-stage 실제CALC33280cycles/frame,여러in-flight FFT34772cycles/frame이다.
  IO동시29996/input-CALC32382/output-CALC32382/세동작29996cycles가모든행에서같다.
  work_active는실제stage_calc OR이므로이전bf2의첫출력RAM읽기보정은필요없다.
  실제복수stage/복수FFT·입출력겹침이보드에서도확인됐다.
- RTL에서검증한지속frame II128을보드profile에서샘플별timestamp로직접측정한것은아니다.
  전체packet active와위카운터가무정체RTL스케줄과일치함을별도로확인했다.
- 계측trial혼입/1LSB출력변조/stage6 retire1회누락거부negative guard도PASS다.
  생성build metadata board_verified:false는원래빌드단계로보존하고
  검증한22 SHA범위의완료는board_verification.json에별도기록했다.

## 별도20회 profile

계측평균2.880577ms/중앙값2.865153ms다. 비계측300회와합치지않는다.

| 겹치지않는host구간 | 평균 ms |
|---|---:|
| 사용자입력복사 |0.239945|
| ioctl전체 |1.687757|
| 사용자출력복사 |0.254236|
| PS gather/scatter |0.687152|
| host잔여 |0.011487|
| 전체 |2.880577|

ioctl내부는kernel copy-in0.218480+submit0.034890+wait0.745637+check0.024483+
copy-out0.639365+잔여0.024903ms다. 이구간과PL active0.711424ms는ioctl에중첩되므로
host전체에다시더하지않는다. 사용자+커널복사합1.352026ms/PS전치0.687152ms다.

| 같은종류의profile평균 | E13-bf2 | E13-stream |
|---|---:|---:|
| 전체 ms |2.885369|2.880577|
| PL active ms |0.837903|0.711424|
| PL밖잔여 ms |2.047466|2.169153|
| 사용자+커널복사 ms |1.247281|1.352026|
| PS전치 ms |0.671572|0.687152|

PL구간은0.126479ms줄었지만비PL잔여는0.121687ms늘어profile전체감소는0.004792ms다.
복사증가0.104745ms/전치증가0.015580ms가증가분대부분을차지한다.
특히사용자출력복사는0.172988→0.254236ms지만원인은분리하지않았다.
이증가를스트리밍연산의필연적인추가비용으로단정하지않으며별도반복/교차실행이필요하다.
비PL잔여는순수CPU실행시간이아니다. PL active는이번전체의24.697272%다.

무정체RTL35540cycles/frame=0.710800ms와실제0.711424ms가가깝다.
입력starvation평균31.2cycles/frame/출력stall0이며모든행의global−input_stall은35540이다.
이관찰을일반적인순수CALC측정법으로사용하지않는다.

## 해석과 남은 개선 대상

전용stage pipeline은기능·단계동시수행·PL시간측면에서성공했다. 실제PL active는약15.1%줄었다.
전체중앙값은이번수집에서약1.9%짧았고,별도profile에서는복사·전치증가가PL절감시간대부분을상쇄했다.
현재복사+PS전치합2.039177ms는profile전체의약70.79%다. 큰전체가속을위해서는이데이터이동비용도줄여야한다.

고정AXIS32/50MHz에서축당16384샘플×두축출력만의하한은32768cycles=0.655360ms다.
현PL active와하한차이는0.056064ms로,같은출력폭·클록하에서연산기만확대해얻을수있는여유는작다.
이하한은달성예측이아니며입력과출력이겹치므로양방향전송량을직렬로더하지않는다.
요청한bf2와스트리밍두단계의보드검증은완료했다. E11d복사/E14 PL전치등의후속변경은이번실험에포함하지않았다.
연속UDP·최악지연·드랍0/실시간보장은아직미검증이다.

## 구현·원본·재현

50MHz WNS10.401/WHS0.024ns, LUT6089/17600·FF6259/35200·BRAM31/60·DSP28/80이다.
bf2의LUT7428/FF6555/BRAM23/DSP32대비논리와DSP는줄고BRAM은늘었다.
[실제빌드·자체검사](../2026-11-21-e13-stream-build/README.md),
[로컬준비·초기실패기록](../2026-11-21-e13-stream-preparation/README.md),
[기준bf2보드](../2026-11-21-e13-bf2-board/README.md).

75원본은ignored build/fft128_dma_stream_measurements에byte-identical로보존했다.
raw_compact에는로그/시간CSV/profile/metadata/환경/wisdom/manifest를보존하고큰spectrum/input CSV는제외한다.
전체경로·크기·SHA는raw_artifact_sha256.json,분석소스SHA와driver도보존했다.
함수호출로독립재계산해원본을수정하지않았다. comparison.json/profile.summary.json은Windows재계산값이다.

재현할때validation_driver.py.txt를repo build/validate_e13_stream_measurements.py로복사하고
공유/로컬수집75파일을준비한다:
```powershell
python build/validate_e13_stream_measurements.py
```
[실험 일지](../../../docs/experiment_log.md).
