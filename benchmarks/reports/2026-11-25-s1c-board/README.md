# S1c — E14 PL Q15 출력의 CFAR 보드 검증 (2026-11-25)

증거 종류: **보드 원본 + Windows 독립 재계산**. CPU0, 기존 E14 ABI8/50MHz/전체 프레임 DMA,
동일 S1b CA-CFAR 헤더를 쓰는 별도 C++ 실행 파일, 구성별 warmup10/repeat100.
잡음 기록3개 × none/hann을 사용했다. Hann은 PC에서 적용하고 float32 RSPB로 저장한 뒤
보드에서 최대 복소수 크기→16384 양자화·단계별 floor/포화를 적용한다.

```sh
sudo sh /opt/fft128/s1c_20261125_195231/run_board.sh \
  /opt/fft128/e14_frame/fft128-receiver \
  /opt/fft128/s1c_20261125_195231/cfar-spectrum
```

6구성 모두 모든16384개 복소수 bin이 독립 Python 정수 모델과 정확히 일치하고 C++ CFAR와
NumPy CFAR의 피크 순서·전력·임계값이 일치했다. 모든 검출 목록이 원래 float 기준과 같다.
Hann 4표적4/4·오검출0, 근접 약표적1/3이라는 기존 CA 한계는 유지된다.

| 입력·창 | 검출/정답 | 오검출 | PL 전달/FFT 중앙값 ms | CFAR 중앙값 ms |
|---|---:|---:|---:|---:|
| single none | 1/1 | 0 | 1.652724 | 3.507012 |
| single hann | 1/1 | 0 | 1.675257 | 3.513786 |
| multi4 none | 4/4 | 1 | 1.661112 | 3.512952 |
| multi4 hann | 4/4 | 0 | 1.670298 | 3.533088 |
| close_weak none | 1/3 | 0 | 1.674372 | 3.497647 |
| close_weak hann | 1/3 | 0 | 1.690308 | 3.500799 |

**성분별 시간이며 합산해 종단 지연으로 쓰지 않는다.** 두 실행 파일 사이 CSV IO, PC Hann 준비,
보드 입력 양자화는 처리 시간 밖이다. CFAR 구간은 CSV 로딩 후 전력 계산·CA·피크 묶기·정렬이다.
지속 입력·큐·드랍·P99·CPU 계측은 S2에서 통합 경로로 확인한다.

원본 입력/모델·스펙트럼·실행 파일은 ignored `build/s1c_board_results_20261125_195231/`에 보존했다.
이 보고서에는 manifest·환경·실행 파일/펌웨어/모듈 SHA·로그·검출/시간 CSV·전체 원본 SHA를 보존했다.
Ubuntu의 확인은 `ubuntu_checked_summary.json`, Windows 독립 확인은 `checked_summary.json` 및
`independent_check_console.txt`다. artifact 전체와 소스8개 SHA, CPU0 로그·ABI8/실제 hardware 메타데이터도 확인했다.

E14 실행 파일 SHA `21128056810a6e195ec90f12cdea86f869108adc5f4b960669653cb615becaec`,
CFAR SHA `84ca32add47553c9d492746092aa308e41daee930470f786fcdd52cdc3f641a4`.
펌웨어/모듈 SHA는 `firmware_module.sha256`에 있다. 실제 로드된 파일의 경로에서 실행 시 해시를 기록한 근거다.
