# VibeLoom v0.3 ↔ DeepSeek Harness (DSH) 适配度报告

Status: analysis, no code changed
Scope: `v03/` skill surface + `v03/engine/` vs DSH `@deepseek-ai/dsh` 0.2.0-rc.2
Companion: [`dsh-adaptation-plan.md`](dsh-adaptation-plan.md) — 本报告结论对应的执行计划

---

## 1. 结论摘要

**可移植性高，但不能零改动直接跑。**

v03 的规范层（methodology / implementation / templates / engine / references）几乎可以原样复用：DSH 的 skill 资源基址解析、原生 `AGENTS.md` 加载、并行子代理、`workflow` 结构化结果都能承接 v03 的模型。真正的缺口集中在三处：

1. **`SKILL.md` 的 frontmatter 是非法 YAML** → 技能被静默丢弃（当前在 DSH 上根本加载不了）。
2. **安装布局与多版本同名遮蔽** → 仓库根不是合法的 skill 根；误配会让已归档的 `v01` 胜出。
3. **`execute_plan` 无法被 DSH 驱动** → §13.3 的并行语义必须由模型或 `workflow` 重新实现。

外加一个环境级约束：**`workspace-write` 沙箱只允许写 session workspace**，因此 v03 只能治理「当前 workspace 内的仓库」。

### 适配度评分

| 维度 | 适配度 | 判定 |
|---|---|---|
| Skill 发现 / 加载 | 0%（当前）→ 95%（修 2 字节后） | `v03/SKILL.md` frontmatter 解析失败，整条技能被丢弃 |
| 资源按需加载（references / tasks / artifacts / engine） | 95% | DSH 注入 `Base directory for this skill: <path>`，所有相对路径解析正确 |
| 安装 / 多版本布局 | 40% | 需专用 bundle 目录或符号链接；仓库根会命中 v01 |
| 命令 / 参数交互 | 60% | `/vibeloom` 可用；`$vibeloom` 是死写法；`argument-hint` 无效；无参数替换 |
| 引擎调用 | 80% | `python -m vibeloom_engine` 实测可跑（0.3.0 / Python 3.13.5）；写入受沙箱限制 |
| 并行编排（dispatch / waves） | 45% | `execute_plan` 无 CLI 入口；子代理无结构化返回 |
| 补丁 / 原子写入 | 30% | DSH 无 staging tree + 原子 apply 原语 |
| 上下文产物（AGENTS.md / CLAUDE.md） | 75% | 根级被 DSH 原生吸收；per-scope 需 touch 触发；CLAUDE.md 重复会被去重 |
| 审批门 | 70% | 需改用 `ask_user_question`，且只能在根代理 |
| 子代理契约（task header） | 50% | DSH 无 header 概念，只有 3–5 词 `description` + 自由文本 `prompt` |

---

## 2. 方法与证据来源

- 逐字阅读 v03 skill 面：[`SKILL.md`](SKILL.md)、[`subagent-prompt.md`](subagent-prompt.md)、[`references/runtime.md`](references/runtime.md)、[`references/modes.md`](references/modes.md)、[`tasks/generate-code-component.md`](tasks/generate-code-component.md)、[`tasks/generate-context.md`](tasks/generate-context.md)、[`vibeloom-implementation.md`](vibeloom-implementation.md) §13–§14、[`SKILL-README.md`](SKILL-README.md)。
- 阅读 DSH 安装包（`/home/asuka/.npm/_npx/1e7f6d9597241db0/node_modules/@deepseek-ai/`）的 README + shipped `lib/` 源码：`dsh-skill`、`dsh-skill-filesystem`、`dsh-tool-skill`、`dsh-tool-subagent`、`dsh-subagent*`、`dsh-tool-workflow`、`dsh-workflow*`、`dsh-tool-goal`、`dsh-tool-ask-user`、`dsh-agent-instructions`、`dsh-sandbox*`、`dsh-fs-sandbox`、`dsh-bash-sandbox`、`dsh-user-approval`、`dsh-hooks-claude-code`、`dsh-hooks-codex`、`dsh-base/cordis.patch.yml`、`dsh-web-app/presets/*.patch.yml`。
- 本机实测：YAML 解析、引擎运行、沙箱边界、安装副本 diff、bundle 体积、`extract-templates.py --check`。

