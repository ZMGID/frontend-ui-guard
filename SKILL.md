---
name: frontend-ui-guard
description: 前端 UI 工程质量守卫——专治 AI 写前端的通病。静态：高度不对齐、内容挤压/撑破/重叠、下拉和弹窗被裁剪或遮挡、z-index 混乱、不复用全局组件（按钮/输入框/滚动条/弹窗重写或用原生标签）、硬编码颜色和随意间距、布局没章法、长文本（如葡萄牙语）撑破布局。动态：点了没反应、重复提交、失败无提示、弹窗 Esc 关不掉/焦点跑到背后/背景还能滚、下拉点外面不收、悬停才出现的操作、键盘无法操作、动画卡顿/太慢/乱飞、transition all、页面加载跳动、没适配减少动态效果、改一处坏一处。只要任务涉及编写、修改、重构或排查任何前端界面或交互（页面、组件、弹窗、表格、表单、按钮、动画、过渡、布局、样式、CSS/Tailwind、React/Vue/Svelte/HTML），都必须使用本 skill，即使用户只说"加个按钮""调一下样式""加个动画""做个弹窗""这里对不齐""做个页面"。它不负责审美风格，只负责让界面在工程上正确、一致、可验证。
---

# Frontend UI Guard

这个 skill 的核心判断：AI 写前端出 bug，主要不是"不会写 CSS"，而是三件事——
1. **看不见**：模型处理的是代码不是像素，写完不渲染就交付，布局问题全靠用户肉眼发现。
2. **不知道有什么**：不清楚项目里已有哪些组件、令牌、全局类，于是用原生标签或重写一个；而且模型会照抄离得最近的代码，而不是遵守规则文件。
3. **修补式改动**：哪里不对就补一个 `!important`、一个魔法数字、一个 z-index，越修越乱，改一处坏一处。

另外，界面不只是静态的一帧：AI 通常只写 happy path，点击后没有 pending、失败没有处理、弹窗没有键盘行为、动画随手 `transition: all 0.5s`。所以动态行为（交互和动效）和静态布局一样要规划、有规则、被验证。

所以本 skill 的流程是：**先盘点 → 再规划（布局 + 交互 + 动效）→ 按规则写 → 用脚本和截图验证（静态 + 动态）→ 批量修根因**。不要跳过验证阶段，它是整个 skill 最有价值的部分。

## 目录

- `scripts/scan_project.py` —— 盘点项目的组件、设计令牌、全局类、z-index 使用情况
- `scripts/ui_lint.py` —— 静态检查（原生标签、硬编码颜色、魔法数字、!important、Tailwind 冲突类、100vh、缺 min-w-0 等）
- `scripts/layout_check.cjs` —— 用 Playwright 真实渲染，多个宽度下检测横向溢出、裁剪、重叠、同行高度不齐、文字被截、滚动条未统一、间距不在刻度上等，并输出带红框标注的截图
- `scripts/interaction_check.cjs` —— 动态检查：悬停反馈、键盘可达与焦点环、焦点被遮挡、仅悬停可见的操作、嵌套交互、布局位移（CLS）、正在运行的动画/过渡（transition all、动画布局属性、时长）、reduced motion；并可探测弹窗（焦点陷阱/Esc/滚动锁定/焦点归还）和提交流程（即时反馈/重复提交/失败提示，接口被拦截模拟，不写真实后端）
- `references/layout.md` —— 布局与尺寸规则（flex/grid、对齐、溢出、截断、高度）
- `references/layering.md` —— 层叠、裁剪、z-index、弹层 portal
- `references/design-system.md` —— 组件复用协议、令牌、间距刻度、字号层级
- `references/states-a11y.md` —— 交互状态、加载/空/错误态、可访问性
- `references/change-safety.md` —— 改动范围控制、防回归、禁止的修补手法
- `references/i18n-text.md` —— 长文本、多语言（葡语等）、数字货币格式
- `references/interaction.md` —— 交互设计：动作状态机、反馈、防重复/竞态/乐观更新、浮层行为、表单、点击目标、悬停/触屏/键盘、URL 状态、危险操作
- `references/motion.md` —— 动效：该不该动、时长缓动令牌、只动 transform/opacity、原点、进入退出、可打断、CLS、加载动效、reduced motion
- `assets/ui-guard.config.example.json` —— 项目配置模板
- `assets/ui-guard.actions.example.json` —— 交互脚本模板（状态、浮层探测、提交探测）
- `assets/ui-rules.template.md` —— 项目 UI 规则模板（组件清单 + 禁止事项）

