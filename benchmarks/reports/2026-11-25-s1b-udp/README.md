# S1b — 실제 UDP 한 프레임 수신 (2026-11-25, 원본 독립 검증 완료)

최초 증거는 **사용자가 붙여넣은 보드 콘솔**이었다. 성공한 마지막 실행 블록만 `console_success.txt`에 보존했다.
과거 실행의 암호 입력·셸 오타는 복사하지 않았다. 아래 초기 판단 뒤 원본 FFT·검출·시간 CSV를 회수하고 독립 검증했다.

보드10.0.0.3, 송신자10.0.0.2:41915, 128×128/fs1.6MHz, CPU0·double FFTW3.3.11,
Hann·CA guard=(2,2)/train=(8,8)/Pfa1e-6, warmup0/repeat1.
중복·invalid·ignored는 모두0이고 CFAR 피크4였다. 피크 bin은(Doppler10, Range10).
전체 검출 bin 목록은 콘솔에 없어 최초에는 정답4/4 일치를 확인하지 못했다.

콘솔 수치: FFT pipeline5.964432ms, CFAR3.890856ms, processing_total10.884054ms.
첫~마지막 패킷335.079279ms이며 receive_total에는 송신 시작 전 대기도 포함된다.
UDP·할당·plan·CSV 저장은 processing_total 밖이다. 단일 프레임 기능 확인이며 연속 처리·P99 합격 근거가 아니다.

출력 경로는 보드 시계에 따라 `/opt/fft128/s1b_20261125_192718/udp_multi4_hann_20180309_135527/`이다.
이 2018년 표기를 실제 측정 날짜로 해석하지 않는다. 원본 회수 후 NumPy 기준·기존 보드 기록 재생 결과와 대조한다.

## 원본 회수와 최종 판정

Ubuntu에서 복사한 원본4파일을 Windows의 ignored `build/s1b_udp_multi4_hann_20261125_01/`에 보존했다.
로그·검출 CSV·시간 CSV는 이 보고서에도 보존했다. 전체 스펙트럼 CSV의 SHA와 독립 재계산 결과는
`independent_validation.json`에 있다. 최초 콘솔만의 미확인 판단은 `console_summary.json`에 유지했다.

- FFT16384개 bin을 NumPy와 대조했다. 최대 복소 오차 `1.9860273225978185e-15`, 상대L2 `4.695164787484549e-16`.
- 같은 입력·Hann의 기존 보드 기록 재생과 FFT CSV의 수치 배열이 정확히 일치하고 검출 CSV는 바이트 단위로 같다.
- 검출 순서는 `(Doppler,Range)=(10,10),(107,20),(4,37),(87,53)`이다. 정답4/4·오검출0이며
  피크 전력·임계값·거리/속도 환산도 대조했다.
- 수신 decode·reassembly는 각128개 표본, FFT/CFAR/processing_total은 각1개다.
  로그의 duplicates/invalid/ignored는 모두0이다.
- CFAR3.890856ms/processing_total10.884054ms는 워밍업 없는 단1회의 보드 측정이다.
  송신 간격을 둔 프레임 수신이며 end-to-end 지속 처리·드랍·P99 합격으로 해석하지 않는다.

**S1b 완료:** 기준 검출의 보드 재현·CFAR 비용 측정과 실제 UDP 한 프레임 수신 경로를 확인했다.
기존 CA의 근접 약표적 미검출 한계는 그대로이며 모든 시나리오의 검출 정확성 목표를 달성했다는 뜻은 아니다.
다음은 S1c에서 보드 Q15 규칙과 Hann 적용 위치를 명시해 E14 PL 출력의 검출을 대조하는 것이다.
