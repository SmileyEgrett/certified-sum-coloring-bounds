"""Solver-free graph-to-bound composition using retained exact primitives."""
import gzip,itertools
from pathlib import Path
from core import graph,load,readj,writej,get,sha,require

def seed_data(m,pi,S,packs,path):
    p,top,removed,res,q,t=m.packing_data(pi,S,packs);w=m.parse_old_dual(path,res)
    require(len(w)==425,'seed needs exactly425 sorted rows');mn=min(sum(w[v] for v in C) for C in q)
    require(mn>=10**12,'seed violates a quad');total=sum(w.values());bound=total//10**12;cap=100 if pi in (2,4) else 101
    require(bound<=cap+1,'seed outside bounded tree contract')
    return {'weights':w,'sha256':sha(path),'total':total,'bound':bound,'slack':total%10**12,'residual':res,'quads':q,'triples':t,'top':top,'packing':p,'minimum_column':mn}

def verify250(records,out):
    m=load('checkers/dsjc250/verify.py');g=m.parse_graph(graph('dsjc250'));S,adj=m.enumerate_stable(g);require([250]+[len(S[s]) for s in range(2,7)]==[250,3228,2869,205,3,0],'250 census')
    packs=m.enumerate_top_packings(S[5]);profiles=m.enumerate_profiles(250,5,max(packs),8276);layered=[];residual=[];trees=[];invalid={}
    for sid in sorted(records):
        try:
            if sid.startswith('dsjc250.dual.'):
                name=sid.split('.')[-1];p=get(records,sid,'certificate')
                if name.startswith('ge4'):layered.append(m.verify_layered_rational(p,g,S,name))
                else:
                    idx={'h5_1_forbid_x1':(0,),'h5_1_x3_slack':(2,),'h5_2_forbid_x1_x3':(0,2)}[name]
                    residual.append(m.verify_residual_rational(p,g,S,name,[S[5][i] for i in idx]))
            elif sid.startswith('dsjc250.tree.'):trees.append(m.verify_lpbb(get(records,sid,'proof'),S,250,sid.split('.')[-1],maximum_proof_bytes=0))
        except (ValueError,KeyError,TypeError,AssertionError) as e:invalid[sid]=str(e)
    coverage=m.logical_chain(profiles,packs,layered,residual,trees);coverage['invalid_available_certificates']=invalid;writej(out/'coverage.json',coverage)
    return {'status':'verified','lower_bound':8277,'invalid_available_certificates':invalid,'unused_conclusions':coverage['unused_conclusions']}

def verify500(records,out):
    m=load('checkers/dsjc500/baseline_verify.py');g=m.parse_graph(graph('dsjc500'));S=m.enumerate_stable(g,6);best,packs=m.enumerate_packings(S[5]);require(best==15 and len(packs)==8 and [len(S[s]) for s in range(2,7)]==[12313,19901,2428,23,0],'500 census')
    old={};bounds={};invalid={};farkas={};profile={};weighted=[];direct=[]
    # Farkas premises need graph-derived packing data, even when an unrelated seed failed.
    for pi in range(1,9):
        p,top,removed,res,q,t=m.packing_data(pi,S,packs);old[pi]={'packing':p,'top':top,'residual':res,'quads':q,'triples':t}
        sid=f'dsjc500.seed.P{pi}';tree=f'dsjc500.residual.P{pi}';cap=100 if pi in (2,4) else 101
        if sid not in records:continue
        failed_id=sid
        try:
            old[pi]=seed_data(m,pi,S,packs,get(records,sid,'dual'));b=old[pi]['bound'];bounds[pi]=b
            failed_id=tree # Subsequent diagnostics refer to the tree, not the successful seed.
            if b<=cap:direct.append({'packing':pi,'bound':b,'reason':'exact fresh seed floor already discharges required cap'});continue
            if tree not in records or 'proof' not in records[tree]['artifacts']:continue
            if pi in (2,4):
                with gzip.open(get(records,tree,'proof'),'rt') as f:header=__import__('json').load(f)
                require(header['top_set_size']==5 and header['residual_set_size']==4 and header['old_dual_denominator']==10**12,'generic tree cap scope')
                r=load('existing/dsjc500/delta/verify_residual_kset_lpbb.py').verify(graph('dsjc500'),get(records,sid,'dual'),get(records,tree,'proof'))
                require(r['packing']==pi and r['bound']==100,'generic tree conclusion scope');bounds[pi]=100
            else:bounds[pi]=m.verify_lpbb(get(records,tree,'proof'),pi,g,S,packs,old)['bound']
        except (ValueError,KeyError,TypeError,AssertionError) as e:invalid[failed_id]=str(e)
    for sid in sorted(records):
        try:
            if sid.startswith('dsjc500.farkas.'):
                pi=int(sid.rsplit('P',1)[1]);farkas[pi]=m.verify_farkas(get(records,sid,'certificate'),pi,g,S,packs,old)
            elif sid.startswith('dsjc500.profile_farkas.'):
                pi=int(sid.rsplit('P',1)[1].split('_')[0]);v=m.verify_profile_farkas(get(records,sid,'certificate'),pi,g,S,packs,old);profile[pi,v['quota']]=v
        except (ValueError,KeyError,TypeError,AssertionError) as e:invalid[sid]=str(e)
    checked=load('existing/dsjc500/delta/exact_mscp_conditional_verify.py');gg=checked.parse_graph(graph('dsjc500'))
    for sid in sorted(records):
        if not sid.startswith('dsjc500.weighted.'):continue
        try:
            model=get(records,sid.replace('.weighted.','.model.'),'model');d=readj(model)
            weighted.append(checked.verify_tree_proof(get(records,sid,'proof'),model,d['model_id'],gg,S,5,0,0,0))
        except (ValueError,KeyError,TypeError,AssertionError,checked.VerificationError) as e:invalid[sid]=str(e)
    rows,qmin,qmax=m.enumerate_threshold_profiles(29790,best);unresolved=[];cells=[]
    # Prove the threshold domain has only maximum packings before consuming the 8-packing domain.
    require(all(r[6]==best for r in rows),'threshold includes nonmaximum packing cardinality; cannot omit its domain')
    for r in rows:
        val,q,h1,h2,h3,h4,h5=r;prof=checked.profile_from_h((0,h1,h2,h3,h4,h5))
        for pi,p in enumerate(packs,1):
            top=tuple(S[5][i] for i in p);reasons=[]
            if pi in bounds and h4>bounds[pi]:reasons.append('fresh_residual_cap')
            if pi in farkas and (h1,h2,h3,h4)==(0,0,7,101):reasons.append('exact_cover_farkas')
            if (pi,(h1,h2,h3,h4)) in profile:reasons.append('profile_farkas')
            reasons += [c.certificate_id for c in weighted if c.rejects(prof,top)]
            cell={'packing':pi,'h':[h1,h2,h3,h4,h5],'objective':val,'reasons':reasons};cells.append(cell)
            if not reasons:unresolved.append(cell)
    writej(out/'coverage.json',{'profiles':rows,'graph_free_q_range':[qmin,qmax],'cells':cells,'unresolved':unresolved,'direct_seed_caps':direct,'invalid_available_certificates':invalid})
    require(not unresolved,'unresolved500 packing/profile cells: '+str(len(unresolved)))
    return {'status':'verified','lower_bound':29791,'profiles':len(rows),'cells':len(cells),'direct_seed_caps':direct,'invalid_available_certificates':invalid}

