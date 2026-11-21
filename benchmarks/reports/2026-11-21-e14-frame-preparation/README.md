# E14-frame — PL 전치·전체 프레임 경로 준비

2026-11-21. **전체 2D RTL·기존 RTL 회귀·host 53개·스크립트/설정 검증을 통과했다.**
ARM 실빌드, 생성 reset IP와 통합 Vivado 자원·타이밍, FPGA 프로그래밍, 보드 성능은 아직 확인하지 않았다.
기준 커밋은 `c776596a9dd3de62e0cb23f51fa6b6a86b9cc088`이며 추가 소스는 이 기록 시점에 미커밋 상태다.
정확한 파일 신원은 `source_sha256.json`에 있다. 기존 E13 보고서·RTL·측정 원본은 수정하지 않았다.

## 문제와 설계 선택

E13-stream 보드 profile 평균 2.880577 ms에서 PL active는 0.711424 ms였고,
사용자+커널 복사 1.352026 ms와 PS gather/scatter 0.687152 ms가 남았다.
이번 변경은 중간 DDR 왕복과 CPU 전치를 제거한다. coherent 버퍼 정책(E11d), 클록·정밀도 변경은 함께 하지 않는다.

- 기존 7단계 DIT FFT 하나를 Range와 Doppler에 재사용한다.
- Range 출력을 16,384×32-bit 행렬 RAM에 chirp-major로 저장하고 열 방향으로 Doppler에 공급한다.
- 한 열 입력의 마지막 handshake가 끝난 뒤에만 그 열의 결과를 같은 RAM에 쓴다. hard guard가 이른 결과를 차단한다.
  `overwrite_errors`는 차단된 이른 결과의 클록 수이며 정상0이다. fault injection으로 실제 차단·오류 카운트도 확인했다.
- Doppler가 끝나면 같은 RAM을 행 방향으로 읽어 기존 Doppler-major/range-minor 출력 순서를 복원한다.
- 중간/최종 행렬에 RAM 두 벌을 쓰지 않는다. 내용 reset 없이 상태만 초기화하고 정지 중 동기 RAM 출력은 유지한다.
- 1 ioctl / 2 DMA 채널 / 입출력 각각64KiB, 합128KiB/프레임이다. E13은 2 ioctl / 4채널 / 합256KiB였다.
- 최초 입력·최종 출력의 사용자/커널/coherent 복사는 유지한다. output 배열 재배열도 측정 안에 포함한다.
- Range→Doppler→drain 세 phase가 순차이며 전체 2D 프레임 간 overlap은 없다.
  기존 `frame_initiation_interval=128`은 코어의 128-point FFT **벡터** 간격이다.

Q15 butterfly·twiddle·반올림/포화·단계별1/2스케일, 50MHz, Simple DMA/HP0 64-bit/AXIS32,
CPU0·창 없음·같은 Q15 입력·전체1/16384정규화·측정 경계는 유지한다.
E14는 버퍼 위치·두 축 묶음 단위·최종 배열 복원·제출 횟수가 함께 바뀌는 데이터 경로 비교다.

## RTL 검증

명령: `python src/PL/fft128_ps/verify_dma_frame.py --skip-baseline`.
별도로 `python src/PL/fft128_ps/verify_dma_stream.py` 전체 회귀도 실행해 성공했다.

- 독립 Python 정수 모델로 만든 6종 전체 128×128 입력: 0, 원점 밖 impulse, 최대 양수 DC,
  full-scale seed 고정 random, 두 복소 tone, 실제 RadarSimPy fixture.
- 반복·오류·복구를 포함한 18개 완성 프레임, **294,912 complex bins 완전 일치**.
- 입력 starvation, 긴 외부 출력 정지, valid/data/keep/last 안정성, 마지막 beat TLAST·TKEEP 오류를 검증했다.
- 독립 AXI AW/W 지연·응답 보관, busy 중 설정/재시작 거부, 부분 요청 거부, 별도 reset 없이 반복 요청을 확인했다.
- Range·Doppler·drain 각각 soft abort와 hard reset 후 전체 재계산을 확인했다. 오래된 RAM 내용이 다음 프레임에 섞이지 않았다.
- in-place 소비 주소 scoreboard, 미소비 입력 덮어쓰기 금지, 같은 주소 read/write 충돌 없음,
  행렬 read/write 각각32768 및 두 축 입출력 각16384를 확인했다.
