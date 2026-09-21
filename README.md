# frontend-ui-guard

一个 Claude Skill：前端 UI 工程质量守卫。专治 AI 写前端时反复出现的工程问题——不管审美，只管"正确、一致、可验证"。

## 解决什么问题

**静态**：高度不对齐、内容挤压/撑破/重叠、下拉被裁剪、z-index 混乱、不复用全局组件（按钮/输入框/滚动条/弹窗）、硬编码颜色和随意间距、布局没章法、长文本（葡萄牙语等）撑破布局、改一处坏一处。

**动态**：点了没反应、重复提交、失败无提示、弹窗 Esc 关不掉/焦点跑到背后/背景还能滚、下拉点外面不收、仅悬停可见的操作、键盘无法操作、`transition: all`、动画布局属性导致卡顿、动画太慢、页面加载跳动、未适配减少动态效果。

## 工作方式

```
盘点项目 → 规划（布局 + 交互状态机 + 动效清单）→ 按规则编写 → 验证（静态 + 渲染 + 交互）→ 批量修根因 → 带证据汇报
```

## 目录

```
SKILL.md                         主流程（Claude 读取的入口）
references/
  layout.md                      布局与尺寸
  layering.md                    层叠、裁剪、z-index、浮层
  design-system.md               组件复用、令牌、排版章法
  states-a11y.md                 元素状态与可访问性
  interaction.md                 交互设计：状态机、防重复、竞态、浮层行为、键盘/触屏
  motion.md                      动效：时长缓动、只动 transform/opacity、CLS、reduced motion
  change-safety.md               改动范围与防回归
  i18n-text.md                   长文本、多语言、货币格式
scripts/
  scan_project.py                盘点组件、令牌、全局类、漂移统计
  ui_lint.py                     静态检查（约 40 条规则）
  layout_check.cjs               Playwright 多宽度渲染检查 + 红框标注截图
  interaction_check.cjs          Playwright 交互/动效检查 + 弹窗/提交探测
assets/
  ui-guard.config.example.json   项目配置模板
  ui-guard.actions.example.json  交互脚本模板（状态、浮层、提交探测）
  ui-rules.template.md           项目 UI 规则模板
```

## 安装

- **Claude.ai**：下载 Release 中的 `frontend-ui-guard.skill`（或把本仓库打包为 zip），在 设置 → Capabilities → Skills 上传。
- **Claude Code**：把本仓库放到 `~/.claude/skills/frontend-ui-guard/`（个人）或项目的 `.claude/skills/frontend-ui-guard/`。

## 在项目中接入

1. 复制 `assets/ui-guard.config.example.json` 到项目根目录为 `ui-guard.config.json`，填写组件目录、组件映射、滚动条类、开发地址。
2. 复制 `assets/ui-rules.template.md` 为项目的 `ui-rules.md`，填写必须使用的组件和禁止事项。
3. 复制 `assets/ui-guard.actions.example.json` 为 `ui-guard.actions.json`，登记关键弹窗和提交按钮。
4. 安装 Playwright：`npm i -D playwright && npx playwright install chromium`

## 脚本单独使用

```bash
python3 scripts/scan_project.py --root . --out .ui-guard/inventory.md
python3 scripts/ui_lint.py --root . --changed
node scripts/layout_check.cjs --url http://localhost:5173/orders --stress
node scripts/interaction_check.cjs --url http://localhost:5173/orders --actions ui-guard.actions.json --mobile
```

报告和截图输出在 `.ui-guard/` 下，建议加入 `.gitignore`。

- `ui_lint.py` 只依赖 Python 3 标准库。
- 两个 `.cjs` 脚本依赖 Playwright；全局安装时先 `export NODE_PATH=$(npm root -g)`。
- 提交探测会拦截指定接口返回模拟结果，不会写入真实后端。
- 退出码：存在 error 时为 1，可接入 CI。
