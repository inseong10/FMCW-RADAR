# E05–E06: reset 원인 재현과 실제 보드 기능 검증

[전체 실험 일지](../../../docs/experiment_log.md)의 E05–E06에 해당한다.
최종 V3 run은 `fft128_ps_20261115_203251`이다. 보존 원본은
`build/vivado/fft128_boardreset_v3_20261115_203251/`, `build/fft128_reset_debug/`,
`build/fft128_pl_integration/`에 있다.

- `old_wiring.log`: 생성된 reset netlist의 기존 보조 reset 연결로 정지를 재현한 PC 시뮬레이션.
- `old_ip_aux_released.log`: 보조 reset을 해제한 동일 IP에서 ID 응답·복구 확인. 보드 실측과 구분한다.
- `reset_simulation.txt`: 수정된 실제 생성 reset IP와 AXI ID·lock-loss 복구 검사.
- `clock_source.txt`, `timing.rpt`, `utilization.rpt`, `sha256.json`: 최종 V3 구현·펌웨어 식별.
- `board_selftest.json`, `board_frame_console_result.json`: 사용자가 제공한 실제 보드 콘솔 근거.
- `board_numpy_validation.json`, `board_numpy_validation.log`: 수집한 실제 입력·출력의 독립 검증.

최종 20 MHz 설계는 setup 32.177 ns, hold 0.052 ns이다. 보드 4벡터/512 bin 자체 검사와
128×128 전체 프레임 16,384 bin 검사를 통과했다. 단일 82.024044 ms는 초기 실행 값으로,
사전 할당 후 300회씩 측정한 [E08 기준선](../2026-11-15-zybo128/README.md)과 구분한다.
`original_artifact_sha256.json`은 V3 run에서 가져온 보고서의 원본 바이트 해시다.
