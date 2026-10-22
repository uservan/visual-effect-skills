"""E3: sample PSBench tasks by E1 class (vague vs explicit) and build scripted candidate results.

Candidates: end (author reference), identity (START), half (START + 0.5*delta), over (START + 3*delta),
opposite (START - delta), naive_global (one global Lab mean/std transfer towards END).
Only tasks where the three E1 voters agreed unanimously or by majority are sampled.
"""
from pathlib import Path
import argparse,csv,importlib.util,json,random
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
# Same transforms as the earlier M3 draft; loaded by path because both files are named make_candidates.py.
_spec=importlib.util.spec_from_file_location('m3_candidates',ROOT/'scripts/m3/make_candidates.py')
_m3=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_m3)
load,naive_global,save=_m3.load,_m3.naive_global,_m3.save

DATA=Path('/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data')
VAGUE={'vague_missing_tool','vague_missing_values'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--n-per-class',type=int,default=30);ap.add_argument('--seed',type=int,default=0)
    ap.add_argument('--out',default=DATA/'e3');args=ap.parse_args();out=Path(args.out)
    inv={r['task_id']:r for r in csv.DictReader(open(ROOT/'motivation/benchmark_audit/task_inventory.csv')) if r['benchmark']=='PSBench'}
    split=[r for r in csv.DictReader(open(ROOT/'motivation/benchmark_audit/split_full.csv'))
           if r['benchmark']=='PSBench' and r['agree'] in ('all','majority')]
    rng=random.Random(args.seed);picked=[]
    for group,keep in [('explicit',lambda c:c=='explicit'),('vague',lambda c:c in VAGUE)]:
        pool=sorted((r for r in split if keep(r['class'])),key=lambda r:r['task_id'])
        picked+=[dict(r,group=group) for r in rng.sample(pool,min(args.n_per_class,len(pool)))]
    manifest=[]
    for r in picked:
        task=r['task_id'];start,end=load(task);delta=end-start
        cands={'end':end,'identity':start,'half':start+0.5*delta,'over':start+3*delta,'opposite':start-delta,'naive_global':naive_global(start,end)}
        for name,arr in cands.items():
            p=out/'candidates'/task/f'{name}.png'
            manifest.append(dict(task_id=task,group=r['group'],e1_class=r['class'],difficulty=inv[task]['difficulty'],candidate=name,
                                 path=str(p),sha256_16=save(arr,p),mean_abs_diff_to_end=round(float(np.abs(np.clip(arr,0,1)-end).mean()),5)))
    (ROOT/'motivation/e3').mkdir(parents=True,exist_ok=True)
    with (ROOT/'motivation/e3/candidates_manifest.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,list(manifest[0]));w.writeheader();w.writerows(manifest)
    tiers={}
    for r in picked:tiers.setdefault(r['group'],{}).setdefault(inv[r['task_id']]['difficulty'],0);tiers[r['group']][inv[r['task_id']]['difficulty']]+=1
    print(json.dumps({'tasks':len(picked),'candidates':len(manifest),'tiers':tiers}))
if __name__=='__main__':main()
