
import secrets, itertools
from typing import List

def build_alias(weights: List[float]):
    n=len(weights)
    avg = sum(weights)/max(n,1)
    prob=[0.0]*n; alias=[0]*n
    small=[]; large=[]
    scaled=[(w/avg if avg>0 else 0) for w in weights]
    for i,w in enumerate(scaled):
        (small if w<1 else large).append(i)
    while small and large:
        s=small.pop(); l=large.pop()
        prob[s]=scaled[s]; alias[s]=l
        scaled[l]=scaled[l]-(1-prob[s])
        (small if scaled[l]<1 else large).append(l)
    for i in itertools.chain(small,large):
        prob[i]=1.0; alias[i]=i
    return prob, alias

def sample_unique(ids: List[str], weights: List[float], k: int, seed=None):
    if seed is not None:
        import random
        random.seed(seed)
        chooser=lambda n: random.randrange(n)
        rand=lambda : random.random()
    else:
        chooser=lambda n: secrets.randbelow(n)
        rand=lambda : secrets.randbits(32)/((1<<32)-1)

    prob, alias = build_alias(weights)
    chosen=set()
    n=min(k, len(ids))
    while len(chosen)<n:
        i = chooser(len(ids))
        chosen.add(i if rand()<prob[i] else alias[i])
    return [ids[i] for i in chosen]
