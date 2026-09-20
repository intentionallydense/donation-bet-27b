# Donation Bet reusable code

Retained upstream-derived runtime, question bank, prompt builders, extraction utilities, tests, and screening launchers. See `../../upstream_value_leakage/README.md` for provenance.

On 2026-09-16, experiments descended from the ambiguous one-sided casual prompt were quarantined and deleted at the user’s request. The casual condition now explicitly refers to “your number” in both directions. Retained historical screening transcripts preserve their actual prompts; they have not been rewritten. On 2026-09-18, the six dropped screening arms were rerun with a minimal referent correction preserving the historical inclusive boundary. See `../../corrected_screen_20260918/REPORT.md`. This is a targeted replacement study, not a full rerun using the current strict-comparison templates.

Run prompt tests from this directory with `PYTHONPATH=. python -m unittest discover -s tests -p test_composable_prompts.py`.
