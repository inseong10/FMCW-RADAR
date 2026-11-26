# S2a-int16 실행 및 수신 원본 검증

기본 조건은 ADC16/profile1/S=1,600,000, Hann 수신기 내부, PS double FFTW ESTIMATE/O2,
PL E14 ABI8/100MHz, 두 CPU 사용 허용, queue4/partial4, warmup10이다.
PS와 PL 모두 같은 기록을 사용한다. 이 구현은 수신/처리 스레드를 두 코어에서 실행할 수 있지만
FFT/CFAR를 여러 worker로 병렬화한 최적 PS의 상한을 뜻하지 않는다. NEON opt1은 별도 실험이다.
다만 작업본에 있던 FFTW 정렬 버퍼와 PL 미사용 FFTW 버퍼 비할당은 포함되며 기존 rxfix1 대비 추가 변경 요인이다.
기존 float 실행 파일과 결과는 유지한다. 아래 새 경로가 이미 있으면 삭제하지 말고 새 label/ID를 사용한다.
송신은 기존 기준선처럼 chirp 간격0의 프레임별 UDP burst다. 실제 ADC 획득 시간 자체를 재는 것이 아니며,
프레임 주기·송신 지연/overrun과 수신 이후 비용을 기록한다. 출력 경로는 기존 `/opt/fft128` 번들 위치를 유지한다.

## 1. Ubuntu 빌드와 스모크

```bash
cd /home/user/fmcw_share/FMCW-FFT-test
bash tools/detection/prepare_adc16.sh 20261126_adc01
```

로그는 `build/s2a_int16_20261126_adc01/prepare.log`에 보존한다. 기존 float 3개 스모크,
ADC PS/model 정상 및 손실 3개 스모크, ADC 첫 프레임 전bin/전체 검출 검증을 통과해야 ARM을 빌드한다.
실패하면 마지막18줄만 출력한다. 바이너리 SHA는 `host/stream-receiver.sha256`,
`arm/stream-receiver.sha256`, 배포 번들 `artifacts.sha256`에 남는다.
기존 ARM double FFTW SHA도 확인한다. `/nfsroot/opt/fft128/s2a_int16_20261126_adc01`로 배포한다.
완료 출력은 `ADC16_DEPLOY_READY`다. 실제 출력이 오기 전에는 Ubuntu/ARM 성공으로 기록하지 않는다.

## 2. 보드 50ms/20프레임 진단 — PS

보드 터미널에서 실행한다. `S2A_READY`가 나온 뒤 Ubuntu 송신을 실행한다. 기다리는 중 Ctrl+C를 누르지 않는다.

```sh
B=/opt/fft128/s2a_int16_20261126_adc01
sudo sh "$B/run_board.sh" ps 92301 20 "$B/ps_diag_01" diag
```

Ubuntu:

```bash
python3 tools/sender/replay_stream.py \
  benchmarks/fixtures/adc16/radarsimpy_128x128_sim_multi4_noise_adc16.rspb \
  --ip 10.0.0.3 --run-id 92301 --frames 20 --period-ms 50 --wait-mode spin \
  --out build/s2a_int16_sender_ps_diag_01.json
```

## 3. 보드 50ms/20프레임 진단 — PL

100MHz E14가 현재 부팅에서 로드되어 있어야 한다. 새로 부팅했다면 기존 검증된
`sudo sh /opt/fft128/e14_clock_100000000_20261126_095418/load_board.sh`를 먼저 실행한다.
125MHz 빌드/RTL/드라이버 변경은 하지 않는다.

보드:

```sh
B=/opt/fft128/s2a_int16_20261126_adc01
sudo sh "$B/run_board.sh" pl 92302 20 "$B/pl_diag_01" diag
```

READY 뒤 Ubuntu:

```bash
python3 tools/sender/replay_stream.py \
  benchmarks/fixtures/adc16/radarsimpy_128x128_sim_multi4_noise_adc16.rspb \
  --ip 10.0.0.3 --run-id 92302 --frames 20 --period-ms 50 --wait-mode spin \
  --out build/s2a_int16_sender_pl_diag_01.json
```

회수와 독립 검산(Ubuntu):

```bash
dst=build/s2a_int16_board_diag_20261126_adc01
test ! -e "$dst" &&
cp -r /nfsroot/opt/fft128/s2a_int16_20261126_adc01 "$dst" &&
python3 tools/detection/check_adc16_stream.py "$dst/ps_diag_01" \
  --sender build/s2a_int16_sender_ps_diag_01.json &&
python3 tools/detection/check_adc16_stream.py "$dst/pl_diag_01" \
  --sender build/s2a_int16_sender_pl_diag_01.json
```

회수한 번들 전체와 두 sender JSON을 보존한다. 각 `adc16_verified.json`에 입력/바이너리/원본 SHA,
모든 처리 프레임 검출·전력·threshold 비교, 첫 프레임16384 complex bin 비교, prepare 중앙값/P99/max가 남는다.
PS는 NumPy double, PL은 독립 Python 정수 Hann/FFT 모델과 비교한다. multi4 Hann 기준4/4·오검출0이다.
원본 회수 전에는 사용자 콘솔 증거로만 분류한다. 진단의 첫 spectrum 복사는 출력 타임스탬프 뒤에 수행하고
CSV는 종료 후 저장하지만, 다음 프레임에 영향을 줄 수 있으므로 이 실행을 연속 합격 판정에 사용하지 않는다.

