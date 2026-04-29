from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .common import case_arguments, solution_path_for


JAVA_IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def parse_type(type_text: str) -> Any:
    text = type_text.strip()
    aliases = {
        "integer": "int",
        "str": "string",
        "boolean": "bool",
        "double": "float",
    }
    text = aliases.get(text, text)
    if text.startswith("list<") and text.endswith(">"):
        return ("list", parse_type(text[5:-1]))
    if text.startswith("optional<") and text.endswith(">"):
        return ("optional", parse_type(text[9:-1]))
    return text


def java_type(type_spec: Any) -> str:
    if isinstance(type_spec, tuple):
        kind, inner = type_spec
        if kind == "list":
            return java_type(inner) + "[]"
        if kind == "optional":
            inner_type = java_type(inner)
            boxed = {
                "int": "Integer",
                "long": "Long",
                "double": "Double",
                "boolean": "Boolean",
            }
            return boxed.get(inner_type, inner_type)
    mapping = {
        "int": "int",
        "long": "long",
        "float": "double",
        "bool": "boolean",
        "string": "String",
        "any": "Object",
    }
    if type_spec in mapping:
        return mapping[type_spec]
    raise RuntimeError(f"unsupported Java interface type: {type_spec}")


def quote_java_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def java_literal(value: Any, type_spec: Any) -> str:
    if isinstance(type_spec, tuple):
        kind, inner = type_spec
        if kind == "optional":
            return "null" if value is None else java_literal(value, inner)
        if kind == "list":
            if not isinstance(value, list):
                raise RuntimeError(f"expected list value for type {java_type(type_spec)}")
            values = ", ".join(java_literal(item, inner) for item in value)
            return f"new {java_type(type_spec)}{{{values}}}"
    if type_spec == "int":
        return str(int(value))
    if type_spec == "long":
        return f"{int(value)}L"
    if type_spec == "float":
        return repr(float(value))
    if type_spec == "bool":
        return "true" if bool(value) else "false"
    if type_spec == "string":
        if not isinstance(value, str):
            raise RuntimeError("expected string value")
        return quote_java_string(value)
    if type_spec == "any":
        raise RuntimeError("Java runner requires concrete argument types, not `any`")
    raise RuntimeError(f"unsupported Java literal type: {type_spec}")


def argument_literals(interface: dict[str, Any], case: dict[str, Any]) -> list[str]:
    args_value, kwargs_value = case_arguments(case)
    if kwargs_value:
        raise RuntimeError("Java runner only supports positional `input.args`")
    arguments = interface.get("arguments") or []
    if not isinstance(arguments, list):
        raise RuntimeError("tests/interface.json `arguments` must be a list")
    if len(args_value) != len(arguments):
        raise RuntimeError(f"case has {len(args_value)} args but interface defines {len(arguments)} arguments")
    literals: list[str] = []
    for value, argument in zip(args_value, arguments):
        if not isinstance(argument, dict) or "type" not in argument:
            raise RuntimeError("each interface argument must include a `type`")
        literals.append(java_literal(value, parse_type(str(argument["type"]))))
    return literals


