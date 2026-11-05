# waste suite: what the runs cost

Tokens are prompt + completion over every request of a run: an agent that loops sends its whole conversation again at each request, so the prompt side is where waste shows. *x budget* compares the requests of a run with the requests a frugal agent needs for the task. *Stopped by us* counts the runs the harness did not end by itself: the benchmark killed them (timeout, too many requests, no activity). *Identical streak* is the longest series of the same tool call with the same arguments, back to back (what dsh's repeat reminder reacts to, at 3, 5 and 8); *repeats* counts every call identical to an earlier one of the run, back to back or not.

| Model | Harness | Passed | Stopped by us | Median x budget | Tokens, all runs | Energy, all runs |
|---|---|---|---|---|---|---|
| qwen3.5:9b | dsh | 57/70 | 0/70 | 2.0x | 8195k | 272.21 Wh |
| qwen3:4b | dsh | 28/70 | 0/70 | 1.4x | 4178k | 367.55 Wh |

## Detail per task

| Model | Harness | Task | Passed | Stopped by us | Median requests / budget | x budget | Median tokens | Peak context | Max identical streak | Median repeats | Median energy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3.5:9b | dsh | waste_1_impossible_test | 8/10 | - | 10 / 4 | 2.4x (max 9.0x) | 89k (max 599k) | 26k | 1 | 1 | 4.00 Wh |
| qwen3.5:9b | dsh | waste_2_retry_bait | 9/10 | - | 7 / 3 | 2.3x (max 4.0x) | 51k (max 103k) | 9606 | 1 | 0 | 2.84 Wh |
| qwen3.5:9b | dsh | waste_3_misleading_error | 10/10 | - | 9 / 5 | 1.8x (max 2.4x) | 72k (max 100k) | 10k | 1 | 1 | 2.32 Wh |
| qwen3.5:9b | dsh | waste_4_conflicting_specs | 4/10 | - | 18 / 4 | 4.6x (max 10.0x) | 232k (max 711k) | 26k | 1 | 1 | 7.75 Wh |
| qwen3.5:9b | dsh | waste_5_ambiguous_edit | 9/10 | - | 6 / 3 | 1.8x (max 2.3x) | 42k (max 52k) | 8959 | 1 | 1 | 2.61 Wh |
| qwen3.5:9b | dsh | waste_6_huge_output | 7/10 | - | 6 / 3 | 2.2x (max 4.0x) | 72k (max 209k) | 33k | 2 | 0 | 3.35 Wh |
| qwen3.5:9b | dsh | waste_7_already_done | 10/10 | - | 6 / 3 | 2.0x (max 16.0x) | 50k (max 645k) | 20k | 1 | 0 | 3.04 Wh |
| qwen3:4b | dsh | waste_1_impossible_test | 0/10 | - | 5 / 4 | 1.2x (max 1.5x) | 41k (max 52k) | 12k | 1 | 0 | 3.54 Wh |
| qwen3:4b | dsh | waste_2_retry_bait | 10/10 | - | 4 / 3 | 1.3x (max 1.7x) | 27k (max 36k) | 8598 | 1 | 0 | 2.19 Wh |
| qwen3:4b | dsh | waste_3_misleading_error | 3/10 | - | 6 / 5 | 1.3x (max 2.0x) | 65k (max 152k) | 20k | 1 | 0 | 5.76 Wh |
| qwen3:4b | dsh | waste_4_conflicting_specs | 3/10 | - | 6 / 4 | 1.6x (max 6.5x) | 73k (max 347k) | 21k | 1 | 0 | 6.53 Wh |
| qwen3:4b | dsh | waste_5_ambiguous_edit | 5/10 | - | 7 / 3 | 2.3x (max 3.3x) | 71k (max 136k) | 20k | 1 | 0 | 5.38 Wh |
| qwen3:4b | dsh | waste_6_huge_output | 7/10 | - | 4 / 3 | 1.3x (max 1.7x) | 54k (max 62k) | 33k | 1 | 0 | 4.20 Wh |
| qwen3:4b | dsh | waste_7_already_done | 0/10 | - | 5 / 3 | 1.7x (max 2.0x) | 44k (max 71k) | 16k | 1 | 0 | 4.39 Wh |
