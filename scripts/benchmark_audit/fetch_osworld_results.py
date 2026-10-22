"""Collect published per-task GIMP scores from xlangai/ubuntu_osworld_verified_trajs.

Reads only result.txt members of each remote zip (HTTP range reads), never the screenshots.
Output: motivation/benchmark_audit/published_results_osworld_gimp.csv (one row per agent run x task).
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import csv,re,zipfile
from huggingface_hub import HfFileSystem

ROOT=Path(__file__).resolve().parents[2]
BASE='datasets/xlangai/ubuntu_osworld_verified_trajs/'
TASK=re.compile(r'(?:^|/)gimp/([0-9a-f-]{36})/result\.txt$')

def scores(name):
    fs=HfFileSystem();rows=[]
    try:
        with fs.open(BASE+name,'rb',block_size=2**20) as f:
            zf=zipfile.ZipFile(f)
            for m in zf.namelist():
                hit=TASK.search(m)
                if not hit:continue
                text=zf.read(m).decode(errors='ignore').strip()
                try:score=float(text)
                except ValueError:score=''
                rows.append({'agent_zip':name,'member':m,'task_id':hit.group(1),'score':score})
    except Exception as e:
        rows.append({'agent_zip':name,'member':f'ERROR {e!r}'[:200],'task_id':'','score':''})
    print(name,len(rows),flush=True)
    return rows

def main():
    zips=sorted(p.split('/')[-1] for p in HfFileSystem().ls(BASE,detail=False) if p.endswith('.zip'))
    with ThreadPoolExecutor(8) as ex:rows=[r for rs in ex.map(scores,zips) for r in rs]
    out=ROOT/'motivation/benchmark_audit/published_results_osworld_gimp.csv'
    with out.open('w',newline='') as h:
        w=csv.DictWriter(h,['agent_zip','member','task_id','score']);w.writeheader();w.writerows(rows)
    print(out,len(rows))
if __name__=='__main__':main()
