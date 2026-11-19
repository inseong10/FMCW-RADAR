# E11b — 축당 128 FFT 묶음 제출

기존 단일 FFT 코어/50 MHz/Q15/출력 2클록과 coherent bounce 복사 정책을 유지한다.
한 축 128 FFT를 입력 64 KiB/출력 64 KiB 패킷 하나씩으로 실행한다.
프레임당 ioctl 2회, DMA 채널 제출 4회, FFT 256회, payload 총 256 KiB다.
FFT 사이 LOAD/CALC/OUTPUT 겹치기는 없으며 E12는 별도다.
기존 `../dma` E11a 소스/ABI/펌웨어/측정/배치 폴더를 보존한다.

## 상태

로컬 RTL/host·ARM·Vivado·보드 자체 검사·전체 프레임·별도20회 profile·각300회 paired 비교와
원본 독립 검증을 완료했다. 중앙값 PL **6.433026 ms** / PS double **5.717376 ms** /
NEON **3.558177 ms**다. 약8 ms는 사전 가설이었다.
[완료 결과·정확도·원시 시간·신원](../../../../benchmarks/reports/2026-11-19-e11b-board/README.md).

## 실행

Ubuntu:

```sh
P="$HOME/fmcw_share/FMCW-FFT-test"
bash "$P/src/PS/fft128/dma_batch/prepare_all.sh"
```

Vivado 2022.1 Tcl:

```tcl
source [file join $env(HOME) fmcw_share FMCW-FFT-test src PL fft128_ps build_dma_batch.tcl]
```

`couldn't read file ... no such file or directory`라면 Ubuntu 재시작 후 공유 마운트가
해제됐는지 확인한다. Windows 공유 폴더에 소스가 있는 경우 기존 프로젝트에서 사용하는
`share-2`를 다음처럼 마운트한다(이미 마운트돼 있으면 건너뛴다).

```tcl
set share [file join $env(HOME) fmcw_share]
file mkdir $share
if {[catch {exec mountpoint -q $share}]} {
    exec /usr/bin/vmhgfs-fuse .host:/share-2 $share
}
source [file join $share FMCW-FFT-test src PL fft128_ps build_dma_batch.tcl]
```

새 출력 포인터는 `build/fft128_dma_batch_latest.txt`다. generated reset IP,
AXI ID/ABI/배치 크기 확인 → 합성/route/50 MHz setup·hold 검사 → bitstream/XSA다.
두 빌드 성공 후 Ubuntu에서:

```sh
bash "$P/src/PS/fft128/dma_batch/prepare_bundle.sh"
bash "$P/src/PS/fft128/dma_batch/deploy.sh"
```

PetaLinux: 이전 DMA 모듈/overlay가 활성화돼 있다면 재부팅하여 해제한 뒤 적용한다.
동작 중인 DMA 장치 아래에서 FPGA를 재프로그램하지 않는다.

```sh
sudo sh /opt/fft128/e11b/load_board.sh
sudo sh /opt/fft128/e11b/profile_board.sh /opt/fft128/e11b/profile_e11b_01
sudo sh /opt/fft128/e11b/run_board.sh /opt/fft128/e11b/results_e11b_01
```

ABI/독점 소유/잘못된 요청 검사와 1 FFT·128 FFT·반복 128 FFT 각 정수 모델 비교를 먼저 수행한다.
프로파일은 warmup 2/repeat 20, 별도 비계측 비교는 PS double/NEON/PL 각 warmup10/repeat100×3이다.
모든 전체 프레임 반복에서 16,384 bin을 정수 모델과 대조한다.
완료 후 IRQ67/68은 각각 330프레임×2축 = 660회 증가해야 한다.

## 계약

제어 주소 `0x43c60000`, ID `0x46544280`, register ABI 2,
DT compatible `fmcw,fft128-dma-batch-v2`, 모듈 `fft128_dma_batch.ko`,
장치 `/dev/fft128-dma-batch`, 배치 `/opt/fft128/e11b`다.
DMA/HP0/IRQ/길이폭 설정은 E11a와 같다.

기존 레지스터에 `0x028` FFT 개수(1..128, idle 중에만 쓰기), `0x02c` 완료 FFT 수를 추가한다.
입출력 handshake 카운터는 축 전체 샘플 수다. 외부 TLAST는 축 마지막에만,
코어 입력 TLAST는 FFT마다 생성한다. 코어 출력 TLAST를 매 FFT 검사한다.
active 사이클은 시작부터 마지막 출력 수락까지이며, 스트림 정지를 포함한다.
시뮬레이션에서 active−input_stall−output_stall = 861×FFT개수를 확인했다.

UAPI 요청은 포인터 없는 고정 배열과 88-byte header다. 전체 131,160 B를 ioctl 크기 필드에
넣을 수 없으므로 `_IOWR`는 header 88 B만 인코딩한다. 실제 인수는 전체 request이고
배열 오프셋은 고정이다. 커널 request/cached 배열과 coherent TX/RX는 probe 시 한 번 할당한다.
요청마다 사용자→커널 cached→coherent 및 역방향 복사를 유지하며, timeout/error에는
양 DMA 채널 동기 종료 후 FFT를 reset한다. 출력은 상태/샘플/FFT 개수 확인 뒤 전달한다.

## 재검증

```sh
python src/PL/fft128_ps/verify_dma_batch.py
python src/PS/fft128/dma_batch/test_tools.py
python benchmarks/compare_dma_batch_board.py build/fft128_dma_batch_measurements/results_e11b_01
python src/PS/fft128/dma_batch/analyze_profile.py build/fft128_dma_batch_measurements/profile_e11b_01/pl.profile.csv
```

프로파일의 fft_calls는 256, dma_requests는 2다. min/max_active_cycles는 **요청(축)당**이다.
중첩 kernel/PL 구간을 host ioctl과 다시 합산하지 않는다.