## 4. 12.8ms/200 예비 검사

두 진단의 원본 검증이 통과한 뒤에만 실행한다. 아래는 진단 옵션을 모두 끈다. 각 READY 뒤 대응 송신을 실행한다.

보드 PS:

```sh
sudo sh "$B/run_board.sh" ps 92311 200 "$B/ps_prelim_01" measure
```

Ubuntu PS:

```bash
python3 tools/sender/replay_stream.py \
  benchmarks/fixtures/adc16/radarsimpy_128x128_sim_multi4_noise_adc16.rspb \
  --ip 10.0.0.3 --run-id 92311 --frames 200 --period-ms 12.8 --wait-mode spin \
  --out build/s2b_int16_sender_ps_prelim_01.json
```

보드 PL:

```sh
sudo sh "$B/run_board.sh" pl 92312 200 "$B/pl_prelim_01" measure
```

Ubuntu PL:

```bash
python3 tools/sender/replay_stream.py \
  benchmarks/fixtures/adc16/radarsimpy_128x128_sim_multi4_noise_adc16.rspb \
  --ip 10.0.0.3 --run-id 92312 --frames 200 --period-ms 12.8 --wait-mode spin \
  --out build/s2b_int16_sender_pl_prelim_01.json
```

새 회수 경로 `build/s2a_int16_board_prelim_20261126_adc01`에 전체 번들을 복사한 뒤 같은 checker에
각 prelim 디렉터리와 sender JSON을 전달한다. 누락이 있으면 `--allow-loss`로 실패 원본을 분석하며,
`zero_drops=false`를 보존한다. 큐 크기를 바꾸거나 처리 개수만으로 최대 FPS를 계산하지 않는다.
200프레임 결과는10,000프레임 합격 근거로 쓰지 않는다.

## 5. 10,000프레임 본검사 준비

예비 검사에서 송신 부하·오류 카운터·정확도·지연을 검토한 뒤 결정한 주기로 실행한다.
12.8ms를 계속 검사한다면 보드 PS는 `ps 92321 10000 "$B/ps_main_01" measure`,
PL은 `pl 92322 10000 "$B/pl_main_01" measure`를 wrapper 인자로 쓴다.
대응 sender는 같은 run ID, `--frames 10000 --period-ms 12.8 --wait-mode spin`, 새 JSON 경로를 쓴다.
각각 약128초의 송신이며 수신기 idle 종료까지 기다린다. 반복·주기 스윕은 별도 새 ID로 남긴다.
합격은 실제10,000프레임 원본에서 드랍0, 유효한 송신 부하, 오류0, 정확도 유지,
**첫 커널 패킷→CSV flush P99 < 주기**, 큐 대기 안정성을 확인한 뒤에만 판정한다.
`check_adc16_stream.py`는 자동으로10,000프레임 합격을 주장하지 않는다.

## 6. S2b-pace: chirp 간격100µs 송신과 조립완료 기준

판정은 P99(조립완료→CSV flush) < 주기다. 첫 커널 패킷→출력은 보조로 보고한다. 수신기 번들은 그대로 쓴다.

Ubuntu 단위 검사와 수신기 없는 송신 probe(보드에서 수신기를 실행하지 않는다):

```bash
cd /home/user/fmcw_share/FMCW-FFT-test
(cd tools/sender && python3 -m unittest -v test_check_pacing)
sha256sum tools/sender/replay_stream.py
python3 tools/sender/replay_stream.py \
  benchmarks/fixtures/adc16/radarsimpy_128x128_sim_multi4_noise_adc16.rspb \
  --ip 10.0.0.3 --run-id 92330 --frames 200 --period-ms 12.8 --wait-mode spin \
  --chirp-gap-us 100 --chirp-detail \
  --out build/s2b_pace_sender_probe_01.json
```

`S2A_CHIRP_PACING … valid=True`(P99<10µs, 총지각최대<주기10%)일 때만 보드 예비로 진행한다.
`boundary_overruns`는 보고값이다. `chrt`/SCHED_FIFO는 probe92335에서 36.9ms 정지를 보여 사용하지 않는다. 보드 PS:

```sh
B=/opt/fft128/s2a_int16_20261126_adc01
sudo sh "$B/run_board.sh" ps 92331 200 "$B/ps_pace_prelim_01" measure
```

READY 뒤 Ubuntu (`--run-id 92331`, `--out build/s2b_pace_sender_ps_prelim_01.json`, 나머지는 probe와 같은 송신 인자).
PL은 `pl 92332 200 "$B/pl_pace_prelim_01" measure`와 `--run-id 92332`, `--out build/s2b_pace_sender_pl_prelim_01.json`.
회수 경로는 새 `build/s2a_int16_board_pace_20261126_adc01`이다.

