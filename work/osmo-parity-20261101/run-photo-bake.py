from pathlib import Path
import json,subprocess,sys
W=Path(__file__).resolve().parent;OLD=W.parent/'osmo-improve-20261031';mode=sys.argv[1] if len(sys.argv)>1 else 'native';is_tsdf=mode in ['tsdf','poisson'];OUT=W/('review/poisson-pilot' if mode=='poisson' else 'review/tsdf-pilot' if is_tsdf else 'review/mesh-pilot');source=(OLD/'photo_bake_agent.py').read_text()
source=source.replace("str(HERE/'pydeps')",repr(str(OLD/'pydeps'))).replace("str(HERE.parent/'osmo-reconstruct-20261031')",repr(str(W.parent/'osmo-reconstruct-20261031')))
source=source.replace("p.add_argument('--images-root'", "p.add_argument('--selection',type=Path,required=False);p.add_argument('--images-root'")
source=source.replace("    sources=[]\n", "    selected=json.loads(args.selection.read_text())['selected'] if args.selection else []; source_times={r['filename']:r['time_seconds'] for r in selected}\n    sources=[]\n")
source=source.replace("time_bin=int(((frame-1)/2)/args.time_group_seconds)", "time_seconds=source_times[Path(im['name']).name] if args.selection else (frame-1)/2;time_bin=int(time_seconds/args.time_group_seconds)")
source=source.replace('1.8325957','1.72787596')
source=source.replace('math.radians(100)','math.radians(94)').replace("'theta_center_degrees':100","'theta_center_degrees':94")
source=source.replace("re.search(r'(\\d+)$',Path(im['name']).stem)","re.search(r'frame_(\\d+)',Path(im['name']).stem)")
script=OUT/'photo-bake-implementation.py';script.write_text(source)
selection=json.loads((W/'frame-selection.json').read_text());eval_names={r['filename'] for r in selection['selected'] if r['split']=='eval'}
prepared=json.loads((W/'highres-preparation.json').read_text());audit=json.loads((Path(prepared['originalDataset'])/'explicit-pinhole-audit.json').read_text());native=Path(audit['sourceDataset'])
sys.path.insert(0,str(W.parent/'osmo-reconstruct-20261031'));from seed_fisheye import read_model
_,ims,_=read_model(native/'sparse/0');excluded=sorted(im['name'] for im in ims.values() if Path(im['name']).name in eval_names)
python312='C:/Users/bombe/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
command=[python312,str(script),'--mesh',str(OUT/('surface-uncompressed.glb' if is_tsdf else 'texture-preview-uncompressed.glb')),'--dataset',str(native),'--selection',str(W/'frame-selection.json'),'--output',str(OUT/'photo-baked-uncompressed.glb'),'--texture-size','4096','--face-size','1024','--mask-erosion','8','--exclude-images',','.join(excluded),'--min-time-groups','3','--time-group-seconds','3','--visibility-absolute','.025','--visibility-relative','.006']
for name in ['photo-bake-job.json','photo-bake.log','photo-bake-request.json']:
    file=OUT/name
    if file.exists():
        index=1
        while file.with_name(file.name+f'.failed-{index:02d}').exists():index+=1
        preserved=file.with_name(file.name+f'.failed-{index:02d}')
        assert file.resolve().parent==OUT.resolve()
        file.rename(preserved)
request={'stage':'native-3840-true-photo-bake','command':command,'cwd':str(W),'log':str(OUT/'photo-bake.log'),'status':str(OUT/'photo-bake-job.json'),'provenance':{'sourceRGB':'Native 3840x3840; final audited source operator and mirror masks','timestamps':'Exact adaptive-selection timestamps; not old 2fps assumptions','excludedEvalImages':excluded,'originalFilesModified':False,'onlyLocalPilot':True}}
(OUT/'photo-bake-request.json').write_text(json.dumps(request,indent=2));raise SystemExit(subprocess.call([sys.executable,str(W/'run_logged_job.py'),str(OUT/'photo-bake-request.json')]))