按需读取 references，不要一次全读：做布局读 layout.md，做弹窗/下拉/浮层读 layering.md + interaction.md §4，有按钮提交/请求读 interaction.md §1–3，加任何动画/过渡读 motion.md，新增组件或页面读 design-system.md，以此类推。

---

## 第 0 步：项目盘点（每个会话首次涉及前端时做一次）

1. 查找项目根目录下的 `ui-rules.md`（或 `docs/ui-rules.md`、`.ui-guard/ui-rules.md`）和 `ui-guard.config.json`。**存在就先读**，里面的组件清单和禁止事项优先级最高。
2. 运行盘点脚本，得到组件、令牌、全局类的清单：
   ```bash
   python3 <skill_dir>/scripts/scan_project.py --root . --out .ui-guard/inventory.md
   ```
   然后读 `.ui-guard/inventory.md`。重点看：按钮/输入/选择/弹窗/表格/滚动条对应哪个组件或类，颜色和间距用哪些令牌，已有的 z-index 分层。
3. 如果项目没有 `ui-rules.md` 和 `ui-guard.config.json`，在完成当前任务后**建议**用户基于 `assets/` 里的模板建立（可以根据盘点结果帮他预填）。不要未经同意就往项目里写这两个文件。

盘点的意义：你接下来写的每一个按钮、输入框、滚动区域、颜色、间距，都应该能在清单里找到出处。找不到的，先问自己"项目里真的没有吗"，再 grep 一次。

## 第 1 步：动手前的规划（写代码前，用几行文字说清楚）

在写任何布局代码之前，先在回复或思考里写出一个简短的布局说明，至少回答这几个问题：

- **结构**：页面/组件分哪几块，每块用 flex 还是 grid，方向是什么。例如"顶部筛选栏（flex 行，左筛选右操作）+ 下方 grid 三列卡片，gap 用 --space-4"。
- **尺寸归属**：每一块谁定宽、谁弹性、谁可收缩。固定宽度的块写死宽度并 `shrink-0`；弹性块 `flex-1 min-w-0`。
- **滚动归属**：整个页面只能有一个明确的滚动容器链。说清楚"哪个元素滚动"，其余祖先要么不滚动、要么高度受约束。
- **复用清单**：这次要用到的现成组件（Button、Input、Modal、Table、Scrollbar 类……）逐一列出；需要新建的组件说明为什么现有的不行。
- **内容压力**：最长的文本是什么（葡语、商品标题、店铺名）？列表为空时显示什么？数据很多时怎么办？加载中和出错时显示什么？
- **交互状态机**：每个会发请求或耗时的操作，写出 idle → pending → success / error 各自界面如何变化；pending 时能否再次触发（不能）；失败后如何重试。浮层（弹窗/抽屉/下拉）写出打开方式、关闭方式（Esc、遮罩、选择后）、焦点去向。
- **动效清单**：这次要加的每一个动画说明"为什么动"（说明因果/点缀）、属性（只允许 transform/opacity）、时长和缓动令牌、退出方式、reduced motion 下的表现。说不出理由的动画不加。

这一步的价值在于把布局、交互、动效决策前置，避免"先写再调"。如果需求本身模糊（比如不知道要几列、要不要移动端、删除要不要确认），在这一步问用户，而不是写完再返工。

## 第 2 步：按规则编写

最核心的硬规则（完整规则和修复配方见 references）：

