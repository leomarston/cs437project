# SOLID Analyzer

Automated SOLID violation detection and refactoring framework powered by Google Gemini LLM.

**Course:** CS437 - Automated Detection and Refactoring of Software Design Issues
**Team:** S1-T5-SolidGuard
**Student:** Ahmet Yağız Sarıdoğan

## Overview

This framework automatically:
1. **Detects** SOLID principle violations in source code repositories using Gemini API
2. **Deduplicates** findings using an IssueID registry
3. **Refactors** detected violations using LLM-generated patches (applied programmatically)
4. **Validates** refactorings by running test suites and computing code quality metrics
5. **Reports** results with PR-style markdown reports and precision/recall/F1 evaluation
6. **Annotates** findings interactively for ground truth establishment

## Target Repositories

| Repository | Language | Detections | Refactorings |
|-----------|----------|------------|--------------|
| `alibaba/fastjson2` | Java | 60 (12/principle) | 60 (12/principle) |
| `Kotlin/kotlinx.coroutines` | Kotlin | 60 (12/principle) | 60 (12/principle) |
| `pallets/flask` | Python | 60 (12/principle) | 60 (12/principle) |
| **Total** | | **180** | **180** |

## SOLID Principles Covered

- **SRP** - Single Responsibility Principle (12 scans + 12 refactors per repo)
- **OCP** - Open/Closed Principle (12 scans + 12 refactors per repo)
- **LSP** - Liskov Substitution Principle (12 scans + 12 refactors per repo)
- **ISP** - Interface Segregation Principle (12 scans + 12 refactors per repo)
- **DIP** - Dependency Inversion Principle (12 scans + 12 refactors per repo)

## Quick Start

```bash
# 1. Install
pip install -e .

# 2. Set API key
export GEMINI_API_KEY="your-gemini-api-key"

# 3. Run everything
./run.sh
```

## Step-by-Step Usage

### Phase 1: Setup
```bash
pip install -e .
export GEMINI_API_KEY="your-key"
solid-analyzer clone all          # Clones all 3 repos into repos/
```

### Phase 2: Detection (60 scans per repo)
```bash
solid-analyzer detect fastjson2
solid-analyzer detect kotlinx-coroutines
solid-analyzer detect flask
```

Each detection run performs 12 scans per SOLID principle with varying:
- Prompt variants (standard, detailed, strict, contextual, educational, refactoring-focused)
- Temperature values (0.1 - 0.5)

### Phase 3: Manual Annotation (MANDATORY for grading)
```bash
solid-analyzer annotate fastjson2 --type detections
solid-analyzer annotate kotlinx-coroutines --type detections
solid-analyzer annotate flask --type detections
```

For each finding, you'll review and mark as:
- `y` = correct violation (true positive)
- `n` = not a real violation (false positive)
- `s` = skip for now
- `q` = quit

### Phase 4: Refactoring (60 attempts per repo)
```bash
solid-analyzer refactor fastjson2
solid-analyzer refactor kotlinx-coroutines
solid-analyzer refactor flask
```

Each refactoring:
1. Sends the violation + code to Gemini for a fix
2. Creates a git branch (`refactor/<issue-id>`)
3. Applies the patch programmatically
4. Runs the test suite
5. Commits if tests pass, rolls back if they fail
6. Generates a PR-style report

### Phase 5: Annotate Refactorings
```bash
solid-analyzer annotate fastjson2 --type refactorings
solid-analyzer annotate kotlinx-coroutines --type refactorings
solid-analyzer annotate flask --type refactorings
```

### Phase 6: Generate Reports
```bash
solid-analyzer report all
```

### Monitoring Progress
```bash
solid-analyzer status all         # Shows budget usage per repo per principle
```

### Seeding Violations (if repos are too clean)
```bash
solid-analyzer seed fastjson2 -n 5     # Inject 5 violations per principle
solid-analyzer seed flask -p SRP -n 3  # Inject 3 SRP violations
```

