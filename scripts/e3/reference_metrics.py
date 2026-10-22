"""E3 (reference-based scoring): can a target-image metric separate correct from wrong results where the
reference-free VLM judge cannot?

Adds near-correct positives (x0.9, x1.1 strength) so the reference is not compared only with itself, then
scores every candidate by CIEDE2000 (mean, p95) and SSIM against END, and compares with the VLM judges.
Output: motivation/e3/reference_metrics.csv and a printed summary.
"""
from pathlib import Path
import csv,importlib.util,json,statistics as st
import numpy as np
from skimage import color
from skimage.metrics import structural_similarity

ROOT=Path(__file__).resolve().parents[2]
DATA=Path('/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data')
_spec=importlib.util.spec_from_file_location('m3_candidates',ROOT/'scripts/m3/make_candidates.py')
_m3=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_m3)
STRENGTH={'end':1.0,'near_0.9':0.9,'near_1.1':1.1,'half':0.5,'over':3.0,'opposite':-1.0,'identity':0.0}

def shrink(a,side=1024):
    """Score at <=1024 px on the long side; full-resolution CIEDE2000 on large PSBench images takes hours."""
    h,w=a.shape[:2];k=side/max(h,w)
    if k>=1:return a
    from PIL import Image
    return np.asarray(Image.fromarray((a*255).round().astype(np.uint8)).resize((round(w*k),round(h*k)),Image.Resampling.LANCZOS),np.float32)/255

def scores(arr,end,lab_end):
    arr=np.clip(arr,0,1);de=color.deltaE_ciede2000(color.rgb2lab(arr),lab_end)
    return float(de.mean()),float(np.percentile(de,95)),float(structural_similarity(arr,end,channel_axis=2,data_range=1.0))

def main():
    man=list(csv.DictReader(open(ROOT/'motivation/e3/candidates_manifest.csv')))
    tasks={r['task_id']:r for r in man};rows=[]
    for t,meta in tasks.items():
        start,end=(shrink(x) for x in _m3.load(t));delta=end-start;lab_end=color.rgb2lab(end)
        cands={k:start+s*delta for k,s in STRENGTH.items()}
        cands['naive_global']=_m3.naive_global(start,end)
        for name,arr in cands.items():
            m,p95,ss=scores(arr,end,lab_end)
            rows.append({'task_id':t,'group':meta['group'],'difficulty':meta['difficulty'],'candidate':name,'de00_mean':round(m,3),'de00_p95':round(p95,3),'ssim':round(ss,4)})
    with (ROOT/'motivation/e3/reference_metrics.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,list(rows[0]));w.writeheader();w.writerows(rows)
    # VLM judge pass rates for the same candidates (all judges, all repeats)
    vlm={}
    for j in map(json.loads,open(ROOT/'motivation/e3/judgments.jsonl')):
        if j['passed'] is not None:vlm.setdefault(j['candidate'],[]).append(j['passed'])
    order=['end','near_0.9','near_1.1','half','over','opposite','naive_global','identity']
    print(f"{'candidate':13s} {'dE00 mean (median)':>19s} {'SSIM (median)':>14s} {'pass@dE<=3':>11s} {'VLM pass':>9s}")
    for c in order:
        r=[x for x in rows if x['candidate']==c];de=[x['de00_mean'] for x in r]
        tol=100*sum(d<=3.0 for d in de)/len(de);v=vlm.get(c)
        print(f"{c:13s} {st.median(de):19.2f} {st.median(x['ssim'] for x in r):14.3f} {tol:10.0f}% {('%8.0f%%'%(100*sum(v)/len(v))) if v else '   (n/a)':>9s}")
if __name__=='__main__':main()
