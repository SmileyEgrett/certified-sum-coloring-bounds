#!/usr/bin/env python3
import argparse,importlib.util,itertools,json,resource,time
from pathlib import Path
import numpy as np
from numerical import linprog
from scipy.optimize import Bounds
from scipy.sparse import csr_matrix
spec=importlib.util.spec_from_file_location('base',Path(__file__).with_name('solve_conditional_lp.py'));base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
ap=argparse.ArgumentParser();ap.add_argument('--sets',type=Path,required=True);ap.add_argument('--scenario',required=True);ap.add_argument('--q5-cap',type=int,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--time-limit',type=float,default=1800);a=ap.parse_args()
selected=[base.TOPS[i] for i,c in enumerate(a.scenario) if c=='1'];used=set(itertools.chain.from_iterable(selected));k=len(selected);residual=[v for v in range(1,1001) if v not in used]
t0=time.perf_counter();sets,sizes=base.load_eligible(a.sets,used);t1=time.perf_counter();A,b,c,yidx,caps,const=base.build(sets,sizes,residual,k);t2=time.perf_counter()
row=np.zeros(A.shape[1]);row[:len(sets)]=(sizes==5);Aub=csr_matrix(row.reshape(1,-1))
print(json.dumps({'stage':'built','scenario':a.scenario,'q5_cap':a.q5_cap,'eligible_sets':len(sets),'variables':A.shape[1],'constraints_eq':A.shape[0]}),flush=True)
lb=np.zeros(A.shape[1]);ub=np.ones(A.shape[1]);ub[:len(sets)]=np.inf
r=linprog(c,A_ub=Aub,b_ub=np.array([a.q5_cap],float),A_eq=A,b_eq=b,bounds=np.column_stack((lb,ub)),method='highs',options={'disp':True,'presolve':True,**({'time_limit':a.time_limit} if a.time_limit > 0 else {}),'dual_feasibility_tolerance':1e-9,'primal_feasibility_tolerance':1e-9,'ipm_optimality_tolerance':1e-10});t3=time.perf_counter()
d={'schema':'dsjc1000_conditional_lp_q5cap_numerical_v1','scenario':a.scenario,'selected_top_classes':[list(x) for x in selected],'k':k,'q5_cap':a.q5_cap,'constant':const,'status':int(r.status),'success':bool(r.success),'message':str(r.message),'variable_objective':None if r.fun is None else float(r.fun),'total_objective':None if r.fun is None else float(r.fun+const),'iterations':int(r.nit),'timing_seconds':{'load_filter':t1-t0,'build':t2-t1,'solve':t3-t2,'total':t3-t0},'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
if r.x is not None:
 x=r.x[:len(sets)];d['q_residual_by_threshold']=[float(x[sizes>=t].sum()) for t in range(1,6)];d['q5_ub_marginal']=float(r.ineqlin.marginals[0]);np.savez_compressed(a.out.with_suffix('.npz'),x=x,eqlin_marginals=r.eqlin.marginals,ineqlin_marginals=r.ineqlin.marginals,upper_marginals=r.upper.marginals,lower_marginals=r.lower.marginals,sizes=sizes,residual=np.asarray(residual,dtype=np.int16))
a.out.with_suffix('.json').write_text(json.dumps(d,indent=2)+'\n');print('FINAL',json.dumps(d,indent=2),flush=True)
