# 时序图（Sequence）

角色之间按时间顺序传递的消息。

## 布局语法

- 顶部一排参与者框（白底 rx=6，sans 12px 名字），框下引出**生命线**（竖直虚线 `4,4`，soft 色）直到底部
- 生命线间距 ≥140px；参与者 ≤5
- 消息 = 水平实线箭头（同步）/ 虚线箭头（异步/返回），从上到下按时间排列，消息间距 ≥36px
- 消息标注直接写在箭头上方 6-10px，mono 8px + 遮罩
- **激活条**：参与者处理期间，生命线上叠一个 8px 宽白底 ink 描边竖条
- 自调用：从生命线出去向右绕一个小 U 形回到同一条线

## 片段框（可选，≤1 个）

`alt`/`opt`/`loop` 用 ink 30% 描边大框圈住相关消息，左上角小标签块写 `LOOP [条件]`（mono 8px，ink 填充白字小旗形）。

## 写法

```svg
<line x1="120" y1="80" x2="120" y2="560" stroke="#8a919c" stroke-width="1" stroke-dasharray="4,4"/>
<line x1="120" y1="160" x2="388" y2="160" stroke="#5c6470" stroke-width="1.2" marker-end="url(#arrow)"/>
<rect x="180" y="140" width="120" height="12" rx="2" fill="#f7f5f2"/>
<text x="240" y="149" text-anchor="middle" font-size="8" font-family="ui-monospace,Menlo,monospace" fill="#5c6470">POST /orders</text>
```

## 预算

生命线 ≤5、消息 ≤12、片段框 ≤1（嵌套 ≤1）。

## 反模式

- 返回消息没有画成虚线
- 所有消息标注同一侧导致重叠——标注统一在线上方
- 生命线间距不等（视觉噪音）
