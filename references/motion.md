# 动效规则

对应问题：动画卡顿、到处都在淡入、动画太慢显得界面迟钝、展开收起一抖一抖、下拉从中间放大、关闭没有动画突然消失、骨架屏换成内容时页面跳动、加载 spinner 一闪而过、悬停时元素来回抖、连续触发时动画从头重播、没有适配"减少动态效果"。

## 目录
1. 先问要不要动
2. 动效令牌
3. 只动 transform 和 opacity
4. 缓动与时长
5. 方向与原点
6. 进入与退出
7. 可打断
8. 布局稳定（CLS）
9. 加载动效
10. 减少动态效果（reduced motion）
11. 修复配方

---

## 1. 先问要不要动

动效只在两种情况下使用：**说明因果关系**（这个面板是从那个按钮展开的、这条数据被删掉了、列表顺序变了），或**刻意的少量点缀**（首次引导、成功庆祝）。

不应该有动画的地方：
- 高频操作（每天上百次的按钮、键盘快捷键、命令面板开关、表格排序切换）——动画只会拖慢。
- 整页所有卡片依次淡入上浮（AI 最常见的"模板味"）。
- 滚动时每个区块都触发入场动画（后台/运营工具尤其不要）。
- 自动播放、循环的装饰动画；超过 5 秒的自动动效必须能暂停。

拿不准时，删掉动画通常是最好的修复。

## 2. 动效令牌

和颜色、间距一样，时长和缓动只用令牌。项目没有时建议（征得同意后）建立：

```css
:root {
  --duration-instant: 100ms;  /* 按下、颜色变化 */
  --duration-fast: 150ms;     /* hover、小元素、退出 */
  --duration-normal: 200ms;   /* 下拉、Popover、Tooltip */
  --duration-slow: 300ms;     /* 弹窗、抽屉、较大位移 */
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);      /* 进入、用户触发的展开 */
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);  /* 屏幕内位置移动 */
  --ease-exit: cubic-bezier(0.4, 0, 1, 1);         /* 退出 */
}
```

规则：UI 动画一般 ≤ 300ms，超过需要理由；反馈类不超过 500ms。不要用 bounce / elastic 回弹曲线（显得过时且抢注意力）。

## 3. 只动 transform 和 opacity

- **禁止动画的属性**：`width`、`height`、`top`、`left`、`right`、`bottom`、`margin`、`padding`、`border-width`、`font-size`。它们每一帧都触发重排，卡顿且影响交互响应。
- **禁止 `transition: all`**（Tailwind `transition-all`）：会把无意中变化的布局属性也动画化。明确列出属性：`transition: opacity 150ms, transform 150ms`（Tailwind `transition-[opacity,transform]` 或 `transition-opacity`/`transition-transform`；`transition-colors` 用于颜色）。
- 展开/收起不要 `height: 0 → auto`：
  - 小面板用 `transform: scaleY()` + `opacity`，`transform-origin: top`；
  - 需要真实推开下方内容的手风琴：用 `grid-template-rows: 0fr → 1fr`，或组件库的 Collapse；
  - 或者干脆不做高度动画，只做内容淡入。
- 用 JS 驱动的动画用 `requestAnimationFrame` 或 Web Animations API，不用 `setInterval`；不要在动画循环中读取布局（offsetTop、getBoundingClientRect）再写样式。
- 不要通过修改父级 CSS 变量逐帧驱动子元素 transform（会导致大范围样式重算）。
- 实现优先级：CSS > Web Animations API > JS 动画库。已经在用 Framer Motion/Motion 的项目沿用它，不再引入第二个动画库。

## 4. 缓动与时长

- 进入和用户触发的展开：**ease-out**（开头快，给人"立即响应"的感觉）。
- 屏幕内元素从 A 移到 B：ease-in-out。
- **UI 进入不要用 ease-in**：它把变化最慢的部分放在最开始，同样 300ms 会显得慢得多。
- 线性（linear）只用于旋转 spinner、进度条等匀速运动。
- 退出比进入快，大约是进入时长的一半到三分之二（弹窗 250ms 进、150ms 出）。
- 按下/松开类交互不对称：按下立刻响应，松开可以稍慢。
- 一组元素同时进入时可以用 30–80ms 的错开（stagger），总时长仍控制在 300–400ms 内；列表很长时只对前几项错开。

## 5. 方向与原点

- 下拉、Popover、Tooltip 从**触发器所在方向**展开：`transform-origin` 设在靠近触发器的一边（组件库一般提供 `--radix-popover-content-transform-origin` 之类变量），不要从中心放大。
- 不要从 `scale(0)` 开始，从 `scale(0.95~0.97)` + `opacity: 0` 开始。弹窗可以居中缩放。
- toast 从它停靠的边缘滑入；抽屉从它所在的一侧滑入。
- 位移幅度小（4–16px），不要整屏飞入。
- 悬停上浮这类位移放在内层元素，外层热区不动，否则指针在边缘时元素上移→离开→下落→再进入，来回闪烁。