def verify1000(records,out,cap_only=False):
    m=load('checkers/dsjc1000/verify_release.py');n,edges,adj,comp,raw,canon=m.parse_graph(graph('dsjc1000'));fam=m.enumerate_stable(n,comp,7);counts=[len(fam[s]) for s in range(1,7)]
    require(n==1000 and len(edges)==449449 and counts==[1000,50051,167104,41659,869,3] and not fam[7],'1000 census');tops=tuple(fam[6]);require(len(set(itertools.chain.from_iterable(tops)))==18,'1000 top disjointness')
    cap_path=get(records,'dsjc1000.cap_exact','certificate');cap=m.verify_packing(m.loadj(cap_path),fam,tops,raw,canon,counts);require(cap.integer_cap==134,'fresh cap must be134')
    if cap_only:return {'status':'verified','integer_cap':cap.integer_cap,'scenario':cap.scenario,'certificate_sha256':sha(cap_path)}
    scenario_bounds={}
    for i in range(8):
        s=f'{i:03b}';p=get(records,'dsjc1000.exact.'+s,'certificate');ss,lb,D=m.verify_cond(m.loadj(p),fam,tops,raw,canon,counts,cap)
        require(ss==s and lb>102343*D,'1000 missing/insufficient scenario');scenario_bounds[s]={'numerator':lb,'denominator':D,'integer':m.ceildiv(lb,D)}
    derived=min(x['integer'] for x in scenario_bounds.values());writej(out/'coverage.json',{'scenarios':scenario_bounds,'derived_lower_bound':derived})
    return {'status':'verified','lower_bound':102344,'derived_lower_bound':derived,'scenarios':scenario_bounds}

def verify_census2000(records):
    a=get(records,'c2000.census','six_sets');b=get(records,'c2000.independent_census','six_sets')
    with gzip.open(a,'rb') as f:require(f.read()==b.read_bytes(),'independent census list mismatch')
    text=get(records,'c2000.independent_census','census_stdout').read_text();rows={}
    for line in text.splitlines():
        k,sep,v=line.partition('=')
        if sep and (k.startswith('stable_sets_size_') or k in ('vertices','edges')):
            require(k not in rows,'duplicate independent census count');rows[k]=int(v)
    require(rows.get('vertices')==2000 and rows.get('edges')==1799532 and rows.get('stable_sets_size_6')==90 and rows.get('stable_sets_size_7')==0,'independent complete census contract')
    return {'status':'verified','counts':rows,'six_sets_sha256':sha(a),'independent_six_sets_sha256':sha(b)}

def verify2000(records,out):
    receipt=readj(get(records,'c2000.bind_census','receipt'));require(receipt['status']=='verified' and receipt['six_sets_sha256']==sha(get(records,'c2000.census','six_sets')),'census receipt scope')
    load('checkers/c2000/verify_c2000_9_top_envelope.py').verify(get(records,'c2000.census','six_sets'),get(records,'c2000.assemble','certificate'))
    return {'status':'verified','lower_bound':381823}
