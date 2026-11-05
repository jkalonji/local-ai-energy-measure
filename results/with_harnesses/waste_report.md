# waste suite: what the runs cost

Tokens are prompt + completion over every request of a run: an agent that loops sends its whole conversation again at each request, so the prompt side is where waste shows. *x budget* compares the requests of a run with the requests a frugal agent needs for the task. *Stopped by us* counts the runs the harness did not end by itself: the benchmark killed them (timeout, too many requests, no activity). *Identical streak* is the longest series of the same tool call with the same arguments, back to back (what dsh's repeat reminder reacts to, at 3, 5 and 8); *repeats* counts every call identical to an earlier one of the run, back to back or not.

| Model | Harness | Passed | Stopped by us | Median x budget | Tokens, all runs | Energy, all runs |
|---|---|---|---|---|---|---|
| deepseek-r1:8b | dsh | 36/70 | 0/70 | 0.7x | 469k | 261.15 Wh |
| granite3.1-dense:2b | dsh | 28/70 | 0/70 | 0.7x | 521k | 12.55 Wh |
| granite3.1-dense:8b | dsh | 20/70 | 0/70 | 0.7x | 511k | 24.28 Wh |
| llama3.1:8b | dsh | 18/70 | 0/70 | 1.3x | 942k | 21.54 Wh |
| mistral-nemo:12b | dsh | 23/70 | 2/70 | 0.9x | 536k | 128.66 Wh |
| qwen3.5:9b | dsh | 57/70 | 0/70 | 2.0x | 8195k | 272.21 Wh |
| qwen3:4b | dsh | 28/70 | 0/70 | 1.4x | 4178k | 367.55 Wh |

## Detail per task

| Model | Harness | Task | Passed | Stopped by us | Median requests / budget | x budget | Median tokens | Peak context | Max identical streak | Median repeats | Median energy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| deepseek-r1:8b | dsh | waste_1_impossible_test | 7/10 | - | 2 / 4 | 0.5x (max 0.5x) | 6218 (max 9237) | 1037 | 0 | 0 | 3.35 Wh |
| deepseek-r1:8b | dsh | waste_2_retry_bait | 9/10 | - | 2 / 3 | 0.7x (max 0.7x) | 6646 (max 9231) | 1020 | 0 | 0 | 3.68 Wh |
| deepseek-r1:8b | dsh | waste_3_misleading_error | 0/10 | - | 2 / 5 | 0.4x (max 0.4x) | 7780 (max 12k) | 1035 | 0 | 0 | 4.48 Wh |
| deepseek-r1:8b | dsh | waste_4_conflicting_specs | 10/10 | - | 2 / 4 | 0.5x (max 0.5x) | 5078 (max 12k) | 1027 | 0 | 0 | 2.56 Wh |
| deepseek-r1:8b | dsh | waste_5_ambiguous_edit | 0/10 | - | 2 / 3 | 0.7x (max 0.7x) | 6310 (max 11k) | 1031 | 0 | 0 | 3.39 Wh |
| deepseek-r1:8b | dsh | waste_6_huge_output | 0/10 | - | 2 / 3 | 0.7x (max 0.7x) | 6461 (max 12k) | 1026 | 0 | 0 | 3.47 Wh |
| deepseek-r1:8b | dsh | waste_7_already_done | 10/10 | - | 2 / 3 | 0.7x (max 0.7x) | 6138 (max 13k) | 1042 | 0 | 0 | 3.22 Wh |
| granite3.1-dense:2b | dsh | waste_1_impossible_test | 4/10 | - | 2 / 4 | 0.5x (max 0.5x) | 7517 (max 7638) | 6822 | 0 | 0 | 0.20 Wh |
| granite3.1-dense:2b | dsh | waste_2_retry_bait | 8/10 | - | 2 / 3 | 0.7x (max 0.7x) | 7409 (max 7525) | 6804 | 0 | 0 | 0.17 Wh |
| granite3.1-dense:2b | dsh | waste_3_misleading_error | 0/10 | - | 2 / 5 | 0.4x (max 0.4x) | 7418 (max 7572) | 6817 | 0 | 0 | 0.17 Wh |
| granite3.1-dense:2b | dsh | waste_4_conflicting_specs | 6/10 | - | 2 / 4 | 0.5x (max 0.5x) | 7566 (max 8023) | 6809 | 0 | 0 | 0.22 Wh |
| granite3.1-dense:2b | dsh | waste_5_ambiguous_edit | 0/10 | - | 2 / 3 | 0.7x (max 0.7x) | 7282 (max 7437) | 6812 | 0 | 0 | 0.13 Wh |
| granite3.1-dense:2b | dsh | waste_6_huge_output | 0/10 | - | 2 / 3 | 0.7x (max 0.7x) | 7419 (max 7569) | 6806 | 0 | 0 | 0.17 Wh |
| granite3.1-dense:2b | dsh | waste_7_already_done | 10/10 | - | 2 / 3 | 0.7x (max 0.7x) | 7480 (max 7714) | 6832 | 0 | 0 | 0.18 Wh |
| granite3.1-dense:8b | dsh | waste_1_impossible_test | 6/10 | - | 2 / 4 | 0.5x (max 0.5x) | 7292 (max 7418) | 6824 | 0 | 0 | 0.33 Wh |
| granite3.1-dense:8b | dsh | waste_2_retry_bait | 0/10 | - | 2 / 3 | 0.7x (max 0.7x) | 7086 (max 7376) | 6804 | 0 | 0 | 0.21 Wh |
| granite3.1-dense:8b | dsh | waste_3_misleading_error | 0/10 | - | 2 / 5 | 0.4x (max 0.4x) | 7310 (max 7800) | 6817 | 0 | 0 | 0.36 Wh |
| granite3.1-dense:8b | dsh | waste_4_conflicting_specs | 4/10 | - | 2 / 4 | 0.5x (max 0.5x) | 7270 (max 7448) | 6809 | 0 | 0 | 0.34 Wh |
| granite3.1-dense:8b | dsh | waste_5_ambiguous_edit | 0/10 | - | 2 / 3 | 0.7x (max 0.7x) | 7332 (max 7435) | 6812 | 0 | 0 | 0.38 Wh |
| granite3.1-dense:8b | dsh | waste_6_huge_output | 0/10 | - | 2 / 3 | 0.7x (max 0.7x) | 7341 (max 7519) | 6807 | 0 | 0 | 0.39 Wh |
| granite3.1-dense:8b | dsh | waste_7_already_done | 10/10 | - | 2 / 3 | 0.7x (max 0.7x) | 7271 (max 7410) | 6830 | 0 | 0 | 0.31 Wh |
| llama3.1:8b | dsh | waste_1_impossible_test | 3/10 | - | 6 / 4 | 1.4x (max 2.0x) | 12k (max 16k) | 6550 | 2 | 0 | 0.33 Wh |
| llama3.1:8b | dsh | waste_2_retry_bait | 3/10 | - | 4 / 3 | 1.2x (max 1.7x) | 8635 (max 11k) | 6531 | 2 | 0 | 0.19 Wh |
| llama3.1:8b | dsh | waste_3_misleading_error | 0/10 | - | 4 / 5 | 0.8x (max 1.0x) | 9279 (max 11k) | 6546 | 2 | 0 | 0.26 Wh |
| llama3.1:8b | dsh | waste_4_conflicting_specs | 2/10 | - | 7 / 4 | 1.8x (max 5.2x) | 14k (max 98k) | 8113 | 3 | 0 | 0.35 Wh |
| llama3.1:8b | dsh | waste_5_ambiguous_edit | 0/10 | - | 6 / 3 | 1.8x (max 2.3x) | 12k (max 14k) | 6539 | 1 | 0 | 0.26 Wh |
| llama3.1:8b | dsh | waste_6_huge_output | 2/10 | - | 3 / 3 | 1.0x (max 1.7x) | 8734 (max 26k) | 18k | 1 | 0 | 0.23 Wh |
| llama3.1:8b | dsh | waste_7_already_done | 8/10 | - | 4 / 3 | 1.3x (max 2.7x) | 9623 (max 17k) | 6555 | 2 | 0 | 0.27 Wh |
| mistral-nemo:12b | dsh | waste_1_impossible_test | 3/10 | - | 3 / 4 | 0.8x (max 0.8x) | 7380 (max 7611) | 6716 | 1 | 0 | 0.16 Wh |
| mistral-nemo:12b | dsh | waste_2_retry_bait | 9/10 | - | 3 / 3 | 1.0x (max 1.0x) | 7114 (max 7342) | 6701 | 1 | 0 | 0.08 Wh |
| mistral-nemo:12b | dsh | waste_3_misleading_error | 0/10 | - | 3 / 5 | 0.6x (max 0.6x) | 7644 (max 7904) | 6713 | 1 | 0 | 0.18 Wh |
| mistral-nemo:12b | dsh | waste_4_conflicting_specs | 0/10 | - | 2 / 4 | 0.5x (max 1.0x) | 7070 (max 7554) | 6706 | 1 | 0 | 0.13 Wh |
| mistral-nemo:12b | dsh | waste_5_ambiguous_edit | 0/10 | - | 3 / 3 | 1.0x (max 1.0x) | 7260 (max 7447) | 6710 | 1 | 0 | 0.13 Wh |
| mistral-nemo:12b | dsh | waste_6_huge_output | 1/10 | 2 timeout | 3 / 3 | 1.0x (max 1.0x) | 7377 (max 33k) | 26k | 1 | 0 | 0.22 Wh |
| mistral-nemo:12b | dsh | waste_7_already_done | 10/10 | - | 3 / 3 | 1.0x (max 1.0x) | 7352 (max 7765) | 6723 | 1 | 0 | 0.95 Wh |
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
