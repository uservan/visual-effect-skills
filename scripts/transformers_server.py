"""Single-request local Holo GUI inference fallback using existing CUDA PyTorch.

BF16 on >=65 GiB devices; NF4 on smaller devices. Precision is immutable for
one server and reported to all paired episode manifests. GUI tools only are
exposed by the client. No model-generated code is evaluated here.
"""
import argparse,base64,hmac,io,json,os,re,time,uuid
from pathlib import Path
from threading import Lock

def parse_tools(text):
    calls=[]
    for name,body in re.findall(r'<function=([^>]+)>(.*?)</function>',text,re.S):
        args={}
        for key,value in re.findall(r'<parameter=([^>]+)>(.*?)</parameter>',body,re.S):
            value=value.strip()
            try:args[key]=json.loads(value)
            except json.JSONDecodeError:args[key]=value
        calls.append({'id':'call_'+uuid.uuid4().hex[:12],'type':'function','function':{'name':name.strip(),'arguments':json.dumps(args)}})
    visible=re.sub(r'<tool_call>.*?</tool_call>','',text,flags=re.S)
    visible=re.sub(r'<think>.*?</think>','',visible,flags=re.S)
    for marker in ['<|im_end|>','<|endoftext|>']:visible=visible.replace(marker,'')
    return visible.strip(),calls

def main():
    import torch
    from transformers import AutoModelForImageTextToText,AutoProcessor,BitsAndBytesConfig
    from PIL import Image
    from fastapi import FastAPI,Header,HTTPException
    import uvicorn
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=18080);a=p.parse_args()
    rt=Path('/scratch/pioneer/jobs/wxy320/visual_effect_runtime');weights=rt/'models/Holo4-27B'
    if not torch.cuda.is_available():raise SystemExit('Existing CUDA PyTorch cannot access GPU')
    total=torch.cuda.get_device_properties(0).total_memory
    precision='bf16' if total>=65*1024**3 else 'nf4'
    kwargs={'torch_dtype':torch.bfloat16,'device_map':{'':0},'low_cpu_mem_usage':True,'attn_implementation':'sdpa'}
    if precision=='nf4':kwargs['quantization_config']=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_compute_dtype=torch.bfloat16,bnb_4bit_use_double_quant=True)
    torch.manual_seed(42)
    model=AutoModelForImageTextToText.from_pretrained(str(weights),**kwargs).eval()
    processor=AutoProcessor.from_pretrained(str(weights))
    manifest={'backend':'transformers','precision':precision,'torch_version':torch.__version__,'cuda_runtime':torch.version.cuda,'gpu':torch.cuda.get_device_name(0),'model_id':'Hcompany/Holo4-27B'}
    (rt/'active_model_server.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest),flush=True)
    secret=(rt/'model_api_key').read_text().strip();lock=Lock();app=FastAPI()
    def authenticate(auth):
        if not auth or not hmac.compare_digest(auth,'Bearer '+secret):raise HTTPException(401,'Invalid API key')
    @app.get('/v1/models')
    def models(authorization:str=Header(default='')):
        authenticate(authorization);return {'object':'list','data':[{'id':'Holo4-27B','object':'model'}]}
    @app.post('/v1/chat/completions')
    def complete(body:dict,authorization:str=Header(default='')):
        authenticate(authorization)
        msgs=[]
        for msg in body['messages']:
            m=dict(msg);content=m.get('content')
            if isinstance(content,list):
                blocks=[]
                for b in content:
                    if b.get('type')=='image_url':
                        url=b['image_url']['url']
                        if not url.startswith('data:image/'):raise HTTPException(400,'Only inline test screenshots allowed')
                        raw=base64.b64decode(url.split(',',1)[1],validate=True)
                        blocks.append({'type':'image','image':Image.open(io.BytesIO(raw)).convert('RGB')})
                    else:blocks.append(b)
                m['content']=blocks
            elif content is None:m['content']=''
            # HF template requires tool arguments as mappings.
            if m.get('tool_calls'):
                m['tool_calls']=json.loads(json.dumps(m['tool_calls']))
                for c in m['tool_calls']:
                    if isinstance(c['function']['arguments'],str):c['function']['arguments']=json.loads(c['function']['arguments'])
            msgs.append(m)
        with lock,torch.inference_mode():
            inputs=processor.apply_chat_template(msgs,tools=body.get('tools',[]),tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt',enable_thinking=False).to(model.device)
            if inputs['input_ids'].shape[1]>24576:raise HTTPException(400,'Pilot context budget exceeded')
            output=model.generate(**inputs,max_new_tokens=min(1024,body.get('max_tokens',1024)),do_sample=False)
            tokens=output[0,inputs['input_ids'].shape[1]:]
            text=processor.decode(tokens,skip_special_tokens=False)
            visible,calls=parse_tools(text)
            msg={'role':'assistant','content':visible or None}
            if calls:msg['tool_calls']=calls
            return {'id':'chatcmpl-'+uuid.uuid4().hex,'object':'chat.completion','model':'Holo4-27B','choices':[{'index':0,'message':msg,'finish_reason':'tool_calls' if calls else 'stop'}],'usage':{'prompt_tokens':inputs['input_ids'].shape[1],'completion_tokens':len(tokens),'total_tokens':inputs['input_ids'].shape[1]+len(tokens)}}
    uvicorn.run(app,host='0.0.0.0',port=a.port)
if __name__=='__main__':main()
