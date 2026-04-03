# Initial Results: Comparison with LOCALIZEAGENT

**Paper:** "An LLM-Based Agent-Oriented Approach for Automated Code Design Issue Localization" (ICSE 2025)
**Authors:** Fraol Batole, David O'Brien, Tien N. Nguyen, Robert Dyer, Hridesh Rajan
**Student:** Ahmet Yağız Sarıdoğan

---

## 1. Paper Summary (LOCALIZEAGENT)

### Problem
Detecting code design issues (poor modularity, tight coupling, excessive complexity) in large codebases is challenging. Directly using LLMs fails because: (1) large codebases exceed context windows, and (2) static analysis outputs (graphs, metrics) are incompatible with LLM text inputs.

### Approach
LOCALIZEAGENT is a multi-agent framework with 4 specialized agents:

| Agent | Role |
|-------|------|
| **Analysis Agent** | Runs PMD static analysis to detect potential design issues |
| **Summarization Agent** | Transforms PMD outputs into LLM-friendly natural language |
| **Prompt Agent** | Generates context-aware prompts tailored to each refactoring type |
| **Localization Agent** | Uses LLM to rank and localize issues by relevance |

### Design Issues Detected (via 8 PMD rules)
| Category | PMD Rules |
|----------|-----------|
| **Modularity** | God Class, Coupling Between Objects, Data Class |
| **Information Hiding** | Law of Demeter, Excessive Parameter List |
| **Complexity** | Too Many Methods, Excessive Public Count, Cyclomatic Complexity |

### Key Results
- **138%** relative improvement for information hiding issues
- **166%** relative improvement for complexity issues
- **206%** relative improvement for modularity issues
- Uses a cooperative multi-agent communication paradigm

---

## 2. Our Approach (SOLID Analyzer)

### Architecture Comparison

| Aspect | LOCALIZEAGENT | Our Approach (SOLID Analyzer) |
|--------|--------------|-------------------------------|
| **LLM** | GPT-based models | Google Gemini 2.0 Flash |
| **Static Analysis** | PMD (8 rules) | LLM-only (no static analysis pre-filter) |
| **Architecture** | Multi-agent (4 agents) | Single pipeline with prompt variants |
| **Design Focus** | Modularity, Info Hiding, Complexity | SOLID (SRP, OCP, LSP, ISP, DIP) |
| **Languages** | Java | Java, Kotlin, Python |
| **Prompt Strategy** | Context-aware per refactoring type | 6 variants (standard, detailed, strict, contextual, educational, refactoring-focused) |
| **Deduplication** | Not described | IssueID registry with similarity matching |
| **Validation** | Manual evaluation | Auto-annotation + test execution + metrics |

### Mapping Between Approaches

| LOCALIZEAGENT Category | SOLID Principle Equivalent | Overlap |
|----------------------|---------------------------|---------|
| God Class (Modularity) | SRP - Single Responsibility | High |
| Coupling Between Objects | DIP - Dependency Inversion | High |
| Data Class (Modularity) | SRP - Single Responsibility | Medium |
| Law of Demeter (Info Hiding) | DIP - Dependency Inversion | Medium |
| Excessive Parameters (Info Hiding) | ISP - Interface Segregation | Medium |
| Too Many Methods (Complexity) | ISP - Interface Segregation | High |
| Excessive Public Count (Complexity) | ISP - Interface Segregation | Medium |
| Cyclomatic Complexity | SRP - Single Responsibility | Medium |

---

## 3. Initial Results from Our Framework

### Budget Completion

| Repository | Language | Detections | Refactorings |
|-----------|----------|------------|--------------|
| alibaba/fastjson2 | Java | 60/60 (100%) | 60/60 (100%) |
| Kotlin/kotlinx.coroutines | Kotlin | 60/60 (100%) | 60/60 (100%) |
| pallets/flask | Python | 60/60 (100%) | 60/60 (100%) |
| **Total** | | **180/180** | **180/180** |

