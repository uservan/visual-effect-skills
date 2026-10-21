"""Check GIMP T4's verifier on an exact known horizontal reflection.

This creates a verifier unit fixture, not an agent episode or benchmark score.
"""
import importlib.util,json,urllib.request,hashlib
from pathlib import Path
from PIL import Image

def main():
    out=Path('/scratch/pioneer/jobs/wxy320/save/visual-effect-skills/verifier_audit');out.mkdir(exist_ok=True)
    source=out/'source.jpg'
    if not source.exists():
        url='https://huggingface.co/datasets/xlangai/ubuntu_osworld_file_cache/resolve/main/gimp/77b8ab4d-994f-43ac-8930-8ca087d7c4b4/The_Lost_River_Of_Dreams.jpg'
        with urllib.request.urlopen(url,timeout=30) as r:source.write_bytes(r.read())
    Image.open(source).transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(out/'perfect_mirror.png')
    records=[]
    for path in [Path('/scratch/pioneer/jobs/wxy320/visual_effect_sources/visualskill_pinned_gimp.py'),Path('/scratch/pioneer/jobs/wxy320/visual_effect_sources/OSWorld/desktop_env/evaluators/metrics/gimp.py')]:
        spec=importlib.util.spec_from_file_location('metrics',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        scores={}
        for name in ['check_file_exists_and_structure_sim','check_image_mirror']:
            scores[name]=float(getattr(m,name)(str(out/'perfect_mirror.png'),str(source)))
        row={'source':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'perfect_mirror':scores,'conjunction_passes':all(x==1 for x in scores.values())};records.append(row);print(row,flush=True)
    (out/'gimp_T4_sanity.json').write_text(json.dumps({'type':'verifier_sanity_only_not_agent_episode','records':records},indent=2)+'\n')
if __name__=='__main__':main()
