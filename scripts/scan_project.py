#!/usr/bin/env python3
"""
scan_project.py —— 盘点前端项目中"已经有什么"，生成给 AI 读的清单。

输出内容：
  - 技术栈识别（框架、样式方案、组件库）
  - 组件清单（按类别：按钮/输入/弹窗/表格/滚动/布局……），并标出 legacy 组件
  - 设计令牌：CSS 自定义属性、Tailwind 主题扩展
  - 全局 CSS 类（如 .app-scrollbar、.btn-primary）
  - 当前代码中实际使用的 z-index、硬编码颜色、任意值的统计（用于发现"事实上的规范"和漂移）

用法：
  python3 scan_project.py --root . [--out .ui-guard/inventory.md] [--config ui-guard.config.json]

只使用 Python 标准库。
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

CODE_EXT = {".tsx", ".jsx", ".ts", ".js", ".vue", ".svelte", ".html"}
STYLE_EXT = {".css", ".scss", ".sass", ".less", ".pcss"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", "out", "coverage",
             ".turbo", ".cache", ".ui-guard", "public", "vendor", ".output", ".svelte-kit"}

CATEGORIES = [
    ("按钮", r"button|btn"),
    ("输入/表单", r"input|textarea|field|form|checkbox|radio|switch|toggle|datepicker|upload"),
    ("选择/下拉", r"select|dropdown|combobox|autocomplete|menu|popover|cascader"),
    ("弹窗/抽屉", r"modal|dialog|drawer|sheet|popup|confirm"),
    ("提示/反馈", r"toast|notif|alert|message|tooltip|badge|tag|chip|empty|skeleton|spin|loading|progress"),
    ("表格/列表", r"table|grid|list|pagination|pager|datatable"),
    ("滚动", r"scroll"),
    ("布局/容器", r"layout|page|container|card|panel|section|header|sidebar|nav|tabs?|stack|flex|box|row|col"),
    ("图标/媒体", r"icon|avatar|image|img"),
]

DEFAULT_CONFIG = {
    "srcDirs": ["src"],
    "componentDirs": [],
    "primitiveDirs": [],
    "legacyDirs": [],
}


def load_config(root, path):
    cfg = dict(DEFAULT_CONFIG)
    p = path or os.path.join(root, "ui-guard.config.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:  # noqa
            print(f"[warn] 读取配置失败 {p}: {e}", file=sys.stderr)
    return cfg


def walk(root, dirs):
    seen = set()
    bases = [os.path.join(root, d) for d in dirs if os.path.isdir(os.path.join(root, d))] or [root]
    for base in bases:
        for dp, dns, fns in os.walk(base):
            dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in fns:
                fp = os.path.join(dp, fn)
                if fp in seen:
                    continue
                seen.add(fp)
                yield fp


def read(fp):
    try:
        with open(fp, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def rel(root, fp):
    return os.path.relpath(fp, root).replace(os.sep, "/")


def detect_stack(root):
    info = {"framework": [], "styling": [], "ui_libs": []}
    pkg_path = os.path.join(root, "package.json")
    deps = {}
    if os.path.exists(pkg_path):
        try:
            pkg = json.load(open(pkg_path, encoding="utf-8"))
            deps.update(pkg.get("dependencies", {}))
            deps.update(pkg.get("devDependencies", {}))
        except Exception:
            pass
    def has(*names):
        return any(n in deps for n in names)
    if has("next"): info["framework"].append("Next.js")
    if has("react"): info["framework"].append("React")
    if has("vue"): info["framework"].append("Vue")
    if has("nuxt"): info["framework"].append("Nuxt")
    if has("svelte"): info["framework"].append("Svelte")
    if has("tailwindcss"): info["styling"].append(f"Tailwind {deps.get('tailwindcss')}")
    if has("styled-components"): info["styling"].append("styled-components")
    if has("@emotion/react", "@emotion/styled"): info["styling"].append("Emotion")
    if has("sass"): info["styling"].append("SCSS")
    if has("less"): info["styling"].append("Less")
    for lib, name in [("antd", "Ant Design"), ("element-plus", "Element Plus"), ("@mui/material", "MUI"),
                      ("@chakra-ui/react", "Chakra UI"), ("naive-ui", "Naive UI"), ("@arco-design/web-react", "Arco"),
                      ("@arco-design/web-vue", "Arco Vue"), ("vant", "Vant"), ("@headlessui/react", "Headless UI"),
                      ("@mantine/core", "Mantine"), ("tdesign-vue-next", "TDesign"), ("tdesign-react", "TDesign")]:
        if has(lib):
            info["ui_libs"].append(name)
    if any(k.startswith("@radix-ui/") for k in deps):
        info["ui_libs"].append("Radix UI（可能是 shadcn/ui）")
    if os.path.exists(os.path.join(root, "components.json")):
        info["ui_libs"].append("shadcn/ui（components.json）")
    return info, deps


EXPORT_RES = [
    re.compile(r"export\s+(?:default\s+)?(?:function|const|class)\s+([A-Z][A-Za-z0-9_]*)"),
    re.compile(r"export\s*\{([^}]+)\}"),
]


def component_names(fp, text):
    names = set()
    ext = os.path.splitext(fp)[1]
    if ext in (".vue", ".svelte"):
        base = os.path.splitext(os.path.basename(fp))[0]
        if base.lower() == "index":
            base = os.path.basename(os.path.dirname(fp))
        names.add(base[:1].upper() + base[1:])
        return names
    for m in EXPORT_RES[0].finditer(text):
        names.add(m.group(1))
    for m in EXPORT_RES[1].finditer(text):
        for part in m.group(1).split(","):
            part = part.strip().split(" as ")[-1].strip()
            if part[:1].isupper():
                names.add(part)
    return names


def variants_hint(text):
    # 抓取 variant/size 的可选值，帮助 AI 知道怎么用
    hints = []
    for key in ("variant", "size", "type", "color", "intent"):
        m = re.search(key + r"\??\s*:\s*((?:['\"][\w-]+['\"]\s*\|?\s*)+)", text)
        if m:
            vals = re.findall(r"['\"]([\w-]+)['\"]", m.group(1))
            if vals:
                hints.append(f"{key}: {'/'.join(vals[:8])}")
        m2 = re.search(key + r"s?\s*:\s*\{([^{}]{0,400})\}", text)
        if m2 and not any(h.startswith(key + ":") for h in hints):
            vals = re.findall(r"^\s*['\"]?([\w-]+)['\"]?\s*:", m2.group(1), re.M)
            if 1 < len(vals) <= 12:
                hints.append(f"{key}: {'/'.join(vals)}")
    return "; ".join(hints)


def categorize(name, path):
    s = (name + " " + path).lower()
    for cat, pat in CATEGORIES:
        if re.search(pat, s):
            return cat
    return "其他"


CSS_VAR_DEF = re.compile(r"(--[\w-]+)\s*:\s*([^;}{]+)[;}]")
CSS_CLASS_DEF = re.compile(r"(?:^|[\s,}])\.([a-zA-Z][\w-]*)(?=[\s,{:.>\[])")
HEX = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
RGB = re.compile(r"\b(?:rgba?|hsla?)\(\s*\d")
ZIDX = re.compile(r"z-index\s*:\s*(-?\d+)|\bz-(\d+)\b|\bz-\[(-?\d+)\]|zIndex\s*:\s*(-?\d+)")
ARBITRARY = re.compile(r"\b(?:p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|gap|gap-x|gap-y|w|h|min-w|min-h|max-w|max-h|top|left|right|bottom|text|leading|rounded|space-x|space-y)-\[[^\]]+\]")
PX_VALUE = re.compile(r"\b(margin|padding|gap)(?:-(?:top|bottom|left|right|inline|block))?\s*:\s*([^;]+);")
FONT_SIZE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px|\btext-\[(\d+)px\]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=None, help="输出 markdown 路径（默认打印到 stdout）")
    ap.add_argument("--config", default=None)
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    cfg = load_config(root, args.config)

    stack, deps = detect_stack(root)
    legacy_dirs = [d.strip("/") for d in cfg.get("legacyDirs", [])]
    legacy_re = re.compile(r"(^|/)(legacy|deprecated|old|_old|bak|_bak|backup)(/|$)", re.I)

    components = defaultdict(list)   # cat -> [(name, path, hint, legacy)]
    css_vars = {}
    css_classes = Counter()
    global_class_files = defaultdict(set)
    z_counter = Counter()
    hex_counter = Counter()
    rgb_count = 0
    arbitrary_counter = Counter()
    spacing_counter = Counter()
    font_counter = Counter()
    raw_tag_counter = Counter()
    scroll_css = []

    comp_dirs = cfg.get("componentDirs") or []
    all_files = list(walk(root, cfg.get("srcDirs") or ["src"]))
    # 额外扫描根目录下的 tailwind 配置和全局样式
    for extra in ("tailwind.config.js", "tailwind.config.ts", "tailwind.config.cjs", "tailwind.config.mjs"):
        p = os.path.join(root, extra)
        if os.path.exists(p):
            all_files.append(p)

    tw_theme = []
    for fp in all_files:
        r = rel(root, fp)
        ext = os.path.splitext(fp)[1]
        text = read(fp)
        if not text:
            continue
        is_legacy = bool(legacy_re.search(r)) or any(r.startswith(d + "/") for d in legacy_dirs)

        if os.path.basename(fp).startswith("tailwind.config"):
            m = re.search(r"extend\s*:\s*\{(.{0,4000})", text, re.S)
            keys = re.findall(r"^\s{4,8}(colors|spacing|borderRadius|fontSize|zIndex|boxShadow|fontFamily)\s*:", text, re.M)
            tw_theme.append((r, sorted(set(keys))))
            continue

        if ext in STYLE_EXT or ext in (".vue", ".svelte"):
            for m in CSS_VAR_DEF.finditer(text):
                name, val = m.group(1), m.group(2).strip()
                if name not in css_vars:
                    css_vars[name] = (val[:60], r)
            # @theme (Tailwind v4)
            if "@theme" in text:
                tw_theme.append((r, ["@theme (Tailwind v4)"]))
            if ext in STYLE_EXT:
                for m in CSS_CLASS_DEF.finditer(text):
                    css_classes[m.group(1)] += 1
                    global_class_files[m.group(1)].add(r)
            if "scrollbar" in text:
                for m in re.finditer(r"([^{}\n]*scrollbar[^{}\n]*)\{", text):
                    scroll_css.append((m.group(1).strip()[:80], r))

        if ext in CODE_EXT or ext in STYLE_EXT:
            for m in ZIDX.finditer(text):
                v = next(g for g in m.groups() if g is not None)
                z_counter[int(v)] += 1
            if not any(tf in r for tf in cfg.get("tokenFiles", [])) and "token" not in r.lower() and "theme" not in r.lower():
                for m in HEX.finditer(text):
                    hex_counter[m.group(0).lower()] += 1
                rgb_count += len(RGB.findall(text))
            for m in ARBITRARY.finditer(text):
                arbitrary_counter[m.group(0)] += 1
            for m in PX_VALUE.finditer(text):
                for px in re.findall(r"(-?\d+(?:\.\d+)?)px", m.group(2)):
                    spacing_counter[float(px)] += 1
            for m in FONT_SIZE.finditer(text):
                v = m.group(1) or m.group(2)
                font_counter[float(v)] += 1

        if ext in CODE_EXT:
            for tag in ("button", "input", "select", "textarea", "table", "dialog"):
                raw_tag_counter[tag] += len(re.findall(r"<" + tag + r"[\s>/]", text))
            in_comp_dir = (not comp_dirs and re.search(r"(^|/)(components?|ui|widgets)(/|$)", r, re.I)) or \
                          any(r.startswith(d.strip("/") + "/") for d in comp_dirs)
            if in_comp_dir and ext in (".tsx", ".jsx", ".vue", ".svelte", ".ts", ".js"):
                for name in sorted(component_names(fp, text)):
                    if name.endswith(("Props", "Context", "Provider", "Type", "Types")) and ext in (".ts", ".tsx"):
                        continue
                    components[categorize(name, r)].append((name, r, variants_hint(text), is_legacy))

    out = []
    w = out.append
    w("# 前端项目 UI 盘点清单")
    w("")
    w("> 由 frontend-ui-guard/scripts/scan_project.py 生成。写 UI 前先在这里找现成的组件、令牌和全局类。")
    w("")
    w("## 技术栈")
    w(f"- 框架：{', '.join(stack['framework']) or '未识别'}")
    w(f"- 样式：{', '.join(stack['styling']) or '未识别（可能是纯 CSS / CSS Modules）'}")
    w(f"- 组件库：{', '.join(stack['ui_libs']) or '未识别第三方组件库'}")
    for r, keys in tw_theme:
        w(f"- Tailwind 主题：{r} → {', '.join(keys) or '（未发现 extend）'}")
    w("")

    w("## 组件清单")
    total = sum(len(v) for v in components.values())
    if not total:
        w("_没有在组件目录中发现导出的组件。检查 ui-guard.config.json 的 componentDirs。_")
    order = [c for c, _ in CATEGORIES] + ["其他"]
    for cat in order:
        items = components.get(cat)
        if not items:
            continue
        w(f"### {cat}")
        for name, r, hint, legacy in sorted(items, key=lambda x: (x[3], x[0])):
            flag = " ⚠️ LEGACY，不要引用" if legacy else ""
            h = f" — {hint}" if hint else ""
            w(f"- `{name}` ({r}){h}{flag}")
        w("")

    w("## 设计令牌（CSS 自定义属性）")
    if css_vars:
        groups = defaultdict(list)
        for name, (val, r) in css_vars.items():
            key = name.split("-")[2] if name.count("-") >= 2 else "misc"
            groups[key].append((name, val, r))
        for g in sorted(groups, key=lambda k: -len(groups[k])):
            items = groups[g]
            w(f"- **{g}**（{len(items)}）：" + ", ".join(f"`{n}`={v}" for n, v, _ in items[:12]) + (" …" if len(items) > 12 else ""))
    else:
        w("_未发现 CSS 自定义属性。颜色和间距可能写死在各处，建议建立令牌。_")
    w("")

    w("## 全局样式类（在样式文件中定义，业务代码应优先使用）")
    interesting = [c for c in css_classes if re.search(r"btn|button|scroll|card|input|form|tag|badge|container|page|layout|table|modal|shadow|text-|title|link|divider|empty", c, re.I)]
    if interesting:
        for c in sorted(interesting)[:80]:
            w(f"- `.{c}` ({', '.join(sorted(global_class_files[c]))[:120]})")
    else:
        w("_无明显的全局组件类。_")
    w("")

    w("## 滚动条样式")
    if scroll_css:
        for sel, r in scroll_css[:15]:
            w(f"- `{sel}` ({r})")
        w("- 可滚动容器应使用上面定义的类，不要让浏览器显示原生滚动条或每处重写。")
    else:
        w("_未发现自定义滚动条样式。_")
    w("")

    w("## 现状统计（用于发现漂移）")
    if z_counter:
        w(f"- z-index 使用值：" + ", ".join(f"{k}×{v}" for k, v in sorted(z_counter.items())))
        big = [k for k in z_counter if k >= 1000]
        if big:
            w(f"  - ⚠️ 存在超大 z-index：{sorted(big)}，说明层级缺少统一规划")
    if hex_counter:
        w(f"- 业务代码中硬编码颜色 {sum(hex_counter.values())} 处，{len(hex_counter)} 种；最常见：" +
          ", ".join(f"{k}×{v}" for k, v in hex_counter.most_common(10)))
    if rgb_count:
        w(f"- rgb()/hsl() 字面量 {rgb_count} 处")
    if arbitrary_counter:
        w(f"- Tailwind 任意值 {sum(arbitrary_counter.values())} 处；最常见：" +
          ", ".join(f"`{k}`×{v}" for k, v in arbitrary_counter.most_common(10)))
    if spacing_counter:
        w("- margin/padding/gap 的 px 值分布（前 15）：" +
          ", ".join(f"{int(k) if k.is_integer() else k}×{v}" for k, v in spacing_counter.most_common(15)))
    if font_counter:
        w(f"- font-size px 值：{len(font_counter)} 种 → " +
          ", ".join(f"{int(k) if k.is_integer() else k}×{v}" for k, v in sorted(font_counter.items())))
    if raw_tag_counter:
        w("- 原生标签出现次数：" + ", ".join(f"<{k}>×{v}" for k, v in raw_tag_counter.items() if v))
    w("")
    w("## 给 AI 的提示")
    w("- 需要按钮/输入/弹窗/表格/滚动区域时，先从上面的组件清单和全局类中选；找不到再 grep 一次。")
    w("- 颜色和间距只用令牌；上面\"现状统计\"里最常见的值可以作为归纳令牌的依据。")
    w("- 标记 LEGACY 的组件不要引用。")

    md = "\n".join(out) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"已写入 {args.out}（组件 {total} 个，令牌 {len(css_vars)} 个）")
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
