"""Small shared I/O and sealed provenance boundary; no numerical imports."""
from pathlib import Path
import hashlib, importlib.util, json, os, re, sys
SNAP = Path(__file__).resolve().parents[1]
def require(ok, message):
    if not ok: raise ValueError(message)
def no_duplicates(pairs):
    d={}
    for k,v in pairs:
        require(k not in d, 'duplicate JSON key '+k);d[k]=v
    return d
def readj(p):
    return json.loads(Path(p).read_text(),object_pairs_hook=no_duplicates,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
def canonical(obj): return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def digest(b): return hashlib.sha256(b).hexdigest()
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def writej(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.new')
    with tmp.open('xb') as f:f.write(canonical(obj));f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def beneath(root,p):
    root=Path(root).resolve();p=Path(p)
    require(p.is_absolute(),'absolute evidence path required')
    q=p.resolve(strict=True);require(q.is_relative_to(root),'path outside evidence root')
    # Symlink aliases obscure selection identity even when they point inside.
    require(p==q,'symlink or noncanonical path');return q
def tree_hashes(root):
    root=Path(root);out={}
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(),'symlink in frozen tree')
        if p.is_file():out[str(p.relative_to(root))]=sha(p)
    return out
def artifact_digest(p):
    p=Path(p)
    return digest(canonical(tree_hashes(p))) if p.is_dir() else sha(p)
def guard_snapshot():
    m=readj(SNAP.parent/'manifest.json')
    require(tree_hashes(SNAP)==m['files'],'source/input/config snapshot drift')
    require(digest(canonical(m['files']))==m['snapshot_id'],'snapshot identity mismatch')
    return m

def admission():
    require(sys.flags.optimize==0,'Python optimization disables retained proof assertions')
    require('PYTHONOPTIMIZE' not in os.environ,'PYTHONOPTIMIZE forbidden')

def load(rel,name=None):
    p=(SNAP/rel).resolve();require(p.is_relative_to(SNAP),'live source import forbidden')
    name=name or 'frozen_'+digest(str(p).encode())[:12]
    # Legacy local imports resolve only in the copied sibling directory.
    sys.path.insert(0,str(p.parent))
    if (p.parent/'common.py').exists():
        cp=p.parent/'common.py';spec=importlib.util.spec_from_file_location('common',cp);mod=importlib.util.module_from_spec(spec);sys.modules['common']=mod;spec.loader.exec_module(mod)
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    sys.path.pop(0);return m

def config():return readj(SNAP/'config/STAGES.json')
def graph(case):
    g=config()['graphs'][case];p=SNAP/g['run_input'];require(sha(p)==g['sha256'],'graph authentication failed');return p

def validate_record(run,record_path,snapshot_id,config_hash,_stack=(),_selection=None):
    p=beneath(Path(run)/'jobs',Path(record_path));require(str(p) not in _stack,'cyclic producer chain');_stack=(*_stack,str(p));r=readj(p)
    if _selection is None:_selection={}
    identity=(r['attempt'],sha(p));require(r['stage'] not in _selection or _selection[r['stage']]==identity,'conflicting transitive producer attempts');_selection[r['stage']]=identity
    require(p.parent.name==r['attempt'] and p.parent.parent.name==r['stage'],'producer identity/path mismatch')
    require(r['snapshot_id']==snapshot_id and r['config_hash']==config_hash,'producer snapshot/config mismatch')
    require(r['status']=='success','producer not successful')
    ip=beneath(Path(run)/'jobs',p.parent/'inputs.json');require(sha(ip)==r['inputs_sha256'],'producer inputs drift')
    expected=digest(canonical([snapshot_id,config_hash,r['stage'],r['attempt'],r['inputs_sha256']]))
    require(r['job_id']==expected,'job identity mismatch')
    z=readj(ip);require(z['schema']=='sealed_inputs_v2' and z['consumer']==r['stage'] and z['snapshot_id']==snapshot_id and z['config_hash']==config_hash,'producer sealed-input identity mismatch')
    seen=set()
    for ref in z['producers']:
        require(ref['stage'] not in seen,'duplicate transitive producer');seen.add(ref['stage'])
        rp=beneath(Path(run)/'jobs',Path(ref['record']));require(sha(rp)==ref['record_sha256'],'transitive producer record drift')
        ancestor=validate_record(run,rp,snapshot_id,config_hash,_stack,_selection)
        require(ancestor['stage']==ref['stage'] and ancestor['attempt']==ref['attempt'],'transitive producer identity mismatch')
    for key,a in r['artifacts'].items():
        q=beneath(p.parent,Path(a['path']));require(artifact_digest(q)==a['sha256'],'artifact drift '+key)
    return r

def sealed_inputs(run,path,stage):
    manifest=guard_snapshot();ch=sha(SNAP/'config/STAGES.json')
    p=beneath(Path(run)/'jobs',Path(path));z=readj(p)
    require(z['schema']=='sealed_inputs_v2' and z['consumer']==stage,'consumer identity mismatch')
    require(z['snapshot_id']==manifest['snapshot_id'] and z['config_hash']==ch,'consumer snapshot/config mismatch')
    require(p.parent.parent.name==stage,'consumer path mismatch')
    result={};seen=set();selection={}
    for ref in z['producers']:
        require(ref['stage'] not in seen,'duplicate producer selection');seen.add(ref['stage'])
        rp=beneath(Path(run)/'jobs',Path(ref['record']));require(sha(rp)==ref['record_sha256'],'producer record drift')
        r=validate_record(run,rp,manifest['snapshot_id'],ch,_selection=selection)
        require(r['stage']==ref['stage'] and r['attempt']==ref['attempt'],'producer selection mismatch');result[r['stage']]=r
    return z,result

def get(records,stage,key):return Path(records[stage]['artifacts'][key]['path'])
def expand(s,run,out,records,inputs):
    def ref(m):return str(get(records,m[1],m[2]))
    s=re.sub(r'\$\{artifact:([^:}]+):([^}]+)\}',ref,s)
    for k,v in {'PYTHON':sys.executable,'SNAPSHOT':SNAP,'RUN_ROOT':run,'OUT':out,'INPUTS':inputs,'STDOUT':Path(out).parent/'stdout.log'}.items():s=s.replace('${'+k+'}',str(v))
    # Every retained graph command reads the authenticated frozen snapshot graph.
    require('${' not in s,'unresolved command template '+s);return s
