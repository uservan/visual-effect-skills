"""Render the M1 audit (pre-labels + evaluator labels + code findings) into one self-contained HTML page."""
from pathlib import Path
import argparse,csv,json

ROOT=Path(__file__).resolve().parents[2]
AUDIT=ROOT/'motivation/benchmark_audit'

def load(name):
    p=AUDIT/name
    return {(r['benchmark'],r['task_id']):r for r in csv.DictReader(open(p,encoding='utf-8'))} if p.exists() else {}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    inv=load('task_inventory.csv');ev=load('evaluator_labels.csv')
    versions={t:load(f'prelabel_{t}.csv') for t in ['qwen35','qwen35_v02']}
    versions={t:v for t,v in versions.items() if v}
    raw={}
    for t in versions:
        for line in open(AUDIT/f'prelabel_{t}_raw.jsonl',encoding='utf-8'):
            j=json.loads(line)
            if j['labels']:raw[(t,j['benchmark'],j['task_id'])]=j['labels']['components']
    tasks=[]
    for k,r in inv.items():
        row={'b':r['benchmark'],'id':r['task_id'],'tier':r['difficulty'] if r['benchmark']=='PSBench' else '','cat':r['category'],
             'ins':r['instruction'],'ev':ev.get(k,{}).get('evaluator_type',''),'evn':ev.get(k,{}).get('evaluator_note','')[:400],'v':{}}
        for t,lab in versions.items():
            l=lab.get(k)
            if l:row['v'][t]={'f':l['instruction_form'],'k':l['k_tags'],'nc':int(l['n_components']),'no':int(l['n_outcome']),
                              'c':[[c['form'],c['text']] for c in raw.get((t,)+k,[])],'note':l['note'],'conf':l['confidence']}
        tasks.append(row)
    html=(Path(__file__).with_name('report_template.html')).read_text(encoding='utf-8')
    data=json.dumps({'tasks':tasks,'versions':list(versions)},ensure_ascii=False).replace('</','<\\/')
    Path(args.out).write_text(html.replace('/*__DATA__*/null',data),encoding='utf-8')
    print(json.dumps({'out':args.out,'tasks':len(tasks),'versions':list(versions)}))
if __name__=='__main__':main()
