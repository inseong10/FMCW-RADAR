"""Ubuntu ADC16 loopback: production model/PS, full-bin diagnostics and explicit loss."""
import argparse
import json
from pathlib import Path
import smoke_s2a
import check_adc16_stream


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    results=[]
    for backend,run,loss in (('model',92381,False),('ps',92382,False),('model',92383,True)):
        result=smoke_s2a.case(a.binary.resolve(),a.out,backend,run,loss,diagnostic=not loss,adc16=True)
        folder=a.out/(backend+('_loss' if loss else '_normal'))
        verified=check_adc16_stream.check(folder,a.out/(folder.name+'_sender.json'),
                                          require_board=False,allow_loss=loss)
        results.append({'trace':result,'accuracy':verified})
        print(f'ADC16_SMOKE_PASS backend={backend} deliberate_loss={loss}',flush=True)
    (a.out/'smoke_summary.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print('ADC16_HOST_SMOKE_PASS cases=3; no board/throughput claim')


if __name__=='__main__':main()
