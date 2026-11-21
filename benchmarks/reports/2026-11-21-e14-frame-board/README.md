# E14-frame — PL 전치와 전체 프레임 DMA 보드 결과

2026-11-21. **E14의 구현·RTL·host53개·ARM/Vivado·보드 자체 검사·전체 프레임·상세 계측·paired 비교와 원시 결과 독립 검증을 완료했다.**
공유 수집 82파일/9,290,439B를 ignored `build/fft128_dma_frame_measurements`에 byte-identical로 보존했다.
Ubuntu에서 만든 요약은 보존하고 Windows에서 별도로 재계산했다.

## 변경과 측정 범위

E13-stream의 단일 전용 7단계 FFT를 그대로 재사용한다. 64KiB in-place 행렬을 추가해
Range→열 방향 읽기→Doppler→최종 출력 배열 복원을 PL에서 수행한다.
CPU의 중간 gather/scatter와 중간 DDR 왕복을 제거했다.
전체 프레임당 2 ioctl/4채널/256KiB를 **1 ioctl/2채널/128KiB**로 줄였다.
최초 입력·최종 출력 coherent bounce 복사, Q15 산술과 단계별 스케일, 50MHz, HP0 Simple DMA/AXIS32는 유지했다.
두 축·최종 배출은 순차적이고 전체 2D 프레임끼리는 겹치지 않는다.

128×128 고정 입력, 창 없음, 전체 1/16384 정규화, CPU0 단일 스레드다.
각 경로 warmup10/repeat100을 3회 회전 순서로 실행했다.
Q15 입력부터 CPU가 사용할 수 있는 전체 2D 결과까지 복사·DMA·IRQ 대기·전치·배열 복원·정규화를 포함한다.
UDP/파일 IO, 양자화, 할당, 검증, FFTW plan 생성은 제외한다.

## 비계측 paired 결과

| 경로 | 표본 | 평균 ms | 중앙값 ms | p05–p95 ms | 최대 ms |
|---|---:|---:|---:|---:|---:|
| CPU double/FFTW |300|5.697748|5.706612|5.638287–5.758423|5.976048|
| CPU float+NEON/FFTW |300|3.507606|3.489441|3.468767–3.565925|3.943170|
| FPGA E14-frame |300|1.661498|1.657914|1.649642–1.694033|1.821228|

같은 회차 NEON 대비 **2.104718배**, double 대비 **3.442043배** 빠르다.
지연 감소는 각각 52.487691%, 70.947490%다.
PL trial 1/2/3 중앙값은 1.656882/1.660215/1.656042ms다.

과거 E13-stream 중앙값 2.787411ms 대비 1.657914ms로 **40.521366% 감소/1.681276배**다.
이 비교는 서로 다른 부팅·회차다. CPU artifact는 같지만 이번 NEON 기준도 4.47%, double도 2.06% 짧아졌다.
순수한 한 변수의 효과나 이번 부팅에서 E13을 교차 실행한 결과로 해석하지 않는다.
환경·boot ID·실제 NEON plan/wisdom·IRQ는 원본에 보존했다. CPU 주파수 sysfs는 unavailable이다.

## 별도 20회 상세 계측

계측 평균 1.700746ms/중앙값 1.695987ms다. 비계측 300회와 합치지 않는다.

| 구간 (각 회차 profile 평균) | 과거 E13-stream ms | E14-frame ms |
|---|---:|---:|
| 전체 프레임 |2.880577|1.700746|
| PL active |0.711424|1.038842|
| 사용자·커널 입력/출력 복사 합 |1.352026|0.590928|
| CPU gather/scatter |0.687152|0|
| 전체에서 PL active를 뺀 시간 |2.169153|0.661904|

PL active의 Range 0.355722 + Doppler 0.355420 + 최종 배출 0.327700ms = 1.038842ms다.
FFT 산술을 빠르게 바꾼 실험은 아니다. 최종 행렬 배출 약 0.328ms가 추가돼 PL 구간은 늘었지만,
CPU 전치와 중간 전송·복사를 줄여 전체 지연이 감소했다. 행렬 저장·열 방향 읽기는 각 FFT phase에 포함된다.
복사·CPU 전치 절감량을 비계측 중앙값 차이에 그대로 더하거나 빼지 않는다.

