"""Custom SQLFluff rules for personal SQL style."""

from __future__ import annotations

import re

from sqlfluff.core.parser import (
    BaseSegment,
    KeywordSegment,
    NewlineSegment,
    SourceFix,
    WhitespaceSegment,
)
from sqlfluff.core.rules import BaseRule, LintFix, LintResult, RuleContext
from sqlfluff.core.rules.crawlers import RootOnlyCrawler, SegmentSeekerCrawler


def _raw_segments(context: RuleContext):
    return tuple(context.segment.raw_segments)


def _is_code_segment(segment) -> bool:
    return not segment.is_type(
        "whitespace",
        "newline",
        "indent",
        "dedent",
        "end_of_file",
    )


def _line_no(segment) -> int:
    return segment.pos_marker.working_line_no


def _keyword(segment, value: str) -> bool:
    return segment.is_type("keyword") and segment.raw.lower() == value


def _keyword_in(segment, values: set[str]) -> bool:
    return segment.is_type("keyword") and segment.raw.lower() in values


_JOIN_CONDITION_ANCHORS = {"on", "using"}
_BOOLEAN_OPERATORS = {"and", "or"}


def _previous_code_index(raw_segments, start_index: int) -> int | None:
    for index in range(start_index - 1, -1, -1):
        if _is_code_segment(raw_segments[index]):
            return index
    return None


def _previous_segment_index(raw_segments, start_index: int) -> int | None:
    if start_index <= 0:
        return None

    return start_index - 1


def _next_code_index(raw_segments, start_index: int) -> int | None:
    for index in range(start_index + 1, len(raw_segments)):
        if _is_code_segment(raw_segments[index]):
            return index
    return None


def _first_code_index(raw_segments) -> int | None:
    for index, segment in enumerate(raw_segments):
        if _is_code_segment(segment):
            return index

    return None


def _line_first_code_index(raw_segments, line_no: int) -> int | None:
    for index, segment in enumerate(raw_segments):
        if _line_no(segment) == line_no and _is_code_segment(segment):
            return index

    return None


def _code_indices_by_line(raw_segments):
    seen_lines = set()
    indices = []

    for index, segment in enumerate(raw_segments):
        if not _is_code_segment(segment):
            continue

        line_no = _line_no(segment)
        if line_no in seen_lines:
            continue

        seen_lines.add(line_no)
        indices.append(index)

    return indices


def _segments_between(raw_segments, start_index: int, stop_index: int):
    return raw_segments[start_index + 1 : stop_index]


def _line_indent(raw_segments, segment_index: int) -> str:
    line_no = _line_no(raw_segments[segment_index])
    line_start_index = segment_index

    for index in range(segment_index, -1, -1):
        if _line_no(raw_segments[index]) != line_no:
            break
        line_start_index = index

    prior_code_on_line = False
    for index in range(line_start_index, segment_index):
        segment = raw_segments[index]
        if segment.is_type("whitespace") and not prior_code_on_line:
            return segment.raw
        if _is_code_segment(segment):
            prior_code_on_line = True

    if not prior_code_on_line and raw_segments[segment_index].pos_marker:
        return " " * (raw_segments[segment_index].pos_marker.working_line_pos - 1)

    return ""


def _replace_or_create_line_indent(raw_segments, code_index: int, indent: str):
    edit_segments = [WhitespaceSegment(indent)] if indent else []

    for previous_index in range(code_index - 1, -1, -1):
        previous_segment = raw_segments[previous_index]
        if _line_no(previous_segment) != _line_no(raw_segments[code_index]):
            break
        if previous_segment.is_type("indent", "dedent"):
            continue
        if previous_segment.is_type("whitespace"):
            if not edit_segments:
                return [LintFix.delete(previous_segment)]

            return [
                LintFix.replace(
                    previous_segment,
                    edit_segments,
                )
            ]
        break

    return [
        LintFix.create_before(
            raw_segments[code_index],
            edit_segments,
        )
    ] if edit_segments else []


def _move_leading_boolean_operator_fixes(raw_segments, operator_index: int):
    operator_segment = raw_segments[operator_index]
    if operator_segment.raw.lower() not in _BOOLEAN_OPERATORS:
        return []

    line_no = _line_no(operator_segment)
    if _line_first_code_index(raw_segments, line_no) != operator_index:
        return []

    previous_code_index = _previous_code_index(raw_segments, operator_index)
    next_code_index = _next_code_index(raw_segments, operator_index)
    if previous_code_index is None or next_code_index is None:
        return []
    if _line_no(raw_segments[previous_code_index]) == line_no:
        return []
    if _line_no(raw_segments[next_code_index]) != line_no:
        return []
    if _keyword_in(raw_segments[previous_code_index], _JOIN_CONDITION_ANCHORS):
        return []

    fixes = [
        LintFix.create_after(
            raw_segments[previous_code_index],
            [
                WhitespaceSegment(" "),
                KeywordSegment(operator_segment.raw.lower()),
            ],
        ),
        LintFix.delete(operator_segment),
    ]
    fixes.extend(
        LintFix.delete(between_segment)
        for between_segment in _segments_between(
            raw_segments,
            operator_index,
            next_code_index,
        )
        if between_segment.is_type("whitespace")
    )
    return fixes


def _newline_with_indent(indent: str, newline_count: int = 1):
    segments = [NewlineSegment() for _ in range(newline_count)]
    if indent:
        segments.append(WhitespaceSegment(indent))

    return segments


def _matching_end_bracket_index(raw_segments, start_index: int) -> int | None:
    bracket_depth = 0

    for index in range(start_index, len(raw_segments)):
        segment = raw_segments[index]
        if segment.is_type("start_bracket"):
            bracket_depth += 1
        elif segment.is_type("end_bracket"):
            bracket_depth -= 1
            if bracket_depth == 0:
                return index

    return None


def _matching_start_bracket_index(raw_segments, end_index: int) -> int | None:
    bracket_depth = 0

    for index in range(end_index, -1, -1):
        segment = raw_segments[index]
        if segment.is_type("end_bracket"):
            bracket_depth += 1
        elif segment.is_type("start_bracket"):
            bracket_depth -= 1
            if bracket_depth == 0:
                return index

    return None


def _bracket_depth_between(raw_segments, start_index: int, stop_index: int) -> int:
    bracket_depth = 0

    for index in range(start_index + 1, stop_index):
        segment = raw_segments[index]
        if segment.is_type("start_bracket"):
            bracket_depth += 1
        elif segment.is_type("end_bracket") and bracket_depth > 0:
            bracket_depth -= 1

    return bracket_depth


def _is_cte_start_bracket(raw_segments, index: int) -> bool:
    previous_code_index = _previous_code_index(raw_segments, index)
    return (
        raw_segments[index].is_type("start_bracket")
        and previous_code_index is not None
        and _keyword(raw_segments[previous_code_index], "as")
    )


