from pathlib import Path
import json,shutil,hashlib,datetime
IP=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261027_IPHONE_WIDE');RUN=IP/'recovery-v2'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,d):Path(p).write_text(json.dumps(d,indent=2),encoding='utf-8')
path=RUN/'analysis/architect-review.json';m=read(path)
if m['display_stage']!='full-native' and not (RUN/'analysis/architect-review-small-candidate.json').exists():shutil.copy2(path,RUN/'analysis/architect-review-small-candidate.json')
controls=read(RUN/'analysis/verification-full-native/fixed-controls-check.json');assert controls['passed'] and len(controls['checks'])==33
perf=next(x['evidence'] for x in controls['checks'] if x['name'].startswith('60 FPS'));orbit=next(x['evidence'] for x in controls['checks'] if x['name'].startswith('Full model orbit'))
m.update(display_stage='full-native',status='FULL NATIVE DELIVERED - size and triangle caps removed; visible reconstruction defects remain',summary=f'The full native reconstruction is now the primary export: 11,891,853 triangles / 435.61 MB, with every native position, normal, UV and triangle preserved. The user explicitly chose full native geometry and removed the delivery size/count caps. The actual native viewer passed all 33 browser/offline checks at {perf["averageFps"]:.1f} FPS. Its 584.63 MB standalone viewer decodes to the same native GLB hash. Living-room and bedroom coverage are substantially improved; doorway-wall tearing and small-object distortion remain.',primary_delivery_state='Published full native GLB, corrected camera model, HTTP viewer and self-contained offline viewer. Delivery size and triangle caps removed by explicit user choice.',promote_improved_candidate=True,delivery_complete=True,visual_fidelity_complete=False)
m['views'][2]['finding']='The door is more coherent after restoring all usable views. The adjacent wall remains a torn foreground structure already present in the native extraction. Delivery preserves it unchanged; this view still fails full visual fidelity.'
m['compaction_finding']='Archived small-candidate measurements explain the delivery decision: the living mesh reached 24.23 mm native-to-fast distance and 7.40 mm in reverse, with 99th percentiles 3.46 / 3.32 mm and about 8% of samples above 2 mm. The user selected the full native extraction instead. Its primary GLB and decoded offline payload are byte-identical to the merged native reference, so no simplification displacement is introduced. This is an export-preservation result, not a claim of 2 mm physical accuracy.'
m['remaining_issues']=[
 'Frame 1398 still contains torn wall geometry inside the unified living component. Restoring all usable views improves the door but does not fully solve the wall.',
 'Kitchen-front floor gaps, cabinet-side perforations, softened small objects and a few bedroom wall patches remain in the native extraction.',
 'The kitchen join remains approximate: the wider bridge did not provide three orthogonal distributed constraints, and the candidate transform was rejected.',
 'Native geometry preservation and zero newly empty pixels prove delivery integrity, not full source fidelity, independent generalization or surveyed dimensional accuracy.'
]
m['recommendations']=[
 'Keep the published full native reconstruction as the primary baseline. Do not reintroduce count/byte-driven decimation unless the user later requests it.',
 'Target the remaining doorway defect with a bounded extraction/occupancy or depth/normal-supervision ablation, judged from the same source cameras. Preserve the current native reference.',
 'Do not reuse the temporal bedroom split, local bedroom tilt, nearest-camera crop or an unsupported wall patch. Any inferred geometric repair should be explicit and separately reviewable.',
 'If precise kitchen registration is required, use the existing unused doorway footage and line/plane constraints. The weak wall-only bridge should remain rejected.'
]
m['architect_questions']=[
 'The user has resolved the size/geometry tradeoff in favor of full native delivery. For the remaining same-component doorway tearing, should the next controlled experiment vary extraction/occupancy settings or depth/normal supervision?',
 'Is the retained approximate kitchen join sufficient for visual review, or should a camera/line/plane registration pass on the existing footage become the next hard quality gate?',
 'If blank-wall evidence stays weak, should an explicitly labelled plane-inference derivative be explored while the full native reconstruction remains unchanged?'
]
m['delivery_decision']=read(RUN/'analysis/delivery-decision.json');save(path,m)
report=read(RUN/'analysis/full-native-verification.json');report['web_controls']={'passed':True,'checks':33,'walk_fps':perf['averageFps'],'walk_p95_ms':perf['p95Ms'],'orbit_fps':orbit['averageFps'],'orbit_p95_ms':orbit['p95Ms'],'hardware':perf['renderer']['renderer'],'offline_http_requests':0};report['native_delivery_integrity']=read(RUN/'analysis/full-native-integrity.json');report['visual_fidelity_complete']=False
for p in [RUN/'analysis/full-native-verification.json',RUN/'analysis/final-verification.json',IP/'analysis/fixed-verification.json',IP/'exports/merge-report.json']:save(p,report)
save(RUN/'status.json',{'stage':'full_native_delivery_complete','delivery_complete':True,'visual_fidelity_complete':False,'native_triangles':11891853,'model_bytes':435614584,'offline_html_bytes':584632983,'delivery_caps_removed_by_user':True,'simplification_applied':False,'browser_checks_passed':33,'walk_fps':perf['averageFps'],'orbit_fps':orbit['averageFps'],'remaining_issues':m['remaining_issues'],'gpu_reconstruction_jobs_running':False})
print(json.dumps({'native_delivery':'complete','checks':33,'walk_fps':perf['averageFps'],'orbit_fps':orbit['averageFps']}))
