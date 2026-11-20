# E12-4core preparation — 2026-11-20

**로컬 RTL272벡터와 host28개 회귀 PASS. ARM/Vivado/보드 미검증.**

E13-4core의 공유 입출력·group barrier가 코어 수 확대의 이득을 제한했다.
각 기존 산술 코어 앞뒤에 독립 동기 RAM FIFO를 두고, 다음 입력과 이전 결과를 저장해
입력·CALC·출력을 겹친다. 입력128개와 출력128개 여유가 있는 코어부터 다음 FFT를 시작한다.
FIFO backing RAM256words+출력 레지스터1word이며 입력용량257/출력예약최대256words다.
산술·코어4개·50 MHz·Q15·내부출력2clocks/sample·DMA32-bit/HP0 64-bit·복사·PS전치는 고정한다.
버퍼와 독립 스케줄 변경을 함께 비교하며 E11c의출력 cadence 개선은 포함하지 않는다.
`external_ping_pong=false`, `external_buffers=true`, `buffering=per_lane_fifos`로 구현을 명시한다.

## 확인한 범위

- 새 RTL: FFT272벡터/34,816 complex bins 정수 일치, 순서/부분배치1/2/3/4/5/6/7/127/128,
  AXIS input gap/output backpressure, stalled payload, 외부축 TLAST/내부FFT TLAST,
  malformed TLAST/TKEEP, 독립 AW/W와응답 정체, 허용되지 않은 주소/설정 거부 PASS.
- 실제 코어 CALC 상태와 외부 handshake를 독립 관측했다. 무정지128 FFT 테스트에서
  최대4 CALC, 실제4-CALC2944cycles, 외부 IO동시11415cycles,
  입력+실제CALC16068/출력+실제CALC16064/세동작11357cycles를 확인했다.
  이 행은 시작 직후 테스트가 의도한21cycles 입력 대기 포함28119cycles다.
- 별도 DMA 유사 launch는 입력valid를 CONTROL 전에 준비하고 수신을 계속 열었다.
  input/output stall이 모두0이며 **28098cycles/axis**임을 직접 assert했다.
  외부 stall 카운터를 빼서 순수 계산 시간을 추정한 값이 아니다.
- FIFO 용량/전체FFT 출력 예약을 매사이클 검사했다. 8000cycles 출력 정체 후128 FFT 전량 배출,
  입력·CALC·stalled lane3 출력·전체버퍼가 찬 상태의 abort/recovery 후 정수 일치 PASS.
- 기존 serial/pipeline/E11a/E11b/E13 baseline도 첫 전체 검증에서 PASS(`baseline.log`).
  이후 새 FIFO 경계/zero-stall assert 추가는`--skip-baseline`으로 기존 fixture를 재사용했다.
  최종`result.json`의`baseline_rerun=false`는 그 마지막 실행 범위를 나타낸다.
- host28개: native9/E11b3/E13-2core4/E13-4core5/E12계측7 PASS.
  실제 C CSV 및 batch metadata, 겹침0/불가능한 카운터·중복시간 거부를 검사한다.
- Python compile, bash10파일 syntax, Tcl`info complete`, 기록된 live-DT의새compatible/metadata,
  기존E13 bundle 거부 PASS. Windows shim 기반 Linux userspace C syntax와112/131224B 배치를 확인했다.
  이것은 ARM 컴파일·DT overlay의실제커널적용·Vivado Tcl 실행을 대신하지 않는다.

## 사이클 모델과 한계

| 범위 | E13-4core | E12-4core |
|---|---:|---:|
| 축당128 FFT, 외부정체0 |52032cycles|28098cycles|
| 두 축/50 MHz |2.081280ms|1.123920ms|

PL 내부 스케줄만 약46.0% 단축/1.852배다. CPU 복사·전치·ioctl/IRQ와 실제DMA/DDR 정체는
이 모델에 없으며 전체보드 성능 개선율로 쓰지 않는다. 단일FFT는 입력 전체를 미리 버퍼링한 뒤
코어가 다시 LOAD하므로 시작 지연이 늘어난다. 이 실험의 주 범위는 축당128 FFT다.
BRAM증가/50 MHz setup·hold와 실제4코어 겹침·보드 정확도/성능은 미확인이다.

## 재현/다음

```powershell
python src/PL/fft128_ps/verify_dma_overlap.py
python src/PS/fft128/dma_overlap/test_tools.py
```

Vivado 2022.1:
```tcl
source /home/user/fmcw_share/FMCW-FFT-test/src/PL/fft128_ps/build_dma_overlap.tcl
```

생성 reset IP/ABI5/실제DSP16개와50 MHz setup·hold 검사 후 ARM 모듈/수신기를 확인한다.
그다음 보드 자체 검사, 별도20회 profile, 각300회 PS double/NEON/PL paired 비교와 원본 검증을 한다.
[빌드·배포·보드 실행](../../../src/PS/fft128/dma_overlap/README.md),
[실험 기록](../../../docs/experiment_log.md).
기존E13 펌웨어·결과는 그대로 보존하며 새 경로는`dma_overlap`/`e12_4core`다.

`intended_dma_config.json`은 현재 Tcl에서 추출한 의도 설정이며 Vivado 생성 결과가 아니다.
`source_sha256.json`은 현재 새 구성·관련공통소스·검증소스의정확한 해시다.
빌드 산출물과 펌웨어는 아직 없다. raw RTL은`build/fft128_dma_overlap_verify`,
host는`build/fft128_dma_overlap_preparation`에 보존했다.

## Build follow-up

ARM/Vivado/generated-reset/50 MHz setup·hold and actual8 BRAM FIFO implementation
now PASS. Sources/artifacts independently verified; board remains pending.
See [build report](../2026-11-20-e12-4core-build/README.md).
The earlier pending state and board_verified:false metadata preserve the preparation stage.


## Final follow-up

Full-frame/profile/paired300-sample raw validation now PASS.
PL median3.129210ms/paired NEON3.488904ms; profile active1.124590ms.
See [final E12 board results](../2026-11-20-e12-4core-board/README.md).
Earlier pending statements and build metadata preserve their original stages.
