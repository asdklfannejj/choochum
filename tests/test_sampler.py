
from src.draw.sampler import sample_unique

def test_sampler():
    ids = ['a','b','c','d','e']
    w = [1,1,1,1,1]
    winners = sample_unique(ids, w, 3, seed=42)
    assert len(set(winners)) == 3
