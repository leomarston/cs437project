# SOLID Analyzer

Automated SOLID violation detection and refactoring framework powered by Google Gemini LLM.

**Course:** CS437 - Automated Detection and Refactoring of Software Design Issues
**Team:** S1-T5-SolidGuard
**Student:** Ahmet Yağız Sarıdoğan

## Overview

This framework automatically:
1. **Detects** SOLID principle violations in source code repositories
2. **Refactors** detected violations using LLM-generated patches
3. **Validates** refactorings by running test suites and computing quality metrics
4. **Reports** results with PR-style reports and precision/recall/F1 evaluation

## Target Repositories

| Repository | Language | Budget |
|-----------|----------|--------|
| `alibaba/fastjson2` | Java | 60 detect + 60 refactor |
| `Kotlin/kotlinx.coroutines` | Kotlin | 60 detect + 60 refactor |
| `pallets/flask` | Python | 60 detect + 60 refactor |

## SOLID Principles Covered

- **SRP** - Single Responsibility Principle
- **OCP** - Open/Closed Principle
- **LSP** - Liskov Substitution Principle
- **ISP** - Interface Segregation Principle
- **DIP** - Dependency Inversion Principle

Each principle gets 12 detection scans and 12 refactoring attempts per repository.

## Setup

```bash
# Install dependencies
pip install -e .

# Set API key
export GEMINI_API_KEY="your-key-here"
```

## Usage

```bash
# Clone target repositories
solid-analyzer clone all

# Run detection on a specific repo
solid-analyzer detect fastjson2

# Run refactoring
solid-analyzer refactor fastjson2

# Run full pipeline (detect + refactor + report)
solid-analyzer run fastjson2

# Run for all repos
solid-analyzer run all

# Check budget status
solid-analyzer status all

# Generate reports from existing data
solid-analyzer report all
```

## Project Structure

```
solid_analyzer/
├── cli.py                  # CLI entry point
├── config.py               # Configuration management
├── pipeline.py             # Main pipeline orchestrator
├── detector/
│   ├── gemini_client.py    # Gemini API wrapper
│   ├── models.py           # Data models (Finding, RefactorResult)
│   ├── prompts.py          # Prompt templates per SOLID principle
│   ├── response_parser.py  # Parse LLM responses
│   └── deduplicator.py     # Issue registry and dedup
├── scanner/
│   ├── repo_manager.py     # Clone/manage repositories
│   ├── file_selector.py    # Source file discovery
│   └── chunker.py          # Split large files for analysis
├── refactorer/
│   ├── refactor_planner.py # Generate refactoring plans via LLM
│   ├── patch_applier.py    # Apply patches with git branch mgmt
│   └── test_runner.py      # Run test suites
├── metrics/
│   ├── code_quality.py     # Cyclomatic complexity, coupling, etc.
│   └── evaluation.py       # Precision, recall, F1 computation
├── reporter/
│   ├── pr_report.py        # Per-refactoring PR reports
│   └── summary_report.py   # Aggregate summary reports
├── languages/
│   ├── base.py             # Language handler interface
│   ├── java.py             # Java-specific operations
│   ├── kotlin.py           # Kotlin-specific operations
│   └── python.py           # Python-specific operations
└── utils/
    ├── budget.py            # API call budget tracker
    ├── logging.py           # Structured logging
    └── git_utils.py         # Git operations
```

## Output

Results are stored in the `output/` directory:
- `output/findings/` - Detection results per repo (JSON + CSV)
- `output/refactors/` - Refactoring results and PR reports
- `output/reports/` - Summary reports with metrics
- `output/budget_state.json` - Budget tracking state
