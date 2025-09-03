import pandas as pd
from src.weighted_draw import run_raffle

def test_weight_bias():
    df = pd.DataFrame({
        "고객ID": range(1000),
        "성별": ["여성"]*700 + ["남성"]*300
    })
    config = {
        "unique_key": "고객ID",
        "eligibility": [],
        "weights": {
            "성별": {"type": "categorical", "mapping": {"여성": 1.2, "남성": 1.0}}
        },
        "defaults": {"categorical": 1.0, "bucket": 1.0}
    }
    winners = run_raffle(df, config, n_winners=200, seed=123)["winners"]
    female_rate = (winners["성별"] == "여성").mean()
    assert 0.7 < female_rate < 0.8
