import pandas as pd
import pytest
from attribution.markov import markov_attribution, transition_matrix, conversion_probability, parse_paths


def df(rows):
    return pd.DataFrame(rows, columns=["path", "converted", "revenue"])


def test_single_channel_gets_all_credit():
    out = markov_attribution(df([("Email", True, 100), ("Email", False, 0)]))
    assert list(out.channel) == ["Email"]
    assert out.credit_share.iloc[0] == pytest.approx(1.0)
    assert out.attributed_revenue.sum() == pytest.approx(100)


def test_credit_sums_to_totals():
    data = df([("Paid Search > Email", True, 500), ("Display > Paid Search", True, 300),
               ("Display", False, 0), ("Organic Search > Email", False, 0), ("Email", True, 200)])
    out = markov_attribution(data)
    assert out.credit_share.sum() == pytest.approx(1.0)
    assert out.attributed_conversions.sum() == pytest.approx(3)
    assert out.attributed_revenue.sum() == pytest.approx(1000)


def test_channel_that_never_converts_gets_no_credit():
    data = df([("Email", True, 100), ("Display", False, 0), ("Display", False, 0)])
    out = markov_attribution(data).set_index("channel")
    assert out.loc["Display", "credit_share"] == pytest.approx(0.0)


def test_baseline_probability_matches_observed_rate():
    data = df([("A", True, 1), ("A", False, 0), ("B", False, 0), ("B", True, 1)])
    states, T = transition_matrix(parse_paths(data))
    assert conversion_probability(states, T) == pytest.approx(0.5)
