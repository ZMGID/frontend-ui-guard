# 布局与尺寸规则

对应问题：高度不对齐、内容挤得大大小小、撑破容器、横向滚动条、截断不生效、元素重叠、断点处崩坏。

## 目录
1. 布局选型
2. flex 的五个坑
3. 等高与对齐
4. 文本：换行还是截断
5. 高度与滚动链
6. 定位
7. 响应式
8. 修复配方（症状 → 根因 → 改法）

---

## 1. 布局选型

- **二维（行和列都要对齐）用 grid**：卡片墙、表单两列、仪表盘指标块。`grid-template-columns: repeat(auto-fill, minmax(240px, 1fr))` 可以在不写断点的情况下自适应。
- **一维（一行或一列排东西）用 flex**：工具栏、按钮组、列表项内部、卡片内部纵向结构。
- **页面骨架用 grid**：`grid-template-columns: 240px minmax(0, 1fr)`（侧栏 + 主区）。注意主区列用 `minmax(0, 1fr)` 而不是 `1fr`，`1fr` 的最小值是内容宽度，会被宽表格撑破。
- 不要用 margin 做兄弟元素间距，用父级的 `gap`。margin 叠加、首尾多余、条件渲染时留空位都会导致"间距大大小小"。

## 2. flex 的五个坑

1. **`min-width: auto`**：flex 子项默认不会缩到比内容更窄。任何包含文本、输入框、表格、代码块、图片的 flex 子项，如果它需要收缩，必须 `min-width: 0`（纵向 flex 对应 `min-height: 0`）。这是"撑破容器 / 截断无效 / 整页横向滚动"的头号原因，而且要沿着祖先链逐级检查——中间任何一层缺了都没用。
2. **固定块被压缩**：图标、头像、徽标、固定宽度侧栏在空间不足时会被压扁。给它们 `flex-shrink: 0`。
3. **`flex: 1` 不等于等分**：`flex: 1` 是 `1 1 0%`，内容仍可能让某项更宽（因为坑 1）。要真正等分用 grid `repeat(n, minmax(0, 1fr))`。
4. **固定 flex-basis 在窄屏溢出**：`flex: 1 1 260px` 在 320px 屏幕上会溢出。用 `flex: 1 1 min(260px, 100%)` 或允许 `flex-wrap: wrap`。
5. **`align-items` 默认是 stretch**：同一行里按钮和输入框被拉成不同高度或被拉伸变形时，行容器用 `align-items: center`，控件高度由组件 size 决定。

## 3. 等高与对齐

- **同行卡片等高**：grid 默认就让同一行等高（`align-items: stretch`）。卡片自身不要写死 height。卡片内部 `display:flex; flex-direction:column;`，把底部操作区 `margin-top:auto` 推到底，这样按钮一排对齐。
- **同行控件等高**：同一工具栏中的 Button、Input、Select 用同一个 size 档位（例如都用 `size="md"`）。不要手写 `height: 38px` 这种值。
- **表格列对齐**：数字列右对齐 + `font-variant-numeric: tabular-nums`；操作列固定宽度；长文本列设 `max-width` + 截断。
- **图文对齐**：图标和文字在同一行用 `inline-flex; align-items:center; gap`，不要靠 `vertical-align` 或 `margin-top: 2px` 微调。
- **基线对齐**：标题和"查看更多"之类不同字号同行时用 `align-items: baseline`。

## 4. 文本：换行还是截断

每个显示动态文本的位置都要做出明确决定：

| 场景 | 做法 |
|---|---|
| 标题、名称（单行） | `overflow:hidden; text-overflow:ellipsis; white-space:nowrap;` + 祖先链 `min-width:0` + `title` 属性或 Tooltip 显示全文 |
| 描述（有限行数） | `-webkit-line-clamp: 2~3`（Tailwind `line-clamp-2`） |
| 长串无空格内容（URL、SKU、邮箱） | `overflow-wrap: anywhere` |
| 按钮文字 | 默认不换行；空间不够时允许按钮组 `flex-wrap`，而不是让文字溢出按钮 |
| 标签/Tab | `white-space: nowrap` + 容器可横向滚动或折叠为"更多" |

不要给文本容器写死高度（`h-12` 装两行文字），字体、语言一变就溢出或被切。

## 5. 高度与滚动链

