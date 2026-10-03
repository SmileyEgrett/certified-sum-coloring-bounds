"""Fresh graph-derived constructors; exact proof authority remains in verify_lower."""
import gzip,itertools,math,time
from pathlib import Path
from core import SNAP,config,graph,load,readj,writej,get,sha,require
from exactmath import cover_round,free_lower,free_upper,cap_multiplier,repair_upper

def write_sets(root,fam):
    root.mkdir()
    for s,sets in sorted(fam.items()):
        with gzip.open(root/f'stable_sets_size_{s}.tsv.gz','wt',encoding='ascii') as f:
            f.write('id\tsize\tvertices\n')
            for i,C in enumerate(sets,1):f.write(f'{i}\t{s}\t'+ ' '.join(map(str,C))+'\n')
def read_sets(root,s):
    p=Path(root)/f'stable_sets_size_{s}.tsv.gz';result=[]
    with gzip.open(p,'rt',encoding='ascii') as f:
        require(next(f)=='id\tsize\tvertices\n','bad set header')
        for i,line in enumerate(f,1):
            a,b,c=line.rstrip('\n').split('\t');C=tuple(map(int,c.split()))
            require(int(a)==i and int(b)==s and len(C)==s and tuple(sorted(set(C)))==C,'bad set row');result.append(C)
    require(result==sorted(set(result)),'set ordering/uniqueness');return result

def reconstruct(case,out):
    if case=='dsjc500':
        m=load('existing/dsjc500/baseline/common.py');g=m.parse_dimacs(graph(case));fam=m.enumerate_stable_sets(g,6);fam[1]=[(v,) for v in range(1,501)]
        best,packs=m.enumerate_packings(fam[5]);require(best==15 and len(packs)==8,'500 packing domain changed')
        scenarios={'maximum':best,'packings':[[list(fam[5][i]) for i in p] for p in packs]}
        info={'raw_sha256':g['raw_sha256'],'canonical_sha256':g['canonical_sha256'],'vertices':500,'unique_edges':len(g['edges'])}
    else:
        m=load('existing/dsjc1000/reconstruct_instance.py');g=m.parse_graph(graph(case));a,nodes,alpha=m.enumerate_stable(g,7 if case=='dsjc1000' else 6)
        fam={s:a[s] for s in range(1,len(a))};fam[alpha+1]=[]
        info={'raw_sha256':g['raw_sha256'],'canonical_sha256':g['canonical_sha256'],'vertices':g['n'],'unique_edges':g['m']}
        if case=='dsjc1000':
            cc=load('existing/dsjc1000/cert_common.py');require(tuple(fam[6])==cc.TOPS,'fresh top family differs from declarative scenarios')
            require(len(set(itertools.chain.from_iterable(fam[6])))==18,'overlapping six-sets')
            scenarios={'tops':fam[6],'scenarios':{f'{i:03b}':[C for j,C in enumerate(fam[6]) if f'{i:03b}'[j]=='1'] for i in range(8)}}
        else:scenarios={'tops':fam[5]}
    if case=='dsjc250':
        check=load('checkers/dsjc250/verify.py');packings=check.enumerate_top_packings(fam[5]);profiles=check.enumerate_profiles(250,5,max(packings),8276);writej(out/'profiles.json',profiles)
    elif case=='dsjc500':
        check=load('checkers/dsjc500/baseline_verify.py');profiles,qmin,qmax=check.enumerate_threshold_profiles(29790,best);writej(out/'profiles.json',{'rows':profiles,'q_range':[qmin,qmax]})
    expected=config()['graphs'][case]['counts_by_size_including_empty_next']
    require([len(fam[s]) for s in range(1,len(expected)+1)]==expected,'fresh census mismatch')
    info['stable_counts']=expected[:-1]
    write_sets(out/'sets',fam);writej(out/'reconstruction.json',{'graph':info,'counts_with_empty':expected});writej(out/'scenarios.json',scenarios)

