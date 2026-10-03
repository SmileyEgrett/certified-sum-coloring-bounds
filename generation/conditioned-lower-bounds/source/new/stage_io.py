"""Stage artifacts and sealed producer selection."""
import glob, os
from pathlib import Path
from core import *

def outputs(stage,run,out,records,inputs):
    result={}
    for key,spec in (stage['outputs']|stage.get('optional_outputs',{})).items():
        if isinstance(spec,dict):
            paths=list(map(Path,glob.glob(expand(spec['glob'],run,out,records,inputs))))
            require(len(paths)==spec['required_count']==1,'output multiplicity '+key);p=paths[0]
        else:p=Path(expand(spec,run,out,records,inputs))
        if key in stage.get('optional_outputs',{}) and not p.exists():continue
        p=beneath(out.parent,p);require(p.is_dir() or p.stat().st_size>0,'empty output '+key)
        result[key]={'path':str(p),'sha256':artifact_digest(p)}
    sid=stage['id']
    # Check actual content and schemas before declaring constructor completion.
    if 'receipt' in result:
        v=readj(result['receipt']['path']);require(v['status']=='verified' and v['stage']==sid and v['inputs_sha256']==sha(inputs),'unbound verification receipt')
    if 'proof' in result:
        import gzip
        with gzip.open(result['proof']['path'],'rt') as f:d=__import__('json').load(f,object_pairs_hook=no_duplicates)
        if 'status' in d:require(d['status']=='PROVED','incomplete tree')
        require(type(d['root']) is int and isinstance(d.get('records',d.get('proof')),list),'malformed proof root/records')
    if sid.startswith('dsjc500.residual.'):
        d=readj(result['decision']['path']);require(d['action'] in ('direct_seed','tree'),'bad residual decision')
        require(d['required_cap']==(100 if sid.endswith(('P2','P4')) else 101),'residual decision scope')
        if d['action']=='tree':require('proof' in result,'tree decision missing exact proof')
        else:require(type(d['bound']) is int and d['bound']<=d['required_cap'],'invalid direct-seed decision')
    if '.farkas.' in sid or '.profile_farkas.' in sid:
        c=readj(result['certificate']['path']);require(c['schema'] in ('dsjc5009_exact_cover_farkas_v1','dsjc5009_profile_farkas_v1') and type(c['rhs']) is int and c['rhs']<0,'missing exact Farkas content')
    if '.lp.' in sid or sid=='dsjc1000.cap_lp':
        summary=readj(result['summary']['path']);require(summary['success'] is True,'numerical solve incomplete')
    for a in result.values():
        p=Path(a['path'])
        for f in (p.rglob('*') if p.is_dir() else (p,)):
            if f.is_file():
                with f.open('rb') as h:os.fsync(h.fileno())
    return result

def sealed(stage,selected,terminal,snapshot_id,config_hash):
    producers=[];missing={}
    for dep in stage['depends_on']:
        if dep in selected:
            p,r=selected[dep];producers.append({'stage':dep,'attempt':r['attempt'],'record':str(p),'record_sha256':sha(p)})
        else:missing[dep]=terminal.get(dep,'not_attempted')
    return {'schema':'sealed_inputs_v2','consumer':stage['id'],'snapshot_id':snapshot_id,'config_hash':config_hash,'producers':producers,'unavailable':missing}

