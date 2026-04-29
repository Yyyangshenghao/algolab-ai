from __future__ import annotations

import argparse
import importlib.resources as resources
import json
import os
import re
import shutil
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from algolab.runners import RunnerError, run_cases


CONFIG_DIR = ".algolab"
CONFIG_FILE = "config.json"
INDEX_FILE = "index.json"
TEST_COMMANDS_FILE = "TESTS.md"
CURRENT_LINK = "current"
DEFAULT_TEST_COMMANDS_FILE = f"{CURRENT_LINK}/{TEST_COMMANDS_FILE}"
CURRENT_MARKER = ".algolab-current"
SOLUTION_FILES = {
    "c": "solutions/c/solution.c",
    "cpp": "solutions/cpp/solution.cpp",
    "go": "solutions/go/solution.go",
    "java": "solutions/java/Solution.java",
    "python": "solutions/python/solution.py",
    "rust": "solutions/rust/solution.rs",
}
DEFAULT_SOLUTION_LANGUAGES = ["c", "cpp", "java", "go", "python", "rust"]
RUNNER_LANGUAGES = ["python", "java"]
DEFAULT_CASE_TIMEOUT_SECONDS = 3.0
IDEA_CURRENT_JAVA_MODULE = "algolab-current-java.iml"
NOT_RUN = object()


class AlgoLabError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value:
        raise AlgoLabError("slug cannot be empty after normalization")
    return value


def template_text(relative_path: str) -> str:
    return resources.files("algolab.templates").joinpath(relative_path).read_text(encoding="utf-8")


