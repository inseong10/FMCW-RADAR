# E11a DMA 설계 합성·구현 결과

2026-11-16, 공유 폴더의 실제 Vivado 2022.1 산출물을 확인했다.
run: `build/vivado/fft128_dma_e11a_20261116_005936`.
**bitstream/XSA·구현 타이밍과 보드 DMA 자체 검사를 통과했다. 이후 전체 프레임·성능도
[E11a 보드 보고서](../2026-11-16-e11a-board/README.md)에서 검증 완료했다.**

| 항목 | E10 MMIO/50 MHz | E11a DMA/50 MHz |
|---|---:|---:|
| LUT | 1,364 / 17,600 | 3,210 / 17,600 |
| FF | 1,048 / 35,200 | 3,987 / 35,200 |
| BRAM tile | 2.5 / 60 | 5 / 60 |
| DSP | 4 / 80 | 4 / 80 |
| setup WNS | 9.807 ns | 10.607 ns |
| hold WHS | 0.034 ns | 0.021 ns |

E11a에서 setup/hold 위반 endpoint는 모두 0, unconstrained internal endpoint도 0이다.
클록 보고서에서 보드 125 MHz → MMCM 50 MHz/20 ns를 확인했다.
클록을 올린 실험이 아니며 slack의 차이를 처리 속도 개선으로 해석하지 않는다.
DMA/인터커넥트·제어 회로를 추가하면서 자원이 늘었고 기존 FFT DSP 4개는 유지됐다.

실제 저장 BD에서 Simple DMA/SG off/DRE off, 메모리 64-bit/stream 32-bit,
burst 16/length width 17, AXIS 양방향 연결과 HP0 DDR 1 GiB 매핑을 대조했다.
FFT 제어 0x43c60000, DMA 0x40400000, MM2S/S2MM IRQ→F2P6/7 연결도 확인했다.
PS FCLK/reset 포트 의존은 없다. PS 설정의 CPU 주파수 값을 실제 부팅 CPU 클록 측정으로 쓰지 않는다.

`implementation.json`에 자원/타이밍, bitstream/XSA/BD 해시와 크기를 저장했다.
`source.sha256`의 모든 소스를 현재 공유 소스와 대조해 일치했고, ARM 수신기·모듈의
각 source manifest도 일치했다. bitstream은 ignored build에 보관한다.
`bd_contract_checked.json`, `timing.rpt`, `utilization.rpt`, 실제 생성 reset IP 통과 기록을 함께 보존한다.

다음: raw firmware 변환/전용 E11a bundle 배치 → FPGA/DT/module 적용 →
DMA ABI/4벡터 자체 검사 → 전체 프레임 → 별도 profile → PS double/NEON과 비계측 비교.
기존 [준비 단계·커널 CRC 검사](../2026-11-16-e11a-preparation/README.md),
[실험 일지](../../../docs/experiment_log.md), [보드 실행 절차](../../../src/PS/fft128/dma/README.md).

## 최초 보드 적용: DMA client 연결 실패

사용자 콘솔에서 20개 artifact 검사 OK, HP0 read/write 64-bit 설정,
raw BIN FPGA Manager 로드(51 ms)를 확인했다. overlay 적용 시 __symbols__ 제거 관련
경고가 출력됐고, 모듈 로드 뒤 `/dev/fft128-dma`가 없어 activation을 중단했다.
DMA 자체 검사·프레임·시간 측정은 시작하지 않았다. 경고를 바인딩 실패 원인으로 단정하지 않는다.
`first_activation_console.log`와 실제 bundle 해시를 보존했다.
다음은 실제 platform device 생성 여부와 dmesg를 확인해 DT/드라이버 연결을 진단하는 것이다.
FPGA 재합성은 이 단계에서 결정하지 않는다.

### DT 등록 구조 수정 v2