**布局**
- flex 行里任何包含文本或动态内容的子项加 `min-width: 0`（Tailwind `min-w-0`），否则会撑破父容器、截断失效。
- 同一行的卡片用 grid（或 flex + `items-stretch`），卡片内部用 flex 纵向 + 把底部操作区推到底（`mt-auto`），让同行卡片等高、按钮对齐。
- 同一行的控件（按钮、输入框、下拉）使用同一个尺寸档位，高度来自组件的 size，不手写 height。
- 不用 `position: absolute` 做常规排版。absolute 只用于角标、浮层、装饰，并且父级必须 `position: relative`。
- 不用 `100vh`；全屏布局用 `height: 100%` 链或 `100dvh`。
- 可能为空的条件元素不要占网格位置/间距；用 flex + gap 让间距随元素消失。
- 文本要么明确允许换行（`break-words`），要么明确截断（单行 `truncate` / 多行 `line-clamp`，并带 title 或 tooltip 显示全文）。不要留给默认行为。

**层叠**
- z-index 只能用项目定义的层级令牌（例如 dropdown < sticky < overlay < modal < toast），不写 9999 之类的数字。
- 下拉、Popover、Tooltip、Modal 必须用组件库自带的或 portal 渲染到 body，不要放在可能 `overflow: hidden` 的容器里裸写 absolute。
- 给容器加 `overflow: hidden`、`transform`、`filter`、`backdrop-filter`、`opacity<1` 前想清楚：它会裁剪子级浮层或创建新的层叠上下文。

**设计系统**
- 按钮、输入框、选择器、弹窗、表格、标签、滚动区域：一律用盘点清单里的组件/类。不用原生 `<button>` `<input>` 直接堆样式，不再写一个新的 XxxButton。
- 颜色只用令牌（CSS 变量或 Tailwind 主题色），不写 hex/rgb。
- 间距、圆角、字号只用刻度里的值，不写 `p-[13px]` 这种任意值。
- 需要新变体时，给现有组件加 variant，而不是复制一个新组件；不要不停加布尔 prop。
- 参照项目中**被标记为规范的**示例写法，而不是离你最近的那个文件（它可能是旧代码）。`legacy`、`deprecated`、`old` 目录里的东西不要引用。

**状态**
- 每个交互元素要有 hover / focus-visible / disabled；异步操作要有 loading；列表要有空状态；请求要有错误态。
- 表单字段要有可见 label，不能只靠 placeholder。

**交互**（完整规则见 interaction.md）
- 异步操作：点击立即进入 pending（按钮禁用 + loading，保留文字和宽度）；try/catch/finally——失败显示原因且可重试，finally 恢复按钮。
- 连续请求（搜索、筛选、分页）取消旧请求或丢弃过期响应；优先使用项目的数据层，不在组件里裸写 useEffect + fetch。
- 弹窗、抽屉、下拉一律用项目组件；自写的必须具备：role/aria-modal、焦点移入与陷阱、Esc 关闭、背景滚动锁定、关闭后焦点归还、下拉点外部关闭。
- 导航用 `<a href>`，操作用 Button；不用 `div onClick`；不嵌套可交互元素。
- 悬停才出现的操作同时在 focus-within 时出现，移动端常显或收进菜单。
- 删除等危险操作用 ConfirmDialog 二次确认或提供撤销；不用 `window.confirm/alert`。
- 筛选、分页、Tab 等状态同步到 URL。

**动效**（完整规则见 motion.md）
- 只在说明因果或刻意点缀时加动画；高频操作不加。
- 只动 `transform` 和 `opacity`；禁止 `transition: all` / `transition-all`；不动画 width/height/top/left/margin/padding。
- 时长和缓动用令牌：hover 150ms、下拉 200ms、弹窗 ≤ 300ms；进入 ease-out，退出更快；不用 ease-in 做进入，不用回弹曲线。
- 下拉/Popover 从触发器方向展开，从 scale(0.95) 而不是 scale(0) 开始；有进入就要有退出动画。
- 可能被连续触发的用 transition 而不是 keyframes。
- 骨架屏尺寸与最终内容一致，图片设尺寸，异步内容不从上方插入推挤页面。
- 全项目必须有 `prefers-reduced-motion` 适配。

## 第 3 步：验证（不能跳过）

写完或改完后，按顺序做：

