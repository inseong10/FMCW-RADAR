# E11b — 축당 128 FFT 묶음 제출

2026-11-19. 기존 E11a의 50 MHz 단일 코어/Q15/2클록 출력과 coherent bounce 복사 정책을 유지한다.
프레임당 ioctl 2회, DMA 채널 제출 4회, 입력/출력 각 축당 65,536 B다.
전송과 연산의 벡터 간 겹치기(E12)는 포함하지 않는다.

로컬 RTL: `python src/PL/fft128_ps/verify_dma_batch.py` PASS.
272개 독립 숫자 벡터를 포함한 128-FFT 패킷, 1/2/128개 요청, AXIS 정지,
TLAST/TKEEP 오류, load/compute/stalled-output abort 후 복구와 기존 E11a 회귀를 확인했다.
active - input_stall - output_stall = 110,208 cycles/axis (861/FFT).
이는 RTL 시뮬레이션이며 AXI DMA IP/DDR/IRQ/커널/보드 검증은 아직 아니다.
독립 host 회귀 3개·기존 native 회귀 9개, 명시적 model 전체 프레임 CLI와 기록 DT 기반 overlay 소스 생성도 PASS다.
Vivado/ARM 빌드와 보드 측정은 실행 대기 중이다. 컴퓨터 제어 도구의 VM 입력이 반영되지 않아
사용자에게 Vivado Tcl source 명령 실행을 요청했다. 해당 명령은 독립 ARM 빌드도 함께 시작한다.
코어/산술/RAM/주소 생성/native 정수 모델 6개 파일은 E11a/E10 기준의 LF 정규화 SHA와 일치한다.
 E11a 15.411639 ms는 과거 기준이며 새 측정값이 아니다.

후속: ARM/Vivado 빌드 및 source/artifact 신원 검증을 완료했다. [빌드 보고서](../2026-11-19-e11b-build/README.md). 보드 실행·측정은 아직이다.
