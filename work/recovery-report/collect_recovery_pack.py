from pathlib import Path
import json,hashlib,shutil,zipfile
ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).parent;PACK=WORK/'reference_pack';OUT=ROOT/'outputs'
IP=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261027_IPHONE_WIDE');RUN=IP/'recovery-v2';OLD=ROOT/'work/report/reference_pack'
manual=json.loads((RUN/'analysis/architect-review.json').read_text(encoding='utf-8'));stage=manual['display_stage']
records=[]
def copy(src,rel):
    src=Path(src)
    if not src.is_file():raise FileNotFoundError(src)
    dst=PACK/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    hs=hashlib.sha256(src.read_bytes()).hexdigest();assert hashlib.sha256(dst.read_bytes()).hexdigest()==hs
    records.append({'file':str(Path(rel)).replace('\\','/'),'source':str(src),'bytes':src.stat().st_size,'sha256':hs})
for p in (RUN/'analysis').glob('*.json'):copy(p,'records/'+p.name)
for folder in [f'verification-{stage}','verification-allviews-raw','verification-alternative-kitchen-raw','seam-ablation','seam-ablation-allviews-raw']:
    for p in (RUN/'analysis'/folder).glob('*'):
        if p.suffix in ['.png','.json']:copy(p,'screenshots/'+folder+'/'+p.name)
for pattern in ['allviews-proj*.jpg','*door-0*.jpg','wide-bridge-witness.jpg','allviews-elevation-and-floorplan.png']:
    for p in (RUN/'analysis').glob(pattern):copy(p,'images/'+p.name)
for p in (RUN/'exports').glob('*allviews*.compression.json'):copy(p,'records/'+p.name)
for p in (IP/'scripts').glob('*.py'):
    if p.name.startswith(tuple(f'{n:02d}_' for n in [5,6,7,8,9,12,20,21,22,23,24,25,26,27,28,29,30])) or p.name in ['reconstruction_frame.py','colmap_io.py','pipeline_guard.py']:copy(p,'implementation/scripts/'+p.name)
for p in (IP/'viewer-src').glob('*'):
    if p.is_file() and p.suffix in ['.js','.mjs','.html','.json']:copy(p,'implementation/viewer-src/'+p.name)
copy(RUN/'architect-mandate.txt','architect-mandate.txt')
copy(IP/'review/cameras.json','records/delivery-cameras.json')
copy(IP/'colmap-gpu/merged/sparse/0/cameras.txt','records/corrected-colmap-cameras.txt')
copy(IP/'colmap-gpu/merged/sparse/0/FRAME.json','records/corrected-colmap-FRAME.json')
copy(IP/'analysis/active-pipeline.json','records/active-pipeline.json')
for p in (OLD/'records').glob('*'):copy(p,'historical-three-models/records/'+p.name)
for name in ['F01-user-reported-iphone.png','F03-samsung-accepted.png','F04-codex-nikon-034.png','F05-codex-nikon-source-comparison.jpg','F13-samsung-source-bedroom.jpg','F14-samsung-source-bathroom.jpg']:copy(OLD/'images'/name,'historical-three-models/images/'+name)
copy(OLD/'manifest.json','historical-three-models/manifest.json');copy(OLD/'codex-nikon-provenance.json','historical-three-models/codex-nikon-provenance.json')
copy(OUT/'Gemini_Argon_Reconstruction_Architecture_Report_2026-10-27.pdf','historical-three-models/original-architecture-report.pdf')
copy(OUT/'Gemini_Argon_iPhone_Recovery_Verification_2026-10-27.pdf','recovery-verification-report.pdf')
readme='''IPHONE WIDE RECOVERY - READ FIRST

The report distinguishes completed rebuilds from failed/uncertain acceptance gates.
The user's chosen primary is the full native 11,891,853-triangle / 435.6 MB model.
Size and triangle delivery caps were explicitly removed. Native geometry is retained exactly.
Read architect-review.json for remaining visual reconstruction defects.

screenshots/: Actual before/after WebGL source comparisons, overview and depth diagnostics.
records/: Input audits, component transforms, exact commands, verification, sampler results.
implementation/: Current reproducible scripts and viewer source. Legacy temporal commands are guarded.
historical-three-models/: The original report and approved Codex Nikon 034 / Samsung references.

No new Nikon or Samsung compute or edits were performed. These references were copied from the prior report pack.
Large checkpoints, native GLBs and video sources stay in the local scan folder; paths and hashes are recorded.
The separate 584.6 MB offline HTML embeds the complete native model in 18 bounded pieces and eight source photos.
Its decoded model hash matches the native GLB exactly. Archived small-mesh failures are not primary delivery.
No report, model or message was sent to Gemini or published externally.
'''
(PACK/'README.txt').write_text(readme,encoding='utf-8')
manifest={'prepared_date':'2026-10-27','status':manual['status'],'display_stage':stage,'records':records,'all_copied_hashes_verified':True}
(PACK/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
ZIP=OUT/'Gemini_Argon_iPhone_Recovery_Evidence_2026-10-27.zip'
with zipfile.ZipFile(ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(PACK.rglob('*')):
        if p.is_file():z.write(p,str(p.relative_to(PACK)).replace('\\','/'))
with zipfile.ZipFile(ZIP) as z:assert z.testzip() is None
print(json.dumps({'zip':str(ZIP),'bytes':ZIP.stat().st_size,'copied_files':len(records),'sha256':hashlib.sha256(ZIP.read_bytes()).hexdigest()}))
