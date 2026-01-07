# Bug Audit Checklist

> **Purpose**: Comprehensive checklist of bugs, antipatterns, and pitfalls common in AI-generated code and ML/research codebases (2025-2026). Use this to continuously audit the codebase.
>
> **Usage**: Run periodic audits against this checklist. Check items off as verified clean. Document any findings in `docs/_bugs/`.

---

## Quick Reference: Critical Bug Categories

| Priority | Category | Risk Level | Common in AI Code? |
|----------|----------|------------|-------------------|
| P0 | Silent Exception Swallowing | Critical | 1.75x more common |
| P0 | Hardcoded Secrets/Credentials | Critical | 2.74x more common |
| P1 | Silent Type Coercion Data Loss | High | Very common |
| P1 | Silent Fallbacks Masking Failures | High | Very common |
| P2 | Race Conditions in Async Code | High | Common |
| P2 | Mock Overuse Creating False Positives | High | Common |
| P3 | Schema Drift / Data Pipeline Corruption | Medium | Common in ML |
| P3 | JSON Serialization Edge Cases | Medium | Common |
| P4 | Over-Engineering / Premature Abstraction | Low | Very common |
| P1 | Python Truthiness Traps | High | Very common |
| P2 | Mutable Default Arguments | High | Classic gotcha |
| P2 | Floating Point & Numerical Bugs | High | Common in ML |
| P1 | ML Reproducibility Bugs | High | Critical for research |
| P0 | Data Leakage / Train-Test Contamination | Critical | 648 papers affected |
| P3 | Off-by-One & Fencepost Errors | Medium | Classic |
| P3 | Resource & Connection Leaks | Medium | Common |
| P3 | Circular Imports | Medium | Common with types |
| P2 | Hallucinated APIs/Libraries | High | AI-specific |
| P3 | TODO/FIXME Incomplete Implementations | Medium | AI leaves stubs |

---

## 1. Silent Exception Swallowing

**Risk**: Critical (P0) — 40% of bug investigations stem from silent failures (2025 PSF Survey)

### What to Look For

- [ ] **Bare `except:` clauses** — Catches everything including `KeyboardInterrupt`, `SystemExit`
- [ ] **`except Exception: pass`** — Swallows errors silently with no logging
- [ ] **`except Exception as e:` without re-raise or log** — Error captured but ignored
- [ ] **Overly broad try blocks** — Wrapping entire functions instead of specific risky lines
- [ ] **Missing `raise` in exception handlers** — Handler "handles" but doesn't propagate

### Bad Pattern
```python
# DANGEROUS: Silent failure
try:
    result = risky_operation()
except Exception:
    pass  # Ghost bug - failure invisible
```

### Good Pattern
```python
# CORRECT: Explicit suppression with logging
try:
    result = risky_operation()
except SpecificError as e:
    logger.warning(f"Expected failure handled: {e}")
    result = fallback_value
```

