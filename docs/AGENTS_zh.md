# AlgoLab 工作区

本仓库是本地算法刷题工作区。用户通过自然语言和 AI 协作，不需要自己敲命令。

## 分发方式

- 这个仓库可以直接放到 GitHub；使用者 clone 后，在仓库根目录打开 Codex、Claude Code 或其他 AI coding 工具即可。
- 默认流程不要求用户安装全局 skill、plugin 或 MCP。
- `skills/algolab/SKILL.md` 是仓库内本地规范，只在这个项目中使用；不要自动复制到用户全局 skill 目录。
- `AGENTS.md` 是英文机器主入口；本文档只给中文用户阅读，不默认导入。

## 工作方式

- 出题、生成测试、评测、复盘、推荐下一题等 AlgoLab 请求，先读 `skills/algolab/SKILL.md`。
- fresh clone 后如果没有 `current/`，运行 `python3 -m algolab current` 重建本地当前题工作区。
- 用户入口是自然语言。需要脚本时，AI 自己调用并用自然语言汇报结果。
- `python3 -m algolab ...` 是 AI 内部辅助工具，不是要求用户手动执行的产品入口。
- 除非用户明确要求命令，否则不要把下一步交给用户去敲命令。
- 题目和测试用例应保持语言无关；解法优先放在 `solutions/<language>/`。
- 可用解法语言读取 `.algolab/config.json` 的 `supported_solution_languages`。
- 每道受管理题目都有稳定数字 ID；测试和定位优先使用 ID。
- `current/TESTS.md` 是本地紧凑测试命令表，应保留“最新题直接命令”和 `PROBLEM_ID`/`LANGUAGE` 变量命令，但不要在里面列出全部题目。
- 选定当前题目后，日常操作优先使用 `current/` 下的路径；`problems/` 只作为持久化存储。
- 题库变大后避免全量扫描；先读 `.algolab/index.json`，再按目标 slug 读取具体题目。

## AI 内部工具

- 初始化当前目录：`python3 -m algolab init .`
- 新建题目骨架：`python3 -m algolab new --slug <slug> --title "<title>" --topic <topic> --difficulty easy|medium|hard --solution-language <language>`
- 按 ID 运行本地评测：`python3 -m algolab test <id> --language <runner-language> --generated --generated-count 200 --generated-seed 0 --fail-fast --case-timeout 3 --jobs 4 --batch-size 25 --report-md`
- 切换当前题目工作区：`python3 -m algolab current <id-or-slug>`
- 生成测试分析记录：`python3 -m algolab analyze-tests <id>`
- 记录一次尝试：`python3 -m algolab record <id> --status pass|fail|partial|skip --notes "..."`
- 检查结构一致性：`python3 -m algolab doctor`
- 刷新当前测试命令表：`python3 -m algolab refresh-tests`
- 刷新本地 IDEA Java 模块：`python3 -m algolab refresh-idea`
- 查看统计：`python3 -m algolab stats`

## 协作规则

- 默认角色是出题人和教练，不是答案生成器。除非用户明确要求“给答案”或“实现代码”，否则不要提供完整可运行解法，也不要填充 `solutions/<language>/`。
- 做题库发现时，先读 `.algolab/index.json`，不要默认打开大量 `problems/` 文件。
- 只有确定目标题目后，才读取该题完整目录。
- 修改既有题目前，先读 `problem.md`、`meta.json`、`tests/interface.json`、`tests/cases.json` 和相关 `records/` 文件。
- 未经明确要求，不覆盖用户的 `solution.*` 和历史记录；需要记录时追加。
- 出题时必须分配下一个 ID，更新 `.algolab/index.json` 的 `max_id` 和 `last_problem_id`，刷新 `current/TESTS.md`，并同时产出题面、约束、样例、测试策略和初始测试用例。
- `current` 是极简当前题目工作区，只放 `problem.md`、`tests/`、`solutions/` 和本地 `TESTS.md` 命令文件。不要在里面加 `records/`、报告别名、包导入桥或元数据别名。用户说“切到 / 打开 / 当前做 / 继续某题工作区”时，AI 应自行运行 `algolab current <id-or-slug>`，不要把命令交给用户。
- 初始解法文件只能是占位模板；可以包含函数签名、`TODO` 或抛错 stub，但不能写入目标算法。
- 除非用户要求语言专项训练，否则题面不要绑定某一种编程语言。
- 测试应保持语言无关：`tests/interface.json` 定义可调用接口，`tests/cases.json` 存输入输出值。
- 新增测试时覆盖样例、边界、退化、随机或构造、反例五类。
- AI 应自行运行相关本地检查，然后用自然语言报告结果。
- 只有 `runner_languages` 中的语言支持本地 runner。当前已实现 Python 和 Java runner。
- runner 适配器固定放在 `algolab/runners/<language>.py`，并暴露 `run_case(...)`；为了性能，应优先补 `run_cases(...)`。
- 本地评测默认 fail-fast：遇到编译错误、runner 错误、超时或首个失败用例后，停止继续调度后续 batch。
- 单个用例默认 3 秒超时；除非用户明确调整 `--case-timeout`，否则超时视为时间复杂度不合格。
- 如果存在 `.idea/`，IDEA 只使用固定模块 `current/solutions/java`；切题时刷新当前解法软链接，而不是为每题创建新模块。Java 文件要从 `current/solutions/java/Solution.java` 打开，不要从 `problems/.../solutions/java` 打开。
- 不读取生成缓存、`__pycache__`、大型日志或无关历史记录，除非当前任务确实需要。

## 国际化

- 默认用户交互语言读取 `.algolab/config.json` 的 `i18n.ui_locale`。
- 默认题面语言读取 `i18n.problem_locale`，并写入新题目的 `meta.json.locale`。
- 面向用户的题面、提示、讲解、复盘、测试分析按 locale 输出。
- JSON 字段名、目录名、slug、状态值、比较模式和脚本接口保持英文稳定。
- 用户临时指定语言时，以用户本次请求为准，并在 `meta.json.locale` 或相关记录中体现。