def _simple_select_star_cte_bounds(raw_segments, start_index: int):
    if not _is_cte_start_bracket(raw_segments, start_index):
        return None

    end_index = _matching_end_bracket_index(raw_segments, start_index)
    if end_index is None:
        return None

    code_indices = [
        index
        for index in range(start_index + 1, end_index)
        if _is_code_segment(raw_segments[index])
    ]
    if len(code_indices) < 4:
        return None

    select_index, star_index, from_index = code_indices[:3]
    if not (
        _keyword(raw_segments[select_index], "select")
        and raw_segments[star_index].is_type("star")
        and _keyword(raw_segments[from_index], "from")
    ):
        return None

    disallowed_keywords = {
        "where",
        "group",
        "having",
        "qualify",
        "order",
        "limit",
        "union",
        "join",
    }
    for code_index in code_indices[3:]:
        if _keyword_in(raw_segments[code_index], disallowed_keywords):
            return None

    return {
        "start": start_index,
        "end": end_index,
        "select": select_index,
        "star": star_index,
        "from": from_index,
        "relation_start": code_indices[3],
        "relation_end": code_indices[-1],
    }


def _simple_select_star_cte_bounds_for_index(raw_segments, segment_index: int):
    for index, segment in enumerate(raw_segments):
        if not segment.is_type("start_bracket"):
            continue

        bounds = _simple_select_star_cte_bounds(raw_segments, index)
        if bounds and bounds["start"] < segment_index < bounds["end"]:
            return bounds

    return None


def _nearest_prior_statement_select_index(raw_segments, start_index: int) -> int | None:
    bracket_depth = 0
    boundary_keywords = {
        "from",
        "where",
        "group",
        "having",
        "qualify",
        "order",
        "limit",
        "union",
    }

    for index in range(start_index - 1, -1, -1):
        segment = raw_segments[index]
        if segment.is_type("end_bracket"):
            bracket_depth += 1
        elif segment.is_type("start_bracket") and bracket_depth > 0:
            bracket_depth -= 1

        if bracket_depth != 0 or not segment.is_type("keyword"):
            continue

        if _keyword(segment, "select"):
            return index
        if segment.raw.lower() in boundary_keywords:
            return None

    return None


def _from_relation_end_index(raw_segments, relation_start_index: int) -> int:
    bracket_depth = 0
    boundary_keywords = {
        "where",
        "group",
        "having",
        "qualify",
        "order",
        "limit",
        "union",
        "left",
        "right",
        "inner",
        "outer",
        "full",
        "cross",
        "join",
    }
    relation_end_index = relation_start_index

    for index in range(relation_start_index, len(raw_segments)):
        segment = raw_segments[index]
        if index > relation_start_index:
            if segment.is_type("start_bracket"):
                bracket_depth += 1
            elif segment.is_type("end_bracket"):
                if bracket_depth == 0:
                    break
                bracket_depth -= 1

            if (
                bracket_depth == 0
                and segment.is_type("keyword")
                and segment.raw.lower() in boundary_keywords
            ):
                break
            if bracket_depth == 0 and segment.is_type("comma"):
                break

        if _is_code_segment(segment):
            relation_end_index = index

    return relation_end_index


def _compact_select_from_bounds(raw_segments, from_index: int, max_line_length: int = 120):
    if not _keyword(raw_segments[from_index], "from"):
        return None

    previous_code_index = _previous_code_index(raw_segments, from_index)
    select_index = _nearest_prior_statement_select_index(raw_segments, from_index)
    relation_start_index = _next_code_index(raw_segments, from_index)
    if (
        previous_code_index is None
        or select_index is None
        or relation_start_index is None
        or _line_no(raw_segments[select_index]) != _line_no(raw_segments[previous_code_index])
    ):
        return None

    relation_end_index = _from_relation_end_index(raw_segments, relation_start_index)
    select_raw = "".join(
        segment.raw
        for segment in raw_segments[select_index : previous_code_index + 1]
        if not segment.is_type("indent", "dedent")
    )
    relation_raw = "".join(
        segment.raw
        for segment in raw_segments[relation_start_index : relation_end_index + 1]
        if not segment.is_type("whitespace", "newline", "indent", "dedent")
    )
    compact_raw = f"{_line_indent(raw_segments, select_index)}{select_raw} from {relation_raw}"
    if len(compact_raw) > max_line_length:
        return None

    return {
        "select": select_index,
        "previous_code": previous_code_index,
        "from": from_index,
        "relation_start": relation_start_index,
        "relation_end": relation_end_index,
    }


def _find_raw_at_source_index(segment: BaseSegment, source_index: int):
    if not segment.segments:
        return None

    for child in segment.segments:
        if not child.pos_marker:
            continue

        source_slice = child.pos_marker.source_slice
        if source_slice.stop <= source_index:
            continue
        if child.is_raw():
            return child
        return _find_raw_at_source_index(child, source_index)

    return None


def _source_line_indent(source: str, source_index: int) -> str:
    line_start_index = source.rfind("\n", 0, source_index) + 1
    indent = []

    for char in source[line_start_index:source_index]:
        if char not in (" ", "\t"):
            break
        indent.append(char)

    return "".join(indent)


def _source_has_code_before_index(source: str, source_index: int) -> bool:
    line_start_index = source.rfind("\n", 0, source_index) + 1
    return bool(source[line_start_index:source_index].strip())


def _bracket_depths(raw_segments):
    depths = []
    depth = 0

    for segment in raw_segments:
        if segment.is_type("end_bracket") and depth > 0:
            depth -= 1

        depths.append(depth)

        if segment.is_type("start_bracket"):
            depth += 1

    return depths


def _nearest_prior_select_at_depth(raw_segments, depths, start_index: int) -> int | None:
    target_depth = depths[start_index]

    for index in range(start_index - 1, -1, -1):
        if depths[index] != target_depth:
            continue
        if _keyword(raw_segments[index], "select"):
            return index

    return None


