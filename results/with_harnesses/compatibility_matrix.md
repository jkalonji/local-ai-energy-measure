# Model x harness compatibility matrix

Each cell: tasks passed / runs · median GPU energy of a run. Energy is the GPU energy of the whole run (harness start-up, idle draw and tool time included), integrated from the driver's ~20 ms power samples of an RTX 5060 Ti; it is *not* the wall-socket power. Every run uses a fresh workspace and a context window of 32768 tokens. A task passes when its objective check passes (see `benchmarks/with_harnesses/tasks/`).

| Model | dsh |
|---|---|
| qwen3:4b | 3/3 · 0.93 Wh |

## Detail per task

| Model | Harness | Task | Result | Median energy | Median time | Energy in model calls | Requests |
|---|---|---|---|---|---|---|---|
| qwen3:4b | dsh | answer_arithmetic | 1 pass | 0.31 Wh | 31 s | 98% | 1 |
| qwen3:4b | dsh | fix_bug | 1 pass | 3.14 Wh | 346 s | 100% | 4 |
| qwen3:4b | dsh | write_file | 1 pass | 0.93 Wh | 101 s | 99% | 2 |
