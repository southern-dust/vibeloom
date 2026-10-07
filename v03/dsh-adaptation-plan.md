# DSH 适配计划（v03 → DeepSeek Harness）

Status: plan, not started
Input: [`dsh-adaptation-report.md`](dsh-adaptation-report.md) — 适配度分析与全部证据
Target harness: DSH `@deepseek-ai/dsh` 0.2.0-rc.2（profile `web`，`workspace-write` + approval `ask`）
Canonical constraint: `vibeloom-templates.md` 是 skill 面的唯一源；`SKILL.md` / `subagent-prompt.md` / `references/` / `tasks/` / `artifacts/` 均由 [`extract-templates.py`](extract-templates.py) 抽取

---

## 决策记录

| # | 决策 | 选定 | 日期 |
|---|---|---|---|
| D1 | 轨道 A 落点 | **(b) v03 旁路**：只改 `vibeloom-templates.md` 一处 + 新增 `v03/dsh/`；既有 skill 面不动 | 2026-10-07 |
| D2 | 波次编排实现 | **`workflow` 脚本 + `agent(prompt,{schema})`** | 2026-10-07 |

### M0 进度

| 项 | 状态 | 产物 |
|---|---|---|
| A1 frontmatter 修复 | **done** | `vibeloom-templates.md` description 加引号 → 重抽取（1 written / 40 unchanged） |
| A1 门禁脚本 | **done** | `v03/dsh/check-skill-frontmatter.py`（strict YAML + structural 双重检查；无 PyYAML 时降级为 structural） |
| A1 门禁接线 | **done** | `build-bundle.sh` step 0 第三条 gate |
| A2 安装入口 | **done** | `v03/dsh/install.sh`（user/project scope、dry-run、uninstall、幂等、拒绝删除真实目录） |
| A2 宿主说明 | **done** | `v03/dsh/README.md` |
| A3 宿主参考 | **done** | `references/host-dsh.md`（8 节，覆盖 invocation / approval / subagents / sandbox-context 四个 seam）+ `SKILL.md` Runtime references 指针 |
| A4 subagent-prompt | **done** | `templates/tasks/` → `tasks/` 路径修复 + fresh-context 宿主说明 |
| A5/A6 波次运行器 + 落盘协议 | **done** | `v03/dsh/wave-runner.md`（配方 + workflow 脚本模板 + 子代理 prompt 形状 + landing 协议 + caps）与 `v03/dsh/dispatch-to-workflow.py`（plan → workflow args，含波内写范围重叠校验）；`references/host-dsh.md` §6/§7 已加指针。A5 与 A6 合并为一份文档 |
| A7 DSH 上下文产物规则 | **done** | `tasks/generate-context.md` + `artifacts/context/{root,container,component}-config.md` 各加一条宿主分支（根级只出 `AGENTS.md`、per-scope 需显式 read、不要 `context/AGENTS.md`） |
| M2 额外修复 | **done** | 发现并修正既有文档缺陷：SKILL.md 引擎章节把全局 `--repo` 写在子命令之后、且 `dispatch` 参数误写为 `--affected`（实为 `--ids`）。所有既有引擎调用示例都会失败 |

**M2 遗留**：`v03/site/public/implementation.html:208` 仍写着 `dispatch --repo <path> --affected <IDs>`。那是已部署站点的实现页，不属于 skill 面，本计划未改——需要单独决定是否一并修正。

M0 遗留（不阻塞 M1）：`v03/dsh/` 目前**不进发布 bundle**——`build-bundle.sh` 只拷贝显式清单，且 `dsh/README.md` 的 `../vibeloom-templates.md` 等链接在 bundle 内不解析，会让 step-7 链接门禁失败。若要让 tarball 用户也能一键安装，需要单独设计（例如 bundle 内一份自包含的 `DSH-INSTALL.md`）。

---

## 0. 目标与非目标

**目标**

- G1 v03 在 DSH 上可被**发现并加载**（`/vibeloom` 手势与 `skill` 工具都能命中）。
- G2 v03 的审批门在 DSH 上有真原语（`ask_user_question`），且失败即未批准。
- G3 v03 的波次生成能在 DSH 上真正跑起来（`engine dispatch` → 并行子代理 → 校验 → 落盘）。
- G4 上述改动不破坏 Claude Code / Codex 安装面，且通过仓库既有门禁。

