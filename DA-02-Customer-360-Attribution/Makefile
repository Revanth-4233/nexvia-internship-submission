# End-to-end pipeline. `make all` runs everything locally on DuckDB (no cloud account needed).
PY ?= python
DBT ?= dbt
DBT_FLAGS = --profiles-dir .

.PHONY: all setup data load dbt markov export compare test docs bq-load bq-dbt bq-markov clean

all: data load dbt markov export compare test

setup:
	$(PY) -m pip install -r requirements.txt
	cp -n dbt/profiles.yml.example dbt/profiles.yml || true

data:
	$(PY) data_generator/generate_data.py --customers 5000 --seed 42 --out data/raw

load:
	$(PY) scripts/load_duckdb.py --db warehouse.duckdb --data data/raw

dbt:
	cd dbt && $(DBT) build $(DBT_FLAGS) --target dev_duckdb

markov:
	$(PY) -m attribution.markov --target duckdb --db warehouse.duckdb

export:
	$(PY) scripts/export_for_tableau.py --db warehouse.duckdb

compare:
	$(PY) scripts/model_comparison.py --db warehouse.duckdb --chart docs/model_comparison.png

test:
	$(PY) -m pytest -q

docs:
	cd dbt && $(DBT) docs generate $(DBT_FLAGS) && $(DBT) docs serve $(DBT_FLAGS)

# ---- BigQuery (set GCP_PROJECT first) ----
bq-load:
	$(PY) scripts/load_bigquery.py --project $(GCP_PROJECT) --dataset raw

bq-dbt:
	cd dbt && $(DBT) build $(DBT_FLAGS) --target bigquery

bq-markov:
	$(PY) -m attribution.markov --target bigquery --project $(GCP_PROJECT) --dataset analytics_marts

clean:
	rm -rf dbt/target dbt/logs warehouse.duckdb warehouse.duckdb.wal