## Project Structure

```
cs437project/
├── run.sh                    # One-command full pipeline runner
├── pyproject.toml            # Dependencies and CLI entry point
├── data/
│   ├── repos.yaml            # Repository configuration
│   └── ground_truth/         # Manual annotations for F1 calculation
├── solid_analyzer/
│   ├── cli.py                # CLI (detect, refactor, annotate, seed, status, report)
│   ├── config.py             # Configuration management
│   ├── pipeline.py           # Main pipeline orchestrator
│   ├── seeder.py             # Violation injection for clean repos
│   ├── detector/
│   │   ├── gemini_client.py  # Gemini REST API client with retry/rate-limiting
│   │   ├── models.py         # Data models (Finding, RefactorResult, ScanReport)
│   │   ├── prompts.py        # 6 prompt variants per SOLID principle
│   │   ├── response_parser.py # Robust JSON parsing of LLM responses
│   │   └── deduplicator.py   # IssueID registry and dedup
│   ├── scanner/
│   │   ├── repo_manager.py   # Clone/update repositories
│   │   ├── file_selector.py  # Source file discovery (language-aware)
│   │   └── chunker.py        # Split large files for context window
│   ├── refactorer/
│   │   ├── refactor_planner.py # Generate refactoring plans via LLM
│   │   ├── patch_applier.py  # Apply patches with git branch management
│   │   └── test_runner.py    # Multi-language test execution
│   ├── metrics/
│   │   ├── code_quality.py   # Cyclomatic complexity, coupling, cohesion
│   │   └── evaluation.py     # Precision, recall, F1 computation
│   ├── reporter/
│   │   ├── pr_report.py      # Per-refactoring markdown PR reports
│   │   └── summary_report.py # Aggregate reports with metrics tables
│   ├── languages/
│   │   ├── java.py           # Java (Maven/Gradle)
│   │   ├── kotlin.py         # Kotlin (Gradle)
│   │   └── python.py         # Python (pytest)
│   └── utils/
│       ├── budget.py         # Per-principle budget enforcement
│       ├── logging.py        # Structured logging
│       └── git_utils.py      # Git operations
├── repos/                    # (runtime) Cloned target repositories
└── output/                   # (runtime) All results
    ├── findings/             # Detection results (JSON registry + CSV + scan reports)
    ├── refactors/            # Refactoring results + PR reports (markdown)
    ├── reports/              # Summary reports with metrics
    ├── seeds/                # Seeded violation logs
    └── budget_state.json     # Budget tracking state
```

## Output Details

### Detection Output
- `output/findings/<repo>_registry.json` - All findings with dedup and annotations
- `output/findings/<repo>_findings.csv` - CSV export for analysis
- `output/findings/<repo>/scans/scan_<PRINCIPLE>_<N>.json` - Per-scan reports

### Refactoring Output
- `output/refactors/<repo>_results.json` - All refactoring results
- `output/refactors/<repo>/PR_<id>_<PRINCIPLE>.md` - PR-style reports

### Summary Reports
- `output/reports/summary_<repo>_<timestamp>.md` - Full metrics dashboard

## Deduplication

Each finding gets an IssueID: `hash(principle + file_path + symbol_name + line_range)`

Duplicate detection uses:
1. Exact match on (principle, file, symbol)
2. Overlapping line ranges with >60% description similarity

Duplicates are tracked but not counted as new unique issues.

## Metrics

### Code Quality (before/after each refactoring)
- Cyclomatic complexity (via `radon` for Python, heuristic for Java/Kotlin)
- Lines of code
- Method count and average length
- Import count (coupling indicator)
- Comment ratio

### Evaluation (after manual annotation)
- **Precision** = TP / (TP + FP) across full detection budget
- **Recall** = TP / (TP + FN) based on ground truth audit
- **F1** = 2 * (Precision * Recall) / (Precision + Recall)