- 全屏应用骨架：`html, body, #root { height: 100% }`，骨架用 grid/flex 纵向，主区 `min-height: 0; overflow: auto`。不用 `100vh`（移动端地址栏会导致多出一截），必要时用 `100dvh`。
- **一个区域只有一个滚动者**。常见错误是页面和内部面板同时滚动、出现双滚动条。先决定谁滚动，其余层 `overflow: hidden` 或不设。
- 纵向 flex 中想让某个子项滚动：该子项 `flex:1; min-height:0; overflow:auto`。缺 `min-height:0` 就不会出现滚动条，而是把父级撑高。
- 滚动容器使用项目的全局滚动条样式类（见盘点清单），不要让它显示浏览器原生滚动条，也不要每个组件自己写 `::-webkit-scrollbar`。
- 弹窗内容过长：弹窗 `max-height: calc(100dvh - 2*边距)`，头部和底部操作区固定，中间 body 滚动。

## 6. 定位

- `position: absolute` 只用于：角标/徽标、浮层（且应该用组件库或 portal）、装饰元素、覆盖在图片上的操作按钮。用之前确认父级 `position: relative`，并确认它不会盖住兄弟内容。
- 不用 absolute + 固定 top/left 来摆放常规内容，内容长度一变就重叠。
- `position: sticky` 需要：设置 `top`；祖先中没有 `overflow: hidden/auto`（除非那个祖先就是滚动容器）；父级比 sticky 元素高。横向防溢出用 `overflow-x: clip` 而不是 `hidden`，前者不破坏 sticky。
- `position: fixed` 的元素在带 `transform` / `filter` 的祖先内会相对该祖先定位，而不是视口。

## 7. 响应式

- 至少在这些宽度检查：360（小手机）、768（平板竖屏）、834（iPad）、1280（笔记本）、1440+。脚本 `layout_check.cjs` 默认覆盖。
- 优先用不依赖断点的写法：`auto-fill + minmax`、`flex-wrap`、`clamp()` 用于大标题（密集的后台界面不要用流式字号）。
- 移动端输入框字号不小于 16px，否则 iOS Safari 聚焦时会放大页面。
- 触控目标不小于 40×40px（至少 32px）。
- 后台管理类页面也要保证在 1280 宽度下侧栏 + 表格不产生页面级横向滚动；宽表格自己在容器内横向滚动。

## 8. 修复配方

| 症状 | 最常见根因 | 改法 |
|---|---|---|
| 整页出现横向滚动条 | 某个 flex 子项缺 `min-width:0`；或固定宽度元素 > 视口；或 `100vw` 算上了滚动条宽度 | 用 layout_check 找出越界元素，沿祖先链补 `min-width:0`；固定宽度改 `max-width:100%`；`100vw` 改 `100%` |
| 截断省略号不出现 | 祖先 flex 子项缺 `min-width:0`；或元素没有确定宽度 | 补 `min-width:0`（整条链）；元素本身 `display:block` 或 `min-w-0 flex-1` |
| 同行卡片高低不齐、按钮不在一条线 | 卡片写死了高度或用了 `items-start`；卡片内部没有把操作区推到底 | 容器 grid/flex stretch；卡片 flex-col + 操作区 `mt-auto` |
| 同行按钮和输入框高度不同 | 各自手写高度/padding，或混用不同 size | 统一用组件 size 档位，删手写高度 |
| 内容大大小小、间距不一 | margin 与 gap 混用；任意值；条件元素留空位 | 统一用父级 gap + 刻度值；条件元素不占位 |
| 元素叠在一起 | absolute 布局；负 margin；固定高度容器内容溢出 | 改为文档流布局；去掉负 margin；去掉固定高度或定义溢出策略 |
| 窄屏某行溢出 | `nowrap` 文本 + 无收缩；固定 flex-basis | 允许截断或换行；`flex-wrap`；`min(Xpx, 100%)` |
| 滚动条不出现，内容被撑高 | 纵向 flex 子项缺 `min-height:0` | 补 `min-height:0; overflow:auto` |
| 出现双滚动条 | 多个祖先都设了 overflow:auto | 只保留一个滚动者 |
| sticky 不生效 | 祖先有 overflow:hidden | 改为 `overflow: clip` 或移除；确认 top 值 |