**非目标（本计划不做）**

- 不重写 v03 的 methodology / implementation 规范语义。
- 不把 v03 迁移到 `file-layout.md` 的 v04 新布局。
- 不为 DSH 之外的宿主（ACP、Codex、Claude Code）新增适配。
- 不在 v03 上实现 v04 的 roadmap 特性（dry-run、contract REPL 等）。

---

## 1. 策略：两条轨道

| | 轨道 A — v03.x 兼容补丁 | 轨道 B — v04 一等公民 |
|---|---|---|
| 目的 | 让当前生产版本在 DSH 上可用 | 把 DSH 作为第一类宿主纳入 v04 设计 |
| 范围 | 安装入口 + host adapter 文档 + 3 处修正 | host 抽象、workflow-native 编排、goal 长跑、结构化结果 |
| 交付面 | `v03/dsh/` + 少量模板修正 | `v04/` canon |
| 风险 | 低（不改语义，只加 host 层） | 中（改架构） |
| 依赖 | 无 | 轨道 A 的实战反馈 |

**推荐：先做轨道 A 的 M0–M2（让 v03 真能跑），把轨道 B 的结论回写进 `v04/intent.md` 的 CAP/CST。** 轨道 A 的 adapter 文档同时是轨道 B 的需求规格。

> ⚠️ 政策冲突需先决策：[`file-layout.md`](../file-layout.md) 声明 `v01/ v02/ v03/` 是 **FROZEN — do not touch**，而根 [`README.md`](../README.md) 声明 v03 是 **Current + runnable**。轨道 A 必然要动 v03。三个选项见 §6「待决策」。

---

## 2. 轨道 A 工作项

所有涉及 skill 面（`SKILL.md`、`subagent-prompt.md`、`references/`、`tasks/`、`artifacts/`）的改动，**必须**：改 `vibeloom-templates.md` → 跑 `python3 v03/extract-templates.py` → `--check` 通过。新增 `references/*.md` 必须作为 `template:references/<name>.md` 块加入模板源，否则 `--check` 的 orphan 检测会失败。

### A1 — 修复 frontmatter YAML（P0，阻断加载）

- **改**：[`vibeloom-templates.md`](vibeloom-templates.md) 第 180 行（`template:skill/SKILL.md` 块内的 `description:`），加引号或改 YAML block scalar。
- **同步**：模板源中所有 `name`/`description` 含 `": "` 或 YAML 指示符的字符串。
- **重抽取**：`python3 v03/extract-templates.py`。
- **新增门禁**：`v03/check-skill-frontmatter.py` —— 对抽取后的 `SKILL.md` 做「first line 是 `---`、frontmatter 可被严格 YAML 解析、`name` 满足 `^[a-z0-9]+(-[a-z0-9]+)*$`、`description` 为非空字符串、无重复键」的 decidable 检查；接入 [`build-bundle.sh`](build-bundle.sh) 的 gate 段（当前 gate 段在 86–90 行附近）。
- **验收**：
  - `node -e "yaml.load(frontmatter of v03/SKILL.md)"` 成功；
  - `python3 v03/extract-templates.py --check` → `OK`；
  - `python3 v03/check-links.py --root v03 --quiet` → exit 0；
  - `python3 v03/check-skill-frontmatter.py` → exit 0。
- **注意**：`v02/SKILL.md` 有同样缺陷，但 v02 已冻结——是否顺手修见 §6。

### A2 — DSH 安装入口（P0，阻断发现）

- **新增**：`v03/dsh/install.sh`（用户侧运行，幂等，支持 `--project` / `--user` / `--uninstall`）。
  - 用户级：`ln -sfn <repo>/v03 ~/.dsh/skills/vibeloom`
  - 项目级：`ln -sfn ../../v03 <repo>/.dsh/skills/vibeloom`
  - 依赖 `DSH_HOME`（默认 `~/.dsh`）；支持 `--dsh-home` 覆盖。
