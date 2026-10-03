"""Single-thread SciPy/HiGHS entry point, with actual native option readback."""
import os,sys,json
from pathlib import Path
from core import admission,require
admission()
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    require(os.environ.get(key)=='1','numerical environment not pinned before import: '+key)
import numpy as np
import scipy
import scipy.optimize._highspy._core as _native
from scipy.optimize import linprog as _linprog,milp as _milp
_NativeHighs=_native._Highs
_reported=False
last_native_options={} 
class AuditedHighs:
    def __init__(self):self.native=_NativeHighs()
    def __getattr__(self,name):return getattr(self.native,name)
    def passOptions(self,options):
        require(options.threads==1,'HiGHS requested threads not1');r=self.native.passOptions(options)
        actual=self.native.getOptions();require(actual.threads==1,'HiGHS actual threads not1')
        last_native_options.update(threads=actual.threads,time_limit=actual.time_limit,mip_max_nodes=actual.mip_max_nodes,simplex_iteration_limit=actual.simplex_iteration_limit,ipm_iteration_limit=actual.ipm_iteration_limit)
        return r
    def run(self):
        global _reported
        try:return self.native.run()
        finally:
            main=sorted(os.sched_getaffinity(0));tids={p.name:sorted(os.sched_getaffinity(int(p.name))) for p in Path('/proc/self/task').iterdir()}
            require(len(main)==1 and all(v==main for v in tids.values()),'numerical TID escaped one-core affinity')
            require(len(tids)==1,'numerical worker count exceeds one TID')
            if not _reported:
                print(json.dumps({'numerical_runtime':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'HiGHS_version':self.native.version(),'actual_HiGHS_threads':self.native.getOptions().threads,'post_solve_tid_affinities':tids,'worker_tid_limit':1,'actual_native_limits':{k:('infinity' if v==float('inf') else v) for k,v in last_native_options.items()}}}),flush=True);_reported=True
_native._Highs=AuditedHighs

def linprog(*args,**kw):
    options=dict(kw.get('options') or {});options['threads']=1;kw['options']=options;return _linprog(*args,**kw)
def milp(*args,**kw):
    options=dict(kw.get('options') or {});options['threads']=1;kw['options']=options;return _milp(*args,**kw)
