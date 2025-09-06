# Common Complexity Patterns & Automated Refactoring Opportunities

After analyzing numerous high-complexity code samples, here are the most common patterns that can be mechanically refactored or automated:

## 1. Nested If-Else → Early Returns (Most Impactful!)

**Pattern:**
```python
def validate_something(value):
    if value is not None:
        if len(value) > 0:
            if value.isalnum():
                return True
            else:
                return False
        else:
            return False
    else:
        return False
```

**Automated Refactoring:**
```python
def validate_something(value):
    if value is None:
        return False
    if len(value) == 0:
        return False
    if not value.isalnum():
        return False
    return True
```

**Impact:** Can reduce cognitive complexity by 80-90%!

## 2. Boolean Flag Accumulation → Any/All Functions

**Pattern:**
```python
has_error = False
for item in items:
    if item.status == "error":
        has_error = True
        break

has_upper = False
has_lower = False
has_digit = False
for char in password:
    if char.isupper():
        has_upper = True
    elif char.islower():
        has_lower = True
    elif char.isdigit():
        has_digit = True
```

**Automated Refactoring:**
```python
has_error = any(item.status == "error" for item in items)

has_upper = any(c.isupper() for c in password)
has_lower = any(c.islower() for c in password)
has_digit = any(c.isdigit() for c in password)
```

## 3. Sequential Type Checking → Dictionary Dispatch

**Pattern:**
```python
if extension == ".json":
    return process_json(file)
elif extension == ".csv":
    return process_csv(file)
elif extension == ".xml":
    return process_xml(file)
elif extension == ".txt":
    return process_txt(file)
else:
    raise ValueError("Unknown extension")
```

**Automated Refactoring:**
```python
processors = {
    ".json": process_json,
    ".csv": process_csv,
    ".xml": process_xml,
    ".txt": process_txt
}

processor = processors.get(extension)
if not processor:
    raise ValueError("Unknown extension")
return processor(file)
```

## 4. Nested Try-Except → Guard Clauses

**Pattern:**
```python
try:
    value = get_value()
    try:
        result = process(value)
        try:
            save(result)
            return True
        except SaveError:
            return False
    except ProcessError:
        return False
except ValueError:
    return False
```

**Automated Refactoring:**
```python
try:
    value = get_value()
except ValueError:
    return False

try:
    result = process(value)
except ProcessError:
    return False

try:
    save(result)
    return True
except SaveError:
    return False
```

## 5. Complex Boolean Conditions → Named Predicates

**Pattern:**
```python
if (user.age >= 18 and user.age <= 65 and
    user.country in ["US", "CA", "UK"] and
    user.verified and not user.suspended):
    # allow action
```

**Automated Refactoring:**
```python
def is_eligible_user(user):
    is_adult = 18 <= user.age <= 65
    is_supported_country = user.country in ["US", "CA", "UK"]
    is_active = user.verified and not user.suspended
    return is_adult and is_supported_country and is_active

if is_eligible_user(user):
    # allow action
```

## 6. Repeated Null Checks → Optional Chaining

**Pattern:**
```python
if data is not None:
    if data.user is not None:
        if data.user.profile is not None:
            if data.user.profile.email is not None:
                return data.user.profile.email
return None
```

**Automated Refactoring (Python 3.8+):**
```python
# Using getattr with default
return getattr(
    getattr(
        getattr(data, 'user', None),
        'profile', None
    ),
    'email', None
)

# Or with a helper function
def safe_get(obj, *attrs):
    for attr in attrs:
        if obj is None:
            return None
        obj = getattr(obj, attr, None)
    return obj

return safe_get(data, 'user', 'profile', 'email')
```

## 7. Long Parameter Lists → Parameter Objects

**Pattern:**
```python
def create_user(username, password, email, first_name, last_name,
                age, country, city, address, phone, newsletter,
                marketing, verified, role, department):
    # 50+ lines of validation
```

**Automated Refactoring:**
```python
@dataclass
class UserData:
    username: str
    password: str
    email: str
    # ... other fields

def create_user(user_data: UserData):
    # Same logic but accessing user_data.field
```

## 8. Accumulator Loops → List Comprehensions

**Pattern:**
```python
results = []
for item in items:
    if item.is_valid():
        processed = process(item)
        if processed is not None:
            results.append(processed)
```

**Automated Refactoring:**
```python
results = [
    processed
    for item in items
    if item.is_valid()
    and (processed := process(item)) is not None
]
```

## 9. Multiple Returns with Same Value → Single Exit

**Pattern:**
```python
def check_access(user, resource):
    if user.role == "admin":
        log("Admin access")
        return True
    if user.id == resource.owner_id:
        log("Owner access")
        return True
    if resource.is_public:
        log("Public access")
        return True
    return False
```

**Automated Refactoring:**
```python
def check_access(user, resource):
    reasons = []

    if user.role == "admin":
        reasons.append("Admin access")
    elif user.id == resource.owner_id:
        reasons.append("Owner access")
    elif resource.is_public:
        reasons.append("Public access")

    if reasons:
        log(reasons[0])
        return True
    return False
```

## 10. String Building in Loops → Join Operation

**Pattern:**
```python
result = ""
for i, item in enumerate(items):
    if i > 0:
        result += ", "
    result += str(item)
```

**Automated Refactoring:**
```python
result = ", ".join(str(item) for item in items)
```

## Automation Potential

These patterns could be automated with AST transformation tools:

### High Automation Potential:
1. **Early Returns** - Clear pattern matching on nested if-else
2. **Boolean Accumulation** - Flag variables in loops
3. **Dictionary Dispatch** - Sequential if-elif on same variable
4. **List Comprehensions** - Accumulator patterns

### Medium Automation Potential:
5. **Named Predicates** - Complex conditions (needs heuristics)
6. **Parameter Objects** - Long parameter lists (needs grouping logic)

### Low Automation Potential (Requires Context):
7. **Null Checks** - Depends on object structure
8. **Try-Except Flattening** - Depends on error handling strategy

## Implementation Sketch

```python
import ast
import astor

class ComplexityReducer(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        # Detect nested if-else pattern
        if self._has_nested_if_pattern(node):
            node.body = self._convert_to_early_returns(node.body)

        # Detect boolean accumulation
        node.body = self._convert_boolean_loops(node.body)

        return self.generic_visit(node)

    def _has_nested_if_pattern(self, node):
        # Check for if-else chains that can be flattened
        pass

    def _convert_to_early_returns(self, body):
        # Transform nested if-else to early returns
        pass
```

## Recommended Approach

1. **Start with Early Returns** - Biggest bang for buck
2. **Focus on Measurable Patterns** - Use AST analysis
3. **Preserve Semantics** - Ensure behavior doesn't change
4. **Add as antipasta Command** - `antipasta refactor --early-returns file.py`
5. **Show Preview** - Let users review changes before applying

## Example Command

```bash
# Analyze and suggest refactorings
antipasta suggest-refactoring complex_file.py

# Apply specific refactoring
antipasta refactor --pattern early-returns complex_file.py

# Apply all safe refactorings
antipasta refactor --auto complex_file.py --safe-only
```

This would make antipasta not just a complexity detector, but also a complexity reducer!