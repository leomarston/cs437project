"""Prompt templates for SOLID principle violation detection and refactoring."""

PRINCIPLE_DESCRIPTIONS = {
    "SRP": (
        "Single Responsibility Principle (SRP): A class should have only one reason to change. "
        "It should have a single, well-defined responsibility. Violations include classes that "
        "handle multiple concerns (e.g., business logic + persistence + UI), god classes, and "
        "methods that perform unrelated tasks."
    ),
    "OCP": (
        "Open/Closed Principle (OCP): Software entities should be open for extension but closed "
        "for modification. Violations include code that requires modifying existing classes to add "
        "new behavior, switch/if-else chains on type codes, and lack of abstraction points for "
        "extending functionality."
    ),
    "LSP": (
        "Liskov Substitution Principle (LSP): Subtypes must be substitutable for their base types "
        "without altering the correctness of the program. Violations include subclasses that throw "
        "unexpected exceptions, override methods to do nothing, strengthen preconditions, or weaken "
        "postconditions."
    ),
    "ISP": (
        "Interface Segregation Principle (ISP): Clients should not be forced to depend on interfaces "
        "they do not use. Violations include fat interfaces with too many methods, classes that "
        "implement interfaces but leave methods empty or throw NotImplementedError, and overly broad "
        "abstract base classes."
    ),
    "DIP": (
        "Dependency Inversion Principle (DIP): High-level modules should not depend on low-level "
        "modules; both should depend on abstractions. Violations include direct instantiation of "
        "concrete dependencies, hard-coded class references instead of interfaces, and lack of "
        "dependency injection."
    ),
}

# Multiple prompt variants per principle for varied scans
PROMPT_VARIANTS = {
    "standard": "Analyze the following {language} code for violations of the {principle_name}.",
    "detailed": (
        "Perform a thorough analysis of the following {language} code. "
        "Focus specifically on identifying violations of the {principle_name}. "
        "Consider class responsibilities, method cohesion, and design patterns."
    ),
    "strict": (
        "As a senior software architect, critically review the following {language} code "
        "for any violations of the {principle_name}. Be strict in your assessment. "
        "Even minor violations should be flagged."
    ),
    "contextual": (
        "Given that this code is from the {repo_name} project, analyze it for violations "
        "of the {principle_name}. Consider the project's domain and common patterns in "
        "{language} development."
    ),
    "educational": (
        "Review the following {language} code as if teaching a student about the {principle_name}. "
        "Identify any violations and explain why they are problematic in terms of maintainability, "
        "testability, and design quality."
    ),
    "refactoring_focused": (
        "Analyze the following {language} code for violations of the {principle_name}. "
        "For each violation found, focus on how it could be refactored. Prioritize violations "
        "that would benefit most from refactoring."
    ),
}

DETECTION_PROMPT_TEMPLATE = """
{variant_instruction}

{principle_description}

## Code to Analyze
**File:** `{file_path}`
**Lines:** {start_line}-{end_line}
**Language:** {language}

```{language}
{code}
```

## Instructions
Identify ALL violations of the {principle_short} principle in this code.
For each violation found, provide:
1. The specific symbol (class/method/function name) that violates the principle
2. The exact line range where the violation occurs
3. A clear description of the violation
4. The reasoning for why this is a violation
5. The severity (low, medium, high, critical)
6. A brief suggestion for how to fix it

Return your analysis as a JSON array. If no violations are found, return an empty array [].

JSON Schema:
```json
[
  {{
    "symbol_name": "ClassName or methodName",
    "line_start": 1,
    "line_end": 50,
    "description": "Brief description of the violation",
    "reasoning": "Detailed explanation of why this violates {principle_short}",
    "severity": "low|medium|high|critical",
    "suggested_fix": "Brief description of recommended refactoring"
  }}
]
```
"""

REFACTORING_PROMPT_TEMPLATE = """
You are a senior software engineer tasked with refactoring code to fix a {principle_short} violation.

## Violation Details
- **Principle:** {principle_name}
- **File:** `{file_path}`
- **Symbol:** `{symbol_name}`
- **Lines:** {line_start}-{line_end}
- **Description:** {description}
- **Reasoning:** {reasoning}

## Original Code
```{language}
{original_code}
```

## Instructions
Refactor this code to resolve the {principle_short} violation described above.

Requirements:
1. Fix the identified violation while preserving the existing functionality
2. Follow {language} best practices and conventions
3. Keep changes minimal and focused on the violation
4. Maintain backward compatibility where possible
5. Include any new files/classes that need to be created

Return your response as JSON with the following structure:
```json
{{
  "explanation": "Description of what was changed and why",
  "refactored_files": [
    {{
      "file_path": "path/to/file.ext",
      "action": "modify|create",
      "content": "Full file content after refactoring"
    }}
  ]
}}
```
"""


def build_detection_prompt(
    principle: str,
    code: str,
    file_path: str,
    language: str,
    start_line: int,
    end_line: int,
    variant: str = "standard",
    repo_name: str = "",
) -> str:
    """Build a complete detection prompt for a given principle and code chunk."""
    variant_template = PROMPT_VARIANTS.get(variant, PROMPT_VARIANTS["standard"])
    variant_instruction = variant_template.format(
        language=language,
        principle_name=PRINCIPLE_DESCRIPTIONS[principle],
        repo_name=repo_name,
    )

    return DETECTION_PROMPT_TEMPLATE.format(
        variant_instruction=variant_instruction,
        principle_description=PRINCIPLE_DESCRIPTIONS[principle],
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        language=language,
        code=code,
        principle_short=principle,
    )


def build_refactoring_prompt(
    principle: str,
    original_code: str,
    file_path: str,
    language: str,
    symbol_name: str,
    line_start: int,
    line_end: int,
    description: str,
    reasoning: str,
) -> str:
    """Build a refactoring prompt for a specific violation."""
    return REFACTORING_PROMPT_TEMPLATE.format(
        principle_short=principle,
        principle_name=PRINCIPLE_DESCRIPTIONS[principle],
        file_path=file_path,
        symbol_name=symbol_name,
        line_start=line_start,
        line_end=line_end,
        description=description,
        reasoning=reasoning,
        language=language,
        original_code=original_code,
    )
