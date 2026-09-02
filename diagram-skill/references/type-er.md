# ER 图（实体关系）

实体 + 字段 + 关系基数。

## 布局语法

- 实体 = 白底 rx=6 框，**顶部标题条**（ink 5% 填充）写实体名（sans 12px 600），下方便携字段列表
- 字段行：mono 9px，格式 `name: type`，主键加粗或前置 `PK`，外键前置 `FK`
- 关系线：实线 ink 60%，两端标注基数：`1`、`N`、`0..1`（mono 8px + 遮罩，贴近端点 8px 内）
- 布局：核心实体居中，关联实体环绕；避免关系线交叉（交换实体位置直到不交叉）
- 焦点实体（核心表）用 accent-tint + accent 描边，≤1-2 个

## 实体框画法

```svg
<rect x="X" y="Y" width="160" height="H" rx="6" fill="#fff" stroke="#1f2937"/>
<rect x="X" y="Y" width="160" height="24" rx="6" fill="rgba(31,41,55,0.05)"/>
<text x="X+80" y="Y+16" text-anchor="middle" font-size="12" font-weight="600" fill="#1f2937">orders</text>
<text x="X+12" y="Y+40" font-size="9" font-family="ui-monospace,Menlo,monospace" fill="#5b6b80">PK  id: bigint</text>
<text x="X+12" y="Y+56" font-size="9" font-family="ui-monospace,Menlo,monospace" fill="#5b6b80">FK  user_id: bigint</text>
```

字段行高 16px，框高 = 24 + 字段数 × 16 + 8，取 4 的倍数。每实体最多展示 8 个字段（多的用 `…` 收尾）。

## 预算

实体 ≤8、关系 ≤10、每实体字段 ≤8。

## 反模式

- 字段类型用中文（类型保持英文：bigint/varchar(64)）
- 关系线斜拉（ER 也必须正交或直线共轴）
- 不标基数