### 3.1 静态检查
```bash
python3 <skill_dir>/scripts/ui_lint.py --root . --changed      # 只查 git 改动的文件
python3 <skill_dir>/scripts/ui_lint.py --root . src/pages/Foo.tsx  # 或指定文件
```
`error` 必须修；`warn` 逐条判断，确认合理的在汇报里说明原因。

### 3.2 渲染检查（只要能跑起来就必须做）
确认开发服务器地址（问用户或看 package.json 脚本），然后：
```bash
node <skill_dir>/scripts/layout_check.cjs --url http://localhost:5173/your-page --out .ui-guard/report
# 加 --stress 用 1.6 倍长度文本做压力测试（多语言场景强烈建议）
# 加 --widths 360,768,1280 自定义宽度；--selector "#app" 限定检查范围
# 需要登录/交互才能看到的状态：--actions actions.json（见脚本头部说明）
```
脚本依赖 Playwright（项目里 `npm i -D playwright && npx playwright install chromium`；若是全局安装，运行前 `export NODE_PATH=$(npm root -g)`）。退出码 1 表示存在 error 或有状态运行失败。没有 node 环境时说明原因并跳过，但要在汇报里明确告诉用户"未做渲染验证"。

然后：
1. 读 `.ui-guard/report/report.md`。
2. **用图片查看工具打开** `annotated-*.png`（问题元素被红框标出）和各宽度的截图，亲眼确认。脚本能发现结构性问题，但"看起来怪不怪"需要你看图判断。
3. 对需要打开才能看到的状态（下拉展开、弹窗打开、空列表、加载中），用 `--actions` 触发后再检查，或至少截图查看。

### 3.3 交互与动效检查（改动涉及按钮、表单、弹窗、下拉、动画、过渡、加载时必须做）
```bash
node <skill_dir>/scripts/interaction_check.cjs --url http://localhost:5173/your-page --actions ui-guard.actions.json --out .ui-guard/interaction
# --mobile 额外检查 390px 触屏；--skip-hover / --skip-tab 可跳过耗时部分
```
- 不带 `--actions` 时只做安全的自动检查（悬停、Tab、读取动画和布局位移），不会点击任何东西。
- 弹窗和提交流程要在 actions 文件的 `overlays` / `submits` 中登记后才会被探测（模板见 `assets/ui-guard.actions.example.json`）。提交探测会拦截指定接口返回模拟结果，不写入真实后端；仍需确认 api 模式只匹配要测的接口。**本次新增或修改的弹窗和提交按钮，都要登记进去再跑。**
- 读 `.ui-guard/interaction/report.md`，查看 `interaction-*.png`（标注图）、`overlay-*.png`、`submit-*-pending.png` / `submit-*-error.png`，确认加载态和错误态的样子是否合理。
- 动效"顺不顺"脚本只能测出时长、属性、缓动；手感问题对照 motion.md 自查，必要时描述给用户让其确认。

### 3.4 批量修复
- 先把所有问题列出来，按根因归并（很多症状来自同一个原因，例如一个没加 `min-w-0` 的元素导致整页横向滚动）。
- 一次性修根因，不要一条一条打补丁。修复手法见 references 各文件的"修复配方"。
- 禁止用 `!important`、提高选择器权重、负 margin、魔法数字、随手加 z-index 来"压住"问题。
- 修完重新跑 3.1、3.2（以及涉及交互时的 3.3），直到 error 清零。最多循环 3 轮；3 轮后仍有问题，停下来向用户说明卡在哪里。

## 第 4 步：汇报

汇报里给出证据，而不是只说"已修复"：
- 复用了哪些现有组件，新建了什么（以及为什么）。
- lint、渲染检查、交互检查的结果（修复前 → 修复后的问题数量）。
- 检查过的宽度、状态、浮层和提交探测；哪些没法自动验证、需要用户人工看一眼（例如动画手感、真实接口下的表现）。
- 如果改动了共享的样式/组件/令牌，列出可能受影响的其他页面。

## 改已有代码时的额外约束

读 `references/change-safety.md`。要点：只改与任务相关的元素；不修改全局样式、共享组件、主题令牌，除非任务就是改它们（改了要说明影响面）；改之前先对相关页面跑一次 layout_check 作为基线，改完对比。

