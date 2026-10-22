"""M3: sample PSBench hard tasks and build scripted candidate results.

Candidates (docs/motivation-benchmark-gaps.md §3.2): end, identity, naive_global,
over_strength, opposite, and subject_damage when a reviewed subject mask exists.
Deterministic: fixed seed, no learned model in any transform.
"""
from pathlib import Path
import argparse,csv,hashlib,json,random,re
import numpy as np
from PIL import Image,ImageFilter
from skimage import color

ROOT=Path(__file__).resolve().parents[2]
DATA=Path('/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data')
PS=DATA/'sources/PSBench-data'
# Strata come from the PSBench category; first match wins. Mixed categories ('1-Minute') fall back to
# instruction keywords, since mentions like "natural skin tones" in colour grades must not count as retouching.
BY_CATEGORY=[('typography',r'typograph'),('retouching',r'retouch|removal|reshap|hide part'),
             ('compositing',r'composit|exposure|sky ?replacement|duplication|surreal|horror|poster'),
             ('effects',r'glow|dispersion|bokeh|blur|reveal|slice|splash'),
             ('color',r'colou?r|grading|adjust|tone|duotone|black|lighting|seasonal|hue')]
BY_INSTRUCTION=[('typography',r"\bword\b|\bletters\b|\btext\b"),
                ('compositing',r'transparent background|replace the (existing )?sky|\bplace\b.*\bbehind\b'),
                ('retouching',r'retouch|blemish|wrinkle|dandruff|skin a polished'),
                ('effects',r'glow|halo|outline|neon|bokeh|blur')]
PRESERVE=re.compile(r'\b(preserv|keep|maintain|retain|without (changing|altering|affecting))',re.I)

def stratum(category,instruction):
    for rules,text in [(BY_CATEGORY,category.lower()),(BY_INSTRUCTION,instruction.lower())]:
        hit=next((name for name,pat in rules if re.search(pat,text)),None)
        if hit:return hit
    return 'color'

def sample(rows,n,seed,min_per):
    by={}
    for r in rows:by.setdefault(r['stratum'],[]).append(r)
    rng=random.Random(seed);total=len(rows)
    quota={s:max(min_per,round(n*len(v)/total)) for s,v in by.items()}
    while sum(quota.values())>n:quota[max(quota,key=lambda s:quota[s]-min_per)]-=1
    while sum(quota.values())<n:quota[max(by,key=lambda s:len(by[s])-quota[s])]+=1
    picked=[]
    for s,v in sorted(by.items()):picked+=rng.sample(sorted(v,key=lambda r:r['task_id']),min(quota[s],len(v)))
    return sorted(picked,key=lambda r:r['task_id'])

def load(task):
    d=PS/task;t=json.loads((d/f'{task}.json').read_text())
    start=Image.open(d/t['resources']['input_file']).convert('RGB');end=Image.open(d/t['reference_output']['expected_file']).convert('RGB')
    if end.size!=start.size:end=end.resize(start.size,Image.Resampling.LANCZOS)  # 2 hard tasks differ only in scale
    return np.asarray(start,np.float32)/255,np.asarray(end,np.float32)/255

def naive_global(start,end):
    """One global Lab mean/std transfer from START towards END: right direction, no local work."""
    a,b=color.rgb2lab(start),color.rgb2lab(end)
    out=(a-a.mean((0,1)))/(a.std((0,1))+1e-6)*b.std((0,1))+b.mean((0,1))
    return np.clip(color.lab2rgb(out),0,1)

def subject_damage(end,mask):
    """Correct edit + visible damage inside the subject: heavy blur and a 90-degree hue shift."""
    img=Image.fromarray((end*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(8))
    hsv=color.rgb2hsv(np.asarray(img,np.float32)/255);hsv[...,0]=(hsv[...,0]+0.25)%1
    m=mask[...,None]
    return end*(1-m)+color.hsv2rgb(hsv)*m

def save(arr,path):
    path.parent.mkdir(parents=True,exist_ok=True);Image.fromarray((np.clip(arr,0,1)*255).round().astype(np.uint8)).save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--n',type=int,default=60);ap.add_argument('--seed',type=int,default=0)
    ap.add_argument('--min-per-stratum',type=int,default=6);ap.add_argument('--out',default=DATA/'m3')
    args=ap.parse_args();out=Path(args.out)
    rows=[dict(r,stratum=stratum(r['category'],r['instruction']),preservation_regex=bool(PRESERVE.search(r['instruction'])))
          for r in csv.DictReader(open(ROOT/'motivation/benchmark_audit/task_inventory.csv',encoding='utf-8'))
          if r['benchmark']=='PSBench' and r['difficulty']=='hard']
    with (ROOT/'motivation/m3/hard_strata.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,['task_id','category','stratum','preservation_regex','instruction']);w.writeheader()
        w.writerows({k:r[k] for k in w.fieldnames} for r in rows)
    picked=sample(rows,args.n,args.seed,args.min_per_stratum);manifest=[]
    for r in picked:
        task=r['task_id'];start,end=load(task);delta=end-start
        cands={'end':end,'identity':start,'naive_global':naive_global(start,end),'over_strength':start+3*delta,'opposite':start-delta}
        mask_path=out/'masks'/task/'subject_reviewed.png'
        if r['preservation_regex'] and mask_path.exists():
            cands['subject_damage']=subject_damage(end,np.asarray(Image.open(mask_path).convert('L'),np.float32)/255)
        for name,arr in cands.items():
            p=out/'candidates'/task/f'{name}.png'
            manifest.append(dict(task_id=task,stratum=r['stratum'],candidate=name,path=str(p.relative_to(out)),sha256_16=save(arr,p),
                                 mean_abs_diff_to_end=round(float(np.abs(np.clip(arr,0,1)-end).mean()),5)))
    with (ROOT/'motivation/m3/candidates_manifest.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,list(manifest[0]));w.writeheader();w.writerows(manifest)
    cnt={}
    for r in picked:cnt[r['stratum']]=cnt.get(r['stratum'],0)+1
    print(json.dumps({'sampled':len(picked),'per_stratum':cnt,'needs_mask':sum(r['preservation_regex'] for r in picked),'candidates':len(manifest)}))
if __name__=='__main__':main()
