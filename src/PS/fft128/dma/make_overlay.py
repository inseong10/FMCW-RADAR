#!/usr/bin/env python3
"""Generate E11a overlay from the recorded live DT; never guess a GIC phandle."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import tarfile

FFT_BASE = 0x43C60000
DMA_BASE = 0x40400000
SPI = (35, 36)  # Zynq IRQ_F2P[6:7], GIC IRQ 67/68


def make_overlay(archive):
    with tarfile.open(archive) as source:
        data = {(m.name[2:] if m.name.startswith('./') else m.name): source.extractfile(m).read()
                for m in source if m.isfile()}
    def cells(name):
        raw = data[name]
        if len(raw) % 4:
            raise ValueError('Invalid DT cell length: ' + name)
        return struct.unpack('>' + 'I' * (len(raw)//4), raw)
    if cells('#address-cells') != (1,) or cells('#size-cells') != (1,):
        raise ValueError('Expected Zynq root address/size cells = 1/1')
    if data.get('amba_pl/compatible', b'').split(b'\0').count(b'simple-bus') != 1:
        raise ValueError('Expected existing populated /amba_pl simple-bus')
    if cells('amba_pl/#address-cells') != (1,) or cells('amba_pl/#size-cells') != (1,):
        raise ValueError('Expected /amba_pl address/size cells = 1/1')
    if data.get('amba_pl/ranges') != b'':
        raise ValueError('Expected identity /amba_pl ranges')
    gics = [k.rsplit('/', 1)[0] for k, v in data.items()
            if k.endswith('/compatible') and b'arm,cortex-a9-gic\0' in v]
    if len(gics) != 1:
        raise ValueError('Expected exactly one Cortex-A9 GIC')
    gic = gics[0]
    if cells(gic+'/#interrupt-cells') != (3,):
        raise ValueError('Expected 3 GIC interrupt cells')
    phandle, = cells(gic+'/phandle')
    if not phandle:
        raise ValueError('Missing GIC phandle')
    # Reject known physical resource collisions, even for disabled legacy nodes.
    for key in data:
        if key.endswith('/interrupts'):
            value = cells(key)
            if len(value) % 3 == 0:
                for n in range(0, len(value), 3):
                    if value[n] == 0 and value[n+1] in SPI:
                        raise ValueError('IRQ conflict: ' + key)
        if key.endswith('/reg'):
            parent = key.rsplit('/', 2)[0] if key.count('/') > 1 else ''
            # Only root, amba_pl, axi and other physical 1/1 buses. Skip local
            # addresses such as I2C devices, graph ports and CPU identifiers.
            if parent not in ('', 'amba_pl', 'axi'):
                continue
            values = cells(key)
            if len(values) % 2:
                continue
            for start, size in zip(values[::2], values[1::2]):
                if any(start < base+length and base < start+size
                       for base, length in ((FFT_BASE, 0x1000), (DMA_BASE, 0x10000))):
                    raise ValueError('Address conflict: ' + key)
    text = f'''/dts-v1/;
/plugin/;
/ {{
    fragment@0 {{
        target-path = "/";
        __overlay__ {{
            fft128_e11a_clock: fft128-e11a-clock {{
                compatible = "fixed-clock";
                #clock-cells = <0>;
                clock-frequency = <50000000>;
            }};
        }};
    }};
    fragment@1 {{
        target-path = "/amba_pl";
        __overlay__ {{
            #address-cells = <1>;
            #size-cells = <1>;
                fft128_e11a_dma: dma@{DMA_BASE:x} {{
                    compatible = "xlnx,axi-dma-1.00.a";
                    interrupt-parent = <0x{phandle:x}>;
                    reg = <0x{DMA_BASE:x} 0x10000>;
                    #dma-cells = <1>;
                    xlnx,addrwidth = <32>;
                    xlnx,sg-length-width = <17>;
                    clocks = <&fft128_e11a_clock>, <&fft128_e11a_clock>, <&fft128_e11a_clock>;
                    clock-names = "s_axi_lite_aclk", "m_axi_mm2s_aclk", "m_axi_s2mm_aclk";
                    dma-channel-mm2s {{
                        compatible = "xlnx,axi-dma-mm2s-channel";
                        interrupts = <0 {SPI[0]} 4>;
                        xlnx,datawidth = <64>;
                    }};
                    dma-channel-s2mm {{
                        compatible = "xlnx,axi-dma-s2mm-channel";
                        interrupts = <0 {SPI[1]} 4>;
                        xlnx,datawidth = <64>;
                    }};
                }};
                fft@{FFT_BASE:x} {{
                    compatible = "fmcw,fft128-dma-v1";
                    reg = <0x{FFT_BASE:x} 0x1000>;
                    dmas = <&fft128_e11a_dma 0>, <&fft128_e11a_dma 1>;
                    dma-names = "tx", "rx";
                }};
        }};
    }};
}};
'''
    return text, dict(overlay_layout='existing_amba_pl_v2', target_bus='/amba_pl',
                      gic_path='/'+gic, gic_phandle=phandle,
                      fft_base=hex(FFT_BASE), dma_base=hex(DMA_BASE), dt_spi=list(SPI),
                      irq_f2p_bits=[6, 7], clock_hz=50000000,
                      live_dt_sha256=hashlib.sha256(Path(archive).read_bytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('live_dt_tar', type=Path)
    parser.add_argument('output_dts', type=Path)
    args = parser.parse_args()
    text, metadata = make_overlay(args.live_dt_tar)
    args.output_dts.parent.mkdir(parents=True, exist_ok=True)
    args.output_dts.write_text(text, encoding='utf-8')
    args.output_dts.with_suffix('.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    print('DMA_OVERLAY_SOURCE_READY:', args.output_dts)


if __name__ == '__main__':
    main()
