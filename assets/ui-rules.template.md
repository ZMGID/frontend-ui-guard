# 项目 UI 规则

> 放在项目根目录（或 docs/）。AI 在写任何前端代码前会先读这个文件。
> 保持简短（100 行以内），只写"必须用什么"和"禁止做什么"，细节指向代码中的示例文件。

## 技术栈
- 框架：<!-- React 18 / Vue 3 / ... -->
- 样式：<!-- Tailwind v3 / CSS Modules / SCSS / styled-components -->
- 组件库：<!-- 自研 src/components/ui / Ant Design / Element Plus / shadcn -->

## 必须使用的组件
| 需求 | 使用 | 示例文件 |
|---|---|---|
| 按钮 | `<Button variant size>` | src/pages/example/Buttons.tsx |
| 图标按钮 | `<IconButton>` | |
| 输入框 | `<Input>` | |
| 下拉选择 | `<Select>` | |
| 弹窗 | `<Modal>` | |
| 抽屉 | `<Drawer>` | |
| 表格 | `<Table>` | |
| 滚动区域 | 类名 `app-scrollbar` / `<ScrollArea>` | |
| 提示 | `toast()` | |
| 空状态 | `<Empty>` | |
| 加载 | `<Skeleton>` / `<Spin>` | |
| 页面骨架 | `<PageLayout title actions>` | |

## 设计令牌
- 颜色：只用 `var(--color-*)` / Tailwind 主题色 `primary`、`muted`...，禁止 hex
- 间距：4px 基准，只用刻度
- 字号：12 / 14 / 16 / 20 / 24
- 圆角：卡片 `--radius-lg`，控件 `--radius-md`
- 层级：`--z-dropdown` `--z-modal` `--z-toast`（禁止写数字）

## 页面规范
- 页面左右内边距：24；区块间距：16
- 页头：标题左，主操作右
- 筛选区：一行，控件 size=md，查询/重置在最右
- 表格：操作列固定在右侧，宽 120

## 禁止
- 业务代码中直接写 `<button>` `<input>` `<select>` 并加样式
- 引用 `src/legacy/` 下任何组件
- `!important`、`z-index` 数字、`100vh`、负 margin
- 修改 `src/styles/global.css` 和 `src/components/ui/` 除非任务明确要求

## 目标语言
- 界面语言：<!-- pt-BR / zh-CN -->，按最长语言设计布局
- 金额格式：<!-- Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL'}) -->
