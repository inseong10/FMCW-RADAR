# E14-frame — PL 전치와 전체 프레임 DMA

128×128 고정 Q15 프레임의 두 축 FFT를 한 요청으로 처리합니다. **RTL/host·Vivado 50MHz·ARM·보드 자체 검사·
20회 profile·각300회 paired와 원시 결과 독립 검증을 완료했습니다.** PL 중앙값1.657914ms, 같은 회차 NEON 대비2.104718배입니다.
[완료 보고서](../../../../benchmarks/reports/2026-11-21-e14-frame-board/README.md).
BRAM47/60, DSP28/80, setup WNS10.166ns/hold WHS0.020ns입니다.
기존 E13-stream 실행 파일·펌웨어·보고서를 보존하고 `/opt/fft128/e14_frame`을 별도로 사용합니다.

```text
PS Q15 row-major input → MM2S 64KiB
  → Range FFT (기존 7단계 스트리밍 코어)
  → 64KiB 행렬 RAM, 열 방향 읽기
  → Doppler FFT (같은 코어 재사용)
  → 같은 RAM의 해당 열에 결과 저장
  → Doppler-major/range-minor 순서로 읽기 → S2MM 64KiB → PS
```

RAM을 두 벌 만들지 않습니다. 한 열의 128개 입력이 모두 FFT에 수락된 뒤 그 열의 출력만 덮어씁니다.
동기 RAM의 출력 보관 레지스터는 정지 중 값을 유지합니다. RAM 내용은 초기화하지 않고 valid/카운터만 reset합니다.
두 축과 최종 출력은 Range→Doppler→배출 순서이며 전체 2D 프레임끼리 겹치지 않습니다.
`frame_initiation_interval=128`은 재사용 코어의 **128-point FFT 벡터** 간격으로, 전체 2D 프레임 간격이 아닙니다.

## E13-stream과의 차이

| 항목 | E13-stream | E14-frame |
|---|---|---|
| FFT 산술·클록 | Q15, 단계별 /2, 전용 7단계, 50 MHz | 유지 |
| 요청·DMA 채널 제출/프레임 | 2 ioctl / 4채널 | 1 ioctl / 2채널 |
| 입출력 payload 합/프레임 | 256KiB | 128KiB |
| 중간 결과·전치·최종 배열 순서 복원 | PS | PL 64KiB in-place RAM |
| coherent bounce 정책 | 유지 | 유지 |
| 사용자·커널 복사 | 두 축 각각 필요 | 최초 입력·최종 출력에 필요 |

복사 최적화(E11d)나 clock/precision 변경을 함께 적용하지 않습니다. 입력 경로는 사용자 작업→사용자 요청→
커널 요청→coherent TX이며, 출력은 역순으로 복사합니다. 타이머의 kernel copy 항목에는
`copy_from_user/to_user`와 커널 요청↔coherent `memcpy`가 함께 포함됩니다.

## 빌드와 배포

1. PC에서 `python src/PL/fft128_ps/verify_dma_frame.py`와 `python src/PS/fft128/dma_frame/test_tools.py`를 실행합니다.
   RTL 검증은 NumPy와 Icarus Verilog가 필요하며 실제 DMA IP·DDR·IRQ·보드 타이밍은 검증하지 않습니다.
2. 소스를 공유 폴더에 반영한 뒤 **Ubuntu Vivado 2022.1 Tcl 콘솔**에서 실행합니다.

   ```tcl
   source /home/user/fmcw_share/FMCW-FFT-test/src/PL/fft128_ps/build_dma_frame.tcl
   ```

   별도 run을 만들고 기존 reset/PS7/HP0/DMA 설정을 유지합니다. ARM userspace와 모듈 빌드도 `prepare_all.sh`로 병행합니다.
   ARM 로그는 `build/fft128_dma_frame_preparation/arm_build.log`입니다. PetaLinux 커널을 설치하거나 FPGA를 프로그래밍하지 않습니다.
   Vivado가 타이밍·reset IP·7단계·행렬 BRAM 추론을 확인한 뒤 `FFT128_DMA_FRAME_BUILD_PASS`를 출력해야 합니다.
