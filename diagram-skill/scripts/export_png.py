#!/usr/bin/env python3
"""diagram-skill PNG 导出：HTML 图表 → PNG（puppeteer headless-shell 截图）。

用法:
    python3 export_png.py diagram.html [-o out.png] [--bare] [--transparent] [--scale 2]

- --bare        只截 <svg> 区域（去标题/图例/页面留白）
- --transparent 透明背景（omitBackground，需 html 已按 references/export.md 做透明适配）
- --scale       缩放倍数（默认 2）

puppeteer 查找顺序：mermaid-cli 全局依赖 → 项目 node_modules → 全局 node_modules。
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

NODE_SCRIPT = """
const puppeteer = require(process.argv[2]);
(async () => {
  const cfg = JSON.parse(process.argv[3]);
  const browser = await puppeteer.launch({ headless: 'shell', args: ['--no-sandbox', '--disable-gpu'] });
  const page = await browser.newPage();
  await page.setViewport({ width: cfg.vw, height: cfg.vh, deviceScaleFactor: cfg.scale });
  await page.goto('file://' + cfg.input);
  await new Promise(r => setTimeout(r, 500));
  const opts = { path: cfg.output };
  if (cfg.transparent) opts.omitBackground = true;
  if (cfg.bare) {
    const svg = await page.$('svg');
    if (!svg) throw new Error('页面中没有 <svg> 元素');
    await svg.screenshot(opts);
  } else {
    await page.screenshot(opts);
  }
  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
"""

# puppeteer 候选位置
PUPPETEER_CANDIDATES = [
    "~/.nvm/versions/node/v22.16.0/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer",
    "/usr/local/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer",
    "/opt/homebrew/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer",
]


def find_puppeteer():
    for p in PUPPETEER_CANDIDATES:
        p = os.path.expanduser(p)
        if os.path.isdir(p):
            return p
    # 兜底：问 npm 全局根目录
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True,
                              timeout=10).stdout.strip()
        for sub in ("@mermaid-js/mermaid-cli/node_modules/puppeteer", "puppeteer"):
            p = os.path.join(root, sub)
            if os.path.isdir(p):
                return p
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="输入 HTML 文件")
    ap.add_argument("-o", "--output", default="", help="输出 PNG 路径（默认与输入同名）")
    ap.add_argument("--bare", action="store_true", help="只截 <svg> 区域（纯图）")
    ap.add_argument("--transparent", action="store_true", help="透明背景")
    ap.add_argument("--scale", type=float, default=2, help="缩放倍数（默认 2）")
    ap.add_argument("--viewport", default="1100x500", help="视口 WxH（默认 1100x500）")
    args = ap.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        print(f"输入不存在: {input_path}", file=sys.stderr)
        sys.exit(2)
    output = args.output or os.path.splitext(input_path)[0] + ".png"
    vw, vh = (int(x) for x in args.viewport.split("x"))

    puppeteer = find_puppeteer()
    if not puppeteer:
        print("未找到 puppeteer。安装方式：npm i -g @mermaid-js/mermaid-cli（自带），"
              "或 npm i puppeteer", file=sys.stderr)
        sys.exit(2)

    cfg = {"input": input_path, "output": os.path.abspath(output),
           "bare": args.bare, "transparent": args.transparent,
           "scale": args.scale, "vw": vw, "vh": vh}

    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False) as f:
        f.write(NODE_SCRIPT)
        script = f.name
    try:
        r = subprocess.run(["node", script, puppeteer, json.dumps(cfg)],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(f"截图失败: {r.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
    finally:
        os.unlink(script)

    print(json.dumps({"ok": True, "output": os.path.abspath(output),
                      "bare": args.bare, "transparent": args.transparent,
                      "scale": args.scale}, ensure_ascii=False))


if __name__ == "__main__":
    main()