후속 사용자 조회에서 platform device는 `fft128-e11a-bus`와 `fft128-e11a-clock`뿐이었다.
새 버스 아래 DMA/FFT가 등록되지 않았음을 확인했고 기존 `/amba_pl`에 DMA/FFT 노드를
직접 추가하도록 수정했다. 원래 `/amba_pl`의 simple-bus·1/1 cells·identity ranges도 조회 파일로 대조했다.
커널의 동적 장치 생성은 부모의 OF_POPULATED_BUS 상태를 검사한다.
[해당 커널 코드](https://github.com/Digilent/linux-digilent/blob/5e8c35eccbabeb08a63f55f18fec677a685c30b3/drivers/of/platform.c#L669).

최초 `first_overlay.dts`와 실패 artifact를 보존했다. 새 출력은
`build/fft128_dma_host_dt_v2` 및 `build/fft128_dma_bundle_dt_v2`로 분리한다.
raw BIN 동일성 비교를 통과해야 배치하며 RTL·클록·DMA 설정·커널 모듈 변경이나 재합성은 없다.
12개 PC DT/CLI/계측 분석 검사를 통과했다. 새 DT의 Ubuntu offline 적용 산출물은
`dt_v2_fft128_e11a.dts`, `dt_v2_artifacts.json`에 보존했다.

### DT v2 보드 적용: DMA 자체 검사 통과

사용자가 `sudo sh /opt/fft128/e11a/retry_overlay_board.sh`로 재적용한 콘솔에서
21개 artifact 검사 OK, AXI DMA 드라이버 probe와 `43c60000.fft` 클라이언트 연결을 확인했다.
`DMA_CLIENT_PASS`는 단일 소유권, 잘못된 ABI/timeout/flags/ioctl 거부, 유효 impulse 처리를 포함한다.
이어 실제 `PL_DMA` backend가 4벡터·512개 bin 자체 검사를 통과했다.
이는 콘솔 근거이며 전체 128×128 프레임의 정확도·시간 측정 완료를 의미하지 않는다.

`dt_v2_selftest_console.log`에 핵심 원문, `dt_v2_selftest.json`에 검증 범위와 bundle 신원을 남겼다.
BIN·모듈·수신기·ABI 검사기는 최초 bundle과 byte 단위로 같고 DT 등록 구조만 바뀌었다.
FPGA Manager의 49 ms는 펌웨어 로드 시간이며 FFT 성능값으로 사용하지 않는다.
overlay 제거 시 __symbols__ 누수 경고는 여전히 출력됐으나 이번 장치 연결과 자체 검사는 통과했다.
다음은 20회 전체 프레임 프로파일 후 별도 비계측 PS double/NEON/PL 각 300회 비교다.

### 최초 전체 프레임 프로파일 통과 (콘솔 근거)

`profile_e11a_01`은 CPU0, warmup 2/repeat 20으로 실행됐고 실제 `PL_DMA`의
16,384 bin 정수 모델 검증과 피크 (107,20)을 통과했다.
평균 18.136317 ms / 중앙값 18.129750 ms, 최소 18.071028 / 최대 18.224922 ms다.
계측 포함 별도 실행이므로 최종 비계측 paired 결과와 구분한다.
원문은 `first_frame_profile_console.log`이며 원시 CSV 회수·독립 분석은 아직 대기 중이다.

콘솔 평균은 host ioctl 15.199543 ms, 그 안의 kernel copies 합 1.004211 ms,
kernel wait 9.406124 ms, PS gather/scatter 1.002013 ms, PL active 4.482577 ms다.
kernel·PL 구간은 ioctl에 포함되므로 서로 더하지 않는다. PL active는 스트림 정지를 포함하며
순수 butterfly 계산 시간이 아니다. wait에는 DMA 완료·IRQ·스케줄링 비용도 섞인다.
기존 E10의 별도 계측 실행 평균 27.327809 ms보다 짧게 관찰됐으나 같은 회차의 paired 비교가
아니고 계측 영향도 있어 확정 성능 가속비로 사용하지 않는다.
