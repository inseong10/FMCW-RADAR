# S1b — ARM 실행 파일 빌드 확인 (2026-11-25)

증거 종류: **Ubuntu ARM 크로스 빌드 원본 + Windows ELF/SHA 독립 확인**. 보드 실행은 없다.

```bash
bash tools/detection/build_s1b.sh arm build/s1b_arm_20261125_192718
```

arm-linux-gnueabihf-g++ 9.4.0, C++17/O2/Wall/Wextra/Werror.
수신기·CFAR 헤더 SHA 2개가 작업 사본과 일치하고 실행 파일 SHA도 manifest와 일치한다.
`summary.json`은 독립 검사 결과다. ELF32 little-endian ARM, flags `0x5000400`(hard-float).

실행 파일은 ignored `build/s1b_arm_20261125_192718/receiver`에 보존했다.
SHA256 `f9320587d09f6e138c15595b9239047e2cd5a4799c0746e7345f57e69534c442`.
보드 로더·glibc/libstdc++·FFTW 런타임 호환성과 실제 실행 시간은 아직 확인하지 않았다.
기존 PS01 double FFTW 라이브러리를 새 S1b 경로에 복사해 검증할 예정이다.
