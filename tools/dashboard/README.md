# FMCW Radar Lab — PS / PL 시각화

프로젝트의 입력 프레임과 PS·PL 결과를 비교하는 로컬 프로그램입니다.
Windows, Linux, macOS의 Python 3.10+와 NumPy를 사용하며 프런트엔드 빌드나 인터넷 연결이 필요 없습니다.
기존 FFT, 펌웨어, 드라이버, 측정 조건과 보고서는 변경하지 않습니다.

## 실행

저장소 루트에서:

```powershell
python -m pip install -r requirements.txt
python tools/dashboard/server.py --open
```

Windows에서는 `tools/dashboard/run_dashboard.bat`를 더블클릭해도 됩니다.
브라우저에서 <http://127.0.0.1:8765>를 엽니다. 종료는 실행한 터미널의 Ctrl+C입니다.
포트가 사용 중이면 `--port 8766`을 지정하세요. 루프백에서만 수신합니다.

## 화면

- **신호 & 검출**: 같은 축과 공통 PS double peak를 기준으로 한 dB 범위에서 PS / PL 히트맵을 비교합니다.
  비교 대상으로 PS NEON을 선택할 수 있고, 오차 맵은 `PL − 선택 PS`의 복소 크기를 같은 dB 기준으로 표시합니다.
  L2 요약값은 항상 PS double 기준입니다. 로그 표시 바닥은 −70 dB입니다.
  클릭 또는 Range / Doppler bin 번호 입력으로 두 맵과 거리 단면을 함께 선택합니다.
  Doppler bin 번호는 fftshift 이전 값이며, 화면 속도 축에는 fftshift를 적용합니다.
  입력 I/Q는 원본 RF 전압이 아닌 Q15 양자화 입력 단위입니다.
- **PS · PL 아키텍처**: 7단계를 느리게 재생하고 E13의 PS 전치와 E14의 PL 행렬을 비교합니다.
  FFT 코어 1개를 Range와 Doppler에 재사용합니다. 설명용 재생은 하드웨어의 실시간 신호나 실제 시간축이 아닙니다.
- **보드 성능 기록**: 기존 E14의 각 300회 비계측 통계와 별도 20회 profile을 표시합니다.
  Host → ioctl → PL active의 중첩 관계를 분리하고 세 시간을 더하지 않습니다.
  활성 프레임에 대한 새 측정, 실시간 FPS, 연속 UDP 처리량으로 해석하지 마세요.

## 데이터와 출처

첫 화면은 `benchmarks/fixtures/radarsimpy_128x128.rspb`를 입력 SHA-256과 대조한 후 불러옵니다.
`build/fft128_dma_frame_measurements/results_e14_frame_01/{double,float_neon,pl}/trial_1.csv`가 있으면
기존 보고서의 `raw_artifact_sha256.json`과 대조해 실제 보드 저장 스펙트럼을 표시합니다.
파일이 있는데 해시가 다르면 오류로 중단합니다.

새 checkout에 ignored 원시 CSV가 없으면 NumPy double 참조와 기존 `receiver.py`의 정확한 Q15 모델로
재계산하고 **소프트웨어 모델**로 표시합니다. NEON 결과를 만들어내지 않습니다.
성능 탭의 커밋된 보드 통계는 이 경우에도 과거 기록으로 표시됩니다.

두 가지 새 입력 생성 모드가 있습니다.

- **빠른 합성 모델**: 단일 복소 beat-tone + seed 42 복소 AWGN, 거리·속도·SNR 조절.
  `f_beat = 2(B/T)R/c + 2v fc/c`, `f_doppler = 2v fc/c`를 사용합니다.
  고정 128×128, 창 없음. RadarSimPy나 RF 측정으로 표시하지 않습니다.
- **프로젝트 RadarSimPy**: `tools/sender/sender.py`의 `simulate()`를 직접 호출합니다.
  기존 패키지 탐색과 레이더 설정을 그대로 사용하고 UDP를 보내지 않습니다.
  SNR 슬라이더는 적용되지 않습니다. 패키지가 없거나 호환되지 않으면 오류를 표시하며 다른 엔진으로 몰래 전환하지 않습니다.
  양쪽 모두 PS FFT는 NumPy 참조, PL은 Q15 소프트웨어 모델입니다. 보드 성능은 측정하지 않습니다.

거리 축은 기존 프로젝트와 같이 Doppler 결합을 보정하지 않은 겉보기 거리입니다.
속도는 현재 I/Q 규약에서 음수가 접근 방향입니다. 피크 탐색은 단순 최댓값으로 CFAR·다중 표적 추적은 구현하지 않습니다.
샘플 수와 chirp 수는 E14에 맞춰 128로 고정합니다.

## CSV 가져오기와 저장

같은 Q15 입력, 창 없음, 전체 `1/16384` 정규화의 PS / PL 출력 파일을 선택하세요.
플로팅 결과는 정규화된 **Q15 입력 단위**여야 합니다. 임의의 원본 전압 단위와 혼합하지 않습니다.

PS / PL 출력은 행 순서와 무관하게 아래 인덱스로 재조립합니다.

```text
doppler_bin_unshifted,range_bin,real,imag
0,0,-2.02386474609375,0.39105224609375
...
```

PL은 `real_q15,imag_q15` 열도 지원합니다. 전체 16,384 bin이 필요합니다.
중복, 누락, 범위 밖 인덱스, NaN / Infinity를 거부합니다.
선택적인 입력 CSV 열은 `chirp,sample,real,imag`이며 Q15 입력 단위를 사용하세요.
샘플링 주파수·대역폭·chirp·PRP·중심 주파수를 입력해 물리 축을 맞춥니다.
파일당 3 MiB, 요청 전체 8 MiB 한도이며 디스크에 업로드 파일을 저장하지 않습니다.
가져온 파일은 사용자가 제공한 것으로 표시하며 원본 보드 측정이라고 인증하지 않습니다.

`현재 분석 JSON 저장`은 unshifted 복소 스펙트럼, 입력 I/Q, 축·설정·출처·정확도와 선택 bin을 내보냅니다.
이 JSON은 분석용 내보내기이며 대시보드로 재가져오기는 CSV만 지원합니다.
세션은 메모리에 최대 8개를 보관하고 페이지 새로고침 시 초기화합니다.

## 검증

```powershell
python -m unittest discover -s tools/dashboard -p "test_*.py" -v
node --check tools/dashboard/static/app.js
```

검증은 fixture·보드 스펙트럼 일치, 부호·축·peak, 원본 해시 변조, 소프트웨어 대체 출처,
CSV round-trip과 잘못된 입력, 결정적 합성 모델, profile 중첩과 HTTP 응답 경계를 확인합니다.
보드나 bitstream을 실행·변경하지 않습니다.
