"""E5: image-grounded effect probe. Can a model tell, from a before/after pair, which operation was applied
and with what setting? Same knowledge is asked in text form as a control.

Operations are canonical implementations of standard editing adjustments (GIMP-style definitions), not
renders from the application itself; each has four settings. Items: source images x random (op, setting).
Output: $DATA/e5/items.jsonl and $DATA/e5/images/<item>_{start,result}.jpg
"""
from pathlib import Path
import argparse,csv,json,random
import numpy as np
from PIL import Image,ImageFilter
from skimage import color

DATA=Path('/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data')
ROOT=Path(__file__).resolve().parents[2]

def hsv_op(a,f):
    h=color.rgb2hsv(a);f(h);return color.hsv2rgb(h)
def blur(a,s):return np.asarray(Image.fromarray((a*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(s)),np.float32)/255
def unsharp(a,amt):
    b=blur(a,2.0);return a+amt*(a-b)
def vignette(a,s):
    h,w=a.shape[:2];y,x=np.mgrid[0:h,0:w];r=np.sqrt(((x-w/2)/(w/2))**2+((y-h/2)/(h/2))**2)/np.sqrt(2)
    return a*(1-s*r**2)[...,None]
def shadows_blue(a,s):
    lum=a.mean(2,keepdims=True);wgt=(1-lum)**2;out=a.copy();out[...,2:3]+=s*wgt;out[...,0:1]-=0.5*s*wgt;return out

# name shown to models, description of the operation, settings (value, label), transform
OPS={
 'brightness':('Brightness-Contrast: Brightness','shifts every tone up or down by the same amount',[(-0.25,'-0.25'),(-0.1,'-0.10'),(0.1,'+0.10'),(0.25,'+0.25')],lambda a,v:a+v),
 'contrast':('Brightness-Contrast: Contrast','stretches or compresses tones around middle grey',[(-0.4,'-40%'),(-0.2,'-20%'),(0.3,'+30%'),(0.7,'+70%')],lambda a,v:(a-0.5)*(1+v)+0.5),
 'gamma':('Levels: midtone (gamma)','brightens or darkens midtones while keeping black and white points',[(0.5,'0.50'),(0.75,'0.75'),(1.4,'1.40'),(2.0,'2.00')],lambda a,v:np.clip(a,0,1)**(1/v)),
 'saturation':('Hue-Saturation: Saturation','makes all colours more or less vivid',[(-0.8,'-80'),(-0.4,'-40'),(0.4,'+40'),(0.9,'+90')],lambda a,v:hsv_op(a,lambda h:h.__setitem__((...,1),np.clip(h[...,1]*(1+v),0,1)))),
 'hue':('Hue-Saturation: Hue','rotates every colour around the colour wheel',[(30,'+30°'),(90,'+90°'),(180,'180°'),(-60,'-60°')],lambda a,v:hsv_op(a,lambda h:h.__setitem__((...,0),(h[...,0]+v/360)%1))),
 'temperature':('Color Temperature','warms (towards orange) or cools (towards blue) the whole image',[(-0.2,'much cooler'),(-0.08,'slightly cooler'),(0.08,'slightly warmer'),(0.2,'much warmer')],lambda a,v:a*np.array([1+v,1,1-v])),
 'shadows_blue':('Color Balance: Shadows towards blue','adds blue (and removes red) in the dark tones only',[(0.08,'+8'),(0.18,'+18'),(0.3,'+30'),(0.45,'+45')],shadows_blue),
 'blur':('Gaussian Blur','softens the whole image uniformly',[(1.0,'radius 1'),(2.5,'radius 2.5'),(5,'radius 5'),(10,'radius 10')],blur),
 'sharpen':('Unsharp Mask','increases local contrast at edges',[(0.5,'amount 0.5'),(1.0,'amount 1.0'),(2.0,'amount 2.0'),(3.5,'amount 3.5')],unsharp),
 'vignette':('Vignette','darkens the corners and edges relative to the centre',[(0.25,'strength 25%'),(0.5,'strength 50%'),(0.75,'strength 75%'),(0.95,'strength 95%')],vignette),
 'posterize':('Posterize','reduces the number of tone levels per channel',[(2,'2 levels'),(3,'3 levels'),(5,'5 levels'),(8,'8 levels')],lambda a,v:np.round(np.clip(a,0,1)*(v-1))/(v-1)),
}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--images',type=int,default=40);ap.add_argument('--per-image',type=int,default=5)
    ap.add_argument('--side',type=int,default=768);ap.add_argument('--seed',type=int,default=0);args=ap.parse_args()
    rng=random.Random(args.seed);out=DATA/'e5';(out/'images').mkdir(parents=True,exist_ok=True)
    ids=sorted(r['task_id'] for r in csv.DictReader(open(ROOT/'motivation/benchmark_audit/task_inventory.csv')) if r['benchmark']=='PSBench')
    items=[]
    for t in rng.sample(ids,args.images):
        meta=json.loads((DATA/'sources/PSBench-data'/t/f'{t}.json').read_text())
        im=Image.open(DATA/'sources/PSBench-data'/t/meta['resources']['input_file']).convert('RGB');im.thumbnail((args.side,args.side))
        start=np.asarray(im,np.float32)/255
        for op in rng.sample(sorted(OPS),args.per_image):
            name,desc,settings,fn=OPS[op];k=rng.randrange(4);v,label=settings[k]
            res=np.clip(fn(start.copy(),v),0,1);iid=f'{t}-{op}'
            Image.fromarray((start*255).astype(np.uint8)).save(out/'images'/f'{iid}_start.jpg',quality=92)
            Image.fromarray((res*255).round().astype(np.uint8)).save(out/'images'/f'{iid}_result.jpg',quality=92)
            others=rng.sample([o for o in sorted(OPS) if o!=op],3);opts=others+[op];rng.shuffle(opts)
            items.append({'item_id':iid,'source':t,'op':op,'setting_index':k,'setting':label,
                          'op_options':[OPS[o][0] for o in opts],'op_answer':'ABCD'[opts.index(op)],
                          'op_options_desc':[OPS[o][1] for o in opts],'op_name':name,
                          'param_options':[s[1] for s in settings],'param_answer':'ABCD'[k]})
    with (out/'items.jsonl').open('w') as h:
        for it in items:h.write(json.dumps(it,ensure_ascii=False)+'\n')
    print(json.dumps({'items':len(items),'ops':{o:sum(i['op']==o for i in items) for o in OPS}}))
if __name__=='__main__':main()