本机 DSH 环境事实：`DSH_HOME=/home/asuka/.dsh`，profile `web`，skill 已手工安装于 `~/.dsh/skills/vibeloom/`（v03 的完整拷贝），`$DSH_BUNDLED_SKILL_DIR` 未设置。

---

## 3. 兼容面（可原样复用）

- **资源基址解析正确。** 本地 provider 为每个技能设置 `resourceBase = {kind:"directory", path: <bundle dir>}`（`dsh-skill-filesystem/lib/index.js:605-608`、`:126-129`），tool 结果渲染为：

  ```
  Base directory for this skill: <path>
  Resolve relative paths mentioned by this skill against the base directory before using them.
  ```

  因此 `references/*.md`、`tasks/*.md`、`artifacts/**`、`subagent-prompt.md`、`vibeloom-methodology.md`、`engine/` 全部解析正确。资源是「指引」不是「附件」——DSH 不会内联或枚举，模型按需用文件工具读取，这正是 v03 load-on-demand 设计想要的。

- **`SKILL.md` 路由表可用。** DSH 的用户手势 `/name` 会把整份 skill body 注入当前 step，`/vibeloom` 之后的文字原样进入用户消息——模型从原始文本解析 `operation`/`target`，v03 的显式路由表（`SKILL.md` §Command routing）正好是这个模式。

- **`AGENTS.md` 有原生协同。** DSH `dsh-agent-instructions` 默认加载 `$DSH_HOME/AGENTS.md` + 项目根（`.git` 标记）→ session cwd 链上的 `AGENTS.md` / `CLAUDE.md`（`lib/index.js:17-18`、`:576-578`）。v03 `generate context` 产出的根级 `AGENTS.md` 会被自动吸收。

- **审批门有真原语。** `ask_user_question`（blocking 默认）支持 `questions[{id, question, header?, options[{label, description}], multi_select?}]`，返回 `{answers:[{id, selected[], custom?}]}`，是真正的暂停门。与 v03「orchestrator mediates all context and approval」的设计天然一致。

- **并行/深度上限够用。** 同一消息内并行 `subagent` 调用上限 `maxParallelToolCalls` 默认 10（v03 默认 `max_wave_size=5`）；`maxDepth` 默认 1（v03 只需 orchestrator→leaf 一层）。

- **引擎可跑。** `PYTHONPATH=v03/engine python3 -m vibeloom_engine --version` → `vibeloom-engine 0.3.0`（Python 3.13.5）；`status` / `parse` 在 workspace 内正常输出 JSON。零依赖假设成立。

- **门禁自洽。** `v03/extract-templates.py --check` 当前通过（`OK: 41 templates match disk`）；`check-links.py` 只扫描固定 skill 面（`SKILL.md`、`subagent-prompt.md`、`SKILL-README.md`、`references/*.md`、`tasks/*.md`、`artifacts/**/*.md`、`examples/*.md`），本报告与计划文件不在其扫描范围。

---

## 4. 硬阻断（必须修）

### 4.1 `v03/SKILL.md` frontmatter 非法 YAML → 技能被静默丢弃

`description` 未加引号且含 `(modes: vibe, ...)` 的 `": "`，YAML 解析直接失败。实测（`yaml@2.9.1`，DSH 使用的库）：

```
v01 OK name=vibeloom
v02 PARSE ERROR: bad indentation of a mapping entry (2:227)
v03 PARSE ERROR: bad indentation of a mapping entry (2:226)
```

DSH 在 `parseFrontmatter` 抛错时只 `logger.warn` 并 `return`（`dsh-skill-filesystem/lib/index.js:671-674`），**模型目录里没有任何 per-skill 诊断**——表现是「技能不存在」。

