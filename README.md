# sqlfluff-ktuft

Personal SQLFluff plugin for local SQL style experiments.

This is intentionally outside project repos. Install it in the Python
environment where SQLFluff runs:

```bash
pip install "git+https://github.com/tuftkyle/sqlfluff-ktuft.git"
```

For editable local development:

```bash
pip install -e .
```

On this machine, the local wrapper is installed into:

```bash
/home/ktuft/.local/share/sqlfluff-ktuft/venv
```

Use the wrapper:

```bash
sqlfluff-ktuft lint models/intermediate/staff/int_gar_staff_annual_clean.sql \
  --config .sqlfluff \
  --rules AL01,ST05,LT12,Ktuft_KL01,Ktuft_KL02,Ktuft_KL03,Ktuft_KL04,Ktuft_KL05,Ktuft_KL06,Ktuft_KL07,Ktuft_KL08,Ktuft_KL09,Ktuft_KL10,Ktuft_KL11,Ktuft_KL12,Ktuft_KL13,Ktuft_KL14,Ktuft_KL15,Ktuft_KL16,Ktuft_KL17,Ktuft_KL18,Ktuft_KL19 \
  -n
```

To apply fixes:

```bash
sqlfluff-ktuft fix models/intermediate/staff/int_gar_staff_annual_clean.sql \
  --config .sqlfluff \
  --rules AL01,ST05,LT12,Ktuft_KL01,Ktuft_KL02,Ktuft_KL03,Ktuft_KL04,Ktuft_KL05,Ktuft_KL06,Ktuft_KL07,Ktuft_KL08,Ktuft_KL09,Ktuft_KL10,Ktuft_KL11,Ktuft_KL12,Ktuft_KL13,Ktuft_KL14,Ktuft_KL15,Ktuft_KL16,Ktuft_KL17,Ktuft_KL18,Ktuft_KL19 \
  -n
```

Rules:

- `Ktuft_KL01` / `ktuft.from_newline`: flags `from <relation>` on the same line.
- `Ktuft_KL02` / `ktuft.join_on_trailing`: flags joins where `on` is moved to its own continuation line.
- `Ktuft_KL03` / `ktuft.join_predicate_indent`: indents join predicate lines one level deeper than the join.
- `Ktuft_KL04` / `ktuft.expand_inline_cte`: expands compact CTE bodies such as `name as (select * from ...)`.
- `Ktuft_KL05` / `ktuft.from_indent`: aligns `from` with the related `select`.
- `Ktuft_KL06` / `ktuft.from_relation_indent`: indents the relation line one level deeper than `from`.
- `Ktuft_KL07` / `ktuft.cte_inner_spacing`: keeps one blank line just inside CTE parentheses.
- `Ktuft_KL08` / `ktuft.select_target_indent`: indents top-level multi-line select targets.
- `Ktuft_KL09` / `ktuft.between_operand_layout`: splits and aligns `between` operands.
- `Ktuft_KL10` / `ktuft.clause_predicate_newline`: puts `where`, `group by`, `having`, and `qualify` predicates/columns on indented continuation lines.
- `Ktuft_KL11` / `ktuft.simple_cte_single_line`: keeps simple `select * from` CTEs on one line.
- `Ktuft_KL12` / `ktuft.long_select_list_wrap`: wraps same-line select lists only when they exceed the line limit.
- `Ktuft_KL13` / `ktuft.with_blank_line`: keeps `with` on its own line followed by one blank line.
- `Ktuft_KL14` / `ktuft.compact_select_from`: keeps short one-line select lists with their `from` clause.
- `Ktuft_KL15` / `ktuft.jinja_surrogate_key_arg_wrap`: wraps long `dbt_utils.generate_surrogate_key` argument lists.
- `Ktuft_KL16` / `ktuft.union_list_indent`: aligns compact `union` list entries with the preceding select.
- `Ktuft_KL17` / `ktuft.leading_closing_bracket_indent`: aligns leading closing brackets with their opening line.
- `Ktuft_KL18` / `ktuft.when_then_same_line`: keeps short `when ... then ...` clauses on one line.
- `Ktuft_KL19` / `ktuft.window_body_indent`: indents multiline window bodies one level under the opening line.

All custom rules are fix-compatible. The recommended personal profile combines
these custom rules with existing SQLFluff rules:

- `AL01`: require explicit `as` for table aliases.
- `ST05`: block long nested subqueries.
- `LT12`: require a final newline.

To combine with the current repo rules:

```bash
sqlfluff-ktuft lint models macros tests analyses \
  --config .sqlfluff \
  --rules AL01,ST05,LT12,Ktuft_KL01,Ktuft_KL02,Ktuft_KL03,Ktuft_KL04,Ktuft_KL05,Ktuft_KL06,Ktuft_KL07,Ktuft_KL08,Ktuft_KL09,Ktuft_KL10,Ktuft_KL11,Ktuft_KL12,Ktuft_KL13,Ktuft_KL14,Ktuft_KL15,Ktuft_KL16,Ktuft_KL17,Ktuft_KL18,Ktuft_KL19 \
  -n
```
