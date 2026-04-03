# ICON_GUIDELINE_V1

> 项目：EmbeddedGUI Designer  
> 版本：v1（2026-04-02）  
> 适用范围：桌面端 UI（Toolbar / Navigation / Canvas / Inspector / Status）

---

## 1. 目标与原则

### 1.1 目标
- 建立统一、可扩展、可替换的图标系统。
- 消除“图标风格混搭、语义冲突、状态不全”的问题。
- 支持亮/暗主题与高频交互场景的一致体验。

### 1.2 核心原则
1. 单一主图标风格（禁止混搭）。
2. 同语义全局唯一图标。
3. 图标语义优先于装饰性。
4. 所有使用必须走 `Icon` 组件，不直接散落引用文件路径。

---

## 2. 风格规范

### 2.1 主风格
- 风格：线性（Outlined）
- 端点：Rounded
- 推荐线宽：`1.75`（可按最终渲染效果在 `1.5~2.0` 微调）

### 2.2 禁止项
- 禁止同屏混用线性和面性图标作为同层级功能。
- 禁止不同供应源图标在“同一语义”下混用。
- 禁止“看起来差不多就行”的临时替代，必须走语义映射。

---

## 3. 尺寸与布局规范

### 3.1 尺寸梯度
- `16`：列表/表格/辅助说明
- `18`：默认（属性面板、普通按钮）
- `20`：Toolbar 主操作
- `24`：强调入口（严格控制数量）

### 3.2 热区（点击区域）
- 最小热区：`28x28`
- 推荐热区：`32x32`

### 3.3 间距
- 图标与文本间距：`8`
- 图标与容器边界最小内边距：`6`

### 3.4 对齐
- 图标必须做像素网格对齐。
- 图标与文本采用基线对齐，并做光学微调，避免“数学居中但视觉偏移”。

---

## 4. 颜色与主题规范（Token 驱动）

### 4.1 颜色 Token
- `icon.default`
- `icon.muted`
- `icon.active`
- `icon.disabled`
- `icon.success`
- `icon.warn`
- `icon.error`
- `icon.info`

### 4.2 使用规则
- 普通功能图标默认使用 `icon.default`。
- 弱化信息使用 `icon.muted`。
- 激活态使用 `icon.active`（或搭配激活背景）。
- 状态图标（成功/警告/错误/信息）才允许使用状态色。
- 禁止硬编码十六进制颜色。

---

## 5. 状态规范

每个可交互图标必须定义：
- `default`
- `hover`
- `active`（或 `pressed`）
- `disabled`
- 可选：`selected`

### 5.1 状态行为建议
- `hover`：亮度/对比轻微提升，不改变语义色。
- `active`：切换到 `icon.active` 或激活容器背景。
- `disabled`：降低对比，取消交互反馈。

---

## 6. 语义映射规范

### 6.1 同语义唯一
例如：
- “删除”全局固定 1 个图标。
- “设置”区分“项目设置”和“全局设置”语义，不可混同。

### 6.2 成套动作一致
- 对齐（左/中/右、上/中/下）必须来自同一骨架。
- 分布（水平/垂直）必须成对一致。
- 展开/收起方向统一（右=收起态，下=展开态）。

---

## 7. 命名规范

### 7.1 文件与标识命名格式
`ic_{domain}_{action|object}_{size}_{style}`

### 7.2 示例
- `ic_toolbar_save_20_rounded`
- `ic_nav_page_20_rounded`
- `ic_layout_align_left_18_rounded`
- `ic_state_error_16_rounded`

### 7.3 domain 建议枚举
- `toolbar`
- `nav`
- `edit`
- `layout`
- `style`
- `state`
- `resource`
- `device`

---

## 8. 资产导出规范（SVG）

### 8.1 格式
- 仅允许：`SVG`
- 不再新增字体图标（font icon）

### 8.2 导出约束
- 画板尺寸必须与图标尺寸一致（16/18/20/24）
- 清理无用 `group/transform/metadata`
- 默认 `fill="none"`（状态/面性图标另行定义）
- 线宽统一，端点与转角风格统一

### 8.3 目录结构建议
- `ui_designer/assets/icons/16/`
- `ui_designer/assets/icons/18/`
- `ui_designer/assets/icons/20/`
- `ui_designer/assets/icons/24/`
- `ui_designer/docs/icons.manifest.json`

---

## 9. 组件接入规范

### 9.1 强制入口
统一使用 `Icon` 组件：
- 输入：`name`, `size`, `state`, `semantic`
- 输出：渲染对应 SVG + 应用 token 色值 + 状态样式

### 9.2 禁止项
- 禁止页面内直接写图标路径。
- 禁止绕过 manifest 直接塞入临时图标。

---

## 10. 质量门禁（PR 必检）

### 10.1 必检项
- [ ] 新增图标是否已登记 manifest
- [ ] 是否存在同语义重复图标
- [ ] 状态是否齐全（default/hover/active/disabled）
- [ ] 是否使用 token 颜色（无硬编码）
- [ ] 亮/暗主题截图是否通过

### 10.2 量化目标
- 图标统一率 >= 98%
- 语义冲突数 = 0
- 硬编码颜色 = 0

---

## 11. 版本管理

- 本规范版本：`v1`
- 变更流程：
  1. 提交变更动机（问题/收益/影响面）
  2. 评审通过后升级版本（v1 -> v1.1 / v2）
  3. 同步更新 manifest 与替换清单

---

## 12. 配套文件

- 替换清单：`ui_designer/docs/ICON_REPLACEMENT_CHECKLIST.md`
- 清单模板：`ui_designer/docs/icons.manifest.json`