## 6. 进入与退出

- 有进入动画的元素也要有退出动画，否则"动画进来、瞬间消失"很突兀。React 中条件渲染会让元素直接卸载，需要使用 `AnimatePresence`、组件库自带的过渡、或 `data-state=closed` 的退出动画。
- 退出动画期间元素不应再响应点击（`pointer-events: none`），也不应阻挡下面的内容。
- 新元素插入列表时，其他元素的位置变化可以用布局动画（FLIP / Motion `layout`），但数据量大时关闭。
- CSS 新特性 `@starting-style` 可以为首次渲染的元素定义进入起点，但要确认浏览器支持范围。

## 7. 可打断

- 可能被快速重复触发的动效（toast、开关、展开收起、悬停）使用 **transition**，它会从当前值继续过渡；不要用 keyframes，它会每次从头重播，连续操作时跳动。
- 动画进行中用户可以继续操作（再次点击关闭、输入），不要用 `setTimeout` 等动画结束才解锁交互。
- 不要让页面切换动画阻塞点击。

## 8. 布局稳定（CLS）

没有用户输入时发生的元素位移会被用户感知为"页面跳了一下"，也会计入 CLS（目标 < 0.1）。
- 图片、视频、广告位、图表：设置宽高或 `aspect-ratio`，提前占位。
- 骨架屏的尺寸和最终内容**一致**（行数、高度、间距），替换时不移动下方元素。
- 异步出现的提示条/横幅不要插入到内容上方把内容往下推；用覆盖式（toast）或预留位置。
- 字体加载用 `font-display: swap` + 尺寸接近的回退字体，关键字体预加载。
- 用 `display: none → block` 做淡入会引起位移；用 opacity + 预留空间。
- 按钮切换 loading 时宽度不变（spinner 叠加或保留文字）。

## 9. 加载动效

- spinner 延迟 150–300ms 再显示，显示后至少保持 300–500ms，避免一闪而过。
- 超过约 1 秒的内容加载用骨架屏而不是全屏 spinner；局部加载只在局部显示，不遮住整页。
- 骨架屏的 shimmer 动画在 reduced motion 下改为静态。
- 骨架屏、占位元素加 `aria-hidden="true"`，容器用 `aria-busy="true"`。
- 进度可知时用进度条而不是无限 spinner。

## 10. 减少动态效果（reduced motion）

- 所有移动类动画（位移、缩放、视差、自动滚动、shimmer、无限循环）必须在 `prefers-reduced-motion: reduce` 下关闭或替换为淡入。这是无障碍要求，不是可选项（前庭功能障碍用户会头晕）。
- 全局兜底（放在全局样式最后，这是 `!important` 少数合理用途之一；只在项目全局样式文件中添加一次）：
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```
- JS 动画同样检查：`matchMedia('(prefers-reduced-motion: reduce)')`，Motion 用 `useReducedMotion` 或 `MotionConfig reducedMotion="user"`。
- `scroll-behavior: smooth` 也属于动效。

## 11. 修复配方

| 症状 | 根因 | 改法 |
|---|---|---|
| 展开收起卡顿、抖动 | 动画 height/max-height/padding | scaleY + opacity；或 grid-rows 0fr→1fr；或不做高度动画 |
| 悬停时整页微卡 | `transition: all` / 动画 box-shadow 大面积 | 列出具体属性；阴影用伪元素 + opacity |
| 下拉从中间弹出，很怪 | transform-origin 默认 center / scale(0) | 原点设在触发器一侧，从 0.95 开始 |
| 界面感觉迟钝 | 时长 400ms+、ease-in | 缩短到 150–250ms，ease-out |
| 关闭时突然消失 | 条件渲染直接卸载 | AnimatePresence / 组件库过渡 / data-state 退出动画 |
| 连点时动画从头重播 | keyframes | 改用 transition |
| 悬停时元素上下抖动 | 位移移动了热区 | 位移放内层，外层固定 |
| 加载完成时页面跳动 | 骨架屏尺寸不一致 / 图片无尺寸 | 骨架屏匹配最终布局；图片设 aspect-ratio |
| spinner 一闪而过 | 无显示延迟 | 延迟 150–300ms 显示，最少显示 300ms |
| 系统开了减少动态效果仍在飞 | 未处理 reduced motion | 全局兜底 + JS 动画检查 |
| 每个卡片都在淡入上浮 | 为动而动 | 删除，最多保留首屏一次轻微淡入 |