def render(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def write_text(path: Path, content: str, *, force: bool = False) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def find_workspace(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / CONFIG_DIR / CONFIG_FILE).is_file():
            return candidate
    return None


def require_workspace(start: Path | None = None) -> Path:
    workspace = find_workspace(start)
    if workspace is None:
        raise AlgoLabError("not inside an algolab workspace; run `python3 -m algolab init .` first")
    return workspace


def load_config(workspace: Path) -> dict[str, Any]:
    config_path = workspace / CONFIG_DIR / CONFIG_FILE
    return json.loads(config_path.read_text(encoding="utf-8"))


def configured_solution_languages(workspace: Path | None = None) -> list[str]:
    if workspace is None:
        workspace = find_workspace()
    if workspace is None:
        return DEFAULT_SOLUTION_LANGUAGES
    config = load_config(workspace)
    languages = config.get("supported_solution_languages") or DEFAULT_SOLUTION_LANGUAGES
    if not isinstance(languages, list) or not all(isinstance(item, str) for item in languages):
        raise AlgoLabError("config `supported_solution_languages` must be a list of language strings")
    return languages


def configured_runner_languages(workspace: Path | None = None) -> list[str]:
    if workspace is None:
        workspace = find_workspace()
    if workspace is None:
        return RUNNER_LANGUAGES
    config = load_config(workspace)
    languages = config.get("runner_languages") or RUNNER_LANGUAGES
    if not isinstance(languages, list) or not all(isinstance(item, str) for item in languages):
        raise AlgoLabError("config `runner_languages` must be a list of language strings")
    return languages


def format_problem_id(value: int | str) -> str:
    return f"{int(value):04d}"


def normalize_problem_id(value: str) -> str | None:
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if text.isdigit():
        return format_problem_id(text)
    match = re.match(r"^(\d{1,})[-_].+", text)
    if match:
        return format_problem_id(match.group(1))
    return None


def index_path(workspace: Path) -> Path:
    return workspace / CONFIG_DIR / INDEX_FILE


def load_index(workspace: Path) -> dict[str, Any]:
    path = index_path(workspace)
    if not path.is_file():
        return {"version": 1, "problems": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("problems"), list):
        data["problems"] = []
    return data


def save_index(workspace: Path, data: dict[str, Any]) -> None:
    path = index_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_index(workspace: Path) -> dict[str, Any]:
    data = load_index(workspace)
    problems = data.get("problems", [])
    changed = False
    next_id = int(data.get("max_id") or 0) + 1
    for item in sorted(problems, key=lambda entry: (str(entry.get("created_at", "")), str(entry.get("slug", "")))):
        if not item.get("id"):
            item["id"] = format_problem_id(next_id)
            next_id += 1
            changed = True
        else:
            item["id"] = format_problem_id(item["id"])
        if not item.get("base_slug"):
            slug = str(item.get("slug", ""))
            item["base_slug"] = re.sub(r"^\d{4}-", "", slug)
            changed = True
    max_id = max((int(item["id"]) for item in problems), default=0)
    if data.get("max_id") != max_id:
        data["max_id"] = max_id
        changed = True
    if "last_problem_id" not in data:
        latest = max(problems, key=lambda entry: str(entry.get("created_at", "")), default=None)
        data["last_problem_id"] = latest.get("id") if latest else None
        changed = True
    if changed:
        save_index(workspace, data)
    return data


def test_commands_path(workspace: Path) -> Path:
    config_path = workspace / CONFIG_DIR / CONFIG_FILE
    if config_path.is_file():
        config = load_config(workspace)
        return workspace / config.get("test_commands_file", DEFAULT_TEST_COMMANDS_FILE)
    return workspace / DEFAULT_TEST_COMMANDS_FILE


def current_link_name(workspace: Path) -> str:
    config = load_config(workspace)
    value = str(config.get("current_link") or CURRENT_LINK)
    if not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise AlgoLabError("config `current_link` must be a safe relative path")
    return value


def current_link_path(workspace: Path) -> Path:
    return workspace / current_link_name(workspace)


def existing_problem_entries(workspace: Path) -> list[dict[str, Any]]:
    index = normalize_index(workspace)
    return [
        item
        for item in index.get("problems", [])
        if (workspace / str(item.get("path", "")) / "meta.json").is_file()
    ]


def entry_for_problem_dir(workspace: Path, problem_dir: Path) -> dict[str, Any] | None:
    resolved = problem_dir.resolve()
    for item in existing_problem_entries(workspace):
        if (workspace / str(item.get("path", ""))).resolve() == resolved:
            return item
    return None


def preferred_problem_entry(workspace: Path) -> dict[str, Any] | None:
    index = normalize_index(workspace)
    entries = existing_problem_entries(workspace)
    current_id = index.get("current_problem_id")
    last_id = index.get("last_problem_id")
    for problem_id in [current_id, last_id]:
        if problem_id:
            match = next((item for item in entries if item.get("id") == problem_id), None)
            if match is not None:
                return match
    if entries:
        return max(entries, key=lambda item: str(item.get("created_at", "")))
    return None


def current_problem_entry(workspace: Path) -> dict[str, Any] | None:
    index = normalize_index(workspace)
    entries = existing_problem_entries(workspace)
    current_id = index.get("current_problem_id")
    if current_id:
        match = next((item for item in entries if item.get("id") == current_id), None)
        if match is not None:
            return match
    return preferred_problem_entry(workspace)


def current_problem_dir_from_index(workspace: Path) -> Path | None:
    entry = current_problem_entry(workspace)
    if entry is None:
        return None
    problem_dir = workspace / str(entry["path"])
    if not (problem_dir / "meta.json").is_file():
        return None
    return problem_dir


def problem_default_language(problem_dir: Path) -> str:
    meta = json.loads((problem_dir / "meta.json").read_text(encoding="utf-8"))
    return str(meta.get("default_solution_language") or meta.get("language") or "python")


def current_solution_target(problem_dir: Path, entry: dict[str, Any] | None = None) -> tuple[Path, str]:
    language = str(entry.get("default_solution_language", "")) if entry is not None else ""
    if not language:
        language = problem_default_language(problem_dir)
    relative_path = SOLUTION_FILES.get(language, f"solutions/{language}/solution")
    return problem_dir / relative_path, relative_path


def current_dir_is_safe_to_replace(current_dir: Path) -> bool:
    for item in current_dir.rglob("*"):
        if item.is_symlink() or item.is_dir():
            continue
        if item.name in {CURRENT_MARKER, TEST_COMMANDS_FILE}:
            continue
        return False
    return True


def set_current_problem(workspace: Path, problem_dir: Path) -> Path:
    problem_dir = problem_dir.resolve()
    if not (problem_dir / "meta.json").is_file():
        raise AlgoLabError(f"not a problem directory: {problem_dir}")
    entry = entry_for_problem_dir(workspace, problem_dir)
    current_dir = current_link_path(workspace)
    if current_dir.is_symlink() or current_dir.is_file():
        current_dir.unlink()
    elif current_dir.exists():
        if not current_dir.is_dir():
            raise AlgoLabError(f"current workspace path is not a directory: {current_dir}")
        if not current_dir_is_safe_to_replace(current_dir):
            raise AlgoLabError(
                f"refusing to replace {current_dir}; it contains non-symlink files. "
                "Move those files out of the current workspace first."
            )
        shutil.rmtree(current_dir)
    current_dir.mkdir(parents=True, exist_ok=True)

    def link(target: Path, link: Path) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        relative_target = os.path.relpath(target, link.parent)
        link.symlink_to(relative_target, target_is_directory=target.is_dir())

    problem_statement = problem_dir / "problem.md"
    if problem_statement.exists():
        link(problem_statement, current_dir / "problem.md")
    tests_dir = problem_dir / "tests"
    if tests_dir.exists():
        link(tests_dir, current_dir / "tests")
    solution_target, current_solution_name = current_solution_target(problem_dir, entry)
    if solution_target.exists():
        link(solution_target, current_dir / current_solution_name)

    if entry is not None:
        index = normalize_index(workspace)
        index["current_problem_id"] = entry.get("id")
        index["current_problem_path"] = entry.get("path")
        save_index(workspace, index)
    return current_dir


def ensure_current_problem(workspace: Path) -> Path | None:
    current_dir = current_link_path(workspace)
    problem_dir = current_problem_dir_from_index(workspace)
    if problem_dir is None:
        return None
    entry = current_problem_entry(workspace)
    _solution_target, current_solution_name = current_solution_target(problem_dir, entry)
    if (
        current_dir.is_dir()
        and (current_dir / "problem.md").is_file()
        and (current_dir / "tests").is_dir()
        and (current_dir / current_solution_name).is_file()
    ):
        return current_dir
    if current_dir.is_symlink():
        current_dir.unlink()
    set_current_problem(workspace, problem_dir)
    return current_dir


def write_test_commands(workspace: Path) -> Path:
    index = normalize_index(workspace)
    current = preferred_problem_entry(workspace)
    problem_id = str(current.get("id", "<id>")) if current is not None else "<id>"
    language = str(current.get("default_solution_language", "<language>")) if current is not None else "<language>"
    problem_ref = "current" if current is not None else "<id>"
    report_path = "$WORKSPACE/<report-path>"
    if current is not None:
        report_path = f"$WORKSPACE/{current.get('path')}/records/test-results.md"
    lines = [
        f"<!-- algolab:max_id={format_problem_id(index.get('max_id') or 0)} last_problem_id={index.get('last_problem_id') or ''} current_problem_id={problem_id if current is not None else ''} -->",
        "# AlgoLab Test Commands",
        "",
        f"- Max issued problem ID: `{format_problem_id(index.get('max_id') or 0)}`",
        f"- Last created problem ID: `{index.get('last_problem_id') or ''}`",
        f"- Current problem ID: `{problem_id if current is not None else ''}`",
        "",
        "Run current problem:",
        "",
        "```bash",
        f"WORKSPACE={shlex.quote(str(workspace))}",
        f'REPORT_MD="{report_path}"',
        f'cd "$WORKSPACE" && python3 -m algolab test {problem_ref} --language {language} --generated --generated-count 200 --generated-seed 0 --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md "$REPORT_MD"',
        "```",
        "",
        "Set the variables, then run:",
        "",
        "```bash",
        f"WORKSPACE={shlex.quote(str(workspace))}",
        f'PROBLEM_ID="{problem_ref}"',
        f'LANGUAGE="{language}"',
        f'REPORT_MD="{report_path}"',
        "",
        'cd "$WORKSPACE" && python3 -m algolab test "$PROBLEM_ID" --language "$LANGUAGE" --generated --generated-count 200 --generated-seed 0 --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md "$REPORT_MD"',
        "```",
        "",
    ]
    path = test_commands_path(workspace)
    content = "\n".join(lines) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    current_dir = current_link_path(workspace)
    if current_dir.is_dir() and (current_dir / TEST_COMMANDS_FILE).resolve() != path.resolve():
        (current_dir / TEST_COMMANDS_FILE).write_text(content, encoding="utf-8")
    return path


def write_xml(path: Path, root: ET.Element) -> None:
    ET.indent(root, space="  ")
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(root, encoding="unicode", short_empty_elements=True)
        + "\n",
        encoding="utf-8",
    )


