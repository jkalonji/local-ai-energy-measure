# Model x harness compatibility matrix

Each cell: tasks passed / runs · median GPU energy of a run. Energy is the GPU energy of the whole run (harness start-up, idle draw and tool time included), integrated from the driver's ~20 ms power samples of an RTX 5060 Ti; it is *not* the wall-socket power. Every run uses a fresh workspace and a context window of 32768 tokens. A task passes when its objective check passes (see `benchmarks/with_harnesses/tasks/`).

| Model | dsh |
|---|---|
| qwen3:4b | 17/63 · 7.73 Wh |

## Detail per task

| Model | Harness | Task | Result | Median energy | Median time | Energy in model calls | Requests |
|---|---|---|---|---|---|---|---|
| qwen3:4b | dsh | answer_arithmetic | 1 pass | 0.31 Wh | 31 s | 98% | 1 |
| qwen3:4b | dsh | fix_bug | 1 pass | 3.14 Wh | 346 s | 100% | 4 |
| qwen3:4b | dsh | office_1_sum_column | 8 pass, 2 fail | 8.16 Wh | 168 s | 100% | 7 |
| qwen3:4b | dsh | office_2_xlsx_total | 5 pass, 4 fail, 1 timeout | 6.32 Wh | 131 s | 100% | 6 |
| qwen3:4b | dsh | office_3_clean_pivot | 9 fail, 1 timeout | 7.30 Wh | 152 s | 100% | 6 |
| qwen3:4b | dsh | office_4_mail_merge | 10 fail | 5.48 Wh | 115 s | 100% | 6 |
| qwen3:4b | dsh | office_5_sales_report | 9 fail, 1 pass | 11.08 Wh | 232 s | 100% | 10 |
| qwen3:4b | dsh | office_6_missing_rate | 10 fail | 7.67 Wh | 160 s | 100% | 8 |
| qwen3:4b | dsh | write_file | 1 pass | 0.93 Wh | 101 s | 99% | 2 |