class Rule_Ktuft_KL01(BaseRule):
    """Place the relation on the line after the `from` keyword."""

    name = "ktuft.from_newline"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    def _eval(self, context: RuleContext):
        violations = []
        raw_segments = _raw_segments(context)

        for index, segment in enumerate(raw_segments):
            if not _keyword(segment, "from"):
                continue
            if _simple_select_star_cte_bounds_for_index(raw_segments, index):
                continue
            if _compact_select_from_bounds(raw_segments, index):
                continue

            next_code_index = _next_code_index(raw_segments, index)
            if next_code_index is None:
                continue

            next_code = raw_segments[next_code_index]
            if _line_no(next_code) == _line_no(segment):
                fixes = [
                    LintFix.delete(between_segment)
                    for between_segment in _segments_between(
                        raw_segments,
                        index,
                        next_code_index,
                    )
                    if between_segment.is_type("whitespace")
                ]
                previous_code_index = _previous_code_index(raw_segments, index)
                current_line_indent = _line_indent(raw_segments, index)

                if (
                    previous_code_index is not None
                    and _line_no(raw_segments[previous_code_index]) == _line_no(segment)
                ):
                    previous_segment_index = _previous_segment_index(raw_segments, index)
                    if (
                        previous_segment_index is not None
                        and raw_segments[previous_segment_index].is_type("whitespace")
                    ):
                        fixes.append(
                            LintFix.replace(
                                raw_segments[previous_segment_index],
                                _newline_with_indent(current_line_indent),
                            )
                        )
                    else:
                        fixes.append(
                            LintFix.create_before(
                                segment,
                                _newline_with_indent(current_line_indent),
                            )
                        )

                fixes.append(
                    LintFix.create_before(
                        next_code,
                        _newline_with_indent(current_line_indent + "    "),
                    )
                )
                violations.append(
                    LintResult(
                        anchor=segment,
                        fixes=fixes,
                        description="Put the relation on the line after `from`.",
                    )
                )

        return violations or None


class Rule_Ktuft_KL02(BaseRule):
    """Keep join condition anchors in trailing `join ... on|using` form."""

    name = "ktuft.join_on_trailing"
    groups = ("all", "ktuft")
    crawl_behaviour = SegmentSeekerCrawler({"join_clause"})
    is_fix_compatible = True

    def _eval(self, context: RuleContext):
        violations = []
        raw_segments = _raw_segments(context)

        for index, segment in enumerate(raw_segments):
            if not _keyword_in(segment, _JOIN_CONDITION_ANCHORS):
                continue

            previous_code_index = _previous_code_index(raw_segments, index)
            if previous_code_index is None:
                continue

            previous_code = raw_segments[previous_code_index]
            if _line_no(previous_code) == _line_no(segment):
                continue

            next_code_index = _next_code_index(raw_segments, index)
            on_line_indent = _line_indent(raw_segments, index)
            first_code_index = _first_code_index(raw_segments)
            predicate_indent = (
                _line_indent(raw_segments, first_code_index) + "    "
                if first_code_index is not None
                else on_line_indent
            )
            fixes = [
                LintFix.delete(between_segment)
                for between_segment in _segments_between(
                    raw_segments,
                    previous_code_index,
                    index,
                )
                if between_segment.is_type("whitespace", "newline")
            ]
            fixes.append(
                LintFix.create_after(
                    previous_code,
                    [
                        WhitespaceSegment(" "),
                    ],
                )
            )
            if (
                next_code_index is not None
                and _line_no(raw_segments[next_code_index]) == _line_no(segment)
            ):
                fixes.extend(
                    LintFix.delete(between_segment)
                    for between_segment in _segments_between(
                        raw_segments,
                        index,
                        next_code_index,
                    )
                    if between_segment.is_type("whitespace")
                )
                fixes.append(
                    LintFix.create_before(
                        raw_segments[next_code_index],
                        _newline_with_indent(predicate_indent),
                    )
                )

            violations.append(
                LintResult(
                    anchor=segment,
                    fixes=fixes,
                    description=(
                        "Keep join condition anchors on the same line as "
                        "the joined relation."
                    ),
                )
            )

        return violations or None


class Rule_Ktuft_KL03(BaseRule):
    """Indent join predicate lines one level deeper than the join."""

    name = "ktuft.join_predicate_indent"
    groups = ("all", "ktuft")
    crawl_behaviour = SegmentSeekerCrawler({"join_clause"})
    is_fix_compatible = True

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        first_code_index = _first_code_index(raw_segments)
        if first_code_index is None:
            return None

        predicate_indent = _line_indent(raw_segments, first_code_index) + "    "
        violations = []
        seen_lines = set()

        for index, segment in enumerate(raw_segments):
            if not _keyword_in(segment, _JOIN_CONDITION_ANCHORS):
                continue

            previous_code_index = _previous_code_index(raw_segments, index)
            if (
                previous_code_index is None
                or _line_no(raw_segments[previous_code_index]) != _line_no(segment)
            ):
                continue

            next_code_index = _next_code_index(raw_segments, index)
            if next_code_index is None:
                continue

            next_code = raw_segments[next_code_index]
            fixes = []
            if _line_no(raw_segments[next_code_index]) == _line_no(segment):
                fixes.extend(
                    LintFix.delete(between_segment)
                    for between_segment in _segments_between(
                        raw_segments,
                        index,
                        next_code_index,
                    )
                    if between_segment.is_type("whitespace")
                )
                fixes.append(
                    LintFix.create_before(
                        next_code,
                        _newline_with_indent(predicate_indent),
                    )
                )
            elif _line_indent(raw_segments, next_code_index) != predicate_indent:
                fixes.extend(
                    _replace_or_create_line_indent(
                        raw_segments,
                        next_code_index,
                        predicate_indent,
                    )
                )

            if fixes:
                violations.append(
                    LintResult(
                        anchor=next_code,
                        fixes=fixes,
                        description=(
                            "Put the first join predicate on the line after `on`."
                        ),
                    )
                )
                continue

            for predicate_index in range(next_code_index, len(raw_segments)):
                predicate_segment = raw_segments[predicate_index]
                predicate_line_no = _line_no(predicate_segment)

                if predicate_line_no in seen_lines:
                    continue
                if not _is_code_segment(predicate_segment):
                    continue

                seen_lines.add(predicate_line_no)
                boolean_operator_fixes = _move_leading_boolean_operator_fixes(
                    raw_segments,
                    predicate_index,
                )
                if boolean_operator_fixes:
                    violations.append(
                        LintResult(
                            anchor=predicate_segment,
                            fixes=boolean_operator_fixes,
                            description=(
                                "Keep join boolean operators trailing on "
                                "the preceding predicate line."
                            ),
                        )
                    )
                    continue

                if _line_indent(raw_segments, predicate_index) == predicate_indent:
                    continue

                fixes = _replace_or_create_line_indent(
                    raw_segments,
                    predicate_index,
                    predicate_indent,
                )
                if fixes:
                    violations.append(
                        LintResult(
                            anchor=predicate_segment,
                            fixes=fixes,
                            description=(
                                "Indent join predicate lines one level deeper "
                                "than the join."
                            ),
                        )
                    )

        return violations or None


