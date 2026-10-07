# 验收计划 — v03 在 DSH 上可运行

Goal: **v03 能在 DeepSeek Harness 上被发现、加载并执行。**
非目标: 方法学语义正确性、v04、发布 bundle、site 内容。

验收环境: DSH `@deepseek-ai/dsh` 0.2.0-rc.2 · profile `web` · file policy `workspace-write` · approval `ask`
验收时点: 2026-10-07
被测对象: `/home/asuka/Dev/vibeloom/v03`（经符号链接安装为 `$DSH_HOME/skills/vibeloom`）

判据等级: **PASS** = 观察到预期结果 · **FAIL** = 观察到反例 · **PENDING-USER** = 必须由人在 GUI 里操作才能完成

---

## 判据

### AC1 — 发现（discovery）
- 判据: `vibeloom` 出现在 DSH 会话技能目录中，且描述为 v03 文案。
- 执行: 检查 `$DSH_HOME/skills/vibeloom/SKILL.md` 存在且 frontmatter 合法；对照会话目录条目。
- 关联阻断: 原 `SKILL.md` frontmatter 非法 YAML（已修）。

### AC2 — 加载（load）
- 判据: `skill` 工具以 `name: vibeloom` 调用成功，返回 `<skill_content name="vibeloom">`，含资源基址指引，且正文包含本次新增的 `references/host-dsh.md` 指针。
- 执行: 直接调用 `skill` 工具。
- 关联阻断: DSH 解析失败会静默丢弃整条技能。

### AC3 — 资源解析（resource base）
- 判据: SKILL.md 中所有相对链接在返回的 base dir 下解析为真实文件。
- 执行: 取 base dir，逐一验证 `references/*.md`、`tasks/*.md`、`subagent-prompt.md`、`engine/`、`vibeloom-methodology.md`、`vibeloom-implementation.md`。
- 关联阻断: v03 load-on-demand 依赖这些路径。

### AC4 — 手势（gesture）
- 判据: `/vibeloom` 是合法的用户手势 token；技能未被 `user-invocable: false` 关闭；正文注入路径与工具加载共用同一渲染器。
- 执行: 用 DSH 源码中的手势正则对 `/vibeloom status` 等真实输入做静态匹配；核对 invocation policy 默认值。

### AC5 — 引擎可执行（engine）
- 判据: 在 session workspace 内，`python3 -m vibeloom_engine` 可执行并输出 JSON。
- 执行: `--version`；对 workspace 内的合成契约仓库跑 `parse` 与 `dispatch --ids`。

### AC6 — 沙箱边界（sandbox）
- 判据: workspace 内可写；workspace 外写入被拒绝（拒绝是策略行为，不是缺陷）。
- 执行: workspace 内创建/删除探针文件；尝试写 `/home/asuka/Dev/` 下的路径。

### AC7 — 仓库门禁（gates）
- 判据: `extract-templates.py --check`、`check-links.py`、`check-skill-frontmatter.py` 全部通过。
- 执行: 三条命令 + 退出码。

### AC8 — 安装（install）
- 判据: 符号链接安装就位并指向仓库 v03；安装脚本幂等、可 dry-run、可安全卸载。
- 执行: `ls -l`/`readlink -f`；在临时 `DSH_HOME` 下跑 dry-run / install / 重复 install / uninstall。

### AC9 — 宿主适配可读（host adapter）
- 判据: `references/host-dsh.md` 存在、被 SKILL.md 引用、且其自身链接可解析。
- 执行: 文件存在性 + SKILL.md 指针 + `check-links.py`。

### AC10 — 实机手势（live gesture，人工）
- 判据: 在 GUI 输入框键入 `/vibeloom status`，技能正文被注入该轮，模型可据此执行操作。
- 执行: 由用户在 GUI 中操作；这是唯一无法由代理代劳的一步（手势监听器只扫描真实用户消息）。

---

## 通过标准

AC1–AC9 全部 PASS，且 AC10 经用户确认后，判定 **v03 在 DSH 上可运行**。
任一 FAIL → 记录证据、修复、重跑该条与其下游。

---

## 执行结果

| AC | 结果 | 证据 |
|---|---|---|
| AC1 发现 | **PASS** | `~/.dsh/skills/vibeloom -> /home/asuka/Dev/vibeloom/v03`（符号链接）；frontmatter 合法；会话技能目录含 `vibeloom` |
| AC2 加载 | **PASS** | `skill(name=vibeloom)` 返回 `<skill_content name="vibeloom">`，`Base directory for this skill: /home/asuka/.dsh/skills/vibeloom`；正文含 `references/host-dsh.md` 指针与修正后的引擎调用 |
| AC3 资源解析 | **PASS** | SKILL.md 13 条相对链接零悬空；`references/host-dsh.md`、`references/runtime.md`、`tasks/generate-code-component.md`、`subagent-prompt.md`、`vibeloom-methodology.md`、`vibeloom-implementation.md`、`engine/vibeloom_engine/__main__.py`、`artifacts/context/root-config.md` 全部存在 |
| AC4 手势 | **PASS** | DSH 手势正则 `/(^|\s)\/([a-z0-9]+(?:-[a-z0-9]+)*)(?=\s\|$)/` 对 9 个用例全部符合预期（`/vibeloom status`、`/vibeloom init --mode vibe "..."`、`please run /vibeloom generate code`、`/vibeloom` 命中；`/vibeloom,`、`/vibeloom.md`、`5/8`、`/usr/bin`、`/vibeloomX` 不命中）；frontmatter 无 `user-invocable: false` / `disable-model-invocation`，双面可达 |
| AC5 引擎 | **PASS** | 经已安装路径：`vibeloom-engine 0.3.0`；`parse` → 4 artifacts / `CAP-0001, FR-0001, EXT-0001`；`dispatch --ids CAP-0001` → affected 3 项、**2 waves**（`W2 deps [W1]`）；bridge 输出合法 workflow args（repo/skill_root/waves/scopes）；`status` 正常 JSON |
| AC6 沙箱 | **PASS** | workspace 内创建/删除探针成功；`touch /home/asuka/Dev/.dsh_acc_probe` → `只读文件系统`（exit 1） |
| AC7 门禁 | **PASS** | `extract-templates.py --check`（42 templates）· `check-links.py` · `check-skill-frontmatter.py` 退出码全 0 |
| AC8 安装 | **PASS** | 临时 `DSH_HOME` 下 dry-run / install / 重复 install（`already installed`）/ uninstall（`removed symlink`）全部符合预期 |
| AC9 宿主适配 | **PASS** | `v03/references/host-dsh.md`（6856 B）存在；SKILL.md 第 31 行引用；`check-links.py` 通过 |
| AC10 实机手势 | **PASS** | 用户在 GUI 输入框键入 `/vibeloom status`，技能正文被注入该轮（2026-10-07 用户确认） |

### 结论

**AC1–AC10 全部 PASS。** v03 已可在 DSH 上被发现、加载、解析资源、经手势注入并执行引擎。**判定：v03 在 DSH 上可运行。**

### 执行备注

- AC2 返回的 base dir 是符号链接路径（`/home/asuka/.dsh/skills/vibeloom`），DSH 按「保留发现路径」处理；相对路径经符号链接解析正常（AC3 已验证）。
- AC5 的第一次夹具缺 `## Functional requirements` 小节标题，引擎按**结构**解析、未识别表格项 → 补标题后正常。这是夹具问题，不是引擎缺陷；同时也验证了引擎确实做结构化解析。
- 验收夹具（`.vl-acc/`）已清理，无残留；清理后重跑三条门禁仍全绿。

