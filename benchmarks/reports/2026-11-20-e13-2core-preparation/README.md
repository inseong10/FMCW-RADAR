# E13-2core 준비·로컬 검증

2026-11-20, 선행 E11b commit `6beaa8b4a207647d4d54d873ab8f03f16b066ec2`.
E11b의 PL active 비중68.1%를 근거로 기존 FFT 코어2개 복제를 먼저 적용했다.
소스 구현과 아래 로컬 검증을 완료했으며 ARM/Vivado/보드 검증은 대기 중이다.

두 unchanged `fft128_pipeline`/50 MHz/Q15/출력2clocks/sample, 공유 ordered AXIS,
두 FFT의 출력을 모두 받은 뒤 다음 pair를 시작하는 barrier다.
복제 스케줄 자체의 core0 CALC/core1 LOAD·CALC 중첩은 포함한다.
외부 버퍼·다음 pair prefetch·E12 ping-pong·E11c 출력 개선은 적용하지 않았다.
축당64 KiB/128 FFT, 프레임2 ioctl/4채널, HP0 coherent 복사와 기존 PS gather/scatter를 유지한다.

| 근거 종류 | 결과 |
|---|---|
| RTL 시뮬레이션 | 272 독립 벡터/34,816 complex bins, 1/2/3/127/128 FFT, 정지·오류·abort/recovery PASS |
| 병렬성 RTL 검사 | 두 코어 실제 CALC 동시 상태·pair barrier·busy/work-window 카운터 불변식 PASS |
| 호스트 회귀 | native9개, E11b 도구3개, 새 CSV export/analyzer4개 PASS |
| 정적 도구 검사 | Python compile, shell9개 syntax, 기록 DT 기반 overlay 생성·compatible PASS |
| 코어 동일성 | E11b/E10 산술·RAM·주소·native model6파일 LF 정규화 SHA 동일 |
| ARM/Vivado | 미실행. 실제 생성 IP/reset, route/timing/resources/DSP8개 및 kernel CRC는 미확인 |
| 보드 성능 | 미측정. 최신 검증 보드 기준은 E11b PL 중앙값6.433026 ms |

`verify_dma_parallel.py`는 먼저 E11b→E11a→기존 serial/pipeline 검증을 실행한다.
최초 전체 실행 후 카운터 합집합·실제 CALC와 work-window 차이 assertion을 강화하고
새 TB를 재컴파일/실행해 통과했다. `dma_parallel_ctrl_tb.log`는 강화된 최종 TB 결과다.
`source_sha256.json`은 그 최종 소스의 정규화/원시 SHA, `evidence_sha256.json`은 근거 파일 SHA다.

무정지 입력 시나리오128 FFT는 테스트 초기 input starvation20cycles를 포함해71444cycles다.
이를 제외하면 pair1116cycles·axis71424·frame142848cycles = **2.856960 ms/50 MHz**다.
E11b nonstall4.408320 ms 대비 약1.543배의 **사이클 기반 내부 가설**이다.
초기 전체 내부 반감2.204160 ms보다 길며 공유 입출력의 직렬 구간이 남는다.
새 보드 프레임 시간·자원·타이밍·CPU 대비 우위는 이 계산으로 입증하지 않는다.

무정지128 FFT의 실제 CALC 겹침22272cycles/axis, work-window22336cycles/axis다.
work-window는 CALC와 최초 output RAM 읽기 지연을 포함한다. 차이는 pair당 최대1cycle이다.
보드 profile은 frame work-window에서128cycles를 뺀 동시 CALC 보수적 하한이 양수인지 검사한다.
global과 per-core busy는 겹친다. 입력·출력 stall도 서로 다른 코어에서 겹칠 수 있으므로
두 합을 빼서 순수 compute 시간으로 해석하지 않는다.

원시 로그와 결과 JSON은 이 폴더, 시뮬레이션 실행 파일/벡터는 ignored
`build/fft128_dma_parallel_verify/`에 있다. 새 Vivado run/firmware/measurements는 각각
`build/vivado/fft128_dma_e13_2core_*`, `build/fft128_dma_parallel_bundle`,
`build/fft128_dma_parallel_measurements`에 분리한다.

다음은 Vivado Tcl source로 FPGA와 ARM 빌드를 시작하고, 보고서·소스/artifact SHA를
확인한 뒤 보드 self-test→full frame/profile→PS double/NEON/PL 각300회 paired 비교다.
이전 VMware UI 입력이 반영되지 않아 Tcl 실행은 사용자에게 요청한다.
[실행 명령·보드 경로](../../../src/PS/fft128/dma_parallel/README.md),
[실험 일지](../../../docs/experiment_log.md).

후속: ARM/Vivado·보드 자체 검사·전체 프레임/profile/각300회 paired 비교와
원본 독립 검증을 완료했다. [최종 보드 결과](../2026-11-20-e13-2core-board/README.md).
위 대기 문구는 로컬 준비 당시 상태를 보존한다.
