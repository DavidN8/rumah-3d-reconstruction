"""Local QA only: add unlit glTF material tags; retain every binary chunk byte."""
from pathlib import Path
import hashlib,json,struct

here=Path(__file__).parent
source=Path(r'C:\Users\bombe\OneDrive\Documents\ChatGPT\Ruang Kamare\roomscan-reconstruction\data\20261031_OSMO360\lite-v1\exports\osmo-lite-source.glb')
output=here/'diagnostics/qa-source-v1-unlit.glb'
if output.exists():raise FileExistsError(output)
raw=source.read_bytes();source_sha=hashlib.sha256(raw).hexdigest()
magic,version,total=struct.unpack_from('<III',raw,0)
assert magic==0x46546c67 and version==2 and total==len(raw)
n,kind=struct.unpack_from('<II',raw,12);assert kind==0x4e4f534a
old_json=json.loads(raw[20:20+n]);g=json.loads(raw[20:20+n])
extensions=g.setdefault('extensionsUsed',[])
if 'KHR_materials_unlit' not in extensions:extensions.append('KHR_materials_unlit')
for material in g['materials']:material.setdefault('extensions',{})['KHR_materials_unlit']={}
modified=json.dumps(g,separators=(',',':')).encode('utf-8')
modified+=b' '*((-len(modified))%4)
binary_tail=raw[20+n:]
new=struct.pack('<III',magic,version,20+len(modified)+len(binary_tail))+struct.pack('<II',len(modified),kind)+modified+binary_tail
assert new[20+len(modified):]==binary_tail
check=json.loads(modified)
for material in check['materials']:
    del material['extensions']['KHR_materials_unlit']
    if not material['extensions']:del material['extensions']
check['extensionsUsed'].remove('KHR_materials_unlit')
if not check['extensionsUsed']:del check['extensionsUsed']
assert check==old_json
output.write_bytes(new)
assert hashlib.sha256(source.read_bytes()).hexdigest()==source_sha
report={'purpose':'Local-only unlit versus PBR QA; no production deployment',
        'source':str(source),'source_sha256':source_sha,'output':str(output),
        'output_sha256':hashlib.sha256(new).hexdigest(),
        'binary_tail_sha256':hashlib.sha256(binary_tail).hexdigest(),
        'binary_chunks_identical':True,'only_json_material_extension_changed':True,
        'materials_changed':len(g['materials']),'bytes':len(new)}
(here/'unlit-v1-edit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
