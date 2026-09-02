#!/usr/bin/env node
/**
 * diagram-skill 降级渲染：@resvg/resvg-js 进程内光栅化（零子进程、无浏览器）。
 *
 * 何时用：沙箱/精简环境禁止 puppeteer 开浏览器（EPERM 命名管道等）时的降级路径；
 * export_png.py 在 puppeteer 缺失或启动失败时会自动降级到本脚本。
 *
 * 用法:
 *   node render_svg.js <input.html|input.svg> [-o out.png] [--scale 2]
 *
 * 行为：提取内联 <svg> 本体渲染（等价 export_png.py 的 --bare --transparent）；
 * 注意 resvg 无 CSS 布局——svg 根必须有数值 width/height，缺失时从 viewBox 自动补齐。
 *
 * 依赖：cd scripts && npm install（@resvg/resvg-js，见 package.json）
 */
const fs = require('fs');
const path = require('path');

let Resvg;
try {
  Resvg = require('@resvg/resvg-js').Resvg;
} catch {
  console.error('缺少依赖 @resvg/resvg-js：请在本目录（scripts/）执行 npm install');
  process.exit(2);
}

const args = process.argv.slice(2);
if (args.length < 1) {
  console.error('用法: node render_svg.js <input.html|svg> [-o out.png] [--scale 2]');
  process.exit(2);
}
const input = path.resolve(args[0]);
let output = input.replace(/\.(html?|svg)$/i, '') + '.png';
let scale = 2;
for (let i = 1; i < args.length; i++) {
  if (args[i] === '-o') output = args[++i];
  else if (args[i] === '--scale') scale = parseFloat(args[++i]);
}

let src = fs.readFileSync(input, 'utf8');
const m = src.match(/<svg[\s\S]*?<\/svg>/);
if (!m) {
  console.error('输入中没有 <svg> 元素');
  process.exit(2);
}
let svg = m[0];

// resvg 无 CSS 布局：svg 根必须带数值 width/height，缺则从 viewBox 推导
if (!/<svg[^>]*\swidth="[\d.]+/.test(svg)) {
  const vb = svg.match(/viewBox="([\d.\s-]+)"/);
  if (!vb) {
    console.error('svg 缺 width/height 且无 viewBox，无法确定渲染尺寸');
    process.exit(2);
  }
  const parts = vb[1].trim().split(/\s+/).map(Number);
  svg = svg.replace('<svg', `<svg width="${parts[2]}" height="${parts[3]}"`);
}

const resvg = new Resvg(svg, {
  fitTo: { mode: 'zoom', value: scale },
  background: 'rgba(0,0,0,0)',          // 透明底
  font: { loadSystemFonts: true },       // 加载系统中文字体
});
fs.writeFileSync(output, resvg.render().asPng());
console.log(JSON.stringify({ ok: true, output: path.resolve(output), engine: 'resvg', scale }));
