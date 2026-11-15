{# Small cross-database helpers so every model runs on BigQuery and DuckDB unchanged. #}

{% macro micros_to_timestamp(col) -%}
  {{ return(adapter.dispatch('micros_to_timestamp')(col)) }}
{%- endmacro %}
{% macro bigquery__micros_to_timestamp(col) -%} timestamp_micros({{ col }}) {%- endmacro %}
{% macro default__micros_to_timestamp(col) -%} make_timestamp({{ col }}) {%- endmacro %}

{% macro nullif_blank(col) -%}
  nullif(trim(cast({{ col }} as {{ dbt.type_string() }})), '')
{%- endmacro %}

{# seconds between two timestamps as a float #}
{% macro seconds_between(start_ts, end_ts) -%}
  cast({{ dbt.datediff(start_ts, end_ts, 'second') }} as {{ dbt.type_float() }})
{%- endmacro %}

{% macro surrogate_key(cols) -%}
  {{ return(adapter.dispatch('surrogate_key')(cols)) }}
{%- endmacro %}
{% macro bigquery__surrogate_key(cols) -%}
  to_hex(md5(concat({% for c in cols %}coalesce(cast({{ c }} as string), '_null_'){% if not loop.last %}, '|', {% endif %}{% endfor %})))
{%- endmacro %}
{% macro default__surrogate_key(cols) -%}
  md5({% for c in cols %}coalesce(cast({{ c }} as varchar), '_null_'){% if not loop.last %} || '|' || {% endif %}{% endfor %})
{%- endmacro %}

{# BigQuery requires the explicit keyword, DuckDB/Postgres accept plain UNION #}
{% macro union_distinct() -%}{{ return(adapter.dispatch('union_distinct')()) }}{%- endmacro %}
{% macro bigquery__union_distinct() -%} union distinct {%- endmacro %}
{% macro default__union_distinct() -%} union {%- endmacro %}
