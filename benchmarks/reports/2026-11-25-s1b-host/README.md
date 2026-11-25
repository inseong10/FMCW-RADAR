# S1b — C++ CA-CFAR PC 커널 검증 (2026-11-25)

증거 종류: **Windows PC 커널 실행**. 전체 Linux 수신기·ARM 실행·보드 측정은 없다.
기준 커밋은 `f884812274e91ed226f92820be0d192fdc2f9ffd`이며 구현은 미커밋 작업 사본이다.
정확한 소스는 `source_sha256.json`, 컴파일러/명령은 `build_console.txt`에 기록했다.

```powershell
python -m unittest discover -s src/PS/receiver/tests -v
```

- 17개 중 13개 통과, 전체 수신기 실행 파일이 필요한 4개는 skip (`tests_console.txt`).
- native g++ `x86_64-w64-mingw32`, C++17/O2/Wall/Wextra/Werror로 수신기와 공유하는 헤더를 컴파일했다.
- 독립 S1a NumPy 셀 합산과 C++ 합산 영역 테이블의 모든 셀 임계값 및 최종 검출 목록을 비교했다.
  무작위 직사각형·작은 Doppler 원형 배열·0 입력·동률 피크·파라미터 오류를 포함한다.
- 잡음 기록 3개 × none/hann의 6구성에서 목록이 일치했다. 최대 임계값 상대 차이는 약 `4.09e-13`이다.
  기록 파일 SHA와 전체 검출 bin은 `summary.json`에 있다.

| 기록 | none: 검출/정답, 오검출 | hann: 검출/정답, 오검출 |
|---|---|---|
| single_noise | 1/1, 0 | 1/1, 0 |
| multi4_noise | 4/4, 1 | 4/4, 0 |
| close_weak_noise | 1/3, 0 | 1/3, 0 |

이는 S1a의 CA masking 한계도 재현한 결과다. 모든 시나리오의 정확성 목표가 통과했다는 뜻은 아니다.
임계값은 부동소수 덧셈 순서 차이를 허용하고 목록은 정확히 비교했다.
보드 CFAR 시간·UDP·P99·드랍·CPU 사용률 수치는 측정하지 않았다.

실행 파일은 ignored `build/s1b_host_kernel/cfar.exe`에 있고 SHA256은 `summary.json`에 있다.
보드 입력 번들은 ignored `build/s1b_board_20261125_01/`에 준비했으며 셸 구문 검사만 통과했다.
`build_s1b.sh`도 셸 구문 검사만 통과했다. Linux/ARM 컴파일 성공을 뜻하지 않는다.

VMware Ubuntu의 셸과 minicom 화면은 확인했지만 Computer Use 재시도에서도 문자·Enter 및
메뉴 클릭의 결과를 확인하지 못했다. 최종 확인 화면의 minicom은 `/dev/ttyUSB1`, Offline이었다.
보드에서 명령을 실행한 근거는 없다. 다음 절차는 [수신기 S1b 안내](../../../src/PS/receiver/README.md#s1b-ca-cfar-보드-검증-전)다.