def refresh_idea_modules(workspace: Path) -> int:
    idea_dir = workspace / ".idea"
    modules_path = idea_dir / "modules.xml"
    if not idea_dir.is_dir():
        raise AlgoLabError(f"missing IDEA config directory: {idea_dir}")
    idea_dir.mkdir(parents=True, exist_ok=True)

    current_problem = ensure_current_problem(workspace)
    desired_names = {IDEA_CURRENT_JAVA_MODULE} if current_problem is not None else set()
    for existing in idea_dir.glob("algolab-java-*.iml"):
        existing.unlink()
    if current_problem is None:
        current_module = idea_dir / IDEA_CURRENT_JAVA_MODULE
        if current_module.exists():
            current_module.unlink()
    else:
        current_name = current_link_name(workspace)
        current_source = f"{current_name}/solutions/java"
        module_path = idea_dir / IDEA_CURRENT_JAVA_MODULE
        module = ET.Element("module", {"type": "JAVA_MODULE", "version": "4"})
        manager = ET.SubElement(module, "component", {"name": "NewModuleRootManager", "inherit-compiler-output": "true"})
        ET.SubElement(manager, "exclude-output")
        content = ET.SubElement(manager, "content", {"url": f"file://$MODULE_DIR$/{current_source}"})
        ET.SubElement(content, "sourceFolder", {"url": f"file://$MODULE_DIR$/{current_source}", "isTestSource": "false"})
        ET.SubElement(manager, "orderEntry", {"type": "inheritedJdk"})
        ET.SubElement(manager, "orderEntry", {"type": "sourceFolder", "forTests": "false"})
        write_xml(module_path, module)

    if modules_path.is_file():
        tree = ET.parse(modules_path)
        project = tree.getroot()
    else:
        project = ET.Element("project", {"version": "4"})

    manager = project.find("./component[@name='ProjectModuleManager']")
    if manager is None:
        manager = ET.SubElement(project, "component", {"name": "ProjectModuleManager"})
    modules = manager.find("modules")
    if modules is None:
        modules = ET.SubElement(manager, "modules")

    for module in list(modules):
        filepath = module.get("filepath", "")
        if (
            "/.idea/algolab-java-" in filepath
            or filepath.startswith("$PROJECT_DIR$/.idea/algolab-java-")
            or filepath.endswith(f"/.idea/{IDEA_CURRENT_JAVA_MODULE}")
            or filepath == f"$PROJECT_DIR$/.idea/{IDEA_CURRENT_JAVA_MODULE}"
        ):
            modules.remove(module)

    existing_filepaths = {module.get("filepath") for module in modules.findall("module")}
    for module_name in sorted(desired_names):
        filepath = f"$PROJECT_DIR$/.idea/{module_name}"
        if filepath not in existing_filepaths:
            ET.SubElement(
                modules,
                "module",
                {
                    "fileurl": f"file://{filepath}",
                    "filepath": filepath,
                },
            )

    write_xml(modules_path, project)
    return 1 if current_problem is not None else 0


def upsert_problem_index(workspace: Path, entry: dict[str, Any]) -> None:
    data = normalize_index(workspace)
    problems = [item for item in data["problems"] if item.get("slug") != entry["slug"]]
    problems.append(entry)
    data["problems"] = sorted(problems, key=lambda item: str(item.get("slug", "")))
    data["max_id"] = max((int(item["id"]) for item in data["problems"]), default=0)
    data["last_problem_id"] = entry["id"]
    save_index(workspace, data)


