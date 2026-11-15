# Experiment records

When changing processing logic, architecture, clocks, data-transfer interfaces,
buffering, numeric precision, or measurement scope, update `docs/experiment_log.md`
in the same working change.

The experiment journal is for changes affecting correctness, performance or
resource use. Do not create experiment entries or report artifacts for script
syntax/compatibility fixes, path corrections, file copies or routine environment
setup that do not change processing logic or measurement conditions.

- Assign a stable experiment ID. Record the problem, hypothesis, changed files
  and parameters, test command, measured scope, result, interpretation and next step.
- Separate board measurements, user-reported console evidence, simulation results
  and cycle-derived estimates. Never fill a missing measurement with a prediction.
- Preserve logic/performance experiment failures and superseded conclusions. Keep
  historical measured results unchanged and link later experiments instead.
- Retain compact evidence under `benchmarks/reports/<date>-<experiment>/` and exact
  source/configuration identities. Build projects and firmware binaries stay in
  ignored `build/`; record their paths and hashes when available.
- Record missing raw files and unverified build/board status explicitly. Store
  new measurements in separate result directories. Document confounding changes
  when multiple variables are changed together.
- Keep the experiment index and current-status links up to date. Documentation
  edits alone do not require repeating hardware builds or performance tests.
- Use target-compatible Tcl constructs for Vivado scripts, with cleanup and
  preserved error options. Host support alone does not establish compatibility.