class Rule_Ktuft_KL04(BaseRule):
    """Expand compact CTE bodies that start on the `as (` line."""

    name = "ktuft.expand_inline_cte"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        violations = []

        for index, segment in enumerate(raw_segments):
            if not segment.is_type("start_bracket"):
                continue
            if _simple_select_star_cte_bounds(raw_segments, index):
                continue

            previous_code_index = _previous_code_index(raw_segments, index)
            next_code_index = _next_code_index(raw_segments, index)
            if (
                previous_code_index is None
                or next_code_index is None
                or not _keyword(raw_segments[previous_code_index], "as")
                or not _keyword(raw_segments[next_code_index], "select")
                or _line_no(raw_segments[next_code_index]) != _line_no(segment)
            ):
                continue

            cte_indent = _line_indent(raw_segments, index)
            body_indent = cte_indent + "    "
            fixes = [
                LintFix.delete(between_segment)
                for between_segment in _segments_between(
                    raw_segments,
                    index,
                    next_code_index,
                )
                if between_segment.is_type("whitespace")
            ]
            fixes.append(
                LintFix.create_before(
                    raw_segments[next_code_index],
                    _newline_with_indent(body_indent),
                )
            )

            end_bracket_index = _matching_end_bracket_index(raw_segments, index)
            if end_bracket_index is not None:
                previous_inner_code_index = _previous_code_index(
                    raw_segments,
                    end_bracket_index,
                )
                if (
                    previous_inner_code_index is not None
                    and _line_no(raw_segments[previous_inner_code_index])
                    == _line_no(raw_segments[end_bracket_index])
                ):
                    fixes.extend(
                        LintFix.delete(between_segment)
                        for between_segment in _segments_between(
                            raw_segments,
                            previous_inner_code_index,
                            end_bracket_index,
                        )
                        if between_segment.is_type("whitespace")
                    )
                    fixes.append(
                        LintFix.create_before(
                            raw_segments[end_bracket_index],
                            _newline_with_indent(cte_indent),
                        )
                    )

            violations.append(
                LintResult(
                    anchor=segment,
                    fixes=fixes,
                    description="Expand compact CTE bodies onto separate lines.",
                )
            )

        return violations or None


class Rule_Ktuft_KL05(BaseRule):
    """Align the `from` keyword with its `select` keyword."""

    name = "ktuft.from_indent"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    _clause_boundaries = {
        "with",
        "select",
        "from",
        "where",
        "group",
        "having",
        "qualify",
        "order",
        "limit",
        "union",
    }

    def _nearest_prior_select_index(self, raw_segments, from_index: int) -> int | None:
        bracket_depth = 0

        for index in range(from_index - 1, -1, -1):
            segment = raw_segments[index]
            if segment.is_type("end_bracket"):
                bracket_depth += 1
            elif segment.is_type("start_bracket"):
                bracket_depth -= 1

            if bracket_depth > 0 or not segment.is_type("keyword"):
                continue

            keyword = segment.raw.lower()
            if keyword == "select":
                return index
            if keyword in self._clause_boundaries:
                return None

        return None

    def _eval(self, context: RuleContext):
        violations = []
        raw_segments = _raw_segments(context)

        for index, segment in enumerate(raw_segments):
            if not _keyword(segment, "from"):
                continue
            if _simple_select_star_cte_bounds_for_index(raw_segments, index):
                continue
            if _compact_select_from_bounds(raw_segments, index):
                continue

            select_index = self._nearest_prior_select_index(raw_segments, index)
            if select_index is None:
                continue

            if _line_no(raw_segments[select_index]) == _line_no(segment):
                continue

            expected_indent = _line_indent(raw_segments, select_index)
            if _line_indent(raw_segments, index) == expected_indent:
                continue

            fixes = _replace_or_create_line_indent(
                raw_segments,
                index,
                expected_indent,
            )
            if fixes:
                violations.append(
                    LintResult(
                        anchor=segment,
                        fixes=fixes,
                        description="Align `from` with the related `select`.",
                    )
                )

        return violations or None


class Rule_Ktuft_KL06(BaseRule):
    """Indent the relation line one level deeper than `from`."""

    name = "ktuft.from_relation_indent"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    def _eval(self, context: RuleContext):
        violations = []
        raw_segments = _raw_segments(context)

        for index, segment in enumerate(raw_segments):
            if not _keyword(segment, "from"):
                continue
            if _simple_select_star_cte_bounds_for_index(raw_segments, index):
                continue
            if _compact_select_from_bounds(raw_segments, index):
                continue

            next_code_index = _next_code_index(raw_segments, index)
            if next_code_index is None:
                continue

            next_code = raw_segments[next_code_index]
            if _line_no(next_code) == _line_no(segment):
                continue

            expected_indent = _line_indent(raw_segments, index) + "    "
            if _line_indent(raw_segments, next_code_index) == expected_indent:
                continue

            fixes = _replace_or_create_line_indent(
                raw_segments,
                next_code_index,
                expected_indent,
            )
            if fixes:
                violations.append(
                    LintResult(
                        anchor=next_code,
                        fixes=fixes,
                        description=(
                            "Indent the relation line one level deeper than `from`."
                        ),
                    )
                )

        return violations or None


class Rule_Ktuft_KL07(BaseRule):
    """Keep one blank line immediately inside CTE parentheses."""

    name = "ktuft.cte_inner_spacing"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    def _eval(self, context: RuleContext):
        violations = []
        raw_segments = _raw_segments(context)

        for index, segment in enumerate(raw_segments):
            if not _is_cte_start_bracket(raw_segments, index):
                continue
            if _simple_select_star_cte_bounds(raw_segments, index):
                continue

            cte_indent = _line_indent(raw_segments, index)
            body_indent = cte_indent + "    "
            next_code_index = _next_code_index(raw_segments, index)
            if (
                next_code_index is not None
                and _line_no(raw_segments[next_code_index]) > _line_no(segment)
                and (
                    _line_no(raw_segments[next_code_index]) != _line_no(segment) + 2
                    or _line_indent(raw_segments, next_code_index) != body_indent
                )
            ):
                fixes = [
                    LintFix.delete(between_segment)
                    for between_segment in _segments_between(
                        raw_segments,
                        index,
                        next_code_index,
                    )
                    if between_segment.is_type("whitespace", "newline")
                ]
                fixes.append(
                    LintFix.create_before(
                        raw_segments[next_code_index],
                        _newline_with_indent(body_indent, newline_count=2),
                    )
                )
                violations.append(
                    LintResult(
                        anchor=raw_segments[next_code_index],
                        fixes=fixes,
                        description=(
                            "Keep one blank line after opening CTE parentheses."
                        ),
                    )
                )

            end_bracket_index = _matching_end_bracket_index(raw_segments, index)
            if end_bracket_index is None:
                continue

            previous_code_index = _previous_code_index(raw_segments, end_bracket_index)
            if (
                previous_code_index is not None
                and _line_no(raw_segments[end_bracket_index])
                > _line_no(raw_segments[previous_code_index])
                and (
                    _line_no(raw_segments[end_bracket_index])
                    != _line_no(raw_segments[previous_code_index]) + 2
                    or _line_indent(raw_segments, end_bracket_index) != cte_indent
                )
            ):
                fixes = [
                    LintFix.delete(between_segment)
                    for between_segment in _segments_between(
                        raw_segments,
                        previous_code_index,
                        end_bracket_index,
                    )
                    if between_segment.is_type("whitespace", "newline")
                ]
                fixes.append(
                    LintFix.create_before(
                        raw_segments[end_bracket_index],
                        _newline_with_indent(cte_indent, newline_count=2),
                    )
                )
                violations.append(
                    LintResult(
                        anchor=raw_segments[end_bracket_index],
                        fixes=fixes,
                        description=(
                            "Keep one blank line before closing CTE parentheses."
                        ),
                    )
                )

        return violations or None


