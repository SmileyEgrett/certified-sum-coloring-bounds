"""One sealed, timed stage; all CLI paths are explicit and within this run."""
import argparse,os,runpy,sys,traceback,math,json
from pathlib import Path
from core import *
from exactmath import direct_seed_action

def run_retained(argv):
    if argv[0]==sys.executable:
        script=Path(argv[1]);require(script.resolve().is_relative_to(SNAP),'retained source outside snapshot')
        sys.path.insert(0,str(script.parent));sys.argv=argv[1:]
        if (script.parent/'common.py').exists():load(str((script.parent/'common.py').relative_to(SNAP)),'common')
        try:runpy.run_path(str(script),run_name='__main__')
        except SystemExit as e:
            require(e.code in (None,0),'retained generator exit '+str(e.code))
        finally:sys.path.pop(0)
    else:
        import subprocess
        subprocess.run(argv,check=True)

def main():
    admission();a=argparse.ArgumentParser();a.add_argument('--run',type=Path,required=True);a.add_argument('--stage',required=True);a.add_argument('--inputs',type=Path,required=True);a.add_argument('--out',type=Path,required=True);args=a.parse_args()
    cfg=config();stage=next(s for s in cfg['stages'] if s['id']==args.stage);sealed,records=sealed_inputs(args.run,args.inputs,args.stage)
    require(set(records)<=set(stage['depends_on']),'undeclared producer dependency')
    if not stage.get('terminal_dependencies'):require(set(records)==set(stage['depends_on']),'missing producer dependency')
    out=beneath(args.run/'jobs',args.out);require(out.parent==args.inputs.parent,'output/consumer mismatch');sid=args.stage
    if stage['case']!='common':graph(stage['case'])
    if sid.startswith('dsjc250.tree.'):os.environ['DSJC2509_GRAPH']=str(graph('dsjc250'))
    if sid=='dsjc1000.lp.111':
        v=readj(get(records,'dsjc1000.cap_verify','receipt'));p=get(records,'dsjc1000.cap_exact','certificate')
        require(v['status']=='verified' and v['integer_cap']==134 and v['scenario']=='111' and v['certificate_sha256']==sha(p),'capped LP needs a fresh verified matching cap134')
    if sid.startswith('dsjc500.residual.'):
        from verify_lower import seed_data
        pi=int(sid.rsplit('P',1)[1]);m=load('checkers/dsjc500/baseline_verify.py');g=m.parse_graph(graph('dsjc500'));S=m.enumerate_stable(g,6);best,packs=m.enumerate_packings(S[5]);o=seed_data(m,pi,S,packs,get(records,f'dsjc500.seed.P{pi}','dual'));cap=100 if pi in (2,4) else 101
        if direct_seed_action(o['bound'],cap)=='direct_seed':
            writej(out/'decision.json',{'action':'direct_seed','bound':o['bound'],'required_cap':cap,'reason':'exact fresh seed floor already discharges cap'});return
        require(o['bound']==cap+1,'tree requires exactly one remaining unit')
    if 'retained_argv' in stage:
        argv=[expand(x,args.run,out,records,args.inputs) for x in stage['retained_argv']]
        print(json.dumps({'retained_argv':argv}),flush=True)
        run_retained(argv)
        if sid.startswith('dsjc500.farkas.'):
            from construct import normalize_farkas
            raw=Path(expand(stage['outputs']['raw'],args.run,out,records,args.inputs));normalize_farkas(int(sid.rsplit('P',1)[1]),raw,records,out)
        if sid.startswith('dsjc500.residual.'):writej(out/'decision.json',{'action':'tree','required_cap':cap})
    elif sid.endswith('.reconstruct'):
        from construct import reconstruct
        reconstruct(stage['case'],out)
    elif sid.startswith('dsjc250.dual.'):
        from construct import dual250
        dual250(sid.split('.')[-1],records,out)
    elif sid.startswith('dsjc500.seed.'):
        from construct import seed500
        seed500(int(sid.rsplit('P',1)[1]),records,out)
    elif sid=='dsjc1000.cap_exact' or sid.startswith('dsjc1000.exact.'):
        from construct import exact1000
        exact1000('111' if sid.endswith('cap_exact') else sid.split('.')[-1],records,out,packing=sid.endswith('cap_exact'))
    elif sid.startswith('c2000.') and sid.split('.')[-1] in ('packing','cliques','cover','assemble'):
        from construct import top2000
        top2000(sid.split('.')[-1],records,out)
    else:
        import verify_lower as v
        if sid=='dsjc250.verify':receipt=v.verify250(records,out)
        elif sid=='dsjc500.verify':receipt=v.verify500(records,out)
        elif sid=='dsjc1000.cap_verify':receipt=v.verify1000(records,out,True)
        elif sid=='dsjc1000.verify':receipt=v.verify1000(records,out)
        elif sid=='c2000.bind_census':receipt=v.verify_census2000(records)
        elif sid=='c2000.verify':receipt=v.verify2000(records,out)
        else:raise ValueError('unimplemented stage '+sid)
        receipt.update(schema='lower_only_receipt_v2',stage=sid,inputs_sha256=sha(args.inputs),snapshot_id=sealed['snapshot_id'],config_hash=sealed['config_hash'],unavailable_stages=sealed['unavailable'])
        writej(out/'verification.json',receipt)
    # This is only producer completion, never proof authority. Runner validates declared outputs.
if __name__=='__main__':main()
