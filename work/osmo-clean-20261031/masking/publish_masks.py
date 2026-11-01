"""Release reviewed candidate masks with binary, roster and SHA256 verification.
A readiness marker is written only after all452 dataset masks and the audit exist.
"""
from pathlib import Path
import json,hashlib,shutil,cv2,numpy as np
from build_masks import HERE,DEFAULT_DATASET,write_json

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 manifest=json.loads((HERE.parent/'frame-selection.json').read_text());audit=json.loads((HERE/'candidate-audit.json').read_text());annpath=HERE/'review-annotations.json';annotations=json.loads(annpath.read_text())
 expected={(c,r['filename']):r for c in ['cam0','cam1'] for r in manifest['selected']};actual={(r['camera'],r['filename']):r for r in audit['frames']}
 assert len(expected)==452 and len(actual)==452 and set(expected)==set(actual)
 assert audit['review_annotations_sha256']==sha(annpath),'Candidate annotation mismatch; re-finalize before release'
 approved=json.loads((HERE/'pinhole-repairs/approved-audit.json').read_text())
 accepted=[r for r in approved['frames'] if r['approved']]
 assert len(accepted)==44
 validated=[]
 for (cam,filename),record in actual.items():
  p=HERE/'candidate-final'/cam/Path(filename).with_suffix('.png');m=cv2.imread(str(p),cv2.IMREAD_UNCHANGED)
  assert m is not None and m.shape==(3840,3840) and m.dtype==np.uint8,(p,'shape/type')
  assert not np.any((m!=0)&(m!=255)),(p,'nonbinary')
  assert np.any(m==255) and np.any(m==0),(p,'degenerate mask')
  assert sha(p)==record['sha256'],(p,'fingerprint mismatch')
  validated.append((p,DEFAULT_DATASET/'masks'/cam/p.name,record))
 print('Validated452 complete native binary masks and all candidate hashes',flush=True)
 review={
  'status':'all selected frames visually reviewed; known major operator gaps corrected',
  'coverage':{'cam0':'Masking agent reviewed all226 corrected operator images; root independently reviewed final tail; masking agent reviewed all48 last changed candidates.',
              'cam1':'Root reviewed first120 corrected operator images; calibration agent reviewed remaining106; masking agent reviewed9 last changed candidates.'},
  'mirror_review':'63 explicit full-glass polygons; first and second bathroom visits checked against source photos, including root approach traces and calibration exit traces.',
  'targeted_pinhole_repairs_accepted':44,
  'targeted_pinhole_candidates_rejected':13,
  'limits':['Visual review is not pixel-level ground truth. Minor hair/boundary residuals can remain.',
            'Conservative small static-clothing exclusions remain in some frames; masks do not create observations behind the operator.',
            'Moving cast shadows were excluded only in reviewed spatial/time regions. No inpainting or source image changes.'],
  'masking_models':'SAM2.1 small plus GroundingDINO tiny; existing local weights. Both Apache2.0; SAM3 license is not used.',
  'pinhole_policy':'Calibrated virtual views for segmentation only; accepted native additions are WHITE=exclude and zero outside covered rays. Final masks are opposite polarity (255=keep,0=exclude).',
  'training_requirement':'apply_loss_for_mask=false: excluded rays carry no photometric loss; do not treat operator masks as empty observed space.'
 }
 for key in annotations['frames']:
  assert tuple(key.split('/',1)) in expected
  annotations['frames'][key]['reviewed']=True
 annotations['release_review']=review
 write_json(annpath,annotations)
 for p,dest,record in validated:
  dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert sha(dest)==record['sha256'],f'Conflicting existing final mask: {dest}'
  else:
   tmp=dest.with_suffix('.png.partial');shutil.copy2(p,tmp);assert sha(tmp)==record['sha256'];tmp.replace(dest)
  assert sha(dest)==record['sha256']
 audit.update(review_annotations_sha256=sha(annpath),release_review=review,dataset=str(DEFAULT_DATASET),count=452)
 audit['candidate_audit_sha256']=sha(HERE/'candidate-audit.json')
 audit['pinhole_approved_audit_sha256']=sha(HERE/'pinhole-repairs/approved-audit.json')
 audit['composition_audit_sha256']=sha(HERE/'composition-audit.json')
 write_json(HERE/'mask-audit.json',audit)
 marker={'status':'ready','count':452,'mask_audit_sha256':sha(HERE/'mask-audit.json')}
 write_json(HERE/'masks-ready.json',marker)
 fractions=np.array([r['keep_fraction'] for r in audit['frames']])
 print(json.dumps({'ready':marker,'keep_fraction_min_mean_max':[float(fractions.min()),float(fractions.mean()),float(fractions.max())],'mirror_polygons':sum(len(e.get('mirror_polygons',[])) for e in annotations['frames'].values())},indent=2),flush=True)
if __name__=='__main__':main()