class Rule_Ktuft_KL08(BaseRule):
    """Indent multi-line select targets one level deeper than `select`."""

    name = "ktuft.select_target_indent"
    groups = ("all", "ktuft")
    crawl_behaviour = SegmentSeekerCrawler({"select_clause"})
    is_fix_compatible = True

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        select_index = _first_code_index(raw_segments)
        if select_index is None or not _keyword(raw_segments[select_index], "select"):
            return None

        select_line_no = _line_no(raw_segments[select_index])
        target_indent = _line_indent(raw_segments, select_index) + "    "
        violations = []

        for code_index in _code_indices_by_line(raw_segments):
            if _line_no(raw_segments[code_index]) <= select_line_no:
                continue

            if _bracket_depth_between(raw_segments, select_index, code_index) > 0:
                continue

            previous_code_index = _previous_code_index(raw_segments, code_index)
            if previous_code_index is None:
                continue

            previous_code = raw_segments[previous_code_index]
            if not (
                _keyword(previous_code, "select")
                or previous_code.is_type("comma")
            ):
                continue

            if _line_indent(raw_segments, code_index) == target_indent:
                continue

            fixes = _replace_or_create_line_indent(
                raw_segments,
                code_index,
                target_indent,
            )
            if fixes:
                violations.append(
                    LintResult(
                        anchor=raw_segments[code_index],
                        fixes=fixes,
                        description=(
                            "Indent multi-line select targets one level deeper "
                            "than `select`."
                        ),
                    )
                )

        return violations or None


class Rule_Ktuft_KL09(BaseRule):
    """Split `between` range operands onto aligned continuation lines."""

    name = "ktuft.between_operand_layout"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    _clause_boundaries = {
        "where",
        "group",
        "having",
        "qualify",
        "order",
        "limit",
        "union",
        "left",
        "right",
        "inner",
        "outer",
        "full",
        "cross",
        "join",
    }

    def _between_and_index(self, raw_segments, between_index: int) -> int | None:
        bracket_depth = 0

        for index in range(between_index + 1, len(raw_segments)):
            segment = raw_segments[index]
            if segment.is_type("start_bracket"):
                bracket_depth += 1
            elif segment.is_type("end_bracket"):
                bracket_depth -= 1

            if bracket_depth != 0 or not segment.is_type("keyword"):
                continue

            keyword = segment.raw.lower()
            if keyword == "and":
                return index
            if keyword in self._clause_boundaries:
                return None

        return None

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        violations = []

        for index, segment in enumerate(raw_segments):
            if not _keyword(segment, "between"):
                continue

            operand_indent = _line_indent(raw_segments, index) + "    "
            lower_index = _next_code_index(raw_segments, index)
            and_index = self._between_and_index(raw_segments, index)
            if lower_index is None or and_index is None:
                continue

            if _line_no(raw_segments[lower_index]) == _line_no(segment):
                fixes = [
                    LintFix.delete(between_segment)
                    for between_segment in _segments_between(
                        raw_segments,
                        index,
                        lower_index,
                    )
                    if between_segment.is_type("whitespace")
                ]
                fixes.append(
                    LintFix.create_before(
                        raw_segments[lower_index],
                        _newline_with_indent(operand_indent),
                    )
                )
                violations.append(
                    LintResult(
                        anchor=raw_segments[lower_index],
                        fixes=fixes,
                        description="Put the lower `between` operand on its own line.",
                    )
                )
            elif _line_indent(raw_segments, lower_index) != operand_indent:
                fixes = _replace_or_create_line_indent(
                    raw_segments,
                    lower_index,
                    operand_indent,
                )
                if fixes:
                    violations.append(
                        LintResult(
                            anchor=raw_segments[lower_index],
                            fixes=fixes,
                            description="Align `between` operands.",
                        )
                    )

            upper_index = _next_code_index(raw_segments, and_index)
            if upper_index is None:
                continue

            if _line_no(raw_segments[upper_index]) == _line_no(raw_segments[and_index]):
                fixes = [
                    LintFix.delete(between_segment)
                    for between_segment in _segments_between(
                        raw_segments,
                        and_index,
                        upper_index,
                    )
                    if between_segment.is_type("whitespace")
                ]
                fixes.append(
                    LintFix.create_before(
                        raw_segments[upper_index],
                        _newline_with_indent(operand_indent),
                    )
                )
                violations.append(
                    LintResult(
                        anchor=raw_segments[upper_index],
                        fixes=fixes,
                        description="Put the upper `between` operand on its own line.",
                    )
                )
            elif _line_indent(raw_segments, upper_index) != operand_indent:
                fixes = _replace_or_create_line_indent(
                    raw_segments,
                    upper_index,
                    operand_indent,
                )
                if fixes:
                    violations.append(
                        LintResult(
                            anchor=raw_segments[upper_index],
                            fixes=fixes,
                            description="Align `between` operands.",
                        )
                    )

        return violations or None


