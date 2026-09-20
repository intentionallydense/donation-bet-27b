# Probe trigger separations

Block 40, using strict score > the existing casual-baseline pooled-token 95th-percentile cutoff. No smoothing. A firing-token distance is the difference in indices of consecutive firing tokens; 1 means adjacent tokens. A silent gap counts only non-firing tokens between consecutive bursts. Burst-start distance is also included in the CSVs. Gaps never cross trace boundaries; leading and trailing censored intervals are omitted. Each observed gap has equal weight, so traces with more triggers contribute more observations. These are descriptive distributions, not independent-event significance tests.

- [Four displayed traces](trigger_gaps_four_displayed.png)
- [All 400 traces](trigger_gaps_all_400.png)
- [Summary statistics](trigger_gap_summary.csv)
- [Exact discrete distributions](trigger_gap_histogram.csv)
- [Per-trace means](trigger_gap_per_trace.csv)
