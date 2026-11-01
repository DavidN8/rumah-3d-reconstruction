from pathlib import Path
import json

WORK=Path(__file__).resolve().parent
RUN=Path(r'C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/clean-v3')
p=WORK/'frame-selection.json';m=json.loads(p.read_text())
assert m['native_decode_complete']
assert not m.get('chronological_names'), 'Already assigned; do not repeat'
for i,r in enumerate(m['selected']):
    split='eval' if i%12==6 else 'train'
    old=r['filename'];new=f'frame_{r["source_frame"]:06d}_{split}.jpg'
    for lens in range(2):
        parent=RUN/f'dataset/images/cam{lens}'
        src=parent/old;dst=parent/new
        if not src.is_file() or dst.exists():raise RuntimeError(f'Rename guard failed {src}')
        src.rename(dst)
    r.update(filename=new,split=split)
m['split_assigned']=True
m['chronological_names']=True
m['split_note']='Every twelfth selected timestamp offset six held out; both lenses share split before SfM/warping. Camera poses estimated by SfM with all images; training seed will use only train observations/colors. Validation is novel-timestamp rendering within the same video, not independent capture ground truth.'
m['train_pairs']=sum(r['split']=='train' for r in m['selected']);m['eval_pairs']=sum(r['split']=='eval' for r in m['selected'])
for dst in [p,RUN/'analysis/frame-selection.json']:dst.write_text(json.dumps(m,indent=2))
print(json.dumps({k:m[k] for k in ['selected_pair_count','train_pairs','eval_pairs','split_assigned']}))
