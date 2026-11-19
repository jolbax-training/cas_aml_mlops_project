## ADDED Requirements

### Requirement: At-scale A-B-A repeat comparison
The repository SHALL support a second experiment, separate from the first, that holds the benchmark, evaluator, model/provider, generation settings, limits, container image and both prompts identical to the first and differs only in trials: ten independent trials of each of the ten tasks per run, with a fresh conversation per trial.

#### Scenario: Second configuration checked against the first
- **WHEN** the second experiment's configuration is checked against the first
- **THEN** the settings hash, model configuration, benchmark hash, limits, image and both prompt hashes are equal, and only the experiment identity, trials per task and schedule differ

#### Scenario: Verify a run's size
- **WHEN** a run's records are checked
- **THEN** one hundred task trials with four hidden check outcomes each are present

### Requirement: Three runs in A-B-A order
The second experiment SHALL run baseline, revised, then baseline again, each as a complete run with its own bundle, so the repeat measures run-to-run variation of one prompt and brackets provider drift.

#### Scenario: Repeat of the baseline
- **WHEN** the third run starts
- **THEN** it is a recorded decision to run the baseline a second time, it writes its own bundle and run marker, and it does not change the first baseline run

### Requirement: First-experiment data is never altered
Creating, running, analysing and recording the second experiment MUST NOT modify, delete, move or overwrite any file of the first: its configuration, evidence, retained bundles, run markers, documents, archived changes or MLflow runs. The second writes only to its own configuration, evidence directory, bundle directory and MLflow experiment name. The configuration, settings-freeze and probe writers MUST refuse to replace any existing file whose content would differ.

#### Scenario: Record written over an existing file
- **WHEN** a configuration, settings freeze or probe record that differs in content, whatever its experiment id or trial count, is written to the path of an existing file
- **THEN** the command refuses, names the path, and the existing file is byte-identical afterwards

#### Scenario: Existing commands without new options
- **WHEN** the configuration, check, run and compare commands are used with their previous arguments
- **THEN** they behave as before, including the first experiment's configuration passing its drift check

### Requirement: Spend ledger only used by the budget path
The analysis SHALL NOT open the spend ledger. The experiment commands read it and append to it only through the existing budget path (reservation, settlement, checkpoint events); no other step reads, rewrites or rotates it.

#### Scenario: Offline analysis
- **WHEN** the analysis runs
- **THEN** it reads only the given bundles and configuration, opens no ledger, makes no network call and writes nothing

### Requirement: Per-run analysis with Wilson intervals
The analysis SHALL read the retained bundles offline and report, for each run, the primary metric and diagnostics of the first comparison, successes out of ten per task, and a Wilson 95% interval for the overall success rate over the planned trials. Output MUST be deterministic for the same bundles.

#### Scenario: Interval for a perfect run
- **WHEN** a run succeeded in 100 of 100 planned trials
- **THEN** its interval has an upper end of 1.0 and a lower end below 1.0, computed from the counts alone

#### Scenario: Incomplete run
- **WHEN** a run is incomplete or does not match the schedule
- **THEN** its figures are reported over the planned denominator, labelled not headline-eligible, and no difference involving it is computed

### Requirement: Run-to-run and variant comparison
The analysis SHALL report baseline against revised and baseline against baseline repeat with the same metrics, per-task differences and whether the intervals overlap as a descriptive aid, and MUST NOT state a significance or improvement claim beyond what the intervals and counts show.

#### Scenario: Pair that differs by more than the prompt
- **WHEN** two compared runs differ in settings, evaluator code, benchmark or schedule beyond the intended prompt difference
- **THEN** the pair is reported as not comparable with the reasons

### Requirement: Claim limits of the at-scale comparison
The write-up SHALL present the comparison as the pipeline run at scale, not as proof of improvement, and MUST state that benchmark-informed tuning remains a limitation, that trials of one task are correlated although the intervals treat them as independent, that one repeat measures variation only roughly, and that one model and provider are covered. Interpretation left to the student MUST NOT be drafted.

#### Scenario: Repeat differs as much as the revision
- **WHEN** the baseline repeat differs from the first baseline run by about as much as the revised run does
- **THEN** the write-up says the revision's difference is within the observed run-to-run variation

### Requirement: Stop rules for the paid runs
The paid runs SHALL stop and ask the user when the actual charged spend of the second experiment's runs exceeds CHF 1, when any run ends incomplete, or when the ledger checkpoint is reached; the check is made between runs. The worst-case reservation projected before a run (about CHF 1.48 for three runs, against the CHF 15 ceiling) is accepted and is not a stop condition. An incomplete run MUST be preserved and labelled, and denominators MUST NOT be reduced.

#### Scenario: A run ends incomplete
- **WHEN** a run's bundle does not verify complete against the schedule
- **THEN** no further run starts until the user decides, and the partial bundle is retained

#### Scenario: Charged spend above the limit after a run
- **WHEN** the charged CHF summed over the finished runs of the second experiment exceeds 1
- **THEN** no further run starts until the user decides
