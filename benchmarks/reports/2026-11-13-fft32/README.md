# E01–E02: 32-point FFT 보드 검증 근거

[전체 실험 일지](../../../docs/experiment_log.md)의 E01–E02에 해당한다.
검증된 로컬 run `build/vivado/validated_20261113_173240/`에서 작은 원본 결과를 복사했다.
FPGA 자체 검사의 범위는 5벡터/160 complex bin이며 레이더 UDP 경로와 별개다.

- `hardware.txt`: 실제 JTAG/VIO 결과 `done=1 passed=31 errors=0`.
- `simulation_upstream.txt`, `simulation_zybo.txt`: 원본/보드용 RTL 검사 결과.
- `multiplier_equivalence.txt`: 589,825개 비교.
- `netlist_post-synthesis_functional.txt`, `netlist_post-implementation_timing.txt`: netlist 검사.
- `timing.rpt`, `utilization.rpt`: 실제 구현 타이밍·자원 보고서.
- `original_artifact_sha256.json`: 복사 전 원본 텍스트 바이트의 해시. Git의 줄바꿈 정규화와 구분한다.

최종 setup 5.156 ns, hold 0.043 ns, DSP 64/80. 초기 `place_design ERROR`의 상세 실패
보고서는 이 폴더에 없으므로 그 최초 실패의 원인을 최종 자원량만으로 확정하지 않는다.
수정 과정과 캡처 스케줄 재현은 [보드 검사 설명](../../../src/PL/zybo_fft_test/README.md)을 참고한다.
`.bit`·`.ltx`·Vivado 프로젝트는 기존 로컬 run에 유지한다.
