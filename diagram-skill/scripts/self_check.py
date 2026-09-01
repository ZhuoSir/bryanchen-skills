#!/usr/bin/env python3
"""diagram-skill 输出自检：交付前必须通过。

    python3 scripts/self_check.py <diagram.html>

检查项（零第三方依赖）：
1. 可访问性契约：svg role="img"、aria-labelledby 指向真实存在的 <title>/<desc>、
   title 是 svg 第一个子元素、id 带 slug 前缀（禁止裸 title/desc）
2. 单文件安全：无 <script>、无事件属性(on*)、无外部资源引用（http/https 链接一律禁止，
   字体用系统栈）、无 <iframe>/<object>/<embed>
3. 网格纪律：font-size、x/y/width/height 属性值应为 4 的倍数（违规仅警告）
"""
import re
import sys
from html.parser import HTMLParser


class Checker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.errors = []
        self.warnings = []
        self.svg_count = 0
        self._svg_depth = 0
        self._in_svg = False
        self._first_svg_child = True
        self.svg_ids = set()
        self.svg_labelledby = None
        self.has_role_img = False
        self.title_seen = False
        self.desc_seen = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        # 安全检查：全文档
        for k in a:
            if k.lower().startswith("on"):
                self.errors.append(f"事件属性 on* 禁止: <{tag} {k}>")
        for k in ("src", "href", "xlink:href", "srcset"):
            v = a.get(k, "")
            if isinstance(v, str) and re.match(r"https?://", v.strip()):
                self.errors.append(f"外部资源禁止: <{tag} {k}={v[:60]}>（字体用系统栈，禁止外链）")
        if tag in ("script", "iframe", "object", "embed", "form"):
            self.errors.append(f"禁止标签: <{tag}>")

        if tag == "svg":
            self.svg_count += 1
            self._svg_depth += 1
            if self._svg_depth == 1:
                self._in_svg = True
                self._first_svg_child = True
                if a.get("role") == "img":
                    self.has_role_img = True
                self.svg_labelledby = a.get("aria-labelledby", "")
            return

        if self._in_svg and self._svg_depth >= 1:
            if "id" in a:
                self.svg_ids.add(a["id"])
            if self._svg_depth == 1 and self._first_svg_child:
                self._first_svg_child = False
                if tag != "title":
                    self.errors.append(f"<title> 必须是 <svg> 第一个子元素，实际先是 <{tag}>")
            if tag == "title" and self._svg_depth == 1:
                self.title_seen = True
                if a.get("id", "") in ("title", ""):
                    self.errors.append("<title> 的 id 禁止为空或裸 'title'，需带 slug 前缀")
            if tag == "desc" and self._svg_depth == 1:
                self.desc_seen = True
                if a.get("id", "") in ("desc", ""):
                    self.errors.append("<desc> 的 id 禁止为空或裸 'desc'，需带 slug 前缀")
            # 4px 网格纪律（警告级）：只查几何元素坐标与尺寸；文本基线 y 由盒中心推导，不强制
            if tag in ("rect", "line", "circle", "ellipse"):
                for k in ("x", "y", "width", "height", "x1", "x2", "y1", "y2", "cx", "cy", "r"):
                    v = a.get(k)
                    if v and re.match(r"^-?\d+(\.\d+)?$", v):
                        n = float(v)
                        if abs(n) > 4 and n % 4 != 0:
                            self.warnings.append(f"<{tag} {k}={v}> 不是 4 的倍数")
            # 字号白名单（9 仅限等宽技术标签）
            v = a.get("font-size")
            if v and re.match(r"^\d+(\.\d+)?$", v) and float(v) not in (8, 9, 12, 16, 20, 24, 28, 32, 40):
                self.warnings.append(f"<{tag} font-size={v}> 不在字号梯度 {{8,9,12,16,20,24,28,32,40}}")
        if tag == "svg":
            pass  # depth handled above

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag == "svg":
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "svg" and self._svg_depth > 0:
            self._svg_depth -= 1
            if self._svg_depth == 0:
                self._in_svg = False

    def finalize(self):
        if self.svg_count == 0:
            self.errors.append("没有 <svg> 元素")
        elif self.svg_count > 1:
            self.errors.append(f"发现 {self.svg_count} 个 <svg>，每张图应只有一个")
        if self.svg_count >= 1:
            if not self.has_role_img:
                self.errors.append('<svg> 缺 role="img"')
            if not self.title_seen:
                self.errors.append("缺 <title>（且必须是 svg 第一个子元素）")
            if not self.desc_seen:
                self.errors.append("缺 <desc>")
            if self.svg_labelledby:
                for ref in self.svg_labelledby.split():
                    if ref not in self.svg_ids:
                        self.errors.append(f"aria-labelledby 引用的 id 不存在: {ref}")
            else:
                self.errors.append("<svg> 缺 aria-labelledby")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    path = sys.argv[1]
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        print(f"读取失败: {e}")
        sys.exit(2)

    c = Checker()
    c.feed(text)
    c.finalize()

    # 去重告警
    seen = set()
    warnings = []
    for w in c.warnings:
        if w not in seen:
            seen.add(w)
            warnings.append(w)

    for e in c.errors:
        print(f"❌ {e}")
    for w in warnings[:10]:
        print(f"⚠️  {w}")
    if len(warnings) > 10:
        print(f"⚠️  …另有 {len(warnings) - 10} 条网格警告")

    if c.errors:
        print(f"\n自检未通过：{len(c.errors)} 个错误，{len(warnings)} 个警告")
        sys.exit(1)
    print(f"✅ 自检通过（{len(warnings)} 个网格警告）")


if __name__ == "__main__":
    main()
