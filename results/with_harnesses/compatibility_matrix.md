# Model x harness compatibility matrix

Each cell: tasks passed / runs · median GPU energy of a run. Energy is the GPU energy of the whole run (harness start-up, idle draw and tool time included), integrated from the driver's ~20 ms power samples of an RTX 5060 Ti; it is *not* the wall-socket power. Every run uses a fresh workspace and a context window of 32768 tokens. A task passes when its objective check passes (see `benchmarks/with_harnesses/tasks/`).

| Model | dsh |
|---|---|
| qwen3.5:9b | 57/70 · 3.19 Wh |
| qwen3:4b | 42/130 · 5.48 Wh |

## Detail per task

| Model | Harness | Task | Result | Median energy | Median time | Energy in model calls | Requests |
|---|---|---|---|---|---|---|---|
| qwen3.5:9b | dsh | waste_1_impossible_test | 8 pass, 2 fail | 4.00 Wh | 94 s | 99% | 9 |
| qwen3.5:9b | dsh | waste_2_retry_bait | 9 pass, 1 fail | 2.84 Wh | 70 s | 99% | 7 |
| qwen3.5:9b | dsh | waste_3_misleading_error | 10 pass | 2.32 Wh | 56 s | 99% | 9 |
| qwen3.5:9b | dsh | waste_4_conflicting_specs | 6 fail, 4 pass | 7.75 Wh | 182 s | 99% | 18 |
| qwen3.5:9b | dsh | waste_5_ambiguous_edit | 9 pass, 1 fail | 2.61 Wh | 62 s | 100% | 5 |
| qwen3.5:9b | dsh | waste_6_huge_output | 7 pass, 3 error | 3.35 Wh | 78 s | 99% | 6 |
| qwen3.5:9b | dsh | waste_7_already_done | 10 pass | 3.04 Wh | 74 s | 99% | 6 |
| qwen3:4b | dsh | office_1_sum_column | 8 pass, 2 fail | 8.16 Wh | 168 s | 100% | 7 |
| qwen3:4b | dsh | office_2_xlsx_total | 5 pass, 4 fail, 1 timeout | 6.32 Wh | 131 s | 100% | 6 |
| qwen3:4b | dsh | office_3_clean_pivot | 9 fail, 1 timeout | 7.30 Wh | 152 s | 100% | 6 |
| qwen3:4b | dsh | office_4_mail_merge | 10 fail | 5.48 Wh | 115 s | 100% | 6 |
| qwen3:4b | dsh | office_5_sales_report | 9 fail, 1 pass | 11.08 Wh | 232 s | 100% | 10 |
| qwen3:4b | dsh | office_6_missing_rate | 10 fail | 7.67 Wh | 160 s | 100% | 8 |
| qwen3:4b | dsh | waste_1_impossible_test | 10 fail | 3.54 Wh | 78 s | 100% | 5 |
| qwen3:4b | dsh | waste_2_retry_bait | 10 pass | 2.19 Wh | 51 s | 99% | 4 |
| qwen3:4b | dsh | waste_3_misleading_error | 7 fail, 3 pass | 5.76 Wh | 125 s | 100% | 6 |
| qwen3:4b | dsh | waste_4_conflicting_specs | 7 fail, 3 pass | 6.53 Wh | 141 s | 100% | 6 |
| qwen3:4b | dsh | waste_5_ambiguous_edit | 5 fail, 5 pass | 5.38 Wh | 117 s | 100% | 7 |
| qwen3:4b | dsh | waste_6_huge_output | 7 pass, 3 fail | 4.20 Wh | 93 s | 100% | 4 |
| qwen3:4b | dsh | waste_7_already_done | 10 fail | 4.39 Wh | 95 s | 100% | 5 |

## Warnings

- `dsh--qwen3.5_9b--waste_6_huge_output--6--20261101_174713`: GPU power samples cover only 98% of the run
- `dsh--qwen3.5_9b--waste_6_huge_output--7--20261101_174713`: GPU power samples cover only 98% of the run
- `dsh--qwen3.5_9b--waste_6_huge_output--9--20261101_174713`: GPU power samples cover only 98% of the run
- `dsh--qwen3.5_9b--waste_7_already_done--7--20261101_174713`: GPU power samples cover only 98% of the run
- `dsh--qwen3.5_9b--waste_7_already_done--9--20261101_174713`: GPU power samples cover only 99% of the run
