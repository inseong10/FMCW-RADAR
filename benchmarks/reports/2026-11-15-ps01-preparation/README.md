# PS01 준비: 정밀도·NEON 기준선

2026-11-15. 변경 목적·가설·측정 경계는 [일지](../../../docs/experiment_log.md)의 PS01,
실행 방법은 [PS01 절차](../../ps_precision/README.md)를 따른다.

상태: **소프트웨어·빌드/배치/실행/분석 도구 준비. ARM 전체 빌드 및 보드 측정 대기.**
기존 double 기본 경로와 E10 FPGA 펌웨어는 유지하며 DMA는 추가하지 않았다.

## 확인한 범위

- `python -m unittest discover -s benchmarks/ps_precision -p test_precision.py -v`:
  7개 PASS. pinned NumPy oracle, 기존 저장 double 보드 출력과의 일치, 분석기의 누락·
  잘못된 NEON 표시·변경 metadata 거부, 실제 C++ 수치 checker의 두 정밀도/NaN/오류/잘못된 bin.
- Bash 빌드/배치와 POSIX sh 보드 실행 스크립트 문법 검사 PASS.
- 추가 host smoke는 실제 수신기의 공개 FFTW ABI, offline replay, 작업 버퍼·전치·FFT·
  정규화·검증 코드를 추출하고 Windows loader bridge로 실제 FFTW에 연결했다.
  double/float 각각 warmup 1/repeat 3의 모든 bin이 수치 기준을 통과했고 MEASURE wisdom의
  저장/재사용이 성공했다. 이는 단위 테스트의 가상 FFT가 아니다.

## 수치 결과 (PC 검증이며 보드 실험 아님)

| 정밀도 | 최대 복소 오차 (Q15 LSB) | RMS (Q15 LSB) | 상대 L2 |
|---|---:|---:|---:|
| double | 1.8749713606747085e-12 | 3.751494330217785e-14 | 2.943383686126648e-16 |
| float | 0.00042680867197479784 | 1.3804696940779287e-5 | 1.0831022571491762e-7 |

두 경로 피크는 (Doppler unshifted, range)=(107,20).
입력은 기존 fixture SHA `aa06ff124034310216693c1398f2f1061c9a6ce32e9ea6f5687675849934c976`다.

이 추가 검사는 [공식 Windows FFTW 3.3.5 배포](https://www.fftw.org/install/windows.html)의
x86-64 DLL을 사용했다. ZIP SHA256은
`cfd88dc0e8d7001115ea79e069a2c695d52c8947f5b4f3b7ac54a192756f439f`다.
소켓·Linux main/CPU affinity는 대체했으므로 Linux 전체 수신기 검증이 아니며,
ARM FFTW 3.3.11/NEON 결과나 보드 시간을 나타내지 않는다. PC 시간은 비교에서 제외한다.

## 남은 작업과 보존

Ubuntu에서 세 ARM 실행 파일·FFTW 라이브러리를 빌드하고 NFS 별도 경로에 배치한 뒤,
같은 Zybo에서 CPU0·warmup 10/repeat 100/3 trial을 실행한다. NEON plan 선택과 매 반복
수치 검증을 통과한 원시 CSV를 수집해야 PS01 시간·가속비를 보고할 수 있다.

검사 요약은 [validation.json](validation.json), 변경 소스의 SHA256은
[source_sha256.json](source_sha256.json)에 보존한다. 빌드·DLL·상세 PC 로그·CSV는
`build/fft128_ps_precision_host/`, 다운로드 ZIP은 `build/third_party/fftw_windows/`에 있다.
이 폴더에는 보드 측정 시간이나 실행하지 않은 DMA 예상 결과를 넣지 않는다.