- 이른 Doppler 결과를 강제로 주입한 검사는 write가 차단되고 오류가 실제로 증가함을 확인한 뒤 abort했다.
- 단계별 issue/retire 각각16384, CALC 합121856, 실제 여러 stage와 여러 FFT 벡터 동시 수행, phase 합을 확인했다.

| 정지 없는 모델 | 클록 |
|---|---:|
| Range |17771|
| Doppler·열 읽기 |17771|
| 최종 행렬 순서 복원·배출 |16385|
| 합 |**51927**|

50MHz 환산은 **1.038540 ms**다. E13-stream의 두 축 RTL35540 cycles/0.710800ms보다 PL 구간은 늘었다.
CPU 전치·중간 복사 절감이 목표이며, 이 환산값은 전체 보드 지연이나 예상 가속비가 아니다.
읽기/쓰기 포트·BRAM 추론, DDR/DMA/IRQ, Linux·clock/reset 통합·최악 지연은 이 RTL 시험에 포함되지 않는다.
로그는 `frame.log`, 요약은 `rtl_result.json`이며 입력/정수 기대값 재생성 경로와 SHA는 `fixture_identity.json`에 있다.

## 호스트·설정 검증

- 기존 native/E11b/2core/4core/E12/bf2/stream 43개 + E14 10개 = **53개 PASS**.
- 실제 C 호출 경로가 한 번의 full-frame transport를 사용하고 PS 배열 전치를 하지 않는지 검사했다.
- 실제 C profile/JSON export를 분석하고, 옛 2요청/4채널 계약·CPU 전치·행렬/단계 계수 오류·phase 합 오류·NaN·잘못된 클록·중첩 시간 오류를 거부했다.
- SOFTWARE_MODEL export는 hardware 증거로 인정하지 않는다. 모델 경로만의 PASS와 FPGA 검증을 구별한다.
- ABI8·PL 전치/최종 배열 복원·64KiB 행렬·배열 순서가 다른 bundle을 거부한다.
- 기존 live DT 기록으로 만든 overlay의 compatible·주소·IRQ·새 설정 신원을 확인했다.
- userspace backend/board client는 Linux header shim으로 `-Wall -Wextra -Werror` 문법과
  header112/request131280/input112/output65648/extra131184 배치를 확인했다. 실제 ARM 빌드 대체 검사는 아니다.
- shell 문법·Python compile·Tcl `info complete`·소스 의존 경로를 검사했다.
  Vivado 2022.1의 실제 elaboration·reset IP 시뮬레이션·타이밍은 별도다.

`local_checks.json`과 각 `*_tests.log`가 근거다. 기존 E13 산술/7단계 소스의 raw SHA는 당시 준비 manifest와 일치한다.
Git의 줄바꿈 정규화 blob과 raw SHA를 혼동하지 않으며 새 E14 파일/변경 공통 파일은 LF로 보존하도록 속성을 지정했다.

## 다음 확인

1. [E14 실행 절차](../../../src/PS/fft128/dma_frame/README.md)의 Vivado Tcl을 실행한다.
   별도 run과 `build/fft128_dma_frame_latest.txt`를 사용하며 ARM 준비도 병행한다.
2. 생성 reset IP·7단계·DSP·실제 행렬 RAM 추론·50MHz setup/hold를 확인한다.
   추가 행렬은 RAMB36 약16개, E13의31개와 합 약47/60개가 자원 예산이며 **합성 실측이 아니다**.
3. ARM32 receiver/client·동일커널 모듈·overlay·source/artifact 신원을 확인한 뒤 새 번들로 배포한다.
4. 보드 자체 검사→전체 frame/20profile→각300회 paired→원본 독립 재검증을 진행한다.
   direction별 paired IRQ는330회가 예상되며, 프로파일은 별도22프레임이다.

상태: **ARM_BUILD_UNVERIFIED / VIVADO_BUILD_UNVERIFIED / BOARD_UNVERIFIED**.
비트스트림 생성만으로 완료 처리하지 않는다. 연속 UDP·무손실 실시간·크기 스윕도 이 단계에서는 미검증이다.

## 후속 구현 확인 — 2026-11-21

이후 실제 ARM/Vivado 빌드·정확한 소스/실행 파일/XSA 신원을 확인했다.
BRAM47/DSP28, 50MHz WNS10.166/WHS0.020ns와 생성 reset IP가 PASS다.
[실제 빌드 기록](../2026-11-21-e14-frame-build/README.md)에 근거를 보존한다.
위 metadata와 초기 미검증 문구는 준비 시점 상태이며 보드 전체 성능은 여전히 미확인이다.
