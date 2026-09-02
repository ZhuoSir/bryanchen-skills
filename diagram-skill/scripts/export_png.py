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

def find_puppeteer():
    """按平台查找 puppeteer：macOS nvm（任意 node 版本）→ linux/homebrew → Windows。"""
    cands = []
    # macOS/Linux nvm：通配所有 node 版本（不绑定具体版本号）
    nvm = os.path.expanduser("~/.nvm/versions/node")
    if os.path.isdir(nvm):
        for ver in sorted(os.listdir(nvm), reverse=True):
            cands.append(os.path.join(
                nvm, ver, "lib", "node_modules", "@mermaid-js", "mermaid-cli",
                "node_modules", "puppeteer"))
    cands += [
        os.path.join("/", "usr", "local", "lib", "node_modules", "@mermaid-js",
                     "mermaid-cli", "node_modules", "puppeteer"),
        os.path.join("/", "opt", "homebrew", "lib", "node_modules", "@mermaid-js",
                     "mermaid-cli", "node_modules", "puppeteer"),
    ]
    # Windows 候选：nvm4w（NVM_SYMLINK/NVM_HOME）与全局 npm 目录（APPDATA）
    for env in ("NVM_SYMLINK", "NVM_HOME"):
        base = os.environ.get(env)
        if base:
            cands.append(os.path.join(
                base, "node_modules", "@mermaid-js", "mermaid-cli",
                "node_modules", "puppeteer"))
    appdata = os.environ.get("APPDATA")
    if appdata:
        cands.append(os.path.join(appdata, "npm", "node_modules", "@mermaid-js",
                                  "mermaid-cli", "node_modules", "puppeteer"))
        cands.append(os.path.join(appdata, "npm", "node_modules", "puppeteer"))
    cands.append(os.path.join("C:\\", "nvm4w", "nodejs", "node_modules", "@mermaid-js",
                              "mermaid-cli", "node_modules", "puppeteer"))

    for p in cands:
        if os.path.isdir(p):
            return p
    # 兜底：问 npm 全局根目录（Windows 上是 npm.cmd，shell=False 时 "npm" 会 FileNotFoundError）
    npm = "npm.cmd" if os.name == "nt" else "npm"
    try:
        root = subprocess.run([npm, "root", "-g"], capture_output=True, text=True,
                              timeout=10).stdout.strip()
        for sub in (os.path.join("@mermaid-js", "mermaid-cli", "node_modules", "puppeteer"),
                    "puppeteer"):
            p = os.path.join(root, sub)
            if os.path.isdir(p):
                return p
    except Exception:
        pass
    return None


def render_with_resvg(input_path, output, scale):
    """降级路径：无浏览器/沙箱环境用 resvg-js 进程内渲染（scripts/render_svg.js）。

    等价于 --bare --transparent（只渲染 svg 本体、透明底）。
    返回 True 表示成功。"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_svg.js")
    if not os.path.exists(script):
        return False
    node = "node.exe" if os.name == "nt" else "node"
    try:
        r = subprocess.run([node, script, input_path, "-o", output, "--scale", str(scale)],
                           capture_output=True, text=True, timeout=120)
        return r.returncode == 0
    except Exception:
        return False


def main():
    # Windows 中文控制台（GBK）下打印 emoji/中文会 UnicodeEncodeError，强制 UTF-8
    _rc = getattr(sys.stdout, "reconfigure", None)
    if _rc:
        _rc(encoding="utf-8", errors="replace")

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
        # 降级 1：无浏览器环境（沙箱/精简系统）走 resvg-js 进程内渲染
        if render_with_resvg(input_path, output, args.scale):
            print(json.dumps({"ok": True, "output": os.path.abspath(output),
                              "engine": "resvg", "bare": True, "transparent": True,
                              "scale": args.scale,
                              "note": "puppeteer 不可用，已降级 resvg（等价 --bare --transparent）"},
                             ensure_ascii=False))
            return
        print("未找到 puppeteer，且 resvg 降级不可用（scripts/render_svg.js 需先 npm install）。"
              "安装方式：npm i -g @mermaid-js/mermaid-cli（自带 puppeteer）", file=sys.stderr)
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
            # 降级 2：puppeteer 存在但启动失败（沙箱禁止命名管道等）→ resvg
            if render_with_resvg(input_path, output, args.scale):
                print(json.dumps({"ok": True, "output": os.path.abspath(output),
                                  "engine": "resvg", "bare": True, "transparent": True,
                                  "scale": args.scale,
                                  "note": f"puppeteer 启动失败（{r.stderr.strip()[:80]}），已降级 resvg（等价 --bare --transparent）"},
                                 ensure_ascii=False))
                return
            print(f"截图失败: {r.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
    finally:
        os.unlink(script)

    print(json.dumps({"ok": True, "output": os.path.abspath(output),
                      "engine": "puppeteer",
                      "bare": args.bare, "transparent": args.transparent,
                      "scale": args.scale}, ensure_ascii=False))


if __name__ == "__main__":
    main()
