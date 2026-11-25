# S1b — 보드 PS FFT/CA-CFAR 기록 재생 검증 (2026-11-25)

증거 종류: **보드 원본 + Windows 독립 재계산**. 실제 UDP·연속 처리 검증은 아직 없다.
PetaLinux 5.15.19-xilinx/ARMv7 Cortex-A9, CPU0, 단일 스레드 double FFTW.
잡음 기록 3개 × none/hann, 원본 IQ·정규화 없음·CA guard=(2,2), train=(8,8), Pfa=1e-6.
warmup 10 후 구성별 동일 프레임 100회 반복이다.

```sh
sudo sh /opt/fft128/s1b_20261125_192718/run_board.sh \
  /opt/fft128/s1b_20261125_192718/receiver \
  /opt/fft128/s1b_20261125_192718/libfftw3.so.3
```

실행 파일 SHA256은 `f9320587d09f6e138c15595b9239047e2cd5a4799c0746e7345f57e69534c442`,
FFTW SHA256은 `182f6f5317bf1480aeee92d9a93958c5c5cc24fdccf36217d3ce253b01cb3c6b`다.
배포 artifact 전체·소스 4개·실행 파일/라이브러리 SHA가 일치했고 각 로그의 CPU0·double·100회를 확인했다.
`environment.txt`에 CPU 정보가 있으나 주파수 sysfs 값은 없었다. BogoMIPS를 클록으로 해석하지 않는다.

| 입력·창 | 검출/정답 | 오검출 | FFT 중앙값 ms | CFAR 중앙값 ms | 처리 전체 중앙값 ms | 처리 전체 P99 ms |
|---|---:|---:|---:|---:|---:|---:|
| single none | 1/1 | 0 | 5.505561 | 3.679449 | 10.180551 | 10.264783 |
| single hann | 1/1 | 0 | 5.507796 | 3.684306 | 10.187452 | 10.294645 |
| multi4 none | 4/4 | 1 | 5.525019 | 3.687033 | 10.212444 | 10.288369 |
| multi4 hann | 4/4 | 0 | 5.514525 | 3.690945 | 10.206336 | 10.308672 |
| close_weak none | 1/3 | 0 | 5.457771 | 3.756648 | 10.236099 | 10.309451 |
| close_weak hann | 1/3 | 0 | 5.496873 | 3.745593 | 10.243332 | 10.315181 |

처리 전체는 FFT·피크/축 계산·CFAR를 포함하는 `processing_total`이다. UDP·기록 파일 읽기·할당·계획 생성·
워밍업·CSV 저장은 제외한다. CFAR에는 전력 맵 생성·배열 변환·임계값·피크 묶기·정렬이 포함된다.
각 단계 중앙값은 별도 분포이므로 합산하지 않는다. 전체 시간 CSV에는 기존 단계 타이머 비용도 포함된다.
Hann 4표적 전체 처리 최대는 10.328154ms다. 이 값이나 100개 표본 P99로 연속 12.8ms 입력 합격을 주장하지 않는다.
기존 E14와 입력/창/정밀도·측정 구간이 다르므로 직접 가속비를 계산하지 않는다.

Windows `verify_receiver.py --check-only`로 모든 FFT bin·검출 순서·피크 전력·임계값과 단계별 100개 표본을
독립 재계산했다(`independent_check_console.txt`). Ubuntu 확인 결과는 `ubuntu_checked_summary.json`,
독립 확인 결과는 `checked_summary.json`, 소형 시간표는 `timing_summary.json`이다.
근접 약표적의 CA masking 실패를 유지하며 모든 정답 검출이 통과했다는 뜻은 아니다.

전체 스펙트럼·입력·실행 파일·라이브러리는 ignored `build/s1b_board_results_20261125_192718/`에 보존했다.
이 보고서에는 로그·검출/시간 CSV·manifest·환경·artifact check·SHA를 보존했다.
`raw_sha256.json`은 회수한 전체 원본, `report_sha256.json`은 README 작성 전의 소형 근거 파일 해시다.
다음은 실제 UDP 한 프레임 수신·동일 검출 확인이며, 지속 입력·드랍·CPU·P99 계측은 S2다.
