# PS01: 보드 원본 검증 완료 — double / float scalar / float+NEON

상태: **2026-11-16 원본 CSV·로그·plan/wisdom·환경·artifact check 수집 및 독립 분석 완료**.
폴더명은 앞서 보존한 콘솔 기록의 날짜를 유지했다. 같은 Zybo, 같은 Q15 프레임, CPU0,
단일 스레드, 각 워밍업 10회 후 100회씩 3 trial이다. 순서는 trial마다 회전했다.

## 전체 FFT 경로 (주 비교)

| PS 변형 | 표본 수 | 중앙값 (ms) | 평균 (ms) | p05~p95 (ms) | 최소~최대 (ms) |
|---|---:|---:|---:|---|---|
| double | 300 | 5.502540 | 5.498577 | 5.442966~5.566529 | 5.432418~5.732772 |
| float scalar | 300 | 4.341573 | 4.350084 | 4.293004~4.409682 | 4.280862~4.560445 |
| float+NEON | 300 | **3.615852** | **3.622898** | 3.563816~3.691539 | 3.495150~3.749508 |

중앙값 기준 float+NEON 변형은 새 double보다 **1.521782배**, float scalar보다
**1.200705배** 빠르다. double 대비 약 34.29% 시간 감소다. double→float 비교에는
정밀도·버퍼 크기·컴파일러 자동 벡터화 정책 차이가 포함되며 순수 NEON 효과로 부르지 않는다.
float 두 변형은 수신기와 라이브러리의 compiler 자동 벡터화를 모두 껐고 FFTW의 명시적
NEON codelet만 달리한다. 이것이 가능한 모든 PS 최적화의 한계라는 뜻은 아니다.

측정 구간은 `fft_pipeline`: 입력 작업 버퍼 복사, Range FFT, 32×32 타일 전치,
Doppler FFT, 정규화 및 기존 단계 타이머 bookkeeping을 포함한다.
UDP·파일 I/O·할당·입력 양자화·plan/wisdom 생성·워밍업·피크/축 계산·수치 검증은 제외한다.
매 반복 검증이 캐시에 영향을 줄 수 있어 이번에 다시 잰 double과 비교했다.
E10 double 5.557368 ms를 이번 실험의 비교 분모로 대체 사용하지 않는다.

## 단계별 평균과 병목

단계별 비교는 평균끼리 한다. 전체 중앙값에 단계 평균을 더하거나 빼지 않는다.

| 단계 평균 (ms) | double | float scalar | float+NEON |
|---|---:|---:|---:|
| 입력 복사/창 | 0.579943 | 0.322194 | 0.339761 |
| Range FFT | 1.664127 | 1.361425 | 0.995189 |
| 전치/창 | 1.234284 | 0.729836 | 0.705625 |
| Doppler FFT | 1.697061 | 1.359793 | 1.002872 |
| 정규화 | 0.288676 | 0.544965 | 0.547702 |
| 내부 타이머 bookkeeping 잔여 | 0.034487 | 0.031871 | 0.031748 |
| 전체 fft_pipeline | 5.498577 | 4.350084 | 3.622898 |

NEON의 FFT 두 축 합은 1.998061 ms, 나머지는 1.624837 ms다.
정규화는 float 두 변형에서 double보다 길게 관찰됐다. 코드 생성/메모리 원인은
아직 분리하지 않았으므로 원인을 단정하거나 이 단계에서 추가 최적화를 섞지 않는다.
전체 시간의 표본 변동계수는 double 0.828%, scalar 0.980%, NEON 1.137%다.

## 앞서 수집한 콘솔 수치

아래는 **FFT only**로 복사·전치·정규화가 빠진 진단값이다. 원본 재계산과 일치했다.

| PS 변형 | FFT only 평균 (ms), 각 300회 | 최대 복소 오차 (Q15 LSB) | 상대 L2 |
|---|---:|---:|---:|
| double | 3.361188 | 1.83315e-12 | 2.9e-16 |
| float scalar | 2.721218 | 0.000470413 | 1.1532413e-7 |
| float+NEON | 1.998061 | 0.000426809 | 1.0831023e-7 |

당시에는 trial당 표본 수가 100으로 같아 표시된 세 평균의 평균을 사용했다.
FFT only에서 NEON은 double 대비
약 1.682배, float scalar 대비 약 1.362배 빠르다. 이를 전체 경로 가속비나
E10 PL 25.259 ms 대비 가속비로 사용하지 않는다. 복사·전치·정규화가 빠진 값이다.

