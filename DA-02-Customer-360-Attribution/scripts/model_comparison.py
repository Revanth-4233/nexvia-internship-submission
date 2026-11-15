"""Print and chart revenue by channel under every attribution model (rule-based + Markov).

    python scripts/model_comparison.py --db warehouse.duckdb --chart docs/model_comparison.png
"""
import argparse
import duckdb
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="warehouse.duckdb")
    ap.add_argument("--schema", default="analytics_marts")
    ap.add_argument("--chart", default="docs/model_comparison.png")
    a = ap.parse_args()
    con = duckdb.connect(a.db, read_only=True)
    rule = con.execute(f"""
        select channel, attribution_model, sum(attributed_revenue) as revenue
        from {a.schema}.fct_attribution_long group by 1, 2""").df()
    wide = rule.pivot(index="channel", columns="attribution_model", values="revenue")
    mk = con.execute(f"select channel, attributed_revenue from {a.schema}.markov_channel_attribution").df()
    wide["markov"] = mk.set_index("channel")["attributed_revenue"]
    spend = con.execute(f"""select channel, sum(spend) as spend from {a.schema}.mart_channel_performance
                            where attribution_model = 'linear' group by 1""").df().set_index("channel")["spend"]
    wide = wide.fillna(0).sort_values("markov", ascending=False)
    order = ["first_touch", "last_touch", "last_non_direct", "linear", "time_decay", "position_based", "markov"]
    wide = wide[order]
    share = wide.div(wide.sum()) * 100
    print("Share of revenue by channel (%):\n", share.round(1).to_string(), "\n")
    roas = wide.div(spend, axis=0).loc[spend[spend > 0].index]
    print("ROAS by paid channel:\n", roas.round(2).to_string())

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ax = share.plot(kind="bar", figsize=(12, 5.5), width=0.85, colormap="tab10")
    ax.set_ylabel("% of attributed revenue"); ax.set_xlabel("")
    ax.set_title("Revenue credit by channel under each attribution model")
    ax.legend(ncol=4, fontsize=9, frameon=False)
    plt.xticks(rotation=20, ha="right"); plt.tight_layout(); plt.savefig(a.chart, dpi=130)
    print(f"\nchart -> {a.chart}")

if __name__ == "__main__":
    main()