class Rule_Ktuft_KL10(BaseRule):
    """Put clause predicates and grouping columns on indented continuation lines."""

    name = "ktuft.clause_predicate_newline"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    _simple_clause_keywords = {"where", "having", "qualify"}
    _boundary_keywords = {
        "from",
        "where",
        "group",
        "having",
        "qualify",
        "order",
        "limit",
        "union",
        "left",
        "right",
        "inner",
        "outer",
        "full",
        "cross",
        "join",
    }

    def _is_clause_start(self, raw_segments, index: int) -> bool:
        segment = raw_segments[index]
        if _keyword_in(segment, self._simple_clause_keywords):
            return True

        if not _keyword(segment, "group"):
            return False

        next_code_index = _next_code_index(raw_segments, index)
        return next_code_index is not None and _keyword(
            raw_segments[next_code_index],
            "by",
        )

    def _clause_value_start_index(self, raw_segments, index: int) -> int | None:
        if _keyword(raw_segments[index], "group"):
            by_index = _next_code_index(raw_segments, index)
            if by_index is None:
                return None
            return _next_code_index(raw_segments, by_index)

        return _next_code_index(raw_segments, index)

    def _clause_anchor_index(self, raw_segments, index: int) -> int:
        if _keyword(raw_segments[index], "group"):
            by_index = _next_code_index(raw_segments, index)
            if by_index is not None and _keyword(raw_segments[by_index], "by"):
                return by_index

        return index

    def _clause_end_index(self, raw_segments, start_index: int) -> int:
        bracket_depth = 0

        for index in range(start_index + 1, len(raw_segments)):
            segment = raw_segments[index]
            if segment.is_type("start_bracket"):
                bracket_depth += 1
            elif segment.is_type("end_bracket"):
                if bracket_depth == 0:
                    return index
                bracket_depth -= 1

            if (
                bracket_depth == 0
                and segment.is_type("keyword")
                and segment.raw.lower() in self._boundary_keywords
            ):
                return index

        return len(raw_segments)

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        violations = []

        for index, segment in enumerate(raw_segments):
            if not self._is_clause_start(raw_segments, index):
                continue

            value_start_index = self._clause_value_start_index(raw_segments, index)
            if value_start_index is None:
                continue

            clause_indent = _line_indent(raw_segments, index)
            value_indent = clause_indent + "    "
            clause_anchor_index = self._clause_anchor_index(raw_segments, index)
            clause_end_index = self._clause_end_index(raw_segments, index)
            first_value = raw_segments[value_start_index]

            if _line_no(first_value) == _line_no(segment):
                fixes = [
                    LintFix.delete(between_segment)
                    for between_segment in _segments_between(
                        raw_segments,
                        clause_anchor_index,
                        value_start_index,
                    )
                    if between_segment.is_type("whitespace")
                ]
                fixes.append(
                    LintFix.create_before(
                        first_value,
                        _newline_with_indent(value_indent),
                    )
                )
                violations.append(
                    LintResult(
                        anchor=first_value,
                        fixes=fixes,
                        description=(
                            "Put clause predicates and grouping columns on "
                            "indented continuation lines."
                        ),
                    )
                )
                continue

            seen_lines = set()
            for code_index in range(value_start_index, clause_end_index):
                code_segment = raw_segments[code_index]
                if not _is_code_segment(code_segment):
                    continue

                line_no = _line_no(code_segment)
                if line_no in seen_lines:
                    continue

                seen_lines.add(line_no)
                if _line_indent(raw_segments, code_index).startswith(value_indent):
                    continue

                fixes = _replace_or_create_line_indent(
                    raw_segments,
                    code_index,
                    value_indent,
                )
                if fixes:
                    violations.append(
                        LintResult(
                            anchor=code_segment,
                            fixes=fixes,
                            description=(
                                "Indent clause predicates and grouping columns."
                            ),
                        )
                    )

        return violations or None


class Rule_Ktuft_KL11(BaseRule):
    """Keep simple `select * from` CTEs on one line."""

    name = "ktuft.simple_cte_single_line"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        violations = []

        for index, segment in enumerate(raw_segments):
            bounds = _simple_select_star_cte_bounds(raw_segments, index)
            if not bounds:
                continue

            if _line_no(raw_segments[bounds["start"]]) == _line_no(
                raw_segments[bounds["end"]]
            ):
                continue

            fixes = []
            for start, stop in (
                (bounds["start"], bounds["select"]),
                (bounds["star"], bounds["from"]),
                (bounds["from"], bounds["relation_start"]),
                (bounds["relation_end"], bounds["end"]),
            ):
                fixes.extend(
                    LintFix.delete(between_segment)
                    for between_segment in _segments_between(raw_segments, start, stop)
                    if between_segment.is_type("whitespace", "newline")
                )

            fixes.append(
                LintFix.create_before(
                    raw_segments[bounds["from"]],
                    [WhitespaceSegment(" ")],
                )
            )
            fixes.append(
                LintFix.create_before(
                    raw_segments[bounds["relation_start"]],
                    [WhitespaceSegment(" ")],
                )
            )
            violations.append(
                LintResult(
                    anchor=segment,
                    fixes=fixes,
                    description="Keep simple `select * from` CTEs on one line.",
                )
            )

        return violations or None


class Rule_Ktuft_KL12(BaseRule):
    """Wrap only over-length same-line select lists."""

    name = "ktuft.long_select_list_wrap"
    groups = ("all", "ktuft")
    crawl_behaviour = SegmentSeekerCrawler({"select_clause"})
    is_fix_compatible = True
    max_line_length = 120

    def _line_end_position(self, raw_segments, line_no: int) -> int:
        end_position = 0
        for segment in raw_segments:
            if _line_no(segment) != line_no or not segment.pos_marker:
                continue

            raw_length = len(segment.raw)
            if raw_length:
                end_position = max(
                    end_position,
                    segment.pos_marker.working_line_pos + raw_length - 1,
                )

        return end_position

    def _top_level_comma_indices(self, raw_segments, select_index: int):
        comma_indices = []
        bracket_depth = 0

        for index in range(select_index + 1, len(raw_segments)):
            segment = raw_segments[index]
            if segment.is_type("start_bracket"):
                bracket_depth += 1
            elif segment.is_type("end_bracket") and bracket_depth > 0:
                bracket_depth -= 1
            elif segment.is_type("comma") and bracket_depth == 0:
                comma_indices.append(index)

        return comma_indices

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        select_index = _first_code_index(raw_segments)
        if select_index is None or not _keyword(raw_segments[select_index], "select"):
            return None

        select_line_no = _line_no(raw_segments[select_index])
        if self._line_end_position(raw_segments, select_line_no) <= self.max_line_length:
            return None

        comma_indices = self._top_level_comma_indices(raw_segments, select_index)
        if not comma_indices:
            return None

        target_indent = _line_indent(raw_segments, select_index) + "    "
        first_target_index = _next_code_index(raw_segments, select_index)
        if first_target_index is None:
            return None

        fixes = []
        if _line_no(raw_segments[first_target_index]) == select_line_no:
            fixes.extend(
                LintFix.delete(between_segment)
                for between_segment in _segments_between(
                    raw_segments,
                    select_index,
                    first_target_index,
                )
                if between_segment.is_type("whitespace")
            )
            fixes.append(
                LintFix.create_before(
                    raw_segments[first_target_index],
                    _newline_with_indent(target_indent),
                )
            )

        for comma_index in comma_indices:
            next_code_index = _next_code_index(raw_segments, comma_index)
            if (
                next_code_index is None
                or _line_no(raw_segments[next_code_index]) != select_line_no
            ):
                continue

            fixes.extend(
                LintFix.delete(between_segment)
                for between_segment in _segments_between(
                    raw_segments,
                    comma_index,
                    next_code_index,
                )
                if between_segment.is_type("whitespace")
            )
            fixes.append(
                LintFix.create_before(
                    raw_segments[next_code_index],
                    _newline_with_indent(target_indent),
                )
            )

        if not fixes:
            return None

        return LintResult(
            anchor=raw_segments[select_index],
            fixes=fixes,
            description="Wrap over-length same-line select lists.",
        )


