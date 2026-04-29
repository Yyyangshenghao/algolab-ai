# AlgoLab AI

AlgoLab AI 是一个仓库级本地算法刷题工作区，面向 AI coding agent 使用。你把仓库拉下来，在仓库根目录打开 Codex、Claude Code 或其他 AI coding 工具，然后用自然语言让 AI 出题、写测试、运行检查、记录复盘即可。

默认流程不需要安装全局 skill、plugin 或 MCP。

## 快速开始

1. clone 这个仓库。
2. 在仓库根目录打开你的 AI coding 工具。
3. 直接用自然语言提出 AlgoLab 任务。

示例：

- `给我出一道中等难度动态规划题，用 Python 作为默认解法语言。`
- `切到 0004，接下来我只在 current 目录里做。`
- `帮我给 longest-stable-subarray 补充边界测试。`
- `跑一下这道题的本地测试，并分析失败原因。`
- `根据最近的错题记录，推荐下一道练习题。`
- `用 C++ 新建一道滑动窗口题，但暂时不用跑本地判题。`

默认情况下，AI 是出题人和教练，不是答案生成器。新建题目不应该附带完整可运行解法，除非你明确要求“给答案”或“帮我实现”。

Codex 会读取 `AGENTS.md`。Claude Code 会读取 `CLAUDE.md`，而 `CLAUDE.md` 会导入 `AGENTS.md`。当任务属于 AlgoLab 时，AI 再读取本仓库内的 `skills/algolab/SKILL.md`。

`docs/AGENTS_zh.md` 是中文人工说明，不会默认导入，避免增加无关上下文。

## AI 会做什么

当你要求新建一道题时，AI 会在 `problems/<id>-<slug>/` 下创建：

- `problem.md`：题面、约束、样例、说明。
- `meta.json`：用于检索和索引的稳定元数据。
- `tests/interface.json`：语言无关的函数接口契约。
- `tests/cases.json`：语言无关的测试用例。
- `tests/generator.py` 和 `tests/oracle.py`：可选的确定性用例生成器和可信校验器。
- `records/`：生成报告、测试分析，以及可选的尝试/复盘记录。
- `solutions/<language>/`：你的解法工作区。

仓库里的 Python CLI 是给 AI 调用的辅助工具，不是要求用户手动使用的产品入口。AI 可以内部调用 `python3 -m algolab ...` 来稳定创建结构、运行检查、更新记录。

## 题目 ID 与 TESTS.md

每道受管理题目都有稳定数字 ID，例如 `0003`。

- `.algolab/index.json` 维护题库索引、`max_id` 和 `last_problem_id`。
- `current/TESTS.md` 是当前题目的本地命令文件，可以写入本机 checkout 的绝对路径。
- 通过辅助工具新建题目时，这两个文件会自动更新。
- 老题目录仍然可以通过 slug 访问，但测试时优先使用 ID。

新题创建后，`current/TESTS.md` 会显示两段命令：当前题目的直接命令，以及一段可修改变量的通用命令：

```bash
python3 -m algolab test current --language java --generated --generated-count 200 --generated-seed 0 --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md
```

```bash
PROBLEM_ID="current"
LANGUAGE="java"

python3 -m algolab test "$PROBLEM_ID" --language "$LANGUAGE" --generated --generated-count 200 --generated-seed 0 --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md
```

## 语言支持

解法语言由 `.algolab/config.json` 控制。

- `supported_solution_languages`：这个工作区允许创建哪些语言的解法目录。
- `runner_languages`：当前本地辅助工具能自动判题的语言。
- `runner_dir`：各语言 runner 适配器的相对路径。

默认解法语言：

- C：`solutions/c/solution.c`
- C++：`solutions/cpp/solution.cpp`
- Java：`solutions/java/Solution.java`
- Go：`solutions/go/solution.go`
- Python：`solutions/python/solution.py`
- Rust：`solutions/rust/solution.rs`

当前已经实现的本地 runner：Python、Java。

C、C++、Go、Rust 目前可以创建解法文件，但本地判题 runner 需要后续单独补。

runner 文件固定放在：

```text
algolab/runners/
  python.py
  java.py
  common.py
```

后续语言 runner 按这个约定补：

```text
algolab/runners/c.py
algolab/runners/cpp.py
algolab/runners/go.py
algolab/runners/rust.py
```

每个 runner 模块暴露同一个接口：

```python
def run_case(problem_dir, interface, case):
    ...
```

## 手动运行测试

用户也可以直接运行 AI 内部使用的同一条辅助命令。最简单的方式是打开 `current/TESTS.md`；要么直接跑最近题命令，要么修改 `PROBLEM_ID` 和 `LANGUAGE` 后跑变量命令。

运行 Java 测试：

```bash
python3 -m algolab test <id> --language java
```

运行 Java 测试并生成 Markdown 报告：

```bash
python3 -m algolab test <id> --language java --generated --generated-count 200 --generated-seed 0 --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md
```

报告路径会以绝对路径写入 `current/TESTS.md`，通常在：

```text
problems/<id>-<slug>/records/test-results.md
```

