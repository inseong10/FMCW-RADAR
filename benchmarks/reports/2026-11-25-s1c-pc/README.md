# S1c — Q15 FFT/CFAR PC 검증 (2026-11-25)

증거 종류: **Windows PC native C SOFTWARE_MODEL + C++ CFAR**. FPGA·ARM 실행은 없다.
검증용 실행 파일은 ignored `build/s1c_host_validation/`, 전체 입력/출력은 `build/s1c_pc_20261125_03/`에 있다.
정확한 소스·컴파일러·실행 파일 SHA는 이 보고서에 보존했다.

```powershell
python -m unittest discover -s tools/detection -p test_s1c.py -v
python tools/detection/verify_s1c.py --model-binary build/s1c_host_validation/model.exe --cfar-binary build/s1c_host_validation/cfar-spectrum.exe --out build/s1c_pc_20261125_03 --warmup 1 --repeat 3
```

별도3테스트와 PC 파이프라인6구성이 통과했다. native C의 양자화/정수 FFT를 독립 Python 모델과
모든 bin에서 정확히 대조하고, 그 출력을 S1b와 공유하는 C++ CA-CFAR 및 NumPy CA-CFAR에 넣었다.
검출 순서·전력·임계값이 일치하고 모든 구성의 피크 목록이 S1b float 기준과 같았다.
Hann 4표적4/4·오검출0, 근접 약표적1/3이라는 기존 한계도 유지된다.

Hann은 PC에서 원본 IQ에 적용한 뒤 float32 RSPB로 준비한다. 실제 보드 규칙인
최대 복소수 크기→16384/ties-to-even 양자화와 각 단계 floor/포화를 사용한다.
`manifest.json`에 원본/준비 입력 SHA, 입력 scale, 이상 Q15 FFT·정수 FFT와 float 기준의 검출,
정수 모델과 이상 FFT 사이 오차를 기록했다.

CFAR는 PL CSV를 읽는 별도 프로그램이다. 이 구조는 정확성을 분리 검증하며
파일 IO·Hann 준비를 포함하는 종단 지연을 측정하지 않는다. 성분별 시간을 합산하지 않는다.
`checked_summary.json`의 시간은 Windows **소프트웨어 모델** 실행값이며 보드 성능으로 쓰지 않는다.
`model_rejected_as_board.txt`는 모델 출력이 hardware 검증을 통과하지 못함을 확인한 음성 검사다.

초기 host checker는 native 모델의 전체 backend 문자열을 짧은 이름으로 비교해 멈췄다.
메타데이터 이름을 실제 문자열에 맞춘 뒤 새 결과 디렉터리에서 통과했다. 수치 처리 규칙은 바꾸지 않았다.
초기 출력은 ignored `build/s1c_pc_20261125_01/`에 유지했다.

## ARM 준비 후속

사용자가 Ubuntu에서 `build_s1c.sh arm build/s1c_arm_20261125_195231` 및 번들 준비를 완료했다.
공유 폴더에서 ELF32 ARM hard-float(flags0x5000400), 실행 파일 SHA, 소스8개와 번들 전체 artifact를 확인했다.
근거는 `arm_preparation.json`, `arm_build_environment.txt`, `arm_cfar-spectrum.sha256`,
`ubuntu_bundle_manifest.json`이다. ARM 파일은 ignored `build/s1c_arm_20261125_195231/`에 보존했다.
이는 크로스 빌드/준비 확인이며 실제 S1c 보드 실행 결과는 아직 없다.