def resolve_problem(value: str) -> Path:
    workspace = require_workspace()
    if value == current_link_name(workspace):
        problem_dir = current_problem_dir_from_index(workspace)
        if problem_dir is None:
            raise AlgoLabError("current problem is not set")
        ensure_current_problem(workspace)
        return problem_dir.resolve()

    path = Path(value)
    if path.exists():
        problem_dir = path
    else:
        config = load_config(workspace)
        index = normalize_index(workspace)
        normalized_id = normalize_problem_id(value)
        match = None
        for item in index.get("problems", []):
            candidates = {
                str(item.get("id", "")),
                str(item.get("slug", "")),
                str(item.get("base_slug", "")),
                Path(str(item.get("path", ""))).name,
            }
            if (normalized_id and normalized_id == item.get("id")) or value in candidates:
                match = item
                break
        if match is not None:
            problem_dir = workspace / str(match["path"])
        else:
            problem_dir = workspace / config.get("problems_dir", "problems") / value
    problem_dir = problem_dir.resolve()
    if not (problem_dir / "meta.json").is_file():
        raise AlgoLabError(f"not a problem directory: {problem_dir}")
    return problem_dir


def normalize_json(value: Any) -> Any:
    if isinstance(value, tuple):
        return [normalize_json(item) for item in value]
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): normalize_json(item) for key, item in value.items()}
    return value


def comparable_key(value: Any) -> str:
    return json.dumps(normalize_json(value), ensure_ascii=False, sort_keys=True)


def compare_result(actual: Any, expected: Any, mode: str) -> bool:
    actual = normalize_json(actual)
    expected = normalize_json(expected)
    if mode == "exact":
        return actual == expected
    if mode == "unordered_list":
        if not isinstance(actual, list) or not isinstance(expected, list):
            return False
        return sorted(comparable_key(item) for item in actual) == sorted(comparable_key(item) for item in expected)
    if mode == "any_of":
        if not isinstance(expected, list):
            raise AlgoLabError("any_of comparison expects `expected` to be a list of accepted outputs")
        return any(actual == normalize_json(candidate) for candidate in expected)
    raise AlgoLabError(f"unknown compare mode: {mode}")


def evaluate_case_result(case: dict[str, Any], actual: Any) -> tuple[bool, Any]:
    if isinstance(actual, BaseException):
        return False, f"{type(actual).__name__}: {actual}"
    expected = case.get("expected")
    compare = str(case.get("compare") or "exact")
    try:
        return compare_result(actual, expected, compare), actual
    except Exception as exc:  # noqa: BLE001 - comparison errors should fail the case.
        return False, f"{type(exc).__name__}: {exc}"


def markdown_cell(value: Any) -> str:
    text = json.dumps(normalize_json(value), ensure_ascii=False)
    return text.replace("|", "\\|").replace("\n", "<br>")