- **新增**：`v03/dsh/README.md` —— 安装、验证、卸载、排障。
- **必写警告**：**不要**把仓库根（或任何同时含 `v01/`、`v02/`、`v03/` 的目录）放进 `customSkillDirs`：三者 `name` 都是 `vibeloom`，同层 first-wins 会命中 `v01`（已归档）。必须使用只含 v03 bundle 的目录或符号链接。
- **必写事实**：`install.sh` 写 `~/.dsh/skills` 位于 DSH 沙箱之外，**必须由用户在 harness 之外运行**；在 `workspace-write` 会话内由代理运行会被拒绝。
- **验收**：安装后 DSH 技能目录出现 `vibeloom` 且描述为 v03 文案；`/vibeloom status` 在 DSH 中可触发并返回 scope/decision/affected/next。

### A3 — DSH host adapter 参考（P0）

- **新增**：`v03/references/host-dsh.md`（作为 `template:references/host-dsh.md` 加入模板源），并在模板源的 `SKILL.md` 「Runtime references」列表里加一行指向它。
- **内容**（每条都要写明 DSH 的行为，而不是笼统建议）：
  1. **调用手势**：只认空白边界的 `/vibeloom`；`$vibeloom` 不存在；token 之后的文字原样进用户消息，无 `$ARGUMENTS` 替换 → 从原文解析 `operation` 与 `target`，按路由表加载。
  2. **审批门**：用 `ask_user_question`（blocking）；`questions[{id, question, header?, options[{label, description}], multi_select?}]`；`NO_PROVIDER` / `ASK_ABORTED` / `DELEGATED_CALLER` 一律视为**未批准**，不得继续。门必须在**根代理**执行——子代理被拒。
  3. **目标仓库与沙箱**：`workspace-write` 下只能治理 session workspace 内的仓库；外部仓库需用户先切 `danger-full-access` 或同意一次性提权；**子代理 approval 固定 `never`，永远无法提权**。遇到 `[sandbox: file access denied under workspace-write mode]` 应停下报告，不得改用 `sandbox_permissions` 硬闯。
  4. **子代理上下文**：`subagent` 是 fresh、无父会话、只返回最终文本 → 每个波次 prompt 必须自包含（把 task header + load set 路径完整写进 prompt）；**不要用 `subagent_fork`**（会继承编排者上下文，泄漏 skill 文档，违反 v03 的 load-set 纪律）。
  5. **结构化结果**：`subagent` 无 schema 参数；`result_shape_id` / `summary.yaml` 校验改由 `workflow` 的 `agent(prompt,{schema})` 承担（schema 仅支持对象根 + `type/properties/required/additionalProperties/items/enum/const/oneOf`），或要求子代理返回 fenced JSON 由编排者解析。
  6. **落盘约定**：子代理写 staging（`.vibeloom/runs/<RUN>/tasks/<TASK>/files/`），编排者校验后搬运；DSH 无原子多文件提交原语；`workspace-changes` **不记录子代理会话**，变更需从子代理结果收集。
  7. **无 per-child timeout**：deadline 自行执行。
  8. **volatile 上限**：`maxParallelToolCalls`（默认 10）、`subagent.maxDepth`（默认 1）、`maxActiveSubagents`（默认 8）是宿主设置 → 技能里不要硬编码数字，只写「按宿主并发策略」。
  9. **重生成摩擦**：`write` 拒绝覆盖未读文件、`edit` 要求先读、观察不跨 resume（`FS_NOT_OBSERVED` / `FS_STALE_VERSION`）→ reconcile / 重生成前先 read，或用引擎（bash/python）写。
- **验收**：`check-links.py` 通过；`extract-templates.py --check` 通过；新文件出现在 DSH 的 base dir 下可被读取。

### A4 — 修 subagent-prompt 的路径与 DSH 说明（P0）

- **改**：模板源中 `template:subagent-prompt.md` 的 `templates/tasks/{{template_id}}.md` → `tasks/{{template_id}}.md`。
- **加**：一段 DSH 说明——子代理无父会话，load set 必须显式给出（路径或内容）；子代理持有 write/bash，写范围靠 prompt 约束；子代理不能提问。
- **验收**：`extract-templates.py --check` 通过；[`subagent-prompt.md`](subagent-prompt.md) 中不再出现 `templates/` 前缀路径。

