# 时间线（Timeline）

事件沿时间轴分布（里程碑、版本史、大事记）。

## 布局语法

- 默认**水平主轴**：ink 色 1.5px 横线居中贯穿，带右向箭头
- 刻度：主轴上 1px 短竖线 + 下方 mono 8px 日期标签
- 事件上下交错排布：刻度向上/下引出 24px 细线（rule 色），接事件卡片
- 事件卡片：白底 rx=6 框（宽 144-200px），内为 sans 12px 事件名 + muted 9-12px 一行说明
- 关键事件（≤2）：accent 描边 + 刻度点实心 accent 圆
- 普通刻度点：6px 纸底 ink 描边空心圆

## 画法

```svg
<line x1="40" y1="300" x2="960" y2="300" stroke="#1f2937" stroke-width="1.5" marker-end="url(#arrow)"/>
<circle cx="320" cy="300" r="6" fill="#ffffff" stroke="#1f2937"/>
<line x1="320" y1="294" x2="320" y2="252" stroke="rgba(31,41,55,0.14)"/>
<rect x="248" y="180" width="144" height="64" rx="6" fill="#fff" stroke="rgba(31,41,55,0.14)"/>
<text x="320" y="272" text-anchor="middle" font-size="8" font-family="ui-monospace,Menlo,monospace" fill="#5b6b80">2026-03</text>
```

## 预算

事件 ≤10、关键事件 ≤2、说明文字 ≤1 行。

## 反模式

- 事件全堆一侧（交错布局利用空间）
- 卡片宽度不一（同图统一宽）
- 时间间隔不均匀却不注明（非匀速轴必须在眉题或图例说明）
