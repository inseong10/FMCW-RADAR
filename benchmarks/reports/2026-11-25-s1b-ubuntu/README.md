# S1b — Ubuntu 전체 수신기 FFT/CFAR 검증 (2026-11-25)

증거 종류: **Ubuntu PC 실행 원본 + Windows 독립 재계산**. ARM·보드 실행은 없다.
사용자 콘솔의 `S1B_RECORDED_CHECK_PASS cases=6`을 공유 폴더 원본으로 다시 확인했다.

- Ubuntu g++ 9.4.0, x86_64-linux-gnu, C++17/O2/Wall/Wextra/Werror.
- 실행 파일: 공유 폴더 `build/s1b_host_20261125_192320/receiver`.
  SHA256 `7dc2fb964bb543888dcbd48db6183db1f5e7b83b792bd9cc53d9ef84efbc650f`.
- 최초 실행은 FFTW3 로딩 실패(`initial_missing_fftw.log`). 런타임 설치 안내 후 재시도한 실행은 통과했다.
  설치 콘솔 자체는 회수하지 않았다.
- 원본 실행: `build/s1b_check_20261125_192503/`, warmup 2/repeat 3,
  잡음 기록 3개 × none/hann, 원본 IQ·double FFTW·정규화 없음·CA-CFAR 기본 파라미터.
- `manifest.json`에 소스 SHA 4개와 입력 SHA·명령이 있다. 작업 사본의 소스 4개와 SHA가 일치했다.
  공유 사본은 `.git`이 없어 해당 manifest의 base_commit은 null이다.

검증 명령:

```bash
python3 tools/detection/verify_receiver.py \
  --binary build/s1b_host_20261125_192320/receiver \
  --out build/s1b_check_20261125_192503 --warmup 2 --repeat 3
```

전체 결과를 ignored `build/s1b_ubuntu_20261125_192503/`로 회수하고
`verify_receiver.py --check-only`로 독립 재계산했다. 모든 FFT 복소수 값·검출 목록·피크 전력·임계값과
FFT/CFAR/전체 처리 단계별 시간 표본 수를 확인했다(`independent_check_console.txt`).
Ubuntu 자체 summary는 `ubuntu_checked_summary.json`, 독립 재계산 summary는 `checked_summary.json`이다.
작은 원본 로그·검출 CSV·시간 CSV·빌드 환경을 이 보고서에 보존했다. 전체 스펙트럼 CSV·입력·실행 파일은 ignored build 경로에 있다.

| 입력 | none: 검출/정답, 오검출 | hann: 검출/정답, 오검출 |
|---|---|---|
| single_noise | 1/1, 0 | 1/1, 0 |
| multi4_noise | 4/4, 1 | 4/4, 0 |
| close_weak_noise | 1/3, 0 | 1/3, 0 |

근접 약표적의 CA masking 실패도 유지했다. 모든 정답 검출을 달성했다는 뜻은 아니다.
repeat 3의 PC 기능 확인이며 paired 300회 보드 성능, 연속 UDP, P99·드랍 합격 근거로 사용하지 않는다.
다음은 ARM 빌드·보드 재생/CFAR 시간 측정과 실제 UDP 수신 검증이다.
