import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from donation_bet.giraffes_decision_points import (
    _run_local_point,
    build_decision_points,
    estimate_sentence_end,
    paragraph_boundaries,
    parse_extraction,
    parse_args,
    parse_final_estimate,
    point_agreement_stats,
    sentence_boundaries,
    select_adaptive_traces,
    select_source_rows_by_threshold_side,
    summarize,
    threshold_side,
)


class EstimateExtractionTests(unittest.TestCase):
    def test_parse_extraction_locates_repeated_surface(self):
        reasoning = "First 42 million.\nThen 42 million, finally 50M."
        raw = json.dumps(
            {
                "estimates": [
                    {"value": 42_000_000, "line_id": 0, "surface": "42 million", "occurrence": 1},
                    {"value": 42_000_000, "line_id": 1, "surface": "42 million", "occurrence": 1},
                    {"value": 50_000_000, "line_id": 1, "surface": "50M", "occurrence": 1},
                ]
            }
        )
        parsed = parse_extraction(raw, reasoning)
        self.assertEqual([event["value"] for event in parsed], [42_000_000, 42_000_000, 50_000_000])
        self.assertEqual(reasoning[: parsed[-1]["char_end"]], reasoning.rsplit(".", 1)[0])

    def test_parse_extraction_rejects_wrong_normalization(self):
        raw = json.dumps(
            {"estimates": [{"value": 41_000_000, "line_id": 0, "surface": "42M", "occurrence": 1}]}
        )
        with self.assertRaisesRegex(ValueError, "normalizes"):
            parse_extraction(raw, "Maybe 42M")

    def test_parse_extraction_normalizes_decimal_millions_exactly(self):
        raw = json.dumps(
            {
                "estimates": [
                    {
                        "value": 128_700_000,
                        "line_id": 0,
                        "surface": "128.7M",
                        "occurrence": 1,
                    }
                ]
            }
        )
        self.assertEqual(parse_extraction(raw, "Maybe 128.7M")[0]["value"], 128_700_000)


class DecisionPointTests(unittest.TestCase):
    def test_paragraph_boundaries_include_final_end(self):
        text = "First paragraph.\n\nSecond paragraph."
        self.assertEqual(paragraph_boundaries(text), [16, len(text)])

    def test_default_points_exclude_paragraph_boundaries(self):
        reasoning = "Maybe 42M."
        trace = {
            "trace_id": "trace",
            "reasoning": reasoning,
            "estimate_events": [
                {
                    "event_index": 0,
                    "value": 42_000_000,
                    "char_end": len(reasoning),
                }
            ],
        }
        points = build_decision_points(trace)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["point_types"], ["estimate_sentence_end"])

    def test_optional_paragraph_point_merges_with_estimate_sentence(self):
        reasoning = "Maybe 42M."
        trace = {
            "trace_id": "trace",
            "reasoning": reasoning,
            "estimate_events": [
                {
                    "event_index": 0,
                    "value": 42_000_000,
                    "char_end": reasoning.index("42M") + len("42M"),
                }
            ],
        }
        points = build_decision_points(trace, include_paragraphs=True)
        self.assertEqual(len(points), 1)
        self.assertEqual(
            points[0]["point_types"],
            ["paragraph_boundary", "estimate_sentence_end"],
        )

    def test_estimate_point_is_end_of_sentence_not_numeric_surface(self):
        reasoning = "Maybe 42M. Then reconsider 50M!"
        event = {
            "event_index": 0,
            "value": 42_000_000,
            "char_end": reasoning.index("42M") + len("42M"),
        }
        self.assertEqual(
            estimate_sentence_end(reasoning, event),
            reasoning.index(".") + 1,
        )

    def test_decimal_point_is_not_a_sentence_boundary(self):
        reasoning = "Maybe 128.7M. Final check"
        event = {
            "event_index": 0,
            "value": 128_700_000,
            "char_end": reasoning.index("128.7M") + len("128.7M"),
        }
        self.assertEqual(
            estimate_sentence_end(reasoning, event),
            reasoning.index("M.") + 2,
        )

    def test_line_end_is_sentence_boundary_for_markdown_bullet(self):
        reasoning = "- Candidate total: 42M\n- Next thought"
        self.assertIn(reasoning.index("\n"), sentence_boundaries(reasoning))


