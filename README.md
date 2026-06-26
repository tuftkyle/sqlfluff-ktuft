# sqlfluff-ktuft

Personal SQLFluff plugin for KTuft SQL layout preferences.

This package adds custom SQLFluff rules named `Ktuft_KL01` through
`Ktuft_KL19`. It is intended for personal/editor formatting workflows, not as a
default team formatter unless a project explicitly chooses to adopt it.

## Install

Install the plugin into the same Python environment where `sqlfluff` runs:

```bash
pip install "git+https://github.com/tuftkyle/sqlfluff-ktuft.git"
```

Upgrade to the latest commit:

```bash
pip install --upgrade --force-reinstall "git+https://github.com/tuftkyle/sqlfluff-ktuft.git"
```

For local development:

```bash
git clone https://github.com/tuftkyle/sqlfluff-ktuft.git
cd sqlfluff-ktuft
pip install -e .
```

Confirm SQLFluff can see the plugin:

```bash
sqlfluff rules | grep Ktuft
```

You should see rules such as `Ktuft_KL01` and `Ktuft_KL19`.

## Recommended Rule Profile

The personal profile is:

```text
AL01,ST05,LT12,Ktuft_KL01,Ktuft_KL02,Ktuft_KL03,Ktuft_KL04,Ktuft_KL05,Ktuft_KL06,Ktuft_KL07,Ktuft_KL08,Ktuft_KL09,Ktuft_KL10,Ktuft_KL11,Ktuft_KL12,Ktuft_KL13,Ktuft_KL14,Ktuft_KL15,Ktuft_KL16,Ktuft_KL17,Ktuft_KL18,Ktuft_KL19
```

This combines a small set of built-in SQLFluff rules with the custom personal
rules:

- `AL01`: require explicit `as` for table aliases.
- `ST05`: block long nested subqueries.
- `LT12`: require a final newline.

## Configure SQLFluff To Use It

If you want a project to use this profile by default, add the plugin rules to
that project config:

```ini
[sqlfluff]
dialect = snowflake
templater = dbt
rules = AL01,ST05,LT12,Ktuft_KL01,Ktuft_KL02,Ktuft_KL03,Ktuft_KL04,Ktuft_KL05,Ktuft_KL06,Ktuft_KL07,Ktuft_KL08,Ktuft_KL09,Ktuft_KL10,Ktuft_KL11,Ktuft_KL12,Ktuft_KL13,Ktuft_KL14,Ktuft_KL15,Ktuft_KL16,Ktuft_KL17,Ktuft_KL18,Ktuft_KL19
```

For dbt projects, keep the existing project-specific settings such as
`project_dir`, `profiles_dir`, `profile`, and `target`. This plugin only adds
rules; it does not replace the dbt templater setup.

## Use Without Replacing A Project Formatter

For personal formatting, do not edit the project `.sqlfluff` file. Instead,
pass the rule profile at the command line.

Lint one file:

```bash
sqlfluff lint models/intermediate/staff/int_gar_staff_annual_clean.sql \
  --config .sqlfluff \
  --rules AL01,ST05,LT12,Ktuft_KL01,Ktuft_KL02,Ktuft_KL03,Ktuft_KL04,Ktuft_KL05,Ktuft_KL06,Ktuft_KL07,Ktuft_KL08,Ktuft_KL09,Ktuft_KL10,Ktuft_KL11,Ktuft_KL12,Ktuft_KL13,Ktuft_KL14,Ktuft_KL15,Ktuft_KL16,Ktuft_KL17,Ktuft_KL18,Ktuft_KL19 \
  -n
```

Fix one file:

```bash
sqlfluff fix models/intermediate/staff/int_gar_staff_annual_clean.sql \
  --config .sqlfluff \
  --rules AL01,ST05,LT12,Ktuft_KL01,Ktuft_KL02,Ktuft_KL03,Ktuft_KL04,Ktuft_KL05,Ktuft_KL06,Ktuft_KL07,Ktuft_KL08,Ktuft_KL09,Ktuft_KL10,Ktuft_KL11,Ktuft_KL12,Ktuft_KL13,Ktuft_KL14,Ktuft_KL15,Ktuft_KL16,Ktuft_KL17,Ktuft_KL18,Ktuft_KL19 \
  -n
```

Fix a copied style-lab folder:

