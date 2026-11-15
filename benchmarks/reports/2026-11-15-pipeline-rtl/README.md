# E10: 파이프라인 RTL 검증, 보드 실험 대기

[전체 실험 일지](../../../docs/experiment_log.md)의 E10에 해당한다.
실행 명령은 `python src/PL/fft128_ps/verify.py`다. 이 폴더의 원본 로그는 해당 명령이
`build/fft128_verify/`에 생성한 것으로, 기존 serial과 새 pipeline을 같은 참조 벡터로 검사했다.

- `stream_tb_*`: 16벡터, backpressure·TLAST·reset 검사.
- `axi_tb_*`: 각 구성 272 FFT/34,816 bin, AW/W 순서·응답 지연·오류 접근,
  계산 중 abort 후 재실행 검사. 추가 재실행 확인은 기본 272벡터 수에 포함되지 않는다.
- `CYCLE_PASS`: serial=3,073 / pipeline=861 cycles per FFT.
- `result.json`: 두 경로의 결과와 독립 NumPy 비교.
- `source_snapshot.json`: 당시 기준 커밋과 **커밋되지 않은 개선 소스**의 파일 SHA256.
- `original_artifact_sha256.json`: 원본 로그 바이트 해시. Git 줄바꿈 정규화와 구분한다.

이 결과는 PC RTL 시뮬레이션이다. **50 MHz Vivado 구현 타이밍·자원·실제 보드 성능은 미확인**이다.
861×256/50 MHz = 4.40832 ms는 PL 내부 구간의 계산값이며 실제 전체 처리 시간이 아니다.
파이프라인은 연산 단계들을 겹치지만 FFT 코어 여러 개나 DMA를 구현한 것은 아니다.
실행·검증 순서는 [최적화 절차](../../../docs/fft128_optimization.md)를 참고한다.
