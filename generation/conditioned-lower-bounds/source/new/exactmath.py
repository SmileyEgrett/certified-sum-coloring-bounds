"""Exact reconstruction rounding directions; no numerical library dependency."""
import math
from core import require

def cover_round(x,D):return max(0,math.ceil(float(x)*D+1e-4))
def free_lower(x,D):return math.floor(float(x)*D)-1000
def free_upper(x,D):return math.ceil(float(x)*D)+1000
def cap_multiplier(m,D):return max(0,math.ceil(-float(m)*D)+1000)
def repair_upper(W,columns,upper):
    for C in columns:
        excess=sum(W[v-1] for v in C)-upper
        if excess>0:W[C[0]-1]-=excess
    require(all(sum(W[v-1] for v in C)<=upper for C in columns),'upper repair failure')
def direct_seed_action(bound,cap):
    require(type(bound)is int and type(cap)is int and bound>=0 and cap>=0,'bad cap integer')
    require(bound<=cap+1,'seed floor exceeds tree contract')
    return 'direct_seed' if bound<=cap else 'tree'