```bash
sqlfluff fix debug/sqlfluff-style-lab/output/models \
  --config .sqlfluff \
  --rules AL01,ST05,LT12,Ktuft_KL01,Ktuft_KL02,Ktuft_KL03,Ktuft_KL04,Ktuft_KL05,Ktuft_KL06,Ktuft_KL07,Ktuft_KL08,Ktuft_KL09,Ktuft_KL10,Ktuft_KL11,Ktuft_KL12,Ktuft_KL13,Ktuft_KL14,Ktuft_KL15,Ktuft_KL16,Ktuft_KL17,Ktuft_KL18,Ktuft_KL19 \
  --disregard-sqlfluffignores \
  -n
```

## Optional Personal Wrapper

To avoid changing a repo's default formatter, create a local wrapper script that
always passes the personal rule profile. Keep this script outside project repos,
for example at `~/.local/bin/sqlfluff-ktuft`.

```bash
#!/usr/bin/env bash
set -euo pipefail

RULES="AL01,ST05,LT12,Ktuft_KL01,Ktuft_KL02,Ktuft_KL03,Ktuft_KL04,Ktuft_KL05,Ktuft_KL06,Ktuft_KL07,Ktuft_KL08,Ktuft_KL09,Ktuft_KL10,Ktuft_KL11,Ktuft_KL12,Ktuft_KL13,Ktuft_KL14,Ktuft_KL15,Ktuft_KL16,Ktuft_KL17,Ktuft_KL18,Ktuft_KL19"

sqlfluff "$@" --rules "$RULES"
```

Make it executable:

```bash
chmod +x ~/.local/bin/sqlfluff-ktuft
```

Then run:

```bash
sqlfluff-ktuft fix models/intermediate/staff/int_gar_staff_annual_clean.sql --config .sqlfluff -n
```

This keeps the project `.sqlfluff`, pre-commit hooks, and dbt Cloud formatting
behavior unchanged. The wrapper only affects commands where you explicitly call
`sqlfluff-ktuft`.

## Uninstall

Remove the plugin from the Python environment where it was installed:

```bash
pip uninstall sqlfluff-ktuft
```

If you installed from an editable checkout, run the same command from any
directory:

```bash
pip uninstall sqlfluff-ktuft
```

If you created the optional wrapper script, remove it:

```bash
rm ~/.local/bin/sqlfluff-ktuft
```

To leave a project's original formatter alone:

- Do not add `Ktuft_*` rules to the project `.sqlfluff`.
- Do not add this package to project requirements unless the team wants it.
- Do not add the wrapper to project pre-commit hooks.
- Use the plugin only through explicit local commands such as `sqlfluff-ktuft fix ...`.

After uninstalling, verify SQLFluff no longer sees these rules:

```bash
sqlfluff rules | grep Ktuft
```

No output means the plugin is no longer active in that environment.

## Rule Reference

All custom rules are fix-compatible. The examples below are intentionally small;
they show the formatting preference each rule enforces.

### `Ktuft_KL01` / `ktuft.from_newline`

Places the relation on the line after the `from` keyword.

Before:

```sql
select *
from my_table
```

After:

```sql
select *
from
    my_table
```

### `Ktuft_KL02` / `ktuft.join_on_trailing`

Keeps `on` on the same line as the joined relation.

Before:

```sql
left join dim_grantee as g
    on f.grantee_id = g.id
```

After:

```sql
left join dim_grantee as g on
    f.grantee_id = g.id
```

### `Ktuft_KL03` / `ktuft.join_predicate_indent`

Indents join predicate lines one level deeper than the join line.

Before:

```sql
left join dim_grantee as g on
f.grantee_id = g.id
```

After:

```sql
left join dim_grantee as g on
    f.grantee_id = g.id
```

### `Ktuft_KL04` / `ktuft.expand_inline_cte`

Expands compact CTE bodies onto separate lines, except for simple `select * from`
CTEs handled by `Ktuft_KL11`.

Before:

```sql
with source as (select id, name from {{ ref('stg_grantee') }})
```

After:

```sql
with

source as (

    select
        id,
        name
    from
        {{ ref('stg_grantee') }}

)
```

### `Ktuft_KL05` / `ktuft.from_indent`

Aligns `from` with the related `select`.

Before:

```sql
select
    id
    from
        my_table
```

After:

```sql
select
    id
from
    my_table
```

### `Ktuft_KL06` / `ktuft.from_relation_indent`

Indents the relation line one level deeper than `from`.

Before:

```sql
select *
from
my_table
```

After:

```sql
select *
from
    my_table
```

### `Ktuft_KL07` / `ktuft.cte_inner_spacing`

Keeps one blank line immediately inside multi-line CTE parentheses.

Before:

```sql
source as (
    select *
    from
        my_table
),
```

After:

```sql
source as (

    select *
    from
        my_table

),
```

### `Ktuft_KL08` / `ktuft.select_target_indent`