默认会在遇到编译错误、runner 错误、超时或首个失败用例后停止继续调度新 batch。单个用例默认 3 秒超时；只有明确需要完整失败列表或调整限制时，才使用 `--no-fail-fast` 或 `--case-timeout <秒数>`。

报告里会有一张紧凑表，展示已执行 case 的状态、期望值和实际值。

## IntelliJ IDEA

Java 练习文件采用 LeetCode 风格：默认包里的 `Solution.java`。为了避免多道题都叫 `Solution` 时互相冲突，AlgoLab 会维护一个极简本地 `current` 工作区，IDEA 只使用固定模块 `current/solutions/java`。

日常使用时，尽量只待在 `current/` 里：

```text
current/
  problem.md
  TESTS.md
  tests/
  solutions/<language>/
```

真实的 `problems/<id>-<slug>/` 目录只是后台持久化存储。Java 文件要从 `current/solutions/java/Solution.java` 打开，这样 IDEA 才会按 source root 识别。`records/`、报告别名、包导入桥和元数据别名都不放进 `current/`。

切换当前题目工作区：

```bash
python3 -m algolab current <id-or-slug>
```

手动调整题目目录后，可以刷新固定 IDEA 模块：

```bash
python3 -m algolab refresh-idea
```

如果项目已经有 `.idea/`，`algolab new` 新建题目后会自动把 `current` 切到新题，并刷新 IDEA 模块。

Java 解法约定：

- 后台文件：`solutions/java/Solution.java`
- 当前工作区文件：`current/solutions/java/Solution.java`
- 类名：`public class Solution`
- 方法名：读取 `tests/interface.json` 的 `entrypoint`，通常是 `solve`
- 不写 Java package
- `list<T>` 使用数组类型，例如 `list<int>` 对应 `int[]`

## 测试模型

测试用例不按语言复制。

- `tests/interface.json` 定义可调用接口：函数名、参数名、参数类型、返回类型和类型系统版本。
- `tests/cases.json` 存少量可读的语言无关输入/输出值。
- `tests/oracle.py` 存必要时使用的慢速可信解。
- `tests/generator.py` 用确定性脚本生成大量隐藏风格判题用例，不把几百行 JSON 存进上下文。
- 各语言 runner 是适配层：读取同一份 interface 和 cases，调用对应语言的解法，再比较结果。

默认使用 `input.args` 这种位置参数。`input.kwargs` 可以用于 Python 专项流程，但可移植题目应尽量避免。

生成用例脚本必须支持：

```bash
python3 tests/generator.py --seed 0 --count 200
```

并输出和 `tests/cases.json` 同结构的 JSON。

大量生成用例可以用批量并发评测：

```bash
python3 -m algolab test <id> --language java --generated --fail-fast --case-timeout 3 --jobs 4 --batch-size 25
```

Java 会使用批量 harness，每个 batch 编译一次，而不是每个 case 编译一次。

当前可移植类型词汇：

- `int`、`long`、`float`、`bool`、`string`
- `list<T>`
- `map<K,V>`
- `tuple<T1,T2,...>`
- `optional<T>`

## 题库增长

这个仓库设计时考虑了长期使用后题库变大的情况。

- `.algolab/index.json` 是轻量题库索引，用于发现、统计、推荐。
- AI 应先读索引，确定目标 ID 或 slug 后才打开完整题目目录。
- 除非当前任务需要，不应读取生成缓存、大型日志或无关历史记录。
- `python3 -m algolab doctor` 可检查索引过期或题目目录未入索引的问题。

## 国际化

国际化是工作区契约的一部分。

- `i18n.ui_locale`：AI 回复用户时的默认语言。
- `i18n.problem_locale`：新题题面的默认语言。
- `meta.json.locale`：某道题实际使用的语言。

题面、提示、讲解、复盘、测试分析等面向用户的内容按 locale 输出。JSON 字段名、目录名、slug、状态值、比较模式和脚本接口保持英文稳定。

## 题目结构

```text
problems/<id>-<slug>/
  problem.md
  meta.json
  solutions/
    c/solution.c
    cpp/solution.cpp
    java/Solution.java
    go/solution.go
    python/solution.py
    rust/solution.rs
  tests/
    interface.json
    cases.json
    generator.py
    oracle.py
  records/
    test-analysis.md
    test-results.md
    attempts.jsonl  # 可选，由 --record 创建
    review.md       # 可选，复盘时创建
```

## 配置

修改 `.algolab/config.json` 可以调整默认行为：

```json
{
  "default_solution_language": "python",
  "supported_solution_languages": ["c", "cpp", "java", "go", "python", "rust"],
  "runner_languages": ["python", "java"],
  "runner_dir": "algolab/runners",
  "i18n": {
    "ui_locale": "zh-CN",
    "problem_locale": "zh-CN"
  }
}
```

## 设计原则

稳定接口是文件结构和仓库内 AI 工作流规范。脚本只是实现细节，用来让 AI 的操作更稳定、可审计。

除非用户明确要求语言专项训练，否则题目和测试用例应保持语言无关。