## 何时降级

- 纯静态 HTML 原型：盘点可以跳过，但渲染检查照做（`--url file:///绝对路径.html`）。
- 用户只是问 CSS 知识，没有要改代码：直接回答，引用 references 里的相关规则即可。
- 环境里没有浏览器/Playwright：做静态检查 + 仔细按规则自查，并在汇报中明确声明未做渲染验证。

## 问题 → 负责环节 对照

| 问题 | 规划 | 规则 | 静态检查 | 渲染检查 |
|---|---|---|---|---|
| 横向溢出、挤压、撑破（缺 min-width:0） | 尺寸归属 | layout.md | flex-grow-no-minw | page-overflow, text-spill |
| 同行高度/按钮不对齐 | 结构 | layout.md §3 | tw-conflict | control-height, card-height, card-actions |
| 元素重叠 | 结构 | layout.md §6 | negative-margin | text-overlap |
| 截断失效 / 文字被切 | 内容压力 | layout.md §4 | truncate-check | text-cut, truncated-no-title |
| 下拉被裁、弹窗被盖、z-index 混乱 | — | layering.md | z-index, overflow-hidden | clipped-overlay, z-index |
| 全局组件没用上 / 又写一个 | 复用清单 | design-system.md | raw-primitive, legacy-import | — |
| 原生滚动条、双滚动条 | 滚动归属 | layout.md §5 | native-scroll | native-scroll, double-scroll |
| 硬编码颜色、间距乱、字号乱 | — | design-system.md §3 | hardcoded-color, arbitrary-value, off-scale-spacing | spacing-off-scale, font-sizes |
| 缺 hover/focus/加载/空/错误态 | 内容压力 | states-a11y.md | outline-none, placeholder-label, img-alt | 用 --actions 触发各状态截图查看 |
| 改一处坏一处、!important 堆叠 | — | change-safety.md | important, tw-conflict, inline-style | 改前改后两次报告对比 |
| 葡语等长文本撑破 | 内容压力 | i18n-text.md | — | --stress |
| 100vh、移动端问题 | — | layout.md §5/§7 | viewport-unit | offscreen-fixed, touch-target, ios-input-zoom |
| 图片变形/加载失败 | — | — | img-alt | img-distorted, img-broken |
| 点了没反应、重复提交 | 交互状态机 | interaction.md §1–3 | async-no-pending | 提交探测：no-pending-feedback, double-submit |
| 失败无提示、按钮卡死 | 交互状态机 | interaction.md §2 | async-no-pending | 提交探测：no-error-feedback, stuck-disabled, unhandled-error |
| 搜索结果乱序、勾选闪回 | 交互状态机 | interaction.md §3 | fetch-race, url-state | —（人工按规则检查） |
| 弹窗关不掉、焦点跑到背后、背景滚动 | 浮层行为 | interaction.md §4 | native-dialog | 浮层探测：focus-trap, esc-close, scroll-lock, focus-restore, dialog-semantics |
| 下拉点外面不收 | 浮层行为 | interaction.md §4 | — | 浮层探测：outside-close, esc-close |
| 悬停无反馈、手型不对 | — | states-a11y.md | — | no-hover-feedback, cursor |
| 键盘不可用、焦点看不见 | — | interaction.md §7 | clickable-div, positive-tabindex, outline-none | no-focus-ring, pointer-only, focus-stuck, focus-obscured, focus-invisible |
| 仅悬停出现的操作 | — | interaction.md §7 | hover-only | hover-only-action（含 --mobile） |
| 嵌套按钮/链接 | — | interaction.md §6 | bad-href | nested-interactive, unnamed-control |
| 动画卡顿 | 动效清单 | motion.md §3 | transition-all, animate-layout | transition-all, animate-layout, long-frame |
| 动画太慢、缓动不对、scale(0) | 动效清单 | motion.md §4–5 | motion-duration, motion-easing, scale-zero | motion-duration, motion-easing |
| 加载完成页面跳动 | 内容压力 | motion.md §8 | — | layout-shift |
| 没适配减少动态效果 | 动效清单 | motion.md §10 | reduced-motion | reduced-motion |
