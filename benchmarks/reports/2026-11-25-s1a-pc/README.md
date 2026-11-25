# S1a — PC CFAR 기준 모델과 ground truth (2026-11-25)

증거 종류: **PC 시뮬레이션** (macOS, Python 3.13.5, NumPy 2.1.3, 프로젝트 동봉 RadarSimPy 15.5.0 free tier).
보드 실행은 없다.

```bash
python3 tools/detection/cfar_reference.py --out <dir>
```

- 파일: `summary.json`(모든 실행의 검출·오검출·프레임 SHA256), `console.txt`, `scenarios.json`,
  `source_sha256.txt`. 프레임·전력 맵 `.npy`는 결정적으로 재생성되므로 저장하지 않았다.
- 같은 명령을 두 번 실행해 콘솔 출력과 7개 프레임 SHA256이 모두 일치함을 확인했다.
- 고정 기록 SHA256 `aa06ff12…c976`. 그 외 시나리오는 단일 표적 실행의 합(무료판 표적 2개 제한)이다.

조건: map[doppler, range], fftshift 없음, square-law, guard (2,2), train (8,8), Pfa 1e-6,
Doppler 축 원형, Range 가장자리는 CA=가용 셀 평균 / OS=reflect, OS k = 0.75N, 3×3 지역 최대로 피크 묶기,
판정 ±1 bin. 결과 표는 [실험 일지 S1a](../../../docs/experiment_log.md#s1a--cfar-기준-모델과-ground-truth)에 있다.