def harness_source(entrypoint: str, case_literals: list[list[str]], fail_fast: bool, case_timeout: float) -> str:
    case_blocks = []
    timeout_millis = 0 if case_timeout <= 0 else max(1, round(case_timeout * 1000))
    fail_fast_literal = "true" if fail_fast else "false"
    for literals in case_literals:
        joined_args = ", ".join(literals)
        case_blocks.append(
            f"""
        if (!stop) {{
            if (emitted > 0) out.append(",");
            CaseResult caseResult = runWithTimeout(new CaseCall() {{
                public Object call() throws Throwable {{
                    return solution.{entrypoint}({joined_args});
                }}
            }}, {timeout_millis}L);
            out.append(caseResult.json);
            emitted++;
            if ({fail_fast_literal} && !caseResult.ok) {{
                stop = true;
            }}
        }}
""".rstrip()
        )
    joined_cases = "\n".join(case_blocks)
    return f"""
import java.lang.reflect.Array;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.Iterator;
import java.util.Map;

public class AlgoLabHarness {{
    public static void main(String[] args) throws Exception {{
        Solution solution = new Solution();
        StringBuilder out = new StringBuilder();
        out.append("[");
        int emitted = 0;
        boolean stop = false;
{joined_cases}
        out.append("]");
        System.out.print(out.toString());
    }}

    private interface CaseCall {{
        Object call() throws Throwable;
    }}

    private static class CaseFailure extends Exception {{
        private final Throwable original;

        CaseFailure(Throwable original) {{
            super(original);
            this.original = original;
        }}
    }}

    private static class CaseResult {{
        private final boolean ok;
        private final String json;

        CaseResult(boolean ok, String json) {{
            this.ok = ok;
            this.json = json;
        }}
    }}

    private static CaseResult runWithTimeout(final CaseCall caseCall, long timeoutMillis) {{
        if (timeoutMillis <= 0) {{
            try {{
                return ok(caseCall.call());
            }} catch (Throwable throwable) {{
                return error(throwable);
            }}
        }}

        ExecutorService executor = Executors.newSingleThreadExecutor(new ThreadFactory() {{
            public Thread newThread(Runnable runnable) {{
                Thread thread = new Thread(runnable, "algolab-case");
                thread.setDaemon(true);
                return thread;
            }}
        }});
        Future<Object> future = executor.submit(new Callable<Object>() {{
            public Object call() throws Exception {{
                try {{
                    return caseCall.call();
                }} catch (Throwable throwable) {{
                    throw new CaseFailure(throwable);
                }}
            }}
        }});
        try {{
            return ok(future.get(timeoutMillis, TimeUnit.MILLISECONDS));
        }} catch (TimeoutException timeout) {{
            future.cancel(true);
            return error("TimeoutError: case exceeded " + (timeoutMillis / 1000.0) + " seconds");
        }} catch (ExecutionException execution) {{
            Throwable throwable = execution.getCause();
            if (throwable instanceof CaseFailure) {{
                throwable = ((CaseFailure) throwable).original;
            }}
            return error(throwable);
        }} catch (Throwable throwable) {{
            return error(throwable);
        }} finally {{
            executor.shutdownNow();
        }}
    }}

    private static CaseResult ok(Object result) {{
        return new CaseResult(true, "{{\\\"ok\\\":true,\\\"value\\\":" + toJson(result) + "}}");
    }}

    private static CaseResult error(Throwable throwable) {{
        return error(throwable.getClass().getSimpleName() + ": " + String.valueOf(throwable.getMessage()));
    }}

    private static CaseResult error(String message) {{
        return new CaseResult(false, "{{\\\"ok\\\":false,\\\"error\\\":" + quote(message) + "}}");
    }}

    private static String toJson(Object value) {{
        if (value == null) {{
            return "null";
        }}
        Class<?> cls = value.getClass();
        if (cls.isArray()) {{
            StringBuilder sb = new StringBuilder();
            sb.append("[");
            int length = Array.getLength(value);
            for (int i = 0; i < length; i++) {{
                if (i > 0) sb.append(",");
                sb.append(toJson(Array.get(value, i)));
            }}
            sb.append("]");
            return sb.toString();
        }}
        if (value instanceof String) {{
            return quote((String) value);
        }}
        if (value instanceof Character) {{
            return quote(String.valueOf(value));
        }}
        if (value instanceof Boolean || value instanceof Number) {{
            return String.valueOf(value);
        }}
        if (value instanceof Iterable<?>) {{
            StringBuilder sb = new StringBuilder();
            sb.append("[");
            Iterator<?> iterator = ((Iterable<?>) value).iterator();
            boolean first = true;
            while (iterator.hasNext()) {{
                if (!first) sb.append(",");
                first = false;
                sb.append(toJson(iterator.next()));
            }}
            sb.append("]");
            return sb.toString();
        }}
        if (value instanceof Map<?, ?>) {{
            StringBuilder sb = new StringBuilder();
            sb.append("{{");
            boolean first = true;
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {{
                if (!first) sb.append(",");
                first = false;
                sb.append(quote(String.valueOf(entry.getKey())));
                sb.append(":");
                sb.append(toJson(entry.getValue()));
            }}
            sb.append("}}");
            return sb.toString();
        }}
        return quote(String.valueOf(value));
    }}

    private static String quote(String value) {{
        StringBuilder sb = new StringBuilder();
        sb.append('"');
        for (int i = 0; i < value.length(); i++) {{
            char ch = value.charAt(i);
            switch (ch) {{
                case '"': sb.append("\\\\\\""); break;
                case '\\\\': sb.append("\\\\\\\\"); break;
                case '\\b': sb.append("\\\\b"); break;
                case '\\f': sb.append("\\\\f"); break;
                case '\\n': sb.append("\\\\n"); break;
                case '\\r': sb.append("\\\\r"); break;
                case '\\t': sb.append("\\\\t"); break;
                default:
                    if (ch < 0x20) {{
                        sb.append(String.format("\\\\u%04x", (int) ch));
                    }} else {{
                        sb.append(ch);
                    }}
            }}
        }}
        sb.append('"');
        return sb.toString();
    }}
}}
""".strip()


def run_case(problem_dir: Path, interface: dict[str, Any], case: dict[str, Any]) -> Any:
    result = run_cases(problem_dir, interface, [case])[0]
    if isinstance(result, Exception):
        raise result
    return result


def run_cases(
    problem_dir: Path,
    interface: dict[str, Any],
    cases: list[dict[str, Any]],
    *,
    fail_fast: bool = False,
    case_timeout: float = 0,
) -> list[Any]:
    solution_path = solution_path_for(problem_dir, "java")
    if not solution_path.is_file():
        raise RuntimeError(f"missing Java solution: {solution_path}")
    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac is None or java is None:
        raise RuntimeError("Java runner requires `javac` and `java` on PATH")
    entrypoint = str(interface.get("entrypoint") or "solve")
    if not JAVA_IDENTIFIER.match(entrypoint):
        raise RuntimeError(f"invalid Java entrypoint: {entrypoint}")
    case_literals = [argument_literals(interface, case) for case in cases]

    with tempfile.TemporaryDirectory(prefix="algolab-java-") as temp_name:
        temp_dir = Path(temp_name)
        shutil.copy2(solution_path, temp_dir / "Solution.java")
        (temp_dir / "AlgoLabHarness.java").write_text(
            harness_source(entrypoint, case_literals, fail_fast, case_timeout),
            encoding="utf-8",
        )
        compile_result = subprocess.run(
            [javac, "Solution.java", "AlgoLabHarness.java"],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if compile_result.returncode != 0:
            raise RuntimeError((compile_result.stderr or compile_result.stdout).strip())
        run_timeout = max(10.0, (case_timeout * max(len(cases), 1)) + 5.0) if case_timeout > 0 else 10
        run_result = subprocess.run(
            [java, "-cp", str(temp_dir), "AlgoLabHarness"],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=run_timeout,
            check=False,
        )
        if run_result.returncode != 0:
            raise RuntimeError((run_result.stderr or run_result.stdout).strip())
        output = run_result.stdout.strip()
        if not output:
            return [None for _ in cases]
        parsed = json.loads(output)
        results: list[Any] = []
        for item in parsed:
            if item.get("ok"):
                results.append(item.get("value"))
            else:
                results.append(RuntimeError(str(item.get("error", "Java solution failed"))))
        return results
