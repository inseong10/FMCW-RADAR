# 인터페이스

## PC → PS: UDP 프레임 (현재 구현)

chirp 1개를 UDP 데이터그램 1개로 보냅니다.

| 필드 | 형식 | 내용 |
|---|---|---|
| magic | 4 bytes | `RSPY` |
| version | uint8 | 1 |
| message type | uint8 | 1 (baseband) |
| channel | uint16 | 채널 번호 |
| chirp index | uint32 | 프레임 안에서 chirp 번호 |
| chirp count | uint32 | 프레임의 chirp 수 |
| sample count | uint32 | chirp당 샘플 수 |
| sample rate | float64 | 샘플링 주파수 (Hz) |
| payload | float32 × 2 × sample count | I, Q 순서로 교차 배치 |

헤더는 28바이트이고, 헤더와 payload 모두 big-endian입니다.
프로토콜에 frame ID가 없으므로 한 번에 프레임 하나만 보냅니다.

## PS → PL: 현재 구현된 경로

| 경로 | 전송 단위 | 계약 |
|---|---|---|
| MMIO (E06~E10) | FFT 1개를 AXI4-Lite 데이터 창으로 읽고 씀 | [AXI4-Lite 계약](../src/PL/fft128_ps/README.md) |
| DMA, FFT당 (E11a) | FFT 1개 = 512 B, 외부 TLAST는 매 128번째 beat | [E11a 실행 계약](../src/PS/fft128/dma/README.md) |
| DMA, 축당 묶음 (E11b) | FFT 128개 = 65,536 B, 외부 TLAST는 축 마지막 beat | [E11b 실행 계약](../src/PS/fft128/dma_batch/README.md) |
| DMA, E13-2core | 축당 128 FFT = 65,536 B, 외부 TLAST는 축 마지막 beat | [기존 코어 2개, pair barrier](../src/PS/fft128/dma_parallel/README.md) |
| DMA, E13-4core | 축당 128 FFT = 65,536 B, 외부 TLAST는 축 마지막 beat | [기존 코어 4개, group barrier](../src/PS/fft128/dma_quad/README.md) |
| DMA, E12-4core | 축당 128 FFT = 65,536 B, 외부 TLAST는 축 마지막 beat | [4코어, FIFO·독립 스케줄](../src/PS/fft128/dma_overlap/README.md) |
| DMA, E13-bf2 | 축당 128 FFT = 65,536 B, 외부 TLAST는 축 마지막 beat | [4코어, 코어당 버터플라이 2개](../src/PS/fft128/dma_bf2/README.md) |
| DMA, E13-stream | 축당 128 FFT = 65,536 B, 외부 TLAST는 축 마지막 beat | [전용 7단계 프레임 스트리밍](../src/PS/fft128/dma_stream/README.md) |

위 경로 모두 128×128 고정 크기이고, 두 축 사이 전치는 PS가 합니다.

E13-stream의 스트리밍은 단일 축 안에서 FFT 벡터의 단계 처리를 겹치는 구조입니다.
Range→전치→Doppler 전체 프레임을 PL 안에서 연결한 경로는 아직 구현하지 않았습니다.

## PS → PL: 전체 프레임 AXI4-Stream 입력 (명세 초안, 미구현)

아래는 가변 크기·전체 프레임 통합을 위한 초안이며 아직 구현하지 않았습니다.

- **형식:** AXI4-Stream 32비트, 1 beat = 복소 샘플 1개입니다. `TDATA[15:0]`는 I, `TDATA[31:16]`은 Q이고, 각각 int16 2의 보수입니다.
- **정수 변환:** PS가 고정 계수 S를 곱하고 반올림한 뒤 int16 범위로 포화합니다. 창함수나 정규화는 PS가 적용하지 않습니다.
- **순서:** chirp 우선입니다. chirp 0의 sample 0부터 N_SAMPLES−1까지 보낸 뒤 chirp 1을 보냅니다. `TLAST`는 프레임의 마지막 beat에서만 1입니다.
- **프레임 크기:** N_CHIRPS × N_SAMPLES beat, 즉 4 × N_CHIRPS × N_SAMPLES 바이트입니다. DDR 버퍼 1개를 AXI DMA(MM2S) 전송 1회로 보냅니다.
- **가변 크기:** N_CHIRPS와 N_SAMPLES는 프레임 사이에서만 바뀝니다. PS가 AXI4-Lite 설정 레지스터에 쓰면 다음 프레임부터 적용되며, 비트스트림 재합성 없이 바꿀 수 있어야 합니다.
- **흐름 제어:** PL은 `TREADY`로 backpressure를 걸 수 있습니다. PL이 이전 프레임을 처리 중이면 PS가 대기하거나 드랍하고 드랍 수를 기록합니다.
- **미정 사항(OPEN-02):** N_SAMPLES = 160처럼 2의 거듭제곱이 아닌 크기를 어느 쪽에서 zero-padding할지 협의가 필요합니다.

PL 내부 처리, 출력 포맷, 레지스터 맵 세부는 PL 담당이 정합니다.