canonical 源在 [`vibeloom-templates.md`](vibeloom-templates.md) 第 180 行（`SKILL.md` 是由它抽取生成的），所以修复必须落在模板源上，再重跑抽取器，否则 `--check` 会失败。

旁证：本机 `~/.dsh/skills/vibeloom/SKILL.md` 与仓库 v03 的**唯一差异就是给 description 加了双引号**（diff 仅 2 字节）——已有人手工绕过。

DSH 的 YAML 比预期严格：**重复键**、`description` 被解析成数字/布尔、值里未加引号的 `": "`，都会导致整条技能被丢弃。

### 4.2 安装布局 + 同名遮蔽

DSH 只发现 `<root>/<name>/SKILL.md` 或 `<root>/<name>.md`，**深度恰好一层**，不做 `**/SKILL.md` 递归（`dsh-skill-filesystem/lib/index.js:583`、`:586-593`）。

而 `v01`、`v02`、`v03` 的 frontmatter `name` **全都是 `vibeloom`**。同层重复名按 rank → provider 注册序 → provider 本地序解析（本地序 = 目录名字典序）first-wins。若把仓库根放进 `customSkillDirs`，同时发现 `v01/SKILL.md`、`v02/SKILL.md`、`v03/SKILL.md` → **`v01`（已归档）胜出**。

正确做法：专用 bundle 目录或符号链接，例如 `~/.dsh/skills/vibeloom -> <repo>/v03`（DSH 支持符号链接目录，`dsh-skill-filesystem/README.md:40`）。仓库目前**没有** `.dsh/skills/`，也没有任何 DSH 安装说明；`getting-started.md` 只覆盖 Claude Code / Codex。

注意：`name` 不要求与目录名一致（`dsh-skill-filesystem/lib/index.js:586-597` 不比较二者），所以「目录叫 v03、name 叫 vibeloom」是合法的——这正是遮蔽风险的来源。

### 4.3 `execute_plan` 无法被 DSH 驱动

[`engine/vibeloom_engine/dispatch.py`](engine/vibeloom_engine/dispatch.py) 的 `execute_plan(plan, callback)` 是**库 API**：`callback` 由宿主接到真实的 subagent spawn 上。引擎 CLI 只有 `parse / graph / eval / affected / staleness / detect-edits / dispatch / status / decisions`，**没有 execute 命令**（`python3 -m vibeloom_engine --help` 实测）。

DSH 的 `subagent` 是**模型工具**，Python 进程无法回调。因此 §13.3 的并行语义在 DSH 上必须由模型循环（或 `workflow` 脚本）重新实现；引擎只能提供 `dispatch` 出的 plan。`engine-build-report.md` 也自认「`execute_plan` callback harness」是未接线的部分。

---

## 5. 环境级约束

### 5.1 `workspace-write` 是硬边界

写只允许 session workspace root + `/tmp`（`dsh-sandbox/lib/index.js:166-172`）。实测：

```
$ touch /home/asuka/Dev/.dsh_probe_write
touch: 无法 touch '/home/asuka/Dev/.dsh_probe_write': 只读文件系统
```

bash 也是被 confine 的（base bundle 挂的是 `dsh-bash-sandbox`，不是 `dsh-bash-local`）：`bash -c` 被 bwrap/Landlock/Seatbelt 包裹，Python 子进程继承 mount namespace / Landlock domain，宿主是 `--ro-bind / /`，只有 workspace root 是 rw bind。

**结论**：引擎只能治理 session workspace 内的仓库；用户指定的外部仓库连 `python3` 都写不进去。拒绝报告是 `[sandbox: file access denied under workspace-write mode]`（`FS_SANDBOX_DENIED`）。

### 5.2 提权可用性在根代理与子代理之间不同

- 根会话：`workspace-write` + approval `ask` → 可请求一次性提权到 `danger-full-access`。
- 子代理：approval **固定为 `never`**（`dsh-subagent/lib/types/child-agent.js:181,206-208`），**永远无法提权**；需要审批的操作被自动拒绝。

