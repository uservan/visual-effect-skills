"""E3 human judgments: build the annotation page (one self-contained HTML) and the blind item key.

Annotators see START, RESULT and the instruction, never the candidate name: each item carries an
opaque id; the id -> (task, candidate) key stays in motivation/e3/annotation_key.csv (not in the page).
Answers are stored by the page in the artifact db at judgments/<annotator id>.
"""
from pathlib import Path
import argparse,base64,csv,hashlib,io,json
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
DATA=Path('/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data')
SALT='e3-human-v1'

def jpeg(path,side,q):
    im=Image.open(path).convert('RGB');im.thumbnail((side,side),Image.Resampling.LANCZOS)
    b=io.BytesIO();im.save(b,'JPEG',quality=q,optimize=True)
    return 'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--side',type=int,default=448);ap.add_argument('--quality',type=int,default=80)
    args=ap.parse_args()
    # 'identity' (unchanged START) is left out: both VLM judges already reject it (1-3 %).
    rows=[r for r in csv.DictReader(open(ROOT/'motivation/e3/candidates_manifest.csv')) if r['candidate']!='identity']
    # Three batches of whole tasks, each with an equal share of explicit and vague tasks.
    by_group={}
    for r in rows:by_group.setdefault(r['group'],[]).append(r['task_id'])
    batch={t:'ABC'[i%3] for g in sorted(by_group) for i,t in enumerate(sorted(set(by_group[g])))}
    inv={r['task_id']:r for r in csv.DictReader(open(ROOT/'motivation/benchmark_audit/task_inventory.csv')) if r['benchmark']=='PSBench'}
    tasks={};items=[];key=[]
    for r in rows:
        t=r['task_id']
        if t not in tasks:
            meta=json.loads((DATA/'sources/PSBench-data'/t/f'{t}.json').read_text())
            tasks[t]={'ins':inv[t]['instruction'],'start':jpeg(DATA/'sources/PSBench-data'/t/meta['resources']['input_file'],args.side,args.quality)}
        iid=hashlib.sha1(f"{SALT}|{t}|{r['candidate']}".encode()).hexdigest()[:10]
        items.append({'id':iid,'t':t,'b':batch[t],'img':jpeg(r['path'],args.side,args.quality)})
        key.append({'item_id':iid,'batch':batch[t],'task_id':t,'candidate':r['candidate'],'group':r['group'],'e1_class':r['e1_class'],'difficulty':r['difficulty']})
    with (ROOT/'motivation/e3/annotation_key.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,list(key[0]));w.writeheader();w.writerows(key)
    data=json.dumps({'tasks':tasks,'items':items},ensure_ascii=False).replace('</','<\\/')
    html=Path(__file__).with_name('annotation_template.html').read_text(encoding='utf-8').replace('/*__DATA__*/null',data)
    Path(args.out).write_text(html,encoding='utf-8')
    print(json.dumps({'out':args.out,'items':len(items),'tasks':len(tasks),'MB':round(len(html.encode())/1e6,2)}))
if __name__=='__main__':main()
