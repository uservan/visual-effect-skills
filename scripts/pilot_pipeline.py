"""Run an A/B smoke pair once its existing GPU reservation starts.

No new GPU jobs are submitted. Status/checkpoint files survive interruption.
"""
from pathlib import Path
import argparse,json,os,secrets,signal,subprocess,time,zipfile
import httpx
ROOT=Path(__file__).resolve().parents[1]
RT=Path('/scratch/pioneer/jobs/wxy320/visual_effect_runtime')
ART=Path('/scratch/pioneer/jobs/wxy320/save/visual-effect-skills')

def save(stage, **extra):
    data={'stage':stage,'updated_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'cpu_job':os.getenv('SLURM_JOB_ID'),**extra}
    temp=ART/'pipeline_status.tmp';temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(ART/'pipeline_status.json')
    print(json.dumps(data),flush=True)

def stop(p):
    if p is not None and p.poll() is None:
        os.killpg(p.pid,signal.SIGTERM)
        try:p.wait(timeout=20)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()

def check_download():
    m=json.loads((ROOT/'motivation/runtime/model_manifest.json').read_text());model=Path(m['weights_path'])
    # Do not infer download completion from directory existence.
    index=json.loads((model/'model.safetensors.index.json').read_text())
    for name in set(index['weight_map'].values()):
        if not (model/name).is_file():return False
    return all((model/n).is_file() for n in ['config.json','tokenizer_config.json','tokenizer.json','preprocessor_config.json','chat_template.jinja'])

def main(gpu_job):
    ART.mkdir(parents=True,exist_ok=True);server=vm=None
    try:
        save('waiting_for_prepared_artifacts',gpu_job=gpu_job)
        deadline=time.monotonic()+5400
        while True:
            try:ready=check_download() and (RT/'qemu-root/usr/bin/qemu-system-x86_64').exists() and (RT/'transformers-venv/bin/python').exists() and (RT/'transformers_env.ready').exists()
            except (FileNotFoundError,json.JSONDecodeError):ready=False
            if ready:break
            if time.monotonic()>deadline:raise TimeoutError('Prepared model/runtime artifacts unavailable after 90 minutes')
            time.sleep(30)
        node=subprocess.check_output(['squeue','-h','-j',gpu_job,'-o','%N'],text=True).strip()
        state=subprocess.check_output(['squeue','-h','-j',gpu_job,'-o','%T'],text=True).strip()
        if state!='RUNNING' or not node or ',' in node or '[' in node:raise RuntimeError('GPU allocation not running on one node: '+state+' '+node)
        key=RT/'model_api_key'
        if not key.exists():
            fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32)+'\n')
        save('starting_model',gpu_job=gpu_job,gpu_node=node)
        step_env={k:v for k,v in os.environ.items() if not k.startswith('SLURM_') or k=='SLURM_CONF'}
        with (RT/'model_server.log').open('a') as log:
            server=subprocess.Popen(['srun','--jobid='+gpu_job,'--overlap','--ntasks=1','--cpus-per-task=12','bash',str(ROOT/'scripts/serve_holo.sh')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=step_env)
        url='http://'+node+':18080/v1'
        with httpx.Client(timeout=10,trust_env=False) as client:
            deadline=time.monotonic()+1800
            while True:
                if server.poll() is not None:raise RuntimeError('Model server exited; inspect '+str(RT/'model_server.log'))
                try:
                    r=client.get(url+'/models',headers={'Authorization':'Bearer '+key.read_text().strip()})
                    if r.status_code==200:break
                except httpx.HTTPError:pass
                if time.monotonic()>deadline:raise TimeoutError('Model readiness timeout')
                time.sleep(10)
        for condition in ['A','B']:
            save('booting_desktop',condition=condition,gpu_job=gpu_job)
            with (RT/('desktop_'+condition+'.log')).open('a') as log:
                vm=subprocess.Popen(['bash',str(ROOT/'scripts/start_desktop.sh')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            with httpx.Client(timeout=10,trust_env=False) as client:
                deadline=time.monotonic()+600
                while True:
                    if vm.poll() is not None:raise RuntimeError('Desktop process exited; inspect desktop_'+condition+'.log')
                    try:
                        r=client.get('http://127.0.0.1:15000/screenshot')
                        if r.status_code==200:break
                    except httpx.HTTPError:pass
                    if time.monotonic()>deadline:raise TimeoutError('Desktop readiness timeout')
                    time.sleep(5)
            save('running_episode',condition=condition,gpu_job=gpu_job)
            rc=subprocess.call([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/recorded_pilot.py'),'--condition',condition,'--model-url',url])
            stop(vm);vm=None
            subprocess.check_call([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/build_viewer.py')])
            if rc:raise RuntimeError('Episode invalid; inspect result.json. Stop paired pilot rather than fabricate a score.')
        save('completed_pair',gpu_job=gpu_job,viewer=str(ART/'index.html'))
    except Exception as e:
        save('blocked',gpu_job=gpu_job,error=repr(e));raise
    finally:
        stop(vm);stop(server)
        # Release only the dedicated reservation passed explicitly to this pilot.
        # User's CPU entry job and all unrelated experiments remain untouched.
        subprocess.run(['scancel',gpu_job],check=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--gpu-job',required=True);main(p.parse_args().gpu_job)
