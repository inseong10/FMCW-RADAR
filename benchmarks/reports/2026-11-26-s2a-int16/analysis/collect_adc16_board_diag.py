from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
SHARED=Path('C:/Users/user/Documents/share/FMCW-FFT-test')
sys.path.insert(0,str(ROOT/'tools/detection'))
import check_adc16_stream as checker
import analyze_stream

relative=Path('build/s2a_int16_board_diag_20261126_adc01')
raw=ROOT/relative
if raw.exists():raise SystemExit('Use a fresh local raw directory')
source=SHARED/relative
original={p.relative_to(source).as_posix():checker.sha(p) for p in source.rglob('*') if p.is_file()}
shutil.copytree(source,raw)
for name,digest in original.items():assert checker.sha(raw/name)==digest,name
for line in (raw/'source.sha256').read_text().splitlines():
    digest,name=line.split(None,1);assert checker.sha(ROOT/name.strip())==digest,name
report=ROOT/'benchmarks/reports/2026-11-26-s2a-int16'
results=[]
for backend,run in [('ps',92301),('pl',92302)]:
    name=f'{backend}_diag_01'
    sender=f's2a_int16_sender_{name}.json'
    shutil.copy2(SHARED/'build'/sender,raw/sender)
    result=checker.check(raw/name,raw/sender,require_board=True)
    env=analyze_stream.fields(raw/name/'trace/environment.txt')
    assert int(env['run_id'])==run
    assert env['frames']=='20' and env['window']=='hann' and env['warmup']=='10'
    assert env['cpu0']=='0' and env['queue']=='4' and env['partial']=='4'
    assert env['ps_precision']=='float64' and env['ps_plan']=='ESTIMATE'
    assert result['zero_drops'] and result['offered_load_valid'] and result['first_frame_all_bins_checked']
    assert result['accuracy']['hits']==4 and result['accuracy']['false']==0
    counters=analyze_stream.fields(raw/name/'trace/counters.txt')
    assert counters['received_packets']=='2560'
    assert all(v=='0' for k,v in counters.items() if k not in ('received_packets','error'))
    before=(raw/name/'clock_before.txt').read_text();after=(raw/name/'clock_after.txt').read_text()
    assert before==after,'Clock context changed during '+name
    result['runtime_clock_context_unchanged']=True
    result['run_id']=run
    result['raw_collection_directory']=str(relative/name)
    results.append(result)
    target=report/name;target.mkdir(exist_ok=False)
    for rel in ('runtime.txt','clock_before.txt','clock_after.txt','receiver_exit.txt','artifact_check.txt',
                'source.sha256','build_environment.txt','interrupts_before.txt','interrupts_after.txt',
                'trace/frames.csv','trace/counters.txt','trace/environment.txt','trace/detections.csv',
                'trace/resources.csv','adc16_verified.json','trace/summary.json'):
        destination=target/rel;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(raw/name/rel,destination)
    if (raw/name/'trace/fftw_plan.txt').exists():
        shutil.copy2(raw/name/'trace/fftw_plan.txt',target/'trace/fftw_plan.txt')
    expected_sender=report/(name+'_sender.json')
    if expected_sender.exists():assert checker.sha(expected_sender)==checker.sha(raw/sender)
    else:shutil.copy2(raw/sender,expected_sender)
    print(json.dumps({'backend':backend,'run_id':run,'processed':result['processed_frames_checked'],
          'accuracy':result['accuracy'],'metrics':result['metrics']},indent=2))
manifest={'experiment':'S2a-int16','scope':'board 50ms/20 diagnostic; not continuous acceptance',
          'raw_collection_directory':str(relative),'original_copied_sha256':original,
          'board_binary_sha256':checker.sha(raw/'stream-receiver'),'runs':results,
          'acceptance_10000_frames':False}
(report/'board_diag_validation.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('ADC16_BOARD_DIAGNOSTIC_RAW_VERIFIED PS=20/20 PL=20/20')