겹치지 않는 host 구간은 사용자 입력복사 0.110027ms, ioctl 1.501700ms, 사용자 출력복사 0.084784ms,
잔여 0.004235ms다. ioctl 내부는 kernel copy-in 0.094773ms, submit 0.017067ms, wait 1.063736ms,
check 0.013773ms, copy-out 0.301344ms, 잔여 0.011007ms다.
**PL active와 kernel 구간은 ioctl에 포함되므로 전체에 다시 더하지 않는다.**
현재 복사 0.590928ms는 남아 있고, PL active 1.038842ms도 주요 비용이다.

## 정확도·신원·카운터 검증

- 비계측 매 반복 보드 정수 검사 PASS. 저장된 PL 3trial와 profile의 각 16,384 complex bins가
  독립 Python Q15 모델과 허용오차 없이 일치한다. profile 입력 Q15도 fixture와 같고 peak는 (107,20)이다.
- NumPy 대비 PL 최대 복소 오차 8.749842363 Q15 LSB, RMS 1.734691376 LSB, 상대 L2 1.361020928%로
  E13과 같다. CPU double/NEON도 각 정확도 기준을 통과했다.
- Ubuntu/Windows 부동소수점 재계산 끝자리 차이 18필드는 `raw_validation.json`에 보존했다.
  요약 대조 허용치는 relative 1e-13/absolute 2e-12이며 정수 결과 일치에는 적용하지 않았다.
- 자체 검사 때 확인한 22개 bundle artifact와 비계측/profile 신원이 같다. 수집한 PL/host/module 소스 SHA가
  현재 로컬·공유 소스와 같다. `dma_artifact_check.txt` 및 profile `artifact_check.txt`의 보드 해시 PASS도 확인했다.
- paired DMA IRQ67/68은 CPU0 각각330회, CPU1 증가0이다. warmup 포함330프레임×1요청에 맞는다.
  별도 profile은 warmup2+20프레임이므로 각22회다. profile과 paired의 boot ID도 같다.
- 20개 profile 행 모두 matrix reads/writes 각각32768, range output/doppler input/output 각각16384,
  overwrite_errors=0, matrix_words=16384, 외부 input/output 동시 handshake=0이다.
- Range cycles는17785~17791, Doppler17771, drain16385다. 합계가 global active와 정확히 같다.
  외부 input stall 평균15.1cycles, output stall0이다. 이 카운터를 임의로 빼서 순수 계산시간으로 정의하지 않는다.
- 모든 행의 7단계 issue/retire 각각16384, stage CALC 합121856, multi-stage CALC33280,
  여러 in-flight FFT34772cycles다. 누적 stage 수치를 벽시간에 더하지 않는다.
- routed LUT6158/FF6305/BRAM47/DSP28, 50MHz WNS10.166ns/WHS0.020ns는
  [실제 빌드 보고서](../2026-11-21-e14-frame-build/README.md)에 있다.
  원래 build metadata의 `board_verified:false`는 과거 단계 상태로 보존하며 완료 범위는 `board_verification.json`이다.

## 재현과 다음 범위

```powershell
python build/validate_e14_frame_measurements.py
```

`validation_driver.py.txt`가 동일 코드 사본이다. 전체 raw 82개 SHA는 `raw_artifact_sha256.json`,
요약은 `comparison.json`, `profile.summary.json`, `progression.json`에 있다.
큰 입력·출력 CSV를 제외한 원본은 `raw_compact/`에 보존했다.
분석 소스 SHA는 `analysis_source_sha256.json`, 보고서 전체 SHA는 `evidence_sha256.json`이다.
업로드한 소스와 실제 빌드 소스의 대응은 `repository_source_identity.json`에 보존했다.
기존 소스 5개는 빌드 작업 파일의 CRLF를 Git이 LF로 저장하며, 개행 외 바이트가 같음을 확인했다.
실제 빌드 당시 raw SHA manifest는 수정하지 않았다.

E14의 고정 크기 오프라인 가속 검증은 완료했다. 연속 UDP 처리량·최악 지연·누락·크기 스윕은 별도 검증 범위다.
다음 최적화 후보는 남은 복사를 줄이는 E11d 또는 PL 최종 배출·프레임 처리 구조 개선이다.
목표를 정하고 기존 E14를 보존한 별도 구성으로 측정한다.
