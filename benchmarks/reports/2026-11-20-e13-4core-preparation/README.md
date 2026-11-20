# E13-4core 준비·로컬 검증 — 2026-11-20

E13-2core의 PL 중앙값4.920621 ms/별도 profile active2.857541 ms,
전체 중 active57.45%를 근거로 사용자가4코어 실험을 선택했다.
소스 구현·로컬 검증을 완료했고 ARM/Vivado 및 보드 측정은 대기 중이다.

## 고정과 변경

동일 fft128_pipeline4개/50 MHz/Q15/출력2clocks/sample을 사용한다.
2개 pair barrier를4개 group barrier로 확장해 네 결과를 원래 순서로 모두 배출한 뒤
다음 묶음을 시작한다. 외부 버퍼·다음 group prefetch·E11c 출력 개선·E12 ping-pong은 없다.
1..128 FFT 및 불완전 group을 지원한다.
HP0 64bit/AXIS32/Simple DMA/SG·DRE off/burst16/length17,
64 KiB/axis/direction·2 ioctl/4채널·PS gather/scatter·coherent 복사 단계를 고정했다.

별도 `fft128_dma_quad_ctrl.v`와 `dma_quad/` ABI4/모듈·수신기·실행 도구를 추가했다.
ID0x46545084, compatible quad-v4, register0x30 core-count4다.
UAPI header112 B와 input/output offset112/65648은2코어와 같게 유지했다.
추가 profile counters24 B를 기존 payload 뒤에 두어 request는131208 B다.
새 카운터는 각 core busy·시간 합집합·2개 이상/4개 모두 busy/work-window·출력 arbitration이다.
제어·계측 추가와 ABI 변경은 실험에 수반되지만 산술·복사 payload와 정책은 고정했다.

## 근거 종류와 결과

| 범위 | 결과 |
|---|---|
| 기존 회귀 | 2코어→E11b/E11a→serial/pipeline RTL 회귀 PASS |
| 새 RTL | 272 독립 벡터/34,816 complex bins, 1/2/3/4/5/6/7/127/128 FFT PASS |
| 전송·오류 | AXI AW/W 분리·응답 정지, AXIS 공백/역압/정지 payload, malformed TLAST/TKEEP PASS |
| 복구·경계 | 부분 lane2 LOAD, 실제4코어 CALC, stalled lane3 OUTPUT 중 abort/recovery·불완전 group·다음 group 차단 PASS |
| 실제 병렬성 | 무정지 입력에서4코어 CALC 동시 상태 직접 확인; source-starved CALC 겹침0에서도 정확한 완료 PASS |
| 호스트 회귀 | native9/E11b tools3/2코어 tools4/4코어 tools5 = 21개 PASS |
| 도구 정적 검사 | Python compile·shell10개 syntax·Tcl 구문 완료·기록 DT overlay 생성·옛2코어 artifact 오인 수용 거부 PASS |
| 산술 동일성 | 기존 산술/RAM/주소/native model6파일 LF 정규화 SHA 동일 |
| 미확인 | 실제 ARM build/ABI static assertions·module CRC·Vivado generated IP/route/50 MHz·자원/DSP16·보드 성능 |

전체 `verify_dma_quad.py` 실행은 기존 회귀와 새 TB를 통과했다. 이후 lane2 부분 입력 및
lane3 출력 정지 abort 검사를 보강해 새 TB만 재컴파일/실행했고 최종 PASS 로그를 보존했다.
최종 test source·결과/로그의 신원은 source_sha256.json과 evidence_sha256.json에 기록한다.
호스트4코어 테스트는 실제 native CSV 작성기를 컴파일해 analyzer 입력과 연결한다.
1/2코어 설정·거짓4코어 CALC·불가능한 busy 합·잘못된 group 기포·중첩 시간 오류를 거부한다.

## 사이클 계산, 보드 성능 아님

초기 테스트 input starvation20cycles를 포함한128 FFT는52052cycles/axis다.
20을 제외하면1626cycles/group·52032/axis·104064/frame,
50 MHz **2.081280 ms**로2코어 모델2.856960 ms 대비 **1.372694배** PL 내부 개선 계산이다.
새 전체 프레임 지연·NEON 우위·자원량은 측정하지 않았다.

무정지128 FFT의 all-work2976/actual all-CALC2944cycles/axis,
multi-work19360/actual multi-CALC19328cycles/axis를 확인했다.
work-window는 마지막 입력부터 첫 출력 valid 전까지라 초기 output RAM 읽기 지연도 포함한다.
full frame4코어 실제 CALC 겹침의 보수적 하한은 all-work−64,
2개 이상 CALC 겹침은 multi-work−256cycles다. 보드 검사는 하한 양수를 요구한다.
busy 합집합과 global 차이는 group당1cycle/full frame64cycles다.
input/output stall 합은 lane 간 겹칠 수 있으므로 순수 compute 환산에 사용하지 않는다.
source-starved 기능 검사는 계산이 겹치지 않아도 정수 결과가 정확히 완료되어야 한다.

## 다음 실행

Vivado Tcl에서 build_dma_quad.tcl을 source하면 독립 ARM build도 시작한다.
새 run/host/module/bundle/measurement는 `fft128_dma_quad_*`, 보드 배포는 `e13_4core`다.
E13-2core firmware/bundle/raw 결과는 보존한다. 새 FPGA를 적용하기 전 기존 DMA 모듈과
overlay가 활성화되어 있으면 보드를 재부팅한다.
실제 Vivado reset·setup/hold·50 MHz/DSP16개, ARM ABI/CRC 확인→보드 자체 검사→
full frame/profile→PS double/NEON/PL 각300회 paired 비교를 순서대로 검증한다.

VMware 입력 도구가 반영되지 않는 기존 제한으로 Tcl 실행은 사용자에게 요청한다.
[명령과 보드 절차](../../../src/PS/fft128/dma_quad/README.md),
[선행2코어 실제 결과](../2026-11-20-e13-2core-board/README.md),
[실험 일지](../../../docs/experiment_log.md).

후속: 실제 ARM/Vivado 빌드·ABI static assert·DSP16개·50 MHz setup/hold·source/artifact
검증을 완료했다. [빌드 근거](../2026-11-20-e13-4core-build/README.md).
위 대기 문구는 로컬 준비 당시 상태를 보존한다. 보드 실행·측정은 아직 대기다.

최종 후속: 보드 자체 검사·실제 DMA4코어 동시 계산·전체 프레임/profile/각300회 paired 비교와
원본 독립 검증을 완료했다. [최종 보드 결과](../2026-11-20-e13-4core-board/README.md).