因此「外部仓库治理」只能在根代理、且需用户同意的前提下发生。

### 5.3 其他约束

- **子代理不能问用户。** `ask_user_question` 对 live child 返回 `DELEGATED_CALLER`（`dsh-user-questions/lib/index.js:534`）。审批门必须在根代理——与 v03 设计一致，但必须写进技能。
- **无 per-child timeout。** `dsh-subagent` / `dsh-tool-subagent` / driver 中零 `timeout`；deadline 需自行执行。
- **`fs` 观察策略摩擦。** `write` 拒绝覆盖未读过的文件、`edit` 要求先读，且观察不跨 resume（`FS_NOT_OBSERVED` / `FS_STALE_VERSION`）。对 `reconcile` / 重生成流程有实际摩擦。
- **DSH 部分上限是 volatile host settings**（`maxParallelToolCalls`、`subagent.maxDepth`、`maxActiveSubagents`）→ 不要把数字硬编码进技能语义。

---

## 6. 半兼容项（需改造）

| v03 假设 | DSH 实际 | 需要的改造 |
|---|---|---|
| `$vibeloom` 或 `/vibeloom` | 只有空白边界的 `/vibeloom`；全客户端无 `$` 手势（只有 `/` 和 `@`） | 删掉 `$` 写法 |
| `argument-hint` | 未知键被容忍但从不解析；DSH 无 argument-hint 面 | 降级为文档，或删除 |
| 命令参数解析 | `/name` token 之后文字原样进用户消息；无 `$ARGUMENTS`/`$1` 替换；body 不做模板化 | SKILL.md 需显式要求模型从原文解析 operation/target |
| `result_shape_id` / `summary.yaml` 校验 | `subagent` 工具只返回最终文本，**无 schema/outputSchema 参数** | 用 `workflow` 的 `agent(prompt,{schema})` 拿校验后对象；或要求子代理输出 fenced JSON |
| §13.4 subagent task header | DSH 无 header 概念；只有 `description`(3–5 词) + 自由文本 `prompt`；`subagent/descriptor` 仅日志、模型不可见 | header 只能作为 prompt 内嵌 YAML，靠模型自律 |
| §14 staging patch + 原子 apply | 子代理直接持 write/bash 落盘；无原子多文件提交原语；`workspace-changes` **不记录子代理会话** | 技能自定 staging 约定（子代理写 `.vibeloom/runs/.../files/`，编排者校验后搬运）；变更卡片看不到子代理写入 |
| 「halt and surface findings」审批门 | `ask_user_question`（blocking）是唯一真门；`NO_PROVIDER`/`ASK_ABORTED`/`DELEGATED_CALLER` 都是**未批准** | 显式改用 `ask_user_question`，失败即未批准 |
| root + per-container + per-component `AGENTS.md` / `CLAUDE.md` | baseline 只加载项目根→cwd 链上的直接子文件；嵌套文件只在 read/write/edit 触达后才加载（bash 写不触发）；内容相同的 `CLAUDE.md` 会被去重；`context/AGENTS.md` 形式不会被加载 | 根级只生成 `AGENTS.md`（`CLAUDE.md` 可做一行指针）；per-scope 由子代理显式 read |
| 「子代理不得加载 skill/methodology/implementation」 | DSH 子代理**有** skill 目录与 `skill` 工具，无法强制 | 只能靠 prompt 纪律；不要用 `subagent_fork`（会继承编排者完整上下文，泄漏 skill 文档），用 `subagent`（fresh，无父会话） |
| `subagent-prompt.md:51` 指向 `templates/tasks/{{template_id}}.md` | 实际路径是 `tasks/`；DSH 下子代理会读到不存在的文件 | 修路径 |
| Claude Code hooks / `.claude/commands/*.md` | hooks 需显式 `configPath`、仅 7 个事件、仅 shell handler、语义部分实现；`.claude/commands/*.md` 完全不存在 | 不要把审批门放在 CC hooks 里 |
| 技能包构成 | bundle 2.3 MB，其中约 1.2 MB 是 `site/`、`adversarial-*`、`build-*`、manifesto/comparison HTML，且带 `engine/__pycache__` | 精简（不影响上下文，只影响包体） |

