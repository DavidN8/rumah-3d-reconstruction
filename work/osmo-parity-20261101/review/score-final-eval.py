"""Reuse the independently matched, valid-pixel evaluation on the new full run."""
from pathlib import Path
W=Path(__file__).resolve().parent;original=W.parent.parent/'osmo-clean-20261031/review/score-native-eval.py'
source=original.read_text().replace('20261031_OSMO360/clean-v3/explicit-full-v1','20261031_OSMO360/parity-20261101/explicit-1600').replace("TRAIN=ROOT/'training/osmo-explicit-depth-v1'","TRAIN=ROOT/'training/osmo-sharp-1600-full'").replace('(1200,1200,3)','(1600,1600,3)').replace('1200x1200','1600x1600')
(W/'renders').mkdir(exist_ok=True);Path('C:/Users/bombe/OneDrive/Documents/ChatGPT/Ruang Kamare/roomscan-reconstruction/data/20261031_OSMO360/parity-20261101/explicit-1600/analysis').mkdir(exist_ok=True)
exec(compile(source,str(__file__),'exec'))