### A5 — 波次编排桥（P1，让 §13.3 在 DSH 上可执行）

- **新增**：`v03/dsh/wave-runner.md` —— 把 `engine dispatch` 的 plan 变成 DSH `workflow` 调用的配方：
  1. 根代理跑 `PYTHONPATH=v03/engine python3 -m vibeloom_engine --repo <target> dispatch --ids <ID> [<ID> ...] --max-wave-size N`；
  2. 用一小段脚本把 plan JSON 映射为 `workflow` 的 `args`（`args = {waves:[{wave_id, scopes:[{scope_id, kind, owned_paths, allowed_read_paths, task_template_id}]}]}`）；
  3. workflow 脚本按 wave 串行、wave 内 `parallel()` 扇出，每个 `agent()` 带 `schema`（对应 `result_shape_id`），`phase()` 报波次进度；
  4. 结果按 `scope_id` 排序后由根代理落盘/写 trace，保证 run-to-run 可复现（对齐 §13.3 的确定性顺序）。
- **可选**：给引擎加 `dispatch --format workflow` 直接输出 `args` 形状（不改语义，只加序列化格式）。**若采纳**，`dispatch.py`/`cli.py` 改动需配 `tests/test_dispatch.py` 扩展。
- **验收**：用一个 3-scope 的合成 affected set，在 DSH 里一次 `workflow` 调用完成三波并行、返回 schema 校验后的 summaries，且失败 scope 不阻塞同波其它 scope（对齐 §13.3 的 per-task atomicity）。

### A6 — 落盘与 staging 约定（P1）

- **新增**：`v03/dsh/landing.md`（或并入 A3）——staging 目录形状、编排者校验顺序（summary → 写范围 → runner → 搬运）、失败保留现场、`code-sync`/`generation` trace 的写入责任（编排者本地 append）。
- **验收**：一次失败的 scope 在 `.vibeloom/runs/.../tasks/.../` 留下可检视的产物，工作树未被污染。

### A7 — DSH 上下文产物规则（P1）

- **改**：模板源中 `template:tasks/generate-context.md` 与 `template:artifacts/context/root-config.md`（及 container/component-config）——增加宿主分支：
  - DSH：根级只生成 `AGENTS.md`；`CLAUDE.md` 可生成一行指针（内容相同会被 DSH 去重，纯重复无收益）；
  - per-container / per-component 的 `AGENTS.md` 不在 DSH baseline 链上，只在 read/write/edit 触达该目录后才加载 → 子代理必须**显式 read** 自己的 scope 配置，不能依赖自动注入；
  - 不要生成 `context/AGENTS.md` 形式（DSH 不加载）。
- **验收**：在 DSH 里生成 context 后，根 `AGENTS.md` 出现在 baseline；per-scope 文件可被子代理显式读取。

### A8 — 技能包瘦身（P2）

- **改**：[`build-bundle.sh`](build-bundle.sh) 的打包排除列表，剔除 `site/`、`adversarial-*`、`build-*`、`review-*`、`*-build-report.md`、`codæ-manifesto.html`、`vibeloom-comparison.html`、`engine/**/__pycache__`。
- **验收**：bundle 从 2.3 MB 降到 ~750 KB；`extract-templates.py --check` 与 `check-links.py` 仍通过；解包后相对链接仍全部解析。

### A9 — DSH 端到端冒烟（P0，最终验收）

在 DSH 里跑最小闭环（vibe 模式）：

```
/vibeloom init --mode vibe "a personal note-taking app with full-text search and tags"
/vibeloom approve intent-specs          # 触发 ask_user_question 审批门
/vibeloom generate code                 # 触发波次编排
/vibeloom status
```

- **通过标准**：四步都命中 v03 路由；审批门真实暂停并接受/拒绝；`generate` 至少走完一波并行子代理并写出 trace；`status` 输出 DSH 可读的一屏报告；全程无沙箱拒绝（目标仓库 == session workspace）。