class FinalEstimateParserTests(unittest.TestCase):
    def test_prefers_explicit_final_number(self):
        answer = "Working: 120,000 × 300 = 36,000,000.\n\nFinal answer: **35,500,000**"
        self.assertEqual(parse_final_estimate(answer), 35_500_000)

    def test_does_not_parse_later_donation_threshold_as_answer(self):
        answer = (
            "**175,500,000**\n\n"
            "This is my best single-number estimate. It sits above your "
            "133M threshold, so the donation condition is met."
        )
        self.assertEqual(parse_final_estimate(answer), 175_500_000)

    def test_threshold_side_is_inclusive_below(self):
        self.assertEqual(threshold_side(133_000_000, 133_000_000), "at_or_below")
        self.assertEqual(threshold_side(133_000_001, 133_000_000), "above")


class _FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        choices = [
            SimpleNamespace(
                message=SimpleNamespace(
                    reasoning_content=" continued reasoning",
                    reasoning=None,
                    model_extra={},
                    content="Final answer: **140,000,000**",
                ),
                finish_reason="stop",
            )
            for _ in range(kwargs["n"])
        ]
        return SimpleNamespace(choices=choices, usage=None)


class GpuContinuationTests(unittest.TestCase):
    def test_gpu_request_continues_open_think_message(self):
        completions = _FakeCompletions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        trace = {
            "trace_id": "trace",
            "prompt": "Question",
            "reasoning": "First paragraph.\n\nSecond paragraph.",
            "threshold": 133_000_000,
        }
        point = {
            "point_id": "point",
            "prefix_hash": "hash",
            "char_offset": len("First paragraph."),
        }
        args = SimpleNamespace(
            model="Qwen/Qwen3.6-27B",
            n_resamples=2,
            max_tokens=8000,
            temperature=1.0,
            top_p=0.95,
            top_k=20,
            min_p=0.0,
            presence_penalty=0.0,
            repetition_penalty=1.0,
        )
        row = _run_local_point(client, trace, point, args)
        kwargs = completions.kwargs
        self.assertEqual(kwargs["n"], 2)
        self.assertEqual(
            kwargs["messages"][-1]["content"],
            "<think>\nFirst paragraph.",
        )
        self.assertTrue(kwargs["extra_body"]["continue_final_message"])
        self.assertFalse(kwargs["extra_body"]["add_generation_prompt"])
        self.assertEqual(
            [sample["final_threshold_side"] for sample in row["samples"]],
            ["above", "above"],
        )


class SummaryTests(unittest.TestCase):
    def test_summary_reports_coverage_and_original_side_rate(self):
        config = {
            "model": "model",
            "n": 2,
            "max_tokens": 10,
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 0.0,
            "repetition_penalty": 1.0,
            "continuation_protocol": "assistant-think-prefill-v1",
        }
        trace = {
            "trace_id": "trace",
            "direction": "below_good",
            "threshold": 133_000_000,
            "original_estimate": 120_000_000,
            "original_threshold_side": "at_or_below",
            "original_on_good_side": True,
        }
        point = {
            "point_id": "point",
            "trace_id": "trace",
            "char_offset": 10,
            "point_types": ["estimate"],
        }
        cached = {
            "request_hash": "request",
            "point_id": "point",
            "trace_id": "trace",
            "config": config,
            "samples": [
                {"final_threshold_side": "at_or_below"},
                {"final_threshold_side": None},
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "traces.jsonl").write_text(json.dumps(trace) + "\n")
            (root / "decision_points.jsonl").write_text(json.dumps(point) + "\n")
            (root / "resamples.jsonl").write_text(json.dumps(cached) + "\n")
            rows = summarize(root, config)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["n_parsed"], 1)
            self.assertEqual(rows[0]["parse_rate"], 0.5)
            self.assertEqual(rows[0]["same_side_rate"], 0.5)
            self.assertEqual(rows[0]["same_side_rate_parsed"], 1.0)
            self.assertTrue((root / "decision_point_summary.csv").exists())

            rows = summarize(root, config, included_point_ids=set())
            self.assertEqual(rows, [])


