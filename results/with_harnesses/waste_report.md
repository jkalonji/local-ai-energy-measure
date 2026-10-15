# waste suite: what the runs cost

Tokens are prompt + completion over every request of a run: an agent that loops sends its whole conversation again at each request, so the prompt side is where waste shows. *x budget* compares the requests of a run with the requests a frugal agent needs for the task. *Stopped by us* counts the runs the harness did not end by itself: the benchmark killed them (timeout, too many requests, no activity). *Identical streak* is the longest series of the same tool call with the same arguments, back to back (what dsh's repeat reminder reacts to, at 3, 5 and 8); *repeats* counts every call identical to an earlier one of the run, back to back or not.

| Model | Harness | Passed | Stopped by us | Median x budget | Tokens, all runs | Energy, all runs |
|---|---|---|---|---|---|---|
| qwen3:4b | dsh | 2/8 | 1/8 | 1.3x | 581k | 109.40 Wh |

## Detail per task

| Model | Harness | Task | Passed | Stopped by us | Median requests / budget | x budget | Median tokens | Peak context | Max identical streak | Median repeats | Median energy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:4b | dsh | waste_1_impossible_test | 0/1 | - | 4 / 4 | 1.0x (max 1.0x) | 28k (max 28k) | 9155 | 1 | 0 | 2.53 Wh |
| qwen3:4b | dsh | waste_2_retry_bait | 1/1 | - | 4 / 3 | 1.3x (max 1.3x) | 28k (max 28k) | 8816 | 1 | 0 | 2.30 Wh |
| qwen3:4b | dsh | waste_3_misleading_error | 0/1 | 1 timeout | 21 / 5 | 4.2x (max 4.2x) | 300k (max 300k) | 22k | 2 | 4 | 58.24 Wh |
| qwen3:4b | dsh | waste_4_conflicting_specs | 0/1 | - | 3 / 4 | 0.8x (max 0.8x) | 24k (max 24k) | 9213 | 1 | 0 | 8.99 Wh |
| qwen3:4b | dsh | waste_5_ambiguous_edit | 0/1 | - | 7 / 3 | 2.3x (max 2.3x) | 70k (max 70k) | 14k | 1 | 0 | 12.23 Wh |
| qwen3:4b | dsh | waste_6_huge_output | 1/1 | - | 4 / 3 | 1.3x (max 1.3x) | 57k (max 57k) | 32k | 1 | 0 | 8.88 Wh |
| qwen3:4b | dsh | waste_7_already_done | 0/1 | - | 4 / 3 | 1.3x (max 1.3x) | 35k (max 35k) | 12k | 1 | 0 | 10.22 Wh |
| qwen3:4b | dsh | waste_8_waits_for_input | 0/1 | - | 5 / 4 | 1.2x (max 1.2x) | 38k (max 38k) | 9777 | 1 | 0 | 6.00 Wh |