def cover_lp(vertices,columns,D,out,extra=None):
    from numerical import np,linprog
    from scipy.sparse import coo_matrix
    vi={v:i for i,v in enumerate(vertices)};rows=[];cols=[];data=[]
    for i,C in enumerate(columns):
        for v in C:rows.append(i);cols.append(vi[v]);data.append(-1.)
        if extra is not None and len(C)==5:rows.append(i);cols.append(len(vertices));data.append(-1.)
    N=len(vertices)+(extra is not None)
    A=coo_matrix((data,(rows,cols)),shape=(len(columns),N)).tocsr();c=np.ones(N)
    bounds=[(0,None)]*len(vertices)
    if extra is not None:c[-1]=extra;bounds.append((None,None))
    r=linprog(c,A_ub=A,b_ub=-np.ones(len(columns)),bounds=bounds,method='highs-ds')
    require(r.success and r.x is not None and np.isfinite(r.x).all(),'cover numerical construction failed')
    np.savez_compressed(out/'numerical.npz',x=r.x,ineqlin_marginals=r.ineqlin.marginals)
    w={v:max(0,math.ceil(float(r.x[i])*D)) for i,v in enumerate(vertices)};mu=math.ceil(float(r.x[-1])*D) if extra is not None else 0
    for C in columns:
        lack=D-sum(w[v] for v in C)-(mu if extra is not None and len(C)==5 else 0)
        if lack>0:w[C[0]]+=lack
    require(all(sum(w[v] for v in C)+(mu if extra is not None and len(C)==5 else 0)>=D for C in columns),'cover exact repair failed')
    writej(out/'model.json',{'vertices':vertices,'columns':columns,'denominator':D,'five_equality_count':extra,'equality_multiplier_free':extra is not None})
    return w,mu