## 7. 정식 조건: 스레드 고정 (11-26 채택)

PS·PL 모두 수신기 실행 직후 main·sampler→CPU0, worker→CPU1로 고정한다. 측정 중 셸 반복 기록은 쓰지 않는다.

보드에서 한 번 만든다:

```sh
cat > /tmp/pin_once.sh <<'EOF'
T=/opt/fft128/pin_tid_20261126_01/pin-tid
until P=$(pidof stream-receiver) && [ "$(ls /proc/$P/task | wc -l)" -ge 3 ]; do sleep 0.02; done
set -- $(ls /proc/$P/task | sort -n)
echo "pid=$P tasks=$*"
"$T" 1 "$1" "$2"; "$T" 2 "$3"
echo "T $(cut -d' ' -f1 /proc/uptime)"; grep '^cpu[01] ' /proc/stat
EOF
```

각 실행: `sudo sh /tmp/pin_once.sh > /tmp/pin_<ID>.txt 2>&1 &` 뒤 `run_board.sh`, 종료 후
`sudo cp /tmp/pin_<ID>.txt "$B/pin_<OUT>.txt"`. `tasks=` 3개와 mask 1/1/2를 확인한다.
10,000프레임 송신은 `--chirp-detail`을 빼서 JSON 크기를 줄인다(프레임별 최대 지각·요약은 남는다).

## 8. 재고정 송신 (11-26 채택, PL 92344 이후)

송신에 `--schedule reanchor`를 더한다. 지각이 10µs를 넘으면 실제 송신 시각으로 시간표를 다시 맞추고 몰아 보내지 않는다.
송신기 SHA `51ba255c…f5452d`. 콘솔의 `S2A_REANCHOR … valid=True`가 송신 부하 유효 조건이다(P99<10µs, 최소 chirp 간격≥90µs,
최소 프레임 간격≥주기−10µs, 정지 프레임≤1%). `S2A_CHIRP_PACING`의 `total_max_ms`는 이 규칙에서 보고값이다.

## 프로토콜과 수치 경계

RSPY v2/dtype1은 기존 float32, v3/dtype2는 ADC int16이다. 공통52바이트 big-endian
`!4sBBHQQIIIdQ`는 magic/version/type/channel/run/frame/chirp/pulses/samples/fs/sender_ns다.
v3는 offset52에 profile uint32(1)를 추가하고 offset56부터 I,Q signed16 big-endian128쌍을 싣는다.
총568바이트/패킷,128패킷/프레임이다. 알 수 없는 profile·타입·길이·혼합 metadata를 거절한다.
수신기는 `--input-format adc16`을 명시해야 하며 기본값 float32는 v2를 유지한다.

ADC payload는128KiB→64KiB, UDP datagram 합은137728→72704바이트/프레임이다(IP/UDP 헤더 제외).
이와 함께 raw 조립 버퍼 표현과 backend 분기 위치도 바뀌므로 준비 비용 개선을 정규화 제거 하나에 귀속하지 않는다.
PS는 ADC code를 double로 변환해 부동 Hann/FFTW/16384를 수행한다. PL은 사전 Q15 Hann 계수
두 개의 Q30 곱에 code를 곱해 최근접 짝수 반올림하고 real하위16/imag상위16으로 패킹한다.
E14 입력 code는 그대로이며 추가 shift/프레임 gain이 없다. 두 경로의 power 단위는 ADC code²,
원본 float power와 물리 스케일 비교 시 S²를 고려한다. 창 양자화·FFT 단계 floor/포화 차이는 정확도 검사에서 분리한다.

## 9. 에이전트 실행 (11-26 사용자 승인)

Windows `~/.ssh/fmcw_agent`로 Ubuntu(`user@192.168.25.129`)에, 그리고 Ubuntu를 거쳐 보드(`petalinux@10.0.0.3`)에 접속한다.
보드에서는 `sudo -n /opt/fft128/agent_20261126_01/run_pinned.sh pl|ps RUN_ID FRAMES OUT_NAME`만 비밀번호 없이 실행된다
(`/etc/sudoers.d/fmcw_agent`). 비대화형 SSH에서는 먼저 `export PATH=/usr/sbin:/usr/bin:/sbin:/bin`을 한다(92347: devmem 없음).
로그는 `/opt/fft128/agent_logs_20261126_01/run_<ID>.log`·`pin_<ID>.txt`에 남는다.
11-26 S3a-0부터는 v3 `sudo -n /opt/fft128/agent_20261126_03/run_pinned3.sh BUNDLE ps|pl RUN_ID FRAMES OUT_NAME nfs|ram`을 쓴다.
v3는 루트 소유이고 그룹·기타 쓰기 권한이 없으며 artifacts.sha256 검증을 통과한 `/opt/fft128/s2a_int16_*` 번들만 실행한다. sudoers에는 v3 한 줄만 남는다(v2 권한 제거).
`S2A_READY`와 mask 1/1/2를 확인한 뒤에만 송신한다. 해제하려면 sudoers 파일과 `authorized_keys`의 `fmcw_agent` 줄을 지운다.
