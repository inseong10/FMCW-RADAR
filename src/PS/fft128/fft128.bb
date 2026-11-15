SUMMARY = "Native C PS/PL FFT functional bring-up receiver, no Python runtime"
LICENSE = "CLOSED"
SRC_URI = "file://mmio.c file://native_core.h file://native_core.c file://native_receiver.c"
S = "${WORKDIR}"

do_compile() {
    ${CC} ${CFLAGS} -std=c11 -Wall -Wextra ${S}/mmio.c ${S}/native_core.c ${S}/native_receiver.c -o fft128-receiver ${LDFLAGS} -lm
}
do_install() {
    install -d ${D}${bindir}
    install -m 0755 fft128-receiver ${D}${bindir}/
}
