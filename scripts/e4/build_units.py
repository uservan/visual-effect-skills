"""E4: turn mirrored manuals into page-level units (one HTML page = one unit).

Keeps pages about tools / filters / adjustments / modules, where effect questions can be asked.
Output: $DATA/e4/units_<app>.jsonl with {app, unit_id, url_path, title, text}.
"""
from pathlib import Path
import argparse,hashlib,json,re
from bs4 import BeautifulSoup

DATA=Path('/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data')
# Path fragments of pages that document a tool, filter, adjustment or processing module.
TOPIC={'gimp':r'/filters-|/gimp-tool-|/gimp-filter-|/plug-in-|/gimp-layer-|/gimp-image-',
       'darktable':r'/module-reference/',
       'krita':r'/reference_manual/(filters|tools|dockers|layers_and_masks|blending_modes)',
       'opentoonz':r'',
       'photoshop':r'/photoshop/using/'}
MAIN=['main','article','[role=main]','.document','#content','.body']

def text_of(html):
    soup=BeautifulSoup(html,'html.parser')
    for t in soup(['script','style','nav','header','footer','aside']):t.decompose()
    node=next((soup.select_one(s) for s in MAIN if soup.select_one(s)),soup.body or soup)
    title=(soup.title.get_text(' ',strip=True) if soup.title else '')
    text=re.sub(r'\n{3,}','\n\n',node.get_text('\n',strip=True))
    return title,text

def sections(html):
    """Split a single-page manual (ReadTheDocs htmlzip) into its second-level sections."""
    soup=BeautifulSoup(html,'html.parser')
    for t in soup(['script','style','nav','header','footer','aside']):t.decompose()
    for sec in soup.select('section > section, div.section > div.section'):
        head=sec.find(['h2','h3']);anchor=sec.get('id','')
        if head:yield anchor,head.get_text(' ',strip=True),re.sub(r'\n{3,}','\n\n',sec.get_text('\n',strip=True))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('apps',nargs='+');ap.add_argument('--min-chars',type=int,default=800)
    args=ap.parse_args();(DATA/'e4').mkdir(parents=True,exist_ok=True)
    for app in args.apps:
        root=DATA/'manuals'/app;seen=set();n=0
        with (DATA/'e4'/f'units_{app}.jsonl').open('w') as h:
            for p in sorted(root.rglob('*.html')):
                rel='/'+p.relative_to(root).as_posix()
                if not re.search(TOPIC[app],rel):continue
                html=p.read_text(errors='ignore')
                parts=[(f'{rel}#{a}',t,x) for a,t,x in sections(html)] if app=='opentoonz' else [(rel,*text_of(html))]
                for path,title,text in parts:
                    digest=hashlib.sha1(text.encode()).hexdigest()[:12]
                    if len(text)<args.min_chars or digest in seen:continue  # skip stubs and duplicate pages
                    seen.add(digest);n+=1
                    h.write(json.dumps({'app':app,'unit_id':f'{app}-{digest}','url_path':path,'title':title,'text':text[:12000]},ensure_ascii=False)+'\n')
        print(app,n,'units')
if __name__=='__main__':main()