---

## 7. 未被利用的 DSH 能力（机会）

- **`workflow`** —— 最贴近 v03 §13 的替代实现：把 `engine dispatch` 的 waves 作为 `args` 传入，脚本用 `pipeline`/`parallel` 扇出、`agent(prompt,{schema})` 校验结果、`phase()` 报进度。并发约 `CPU-2`（≤16），`maxTotalAgents` 1000，`maxItemsPerCall` 4096。脚本无 fs/network API；`agent()` 普通失败返回 `null`（需 `.filter(Boolean)`）；schema 只支持 `type/properties/required/additionalProperties/items/enum/const/oneOf`（对象根）。
- **`create_goal` / goal rounds** —— 同会话多波自主续跑，适配长 `generate`。约束：默认 256 轮、到顶只能 `edit` 提额不能 `resume`；resume/fork 后需人类重新 arm；`blocked` 对模型上报需连续 ≥3 轮；create/edit/pause/resume 需直接人类消息。
- **后台 job** —— `run_in_background` + `job_output`/`job_kill` + 结算通知，大扇出无槽位压力；进程本地、随 harness 进程消亡，需在波次末尾显式 `job_output(wait:true)` 清扫（存在结算通知不唤醒的窗口）。
- **`todo_write`** 展示 wave/scope 进度；**`present`** 交付物卡片（子代理创建的文件必须由父代理自己 present）。
- **`subagent_fork`** —— 可让子代理继承编排者的已完成轮次；与 v03 的 load-set 纪律冲突，仅在明确需要编排上下文时使用。
- **计划模式不能当审批门**：`/plan` 仅用户可触发，模型只有 `exit_plan_mode`，且不强制任何限制（guidance only）。

---

## 8. 与仓库既有门禁的关系

适配改动必须尊重三条现有门禁：

1. **`vibeloom-templates.md` 是 canonical 源。** `SKILL.md`、`subagent-prompt.md`、`references/`、`tasks/`、`artifacts/` 都由 [`extract-templates.py`](extract-templates.py) 抽取。**改抽取产物无效**——必须改模板源再重抽取。
2. **`extract-templates.py --check` 是漂移门禁**，由 [`build-bundle.sh`](build-bundle.sh) 在打包前执行（当前通过，41 个模板一致）。
3. **`check-links.py` 是链接门禁**，由同一脚本执行；扫描范围是固定 skill 面，本报告与计划文件不在其中。

---

## 9. 附：实测记录

| 实测 | 命令 | 结果 |
|---|---|---|
| 引擎版本 | `PYTHONPATH=v03/engine python3 -m vibeloom_engine --version` | `vibeloom-engine 0.3.0`（Python 3.13.5） |
| 引擎 status | `... --repo /home/asuka/Dev/vibeloom status` | 正常 JSON，`current_mode: vibe`，exit 0 |
| 引擎 CLI 无 execute | `... --help` | 9 个子命令，无 execute |
| 沙箱外写 | `touch /home/asuka/Dev/.dsh_probe_write` | `只读文件系统`（拒绝） |
| v03 frontmatter | `yaml.load`（yaml@2.9.1） | `bad indentation of a mapping entry (2:226)` |
| v01 / v02 frontmatter | 同上 | v01 OK / v02 报错 |
| 安装副本差异 | `diff v03/SKILL.md ~/.dsh/skills/vibeloom/SKILL.md` | 仅 description 加引号（2 字节） |
| 模板漂移门禁 | `python3 v03/extract-templates.py --check` | `OK: 41 templates match disk` |
| bundle 体积 | `du -sh ~/.dsh/skills/vibeloom` | 2.3 MB（核心 ~732 KB） |