def write_markdown_report(
    problem_dir: Path,
    language: str,
    rows: list[dict[str, Any]],
    passed: int,
    total: int,
    report_path: Path | None,
    report_limit: int,
    skipped: int = 0,
) -> Path:
    if report_path is None:
        report_path = problem_dir / "records" / "test-results.md"
    if not report_path.is_absolute():
        report_path = problem_dir / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    status = "PASS" if passed == total else "FAIL"
    if report_limit < 0:
        display_rows = rows
    else:
        failed_rows = [row for row in rows if row["status"] != "PASS"]
        passed_rows = [row for row in rows if row["status"] == "PASS"]
        pass_room = max(report_limit - len(failed_rows), 0)
        display_rows = failed_rows + passed_rows[:pass_room]
    omitted = max(len(rows) - len(display_rows), 0)
    lines = [
        f"# Test Results - {problem_dir.name}",
        "",
        f"- Language: `{language}`",
        f"- Status: `{status}`",
        f"- Passed: `{passed}/{total}`",
        f"- Executed: `{len(rows)}/{total}`",
        f"- Cases shown: `{len(display_rows)}/{len(rows)}`",
        f"- Skipped after fail-fast: `{skipped}`",
        f"- Omitted passing cases: `{omitted}`",
        f"- Generated: `{utc_now()}`",
        "",
        "| Case | Status | Expected | Actual |",
        "| --- | --- | --- | --- |",
    ]
    for row in display_rows:
        lines.append(
            f"| {row['name']} | {row['status']} | {markdown_cell(row['expected'])} | {markdown_cell(row['actual'])} |"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def load_interface(problem_dir: Path) -> dict[str, Any]:
    interface_path = problem_dir / "tests" / "interface.json"
    if not interface_path.is_file():
        return {"entrypoint": "solve", "arguments": [], "returns": {"type": "any"}}
    data = json.loads(interface_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AlgoLabError("tests/interface.json must be a JSON object")
    return data


def load_cases(problem_dir: Path) -> list[dict[str, Any]]:
    cases_path = problem_dir / "tests" / "cases.json"
    if not cases_path.is_file():
        raise AlgoLabError(f"missing test cases: {cases_path}")
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    return extract_cases(data, "tests/cases.json")


def extract_cases(data: Any, source: str) -> list[dict[str, Any]]:
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list):
        raise AlgoLabError(f"{source} must be a list or an object with a `cases` list")
    if not all(isinstance(case, dict) for case in cases):
        raise AlgoLabError(f"{source} cases must be JSON objects")
    return cases


def load_generated_cases(problem_dir: Path, seed: int, count: int) -> list[dict[str, Any]]:
    if count < 0:
        raise AlgoLabError("--generated-count must be >= 0")
    generator_path = problem_dir / "tests" / "generator.py"
    if not generator_path.is_file():
        return []
    result = subprocess.run(
        [sys.executable, str(generator_path), "--seed", str(seed), "--count", str(count)],
        cwd=generator_path.parent,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise AlgoLabError(f"generated test script failed: {message}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AlgoLabError(f"generated test script must print JSON: {exc}") from exc
    return extract_cases(data, "tests/generator.py")


def case_batches(cases: list[dict[str, Any]], batch_size: int) -> list[list[tuple[int, dict[str, Any]]]]:
    if batch_size <= 0:
        raise AlgoLabError("--batch-size must be > 0")
    indexed_cases = list(enumerate(cases))
    return [indexed_cases[start : start + batch_size] for start in range(0, len(indexed_cases), batch_size)]


def run_case_batches(
    problem_dir: Path,
    language: str,
    interface: dict[str, Any],
    cases: list[dict[str, Any]],
    jobs: int,
    batch_size: int,
    fail_fast: bool,
    case_timeout: float,
) -> list[Any]:
    if jobs == 0:
        jobs = min(4, os.cpu_count() or 1)
    if jobs < 0:
        raise AlgoLabError("--jobs must be >= 0")
    if case_timeout < 0:
        raise AlgoLabError("--case-timeout must be >= 0")
    batches = case_batches(cases, batch_size)
    actuals: list[Any] = [NOT_RUN] * len(cases)

    def execute(batch: list[tuple[int, dict[str, Any]]]) -> tuple[list[int], list[Any]]:
        indices = [index for index, _case in batch]
        batch_cases = [case for _index, case in batch]
        values = run_cases(
            problem_dir,
            language,
            interface,
            batch_cases,
            fail_fast=fail_fast,
            case_timeout=case_timeout,
        )
        if len(values) > len(batch_cases):
            raise RuntimeError(f"runner returned {len(values)} results for {len(batch_cases)} cases")
        return indices, values

    def store_results(indices: list[int], values: list[Any]) -> bool:
        for index, value in zip(indices, values):
            actuals[index] = value
            if fail_fast and not evaluate_case_result(cases[index], value)[0]:
                return True
        if len(values) < len(indices):
            if fail_fast and values and isinstance(values[-1], BaseException):
                return True
            raise RuntimeError(f"runner returned {len(values)} results for {len(indices)} cases")
        return False

    def run_batch(batch: list[tuple[int, dict[str, Any]]]) -> bool:
        try:
            returned_indices, values = execute(batch)
        except RunnerError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail fast on compile/setup/batch runner errors.
            raise AlgoLabError(f"runner failed before completing the batch: {exc}") from exc
        return store_results(returned_indices, values)

    if jobs <= 1 or len(batches) <= 1:
        for batch in batches:
            if run_batch(batch):
                break
        return actuals

    # Run the first batch before parallel scheduling so compile/setup errors stop immediately.
    if run_batch(batches[0]):
        return actuals

    remaining_batches = iter(batches[1:])
    max_workers = min(jobs, len(batches) - 1)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: dict[Future[tuple[list[int], list[Any]]], None] = {}

        def submit_next() -> bool:
            try:
                batch = next(remaining_batches)
            except StopIteration:
                return False
            futures[executor.submit(execute, batch)] = None
            return True

        for _ in range(max_workers):
            submit_next()

        while futures:
            done, _pending = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                futures.pop(future, None)
                try:
                    returned_indices, values = future.result()
                except RunnerError:
                    raise
                except Exception as exc:  # noqa: BLE001 - fail fast on compile/setup/batch runner errors.
                    for pending in futures:
                        pending.cancel()
                    raise AlgoLabError(f"runner failed before completing the batch: {exc}") from exc
                if store_results(returned_indices, values):
                    for pending in futures:
                        pending.cancel()
                    return actuals
                submit_next()
    return actuals


def append_record(problem_dir: Path, record: dict[str, Any]) -> Path:
    records_dir = problem_dir / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    path = records_dir / "attempts.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    values = {
        "created_at": utc_now(),
    }
    created: list[str] = []
    skipped: list[str] = []

    targets = {
        root / CONFIG_DIR / CONFIG_FILE: json.dumps(
            {
                "version": 1,
                "default_language": "python",
                "default_solution_language": "python",
                "supported_solution_languages": DEFAULT_SOLUTION_LANGUAGES,
                "runner_languages": RUNNER_LANGUAGES,
                "runner_dir": "algolab/runners",
                "test_commands_file": DEFAULT_TEST_COMMANDS_FILE,
                "index_file": f"{CONFIG_DIR}/{INDEX_FILE}",
                "current_link": CURRENT_LINK,
                "problems_dir": "problems",
                "records_dir": "records",
                "i18n": {
                    "ui_locale": args.ui_locale,
                    "problem_locale": args.problem_locale,
                    "fallback_locale": "en-US",
                    "supported_locales": ["zh-CN", "en-US"],
                },
            },
            indent=2,
        )
        + "\n",
        root / CONFIG_DIR / INDEX_FILE: json.dumps(
            {"version": 1, "max_id": 0, "last_problem_id": None, "problems": []}, indent=2
        )
        + "\n",
        root / "AGENTS.md": render(template_text("agent/AGENTS.md.tpl"), values),
        root / "docs" / "AGENTS_zh.md": render(template_text("agent/AGENTS_zh.md.tpl"), values),
        root / "CLAUDE.md": render(template_text("agent/CLAUDE.md.tpl"), values),
        root / "skills" / "algolab" / "SKILL.md": render(template_text("skill/algolab/SKILL.md"), values),
        root / "skills" / "algolab" / "references" / "workspace.md": render(
            template_text("skill/algolab/references/workspace.md"), values
        ),
        root / "skills" / "algolab" / "references" / "problem-authoring.md": render(
            template_text("skill/algolab/references/problem-authoring.md"), values
        ),
        root / "skills" / "algolab" / "references" / "testing.md": render(
            template_text("skill/algolab/references/testing.md"), values
        ),
        root / "skills" / "algolab" / "references" / "runners.md": render(
            template_text("skill/algolab/references/runners.md"), values
        ),
        root / "skills" / "algolab" / "references" / "coaching.md": render(
            template_text("skill/algolab/references/coaching.md"), values
        ),
        root / "skills" / "algolab" / "references" / "i18n.md": render(
            template_text("skill/algolab/references/i18n.md"), values
        ),
        root / "problems" / ".gitkeep": "",
    }

    for path, content in targets.items():
        if write_text(path, content, force=args.force):
            created.append(str(path.relative_to(root)))
        else:
            skipped.append(str(path.relative_to(root)))

    for item in created:
        print(f"created {item}")
    for item in skipped:
        print(f"kept {item}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    workspace = require_workspace()
    config = load_config(workspace)
    supported_languages = configured_solution_languages(workspace)
    if args.solution_language not in supported_languages:
        raise AlgoLabError(
            f"solution language `{args.solution_language}` is not enabled; "
            f"enabled languages: {', '.join(supported_languages)}"
        )
    title = args.title or args.slug.replace("-", " ").title()
    base_slug = slugify(args.slug or title)
    index = normalize_index(workspace)
    problem_id = format_problem_id(int(index.get("max_id") or 0) + 1)
    slug = f"{problem_id}-{base_slug}"
    problem_dir = workspace / config.get("problems_dir", "problems") / slug
    if problem_dir.exists() and any(problem_dir.iterdir()) and not args.force:
        raise AlgoLabError(f"problem already exists: {problem_dir}")

    values = {
        "slug": slug,
        "base_slug": base_slug,
        "problem_id": problem_id,
        "title": title,
        "difficulty": args.difficulty,
        "topic": args.topic,
        "problem_locale": config.get("i18n", {}).get("problem_locale", "zh-CN"),
        "solution_language": args.solution_language,
        "created_at": utc_now(),
    }
    files = {
        "problem/common/problem.md.tpl": problem_dir / "problem.md",
        "problem/common/meta.json.tpl": problem_dir / "meta.json",
        "problem/common/tests/interface.json.tpl": problem_dir / "tests" / "interface.json",
        "problem/common/tests/cases.json.tpl": problem_dir / "tests" / "cases.json",
        "problem/common/tests/generator.py.tpl": problem_dir / "tests" / "generator.py",
        "problem/common/tests/oracle.py.tpl": problem_dir / "tests" / "oracle.py",
        "problem/common/records/test-analysis.md.tpl": problem_dir / "records" / "test-analysis.md",
    }
    if args.solution_language == "python":
        files["problem/python/solution.py.tpl"] = problem_dir / "solutions" / "python" / "solution.py"
    elif args.solution_language == "c":
        files["problem/c/solution.c.tpl"] = problem_dir / "solutions" / "c" / "solution.c"
    elif args.solution_language == "cpp":
        files["problem/cpp/solution.cpp.tpl"] = problem_dir / "solutions" / "cpp" / "solution.cpp"
    elif args.solution_language == "java":
        files["problem/java/Solution.java.tpl"] = problem_dir / "solutions" / "java" / "Solution.java"
    elif args.solution_language == "go":
        files["problem/go/solution.go.tpl"] = problem_dir / "solutions" / "go" / "solution.go"
    elif args.solution_language == "rust":
        files["problem/rust/solution.rs.tpl"] = problem_dir / "solutions" / "rust" / "solution.rs"
    else:
        raise AlgoLabError(f"unsupported solution language: {args.solution_language}")
    for template, target in files.items():
        write_text(target, render(template_text(template), values), force=args.force)
    upsert_problem_index(
        workspace,
        {
            "slug": slug,
            "base_slug": base_slug,
            "id": problem_id,
            "title": title,
            "difficulty": args.difficulty,
            "topic": args.topic,
            "locale": values["problem_locale"],
            "default_solution_language": args.solution_language,
            "supported_solution_languages": supported_languages,
            "path": str(problem_dir.relative_to(workspace)),
            "created_at": values["created_at"],
            "status": "draft",
        },
    )
    set_current_problem(workspace, problem_dir)
    write_test_commands(workspace)
    if (workspace / ".idea").is_dir():
        refresh_idea_modules(workspace)
    print(problem_dir.relative_to(workspace))
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    problem_dir = resolve_problem(args.problem)
    cases = load_cases(problem_dir)
    generated_count = 0
    if args.generated:
        generated_cases = load_generated_cases(problem_dir, args.generated_seed, args.generated_count)
        generated_count = len(generated_cases)
        cases.extend(generated_cases)
    if not cases:
        raise AlgoLabError("no test cases found in tests/cases.json")
    interface = load_interface(problem_dir)
    language = args.language or problem_default_language(problem_dir)
    workspace = require_workspace(problem_dir)
    supported_languages = configured_solution_languages(workspace)
    if language not in supported_languages:
        raise AlgoLabError(f"solution language `{language}` is not enabled in config")
    runner_languages = configured_runner_languages(workspace)
    if language not in runner_languages:
        raise AlgoLabError(
            f"local runner for `{language}` is not enabled; "
            f"enabled runners: {', '.join(runner_languages)}; "
            f"runner files live under `algolab/runners/<language>.py`"
        )
    try:
        actuals = run_case_batches(
            problem_dir,
            language,
            interface,
            cases,
            args.jobs,
            args.batch_size,
            args.fail_fast,
            args.case_timeout,
        )
    except RunnerError as exc:
        raise AlgoLabError(
            f"{exc}; runner files live under `algolab/runners/<language>.py`"
        ) from exc
    passed = 0
    failures: list[str] = []
    rows: list[dict[str, Any]] = []

    for index, case in enumerate(cases, start=1):
        actual = actuals[index - 1]
        if actual is NOT_RUN:
            continue
        name = str(case.get("name") or f"case-{index}")
        expected = case.get("expected")
        if isinstance(actual, RunnerError):
            raise AlgoLabError(
                f"{actual}; runner files live under `algolab/runners/<language>.py`"
            ) from actual
        ok, actual = evaluate_case_result(case, actual)
        if ok:
            passed += 1
            rows.append({"name": name, "status": "PASS", "expected": expected, "actual": actual})
            if not args.quiet:
                print(f"[PASS] {name}")
        else:
            failures.append(name)
            rows.append({"name": name, "status": "FAIL", "expected": expected, "actual": actual})
            print(f"[FAIL] {name}")
            print(f"  expected: {json.dumps(expected, ensure_ascii=False)}")
            print(f"  actual:   {json.dumps(normalize_json(actual), ensure_ascii=False)}")
            if args.fail_fast:
                break

    status = "pass" if passed == len(cases) else "fail"
    skipped = sum(1 for actual in actuals if actual is NOT_RUN)
    print(f"{passed}/{len(cases)} passed")
    if skipped:
        print(f"stopped early; skipped {skipped} unrun cases")
    if args.generated:
        print(f"generated cases: {generated_count}")
    if args.report_md is not None:
        report_path = None if args.report_md == "_default" else Path(args.report_md)
        print(
            f"report: {write_markdown_report(problem_dir, language, rows, passed, len(cases), report_path, args.report_limit, skipped)}"
        )
    if args.record:
        append_record(
            problem_dir,
            {
                "timestamp": utc_now(),
                "status": status,
                "command": f"test {problem_dir.name}",
                "passed": passed,
                "total": len(cases),
                "failures": failures,
            },
        )
    return 0 if passed == len(cases) else 1


def cmd_analyze_tests(args: argparse.Namespace) -> int:
    problem_dir = resolve_problem(args.problem)
    cases = load_cases(problem_dir)
    tag_counts: Counter[str] = Counter()
    compare_counts: Counter[str] = Counter()
    lines = [
        "",
        f"## Local Test Inventory - {utc_now()}",
        "",
        f"- Total cases: {len(cases)}",
    ]
    for case in cases:
        compare_counts[str(case.get("compare") or "exact")] += 1
        for tag in case.get("tags") or []:
            tag_counts[str(tag)] += 1
    if compare_counts:
        lines.append("- Compare modes: " + ", ".join(f"{key}={value}" for key, value in sorted(compare_counts.items())))
    if tag_counts:
        lines.append("- Tags: " + ", ".join(f"{key}={value}" for key, value in sorted(tag_counts.items())))
    lines.extend(["", "| Case | Compare | Tags |", "| --- | --- | --- |"])
    for case in cases:
        tags = ", ".join(str(tag) for tag in case.get("tags") or [])
        lines.append(f"| {case.get('name', '')} | {case.get('compare', 'exact')} | {tags} |")
    path = problem_dir / "records" / "test-analysis.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print(path)
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    problem_dir = resolve_problem(args.problem)
    record = {
        "timestamp": utc_now(),
        "status": args.status,
        "notes": args.notes or "",
    }
    if args.command:
        record["command"] = args.command
    if args.duration_ms is not None:
        record["duration_ms"] = args.duration_ms
    path = append_record(problem_dir, record)
    print(path)
    return 0


def read_attempts(problem_dir: Path) -> list[dict[str, Any]]:
    path = problem_dir / "records" / "attempts.jsonl"
    if not path.is_file():
        return []
    attempts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            attempts.append(json.loads(line))
    return attempts


def cmd_stats(args: argparse.Namespace) -> int:
    workspace = require_workspace()
    config = load_config(workspace)
    problems_dir = workspace / config.get("problems_dir", "problems")
    index = load_index(workspace)
    entries = index.get("problems", [])
    if entries:
        problem_dirs = [workspace / entry["path"] for entry in entries if (workspace / entry["path"] / "meta.json").is_file()]
    else:
        problem_dirs = sorted(path for path in problems_dir.iterdir() if (path / "meta.json").is_file())
    if not problem_dirs:
        print("no problems yet")
        return 0
    for problem_dir in problem_dirs:
        meta = json.loads((problem_dir / "meta.json").read_text(encoding="utf-8"))
        attempts = read_attempts(problem_dir)
        latest = attempts[-1]["status"] if attempts else "none"
        print(
            f"{problem_dir.name}\t{meta.get('difficulty', '')}\t{meta.get('topic', '')}\t"
            f"attempts={len(attempts)}\tlatest={latest}"
        )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    workspace = require_workspace()
    config = load_config(workspace)
    index = normalize_index(workspace)
    problems_dir = workspace / config.get("problems_dir", "problems")
    warnings: list[str] = []

    indexed_paths = set()
    for item in index.get("problems", []):
        path_text = str(item.get("path", ""))
        indexed_paths.add(path_text)
        if not (workspace / path_text / "meta.json").is_file():
            warnings.append(f"missing indexed problem: id={item.get('id', '')} path={path_text}")

    if problems_dir.is_dir():
        for child in sorted(problems_dir.iterdir()):
            if child.is_dir() and (child / "meta.json").is_file():
                relative = str(child.relative_to(workspace))
                if relative not in indexed_paths:
                    warnings.append(f"unindexed problem directory: path={relative}")

    if warnings:
        for warning in warnings:
            print(f"[WARN] {warning}")
        return 1
    print("workspace structure ok")
    return 0


def cmd_refresh_tests(args: argparse.Namespace) -> int:
    workspace = require_workspace()
    ensure_current_problem(workspace)
    path = write_test_commands(workspace)
    print(path)
    return 0


def cmd_current(args: argparse.Namespace) -> int:
    workspace = require_workspace()
    if args.problem:
        problem_dir = resolve_problem(args.problem)
        workspace = require_workspace(problem_dir)
        link_path = set_current_problem(workspace, problem_dir)
        write_test_commands(workspace)
        if (workspace / ".idea").is_dir():
            refresh_idea_modules(workspace)
        print(f"{link_path.relative_to(workspace)} -> {problem_dir.relative_to(workspace)}")
        return 0

    current_problem = ensure_current_problem(workspace)
    if current_problem is None:
        print("current problem is not set")
        return 1
    write_test_commands(workspace)
    entry = preferred_problem_entry(workspace)
    target = str(entry.get("path")) if entry is not None else str(current_problem.relative_to(workspace))
    if (workspace / ".idea").is_dir():
        refresh_idea_modules(workspace)
    print(f"{current_link_path(workspace).relative_to(workspace)} -> {target}")
    return 0


def cmd_refresh_idea(args: argparse.Namespace) -> int:
    workspace = require_workspace()
    count = refresh_idea_modules(workspace)
    print(f"refreshed {count} current Java IDEA module(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="algolab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize an algolab workspace")
    init_parser.add_argument("path", nargs="?", default=".")
    init_parser.add_argument("--ui-locale", default="zh-CN")
    init_parser.add_argument("--problem-locale", default="zh-CN")
    init_parser.add_argument("--force", action="store_true", help="overwrite managed scaffold files")
    init_parser.set_defaults(func=cmd_init)

    new_parser = subparsers.add_parser("new", help="create a problem folder")
    new_parser.add_argument("--slug", required=True)
    new_parser.add_argument("--title")
    new_parser.add_argument("--topic", default="general")
    new_parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default="medium")
    new_parser.add_argument("--solution-language", default="python")
    new_parser.add_argument("--force", action="store_true")
    new_parser.set_defaults(func=cmd_new)

    test_parser = subparsers.add_parser("test", help="run local JSON cases against a solution")
    test_parser.add_argument("problem")
    test_parser.add_argument("--language")
    test_parser.add_argument("--quiet", action="store_true")
    test_parser.add_argument("--generated", action="store_true", help="include deterministic cases from tests/generator.py")
    test_parser.add_argument("--generated-count", type=int, default=100, help="number of generated cases to request")
    test_parser.add_argument("--generated-seed", type=int, default=0, help="seed passed to tests/generator.py")
    test_parser.add_argument("--jobs", type=int, default=0, help="parallel test workers; 0 picks a conservative default")
    test_parser.add_argument("--batch-size", type=int, default=25, help="cases per worker batch")
    test_parser.add_argument(
        "--case-timeout",
        type=float,
        default=DEFAULT_CASE_TIMEOUT_SECONDS,
        help="seconds allowed per individual case; 0 disables runner-level case timeout",
    )
    test_parser.add_argument("--fail-fast", dest="fail_fast", action="store_true", help="stop after the first error or failed case")
    test_parser.add_argument("--no-fail-fast", dest="fail_fast", action="store_false", help="run all cases even after failures")
    test_parser.add_argument("--report-limit", type=int, default=80, help="max rows to show in Markdown report; -1 shows all")
    test_parser.add_argument(
        "--report-md",
        nargs="?",
        const="_default",
        help="write a Markdown result table; default path is records/test-results.md",
    )
    test_parser.add_argument("--record", action="store_true", help="append test result to records/attempts.jsonl")
    test_parser.set_defaults(fail_fast=True)
    test_parser.set_defaults(func=cmd_test)

    analyze_parser = subparsers.add_parser("analyze-tests", help="append a deterministic test inventory")
    analyze_parser.add_argument("problem")
    analyze_parser.set_defaults(func=cmd_analyze_tests)

    record_parser = subparsers.add_parser("record", help="append an attempt record")
    record_parser.add_argument("problem")
    record_parser.add_argument("--status", choices=["pass", "fail", "partial", "skip"], required=True)
    record_parser.add_argument("--notes")
    record_parser.add_argument("--command")
    record_parser.add_argument("--duration-ms", type=int)
    record_parser.set_defaults(func=cmd_record)

    stats_parser = subparsers.add_parser("stats", help="print local progress summary")
    stats_parser.set_defaults(func=cmd_stats)

    doctor_parser = subparsers.add_parser("doctor", help="check workspace/index structural consistency")
    doctor_parser.set_defaults(func=cmd_doctor)

    refresh_tests_parser = subparsers.add_parser("refresh-tests", help="refresh current/TESTS.md from index")
    refresh_tests_parser.set_defaults(func=cmd_refresh_tests)

    current_parser = subparsers.add_parser("current", help="show or switch the current problem workspace")
    current_parser.add_argument("problem", nargs="?")
    current_parser.set_defaults(func=cmd_current)

    refresh_idea_parser = subparsers.add_parser("refresh-idea", help="refresh the stable IntelliJ IDEA module for current/solutions/java")
    refresh_idea_parser.set_defaults(func=cmd_refresh_idea)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except AlgoLabError as exc:
        print(f"algolab: {exc}", file=sys.stderr)
        return 2
