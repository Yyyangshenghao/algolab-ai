# Runners

Problem statements and tests are language-neutral. Runner adapters translate the same interface and cases into language-specific execution.

## Interface Contract

`tests/interface.json` example:

```json
{
  "entrypoint": "solve",
  "arguments": [{"name": "nums", "type": "list<int>"}],
  "returns": {"type": "int"},
  "type_system": "algolab-v1"
}
```

Portable type vocabulary:

- `int`, `long`, `float`, `bool`, `string`
- `list<T>`
- `map<K,V>`
- `tuple<T1,T2,...>`
- `optional<T>`

## Python

Preferred file: `solutions/python/solution.py`.

Legacy `solution.py` is accepted for older problems.

The file must define the configured entrypoint, usually:

```python
def solve(*args, **kwargs):
    ...
```

The runner passes `input.args`; Python also supports `input.kwargs`.

## Java

- Solution file: `solutions/java/Solution.java`
- Current workspace file: `current/solutions/java/Solution.java`
- Class: `public class Solution`
- Method name: `tests/interface.json` `entrypoint`
- No package declaration
- `list<T>` maps to Java arrays such as `int[]`, `long[]`, `String[]`, or nested arrays.

## Other Languages

For `c`, `cpp`, `go`, and `rust`, create solution files under `solutions/<language>/`, but explain that local judging is not implemented until a runner is added.

## Adding A Runner

Create `algolab/runners/<language>.py` with:

```python
def run_case(problem_dir, interface, case):
    ...
```

For performance, also add:

```python
def run_cases(problem_dir, interface, cases, *, fail_fast=False, case_timeout=0):
    ...
```

Runners should prefer batch execution over compiling or launching once per case.