class Rule_Ktuft_KL13(BaseRule):
    """Put `with` on its own line followed by one blank line."""

    name = "ktuft.with_blank_line"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        violations = []

        for index, segment in enumerate(raw_segments):
            if not _keyword(segment, "with"):
                continue

            next_code_index = _next_code_index(raw_segments, index)
            if next_code_index is None:
                continue

            next_code = raw_segments[next_code_index]
            if _line_no(next_code) == _line_no(segment) + 2:
                continue

            fixes = [
                LintFix.delete(between_segment)
                for between_segment in _segments_between(
                    raw_segments,
                    index,
                    next_code_index,
                )
                if between_segment.is_type("whitespace", "newline")
            ]
            fixes.append(
                LintFix.create_before(
                    next_code,
                    _newline_with_indent("", newline_count=2),
                )
            )
            violations.append(
                LintResult(
                    anchor=segment,
                    fixes=fixes,
                    description="Put `with` on its own line followed by one blank line.",
                )
            )

        return violations or None


class Rule_Ktuft_KL14(BaseRule):
    """Keep short one-line select lists with their `from` clause."""

    name = "ktuft.compact_select_from"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True
    max_line_length = 120

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        violations = []

        for index, segment in enumerate(raw_segments):
            bounds = _compact_select_from_bounds(
                raw_segments,
                index,
                max_line_length=self.max_line_length,
            )
            if not bounds:
                continue

            if (
                _line_no(raw_segments[bounds["from"]])
                == _line_no(raw_segments[bounds["select"]])
                and _line_no(raw_segments[bounds["relation_start"]])
                == _line_no(raw_segments[bounds["select"]])
            ):
                continue

            fixes = []
            for start, stop in (
                (bounds["previous_code"], bounds["from"]),
                (bounds["from"], bounds["relation_start"]),
            ):
                fixes.extend(
                    LintFix.delete(between_segment)
                    for between_segment in _segments_between(raw_segments, start, stop)
                    if between_segment.is_type("whitespace", "newline")
                )

            fixes.append(
                LintFix.create_before(
                    raw_segments[bounds["from"]],
                    [WhitespaceSegment(" ")],
                )
            )
            fixes.append(
                LintFix.create_before(
                    raw_segments[bounds["relation_start"]],
                    [WhitespaceSegment(" ")],
                )
            )
            violations.append(
                LintResult(
                    anchor=segment,
                    fixes=fixes,
                    description=(
                        "Keep short one-line select lists with their `from` clause."
                    ),
                )
            )

        return violations or None


class Rule_Ktuft_KL15(BaseRule):
    """Wrap long dbt surrogate-key macro argument lists."""

    name = "ktuft.jinja_surrogate_key_arg_wrap"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    targets_templated = True
    is_fix_compatible = True
    max_line_length = 120

    _surrogate_key_pattern = re.compile(
        r"^\{\{\s*dbt_utils\.generate_surrogate_key\(\[(?P<items>.*?)\]\)\s*\}\}$",
        re.DOTALL,
    )

    def _source_line_length(self, source: str, source_index: int) -> int:
        line_start_index = source.rfind("\n", 0, source_index) + 1
        line_end_index = source.find("\n", source_index)
        if line_end_index == -1:
            line_end_index = len(source)

        return line_end_index - line_start_index

    def _wrapped_macro(self, stripped: str, indent: str) -> str | None:
        match = self._surrogate_key_pattern.match(stripped)
        if not match:
            return None

        items = [
            item.strip()
            for item in match.group("items").split(",")
            if item.strip()
        ]
        if len(items) < 2:
            return None

        item_indent = indent + "    "
        item_lines = [
            f"{item_indent}{item}," for item in items[:-1]
        ] + [
            f"{item_indent}{items[-1]}"
        ]

        return "\n".join(
            [
                "{{ dbt_utils.generate_surrogate_key([",
                *item_lines,
                f"{indent}]) }}}}",
            ]
        )

    def _eval(self, context: RuleContext):
        if not context.templated_file:
            return []

        assert context.segment.pos_marker
        if context.segment.pos_marker.is_literal():
            return []

        source = context.templated_file.source_str
        results = []

        for raw_slice in context.templated_file.raw_sliced:
            if raw_slice.slice_type not in ("templated", "block_start", "block_end"):
                continue

            stripped = raw_slice.raw.strip()
            if (
                not stripped.startswith("{{")
                or not stripped.endswith("}}")
                or "dbt_utils.generate_surrogate_key([" not in stripped
            ):
                continue

            if (
                "\n" not in stripped
                and self._source_line_length(source, raw_slice.source_idx)
                    <= self.max_line_length
            ):
                continue

            indent = _source_line_indent(source, raw_slice.source_idx)
            macro_indent = (
                indent + "    "
                if _source_has_code_before_index(source, raw_slice.source_idx)
                else indent
            )
            fixed = self._wrapped_macro(stripped, macro_indent)
            if fixed is None or fixed == stripped:
                continue

            raw_segment = _find_raw_at_source_index(
                context.segment,
                raw_slice.source_idx,
            )
            if raw_segment is None or raw_segment.source_fixes:
                continue

            position = raw_slice.raw.find(stripped[0])
            source_fixes = [
                SourceFix(
                    fixed,
                    slice(
                        raw_slice.source_idx + position,
                        raw_slice.source_idx + position + len(stripped),
                    ),
                    raw_segment.pos_marker.templated_slice,
                )
            ]

            results.append(
                LintResult(
                    anchor=raw_segment,
                    fixes=[
                        LintFix.replace(
                            raw_segment,
                            [raw_segment.edit(source_fixes=source_fixes)],
                        )
                    ],
                    description=(
                        "Wrap long dbt_utils.generate_surrogate_key argument lists."
                    ),
                )
            )

        return results


