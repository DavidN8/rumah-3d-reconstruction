from pathlib import Path
import json
W=Path(__file__).resolve().parent
a=json.loads((W/'geometry/fresh-sfm-preparation-audit.json').read_text())
def compact(v):
    if isinstance(v,dict):return {k:compact(x) for k,x in v.items() if k not in ['per_image','pairs','per_camera_angle_bin','written_files_sha256']}
    if isinstance(v,list):
        if len(v)>5:return {'count':len(v),'first':compact(v[0]),'last':compact(v[-1])}
        return [compact(x) for x in v]
    return v
keys=['components','reprojection','rig_pair_audit','repeat_visit_audit','trajectory_continuity','transform','seed_filter','projection_ray_identity_max_error']
print(json.dumps(compact({k:a[k] for k in keys}),indent=2))