### Ground Truth (Auto-Annotated Correct Violations)

| Repository | SRP | OCP | LSP | ISP | DIP | Total |
|-----------|-----|-----|-----|-----|-----|-------|
| fastjson2 | - | - | - | 31 | - | **31** |
| flask | - | - | 3 | 9 | 5 | **17** |
| kotlinx-coroutines | - | - | - | - | - | **0** |
| **Total** | **0** | **0** | **3** | **40** | **5** | **48** |

### Observations

1. **ISP dominates:** 40 out of 48 confirmed violations (83%) are Interface Segregation Principle violations. This aligns with LOCALIZEAGENT's finding that "Excessive Public Count" and "Too Many Methods" (both ISP-related) are common in large codebases.

2. **SRP/OCP gaps:** The auto-annotator marked most SRP and OCP findings as incorrect (false positives). This suggests that:
   - LLMs tend to over-report SRP violations (labeling any large class as violating SRP)
   - OCP violations are harder to detect without runtime/extension analysis
   - This is consistent with LOCALIZEAGENT's approach of using static analysis as a pre-filter

3. **Language effect:** kotlinx-coroutines had 0 confirmed violations, possibly because:
   - Kotlin's language features (data classes, extension functions) naturally prevent many SOLID violations
   - The codebase is well-designed (maintained by JetBrains)

4. **fastjson2 most violations:** 31 confirmed ISP violations — consistent with the codebase having large reader/writer classes with many methods (fat interfaces), similar to what LOCALIZEAGENT would detect as "Excessive Public Count."

### Detection Precision (Initial Estimate)

Based on auto-annotations (correct vs incorrect findings):

| Repository | Correct (TP) | Total Unique | Estimated Precision |
|-----------|-------------|-------------|-------------------|
| fastjson2 | 31 | ~60+ | ~50% |
| flask | 17 | ~60+ | ~28% |
| kotlinx-coroutines | 0 | ~60+ | ~0% |

**Note:** These are initial estimates from auto-annotation. Manual review may adjust these numbers. Recall calculation requires a full manual audit of the codebase to identify false negatives.

---

## 4. Key Differences and Insights

### What LOCALIZEAGENT Does Better
1. **Pre-filtering with PMD:** By running static analysis first, LOCALIZEAGENT avoids sending irrelevant code to the LLM, reducing false positives
2. **Multi-agent specialization:** Each agent focuses on one task, improving output quality
3. **Abstraction-aware summaries:** Converting analysis outputs to natural language helps the LLM understand context better

### What Our Approach Does Differently
1. **Broader scope:** We detect 5 SOLID principles vs. 3 design categories
2. **Multi-language:** Java, Kotlin, Python vs. Java only
3. **Full automation:** Detection + refactoring + testing + reporting in one pipeline
4. **Prompt diversity:** 6 prompt variants × 12 temperature variations per principle
5. **Budget tracking:** Systematic 60/60 per repo with deduplication

### Potential Improvements (Inspired by LOCALIZEAGENT)
1. Add a **static analysis pre-filter** (PMD for Java, detekt for Kotlin, pylint for Python) before sending code to the LLM
2. Implement a **multi-agent architecture** where separate agents handle detection, verification, and refactoring
3. Add a **summarization step** to convert code structure information into natural language before prompting

---

## 5. Conclusion

Our SOLID Analyzer framework successfully completed the full 180/180 detection and refactoring budget across 3 repositories in 3 languages. Initial results show that ISP violations are the most reliably detected (83% of confirmed findings), while SRP and OCP detection has higher false positive rates.

Compared to LOCALIZEAGENT, our approach trades the precision of static-analysis-backed detection for broader coverage across principles and languages. The key takeaway from LOCALIZEAGENT that could improve our results is the use of **static analysis as a pre-filter** to reduce false positives before LLM-based analysis.
