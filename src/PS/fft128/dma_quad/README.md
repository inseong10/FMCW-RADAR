# E13-4core: 기존 FFT 코어4개

상태(2026-11-20): RTL·host·ARM/Vivado·보드 자체 검사·전체 프레임·별도20회 profile·
각300회 paired 비교와 원본 독립 검증 PASS. 실제4코어 CALC와50 MHz/DSP16개를 확인했다.
중앙값 PL4.186353/double5.767911/NEON3.649998 ms, 과거2코어보다 지연14.92% 감소다.
PL active 평균2.081883 ms, 복사합1.324075 ms, PS 전치0.685061 ms다.
[최종 보드 결과·원본](../../../../benchmarks/reports/2026-11-20-e13-4core-board/README.md).

## 변경 범위

코어 수를2→4로 확대하고 네 FFT의 입력을 lane0→1→2→3에 분배한다.
출력도 같은 순서로 내보내며 네 결과를 모두 수락한 뒤 다음 묶음을 시작한다.
1..128 FFT와 마지막1/2/3개 불완전 묶음을 지원한다.
E13-2core의 pair barrier를4개 group barrier로 확대한 구조이며 외부 버퍼·다음 group
prefetch·E12 ping-pong·E11c 출력 개선을 추가하지 않았다.

동일 fft128_pipeline/50 MHz/Q15/출력2clocks/sample과 산술·RAM·주소 생성 소스를 사용한다.
HP0 64bit/AXIS32bit/Simple DMA/SG·DRE off/burst16/length17,
축당128 FFT/64 KiB·프레임2 ioctl/4채널·PS gather/scatter·복사 단계를 유지한다.
산술6파일과 PS gather/scatter는 기존 검증 소스와 같다.

## ABI와 계측

ID0x46545084/register ABI4, compatible `fmcw,fft128-dma-quad-v4`,
모듈 `fft128_dma_quad`, 장치 `/dev/fft128-dma-quad`다.
헤더112 B, input offset112/output offset65648을 ABI3과 동일하게 유지한다.
추가 profile 카운터24 B를 두 payload 뒤 offset131184에 배치해 request는131208 B다.
extra는 PROFILE 요청에서만 반환하며 unprofiled 요청의 payload/metadata 복사 크기는 같다.

| Offset | 의미 |
|---|---|
| 0x00..0x2c | 기존 제어·개수·global/stall, 새 ID/ABI |
| 0x30 | 코어 수4 |
| 0x34/0x38/0x3c/0x40 | 코어0/1/2/3 busy cycles |
| 0x44 | 한 개 이상 busy, 시간 합집합 |
| 0x48 | 두 개 이상 동시 busy |
| 0x4c | 네 개 모두 동시 busy |
| 0x50 | 두 개 이상 동시 work-window |
| 0x54 | 네 개 모두 동시 work-window |
| 0x58 | 차례가 아닌 코어에 output valid가 있는 cycles, lane별 합이 아님 |

work-window는 마지막 입력 handshake 이후부터 첫 출력 valid 전까지다.
CALC와 초기 출력 RAM 읽기 지연을 포함한다. RTL에서는 실제 각 코어 CALC 상태를 별도로
비교한다. full frame의 실제4코어 CALC 겹침 하한은 all-work−64cycles,
2개 이상 CALC 겹침 하한은 multi-work−256cycles다. 보드 자체 검사·profile 분석에서
이 하한이 양수인지 확인한다. global−any-busy는 full frame64cycles다.
per-core busy·global·host ioctl·kernel wait는 겹치므로 더하지 않는다.
서로 다른 lane의 input/output stall 합을 빼 순수 compute라고 부르지 않는다.

입력 지연으로 실제 CALC가 겹치지 않아도 기능적으로 올바른 전송은 허용한다.
보드 성능 실험은 정상 DMA 입력에서 실제4개 코어가 겹치는지도 별도로 요구한다.

## 로컬 검증

```text
python src/PL/fft128_ps/verify_dma_quad.py
python src/PS/fft128/test_native.py
python src/PS/fft128/dma_batch/test_tools.py
python src/PS/fft128/dma_parallel/test_tools.py
python src/PS/fft128/dma_quad/test_tools.py
```

