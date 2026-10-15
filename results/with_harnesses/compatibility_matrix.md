# Model x harness compatibility matrix

Each cell: tasks passed / runs · median GPU energy of a run. Energy is the GPU energy of the whole run (harness start-up, idle draw and tool time included), integrated from the driver's ~20 ms power samples of an RTX 5060 Ti; it is *not* the wall-socket power. Every run uses a fresh workspace and a context window of 32768 tokens. A task passes when its objective check passes (see `benchmarks/with_harnesses/tasks/`).

| Model | dsh |
|---|---|
| qwen3:4b | 16/68 · 8.61 Wh |

## Detail per task

| Model | Harness | Task | Result | Median energy | Median time | Energy in model calls | Requests |
|---|---|---|---|---|---|---|---|
| qwen3:4b | dsh | office_1_sum_column | 8 pass, 2 fail | 8.16 Wh | 168 s | 100% | 7 |
| qwen3:4b | dsh | office_2_xlsx_total | 5 pass, 4 fail, 1 timeout | 6.32 Wh | 131 s | 100% | 6 |
| qwen3:4b | dsh | office_3_clean_pivot | 9 fail, 1 timeout | 7.30 Wh | 152 s | 100% | 6 |
| qwen3:4b | dsh | office_4_mail_merge | 10 fail | 5.48 Wh | 115 s | 100% | 6 |
| qwen3:4b | dsh | office_5_sales_report | 9 fail, 1 pass | 11.08 Wh | 232 s | 100% | 10 |
| qwen3:4b | dsh | office_6_missing_rate | 10 fail | 7.67 Wh | 160 s | 100% | 8 |
| qwen3:4b | dsh | waste_1_impossible_test | 1 fail | 2.53 Wh | 68 s | 98% | 4 |
| qwen3:4b | dsh | waste_2_retry_bait | 1 pass | 2.30 Wh | 54 s | 99% | 4 |
| qwen3:4b | dsh | waste_3_misleading_error | 1 timeout | 58.24 Wh | 1200 s | 98% | 21 |
| qwen3:4b | dsh | waste_4_conflicting_specs | 1 fail | 8.99 Wh | 185 s | 99% | 3 |
| qwen3:4b | dsh | waste_5_ambiguous_edit | 1 fail | 12.23 Wh | 249 s | 100% | 7 |
| qwen3:4b | dsh | waste_6_huge_output | 1 pass | 8.88 Wh | 184 s | 99% | 4 |
| qwen3:4b | dsh | waste_7_already_done | 1 fail | 10.22 Wh | 209 s | 100% | 4 |
| qwen3:4b | dsh | waste_8_waits_for_input | 1 fail | 6.00 Wh | 123 s | 99% | 5 |
