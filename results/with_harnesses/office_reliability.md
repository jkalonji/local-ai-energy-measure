# office suite: reliability per level

Each cell: pass rate over the runs of the most recent batch (passed/runs). The mean is the average of the levels' pass rates. A run stopped for going in circles (timeout, too many model requests, no request finished for too long) is a failure.

| Model | Harness | L1 | L2 | L3 | L4 | L5 | L6 | Mean |
|---|---|---|---|---|---|---|---|---|
| qwen3:4b | dsh | 80% (8/10) | 50% (5/10) | 0% (0/10) | 0% (0/10) | 10% (1/10) | 0% (0/10) | 23% |

## Detail

| Model | Harness | Level | Task | Passed | 95% interval | Median energy | Median time | Median requests | Stopped by a limit |
|---|---|---|---|---|---|---|---|---|---|
| qwen3:4b | dsh | L1 | office_1_sum_column | 8/10 | 49%-94% | 8.16 Wh | 168 s | 7 | - |
| qwen3:4b | dsh | L2 | office_2_xlsx_total | 5/10 | 24%-76% | 6.32 Wh | 131 s | 6 | 1 timeout |
| qwen3:4b | dsh | L3 | office_3_clean_pivot | 0/10 | 0%-28% | 7.30 Wh | 152 s | 6 | 1 timeout |
| qwen3:4b | dsh | L4 | office_4_mail_merge | 0/10 | 0%-28% | 5.48 Wh | 115 s | 6 | - |
| qwen3:4b | dsh | L5 | office_5_sales_report | 1/10 | 2%-40% | 11.08 Wh | 232 s | 10 | - |
| qwen3:4b | dsh | L6 | office_6_missing_rate | 0/10 | 0%-28% | 7.67 Wh | 160 s | 8 | - |
