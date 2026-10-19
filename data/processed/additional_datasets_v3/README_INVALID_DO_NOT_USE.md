# Invalid development output — do not report

This directory is preserved for provenance. The first development run aligned
the SOH target to the same row as the SOH input, causing direct target leakage
and artificially near-zero errors. Do not use its SOH predictions or metrics.

Use the corrected outputs in `additional_datasets_v3_1`, where each row's
current-cycle features predict the next recorded SOH. No source datasets or
earlier project results were modified.