Indents top-level multi-line select targets one level deeper than `select`.

Before:

```sql
select
id,
name
from
    my_table
```

After:

```sql
select
    id,
    name
from
    my_table
```

### `Ktuft_KL09` / `ktuft.between_operand_layout`

Splits `between` operands onto aligned continuation lines.

Before:

```sql
where report_date between start_date and end_date
```

After:

```sql
where
    report_date between
        start_date and
        end_date
```

### `Ktuft_KL10` / `ktuft.clause_predicate_newline`

Puts `where`, `group by`, `having`, and `qualify` predicates or columns on
indented continuation lines.

Before:

```sql
select *
from
    my_table
where id is not null
group by id
```

After:

```sql
select *
from
    my_table
where
    id is not null
group by
    id
```

### `Ktuft_KL11` / `ktuft.simple_cte_single_line`

Keeps simple `select * from` CTEs on one line.

Before:

```sql
source as (

    select *
    from
        {{ ref('stg_grantee') }}

),
```

After:

```sql
source as (select * from {{ ref('stg_grantee') }}),
```

### `Ktuft_KL12` / `ktuft.long_select_list_wrap`

Wraps same-line select lists only when they exceed the line limit.

Before:

```sql
select id, name, service_area_title, service_area_type, state_code, service_area_status, source_family
```

After:

```sql
select
    id,
    name,
    service_area_title,
    service_area_type,
    state_code,
    service_area_status,
    source_family
```

### `Ktuft_KL13` / `ktuft.with_blank_line`

Keeps `with` on its own line followed by one blank line.

Before:

```sql
with source as (select * from {{ ref('stg_grantee') }})
```

After:

```sql
with

source as (select * from {{ ref('stg_grantee') }})
```

### `Ktuft_KL14` / `ktuft.compact_select_from`

Keeps short one-line select lists with their `from` clause.

Before:

```sql
select *, 'A', a_count
from
    wide
```

After:

```sql
select *, 'A', a_count from wide
```

### `Ktuft_KL15` / `ktuft.jinja_surrogate_key_arg_wrap`

Wraps long `dbt_utils.generate_surrogate_key` argument lists while keeping the
alias on the closing Jinja line.

Before:

```sql
{{ dbt_utils.generate_surrogate_key(['rno', 'org_name', 'public_org_name', 'grantee_status', 'state_code']) }} as id,
```

After:

```sql
{{ dbt_utils.generate_surrogate_key([
    'rno',
    'org_name',
    'public_org_name',
    'grantee_status',
    'state_code'
]) }} as id,
```

### `Ktuft_KL16` / `ktuft.union_list_indent`

Aligns compact `union` list entries with the preceding select.

Before:

```sql
select id from first_source
    union all
    select id from second_source
```

After:

```sql
select id from first_source
union all
select id from second_source
```

### `Ktuft_KL17` / `ktuft.leading_closing_bracket_indent`

Aligns leading closing brackets with the line that opened the bracketed
expression.

Before:

```sql
qualify
    row_number() over (
        order by
            updated_at desc
        ) = 1
```

After:

```sql
qualify
    row_number() over (
        order by
            updated_at desc
    ) = 1
```

### `Ktuft_KL18` / `ktuft.when_then_same_line`

Keeps short `when ... then ...` clauses on one line.

Before:

```sql
case
    when source_family = 'grantease'
    then 1
    else 2
end
```

After:

```sql
case
    when source_family = 'grantease' then 1
    else 2
end
```

### `Ktuft_KL19` / `ktuft.window_body_indent`

Indents multiline window bodies one level under the opening line, preserving
relative indentation inside the window body.

Before:

```sql
qualify
    row_number() over (
    partition by
        rno,
        gar_year
    order by
        ingested_at desc
    ) = 1
```

After:

```sql
qualify
    row_number() over (
        partition by
            rno,
            gar_year
        order by
            ingested_at desc
    ) = 1
```

## Development

Install editable:

```bash
pip install -e .
```

Run a compile check:

```bash
python -m py_compile src/sqlfluff_ktuft/__init__.py src/sqlfluff_ktuft/rules.py
```

Run SQLFluff rule discovery:

```bash
sqlfluff rules | grep Ktuft
```

When testing formatter behavior, run multiple fix passes and then lint. Some
SQLFluff fixes intentionally settle over more than one pass:

```bash
sqlfluff fix path/to/sql --rules "$RULES" -n
sqlfluff fix path/to/sql --rules "$RULES" -n
sqlfluff fix path/to/sql --rules "$RULES" -n
sqlfluff lint path/to/sql --rules "$RULES" -n
```
