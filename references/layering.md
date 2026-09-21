# 层叠、裁剪与浮层规则

对应问题：下拉菜单被裁掉、弹窗被导航栏盖住、Tooltip 藏在相邻区块后面、半透明遮罩导致下拉透明、sticky/fixed 失效。

## 1. z-index 分层

项目应有一套固定的层级令牌，所有 z-index 只能取其中之一。如果项目没有，建议（并征得用户同意后）建立：

```css
:root {
  --z-base: 0;
  --z-raised: 10;      /* 卡片悬浮、局部叠放 */
  --z-sticky: 100;     /* 吸顶表头、吸顶工具栏 */
  --z-header: 200;     /* 全局顶栏、侧栏 */
  --z-dropdown: 300;   /* 下拉、Popover、自动补全 */
  --z-overlay: 400;    /* 遮罩 */
  --z-modal: 500;      /* 弹窗、抽屉 */
  --z-toast: 600;      /* 全局提示 */
  --z-tooltip: 700;
}
```

规则：
- 不写 `z-index: 9999`、`z-50` 之类随手值。遇到"被盖住"，先查层叠上下文，而不是把数字调大。
- 组件内部的局部叠放（角标压在头像上）用 `isolation: isolate` 在组件根上建立局部上下文，内部用 1、2 这样的小值，不污染全局。
- z-index 只对定位元素（非 static）和 flex/grid 子项生效。

## 2. 层叠上下文陷阱

以下属性会创建新的层叠上下文，子元素的 z-index 再大也出不去：
`transform`、`filter`、`backdrop-filter`、`opacity < 1`、`mix-blend-mode`、`will-change`、`contain: paint`、`isolation: isolate`、定位元素 + z-index。

典型事故：
- 顶栏加了 `backdrop-filter: blur()`，里面的下拉菜单永远被下面的内容区盖住，或者变成半透明。
- 卡片 hover 时 `transform: translateY(-2px)`，卡片里的 Tooltip 被下一张卡片盖住。
- `position: fixed` 的元素放在有 `transform` 的祖先里，定位变成相对那个祖先。

处理：浮层渲染到 body（portal），或把 `transform/filter` 移到不包含浮层的元素上。

## 3. 裁剪

`overflow: hidden / auto / scroll / clip` 会裁掉超出范围的子元素，包括 absolute 定位的下拉菜单。

- 在卡片、表格单元格、弹窗 body、侧栏等容器里放下拉/日期选择/自动补全时，**必须**使用组件库的浮层组件（它们通常会 portal 到 body 并自动翻转方向），不要自己写 `position:absolute` 的菜单。
- 给容器加 `overflow:hidden` 只为了圆角裁剪图片时，改为只给图片加圆角，或用 `overflow: clip` + 确认内部没有浮层。
- 表格内操作列的"更多"菜单是最常见的被裁剪点，一定用 portal。

## 4. 浮层组件检查清单

写/改任何 Dropdown、Select、Popover、Tooltip、DatePicker、Modal、Drawer 时确认：
- 使用项目已有组件（盘点清单）。
- 渲染在 body 或专用浮层容器中。
- 靠近视口边缘时会翻转/偏移（组件库一般自带；手写的需要 floating-ui 之类）。
- 弹窗：遮罩层级 < 弹窗层级；弹窗打开时锁定背景滚动；ESC 和点击遮罩可关闭（除非是危险确认）；焦点被限制在弹窗内，关闭后回到触发按钮。
- 弹窗内部的下拉，层级要高于弹窗（组件库通常自动处理；自定义时用 `--z-dropdown` 提升到弹窗之上或挂载到弹窗容器内）。

## 5. 修复配方

| 症状 | 根因 | 改法 |
|---|---|---|
| 下拉菜单只显示一半 | 祖先 `overflow:hidden/auto` | 用 portal 的浮层组件；或移除不必要的 overflow |
| 弹窗被顶栏盖住 | 弹窗在带 transform/z-index 的容器内；或层级数字随意 | portal 到 body + 使用 `--z-modal` |
| 下拉/菜单变半透明 | 祖先有 backdrop-filter 或 opacity | portal 出去；遮罩改为纯色 rgba 背景 |
| Tooltip 在相邻卡片后面 | 卡片 hover transform 创建上下文 | Tooltip 用 portal；或 hover 效果改用 box-shadow |
| fixed 元素位置不对 | 祖先有 transform/filter | 移到 body 层级或去掉祖先 transform |
| 调大 z-index 仍无效 | 元素所在的上下文整体低于对方 | 找到共同祖先下的上下文层级，调整上下文根元素或 portal |
