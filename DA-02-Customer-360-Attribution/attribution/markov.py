"""
Data-driven attribution with a first-order Markov chain + removal effect.

Reads customer journeys from the dbt model `fct_conversion_paths`, builds the channel transition matrix
(START -> channels -> CONVERSION / NULL), and measures each channel's *removal effect*: how much the overall
conversion probability drops if that channel disappears. Conversions and revenue are then shared out in
proportion to the removal effects. Results are written back to the warehouse (`markov_channel_attribution`)
and to exports/markov_channel_attribution.csv for Tableau.

    python -m attribution.markov --target duckdb --db warehouse.duckdb
    python -m attribution.markov --target bigquery --project my-gcp-project --dataset analytics_marts
"""
from __future__ import annotations

import argparse
import os
from collections import defaultdict

import numpy as np
import pandas as pd

START, CONV, NULL = "(start)", "(conversion)", "(null)"


def parse_paths(df: pd.DataFrame) -> list[tuple[list[str], bool, float]]:
    return [([c.strip() for c in str(p).split(">") if c.strip()], bool(cv), float(rv or 0))
            for p, cv, rv in zip(df["path"], df["converted"], df["revenue"])]


def transition_matrix(journeys) -> tuple[list[str], np.ndarray]:
    counts: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for path, converted, _ in journeys:
        seq = [START] + path + [CONV if converted else NULL]
        for a, b in zip(seq[:-1], seq[1:]):
            counts[a][b] += 1
    channels = sorted({c for path, _, _ in journeys for c in path})
    states = [START] + channels + [CONV, NULL]
    idx = {s: i for i, s in enumerate(states)}
    T = np.zeros((len(states), len(states)))
    for a, row in counts.items():
        total = sum(row.values())
        for b, n in row.items():
            T[idx[a], idx[b]] = n / total
    T[idx[CONV], idx[CONV]] = 1.0  # absorbing states
    T[idx[NULL], idx[NULL]] = 1.0
    return states, T


def conversion_probability(states: list[str], T: np.ndarray, removed: str | None = None) -> float:
    """P(reach CONVERSION from START), solved exactly via absorbing-chain algebra."""
    T = T.copy()
    idx = {s: i for i, s in enumerate(states)}
    if removed is not None:  # every visit to the removed channel now leads to NULL
        r = idx[removed]
        T[r, :] = 0.0
        T[r, idx[NULL]] = 1.0
    transient = [i for s, i in idx.items() if s not in (CONV, NULL)]
    Q = T[np.ix_(transient, transient)]
    R = T[np.ix_(transient, [idx[CONV]])]
    N = np.linalg.solve(np.eye(len(transient)) - Q, R)  # absorption probabilities into CONV
    return float(N[transient.index(idx[START]), 0])


def markov_attribution(df: pd.DataFrame) -> pd.DataFrame:
    journeys = parse_paths(df)
    states, T = transition_matrix(journeys)
    base = conversion_probability(states, T)
    channels = [s for s in states if s not in (START, CONV, NULL)]
    effects = {c: max(0.0, 1 - conversion_probability(states, T, removed=c) / base) for c in channels}
    total_effect = sum(effects.values()) or 1.0
    total_conv = sum(1 for _, cv, _ in journeys if cv)
    total_rev = sum(rv for _, cv, rv in journeys if cv)
    out = pd.DataFrame({
        "channel": channels,
        "removal_effect": [effects[c] for c in channels],
        "credit_share": [effects[c] / total_effect for c in channels],
    })
    out["attributed_conversions"] = out["credit_share"] * total_conv
    out["attributed_revenue"] = out["credit_share"] * total_rev
    out["baseline_conversion_probability"] = base
    return out.sort_values("attributed_revenue", ascending=False).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["duckdb", "bigquery"], default="duckdb")
    ap.add_argument("--db", default="warehouse.duckdb")
    ap.add_argument("--schema", default="analytics_marts")
    ap.add_argument("--project")
    ap.add_argument("--dataset", default="analytics_marts")
    ap.add_argument("--export", default="exports/markov_channel_attribution.csv")
    a = ap.parse_args()

    if a.target == "duckdb":
        import duckdb
        con = duckdb.connect(a.db)
        paths = con.execute(f"select path, converted, revenue from {a.schema}.fct_conversion_paths").df()
        result = markov_attribution(paths)
        con.register("result_df", result)
        con.execute(f"create or replace table {a.schema}.markov_channel_attribution as select * from result_df")
        con.close()
    else:
        from google.cloud import bigquery
        client = bigquery.Client(project=a.project)
        paths = client.query(
            f"select path, converted, revenue from `{a.project}.{a.dataset}.fct_conversion_paths`").to_dataframe()
        result = markov_attribution(paths)
        client.load_table_from_dataframe(
            result, f"{a.project}.{a.dataset}.markov_channel_attribution",
            job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")).result()

    os.makedirs(os.path.dirname(a.export) or ".", exist_ok=True)
    result.to_csv(a.export, index=False)
    with pd.option_context("display.float_format", "{:,.3f}".format):
        print(result.to_string(index=False))


if __name__ == "__main__":
    main()