매 반복 16,384 complex bins를 측정 밖에서 NumPy 기준과 비교했다.
세 변형 모두 설정한 최대 복소 오차·상대 L2 기준을 통과했다.
수집한 콘솔에는 `PS_PRECISION_COMPLETE: /opt/fft128/ps_precision/results_ps01`가 있다.
원본을 확인한 결과 NEON 버전은 `fftw-3.3.11-neon`이며 두 축 모두
`t2fv_8_neon`, `n2fv_16_neon`을 사용했다. preflight와 모든 trial의 두 축 plan을
검사했다. float scalar에는 NEON codelet이 없고, 모든 trial은 각자 보드 wisdom을 사용했다.
저장 출력 9개를 NumPy로 독립 비교한 최대 오차는 double 1.833145e-12,
scalar 0.000470412707, NEON 0.000426808672 Q15 LSB다. 피크는 모두 (107,20)이다.

## 입력·빌드 식별

Ubuntu 공유 폴더의 build artifact 16개를 SHA256 manifest와 독립적으로 대조했다.
컴파일러는 arm-linux-gnueabihf-g++ 9.4.0이며, 빌드 환경의 수신기 소스 해시도
현재 작업 트리의 LF 정규화 해시와 일치했다. 실행 파일·라이브러리·기준 CSV는
ignored `build/fft128_ps_precision/`에 복사했고 다음 소형 근거를 보존했다.

- [콘솔 수치와 확인 범위](console_summary.json)
- [입력·기준 정의](reference.json), [빌드 artifact SHA256](artifacts.sha256)
- 각 변형 디렉터리의 컴파일러 flags·FFTW 빌드 환경
- [준비 단계의 소스 스냅샷·로컬 검증](../2026-11-15-ps01-preparation/README.md)

회수한 `artifact_check.txt`에서 보드 실행 전 16개 manifest 항목의 OK를 확인했고,
회수한 build environment의 해시도 manifest와 일치한다. 회수 후 보드 파일을 다시
읽어 재해시한 것은 아니다. FPGA·클록·전송 경로 변경은 없다.
환경은 PetaLinux 5.15.19-xilinx/ARMv7 Cortex-A9, CPU0이며 CPU 주파수는 직접 확인되지 않았다.

## 결론과 다음 PL 목표

새 PS 기준은 전체 경로 중앙값 **3.615852 ms**다. E10 PL 내부 측정 4.408320 ms가
이미 이보다 0.792468 ms 길다. 따라서 기존 코어/50 MHz/256 FFT 순차 실행을 유지하는
E11 DMA만으로 PS를 이긴다고 예측하지 않는다. E11a/E11b는 전송 비용을 분리·검증하는
단계로 유지하고, 이후 출력 개선·연산기 확장·겹치기를 프로파일에 따라 선택한다.

과거 E10 PL 전체 중앙값 25.2591725 ms는 참고로 약 6.986배 길지만 이번 PS01에서
PL을 교차 실행한 비율은 아니다. 이후 가속 주장은 새 PL 단계와 PS를 함께 재측정한다.
12.8 ms 프레임 간격을 감당하는 목표와 PS보다 빠른 목표도 계속 구분한다.

## 원본·재현·한계

[comparison.json](comparison.json)은 [분석기](../../ps_precision/analyze.py)의 검증 결과이며,
[analysis_validation.json](analysis_validation.json)은 단계별 시간·분포·추가 교차 검사다.
소스 식별은 [analysis_source_sha256.json](analysis_source_sha256.json), 회수한 전체 파일
해시는 [raw_artifact_sha256.json](raw_artifact_sha256.json)에 있다.
원시 시간 CSV·runtime/preflight 로그·wisdom·환경·보드 artifact check를 이 폴더에 보존했다.
최초 [console_summary.json](console_summary.json)의 원본 미수집 표시는 당시의 확인 범위로
유지하며 현재 상태는 이번 분석 기록으로 갱신한다.

전체 결과와 마지막 출력 9개는 `build/fft128_ps_precision/results_ps01/`에 보존했다.
아래 명령으로 정확도까지 재검증할 수 있다. 보고서 폴더에는 큰 출력 CSV를 중복 저장하지
않았으므로 정확도 재검증에는 build의 전체 결과가 필요하다. 시간 통계는 보존한 CSV로 재계산 가능하다.

```bash
python3 benchmarks/ps_precision/analyze.py build/fft128_ps_precision/results_ps01
```

고정 프레임의 warm-cache 지연이며 연속 UDP 처리량이나 실시간 보장이 아니다.
이번 실험은 PS 비교만 수행했고 PL/DMA/ACP/추가 클록 변경은 하지 않았다.