---

## 3. 轨道 B 工作项（并入 v04）

| ID | 工作项 | 落点 |
|---|---|---|
| B1 | 把 DSH 适配写成 v04 的 CAP/CST | [`v04/intent.md`](../v04/intent.md)（当前 CAP-0001/CST-0001 为空） |
| B2 | host 抽象：skill 只声明 host-agnostic 语义，host adapter 文件负责工具映射 | `v04` canon + skill |
| B3 | workflow-native `execute_plan`：引擎 plan 与 workflow args 1:1 对应 | `v04` engine |
| B4 | goal-driven 长跑：多波生成用 goal rounds 续跑 | `v04` skill |
| B5 | 结构化结果契约：`result_shape_id` → JSON Schema | `v04` implementation |

**建议写入 v04 intent 的候选条目**

- CAP：「VibeLoom 在 DSH 上零配置可运行——安装后 `/vibeloom` 全操作可用，审批门与并行生成由宿主原语承载。」
- CST：「skill 面保持 host-agnostic；宿主差异只出现在 `references/host-*.md`；不得破坏 Claude Code / Codex 安装面。」
- CST：「所有 skill 面改动必须经 canonical 模板源 + `extract-templates.py --check` + `check-links.py` 门禁。」

---

## 4. 里程碑与顺序

| 里程碑 | 内容 | 出口条件 |
|---|---|---|
| **M0 可加载** | A1 + A2 | DSH 技能目录出现 `vibeloom`；`/vibeloom status` 可触发 |
| **M1 可审批** | A3 + A4 | `init` → 审批门暂停 → `approve` 闭环 |
| **M2 可并行生成** | A5 + A6 + A7 | `generate code` 走完至少一波，trace 与 staging 正确 |
| **M3 收尾与一等公民** | A8 + A9 + 轨道 B | 端到端冒烟通过；DSH 适配进入 v04 intent |

依赖：A1 是其它一切的前提；A2 与 A1 可并行；A5 依赖 A3/A4 的约定先行。

---

## 5. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 动 v03 与 `file-layout.md` 的 FROZEN 声明冲突 | 违反仓库治理 | 先决策（§6）；备选：只改模板源 + 新增 `v03/dsh/` 旁路，不碰既有 skill 面 |
| 忘记走 canonical 模板源 | `--check` 失败，CI/打包阻断 | 每个工作项都把「改模板源 → 重抽取 → `--check`」写进验收 |
| 新增 `references/*.md` 未加入模板源 | orphan 检测失败 | A3 明确要求 `template:references/host-dsh.md` 块 |
| DSH volatile 上限被硬编码 | 宿主升级后行为错 | A3 规定只写「按宿主并发策略」，不写数字 |
| 外部仓库无法治理 | 用户预期落空 | A3 写明：目标仓库必须是 session workspace，否则需 `danger-full-access` |
| 子代理无审批能力 | 子代理内需要审批的操作被静默拒绝 | 审批门一律在根代理；子代理只产出提案 |
| `write` 覆盖未读文件被拒 | reconcile/重生成失败 | A3 + A7 写明先 read；或改用引擎写 |
| DSH 版本漂移（0.2.0-rc.2） | 适配结论过期 | 报告与计划都记录被测版本；M0–M3 每次复测 frontmatter / 手势 / 沙箱三件事 |

---

## 6. 决策记录与剩余待决

已定：D1 轨道 A 走旁路（见顶部「决策记录」）；D2 编排用 `workflow` + `agent(schema)`。

仍待决：

1. **是否顺手修 `v02/SKILL.md`** 的同一 YAML 缺陷（v02 已冻结）。当前未修。
2. **是否要求支持外部仓库**（需用户切 `danger-full-access`），还是明确限定「目标仓库 == session workspace」。A3 目前按「限定 + 说明提权路径」写。
3. **`v03/dsh/` 是否进发布 bundle**（见顶部 M0 遗留；涉及链接门禁与 manifest 哈希）。
4. **A8 瘦身是否影响发布流程**（bundle 清单/哈希 manifest 会变）。