class Rule_Ktuft_KL16(BaseRule):
    """Align `union` list entries with the preceding select."""

    name = "ktuft.union_list_indent"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    def _next_select_after_union(self, raw_segments, union_index: int) -> int | None:
        next_code_index = _next_code_index(raw_segments, union_index)
        if next_code_index is None:
            return None

        if _keyword(raw_segments[next_code_index], "all"):
            return _next_code_index(raw_segments, next_code_index)

        return next_code_index

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        depths = _bracket_depths(raw_segments)
        violations = []

        for index, segment in enumerate(raw_segments):
            if not _keyword(segment, "union"):
                continue

            prior_select_index = _nearest_prior_select_at_depth(
                raw_segments,
                depths,
                index,
            )
            if prior_select_index is None:
                continue

            expected_indent = _line_indent(raw_segments, prior_select_index)
            fixes = []

            if _line_indent(raw_segments, index) != expected_indent:
                fixes.extend(
                    _replace_or_create_line_indent(
                        raw_segments,
                        index,
                        expected_indent,
                    )
                )

            next_select_index = self._next_select_after_union(raw_segments, index)
            if (
                next_select_index is not None
                and _keyword(raw_segments[next_select_index], "select")
                and _line_indent(raw_segments, next_select_index) != expected_indent
            ):
                fixes.extend(
                    _replace_or_create_line_indent(
                        raw_segments,
                        next_select_index,
                        expected_indent,
                    )
                )

            if fixes:
                violations.append(
                    LintResult(
                        anchor=segment,
                        fixes=fixes,
                        description=(
                            "Align `union` list entries with the preceding select."
                        ),
                    )
                )

        return violations or None


class Rule_Ktuft_KL17(BaseRule):
    """Align leading closing brackets with their opening line."""

    name = "ktuft.leading_closing_bracket_indent"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        violations = []

        for index, segment in enumerate(raw_segments):
            if not segment.is_type("end_bracket"):
                continue

            if _line_first_code_index(raw_segments, _line_no(segment)) != index:
                continue

            start_index = _matching_start_bracket_index(raw_segments, index)
            if start_index is None:
                continue

            if _line_no(raw_segments[start_index]) == _line_no(segment):
                continue

            start_line_first_code_index = _line_first_code_index(
                raw_segments,
                _line_no(raw_segments[start_index]),
            )
            if start_line_first_code_index is None:
                continue

            expected_indent = _line_indent(raw_segments, start_line_first_code_index)
            if _line_indent(raw_segments, index) == expected_indent:
                continue

            fixes = _replace_or_create_line_indent(
                raw_segments,
                index,
                expected_indent,
            )
            if fixes:
                violations.append(
                    LintResult(
                        anchor=segment,
                        fixes=fixes,
                        description=(
                            "Align leading closing brackets with their opening line."
                        ),
                    )
                )

        return violations or None


class Rule_Ktuft_KL18(BaseRule):
    """Keep short `when ... then ...` clauses on one line."""

    name = "ktuft.when_then_same_line"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True
    max_line_length = 120

    def _line_code_raw(self, raw_segments, line_no: int) -> str:
        return "".join(
            segment.raw
            for segment in raw_segments
            if _line_no(segment) == line_no
            and not segment.is_type("indent", "dedent", "newline")
        )

    def _line_has_keyword(self, raw_segments, line_no: int, keyword: str) -> bool:
        return any(
            _keyword(segment, keyword)
            for segment in raw_segments
            if _line_no(segment) == line_no
        )

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        violations = []

        for index, segment in enumerate(raw_segments):
            if not _keyword(segment, "then"):
                continue

            line_no = _line_no(segment)
            if _line_first_code_index(raw_segments, line_no) != index:
                continue

            previous_code_index = _previous_code_index(raw_segments, index)
            if previous_code_index is None:
                continue

            previous_line_no = _line_no(raw_segments[previous_code_index])
            if previous_line_no == line_no:
                continue
            if not self._line_has_keyword(raw_segments, previous_line_no, "when"):
                continue

            combined_line = (
                self._line_code_raw(raw_segments, previous_line_no).rstrip()
                + " "
                + self._line_code_raw(raw_segments, line_no).strip()
            )
            if len(combined_line) > self.max_line_length:
                continue

            fixes = [
                LintFix.delete(between_segment)
                for between_segment in _segments_between(
                    raw_segments,
                    previous_code_index,
                    index,
                )
                if between_segment.is_type("whitespace", "newline")
            ]
            fixes.append(
                LintFix.create_before(
                    segment,
                    [WhitespaceSegment(" ")],
                )
            )

            violations.append(
                LintResult(
                    anchor=segment,
                    fixes=fixes,
                    description="Keep short `when ... then ...` clauses on one line.",
                )
            )

        return violations or None


class Rule_Ktuft_KL19(BaseRule):
    """Indent multiline window bodies one level under the opening line."""

    name = "ktuft.window_body_indent"
    groups = ("all", "ktuft")
    crawl_behaviour = RootOnlyCrawler()
    is_fix_compatible = True

    def _is_window_start_bracket(self, raw_segments, index: int) -> bool:
        previous_code_index = _previous_code_index(raw_segments, index)
        return (
            raw_segments[index].is_type("start_bracket")
            and previous_code_index is not None
            and _keyword(raw_segments[previous_code_index], "over")
        )

    def _body_line_first_code_indices(self, raw_segments, start_index: int, end_index: int):
        seen_lines = set()
        indices = []
        start_line_no = _line_no(raw_segments[start_index])
        end_line_no = _line_no(raw_segments[end_index])

        for index in range(start_index + 1, end_index):
            segment = raw_segments[index]
            if not _is_code_segment(segment):
                continue

            line_no = _line_no(segment)
            if (
                line_no in seen_lines
                or line_no == start_line_no
                or line_no == end_line_no
            ):
                continue

            seen_lines.add(line_no)
            indices.append(index)

        return indices

    def _eval(self, context: RuleContext):
        raw_segments = _raw_segments(context)
        violations = []

        for index, segment in enumerate(raw_segments):
            if not self._is_window_start_bracket(raw_segments, index):
                continue

            end_index = _matching_end_bracket_index(raw_segments, index)
            if end_index is None:
                continue

            body_indices = self._body_line_first_code_indices(
                raw_segments,
                index,
                end_index,
            )
            if not body_indices:
                continue

            opening_line_first_code_index = _line_first_code_index(
                raw_segments,
                _line_no(segment),
            )
            if opening_line_first_code_index is None:
                continue

            opening_indent = _line_indent(raw_segments, opening_line_first_code_index)
            target_min_indent_length = len(opening_indent) + 4
            current_min_indent_length = min(
                len(_line_indent(raw_segments, body_index))
                for body_index in body_indices
            )
            indent_delta = target_min_indent_length - current_min_indent_length
            if indent_delta == 0:
                continue

            fixes = []
            for body_index in body_indices:
                current_indent = _line_indent(raw_segments, body_index)
                expected_indent_length = max(0, len(current_indent) + indent_delta)
                fixes.extend(
                    _replace_or_create_line_indent(
                        raw_segments,
                        body_index,
                        " " * expected_indent_length,
                    )
                )

            if fixes:
                violations.append(
                    LintResult(
                        anchor=segment,
                        fixes=fixes,
                        description=(
                            "Indent multiline window bodies one level under "
                            "the opening line."
                        ),
                    )
                )

        return violations or None