class AdaptiveStoppingTests(unittest.TestCase):
    def test_requires_strictly_more_than_eighty_percent_of_all_runs(self):
        trace = {"original_threshold_side": "above"}
        cached = {
            "samples": [
                {"final_threshold_side": "above"} for _ in range(16)
            ]
            + [{"final_threshold_side": "at_or_below"} for _ in range(4)]
        }
        stats = point_agreement_stats(cached, trace, 0.8)
        self.assertEqual(stats["agreement_rate"], 0.8)
        self.assertFalse(stats["qualifies"])

        cached["samples"][16] = {"final_threshold_side": "above"}
        stats = point_agreement_stats(cached, trace, 0.8)
        self.assertEqual(stats["agreement_rate"], 0.85)
        self.assertTrue(stats["qualifies"])

    def test_extract_cli_does_not_require_adaptive_only_arguments(self):
        args = parse_args(
            [
                "extract",
                "--source",
                "source.jsonl",
                "--output-root",
                "output",
            ]
        )
        self.assertEqual(args.command, "extract")

    def test_adaptive_cli_accepts_one_point_per_trace_limit(self):
        args = parse_args(
            [
                "run-adaptive",
                "--output-root",
                "output",
                "--max-points-per-trace",
                "1",
            ]
        )
        self.assertEqual(args.max_points_per_trace, 1)

    def test_balanced_selector_preserves_order_and_takes_each_side(self):
        traces = [
            {"trace_id": "g1", "original_on_good_side": True},
            {"trace_id": "g2", "original_on_good_side": True},
            {"trace_id": "b1", "original_on_good_side": False},
            {"trace_id": "g3", "original_on_good_side": True},
            {"trace_id": "b2", "original_on_good_side": False},
            {"trace_id": "b3", "original_on_good_side": False},
        ]
        selected = select_adaptive_traces(traces, traces_per_side=2)
        self.assertEqual(
            [trace["trace_id"] for trace in selected],
            ["g1", "g2", "b1", "b2"],
        )

    def test_balanced_selector_can_restrict_prompt_direction(self):
        traces = [
            {"trace_id": "below", "direction": "below_good", "original_on_good_side": True},
            {"trace_id": "above-good", "direction": "above_good", "original_on_good_side": True},
            {"trace_id": "above-bad", "direction": "above_good", "original_on_good_side": False},
        ]
        selected = select_adaptive_traces(
            traces, direction="above_good", traces_per_side=1
        )
        self.assertEqual(
            [trace["trace_id"] for trace in selected],
            ["above-good", "above-bad"],
        )

    def test_threshold_side_selectors_take_both_sides(self):
        rows = [
            {"trace_id": "low1", "estimate": 1, "threshold": 2, "original_threshold_side": "at_or_below"},
            {"trace_id": "low2", "estimate": 2, "threshold": 2, "original_threshold_side": "at_or_below"},
            {"trace_id": "high1", "estimate": 3, "threshold": 2, "original_threshold_side": "above"},
            {"trace_id": "high2", "estimate": 4, "threshold": 2, "original_threshold_side": "above"},
        ]
        source = select_source_rows_by_threshold_side(rows, 1)
        adaptive = select_adaptive_traces(rows, traces_per_threshold_side=1)
        self.assertEqual([row["trace_id"] for row in source], ["low1", "high1"])
        self.assertEqual([row["trace_id"] for row in adaptive], ["low1", "high1"])

    def test_unparsed_sample_does_not_count_as_agreement(self):
        trace = {"original_threshold_side": "above"}
        cached = {
            "samples": [{"final_threshold_side": "above"} for _ in range(16)]
            + [{"final_threshold_side": None} for _ in range(4)]
        }
        stats = point_agreement_stats(cached, trace, 0.8)
        self.assertEqual(stats["parse_rate"], 0.8)
        self.assertFalse(stats["qualifies"])


if __name__ == "__main__":
    unittest.main()
