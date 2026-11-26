# S2b-int16 예비 검사 — ADC int16 입력, 12.8ms/200프레임 (2026-11-26)

선행: [S2a-int16](../2026-11-26-s2a-int16/README.md) (보드50ms/20 진단 PASS).
이 디렉터리는 **200프레임 예비 검사**다.10,000프레임 합격 근거나 최대 FPS 추정에 쓰지 않는다.

## 조건

| 항목 | 값 |
|---|---|
| 입력 | `benchmarks/fixtures/adc16/radarsimpy_128x128_sim_multi4_noise_adc16.rspb`, SHA256 `d3d5160c…b6b91cf` |
| 프로토콜 | v3/dtype2/profile1, ADC16, S=1,600,000, 568B×128패킷/프레임 |
| 수신기 | `/opt/fft128/s2a_int16_20261126_adc01/stream-receiver`, SHA256 `72396cb0c1abcf6f831d5d00a0fc7d75618c2e8333d2ff99402b3163ca8d28f0` (artifact_check 5개 OK) |
| wrapper | `run_board.sh … measure` (첫 패킷 probe·spectrum 진단 끔), Hann 수신기 내부, warmup10, queue4/partial4, CPU0-1 online/allowed, `--cpu0` 없음 |
| PS | double/O2/FFTW ESTIMATE, single worker |
| PL | E14 ABI8 `/dev/fft128-dma-frame`, 사용자 선택100MHz 번들 |
| 송신 | `replay_stream.py --period-ms 12.8 --wait-mode spin`, chirp gap0 프레임별 burst |
| 클럭 문맥 | 양 실행 `clock_before/after`가 S2a-int16 진단과 바이트 동일(같은 boot ID). 설정값 문맥이며 주파수 실측이 아님 |

| run | 출력 | sender JSON SHA256 |
|---|---|---|
| PS 92311 | `ps_prelim_01` | `4a4547fa…a0748` |
| PL 92312 | `pl_prelim_01` | `1bba723d…7833e` |

원본: 사용자가 `/nfsroot`→공유 `build/s2a_int16_board_prelim_20261126_adc01`로 회수, Windows
`build/s2a_int16_board_prelim_20261126_adc01`에 복사 후 `diff -r` 동일 확인. 이 디렉터리의 `*_raw/`는 수신 원본 사본이다.

## 결과 (보드 원본, Windows `check_adc16_stream.py` 독립 재계산)

| 지표 | PS 92311 | PL 92312 |
|---|---|---|
| receiver exit | **2** | 0 |
| 처리/기대 | **194/200** (`queue_full` 6: 69,92,114,133,153,179) | 200/200 |
| zero_drops | **false** (`--allow-loss` 분석) | true |
| 패킷 수신 / 오류 카운터 | 25600 / 전부0 (kernel_drops0) | 25600 / 전부0 |
| 송신 overrun / 최대 지연 | **1** / 5.041713ms → offered_load_valid=false | 0 / 0.008012ms |
| 정확도 (처리 프레임 전부) | 4/4, 오검출0 | 4/4, 오검출0 |
| 큐 깊이(입력 시) | 0:9, 1:22, 2:17, **3:146** | 0:200 |
| 큐 대기 중앙/P99 ms | **43.530 / 53.119** | 0.099 / 1.535 |
| prepare 중앙/P99 ms | 0.556 / 2.835 | 2.423 / 2.505 |
| FFT/전송 중앙/P99 ms | 6.162 / 7.900 | 1.214 / 1.381 |
| power+CFAR 중앙/P99 ms | 5.077 / 7.799 | **8.368 / 9.103** |
| 출력 flush 중앙/P99 ms | 0.219 / 1.316 | 0.205 / 0.298 |
| 조립완료→출력 P99 ms | 66.415 | 14.024 |
| **첫 커널 패킷→CSV flush 중앙/P99 ms** | 61.575 / **71.097** | 17.235 / **19.135** |
| 첫 커널 패킷→조립완료 중앙/P99 ms | 4.751 / 11.787 | 4.756 / 6.864 |
| 프로세스 CPU(한 코어 %, 활성 표본 중앙/최대) | 136.0 / 141.2 | 126.8 / 130.1 |
| RSS 최대 | 5.21MiB | 3.90MiB |

보조 분석 [`prelim_supplement.json`](prelim_supplement.json)은 frames/resources/sender 원본에서 계산했다.

## 판정

- **PS 12.8ms: 불합격.** 드랍6, 큐가 대부분 3으로 포화, 지연이 프레임마다 증가(18→~60ms).
  송신 overrun1이 있어 부하 유효성도 실패지만, 처리 합계(중앙 약12.0ms)와 큐 포화로 보아 수신기 포화가 주 원인이다.
- **PL 12.8ms: 처리량은 유지, 지연 기준 불합격.** 드랍0·오류0·정확도 유지·큐 안정이지만
  첫 커널 패킷→출력 P99 19.135ms > 12.8ms (200프레임 전부 12.8ms 초과).
- 두 경로 모두 12.8ms/10,000 본검사(92321/92322)는 실행하지 않는다.

## 관찰과 가설 (미검증)

- PL power+CFAR가 50ms 진단(중앙6.099ms)보다 2.27ms 길다. 199/200 프레임의 CFAR 구간이 다음 프레임 패킷 수신과
  겹쳤고(중앙8.369ms), 겹치지 않은 1프레임은6.033ms였다. 수신 스레드와의 CPU/메모리 경합 **가설**이며 원인은 확인하지 않았다.
  PS도 겹침83프레임 중앙7.367ms / 비겹침111프레임 5.014ms다.
- 지연에는 첫 패킷→조립완료 약4.75ms(VM 송신 burst 72,704B)가 포함된다. 측정 정의는 바꾸지 않는다.
- 50ms 진단의 첫 커널 패킷→출력 P99(PS24.203/PL16.890ms)는 경합이 적은 조건의 값이므로,
  그보다 짧은 주기에서는 합격이 불가능하다. 다음 주기 선택의 하한으로만 사용한다.

## 새 실시간 기준 병기 (2026-11-26 사용자 결정 이후, 같은 원본)

기준이 P99(조립완료→CSV flush) < 주기로 바뀌었다([S2b-pace](../../../docs/experiment_log.md#s2b-pace--실제-chirp-간격-송신과-조립완료-기준)).
이 두 run은 burst 송신 조건이며 재측정하지 않았다.

| run | 조립완료→출력 P99 | 새 기준(12.8ms) | 첫 커널 패킷→출력 P99(보조) |
|---|---|---|---|
| PS 92311 | 66.415ms | 미달 (드랍6도 존재) | 71.097ms |
| PL 92312 | 14.024ms | 미달 (1.22ms 초과) | 19.135ms |
