# Retained initial screening and reusable code

`donation_bet_reproduction/` contains reusable code with corrected casual condition wording.

`vast_snapshots/` retains unaffected screening transcripts and raw rollout caches, plus baseline calibration and run metadata. Ambiguous one-sided casual runs were removed: below-good for good-cause/silent and UNICEF/silent, and above-good for silent/naked-run (its below-trigger bad outcome). Paper-style, two-sided casual, baseline, and unambiguous opposite-direction records remain. These are incomplete historical screens, not balanced corrected-prompt experiments. Original run metadata describes the pre-cleanup run; consult the root cleanup manifest for retained counts.

Downstream resampling, J-lens, virtue-patching, prompt-swap, steering and mechanistic work, along with mixed summaries and judge caches, were quarantined and deleted on 2026-09-16.

The six missing screening arms were replaced on 2026-09-18 in [`../corrected_screen_20260918/`](../corrected_screen_20260918/REPORT.md). That directory contains 600 fresh rollouts, judge outputs, and the combined table; historical files here remain unchanged.
