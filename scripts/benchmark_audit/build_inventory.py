"""Build the M1 task inventory from pinned benchmark sources.

Only facts readable from source files are recorded here (instruction, difficulty,
raw evaluator, reference availability, documentation given by the base harness).
Judgement labels (instruction form, required knowledge, evaluator type) belong in
annotations.csv, not here.
"""
from pathlib import Path
import argparse,csv,glob,json,os,re,subprocess

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_SOURCES='/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data/sources'
FIELDS=['benchmark','task_id','group','difficulty','category','app','instruction','evaluator_raw','has_reference_output',
        'docs_given_base','visualskill_selected','instruction_issue','source_file','source_rev']
# Documentation the benchmark's own harness passes to the agent, read from code (see summary.md for evidence).
DOCS={'PSBench':'none','OSWorld':'none','OSExpert':'none_in_base_harness','CUA-World':'none_in_base_harness'}
DRAFT_LEAK=re.compile(r'^\s*\*\s+(Wait|Actually)\b',re.M)

def rev(path):
    return subprocess.run(['git','-C',str(path),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()

def funcs(evaluator):
    f=evaluator.get('func','')
    return json.dumps(f if isinstance(f,list) else [f])

def psbench(src):
    root=src/'PSBench-data';sha='929d0710eb7c86a988f8a69a74619052b60ac293'
    for d in sorted(root.glob('[0-9]*')):
        t=json.loads((d/f'{d.name}.json').read_text());r=json.loads((d/t['rubric_file']).read_text())
        yield dict(task_id=t['id'],group='judge_policy='+r.get('judge_policy','default'),difficulty=t['difficulty_level'],category=t['type'],app='photoshop',
                   instruction=t['instruction'],evaluator_raw=json.dumps({'vlm_rubric':len(r['criteria'])}),
                   has_reference_output=(d/t['reference_output']['expected_file']).is_file(),source_file=d/f'{d.name}.json',source_rev=sha)

def osworld(src):
    repo=src/'OSWorld';sha=rev(repo)
    for f in sorted((repo/'evaluation_examples/examples/gimp').glob('*.json')):
        t=json.loads(f.read_text())
        yield dict(task_id=t['id'],group='examples/gimp',app='gimp',instruction=t['instruction'],evaluator_raw=funcs(t['evaluator']),
                   has_reference_output='expected' in t['evaluator'],source_file=f,source_rev=sha)

def osexpert(src):
    repo=src/'OSExpert';base=repo/'OSWorld/evaluation_examples_expert';sha=rev(repo)
    for split in ['eval_long_horizon_gimp.json','eval_data_low.json']:
        for rel in json.loads((base/split).read_text()):
            f=base/rel;t=json.loads(f.read_text())
            # data_low mixes GIMP and Impress tasks and leaves related_apps empty; keep GIMP ones only.
            if 'gimp' not in json.dumps(t.get('config',[])).lower() and 'gimp' not in rel:continue
            yield dict(task_id=f'{f.parent.name}/{f.stem}',group=f.parent.relative_to(base/'OSExpert_Eval').as_posix(),
                       difficulty=';'.join(t.get('type',[])),app='gimp',instruction=t['instruction'],evaluator_raw=funcs(t.get('evaluator',{})),
                       has_reference_output='expected' in t.get('evaluator',{}),source_file=f,source_rev=sha)

def cua_world(src,selected):
    repo=src/'gym-anything';sha=rev(repo)
    for f in sorted((repo/'benchmarks/cua_world/environments/opentoonz_env/tasks').glob('*/task.json')):
        t=json.loads(f.read_text());name=f.parent.name
        yield dict(task_id=name,group='opentoonz',difficulty=t.get('difficulty',''),app='opentoonz',instruction=t['description'],
                   evaluator_raw=json.dumps([t['success']['spec'].get('program','')]),has_reference_output='',
                   visualskill_selected=selected.get(name,'unknown'),source_file=f,source_rev=sha)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--sources',default=os.getenv('VE_SOURCES',DEFAULT_SOURCES))
    ap.add_argument('--out',default=ROOT/'motivation/benchmark_audit/task_inventory.csv');args=ap.parse_args()
    src=Path(args.sources);out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    # VisualSkill's 21-task OpenToonz selection was recorded in the earlier audit from its pinned stage-2 config.
    old=csv.DictReader(open(ROOT/'motivation/task_audit/initial_task_inventory.csv',encoding='utf-8'))
    selected={r['task_id']:r['visualskill_selected'] for r in old if r['source']=='CUA-World'}
    rows=[]
    for bench,gen in [('PSBench',psbench(src)),('OSWorld',osworld(src)),('OSExpert',osexpert(src)),('CUA-World',cua_world(src,selected))]:
        for r in gen:
            r.update(benchmark=bench,docs_given_base=DOCS[bench],source_file=Path(r['source_file']).relative_to(src).as_posix(),
                     instruction_issue='leaked_drafting_text' if DRAFT_LEAK.search(r['instruction']) else '')
            rows.append({k:r.get(k,'') for k in FIELDS})
    with out.open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,FIELDS);w.writeheader();w.writerows(rows)
    counts={}
    for r in rows:counts[r['benchmark']]=counts.get(r['benchmark'],0)+1
    print(json.dumps({'out':str(out),'counts':counts}))
if __name__=='__main__':main()