기존2코어/DMA/serial/pipeline 회귀와272벡터/34,816 complex bins,
1/2/3/4/5/6/7/127/128 FFT, AXI AW/W 분리·응답 정지, AXIS 공백·역압·payload 안정성,
malformed TLAST/TKEEP, lane2 부분 입력·실제4코어 계산·lane3 출력 정지 중 abort/recovery,
불완전 group·다음 group 차단을 확인했다. 입력을 크게 지연시켜 CALC 겹침0인 경우도 PASS다.
호스트 테스트는 native9/E11b 도구3/2코어 도구4/4코어 도구5개로 총21개 PASS다.

초기 테스트 starvation20cycles를 제외한 무정지 결과는1626cycles/group,
52032cycles/axis,104064cycles/frame = **2.081280 ms/50 MHz**다.
2코어 모델2.856960 ms 대비1.372694배 PL 내부 개선 계산이며 전체 보드 성능은 미측정이다.
full axis의 실제4코어 CALC 겹침2944cycles/all-work2976cycles를 확인했다.
AXI DMA IP·DDR·IRQ·실제 ARM 커널은 로컬 시뮬레이션 범위 밖이다.

## Vivado 및 ARM 빌드

Ubuntu Vivado Tcl 콘솔에서 공유 폴더 마운트와 빌드를 실행한다.

```tcl
set share /home/user/fmcw_share
file mkdir $share
if {[catch {exec mountpoint -q $share}]} {
    exec /usr/bin/vmhgfs-fuse .host:/share-2 $share
}
source [file join $share FMCW-FFT-test src PL fft128_ps build_dma_quad.tcl]
```

ARM userspace/module 빌드도 백그라운드로 시작한다. 기존 prepared kernel과 기록 DT를
사용하며 커널을 설치하거나 FPGA를 프로그래밍하지 않는다.
완료 표시는 `FFT128_DMA_QUAD_BUILD_PASS`와
`build/fft128_dma_quad_preparation/arm_build.log`의 `E13_4CORE_ARM_BUILD_PASS`다.
생성 reset IP·ABI/core-count, 50 MHz setup/hold와 DSP16개를 검사한다.

두 빌드가 통과한 뒤 Ubuntu에서 실행한다.

```bash
P="$HOME/fmcw_share/FMCW-FFT-test"
bash "$P/src/PS/fft128/dma_quad/prepare_bundle.sh" &&
bash "$P/src/PS/fft128/dma_quad/deploy.sh"
```

새 배포는 Ubuntu `/nfsroot/opt/fft128/e13_4core`, 보드 `/opt/fft128/e13_4core`다.
E13-2core 활성 모듈/overlay가 있으면 보드를 재부팅한 뒤 실행한다.

```sh
sudo sh /opt/fft128/e13_4core/load_board.sh
```

`DMA_E13_4CORE_SELFTEST_READY`와 `QUAD_OVERLAP_PASS`를 확인한다.
숫자 자체 검사·ABI/독점 소유·실제 동시 계산 검사를 마친 후 보드에서 실행한다.

```sh
B=/opt/fft128/e13_4core
sudo sh "$B/profile_board.sh" "$B/profile_e13_4core_01" &&
sudo sh "$B/run_board.sh" "$B/results_e13_4core_01"
```

별도 profile은 warmup2/repeat20, 비계측 paired PS double/NEON/PL은 CPU0,
warmup10/repeat100×3/순서 회전이다. paired 실행 DMA IRQ는 각660회 증가가 기대된다.
새 결과 디렉터리를 사용하고 원본을 덮어쓰지 않는다. Ubuntu에서 회수한다.

```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/src/PS/fft128/dma_quad/collect_results.sh"
```

[준비 근거](../../../../benchmarks/reports/2026-11-20-e13-4core-preparation/README.md),
[빌드 근거](../../../../benchmarks/reports/2026-11-20-e13-4core-build/README.md),
[실험 일지](../../../../docs/experiment_log.md).
