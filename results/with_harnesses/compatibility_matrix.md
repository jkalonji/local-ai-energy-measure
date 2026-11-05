# Model x harness compatibility matrix

Each cell: tasks passed / runs · median GPU energy of a run. Energy is the GPU energy of the whole run (harness start-up, idle draw and tool time included), integrated from the driver's ~20 ms power samples of an RTX 5060 Ti; it is *not* the wall-socket power. Every run uses a fresh workspace and a context window of 32768 tokens. A task passes when its objective check passes (see `benchmarks/with_harnesses/tasks/`).

| Model | dsh |
|---|---|
| deepseek-r1:8b | 36/70 · 3.46 Wh |
| granite3.1-dense:2b | 28/70 · 0.17 Wh |
| granite3.1-dense:8b | 20/70 · 0.35 Wh |
| llama3.1:8b | 18/70 · 0.26 Wh |
| mistral-nemo:12b | 23/70 · 0.16 Wh |
| qwen3.5:9b | 57/70 · 3.19 Wh |
| qwen3:4b | 42/130 · 5.48 Wh |

## Detail per task

| Model | Harness | Task | Result | Median energy | Median time | Energy in model calls | Requests |
|---|---|---|---|---|---|---|---|
| deepseek-r1:8b | dsh | waste_1_impossible_test | 7 pass, 3 fail | 3.35 Wh | 74 s | 100% | 2 |
| deepseek-r1:8b | dsh | waste_2_retry_bait | 9 pass, 1 fail | 3.68 Wh | 81 s | 100% | 2 |
| deepseek-r1:8b | dsh | waste_3_misleading_error | 10 fail | 4.48 Wh | 97 s | 100% | 2 |
| deepseek-r1:8b | dsh | waste_4_conflicting_specs | 10 pass | 2.56 Wh | 57 s | 100% | 2 |
| deepseek-r1:8b | dsh | waste_5_ambiguous_edit | 10 fail | 3.39 Wh | 74 s | 100% | 2 |
| deepseek-r1:8b | dsh | waste_6_huge_output | 10 fail | 3.47 Wh | 76 s | 100% | 2 |
| deepseek-r1:8b | dsh | waste_7_already_done | 10 pass | 3.22 Wh | 72 s | 100% | 2 |
| granite3.1-dense:2b | dsh | waste_1_impossible_test | 6 fail, 4 pass | 0.20 Wh | 6 s | 97% | 2 |
| granite3.1-dense:2b | dsh | waste_2_retry_bait | 8 pass, 2 fail | 0.17 Wh | 5 s | 97% | 2 |
| granite3.1-dense:2b | dsh | waste_3_misleading_error | 10 fail | 0.17 Wh | 5 s | 97% | 2 |
| granite3.1-dense:2b | dsh | waste_4_conflicting_specs | 6 pass, 4 fail | 0.22 Wh | 7 s | 97% | 2 |
| granite3.1-dense:2b | dsh | waste_5_ambiguous_edit | 10 fail | 0.13 Wh | 4 s | 96% | 2 |
| granite3.1-dense:2b | dsh | waste_6_huge_output | 10 fail | 0.17 Wh | 5 s | 97% | 2 |
| granite3.1-dense:2b | dsh | waste_7_already_done | 10 pass | 0.18 Wh | 6 s | 97% | 2 |
| granite3.1-dense:8b | dsh | waste_1_impossible_test | 6 pass, 4 fail | 0.33 Wh | 9 s | 98% | 2 |
| granite3.1-dense:8b | dsh | waste_2_retry_bait | 10 fail | 0.21 Wh | 6 s | 97% | 2 |
| granite3.1-dense:8b | dsh | waste_3_misleading_error | 10 fail | 0.36 Wh | 9 s | 98% | 2 |
| granite3.1-dense:8b | dsh | waste_4_conflicting_specs | 6 fail, 4 pass | 0.34 Wh | 9 s | 98% | 2 |
| granite3.1-dense:8b | dsh | waste_5_ambiguous_edit | 10 fail | 0.38 Wh | 10 s | 98% | 2 |
| granite3.1-dense:8b | dsh | waste_6_huge_output | 10 fail | 0.39 Wh | 10 s | 98% | 2 |
| granite3.1-dense:8b | dsh | waste_7_already_done | 10 pass | 0.31 Wh | 8 s | 98% | 2 |
| llama3.1:8b | dsh | waste_1_impossible_test | 7 fail, 3 pass | 0.33 Wh | 9 s | 97% | 5 |
| llama3.1:8b | dsh | waste_2_retry_bait | 7 fail, 3 pass | 0.19 Wh | 6 s | 96% | 3 |
| llama3.1:8b | dsh | waste_3_misleading_error | 10 fail | 0.26 Wh | 7 s | 97% | 4 |
| llama3.1:8b | dsh | waste_4_conflicting_specs | 8 fail, 2 pass | 0.35 Wh | 9 s | 97% | 7 |
| llama3.1:8b | dsh | waste_5_ambiguous_edit | 10 fail | 0.26 Wh | 7 s | 97% | 5 |
| llama3.1:8b | dsh | waste_6_huge_output | 8 fail, 2 pass | 0.23 Wh | 7 s | 97% | 3 |
| llama3.1:8b | dsh | waste_7_already_done | 8 pass, 2 fail | 0.27 Wh | 7 s | 96% | 4 |
| mistral-nemo:12b | dsh | waste_1_impossible_test | 7 fail, 3 pass | 0.16 Wh | 6 s | 95% | 3 |
| mistral-nemo:12b | dsh | waste_2_retry_bait | 9 pass, 1 fail | 0.08 Wh | 6 s | 82% | 3 |
| mistral-nemo:12b | dsh | waste_3_misleading_error | 10 fail | 0.18 Wh | 7 s | 97% | 3 |
| mistral-nemo:12b | dsh | waste_4_conflicting_specs | 10 fail | 0.13 Wh | 5 s | 96% | 2 |
| mistral-nemo:12b | dsh | waste_5_ambiguous_edit | 10 fail | 0.13 Wh | 5 s | 95% | 3 |
| mistral-nemo:12b | dsh | waste_6_huge_output | 7 fail, 2 timeout, 1 pass | 0.22 Wh | 7 s | 93% | 3 |
| mistral-nemo:12b | dsh | waste_7_already_done | 10 pass | 0.95 Wh | 24 s | 87% | 3 |
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
- `dsh--granite3.1-dense_2b--waste_4_conflicting_specs--3--20261105_185118`: GPU power samples cover only 96% of the run
- `dsh--deepseek-r1_8b--waste_2_retry_bait--2--20261105_200004`: GPU power samples cover only 98% of the run
- `dsh--deepseek-r1_8b--waste_3_misleading_error--2--20261105_200004`: GPU power samples cover only 97% of the run
- `dsh--deepseek-r1_8b--waste_3_misleading_error--6--20261105_200004`: GPU power samples cover only 99% of the run
- `dsh--deepseek-r1_8b--waste_3_misleading_error--7--20261105_200004`: GPU power samples cover only 99% of the run
- `dsh--deepseek-r1_8b--waste_4_conflicting_specs--9--20261105_200004`: GPU power samples cover only 98% of the run
- `dsh--deepseek-r1_8b--waste_7_already_done--1--20261105_200004`: GPU power samples cover only 99% of the run
- `dsh--deepseek-r1_8b--waste_7_already_done--2--20261105_200004`: GPU power samples cover only 98% of the run
- `dsh--deepseek-r1_8b--waste_7_already_done--4--20261105_200004`: GPU power samples cover only 95% of the run
- `dsh--deepseek-r1_8b--waste_7_already_done--9--20261105_200004`: GPU power samples cover only 96% of the run
- `dsh--mistral-nemo_12b--waste_1_impossible_test--1--20261105_200004`: GPU power samples cover only 86% of the run
- `dsh--mistral-nemo_12b--waste_1_impossible_test--3--20261105_200004`: GPU power samples cover only 87% of the run
- `dsh--mistral-nemo_12b--waste_1_impossible_test--4--20261105_200004`: GPU power samples cover only 77% of the run
- `dsh--mistral-nemo_12b--waste_1_impossible_test--5--20261105_200004`: GPU power samples cover only 87% of the run
- `dsh--mistral-nemo_12b--waste_1_impossible_test--6--20261105_200004`: GPU power samples cover only 95% of the run
- `dsh--mistral-nemo_12b--waste_1_impossible_test--8--20261105_200004`: GPU power samples cover only 86% of the run
- `dsh--mistral-nemo_12b--waste_1_impossible_test--10--20261105_200004`: GPU power samples cover only 97% of the run
- `dsh--mistral-nemo_12b--waste_2_retry_bait--1--20261105_200004`: GPU power samples cover only 65% of the run
- `dsh--mistral-nemo_12b--waste_2_retry_bait--2--20261105_200004`: GPU power samples cover only 96% of the run
- `dsh--mistral-nemo_12b--waste_2_retry_bait--3--20261105_200004`: GPU power samples cover only 45% of the run
- `dsh--mistral-nemo_12b--waste_2_retry_bait--4--20261105_200004`: GPU power samples cover only 84% of the run
- `dsh--mistral-nemo_12b--waste_2_retry_bait--5--20261105_200004`: GPU power samples cover only 48% of the run
- `dsh--mistral-nemo_12b--waste_2_retry_bait--6--20261105_200004`: GPU power samples cover only 80% of the run
- `dsh--mistral-nemo_12b--waste_2_retry_bait--8--20261105_200004`: GPU power samples cover only 83% of the run
- `dsh--mistral-nemo_12b--waste_2_retry_bait--9--20261105_200004`: GPU power samples cover only 59% of the run
- `dsh--mistral-nemo_12b--waste_2_retry_bait--10--20261105_200004`: GPU power samples cover only 77% of the run
- `dsh--mistral-nemo_12b--waste_3_misleading_error--1--20261105_200004`: GPU power samples cover only 79% of the run
- `dsh--mistral-nemo_12b--waste_3_misleading_error--2--20261105_200004`: GPU power samples cover only 76% of the run
- `dsh--mistral-nemo_12b--waste_3_misleading_error--3--20261105_200004`: GPU power samples cover only 78% of the run
- `dsh--mistral-nemo_12b--waste_3_misleading_error--4--20261105_200004`: GPU power samples cover only 82% of the run
- `dsh--mistral-nemo_12b--waste_3_misleading_error--5--20261105_200004`: GPU power samples cover only 88% of the run
- `dsh--mistral-nemo_12b--waste_3_misleading_error--6--20261105_200004`: GPU power samples cover only 72% of the run
- `dsh--mistral-nemo_12b--waste_3_misleading_error--7--20261105_200004`: GPU power samples cover only 78% of the run
- `dsh--mistral-nemo_12b--waste_3_misleading_error--8--20261105_200004`: GPU power samples cover only 81% of the run
- `dsh--mistral-nemo_12b--waste_3_misleading_error--9--20261105_200004`: GPU power samples cover only 77% of the run
- `dsh--mistral-nemo_12b--waste_3_misleading_error--10--20261105_200004`: GPU power samples cover only 55% of the run
- `dsh--mistral-nemo_12b--waste_4_conflicting_specs--1--20261105_200004`: GPU power samples cover only 57% of the run
- `dsh--mistral-nemo_12b--waste_4_conflicting_specs--2--20261105_200004`: GPU power samples cover only 79% of the run
- `dsh--mistral-nemo_12b--waste_4_conflicting_specs--5--20261105_200004`: GPU power samples cover only 95% of the run
- `dsh--mistral-nemo_12b--waste_4_conflicting_specs--6--20261105_200004`: GPU power samples cover only 92% of the run
- `dsh--mistral-nemo_12b--waste_4_conflicting_specs--7--20261105_200004`: GPU power samples cover only 58% of the run
- `dsh--mistral-nemo_12b--waste_4_conflicting_specs--8--20261105_200004`: GPU power samples cover only 89% of the run
- `dsh--mistral-nemo_12b--waste_4_conflicting_specs--9--20261105_200004`: GPU power samples cover only 96% of the run
- `dsh--mistral-nemo_12b--waste_4_conflicting_specs--10--20261105_200004`: GPU power samples cover only 93% of the run
- `dsh--mistral-nemo_12b--waste_5_ambiguous_edit--1--20261105_200004`: GPU power samples cover only 88% of the run
- `dsh--mistral-nemo_12b--waste_5_ambiguous_edit--2--20261105_200004`: GPU power samples cover only 78% of the run
- `dsh--mistral-nemo_12b--waste_5_ambiguous_edit--3--20261105_200004`: GPU power samples cover only 80% of the run
- `dsh--mistral-nemo_12b--waste_5_ambiguous_edit--6--20261105_200004`: GPU power samples cover only 90% of the run
- `dsh--mistral-nemo_12b--waste_5_ambiguous_edit--7--20261105_200004`: GPU power samples cover only 81% of the run
- `dsh--mistral-nemo_12b--waste_5_ambiguous_edit--9--20261105_200004`: GPU power samples cover only 96% of the run
- `dsh--mistral-nemo_12b--waste_5_ambiguous_edit--10--20261105_200004`: GPU power samples cover only 95% of the run
- `dsh--mistral-nemo_12b--waste_6_huge_output--3--20261105_200004`: GPU power samples cover only 94% of the run
- `dsh--mistral-nemo_12b--waste_6_huge_output--4--20261105_200004`: GPU power samples cover only 94% of the run
