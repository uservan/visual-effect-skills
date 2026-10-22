"""M3: proposed masks of the region each instruction asks to preserve.

1. A VLM names the preserved target and boxes it on START (0-1000 coordinates).
2. SAM 2.1 turns the box into a mask.
3. A contact sheet is written for human review. Only masks a reviewer copies to
   subject_reviewed.png are used by make_candidates.py.
"""
from pathlib import Path
import argparse,base64,csv,io,json
import httpx,numpy as np,torch
from PIL import Image,ImageDraw
from transformers import Sam2Model,Sam2Processor

ROOT=Path(__file__).resolve().parents[2]
DATA=Path('/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data')
PS=DATA/'sources/PSBench-data'
SCHEMA={'type':'object','additionalProperties':False,'required':['preserved_target','box_2d','note'],
        'properties':{'preserved_target':{'type':'string'},'note':{'type':'string'},
                      'box_2d':{'type':'array','items':{'type':'integer','minimum':0,'maximum':1000},'minItems':4,'maxItems':4}}}

def b64(img):
    buf=io.BytesIO();img.save(buf,'PNG');return base64.b64encode(buf.getvalue()).decode()

def ground(args,task,instruction,start):
    msgs=[{'role':'user','content':[
        {'type':'text','text':'Instruction given to an image editor:\n'+instruction+'\n\nWhich single object or region does the instruction ask to keep or preserve '
         '(e.g. the subject, a face)? If several, choose the main subject. Return its bounding box on this image as [x1,y1,x2,y2] in 0-1000 '
         'normalised coordinates. Return only JSON.'},
        {'type':'image_url','image_url':{'url':'data:image/png;base64,'+b64(start)}}]}]
    # temperature 0 with guided JSON can loop on whitespace for this model; use its recommended sampling with a fixed seed.
    body={'model':args.model,'messages':msgs,'temperature':0.6,'top_p':0.95,'seed':0,'max_tokens':8000,
          'response_format':{'type':'json_schema','json_schema':{'name':'box','schema':SCHEMA}}}
    r=httpx.post(f'{args.base_url}/chat/completions',json=body,timeout=900);r.raise_for_status()
    return json.loads(r.json()['choices'][0]['message']['content'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-url',default='http://localhost:8001/v1')
    ap.add_argument('--model',default='Qwen3.5-397B-A17B-FP8');ap.add_argument('--device',default='cuda:0');args=ap.parse_args()
    tasks=sorted({r['task_id'] for r in csv.DictReader(open(ROOT/'motivation/m3/candidates_manifest.csv'))})
    strata={r['task_id']:r for r in csv.DictReader(open(ROOT/'motivation/m3/hard_strata.csv'))}
    tasks=[t for t in tasks if strata[t]['preservation_regex']=='True']
    proc=Sam2Processor.from_pretrained(DATA/'models/sam2.1-hiera-large')
    sam=Sam2Model.from_pretrained(DATA/'models/sam2.1-hiera-large').to(args.device).eval()
    sheet=[];log=[]
    for task in tasks:
        t=json.loads((PS/task/f'{task}.json').read_text());start=Image.open(PS/task/t['resources']['input_file']).convert('RGB')
        g=ground(args,task,t['instruction'],start);W,H=start.size
        box=[g['box_2d'][0]*W/1000,g['box_2d'][1]*H/1000,g['box_2d'][2]*W/1000,g['box_2d'][3]*H/1000]
        inputs=proc(images=start,input_boxes=[[box]],return_tensors='pt').to(args.device)
        with torch.no_grad():out=sam(**inputs,multimask_output=False)
        mask=proc.post_process_masks(out.pred_masks.cpu(),inputs['original_sizes'].cpu())[0][0,0].numpy()
        d=DATA/'m3/masks'/task;d.mkdir(parents=True,exist_ok=True)
        Image.fromarray((mask*255).astype(np.uint8)).save(d/'subject_proposed.png')
        over=start.copy();tint=Image.new('RGB',start.size,(255,0,0))
        over=Image.composite(Image.blend(over,tint,0.45),over,Image.fromarray((mask*255).astype(np.uint8)))
        ImageDraw.Draw(over).rectangle(box,outline=(0,255,0),width=max(2,W//200))
        over.thumbnail((480,480));sheet.append((task,g['preserved_target'],over))
        log.append(dict(task_id=task,preserved_target=g['preserved_target'],box_2d=g['box_2d'],mask_fraction=round(float(mask.mean()),4),note=g['note']))
        print(task,g['preserved_target'],round(float(mask.mean()),3),flush=True)
    (ROOT/'motivation/m3/mask_proposals.json').write_text(json.dumps(log,indent=1)+'\n')
    cols=6;cell=500;img=Image.new('RGB',(cols*cell,((len(sheet)+cols-1)//cols)*cell),'white');dr=ImageDraw.Draw(img)
    for i,(task,target,o) in enumerate(sheet):
        x,y=(i%cols)*cell,(i//cols)*cell;img.paste(o,(x+10,y+10));dr.text((x+10,y+cell-28),f'{task}: {target}'[:70],fill='black')
    img.save(DATA/'m3/masks/contact_sheet.png');print(json.dumps({'proposed':len(log),'sheet':str(DATA/'m3/masks/contact_sheet.png')}))
if __name__=='__main__':main()