3. 실제 결과 확인 후 Ubuntu에서 번들을 만들고 NFS root에 배포합니다.

   ```bash
   root="$HOME/fmcw_share/FMCW-FFT-test"
   bash "$root/src/PS/fft128/dma_frame/prepare_bundle.sh"
   bash "$root/src/PS/fft128/dma_frame/deploy.sh"
   ```

   기존 번들·다른 배포를 덮어쓰지 않습니다. `build/fft128_dma_frame_latest.txt`가 선택한 run과 ARM 소스/실행 파일 해시를 검사합니다.
   `.bit/.bin/.xsa/.ko`와 ARM 실행 파일은 ignored `build/`에 둡니다. `/opt/fft128/e14_frame/load_board.sh`는 이 단계 후에 생깁니다.

## 보드 실행과 수집

기존 DMA 드라이버·overlay가 남아 있으면 `load_board.sh`가 중단합니다. 사용 중인 드라이버에 다른 레지스터 ABI의
펌웨어를 올리지 않기 위한 검사입니다. 이 경우 기존 결과를 보존하고 새로 부팅한 상태에서 아래 명령을 실행합니다.
스크립트가 자동 재부팅하거나 커널을 교체하지는 않습니다.

```sh
sudo sh /opt/fft128/e14_frame/load_board.sh
sudo sh /opt/fft128/e14_frame/profile_board.sh /opt/fft128/e14_frame/profile_e14_frame_01
sudo sh /opt/fft128/e14_frame/run_board.sh /opt/fft128/e14_frame/results_e14_frame_01
```

자체 검사는 ABI·독점 소유·잘못된 크기/timeout/flags·반복 요청·전체 2D 정수 모델·행렬/단계 카운터를 확인합니다.
이후 별도 20회 계측과 double/NEON/PL 각 300회 비계측 비교를 수행합니다. 매 반복 16,384 bin을 검사하며 검증은 타이밍 밖입니다.
paired 330프레임(워밍업 포함)에서 방향별 DMA IRQ는 330회가 예상됩니다. profile 22프레임은 별도입니다.

```bash
bash "$HOME/fmcw_share/FMCW-FFT-test/src/PS/fft128/dma_frame/collect_results.sh"
```

원본은 `build/fft128_dma_frame_measurements`에 새로 회수합니다. 같은 입력/정규화/CPU0/계측 범위를 유지하며
원본을 덮어쓰지 않습니다. 오프라인 반복 지연이며 연속 UDP 처리량·무손실 실시간 보장은 별도입니다.

## ABI와 카운터

- ABI8 / ID `0x46545088` / compatible `fmcw,fft128-dma-frame-v8`, `/dev/fft128-dma-frame`.
- ioctl `0x18`은 112-byte header만 인코딩합니다. 전체 요청은 131280 B이며 입력/출력/extra offset은 112/65648/131184 B입니다.
- `frame_words=16384`만 허용합니다. 완료 FFT는 256개, 외부 입력·출력은 각각 16384 words입니다. 1D 명령이나 부분 축을 에뮬레이션하지 않습니다.
- `0x34/38/3c`: Range/Doppler/drain cycles. 세 값의 합은 global active이며 kernel wait/ioctl과 겹칩니다.
- `0x40/44`: matrix writes/reads, 정상 각32768. `0x48/4c/50`: Range output/Doppler input/output, 정상 각16384.
- `0x54`: phase(0 idle, 1 Range, 2 Doppler, 3 drain). `0x58`: 덮어쓰기 guard가 차단한 이른 결과의 클록 수, 정상0.
- `0x5c`: 외부 input/output 동시 handshake, 이 순차 프레임 구조에서는0. `0x60`: matrix words=16384.
- 기존 `0x6c/70/74/78`과 stage issue/retire `0x80..98/0xa0..b8`는 전용 7단계의 실제 활동을 셉니다.
  정상 프레임마다 stage issue/retire 각각16384, stage CALC 합121856입니다. 여러 stage의 합은 벽시간에 더하지 않습니다.
- profile CSV의 `bytes_each_direction_per_fft=0`은 per-FFT 외부 전송이 없다는 뜻이며, 실제 전송은 `bytes_each_direction_per_request=65536`입니다.
