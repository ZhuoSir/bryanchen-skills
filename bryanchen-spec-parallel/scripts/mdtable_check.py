#!/usr/bin/env python3
"""mdtable_check.py — markdown 表格语法闸（bryanchen-spec 配套，零依赖 python3）
用法: python3 mdtable_check.py <文件.md>...   退出码 0=全绿；非0=有缺陷（file:line: 问题）
检查: ①fence 配平（闭栏须无 info，GFM）②表行列数与表头一致 ③分隔行列数 ④行尾|
      ⑤表格不得紧跟正文段落（GFM 表格不能中断段落）
规则: 只校验「首行以|开、次行为分隔行」的块；单元格内 `code` 的 | 与 \\| 不计列。"""
import re, sys

def mask_inline(s):
    out, i = [], 0
    while i < len(s):
        j = s.find('`', i)
        if j < 0: out.append(s[i:].replace('\\|', '\x00')); break
        out.append(s[i:j].replace('\\|', '\x00'))
        k = s.find('`', j + 1)
        if k < 0: out.append(s[j:].replace('\\|', '\x00')); break
        out.append('\x01' * (k - j + 1)); i = k + 1
    return ''.join(out)

def cells(line):
    s = mask_inline(line.strip())
    if not s.startswith('|'): return None
    trailing = s.endswith('|')
    body = s[1:-1] if trailing else s[1:]
    return len(body.split('|')) + (0 if trailing else 1), trailing

def is_sep(line):
    s = line.strip()
    return bool(s) and s.startswith('|') and s.endswith('|') and set(s) <= set('|:-\\` \x01') and '-' in s

def check_file(path):
    errs = []
    try: lines = open(path, encoding='utf-8').read().split('\n')
    except Exception as e: return [f"{path}:1: 无法读取 {e}"]
    fence = None   # (mark, 行号)
    i = 0
    while i < len(lines):
        st = lines[i].lstrip()
        if st.startswith('```') or st.startswith('~~~'):
            mark = st[:3]; bare = st.rstrip() in ('```', '~~~')
            if fence is None: fence = (mark, i + 1)
            elif fence[0] == mark and bare: fence = None
            i += 1; continue
        if fence: i += 1; continue
        c = cells(lines[i])
        if c and i + 1 < len(lines) and is_sep(lines[i + 1]):
            header_n = c[0]
            sc = cells(lines[i + 1])
            if sc[0] != header_n: errs.append(f"{path}:{i+2}: 分隔行列数 {sc[0]} ≠ 表头 {header_n}")
            prev = lines[i - 1].strip() if i > 0 else ""
            if prev and not re.match(r'^#{1,6}\s|^[-*+]\s|^\d+[.)]\s|^>|^(\||```|~~~)', prev) and not prev.endswith(':'):
                errs.append(f"{path}:{i+1}: 表格紧跟正文段落（上方必须空行，否则整表不渲染）")
            j = i
            while j < len(lines):
                cc = cells(lines[j])
                if not cc: break
                n, tr = cc
                if n != header_n: errs.append(f"{path}:{j+1}: 列数 {n} ≠ 表头 {header_n}")
                if not tr: errs.append(f"{path}:{j+1}: 行尾缺 |（单元格含竖线须 \\| 或 `code`）")
                j += 1
            i = j; continue
        i += 1
    if fence: errs.append(f"{path}:{fence[1]}: ```/~~~ 未闭合（从这行起后续全部错乱）")
    return errs

if __name__ == "__main__":
    files = sys.argv[1:]
    if not files: print(__doc__); sys.exit(2)
    all_errs = [e for f in files for e in check_file(f)]
    for e in all_errs: print("✗", e)
    print(("✓ mdtable_check 全绿: %d 文件" % len(files)) if not all_errs else f"— 共 {len(all_errs)} 处问题")
    sys.exit(0 if not all_errs else 1)