def dual250(name,records,out):
    root=get(records,'dsjc250.reconstruct','sets');fam={s:read_sets(root,s) for s in (4,5)}
    check=load('checkers/dsjc250/verify.py');g=check.parse_graph(graph('dsjc250'));D=10**9
    specs={'ge4_global':((),None,39,0),'ge4_h5_eq_2':((),2,36,0),'h5_1_forbid_x1':((0,),None,36,37),'h5_1_x3_slack':((2,),None,37,37),'h5_2_forbid_x1_x3':((0,2),None,33,34)}
    indices,extra,cap,required=specs[name];tops=[fam[5][i] for i in indices];used=set(itertools.chain.from_iterable(tops));verts=[v for v in range(1,251) if v not in used]
    columns=[C for s in ((4,5) if name.startswith('ge4') else (4,)) for C in fam[s] if used.isdisjoint(C)]
    w,mu=cover_lp(verts,columns,D,out,extra);W={v:w.get(v,0) for v in range(1,251)};rhs=sum(W.values())+(extra or 0)*mu
    require(0<=rhs//D<=cap,'new 250 cover misses required bound')
    props={'schema':'exact_mscp_layered_rational_v1' if name.startswith('ge4') else 'dsjc2509_residual_k4_dual_v1','certificate_id':name,'graph_raw_sha256':g['raw_hash'],'graph_canonical_sha256':g['canonical_hash'],'vertices':250,'denominator':D,'rhs_numerator':rhs,'claimed_bound':rhs//D}
    rows=[]
    if name.startswith('ge4'):
        props.update(maximum_class_size=5,minimum_class_size=4,condition_count=int(extra is not None))
        if extra is not None:rows.append(f'condition\t5\t{extra}\t{mu}')
    else:
        props.update(stable_set_size=4,fixed_top_set_count=len(tops),required_residual_sets=required,slack_budget=rhs-required*D,purpose='fresh residual covering bound')
        rows += [f'fixed_top_set\tx{i+1}\t'+ ' '.join(map(str,C)) for i,C in zip(indices,tops)]
    rows += [f'weight\t{v}\t{W[v]}' for v in range(1,251)]
    filename=name+'.rational' if name.startswith('ge4') else 'dual_'+name+'.rational'
    (out/filename).write_text('\n'.join([f'{k}={v}' for k,v in props.items()]+rows)+'\n')

def seed500(pi,records,out):
    root=get(records,'dsjc500.reconstruct','sets');S={s:read_sets(root,s) for s in (3,4,5)}
    tops=readj(get(records,'dsjc500.reconstruct','scenarios'))['packings'][pi-1];used=set(itertools.chain.from_iterable(tops));res=[v for v in range(1,501) if v not in used]
    require(len(res)==425,'seed residual universe');q=[C for C in S[4] if used.isdisjoint(C)]
    w,_=cover_lp(res,q,10**12,out);bound=sum(w.values())//10**12;cap=100 if pi in (2,4) else 101
    require(bound<=cap+1,'fresh seed floor exceeds tree contract')
    (out/f'k4dual_P{pi}.txt').write_text(''.join(f'{v} {w[v]}\n' for v in res))

def normalize_farkas(pi,raw,records,out):
    m=load('existing/dsjc500/baseline/common.py');g=m.parse_dimacs(graph('dsjc500'));S=m.enumerate_stable_sets(g,6);best,packs=m.enumerate_packings(S[5]);p=packs[pi-1]
    d=readj(raw);c=d['certificate'];z=c['weights'];require(type(c['denominator']) is int and c['denominator']>0 and all(type(x) is int for x in z),'malformed Farkas candidate')
    top=[S[5][i] for i in p];used=set(itertools.chain.from_iterable(top));res=[v for v in range(1,501) if v not in used];q=[C for C in S[4] if used.isdisjoint(C)];t=[C for C in S[3] if used.isdisjoint(C)]
    require(len(z)==len(res)+2,'Farkas dimensions');w=dict(zip(res,z));m4,m3=z[-2:];mins4=min(sum(w[v] for v in C)+m4 for C in q);mins3=min(sum(w[v] for v in C)+m3 for C in t);rhs=sum(z[:-2])+101*m4+7*m3
    require(min(mins4,mins3)>=0 and rhs<0,'Farkas content is not an exact certificate')
    writej(out/'certificate.json',{'schema':'dsjc5009_exact_cover_farkas_v1','graph_raw_sha256':g['raw_sha256'],'graph_canonical_sha256':g['canonical_sha256'],'vertices':500,'packing_number':pi,'packing_indices':list(p),'packing_sets':top,'residual_vertices':res,'residual4_family_sha256':m.stable_tuple_hash(q),'residual3_family_sha256':m.stable_tuple_hash(t),'quad_quota':101,'triple_quota':7,'vertex_weights':[[v,w[v]] for v in res if w[v]],'quad_multiplier':m4,'triple_multiplier':m3,'rhs':rhs,'minimum_quad_column':mins4,'minimum_triple_column':mins3,'source_rounding_denominator':c['denominator'],'meaning':'Exact alternative for residual cover equations.'})

def exact1000(scenario,records,out,packing=False):
    from numerical import np
    rec=readj(get(records,'dsjc1000.reconstruct','reconstruction'));info=rec['graph'];sets=get(records,'dsjc1000.reconstruct','sets');tops=tuple(map(tuple,readj(get(records,'dsjc1000.reconstruct','scenarios'))['tops']))
    fixed=tuple(tops[i] for i,b in enumerate(scenario) if b=='1');used=set(itertools.chain.from_iterable(fixed));res=[v for v in range(1,1001) if v not in used];D=10**9;k=len(fixed)
    z=np.load(get(records,'dsjc1000.cap_lp' if packing else 'dsjc1000.lp.'+scenario,'numerical'),allow_pickle=False)
    require(z['residual'].tolist()==res,'numerical residual order mismatch');W=[0]*1000
    if packing:
        vals=z['ineqlin_marginals'];require(len(vals)==len(res) and np.isfinite(vals).all(),'bad packing marginals')
        for v,y in zip(res,vals):W[v-1]=cover_round(-float(y),D)
        eligible=[C for C in read_sets(sets,5) if used.isdisjoint(C)]
        for C in eligible:
            lack=D-sum(W[v-1] for v in C)
            if lack>0:W[C[0]-1]+=lack
        mn=min(sum(W[v-1] for v in C)-D for C in eligible);total=sum(W)
        require(mn>=0 and total<135*D,'fresh residual cap134 not obtained')
        c={'schema':'dsjc1000_size5_packing_dual_certificate_v1','graph':info,'scenario':'111','fixed_size6_classes':fixed,'denominator':D,'strict_upper_threshold':135,'integer_packing_cap':134,'residual_vertex_cover_weights_num':W,'minimum_column_surplus_num':mn,'dual_objective_num':total,'dual_objective_den':D}
    else:
        vals=z['eqlin_marginals'];require(len(vals)==len(res)+5 and np.isfinite(vals).all(),'bad conditional marginals')
        for v,y in zip(res,vals[:len(res)]):W[v-1]=free_lower(y,D)
        B=[free_upper(-float(x),D) for x in vals[len(res):]];delta=0;qcap=None
        if scenario=='111':
            receipt=readj(get(records,'dsjc1000.cap_verify','receipt'));cap=readj(get(records,'dsjc1000.cap_exact','certificate'))
            require(receipt['status']=='verified' and receipt['integer_cap']==134 and receipt['certificate_sha256']==sha(get(records,'dsjc1000.cap_exact','certificate')),'fresh cap gate mismatch')
            require(cap['scenario']==scenario and cap['fixed_size6_classes']==[list(C) for C in fixed] and cap['denominator']==D,'cap scope mismatch')
            require(len(z['ineqlin_marginals'])==1 and np.isfinite(z['ineqlin_marginals']).all(),'bad cap marginal')
            delta=cap_multiplier(z['ineqlin_marginals'][0],D);qcap=134 if delta else None
        mins=[]
        family={s:[C for C in read_sets(sets,s) if used.isdisjoint(C)] for s in range(1,6)}
        require(z['sizes'].tolist()==[s for s in range(1,6) for C in family[s]],'numerical column size/order mismatch')
        # All repairs decrease free equality potentials, preserving previously repaired columns.
        for s in range(1,6):
            upper=sum(B[:s])+(delta if s==5 else 0)
            repair_upper(W,family[s],upper)
        for s in range(1,6):mins.append(min(sum(B[:s])+(delta if s==5 else 0)-sum(W[v-1] for v in C) for C in family[s]))
        cc=load('existing/dsjc1000/cert_common.py');const=6*k*(k+1)//2*D;lb=const+sum(W)-sum(cc.gamma_num(b,D,k) for b in B)-delta*(qcap or 0)
        require(min(mins)>=0 and lb>102343*D,'fresh conditional target not obtained')
        c={'schema':'dsjc1000_conditional_dual_certificate_v1','graph':info,'scenario':scenario,'fixed_size6_classes':fixed,'forbidden_unselected_size6_classes':tuple(tops[i] for i,b in enumerate(scenario) if b=='0'),'k':k,'denominator':D,'residual_vertex_weights_num':W,'threshold_slopes_num':B,'q5_cap':qcap,'q5_cap_multiplier_num':delta,'constant_num':const,'lower_bound_num':lb,'lower_bound_den':D,'integer_lower_bound':-(-lb//D),'minimum_slack_num_by_size':mins}
    writej(out/'certificate.json',c)

def top2000(action,records,out):
    root=get(records,'c2000.census','sets');sets=read_sets(root,6);require(len(sets)==90,'unexpected six-family')
    adjacency=[set(j for j,T in enumerate(sets) if i!=j and not set(S).isdisjoint(T)) for i,S in enumerate(sets)]
    if action=='cliques':
        found=[];complete=True
        def visit(R,P,X):
            if not P and not X:found.append(sorted(x+1 for x in R));return
            u=max(P|X,key=lambda v:len(P&adjacency[v])) if P|X else None
            for v in sorted(P-(adjacency[u] if u is not None else set())):
                visit(R|{v},P&adjacency[v],X&adjacency[v]);P.remove(v);X.add(v)
        visit(set(),set(range(90)),set());found=sorted(set(map(tuple,found)))
        # Enumerate completely; retain valid singletons as in the reviewed constructor.
        found=sorted(set(found)|{(i,) for i in range(1,91)})
        writej(out/'cliques.json',found);writej(out/'status.json',{'complete':complete,'count':len(found)})
    elif action in ('packing','cover'):
        from numerical import np,milp
        from scipy.optimize import Bounds,LinearConstraint
        from scipy.sparse import coo_matrix
        rows=[];cols=[];data=[];lo=[];hi=[]
        if action=='packing':
            N=90
            for i in range(N):
                for j in sorted(adjacency[i]):
                    if j>i:
                        row=len(lo);rows += [row,row];cols += [i,j];data += [1.,1.];lo.append(-np.inf);hi.append(1.)
            row=len(lo);rows+= [row]*N;cols+=list(range(N));data += [1.]*N;lo.append(52.);hi.append(52.)
        else:
            cliques=readj(get(records,'c2000.cliques','cliques'));N=len(cliques)
            for C in cliques:
                require(C and len(set(C))==len(C) and all(type(i)is int and 1<=i<=90 for i in C),'invalid candidate clique')
                require(all(j-1 in adjacency[i-1] for i,j in itertools.combinations(C,2)),'candidate is not clique')
            for j,C in enumerate(cliques):
                for i in C:rows.append(i-1);cols.append(j);data.append(1.)
            lo=[1.]*90;hi=[np.inf]*90;rows += [90]*N;cols +=list(range(N));data +=[1.]*N;lo.append(-np.inf);hi.append(52.)
        A=coo_matrix((data,(rows,cols)),shape=(len(lo),N)).tocsc()
        r=milp(np.zeros(N),integrality=np.ones(N),bounds=Bounds(0,1),constraints=LinearConstraint(A,lo,hi),options={})
        require(r.x is not None and np.isfinite(r.x).all(),'no fresh candidate');np.savez_compressed(out/'numerical.npz',x=r.x)
        chosen=[i for i,x in enumerate(r.x) if x>.5]
        if action=='packing':
            require(len(chosen)==52 and all(j not in adjacency[i] for i,j in itertools.combinations(chosen,2)),'invalid packing candidate')
            writej(out/'packing.json',[i+1 for i in chosen]);writej(out/'conflict_graph.json',[sorted(a) for a in adjacency])
        else:
            require(len(chosen)<=52,'too many cover cliques');assigned=set();cover=[]
            for j in chosen:
                C=sorted(set(cliques[j])-assigned)
                if C:cover.append(C);assigned.update(C)
            require(assigned==set(range(1,91)) and len(cover)==52,'cover is not a 52-part partition');writej(out/'cover.json',cover)
    elif action=='assemble':
        check=load('checkers/c2000/verify_c2000_9_top_envelope.py');candidates=[]
        for q6 in range(53):
            a,b=divmod(2000-q6,5);q=[a+1]*b+[a]*(5-b)+[q6];require(q[-2]>=q[-1],'arithmetic monotonicity');candidates.append((sum(x*(x+1)//2 for x in q),q))
        val,q=min(candidates);h=[q[i]-(q[i+1] if i<5 else 0) for i in range(6)]
        c={'schema':'c2000_9_size6_packing_certificate_v1','stable_set_census_sha256':check.semantic_hash(sets),'maximum_packing_size':52,'disjoint_packing_ids':readj(get(records,'c2000.packing','packing')),'conflict_clique_cover':readj(get(records,'c2000.cover','cover')),'arithmetic_profile':{'q':q,'h':h,'vertices':2000,'lower_bound':val}}
        writej(out/'certificate.json',c);check.verify(get(records,'c2000.census','six_sets'),out/'certificate.json')
    else:raise ValueError('unknown top constructor')
