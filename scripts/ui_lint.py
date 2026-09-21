#!/usr/bin/env python3
"""
ui_lint.py —— 前端 UI 静态检查（AI 写前端的常见违规）。

检查项（规则 id / 严重度）：
  raw-primitive        error  业务代码直接用原生 <button>/<input>/<select>… 而项目已有对应组件
  legacy-import        error  引用了 legacy/deprecated/old 目录
  important            error  !important 或 Tailwind 的 ! 前缀
  tw-conflict          error  同一 class 字符串里同一属性写了两个类（flex block、p-4 p-6、text-left text-center）
  hardcoded-color      error  业务代码中写死 hex/rgb/hsl 颜色（令牌文件除外）
  z-index              error/warn  z-index 不在允许的层级内，或 >= 1000，或直接写数字
  arbitrary-value      warn   Tailwind 任意值 p-[13px]、w-[347px]、text-[#333]
  off-scale-spacing    warn   CSS 中 margin/padding/gap 的 px 值不在间距刻度内
  negative-margin      warn   负 margin（常用来硬拉位置）
  viewport-unit        warn   100vh / h-screen / 100vw（移动端和滚动条问题）
  flex-grow-no-minw    warn   flex-1/grow 没配 min-w-0（会被内容撑破）
  truncate-check       info   truncate/ellipsis：确认祖先链上有 min-w-0
  native-scroll        warn   overflow-auto/scroll 没有使用全局滚动条类
  inline-style         warn   内联 style 写布局/颜色
  outline-none         warn   去掉了 outline 但没有 focus-visible 样式
  img-alt              warn   <img> 缺 alt
  placeholder-label    info   只有 placeholder 没有 label/aria-label 的输入框
  overflow-hidden      info   overflow-hidden 可能裁掉下拉/浮层
  --- 动效 ---
  transition-all       error  transition: all / transition-all / 只写时长的 transition
  animate-layout       warn   对 width/height/top/left/margin/padding/max-height 做动画（卡顿）
  motion-duration      warn   UI 动画时长过长（transition > 400ms，非循环 animation > 500ms，framer duration > 0.5）
  motion-easing        info   ease-in 用于 UI / 回弹曲线
  scale-zero           warn   从 scale(0) 开始的动画
  reduced-motion       warn   项目中有动画但全项目找不到 prefers-reduced-motion 适配
  --- 交互 ---
  hover-only           warn   仅悬停显示的内容/操作（group-hover:opacity-100 等）没有 focus-within 兜底
  clickable-div        warn   div/span/li 等绑定点击却没有 role 和 tabIndex（键盘无法操作）
  native-dialog        warn   window.alert / confirm（应使用项目的 ConfirmDialog / toast）
  bad-href             warn   href="#" / javascript:
  async-no-pending     warn   文件中有异步点击/提交处理，但找不到 loading/disabled/pending 处理
  fetch-race           warn   useEffect 中 fetch 未使用 AbortController/忽略标记（竞态、卸载后 setState）
  positive-tabindex    warn   tabIndex 为正数
  zoom-disabled        warn   user-scalable=no / maximum-scale=1
  block-paste          warn   阻止粘贴
  url-state            info   分页/筛选/Tab 等状态只在 useState 中（刷新后丢失）

用法：
  python3 ui_lint.py --root . --changed          # 只检查 git 中改动/新增的文件
  python3 ui_lint.py --root . src/pages/A.tsx     # 检查指定文件或目录
  python3 ui_lint.py --root . --all               # 检查 srcDirs 下全部文件
  可选：--format json   --min-severity warn   --config path

行内豁免：在该行或上一行写注释 ui-guard-ignore 或 ui-guard-ignore:rule-id
退出码：存在 error 时为 1。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

CODE_EXT = {".tsx", ".jsx", ".vue", ".svelte", ".html", ".ts", ".js"}
MARKUP_EXT = {".tsx", ".jsx", ".vue", ".svelte", ".html"}
STYLE_EXT = {".css", ".scss", ".sass", ".less", ".pcss"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", "out", "coverage", ".ui-guard", ".output"}
SEV_ORDER = {"info": 0, "warn": 1, "error": 2}

DEFAULTS = {
    "srcDirs": ["src"],
    "componentDirs": [],
    "primitiveDirs": [],
    "legacyDirs": [],
    "tokenFiles": [],
    "primitives": None,  # None = 自动探测
    "scrollbarClass": "",
    "spacingScale": [0, 1, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 36, 40, 44, 48, 56, 64, 72, 80, 96, 128],
    "zIndexAllowed": None,
}

AUTO_PRIMITIVES = {
    "button": ["Button", "Btn", "BaseButton", "AppButton"],
    "input": ["Input", "TextField", "BaseInput", "AppInput"],
    "textarea": ["Textarea", "TextArea"],
    "select": ["Select", "BaseSelect"],
    "table": ["Table", "DataTable"],
    "dialog": ["Modal", "Dialog"],
}
UI_LIB_PRIMITIVES = {  # 第三方组件库 -> 默认存在的组件
    "antd": {"button": "Button", "input": "Input", "textarea": "Input.TextArea", "select": "Select", "table": "Table", "dialog": "Modal"},
    "element-plus": {"button": "el-button", "input": "el-input", "textarea": "el-input type=textarea", "select": "el-select", "table": "el-table", "dialog": "el-dialog"},
    "naive-ui": {"button": "n-button", "input": "n-input", "select": "n-select", "table": "n-data-table", "dialog": "n-modal"},
    "@mui/material": {"button": "Button", "input": "TextField", "select": "Select", "table": "Table", "dialog": "Dialog"},
    "@arco-design/web-react": {"button": "Button", "input": "Input", "select": "Select", "table": "Table", "dialog": "Modal"},
    "@arco-design/web-vue": {"button": "a-button", "input": "a-input", "select": "a-select", "table": "a-table", "dialog": "a-modal"},
    "vant": {"button": "van-button", "input": "van-field", "dialog": "van-dialog"},
}


# ---------------------------------------------------------------- helpers
def load_config(root, path):
    cfg = json.loads(json.dumps(DEFAULTS))
    p = path or os.path.join(root, "ui-guard.config.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            user = json.load(f)
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
    return cfg


def rel(root, fp):
    return os.path.relpath(fp, root).replace(os.sep, "/")


def iter_files(root, targets):
    for t in targets:
        p = t if os.path.isabs(t) else os.path.join(root, t)
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for dp, dns, fns in os.walk(p):
                dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
                for fn in fns:
                    yield os.path.join(dp, fn)


def git_changed(root):
    files = set()
    for cmd in (["git", "diff", "--name-only", "HEAD"], ["git", "diff", "--name-only", "--cached"],
                ["git", "ls-files", "--others", "--exclude-standard"]):
        try:
            out = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=20).stdout
            files.update(l.strip() for l in out.splitlines() if l.strip())
        except Exception:
            pass
    return [f for f in files if os.path.exists(os.path.join(root, f))]


def detect_primitives(root, cfg):
    """返回 {原生标签: 推荐组件}。优先配置；否则从组件目录和依赖里自动探测。"""
    if cfg.get("primitives"):
        return cfg["primitives"]
    found = {}
    pkg = os.path.join(root, "package.json")
    if os.path.exists(pkg):
        try:
            d = json.load(open(pkg, encoding="utf-8"))
            deps = {**d.get("dependencies", {}), **d.get("devDependencies", {})}
            for lib, mapping in UI_LIB_PRIMITIVES.items():
                if lib in deps:
                    for k, v in mapping.items():
                        found.setdefault(k, f"{v}（{lib}）")
        except Exception:
            pass
    names = set()
    comp_dirs = cfg.get("componentDirs") or []
    scan_dirs = comp_dirs or cfg.get("srcDirs") or ["src"]
    for fp in iter_files(root, scan_dirs):
        r = rel(root, fp)
        if not comp_dirs and not re.search(r"(^|/)(components?|ui)(/|$)", r, re.I):
            continue
        ext = os.path.splitext(fp)[1]
        if ext in (".vue", ".svelte"):
            b = os.path.splitext(os.path.basename(fp))[0]
            names.add(b[:1].upper() + b[1:])
        elif ext in (".tsx", ".jsx", ".ts", ".js"):
            try:
                t = open(fp, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            names.update(re.findall(r"export\s+(?:default\s+)?(?:function|const|class)\s+([A-Z]\w*)", t))
            for grp in re.findall(r"export\s*\{([^}]+)\}", t):
                names.update(p.strip().split(" as ")[-1].strip() for p in grp.split(","))
    for tag, cands in AUTO_PRIMITIVES.items():
        for c in cands:
            if c in names:
                found[tag] = c
                break
    return found


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


# ---------------------------------------------------------------- tailwind conflicts
TW_GROUPS = [
    ("display", r"(block|inline-block|inline|flex|inline-flex|grid|inline-grid|hidden|contents|table|flow-root)"),
    ("position", r"(static|fixed|absolute|relative|sticky)"),
    ("text-align", r"text-(left|center|right|justify|start|end)"),
    ("flex-direction", r"flex-(row|col|row-reverse|col-reverse)"),
    ("flex-wrap", r"flex-(wrap|nowrap|wrap-reverse)"),
    ("justify", r"justify-(start|end|center|between|around|evenly|stretch|normal)"),
    ("items", r"items-(start|end|center|baseline|stretch)"),
    ("font-weight", r"font-(thin|extralight|light|normal|medium|semibold|bold|extrabold|black)"),
    ("font-size", r"text-(xs|sm|base|lg|xl|[2-9]xl)"),
    ("overflow", r"overflow-(auto|hidden|visible|scroll|clip)"),
    ("overflow-x", r"overflow-x-(auto|hidden|visible|scroll|clip)"),
    ("overflow-y", r"overflow-y-(auto|hidden|visible|scroll|clip)"),
    ("whitespace", r"whitespace-(normal|nowrap|pre|pre-line|pre-wrap|break-spaces)"),
    ("rounded", r"rounded(-(none|sm|md|lg|xl|2xl|3xl|full))?"),
    ("shadow", r"shadow(-(none|sm|md|lg|xl|2xl|inner))?"),
]
for side in ["p", "px", "py", "pt", "pr", "pb", "pl", "ps", "pe", "m", "mx", "my", "mt", "mr", "mb", "ml",
             "w", "h", "min-w", "min-h", "max-w", "max-h", "gap", "gap-x", "gap-y", "top", "left", "right", "bottom",
             "inset", "leading", "tracking", "z", "space-x", "space-y", "grid-cols", "col-span"]:
    TW_GROUPS.append((side, re.escape(side) + r"-(\[[^\]]+\]|[\w./]+)"))
TW_GROUPS_C = [(g, re.compile(r"^-?" + p + r"$")) for g, p in TW_GROUPS]


def tw_group(cls):
    variant, _, base = cls.rpartition(":")
    base = base.lstrip("!")
    for g, rx in TW_GROUPS_C:
        if rx.match(base):
            return variant + "|" + g
    return None


CLASS_ATTR = re.compile(r"""(?<![\w-])(?::class|className|class)\s*=\s*(?:"([^"]*)"|'([^']*)'|\{\s*["'`]([^"'`$]*)["'`]\s*\})""")
CLASS_FN = re.compile(r"""\b(?:cn|clsx|classnames|classNames|twMerge|twJoin|cva|tw)\s*\(""")
QUOTED = re.compile(r"""["'`]([^"'`]{2,400})["'`]""")


def class_strings(text):
    """(pos, class_string) 列表。"""
    out = []
    for m in CLASS_ATTR.finditer(text):
        s = next(g for g in m.groups() if g is not None)
        out.append((m.start(), s))
    for m in CLASS_FN.finditer(text):
        seg = text[m.end(): m.end() + 800]
        depth, end = 1, len(seg)
        for i, ch in enumerate(seg):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        for q in QUOTED.finditer(seg[:end]):
            if re.search(r"[a-z]-|^(flex|grid|block|hidden|relative|absolute)\b", q.group(1)):
                out.append((m.end() + q.start(), q.group(1)))
    return out


# ---------------------------------------------------------------- lint
class Linter:
    def __init__(self, root, cfg):
        self.root = root
        self.cfg = cfg
        self.issues = []
        self.saw_motion = False
        self.primitives = detect_primitives(root, cfg)
        self.spacing = set(float(x) for x in cfg["spacingScale"])
        self.z_allowed = set(cfg["zIndexAllowed"]) if cfg.get("zIndexAllowed") else None
        self.scroll_cls = cfg.get("scrollbarClass") or self.detect_scrollbar_class()
        legacy = [d.strip("/") for d in cfg.get("legacyDirs", [])]
        self.legacy_re = re.compile(r"""from\s+['"][^'"]*(?:/|^)(?:legacy|deprecated|old|_old|bak)(?:/|['"])""" +
                                    "".join(r"|from\s+['\"][^'\"]*" + re.escape(d) for d in legacy))

    def detect_scrollbar_class(self):
        """没有配置时，从样式文件中找自定义滚动条类（.xxx::-webkit-scrollbar 或含 scrollbar-width 的类）。"""
        for fp in iter_files(self.root, self.cfg.get("srcDirs") or ["src"]):
            if os.path.splitext(fp)[1] not in STYLE_EXT:
                continue
            try:
                t = open(fp, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            m = re.search(r"\.([A-Za-z][\w-]*)::-webkit-scrollbar", t) or \
                re.search(r"\.([A-Za-z][\w-]*)\s*\{[^}]*scrollbar-(?:width|color)", t)
            if m:
                return m.group(1)
        return ""

    def add(self, fp, text, pos, rule, sev, msg, lines):
        ln = line_of(text, pos)
        cur = lines[ln - 1] if ln - 1 < len(lines) else ""
        prev = lines[ln - 2] if ln >= 2 else ""
        for l in (cur, prev):
            if "ui-guard-ignore" in l:
                m = re.search(r"ui-guard-ignore:([\w-]+)", l)
                if not m or m.group(1) == rule:
                    return
        self.issues.append({"file": rel(self.root, fp), "line": ln, "rule": rule, "severity": sev,
                            "message": msg, "snippet": cur.strip()[:140]})

    def is_under(self, r, dirs):
        return any(r == d.strip("/") or r.startswith(d.strip("/") + "/") for d in dirs)

    def lint_file(self, fp):
        ext = os.path.splitext(fp)[1]
        if ext not in CODE_EXT and ext not in STYLE_EXT:
            return
        r = rel(self.root, fp)
        if any(part in SKIP_DIRS for part in r.split("/")):
            return
        try:
            text = open(fp, encoding="utf-8", errors="ignore").read()
        except Exception:
            return
        lines = text.split("\n")
        is_primitive_file = self.is_under(r, self.cfg.get("primitiveDirs", [])) or \
            bool(re.search(r"(^|/)(components/ui|ui/primitives|primitives)(/|$)", r))
        is_token_file = self.is_under(r, self.cfg.get("tokenFiles", [])) or \
            bool(re.search(r"(token|theme|variables|palette)", os.path.basename(r), re.I)) or \
            os.path.basename(r).startswith("tailwind.config")
        add = lambda pos, rule, sev, msg: self.add(fp, text, pos, rule, sev, msg, lines)

        # ---- 通用：!important
        for m in re.finditer(r"!important", text):
            add(m.start(), "important", "error", "禁止 !important：找到冲突规则的来源并修正，而不是压制")

        # ---- 硬编码颜色
        if not is_token_file:
            for m in re.finditer(r"(?<![\w&/])#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b", text):
                # 过滤 JSX 中的锚点/ID、HTML 实体
                ctx = text[max(0, m.start() - 12):m.start()]
                if re.search(r"(href|to|id)\s*=\s*[\"'{]?$", ctx):
                    continue
                add(m.start(), "hardcoded-color", "error" if ext in CODE_EXT else "warn",
                    f"硬编码颜色 {m.group(0)}：改用颜色令牌（CSS 变量/主题色）")
            for m in re.finditer(r"\b(?:rgba?|hsla?)\(\s*\d", text):
                add(m.start(), "hardcoded-color", "warn", "rgb()/hsl() 字面量：改用颜色令牌")

        # ---- 动效（CSS 文件与 JS 样式对象）
        self.css_motion(text, add)

        # ---- z-index
        for m in re.finditer(r"z-index\s*:\s*(-?\d+)|zIndex\s*:\s*['\"]?(-?\d+)", text):
            v = int(m.group(1) or m.group(2))
            self._z(add, m.start(), v, raw=True)

        # ---- 视口单位
        for m in re.finditer(r"\b100vh\b", text):
            add(m.start(), "viewport-unit", "warn", "100vh 在移动端会多出地址栏高度：用 height:100% 链或 100dvh")
        for m in re.finditer(r"\b100vw\b", text):
            add(m.start(), "viewport-unit", "warn", "100vw 包含滚动条宽度，常导致横向溢出：用 100%")

        # ---- 负 margin（CSS）
        for m in re.finditer(r"\bmargin(?:-(?:top|bottom|left|right|inline|block)(?:-start|-end)?)?\s*:\s*[^;]*-\d", text):
            add(m.start(), "negative-margin", "warn", "负 margin 常用来硬拉位置：修正父级布局或 gap")

        # ---- CSS 间距刻度
        if ext in STYLE_EXT or ext in (".vue", ".svelte") or "styled" in text or "css`" in text:
            for m in re.finditer(r"\b(margin|padding|gap|row-gap|column-gap)(-(?:top|bottom|left|right|inline|block)(?:-start|-end)?)?\s*:\s*([^;{}\n]+)", text):
                bad = [px for px in re.findall(r"(?<![\w.-])(-?\d+(?:\.\d+)?)px", m.group(3)) if abs(float(px)) not in self.spacing]
                if bad:
                    add(m.start(), "off-scale-spacing", "warn", f"{m.group(1)} 使用了刻度外的值 {', '.join(b + 'px' for b in bad)}：改用间距令牌")
            for m in re.finditer(r"outline\s*:\s*(none|0)\b", text):
                window = text[m.start(): m.start() + 2000]
                if ":focus" not in text:
                    add(m.start(), "outline-none", "warn", "去掉 outline 但文件内没有任何 :focus/:focus-visible 样式，键盘用户看不到焦点")

        if ext not in CODE_EXT:
            return

        # ---- legacy import
        for m in self.legacy_re.finditer(text):
            add(m.start(), "legacy-import", "error", "引用了 legacy/deprecated 目录中的代码：使用当前规范组件")

        self.code_interaction(text, ext, add)

        # ---- 原生标签
        if ext in MARKUP_EXT and not is_primitive_file:
            for tag, comp in self.primitives.items():
                for m in re.finditer(r"<" + re.escape(tag) + r"(?=[\s>/])", text):
                    snippet_end = text.find(">", m.start())
                    attrs = text[m.start(): snippet_end if snippet_end > 0 else m.start() + 200]
                    if tag == "input" and re.search(r"type\s*=\s*[\"'](hidden|file|checkbox|radio)[\"']", attrs):
                        continue  # 这些经常合理地用原生
                    add(m.start(), "raw-primitive", "error",
                        f"业务代码直接使用原生 <{tag}>：项目已有 {comp}，请复用（组件实现目录内可忽略）")

        # ---- img alt / placeholder label
        if ext in MARKUP_EXT:
            for m in re.finditer(r"<img\b[^>]*>", text, re.S):
                if not re.search(r"\balt\s*=", m.group(0)) and not re.search(r":alt\s*=", m.group(0)):
                    add(m.start(), "img-alt", "warn", "<img> 缺少 alt（装饰图用 alt=\"\"）")
            for m in re.finditer(r"<(?:input|Input|textarea|Textarea)\b[^>]*placeholder[^>]*>", text, re.S):
                t = m.group(0)
                if not re.search(r"aria-label|aria-labelledby|\blabel\s*=|\bid\s*=", t):
                    add(m.start(), "placeholder-label", "info", "只有 placeholder 的输入框：补可见 label 或 aria-label")
            for m in re.finditer(r"style\s*=\s*\{\{([^}]*)\}\}|style\s*=\s*\"([^\"]*)\"", text):
                body = m.group(1) or m.group(2) or ""
                if re.search(r"\b(width|height|margin|padding|color|background|position|top|left|right|bottom|fontSize|font-size|display)\b", body) \
                        and not re.search(r"--[\w-]+|var\(", body):
                    add(m.start(), "inline-style", "warn", "内联 style 写布局/颜色：改用类名/组件 props/令牌（动态计算值除外）")

        # ---- Tailwind class 字符串
        for pos, s in class_strings(text):
            classes = s.split()
            if not classes:
                continue
            groups = defaultdict(list)
            for c in classes:
                g = tw_group(c)
                if g:
                    groups[g].append(c)
                if c.startswith("!") or ":!" in c:
                    add(pos, "important", "error", f"Tailwind important 前缀 {c}：修正冲突来源而不是强压")
                am = re.match(r"^(?:[\w-]+:)*-?(p[xytrblse]?|m[xytrbl]?|gap(?:-[xy])?|w|h|min-w|min-h|max-w|max-h|top|left|right|bottom|inset|text|leading|tracking|rounded|space-[xy]|bg|border|z)-\[([^\]]+)\]$", c)
                if am:
                    val = am.group(2)
                    kind = "颜色" if re.match(r"#|rgb|hsl", val) else "值"
                    sev = "error" if kind == "颜色" else "warn"
                    add(pos, "hardcoded-color" if kind == "颜色" else "arbitrary-value", sev,
                        f"Tailwind 任意{kind} {c}：改用主题中的刻度/令牌")
                zm = re.match(r"^(?:[\w-]+:)*z-(\d+)$", c)
                if zm:
                    self._z(add, pos, int(zm.group(1)), raw=False)
                if re.match(r"^(?:[\w-]+:)*-m[xytrbl]?-", c):
                    add(pos, "negative-margin", "warn", f"负 margin {c}：修正布局而不是硬拉")
                if re.match(r"^(?:[\w-]+:)*(h|min-h|max-h)-screen$", c):
                    add(pos, "viewport-unit", "warn", f"{c} 即 100vh：移动端改用 h-dvh / h-full 链")
                if re.match(r"^(?:[\w-]+:)*w-screen$", c):
                    add(pos, "viewport-unit", "warn", "w-screen 即 100vw，易导致横向溢出：用 w-full")
                base_c = re.sub(r"^(?:[\w-]+:)*", "", c)
                if base_c == "transition-all":
                    add(pos, "transition-all", "error", "transition-all 会把布局属性也动画化：改用 transition-colors / transition-opacity / transition-transform")
                tm = re.match(r"^transition-\[([^\]]+)\]$", base_c)
                if tm and re.search(r"\b(width|height|max-height|top|left|right|bottom|margin|padding)\b", tm.group(1)):
                    add(pos, "animate-layout", "warn", f"{c} 对布局属性做动画，会卡顿：改用 transform/opacity 或 grid-rows 0fr→1fr")
                dm = re.match(r"^duration-(\d+)$", base_c)
                if dm and int(dm.group(1)) > 400:
                    add(pos, "motion-duration", "warn", f"{c} 过长：UI 动画一般 ≤ 300ms（用时长令牌）")
                if base_c == "ease-in":
                    add(pos, "motion-easing", "info", "ease-in 用于 UI 进入会显得迟钝：进入用 ease-out")
                if re.match(r"^scale-0$", base_c) and ":" not in c:
                    add(pos, "scale-zero", "warn", "从 scale-0 开始的动画不自然：从 scale-95 + opacity-0 开始")
                if base_c.startswith("animate-") and base_c not in ("animate-none",):
                    self.saw_motion = True
                if base_c.startswith(("transition", "duration-")):
                    self.saw_motion = True
            for g, cs in groups.items():
                uniq = list(dict.fromkeys(cs))
                if len(uniq) > 1:
                    add(pos, "tw-conflict", "error", f"同一属性写了多个类 {' '.join(uniq)}：只保留一个")
            has = set(re.sub(r"^(?:[\w-]+:)*", "", c) for c in classes)
            if ({"flex-1", "grow", "flex-auto"} & has) and "min-w-0" not in has and "shrink-0" not in has \
                    and not ({"flex-col", "flex-row"} & has and "flex" in has):
                add(pos, "flex-grow-no-minw", "warn", "flex-1/grow 没有 min-w-0：内容过长时会撑破父容器（纵向 flex 子项则需 min-h-0）")
            reveal = [c for c in classes if re.match(r"^(?:[\w-]+:)*(?:group-hover|peer-hover|hover):(opacity-100|visible|block|flex|inline-flex|grid)$", c)]
            hidden_default = ({"opacity-0", "invisible", "hidden"} & has)
            if reveal and hidden_default and not any(re.search(r"focus-within|focus-visible|focus:|group-focus|peer-focus|aria-|data-\[state", c) for c in classes):
                add(pos, "hover-only", "warn", f"{' '.join(reveal)}：仅悬停时显示，键盘和触屏用户看不到。加 group-focus-within: 变体，移动端默认显示或收进“更多”菜单")
            if ({"truncate", "text-ellipsis"} & has or any(c.startswith("line-clamp-") for c in has)):
                add(pos, "truncate-check", "info", "截断：确认本元素及所有 flex 祖先都有 min-w-0，并提供 title/tooltip 显示全文")
            scroll = [c for c in has if re.match(r"overflow(-[xy])?-(auto|scroll)$", c)]
            if scroll and self.scroll_cls and self.scroll_cls not in has:
                add(pos, "native-scroll", "warn", f"滚动容器 {scroll[0]} 未使用全局滚动条类 .{self.scroll_cls}")
            if {"overflow-hidden"} & has:
                add(pos, "overflow-hidden", "info", "overflow-hidden 会裁掉内部 absolute 下拉/浮层：内部有浮层时用 portal 组件")
            if "outline-none" in has and not any("focus" in c for c in classes):
                add(pos, "outline-none", "warn", "outline-none 但没有 focus/focus-visible 样式")

    LAYOUT_PROPS = r"(?:width|height|max-height|min-height|top|left|right|bottom|margin(?:-\w+)?|padding(?:-\w+)?|font-size|border-width)"

    @staticmethod
    def _ms(v):
        m = re.match(r"([\d.]+)(ms|s)$", v)
        if not m:
            return None
        n = float(m.group(1))
        return n * 1000 if m.group(2) == "s" else n

    def css_motion(self, text, add):
        for m in re.finditer(r"(?<![\w-])transition(?:-property)?\s*:\s*([^;{}]+)", text):
            val = m.group(1).strip().strip("'\"`")
            if not val or val.startswith(("string", "var(--")) and not re.search(r"\d", val):
                continue
            self.saw_motion = True
            if re.match(r"^all\b", val) or re.match(r"^[\d.]+m?s\b", val) or re.search(r",\s*all\b", val):
                add(m.start(), "transition-all", "error", "transition: all（或只写时长）会把布局属性也动画化：明确列出 opacity/transform/颜色")
            if re.search(r"(?<![\w-])" + self.LAYOUT_PROPS + r"(?![\w-])", val):
                add(m.start(), "animate-layout", "warn", "对布局属性做过渡（width/height/top/margin…）每帧重排、卡顿：改用 transform/opacity")
            for t in re.findall(r"(?<![\w.])([\d.]+m?s)\b", val)[:1]:
                ms = self._ms(t)
                if ms and ms > 400:
                    add(m.start(), "motion-duration", "warn", f"过渡时长 {t} 过长：UI 一般 ≤ 300ms，用时长令牌")
            if re.search(r"\bease-in\b(?!-out)", val):
                add(m.start(), "motion-easing", "info", "ease-in 用于 UI 会显得迟钝：进入用 ease-out，退出可用 ease-in")
        for m in re.finditer(r"(?<![\w-])transition-duration\s*:\s*([\d.]+m?s)", text):
            ms = self._ms(m.group(1))
            if ms and ms > 400:
                add(m.start(), "motion-duration", "warn", f"过渡时长 {m.group(1)} 过长：UI 一般 ≤ 300ms")
        for m in re.finditer(r"(?<![\w-])animation\s*:\s*([^;{}]+)", text):
            val = m.group(1).strip().strip("'\"`")
            if not re.search(r"\d", val):
                continue
            self.saw_motion = True
            if "infinite" in val:
                continue
            for t in re.findall(r"(?<![\w.])([\d.]+m?s)\b", val)[:1]:
                ms = self._ms(t)
                if ms and ms > 500:
                    add(m.start(), "motion-duration", "warn", f"动画时长 {t} 过长：UI 动画一般 ≤ 300ms，入场装饰也不宜超过 500ms")
        for m in re.finditer(r"@keyframes\s+([\w-]+)\s*\{", text):
            self.saw_motion = True
            depth, i = 1, m.end()
            while i < len(text) and depth:
                depth += {"{": 1, "}": -1}.get(text[i], 0)
                i += 1
            body = text[m.end():i]
            props = set(re.findall(r"(?<![\w-])(" + self.LAYOUT_PROPS + r")\s*:", body))
            if props:
                add(m.start(), "animate-layout", "warn", f"@keyframes {m.group(1)} 对布局属性 {', '.join(sorted(props))} 做动画：改用 transform/opacity")
            if re.search(r"scale\(\s*0\s*\)", body):
                add(m.start(), "scale-zero", "warn", f"@keyframes {m.group(1)} 从 scale(0) 开始：改为 scale(0.95) + opacity")
        for m in re.finditer(r"cubic-bezier\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)", text):
            y1, y2 = float(m.group(2)), float(m.group(4))
            if y1 > 1.05 or y2 > 1.05 or y1 < -0.05 or y2 < -0.05:
                add(m.start(), "motion-easing", "info", "回弹/弹性曲线在业务界面中显得过时且抢注意力，谨慎使用")

    def code_interaction(self, text, ext, add):
        # framer-motion / motion
        for m in re.finditer(r"\b(animate|initial|exit|whileHover|whileTap)\s*=\s*\{\{([^{}]*)\}\}", text):
            self.saw_motion = True
            body = m.group(2)
            if re.search(r"\b(height|width|top|left|marginTop|marginLeft|padding\w*|maxHeight)\s*:", body):
                add(m.start(), "animate-layout", "warn", f"{m.group(1)} 中对布局属性做动画：改用 x/y/scale/opacity，或 layout 动画")
            if m.group(1) == "initial" and re.search(r"\bscale\s*:\s*0\s*[,}]?", body) and not re.search(r"scale\s*:\s*0\.", body):
                add(m.start(), "scale-zero", "warn", "initial scale: 0 不自然：从 0.95 开始并配合 opacity")
        for m in re.finditer(r"\btransition\s*=\s*\{\{([^{}]*)\}\}", text):
            dm = re.search(r"duration\s*:\s*([\d.]+)", m.group(1))
            if dm and float(dm.group(1)) > 0.5 and "repeat" not in m.group(1):
                add(m.start(), "motion-duration", "warn", f"motion duration {dm.group(1)}s 过长：UI 动画一般 ≤ 0.3s")
        if re.search(r"from\s+['\"](framer-motion|motion/react|motion)['\"]", text):
            self.saw_motion = True
        # 原生 alert/confirm
        for m in re.finditer(r"(?<![\w.])(?:window\.)?(alert|confirm|prompt)\s*\(", text):
            add(m.start(), "native-dialog", "warn", f"使用了原生 {m.group(1)}()：改用项目的 ConfirmDialog / Modal / toast")
        # 错误的 href
        for m in re.finditer(r"href\s*=\s*[\"'](#|javascript:[^\"']*)[\"']", text):
            add(m.start(), "bad-href", "warn", "href=\"#\" / javascript:：导航用真实链接，操作用 button")
        # 正数 tabindex
        for m in re.finditer(r"tab[iI]ndex\s*=\s*(?:\{\s*|[\"'])([1-9]\d*)", text):
            add(m.start(), "positive-tabindex", "warn", "正数 tabIndex 会打乱 Tab 顺序：用 0 或调整 DOM 顺序")
        for m in re.finditer(r"user-scalable\s*=\s*no|maximum-scale\s*=\s*1(?:\.0)?\b", text):
            add(m.start(), "zoom-disabled", "warn", "禁用了缩放：不要禁止用户缩放（iOS 聚焦放大问题用 16px 字号解决）")
        for m in re.finditer(r"onPaste\s*=\s*\{[^}]*preventDefault|@paste\.prevent", text):
            add(m.start(), "block-paste", "warn", "阻止了粘贴：允许粘贴，再做校验")
        if ext not in MARKUP_EXT:
            return
        # 非语义可点击元素
        for m in re.finditer(r"<(div|span|li|td|tr|img|p|section|article|i|svg)\b([^>]*?)\s(?:onClick|@click|v-on:click|on:click)\s*=", text, re.S):
            tag_end = text.find(">", m.end())
            attrs = m.group(2) + text[m.end(): tag_end if tag_end > 0 else m.end() + 300]
            if not re.search(r"\brole\s*=", attrs) or not re.search(r"tab[iI]ndex", attrs):
                add(m.start(), "clickable-div", "warn", f"<{m.group(1)}> 绑定了点击但不是 button/a：键盘无法操作。导航用 <a href>，操作用 Button；整行可点时补 role + tabIndex + Enter 键处理")
        # 异步处理无 pending
        am = re.search(r"(onClick|onSubmit|@click|@submit(?:\.prevent)?|onConfirm|onOk)\s*=\s*\{?\s*[\"']?\s*async\b|const\s+(handle|on)\w*\s*=\s*async\b|async\s+function\s+(handle|on)\w*", text)
        if am and re.search(r"\bawait\b", text) and not re.search(r"\b(disabled|loading|isLoading|isPending|pending|isSubmitting|submitting|saving|isSaving|aria-busy|isMutating|confirmLoading)\b", text):
            add(am.start(), "async-no-pending", "warn", "异步操作没有 loading/禁用处理：请求期间禁用按钮并显示加载，防止重复提交；失败时显示错误并恢复")
        # useEffect + fetch 竞态
        for m in re.finditer(r"useEffect\s*\(\s*\(\s*\)\s*=>\s*\{", text):
            body = text[m.end(): m.end() + 1200]
            end = body.find("}, [")
            body = body[: end if end > 0 else 1200]
            if re.search(r"\b(fetch|axios|request|http)\s*[.(]", body) and not re.search(r"AbortController|signal|ignore|cancel|isMounted|active\s*=\s*false|stale", body):
                add(m.start(), "fetch-race", "warn", "useEffect 里直接请求且没有取消/忽略过期响应：快速切换时旧结果会覆盖新结果。用项目的数据层（React Query 等）或 AbortController")
        # URL 状态
        for m in re.finditer(r"const\s*\[\s*(page|currentPage|pageNum|activeTab|tab|filters?|sort\w*|keyword|query|search\w*|status)\s*,\s*set\w+\s*\]\s*=\s*useState", text):
            add(m.start(), "url-state", "info", f"{m.group(1)} 只存在组件状态中，刷新/返回后丢失：考虑同步到 URL 查询参数")

    def _z(self, add, pos, v, raw):
        if v >= 1000:
            add(pos, "z-index", "error", f"z-index {v} 过大：说明层级失控，使用层级令牌（dropdown/modal/toast）")
        elif self.z_allowed is not None and v not in self.z_allowed:
            add(pos, "z-index", "error", f"z-index {v} 不在允许的层级 {sorted(self.z_allowed)} 中")
        elif raw and v > 2:
            add(pos, "z-index", "warn", f"z-index 直接写数字 {v}：改用层级令牌 var(--z-*)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--root", default=".")
    ap.add_argument("--config", default=None)
    ap.add_argument("--changed", action="store_true", help="只检查 git 改动文件")
    ap.add_argument("--all", action="store_true", help="检查 srcDirs 下全部文件")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--min-severity", choices=["info", "warn", "error"], default="info")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    cfg = load_config(root, args.config)
    linter = Linter(root, cfg)

    if args.changed:
        targets = git_changed(root)
        if not targets:
            print("没有检测到 git 改动文件（或不是 git 仓库）。可以直接传入文件路径。")
            return 0
    elif args.all or not args.paths:
        targets = cfg.get("srcDirs") or ["src"]
    else:
        targets = args.paths

    for fp in iter_files(root, targets):
        linter.lint_file(fp)

    if linter.saw_motion:
        found_rm = False
        for fp in iter_files(root, (cfg.get("srcDirs") or ["src"]) + [f for f in ("tailwind.config.js", "tailwind.config.ts", "index.html") if os.path.exists(os.path.join(root, f))]):
            if os.path.splitext(fp)[1] not in CODE_EXT | STYLE_EXT:
                continue
            try:
                t = open(fp, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if re.search(r"prefers-reduced-motion|motion-reduce:|motion-safe:|useReducedMotion|reducedMotion", t):
                found_rm = True
                break
        if not found_rm:
            linter.issues.append({"file": "(项目)", "line": 0, "rule": "reduced-motion", "severity": "warn",
                                  "message": "项目中有动画/过渡，但全项目找不到 prefers-reduced-motion 适配。在全局样式加 reduced-motion 兜底（见 references/motion.md §10）",
                                  "snippet": ""})
    issues = [i for i in linter.issues if SEV_ORDER[i["severity"]] >= SEV_ORDER[args.min_severity]]
    issues.sort(key=lambda i: (i["file"], i["line"], -SEV_ORDER[i["severity"]]))
    counts = {s: sum(1 for i in issues if i["severity"] == s) for s in ("error", "warn", "info")}

    if args.format == "json":
        print(json.dumps({"primitives": linter.primitives, "counts": counts, "issues": issues}, ensure_ascii=False, indent=2))
    else:
        if linter.primitives:
            print("识别到的项目组件映射：" + ", ".join(f"<{k}>→{v}" for k, v in linter.primitives.items()))
        else:
            print("未识别到项目按钮/输入等组件（可在 ui-guard.config.json 的 primitives 中配置）")
        if linter.scroll_cls:
            print(f"项目滚动条类：.{linter.scroll_cls}")
        cur = None
        for i in issues:
            if i["file"] != cur:
                cur = i["file"]
                print(f"\n{cur}")
            print(f"  L{i['line']:<5} [{i['severity']}] {i['rule']}: {i['message']}")
            if i["snippet"]:
                print(f"         › {i['snippet']}")
        by_rule = defaultdict(int)
        for i in issues:
            by_rule[i["rule"]] += 1
        print(f"\n合计：error {counts['error']} / warn {counts['warn']} / info {counts['info']}")
        if by_rule:
            print("按规则：" + ", ".join(f"{k}×{v}" for k, v in sorted(by_rule.items(), key=lambda x: -x[1])))
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
