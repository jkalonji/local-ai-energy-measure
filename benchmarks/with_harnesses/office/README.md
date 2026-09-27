# Office task suite

Six office tasks of increasing difficulty, to measure whether a model, driven by an agent
harness, can do everyday spreadsheet and document work, and how reliably.

```bash
python benchmarks/with_harnesses/run_harness_benchmark.py --harness dsh --models qwen3:4b --suite office --repeat 10
```

Results: `results/with_harnesses/office_reliability.md` (pass rate per level, with a 95% Wilson
interval) and the usual `compatibility_matrix.md` (energy, time, requests per task).

## How a run works

- The harness gets a prompt in English and starts in an empty workspace, where it discovers the
  input files, in English too. They are generated reproducibly (fixed seed) by `generate.py`
  into `fixtures/<task_id>/`.
- Every prompt ends with: *"Python 3 is available from the shell, with openpyxl, python-docx and
  matplotlib installed."* Without it, small models conclude that binary `.xlsx`/`.docx` files
  cannot be handled, and levels 2 to 6 all fail on that single obstacle.
- `verify.py` checks the result against `expected/<task_id>.json`, which the agent never sees.
  Money is compared to the cent.
- A task fails if an input file is modified or deleted, or if the run is stopped by a limit
  (see below).
- Each task is meant to be run 10 times: the pass rate over the runs is the result, alongside
  GPU energy, duration and number of model requests.

## The tasks

### L1 - Total of a column (`office_1_sum_column`)

- **Input:** `sales.csv`, 40 orders (order_id, date, customer, product, quantity, unit_price, amount).
- **Asked:** the total of the `amount` column, rounded to 2 decimals.
- **Checked:** the final answer contains the exact total.
- **Tests:** reading one file and a simple computation; one answer, no file to write.

### L2 - CSV to a formatted Excel workbook (`office_2_xlsx_total`)

- **Input:** `expenses.csv`, 15 expense lines (Category, Description, Amount).
- **Asked:** `expenses.xlsx` with a sheet `Expenses`, bold headers, amounts stored as numbers, and
  a Total row holding a `SUM` formula.
- **Checked:** sheet name, headers and their bold font, every row in order with numeric amounts,
  and the exact formula `=SUM(C2:C16)` (a total computed by hand is refused).
- **Tests:** writing a binary Office file and following precise formatting instructions.

### L3 - Data cleaning and pivot table (`office_3_clean_pivot`)

- **Input:** `orders_raw.csv`, 60 Q1 2026 orders plus 8 duplicates, deliberately messy: dates in
  4 formats (`2026-03-28`, `03/28/2026`, `Mar 28, 2026`, `28-Mar-2026`), regions with
  inconsistent case and spaces (`west`, ` WEST `), amounts with `$` and thousands separators.
- **Asked:** `orders_clean.csv` (one row per order, sorted, ISO dates, normalized regions, plain
  numbers) and `region_month.csv` (total per region and month: 4 regions x 3 months).
- **Checked:** exact column names, the 60 rows one by one, and the 12 totals.
- **Tests:** a multi-step transformation of noisy data without getting a format wrong.

### L4 - Mail merge (`office_4_mail_merge`)

- **Input:** `letter_template.docx` (a letter with `{{first_name}}`, `{{company}}`,
  `{{renewal_date}}`, `{{amount}}`) and `contacts.xlsx` (10 customers, 3 of them inactive).
- **Asked:** `letters/<customer_id>.docx` for every active customer, and only for them, with the
  placeholders replaced.
- **Checked:** exactly 7 letters and none for an inactive customer, the right values in each, no
  `{{...}}` left, the rest of the template intact, and both inputs unchanged.
- **Tests:** joining two files, filtering, and producing several output files.

### L5 - Consolidated report (`office_5_sales_report`)

- **Input:** `sales_north.xlsx`, `sales_south.xlsx`, `sales_west.xlsx`, 20 to 30 sales each
  (date, product, units, unit_price).
- **Asked:** `quarterly_report.docx` with the title "Q1 2026 Sales Report", a Region / Revenue
  table ending with a Total row, a bar chart embedded as an image, and a sentence naming the
  region with the highest revenue.
- **Checked:** the title, each region's revenue and the total, the presence of an image, and the
  right region named.
- **Tests:** a long chain across several files, consistent figures from start to end, and a
  complete document as output.

### L6 - Missing data, a trap (`office_6_missing_rate`)

- **Input:** `sales_by_rep.xlsx` (sales of 6 reps) and `rates.csv` (commission rates of only 5 of
  them: one rep has none).
- **Asked:** `commissions.csv` (rep, sales, commission_rate, commission). The prompt says not to
  invent a missing value but to leave the cell empty and report it.
- **Checked:** the 5 computable commissions are right; the missing rep's rate and commission are
  empty, and any invented value fails the task; the final answer names the missing rate.
- **Tests:** spotting an anomaly and not inventing a value.

## Limits against runaway runs

Enforced by the runner, whatever the harness (`execute.watch_run`):

| Level | Max time | Max model requests |
|---|---|---|
| L1 | 10 min | 20 |
| L2 | 15 min | 40 |
| L3 | 20 min | 60 |
| L4 | 20 min | 60 |
| L5 | 25 min | 80 |
| L6 | 15 min | 40 |

A run is also stopped when, for 5 minutes, no model request finishes and the GPU is idle (a hung
command). A long generation keeps the GPU busy and is not stopped. Stopped runs are reported as
`timeout`, `loop_limit` or `stalled`, and count as failures.

## Files

| Path | Role |
|---|---|
| `../tasks/office_*.yaml` | Prompt, level, input folder, limits and check of each task |
| `generate.py` | Writes `fixtures/` and `expected/`; re-run it only to change the data |
| `fixtures/<task_id>/` | Input files, copied into the workspace of every run |
| `expected/<task_id>.json` | Ground truth, read by `verify.py` only |
| `verify.py` | Checks one run's result; the last line printed says why it failed |
| `../../../tests/test_office_suite.py` | A reference solution per level, and the mistakes `verify.py` must refuse |
