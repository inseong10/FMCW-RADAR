from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'build/s2a_int16_board_diag_20261126_adc01'
REPORT=ROOT/'benchmarks/reports/2026-11-26-s2a-int16'

def parse(path):
    text=path.read_text()
    lines=text.splitlines();values={};registers={};current=None
    for line in lines:
        if line.startswith('/sys/'):current=line
        elif current and re.match(r'^0000000\s',line):
            octets=bytes(int(v,8) for v in line.split()[1:])
            assert len(octets)==4
            values[current]=int.from_bytes(octets,'big');current=None
        elif line.startswith('0x'):
            addr,value=line.split(':');registers[addr]=int(value.strip(),16)
    ref=next(v for p,v in values.items() if p.endswith('/ps-clk-frequency'))
    pl=next(v for p,v in values.items() if p.endswith('/fft128-e14_frame-clock/clock-frequency'))
    arm=registers['0xF8000100'];ctrl=registers['0xF8000120']
    assert ((ctrl>>4)&3)==0 and (arm & ((1<<4)|(1<<3)))==0
    mult=(arm>>12)&127;div=(ctrl>>8)&63
    return {'boot_id':lines[0].split('=',1)[1],'ps_reference_hz':ref,'arm_pll_multiplier':mult,
            'cpu_divisor':div,'cpu_configured_hz':ref*mult/div,'pl_declared_clock_hz':pl,
            'registers':registers,'scope':'CPU register-derived setting; PL device-tree declaration; no frequency counter measurement'}

contexts={}
for backend in ('ps','pl'):
    before=parse(RAW/f'{backend}_diag_01/clock_before.txt')
    after=parse(RAW/f'{backend}_diag_01/clock_after.txt')
    assert before==after
    assert before['pl_declared_clock_hz']==100000000
    assert before['cpu_configured_hz']==666666660
    contexts[backend]=before
assert contexts['ps']==contexts['pl']
out={'experiment':'S2a-int16','runtime_context':contexts,'before_after_and_cross_run_equal':True,
     'maximum_frequency_claim':False}
(REPORT/'board_clock_context.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print('ADC16_CLOCK_CONTEXT_PASS cpu_setting_hz=666666660 pl_declared_hz=100000000')