### Sources
- [Avoiding Silent Failures in Python - Index.dev](https://www.index.dev/blog/avoid-silent-failures-python)
- [Python Errors Should Not Pass Silently - Pybites](https://pybit.es/articles/python-errors-should-not-pass-silently/)
- [Best Practices for Exception Handling - MoldStud](https://moldstud.com/articles/p-best-practices-for-exception-handling-in-python-oop-mastering-error-management)

---

## 2. Silent Fallbacks Masking Failures

**Risk**: High (P1) — Creates "successful" pipelines that silently corrupt data

### What to Look For

- [ ] **Default values hiding failures** — `result = api_call() or default_value`
- [ ] **`getattr(obj, 'field', None)`** without checking if None is valid
- [ ] **`dict.get(key, default)`** where default masks missing required data
- [ ] **Optional parameters with dangerous defaults** — `timeout=None` meaning infinite
- [ ] **Retry loops that give up silently** — Max retries exhausted, returns empty
- [ ] **Fallback to empty collections** — `return []` when API fails

### Bad Pattern
```python
# DANGEROUS: Silent fallback masks failure
def get_scores():
    try:
        return fetch_from_api()
    except Exception:
        return []  # Looks like success with no data
```

### Good Pattern
```python
# CORRECT: Explicit failure or documented fallback
def get_scores() -> list[Score]:
    try:
        return fetch_from_api()
    except ApiError as e:
        logger.error(f"API failed: {e}")
        raise  # Let caller decide how to handle
```

### Sources
- [When 'Successful' Pipelines Quietly Corrupt Your Data - Medium](https://medium.com/towards-data-engineering/when-successful-pipelines-quietly-corrupt-your-data-4a134544bb73)
- [The AI Developer Crisis of 2025 - Medium](https://medium.com/@dalio8/the-ai-developer-crisis-of-2025-6-hidden-failures-breaking-your-codebase-and-your-career-3eec01059360)

---

## 3. Silent Type Coercion & Data Loss

**Risk**: High (P1) — Pydantic/Python silently truncates data

### What to Look For

- [ ] **`int` fields receiving floats** — `10.9` → `10` (silent truncation)
- [ ] **`Union[int, float]`** — Float may be coerced to int unexpectedly
- [ ] **String to number coercion** — `"123abc"` behavior varies
- [ ] **Datetime string parsing without timezone** — Silent UTC assumption
- [ ] **Enum value coercion** — String coerced to enum silently
- [ ] **Decimal precision loss** — Float intermediates in calculations
- [ ] **Missing `StrictInt`, `StrictFloat`, `StrictStr`** in Pydantic models

### Bad Pattern
```python
# DANGEROUS: Silent data loss
class Config(BaseModel):
    threshold: int  # 10.9 becomes 10 silently

Config(threshold=10.9)  # No error, data lost
```

### Good Pattern
```python
# CORRECT: Strict typing prevents silent coercion
from pydantic import StrictInt

class Config(BaseModel):
    threshold: StrictInt  # 10.9 raises ValidationError
```

### Sources
- [Pydantic Drawbacks with Examples - Hrekov](https://hrekov.com/blog/pydantic-drawbacks)
- [Pydantic Strict Mode Documentation](https://docs.pydantic.dev/latest/concepts/strict_mode/)
- [Mastering Type-Safe Python - Toolshelf](https://toolshelf.tech/blog/mastering-type-safe-python-pydantic-mypy-2025/)

---

## 4. Hardcoded Secrets & Credentials

**Risk**: Critical (P0) — 90,000+ leaked env vars identified in 2025 research

### What to Look For

- [ ] **API keys in source code** — `api_key = "sk-..."`
- [ ] **Passwords in config files** — Even in "local only" files
- [ ] **Database connection strings with credentials**
- [ ] **`.env` files committed to git** — Check `.gitignore`
- [ ] **Secrets in environment variables** — Better than hardcoded, still risky
- [ ] **Tokens in URL parameters** — Logged in server access logs
- [ ] **Test credentials in production code paths**
- [ ] **Default passwords in configuration**

### Bad Pattern
```python
# DANGEROUS: Hardcoded secret
OPENAI_API_KEY = "sk-abc123..."  # Committed to git
```

### Good Pattern
```python
# CORRECT: Secrets manager at runtime
from functools import lru_cache
import os

@lru_cache
def get_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError("OPENAI_API_KEY not set")
    return key
```

### Sources
- [Are Environment Variables Still Safe for Secrets in 2026? - Security Boulevard](https://securityboulevard.com/2025/12/are-environment-variables-still-safe-for-secrets-in-2026/)
- [Environment Variables Hidden Security Risks - Medium](https://medium.com/@instatunnel/how-your-environment-variables-can-betray-you-in-production-the-hidden-security-risks-developers-d77200b5cda9)
- [Storing Secrets in Env Vars Considered Harmful - Arcjet](https://blog.arcjet.com/storing-secrets-in-env-vars-considered-harmful/)

---

## 5. Async/Await Race Conditions

**Risk**: High (P2) — Intermittent, hard to reproduce

### What to Look For

- [ ] **Check-then-act without lock** — `if not exists: await create()`
- [ ] **Shared mutable state across coroutines** — Dicts, lists modified by multiple tasks
- [ ] **Await between check and modify** — Window for interleaving
- [ ] **Blocking calls in async code** — CPU-bound work blocking event loop
- [ ] **Thread-unsafe asyncio objects** — Called from non-async context
- [ ] **Unhandled task exceptions** — Fire-and-forget `asyncio.create_task()`
- [ ] **Missing `asyncio.Lock()` for critical sections**

### Bad Pattern
```python
# DANGEROUS: Race condition between await calls
async def add_user(user_id: str):
    if user_id not in users:  # Check
        await db.create_user(user_id)  # Another coroutine can interleave here!
        users.add(user_id)  # Act
```

### Good Pattern
```python
# CORRECT: Lock protects critical section
lock = asyncio.Lock()

async def add_user(user_id: str):
    async with lock:
        if user_id not in users:
            await db.create_user(user_id)
            users.add(user_id)
```

### Sources
- [Avoiding Race Conditions in Python 2025 - Medium](https://medium.com/pythoneers/avoiding-race-conditions-in-python-in-2025-best-practices-for-async-and-threads-4e006579a622)
- [Python Dictionary Async-Safety - Medium](https://medium.com/@goldengrisha/is-pythons-dictionary-async-safe-why-you-can-still-get-race-conditions-in-async-code-c786412af567)
- [Python Asyncio Documentation](https://docs.python.org/3/library/asyncio-dev.html)

---

## 6. Mock Overuse & Test False Positives

**Risk**: High (P2) — Tests pass but production fails

### What to Look For

- [ ] **Mocking internal logic instead of external dependencies**
- [ ] **Missing `autospec=True`** — Mocks accept any signature
- [ ] **Global module patches** — `@patch('requests.post')` affects all code
- [ ] **Tests that verify mock was called, not behavior**
- [ ] **Mocked return values that don't match real API**
- [ ] **Test-only methods polluting production code**
- [ ] **Tests that only test the mock, not real behavior**

### Bad Pattern
```python
# DANGEROUS: Mock accepts wrong signature silently
@patch('module.api_call')
def test_function(mock_call):
    mock_call.return_value = {"data": []}
    result = function_under_test("arg1", "arg2", "EXTRA_ARG")  # No error!
```

### Good Pattern
```python
# CORRECT: autospec enforces real signature
@patch('module.api_call', autospec=True)
def test_function(mock_call):
    mock_call.return_value = {"data": []}
    result = function_under_test("arg1", "arg2")  # Extra arg would raise TypeError
```

### Sources
- [Common Mocking Problems - Pytest with Eric](https://pytest-with-eric.com/mocking/pytest-common-mocking-problems/)
- [Testing Anti-Patterns - Claude Skills](https://claude-plugins.dev/skills/@maxritter/claude-codepro/testing-anti-patterns)
- [Python Testing Best Practices - DEV](https://dev.to/nkpydev/python-testing-unit-tests-pytest-and-best-practices-45gl)

---

## 7. Data Pipeline / Schema Drift

**Risk**: Medium (P3) — "Silent pipeline breaker"

### What to Look For

- [ ] **No schema validation on ingestion** — Accepting any shape
- [ ] **Partial data loads treated as success** — 60% of records, no error
- [ ] **Column renames in source not detected**
- [ ] **New enum values not handled** — `default: pass`
- [ ] **Nullable fields becoming non-nullable** — Or vice versa
- [ ] **Distribution drift** — 10% nulls → 90% nulls
- [ ] **No data quality assertions** — Row counts, null checks, range checks
- [ ] **ETL "success" with empty results**

### Bad Pattern
```python
# DANGEROUS: No validation, silent corruption
def process_data(raw: dict) -> ProcessedData:
    return ProcessedData(
        user_id=raw.get("user_id"),  # Could be None
        score=raw.get("score", 0),   # 0 masks missing data
    )
```

### Good Pattern
```python
# CORRECT: Explicit validation with assertions
def process_data(raw: dict) -> ProcessedData:
    assert "user_id" in raw, "Missing required field: user_id"
    assert raw["user_id"] is not None, "user_id cannot be null"

    score = raw.get("score")
    if score is None:
        raise ValueError("Missing required field: score")

    return ProcessedData(user_id=raw["user_id"], score=score)
```

### Sources
- [Schema Drift: The Silent Pipeline Breaker - Medium](https://medium.com/@adilshk047/schema-drift-the-silent-data-pipeline-breaker-how-it-happens-why-it-hurts-and-how-to-fix-it-3bf838662d3d)
- [5 Critical ETL Pipeline Pitfalls - Airbyte](https://airbyte.com/data-engineering-resources/etl-pipeline-pitfalls-to-avoid)
- [Data Quality Challenges in Production ETL - Medium](https://medium.com/@kavyanandesh/4-common-data-quality-challenges-in-production-etl-pipelines-and-how-to-fix-them-02f884d935ba)

---

## 8. JSON Serialization Edge Cases

**Risk**: Medium (P3) — Crashes in production on edge case data

### What to Look For

- [ ] **`datetime` objects not serializable** — Works until one record has datetime
- [ ] **`Decimal` precision loss via float** — Financial calculations corrupted
- [ ] **`Enum` members not serializable** — `MyEnum.VALUE` fails
- [ ] **`UUID` objects not serializable**
- [ ] **`dataclass` instances not handled**
- [ ] **`None` vs `"null"` string confusion**
- [ ] **Bytes objects in JSON payloads**
- [ ] **Circular references causing infinite loops**

### Bad Pattern
```python
# DANGEROUS: Crashes on datetime
import json
data = {"created_at": datetime.now()}
json.dumps(data)  # TypeError: Object of type datetime is not JSON serializable
```

### Good Pattern
```python
# CORRECT: Custom encoder or library
import json
from datetime import datetime

def json_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

json.dumps(data, default=json_serializer)

# Or use orjson which handles datetime/enum natively
import orjson
orjson.dumps(data)
```

### Sources
- [Fixing datetime not JSON serializable - GeeksforGeeks](https://www.geeksforgeeks.org/python/how-to-fix-datetime-datetime-not-json-serializable-in-python/)
- [Fix TypeError Object Not JSON Serializable - SethServer](https://www.sethserver.com/python/typeerror-object-not-json-serializable.html)
- [orjson - Fast Python JSON library](https://github.com/ijl/orjson)

---

## 9. LLM/AI-Specific Vulnerabilities

**Risk**: High — AI code is 1.57x-2.74x more likely to have security issues

### What to Look For

- [ ] **SQL injection in generated queries** — String interpolation, no parameterization
- [ ] **Command injection** — `os.system(f"cmd {user_input}")`
- [ ] **XSS vulnerabilities** — Unescaped user content in HTML (2.74x more common)
- [ ] **Insecure deserialization** — `pickle.loads(untrusted)` (1.82x more common)
- [ ] **Path traversal** — `open(f"files/{user_path}")` without validation
- [ ] **Hardcoded credentials** — AI often generates placeholder secrets
- [ ] **Improper password handling** — (1.88x more common in AI code)
- [ ] **Insecure object references** — (1.91x more common)
- [ ] **Weak crypto defaults** — MD5, SHA1 for security purposes
- [ ] **Unchecked return values** — API call results ignored

### Bad Pattern (AI-Generated)
```python
# DANGEROUS: AI often generates this pattern
def get_user_file(filename):
    return open(f"uploads/{filename}").read()  # Path traversal: ../../../etc/passwd
```

### Good Pattern
```python
# CORRECT: Validate and sanitize
from pathlib import Path

def get_user_file(filename: str) -> str:
    base = Path("uploads").resolve()
    target = (base / filename).resolve()
    if not target.is_relative_to(base):
        raise ValueError("Invalid path")
    return target.read_text()
```

### Sources
- [AI-Generated Code Has 1.7x More Bugs - WebProNews](https://www.webpronews.com/ai-generated-code-has-1-7x-more-bugs-and-vulnerabilities-report-reveals/)
- [Security Pitfalls of AI Code Generation - Medium](https://medium.com/@derekdw/security-pitfalls-of-ai-code-generation-tools-2025-update-8ded7e50244d)
- [Hidden Vulnerabilities in AI-Coded Software - CrowdStrike](https://www.crowdstrike.com/en-us/blog/crowdstrike-researchers-identify-hidden-vulnerabilities-ai-coded-software/)
- [Most Common Security Vulnerabilities in AI-Generated Code - Endor Labs](https://www.endorlabs.com/learn/the-most-common-security-vulnerabilities-in-ai-generated-code)

---

## 10. ML/Research Codebase Specific

**Risk**: Medium-High — Subtle bugs that affect model quality

### What to Look For

- [ ] **Train/test contamination** — Leaking test data into training
- [ ] **Wrong model used for eval** — Training model A, evaluating model B
- [ ] **Argument order confusion** — `score(predicted, actual)` vs `score(actual, predicted)`
- [ ] **Random seed not fixed** — Non-reproducible experiments
- [ ] **Pandas silent failures** — `df[list]` vs `df[series]` different behavior
- [ ] **In-place mutations** — `df.drop(inplace=True)` in middle of pipeline
- [ ] **Gradient accumulation bugs** — Forgetting `optimizer.zero_grad()`
- [ ] **Batch size edge cases** — Last batch smaller, causes issues
- [ ] **Floating point comparison** — `if loss == 0.0` (never true)
- [ ] **Metric calculation on wrong subset** — Val metrics on train data

### Bad Pattern
```python
# DANGEROUS: Silent failure in pandas
def process(df, columns):
    return df[columns]  # If columns is [0, 1], this does row indexing, not column!
```

### Good Pattern
```python
# CORRECT: Explicit column selection
def process(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    missing = set(columns) - set(df.columns)
    if missing:
        raise KeyError(f"Missing columns: {missing}")
    return df.loc[:, columns]
```

### Sources
- [Avoiding Bugs in ML Code - Ben Kuhn](https://www.benkuhn.net/ml-bugs-2/)
- [ML in Production: Anti-patterns - Ahsan Ijaz](https://ahsanijaz.github.io/2019-02-10-patterns/)
- [Why AI Fails at Debugging Real-World Code - StartupHakk](https://startuphakk.com/why-ai-is-still-terrible-at-fixing-bugs-a-veteran-developers-take/)

---

## 11. Static vs Runtime Type Mismatch

**Risk**: Medium (P3) — MyPy passes, runtime crashes

### What to Look For

- [ ] **External data not validated** — JSON from API assumed to match types
- [ ] **`Any` type hiding errors** — `data: Any` bypasses all checks
- [ ] **Stub file divergence** — Type stubs don't match runtime behavior
- [ ] **Optional without None check** — `x: Optional[str]` then `x.upper()`
- [ ] **Type narrowing not preserved** — Check in one function, use in another
- [ ] **Cast without validation** — `cast(MyType, data)` trusts blindly
- [ ] **Forward references not resolved** — `"ClassName"` as string

### Bad Pattern
```python
# DANGEROUS: MyPy trusts, runtime crashes
def process_response(data: UserData) -> str:
    return data.name.upper()  # data might be {"Name": "..."} with wrong case

# Caller:
response = api.get("/user")  # Returns dict, not UserData
process_response(response)  # MyPy: OK, Runtime: AttributeError
```

### Good Pattern
```python
# CORRECT: Validate at boundary
from pydantic import ValidationError

def process_response(raw: dict) -> str:
    try:
        data = UserData.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Invalid API response: {e}")
    return data.name.upper()
```

### Sources
- [Mastering Type-Safe Python 2025 - Toolshelf](https://toolshelf.tech/blog/mastering-type-safe-python-pydantic-mypy-2025/)
- [MyPy Common Issues and Solutions](https://mypy.readthedocs.io/en/stable/common_issues.html)
- [MyPy Runtime Troubles](https://mypy.readthedocs.io/en/stable/runtime_troubles.html)

---

## 12. Over-Engineering & Premature Abstraction

**Risk**: Low (P4) — Technical debt, maintenance burden

### What to Look For

- [ ] **Abstractions for single use** — `AbstractFactory` with one implementation
- [ ] **Feature flags for non-features** — Over-configurability
- [ ] **Dependency injection overkill** — Simple function could suffice
- [ ] **Generic types where concrete would do** — `T extends Base` for one type
- [ ] **Plugin systems without plugins** — YAGNI
- [ ] **Backwards compatibility shims** — Code that will never be removed
- [ ] **Comments describing removed code** — `# removed in v2`
- [ ] **Unused parameters preserved "for compatibility"**

### Principle
> "Three similar lines of code is better than a premature abstraction."

### Sources
- [The Inevitable Rise of Poor Code Quality in AI-Accelerated Codebases - Sonar](https://www.sonarsource.com/blog/the-inevitable-rise-of-poor-code-quality-in-ai-accelerated-codebases/)
- [AI Code Is a Bug-Filled Mess - Futurism](https://futurism.com/artificial-intelligence/ai-code-bug-filled-mess)
- [8 AI Code Generation Mistakes - Vocal Media](https://vocal.media/futurism/8-ai-code-generation-mistakes-devs-must-fix-to-win-2026)

---

## 13. Python Truthiness Traps

**Risk**: High (P1) — Conflates `None`, `0`, `""`, `[]`, `{}`, `False`

### What to Look For

- [ ] **`if value:` when checking for None** — 0 and empty collections are also falsy
- [ ] **`if not value:` instead of `if value is None:`** — Misses valid falsy values
- [ ] **CLI argument handling with truthiness** — `--limit 0` treated as "not set"
- [ ] **Optional return values checked with `if result:`** — May miss valid falsy returns
- [ ] **Boolean coercion of XML/HTML elements** — Empty element exists but is falsy

### Bad Pattern

```python
# DANGEROUS: Truthiness trap with optional scores
def process_score(score):
    if score:  # 0 is treated as "no score"!
        return normalize(score)
    return None  # Valid score of 0 is lost!

# DANGEROUS: CLI argument
if limit:  # --limit 0 is treated as "not set"
    items = items[:limit]
```

### Good Pattern

```python
# CORRECT: Explicit None check
def process_score(score):
    if score is not None:  # 0 is a valid score
        return normalize(score)
    return None

# CORRECT: Explicit None check for CLI
if limit is not None:
    items = items[:limit]
```

### Sources
- [Truthy and Falsy Gotchas - Inspired Python](https://www.inspiredpython.com/article/truthy-and-falsy-gotchas)
- [Common Gotchas - Hitchhiker's Guide to Python](https://docs.python-guide.org/writing/gotchas/)

---

## 14. Mutable Default Arguments

**Risk**: High (P2) — Classic Python gotcha, shared state across calls

### What to Look For

- [ ] **`def func(items=[]):`** — List shared across all calls
- [ ] **`def func(config={}):`** — Dict shared across all calls
- [ ] **`def func(data=set()):`** — Set shared across all calls
- [ ] **Class attributes with mutable defaults** — Shared across instances
- [ ] **Default `datetime.now()`** — Evaluated at definition time, not call time

### Bad Pattern

```python
# DANGEROUS: Shared mutable default
def add_item(item, items=[]):
    items.append(item)
    return items

add_item("a")  # ["a"]
add_item("b")  # ["a", "b"] — Oops! Same list!

# DANGEROUS: Timestamp at import time
def log_event(msg, timestamp=datetime.now()):  # Fixed at import!
    print(f"{timestamp}: {msg}")
```

### Good Pattern

```python
# CORRECT: Use None sentinel
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items

# CORRECT: Compute at call time
def log_event(msg, timestamp=None):
    if timestamp is None:
        timestamp = datetime.now()
    print(f"{timestamp}: {msg}")
```

### Sources
- [Python Mutable Defaults - Hitchhiker's Guide](https://docs.python-guide.org/writing/gotchas/)
- [Mutable Defaults Are The Source of All Evil - Florimond](https://florimond.dev/en/posts/2018/08/python-mutable-defaults-are-the-source-of-all-evil)

---

## 15. Floating Point & Numerical Bugs

**Risk**: High (P2) — `0.1 + 0.2 != 0.3` due to IEEE 754

### What to Look For

- [ ] **Direct `==` comparison of floats** — Almost always wrong
- [ ] **Fixed epsilon that doesn't scale** — May be huge or tiny relative to values
- [ ] **NaN comparisons** — `NaN != NaN` by definition; use `math.isnan()`
- [ ] **Division producing infinity** — Unchecked division by near-zero
- [ ] **Accumulating rounding errors** — Summing many floats compounds error
- [ ] **Financial calculations with float** — Use `Decimal` instead
- [ ] **Integer overflow in NumPy** — Wraps around silently with fixed-width ints

### Bad Pattern

```python
# DANGEROUS: Direct comparison
if result == 0.3:  # May never be true!
    process()

# DANGEROUS: NaN comparison
if value > threshold:  # NaN comparisons are always False
    process()

# DANGEROUS: Score comparison
if score == 2.5:  # Floating point, may fail
    flag_moderate()
```

### Good Pattern

```python
import math

# CORRECT: Use math.isclose()
if math.isclose(result, 0.3, rel_tol=1e-9):
    process()

# CORRECT: Check for NaN first
if not math.isnan(value) and value > threshold:
    process()

# CORRECT: For PHQ scores, use integer representation or Decimal
if int(score * 10) == 25:  # 2.5 as integer
    flag_moderate()
```

### Sources
- [Floating-Point Comparison Guide](https://floating-point-gui.de/errors/comparison/)
- [What Every Programmer Should Know About Floating-Point](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html)

---

## 16. Off-by-One & Fencepost Errors

**Risk**: Medium (P3) — Classic bug category

### What to Look For

- [ ] **Range end confusion** — `range(n)` is 0 to n-1, not 0 to n
- [ ] **Loop boundary wrong** — `<= n` vs `< n`
- [ ] **Array index miscalculation** — Zero-based indexing errors
- [ ] **User-facing 1-based vs internal 0-based** — Conversion errors
- [ ] **Length vs index confusion** — n elements means indices 0 to n-1
- [ ] **Slice endpoint** — `items[start:end]` excludes `end`
- [ ] **PHQ-8 item indexing** — Items 1-8 in clinical terms, 0-7 in code

### Bad Pattern

```python
# DANGEROUS: Fencepost in loop
for i in range(len(items) + 1):  # One too many!
    process(items[i])  # IndexError on last iteration

# DANGEROUS: User input (1-based) used directly
phq_item = int(input("Enter PHQ item (1-8): "))
scores[phq_item]  # Should be scores[phq_item - 1]!
```

### Good Pattern

```python
# CORRECT: Range matches array length
for i in range(len(items)):
    process(items[i])

# CORRECT: Convert 1-based to 0-based explicitly
phq_item = int(input("Enter PHQ item (1-8): "))
if not 1 <= phq_item <= 8:
    raise ValueError("PHQ item must be 1-8")
scores[phq_item - 1]  # Explicit conversion
```

### Sources
- [Off-by-One Errors - Incus Data](https://incusdata.com/blog/off-by-one-errors)
- [Fencepost Errors Explained](https://betterexplained.com/articles/learning-how-to-count-avoiding-the-fencepost-problem/)

---

## 17. ML Reproducibility Bugs

**Risk**: High (P1) — Random seed choice can cause 44-45% accuracy variation

### What to Look For

- [ ] **Random seed not set or not logged** — Results vary between runs
- [ ] **Multiple RNG sources not all seeded** — Python, NumPy, PyTorch, CUDA each have separate RNGs
- [ ] **GPU non-determinism not addressed** — cuDNN benchmarking selects different algorithms
- [ ] **Parallel execution breaks reproducibility** — Threading/multiprocessing introduces variance
- [ ] **Weight initialization not controlled** — Different starting weights, different outcomes
- [ ] **Library version not pinned** — Different versions produce different results
- [ ] **Hardware differences not documented** — CPU vs GPU, different GPU models

### Bad Pattern

```python
# DANGEROUS: No seed control
import random
import numpy as np

# Results vary every run!
data = random.sample(population, k=100)
weights = np.random.randn(10, 10)
```

### Good Pattern

```python
import random
import numpy as np

def set_seed(seed: int) -> None:
    """Set all random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    # For PyTorch:
    # torch.manual_seed(seed)
    # if torch.cuda.is_available():
    #     torch.cuda.manual_seed_all(seed)
    #     torch.backends.cudnn.deterministic = True
    #     torch.backends.cudnn.benchmark = False

# Always set and log the seed
SEED = 42
set_seed(SEED)
logger.info(f"Random seed: {SEED}")
```

### Sources
- [CMU SEI: ML Reproducibility Myth](https://www.sei.cmu.edu/blog/the-myth-of-machine-learning-reproducibility-and-randomness-for-acquisitions-and-testing-evaluation-verification-and-validation/)
- [Wiley: Reproducibility in ML-based Research](https://onlinelibrary.wiley.com/doi/10.1002/aaai.70002)

---

## 18. Data Leakage & Train-Test Contamination

**Risk**: Critical (P0) — Princeton researchers found 648 papers affected

### What to Look For

- [ ] **Preprocessing before split** — Scaling/normalization fit on full dataset
- [ ] **Feature engineering uses test data** — Statistics computed across all data
- [ ] **Time series future leakage** — Using future data to predict past
- [ ] **Duplicate/near-duplicate samples across splits** — Same data in train and test
- [ ] **External data join without timestamp filtering** — Inadvertent overlap
- [ ] **Target leakage** — Features that encode the target variable
- [ ] **Participant-level scores assigned to chunks** — Scores must match data granularity

### Bad Pattern

```python
# DANGEROUS: Preprocessing before split
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)  # Uses ALL data including test!
X_train, X_test = train_test_split(X_scaled)
```

### Good Pattern

```python
# CORRECT: Split first, then fit only on train
from sklearn.preprocessing import StandardScaler

X_train, X_test = train_test_split(X)
scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)  # Fit on train only
X_test = scaler.transform(X_test)  # Transform test with train params
```

### Sources
- [Princeton: Leakage and the Reproducibility Crisis](https://reproducible.cs.princeton.edu/)
- [Data Leakage in Machine Learning](https://machinelearningmastery.com/data-leakage-machine-learning/)

---

## 19. Resource & Connection Leaks

**Risk**: Medium (P3) — Connection pool exhaustion, file handle leaks

### What to Look For

- [ ] **Files opened without `with` statement** — Not guaranteed to close
- [ ] **Database connections not returned to pool** — Pool exhaustion
- [ ] **HTTP clients not closed** — Socket leaks
- [ ] **`multiprocessing.Pool` without context manager** — Resource leaks
- [ ] **Async context managers not awaited properly**
- [ ] **Missing `finally` blocks for cleanup**

### Bad Pattern

```python
# DANGEROUS: File may not close on exception
f = open("data.txt")
data = f.read()
process(data)  # If this raises, file never closes!
f.close()

# DANGEROUS: Connection leak
conn = pool.getconn()
cursor = conn.cursor()
cursor.execute(query)
# Forgot to return connection!
```

### Good Pattern

```python
# CORRECT: Context manager ensures cleanup
with open("data.txt") as f:
    data = f.read()
    process(data)  # File closes even on exception

# CORRECT: Connection returned automatically
async with pool.connection() as conn:
    async with conn.cursor() as cursor:
        await cursor.execute(query)
# Automatically returned to pool
```

### Sources
- [The Python "with" Trick That Fixes Resource Leaks](https://viju-londhe.medium.com/the-python-with-trick-that-will-fix-your-resource-leaks-ec77b280f636)

---

## 20. Circular Imports & TYPE_CHECKING

**Risk**: Medium (P3) — Type hints increase circular import likelihood

### What to Look For

- [ ] **Runtime `ImportError: cannot import name`** — Circular dependency
- [ ] **`TYPE_CHECKING` imports used at runtime** — Should only be for hints
- [ ] **Missing `from __future__ import annotations`** — Forward refs not working
- [ ] **Tightly coupled modules** — Design smell

### Bad Pattern

```python
# module_a.py
from module_b import ClassB  # Circular!

class ClassA:
    def method(self) -> ClassB: ...

# module_b.py
from module_a import ClassA  # Circular!

class ClassB:
    def method(self) -> ClassA: ...
```

### Good Pattern

```python
# module_a.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from module_b import ClassB  # Only imported for type checking

class ClassA:
    def method(self) -> ClassB: ...  # Forward reference works
```

### Sources
- [Python Type Hints: Fix Circular Imports - Adam Johnson](https://adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/)
- [Fixing Circular Imports with Protocol](https://pythontest.com/fix-circular-import-python-typing-protocol/)

---

## 21. Hallucinated APIs & Libraries

**Risk**: High (P2) — 19.7% of AI code samples reference non-existent packages

### What to Look For

- [ ] **Imports that don't resolve** — Library doesn't exist
- [ ] **Method calls on wrong objects** — API hallucination
- [ ] **Deprecated/removed API usage** — LLM trained on old data
- [ ] **Non-existent function parameters** — Made-up kwargs
- [ ] **Fictional library recommendations** — Package doesn't exist in PyPI
- [ ] **Wrong method signatures** — Parameters in wrong order

### Detection

```bash
# Verify all imports actually exist
python -c "from module import thing"  # Will fail if hallucinated

# Check if packages exist
pip index versions <package_name>

# Run type checker
uv run mypy src/ --strict  # Will catch many API mismatches
```

### Verification Steps

1. **Run `pip install` for new dependencies** — Verify they exist
2. **Check PyPI for package** — Manual verification
3. **Read library documentation** — Verify API matches usage
4. **Run type checker** — Will catch many API mismatches
5. **Execute the code** — Hallucinations crash at runtime

### Sources
- [Package Hallucination: LLMs May Deliver Malicious Code](https://www.helpnetsecurity.com/2025/04/14/package-hallucination-slopsquatting-malicious-code/)
- [Importing Phantoms: Measuring LLM Package Hallucination](https://arxiv.org/html/2501.19012v1)

---

## 22. TODO/FIXME Incomplete Implementations

**Risk**: Medium (P3) — AI often leaves placeholder code that looks complete

### What to Look For

- [ ] **`TODO` comments in production code** — Unfinished work
- [ ] **`FIXME` markers** — Known bugs not addressed
- [ ] **`pass` in function bodies** — Stub implementations
- [ ] **`raise NotImplementedError`** — Intentionally incomplete
- [ ] **Hardcoded return values** — `return 0`, `return []`, `return {}`
- [ ] **Commented-out code** — Dead code that may confuse
- [ ] **`...` (Ellipsis) in function bodies** — Placeholder

### Detection

```bash
# Find TODO/FIXME markers
grep -rn "TODO\|FIXME\|XXX\|HACK\|BUG" --include="*.py" src/

# Find stub implementations
grep -rn "pass$" --include="*.py" src/
grep -rn "NotImplementedError" --include="*.py" src/
grep -rn "\.\.\.$" --include="*.py" src/

# Find suspicious hardcoded returns
grep -rn "return 0$\|return \[\]$\|return {}$\|return None$" --include="*.py" src/
```

### Verification Steps

1. **Search for all TODOs** — Track in issue tracker
2. **Review all `pass` statements** — Verify if intentional
3. **Check test coverage** — Stubs often have 0% coverage
4. **Run integration tests** — Unit tests may pass on stubs

---

## Audit Process

### Weekly Quick Scan (15 min)

```bash
# 1. Silent exception swallowing
grep -rn "except:" --include="*.py" src/
grep -rn -A1 "except.*:" --include="*.py" src/ | grep "pass"

# 2. Hardcoded secrets
grep -rn "api_key\|secret\|password\|token" --include="*.py" src/ | grep -v "os.environ\|getenv"
grep -rn "sk-\|pk_\|ghp_\|AKIA" --include="*.py" src/

# 3. Mutable defaults
grep -rn "def.*=\[\]\|def.*={}" --include="*.py" src/

# 4. Truthiness traps (potential)
grep -rn "if score:\|if value:\|if limit:" --include="*.py" src/

# 5. TODO/FIXME markers
grep -rn "TODO\|FIXME\|XXX\|HACK" --include="*.py" src/

# 6. Type ignores
grep -rn "type: ignore" --include="*.py" src/ | wc -l
```

### Monthly Deep Audit (2 hours)

1. Run through full checklist above
2. Check test coverage for edge cases
3. Review Pydantic models for Strict types
4. Audit async code for race conditions
5. Run `uv run bandit -r src/` for security scan
6. Run `uv run mypy src/ --strict` for type issues
7. Check for N+1 queries if using ORM
8. Document findings in `docs/_bugs/`

### Per-PR Checks

- [ ] No new bare `except:` clauses
- [ ] No silent fallbacks without logging
- [ ] No hardcoded secrets
- [ ] Tests use `autospec=True` for mocks
- [ ] Pydantic models validate external input
- [ ] No mutable default arguments
- [ ] Explicit `is None` checks (not truthiness) for optional values
- [ ] New dependencies verified on PyPI
- [ ] Random seeds set and logged for ML code

---

## Statistics (2025-2026 Research)

| Metric | Value | Source |
|--------|-------|--------|
| AI code logic errors vs human | 1.75x more | CodeRabbit 2025 |
| AI code security issues vs human | 1.57x more | CodeRabbit 2025 |
| AI code XSS vulnerabilities | 2.74x more | CodeRabbit 2025 |
| Silent failures causing bugs | 40% of investigations | PSF Survey 2025 |
| Typed exceptions reduce debug time | 40% | PSF Survey 2025 |
| Data engineers fixing pipelines | 44% of time | Gartner 2025 |
| AI-generated code with vulnerabilities | 30-50% | IEEE/Academic 2025 |
| Cost of poor data quality | $12.9M/year avg | Gartner 2025 |

---

## References

### AI Code Quality
- [AI-Authored Code Contains Worse Bugs - The Register](https://www.theregister.com/2025/12/17/ai_code_bugs/)
- [AI Code Has 1.7x More Issues - TechIntelPro](https://techintelpro.com/news/ai/enterprise-ai/study-ai-generated-code-has-17x-more-issues-than-human-code)
- [Hidden Dangers of AI-Generated Code - StartupHakk](https://startuphakk.com/the-hidden-risk-of-ai-code-what-no-one-talks-about/)
- [Package Hallucination / Slopsquatting - HelpNet Security](https://www.helpnetsecurity.com/2025/04/14/package-hallucination-slopsquatting-malicious-code/)

### Python Best Practices
- [Miguel Grinberg's Error Handling Guide](https://blog.miguelgrinberg.com/post/the-ultimate-guide-to-error-handling-in-python)
- [JetBrains Python Concurrency](https://blog.jetbrains.com/pycharm/2025/06/concurrency-in-async-await-and-threading/)
- [Hitchhiker's Guide: Common Gotchas](https://docs.python-guide.org/writing/gotchas/)
- [Truthy and Falsy Gotchas - Inspired Python](https://www.inspiredpython.com/article/truthy-and-falsy-gotchas)

### ML Reproducibility & Data Quality
- [Princeton: Leakage and the Reproducibility Crisis](https://reproducible.cs.princeton.edu/)
- [CMU SEI: ML Reproducibility Myth](https://www.sei.cmu.edu/blog/the-myth-of-machine-learning-reproducibility-and-randomness-for-acquisitions-and-testing-evaluation-verification-and-validation/)
- [Avoiding Bugs in ML Code - Ben Kuhn](https://www.benkuhn.net/ml-bugs-2/)

### Security
- [LLM Security Risks 2026 - Sombra](https://sombrainc.com/blog/llm-security-risks-2026)
- [As Coders Adopt AI Agents, Security Pitfalls Lurk - Dark Reading](https://www.darkreading.com/application-security/coders-adopt-ai-agents-security-pitfalls-lurk-2026)
- [OWASP Top 10 for LLMs](https://genai.owasp.org/)

### Type Safety
- [Mastering Type-Safe Python 2025 - Toolshelf](https://toolshelf.tech/blog/mastering-type-safe-python-pydantic-mypy-2025/)
- [Fix Circular Imports with TYPE_CHECKING - Adam Johnson](https://adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/)

---

*Last updated: 2025-01-07*
*Next audit due: 2025-01-14*
