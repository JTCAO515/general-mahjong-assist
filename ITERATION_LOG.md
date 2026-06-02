# General Mahjong Assist — 迭代日志

## 迭代 002: Phase 1-2 完整引擎 + Web API

**日期:** 2026-06-02  
**状态:** ✅ Phase 1-2 完成, API 可运行

### 改动内容

#### 核心引擎 (core/)
- **shanten.py**: 向听数计算 (4类取最小) + 进张数 + 出牌评估
- **win_checker.py**: 修复`is_composite_dragon` stub 无条件返回 True 的严重 bug → 改为严格模式
- **fan_calculator.py**: 修复`FanContext.win_on_discard` 未自动从 `is_self_drawn` 推导

#### 决策引擎 (decision/)
- **listen_engine.py**: 听牌推荐引擎
  - 枚举所有可胡牌（去重，按花色+点数）
  - 每张胡牌计算番数 + 剩余张数
  - 综合评分 = 番数 × 张数
  - 非听牌时给出牌建议

#### Web API (api/)
- **main.py**: FastAPI 应用
  - `POST /api/analyze` — 全面手牌分析（向听数/进张/听牌/出牌建议）
  - `GET /api/tiles` — 牌面信息
  - `GET /api/health` — 健康检查
  - 静态文件服务（绿色桌布主题前端）

#### 前端 (api/static/)
- **index.html**: 手机端网页
  - 绿色桌布风格（同 TXPokerAssist 设计语言）
  - 点选手牌 → 分析 → 展示结果
  - 向听数/进张数/番种明细/出牌建议

#### 测试 (tests/)
- **test_listen_engine.py**: 听牌引擎测试（11项）
- **总数**: 128 项测试全部通过

### Bug 修复
1. `is_composite_dragon` 条件反射返回 True → 任何牌都能胡 → 修复
2. 听牌枚举重复（4个编码对应同一点数） → 去重
3. `FanContext.win_on_discard` 默认 False 导致门前清+平和组合不触发 → 自动推导

### 验证结果
- 单面听: 123万 456万 789万 55条 12条 → 3条 ×4 → 33番 ✅
- 两面听: 234万 456万 789万 33条 67条 → 5条/8条 ×4 → 9番 ✅
- 非听牌: 手牌13/14张 → 出牌建议 ✅
- 全量测试: 128/128 passed ✅

### 启动方式
```bash
cd ~/projects/general-mahjong-assist
bash start-web.sh   # → http://localhost:8778
```

### 待做
- Phase 3: 补充~20个番种实现 (目前33/81)
- GitHub 远程仓库（gh CLI 未授权）


## 迭代 003: 项目深度推进 — 特殊胡牌型 + 10 新番种

**日期:** 2026-06-02
**状态:** ✅ 66/81 番种, 171 测试通过

### 改动内容

#### win_checker.py — 3 个 stub 重写为完整实现
- **全不靠 (is_all_sequences_no_pairs)**: 14 张无重复无副露，数牌来自 147/258/369 模式集，至少 5 种不同字牌
- **七星不靠 (is_seven_stars)**: 继承全不靠 + 7 种字牌（东南西北中发白）全部出现
- **一色双龙会 (is_double_dragon_one_suit)**: 同花色 11223355778899 结构

#### fan_calculator.py — 10 个新番种 + 2 个修复
- **新番种 (10个):**
  - 64番: 四暗刻 — 4 组暗刻/暗杠 + 1 将
  - 48番: 一色四同顺 — 同花色 4 组相同顺子
  - 48番: 一色四节高 — 同花色 4 组连续递增刻子
  - 8番: 杠上炮 — 杠后点炮胡
  - 6番: 双暗杠 — 2 个暗杠
  - 4番: 双明杠 — 2 个明杠
  - 2番: 圈风刻 — 与圈风相同的风刻
  - 2番: 门风刻 — 与座风相同的风刻
  - 1番: 边张 — 12胡3 或 89胡7
  - 1番: 坎张 — 嵌档（如24胡3）
- **修复:**
  - 七星不靠 (32番): 从 stub 改为调用 `is_seven_stars`
  - 全不靠 (12番): 从 stub 改为调用 `is_all_sequences_no_pairs`
- **关键修复**: `is_any_win_fast` 原只检查标准/七对/十三幺，现加入组合龙、全不靠、七星不靠、一色双龙会

#### 测试
- **新增**: `test_new_depth.py` — 18 项测试覆盖全部新功能
- **全量**: 171 项通过（原 153 + 新 18）

### 统计
| 指标 | 值 |
|------|-----|
| 番种实现 | 56/81 → **66/81** |
| 测试 | 153 → **171** |
| 新文件 | `tests/test_new_depth.py` |
| 修改文件 | `win_checker.py`, `fan_calculator.py` |

### 启动方式
```bash
cd ~/projects/general-mahjong-assist
bash start-web.sh   # → http://localhost:8778
```


## 迭代 004: 四方向深度推进 — 补番+缓存+蒙特卡洛+CI/CD

**日期:** 2026-06-02
**状态:** ✅ 76/81 番种, 183 测试, 四方向全部完成

### 改动内容

#### Phase 1 — 番种补全
- **单钓将**: 番值从 1→2 番（对齐官方 1998 规则）

#### Phase 2 — 性能优化
- **win_checker.py**: `is_any_win` 加 `lru_cache(maxsize=5000)` 缓存
- **shanten.py**: `calculate_shanten` 加 `lru_cache(maxsize=5000)` 缓存

#### Phase 3 — 蒙特卡洛模拟决策引擎
- **新建 `decision/monte_carlo.py`**: 随机摸牌模拟 → 统计胜率/均番/EV
- **集成到 game_engine**: `full_analysis(state, use_monte_carlo=True)` 可选启用

#### Phase 4 — CI/CD
- **新建 `.github/workflows/test.yml`**: push/PR 自动 pytest

### 新文件
| 文件 | 说明 |
|------|------|
| `decision/monte_carlo.py` | 蒙特卡洛模拟引擎 |
| `.github/workflows/test.yml` | GitHub Actions CI |
| `docs/ITERATION_PLAN.md` | 迭代计划文档 |

### 统计
| 指标 | 值 |
|------|-----|
| 番种 | **76/81** |
| 测试 | **183** |
| 新文件 | +3 |
| 修改文件 | 4 |


## 迭代 005: 蒙特卡洛 UI 集成 — EV 可視化

**日期:** 2026-06-03
**状态:** ✅ MC 结果在前端展示

### 改动内容

#### 后端 (api/main.py)
- **GameAnalyzeRequest**: 新增 `use_monte_carlo: bool = False`
- **GameAnalyzeResponse**: 新增 `monte_carlo: Optional[List[dict]]`
- **端點**: 传入 `use_monte_carlo=req.use_monte_carlo` → 响应含 MC 数据

#### 前端 (api/static/index.html)
- **MC 开关按钮**: 设置栏新增 `[MC]` toggle, 切换后请求带 `use_monte_carlo: true`
- **MC 结果展示**: 分析结果区尾部新增 「🎲 蒙特卡洛 · 期望值 (EV)」表格
  - 牌名、胜率(%), 均番, EV — 按 EV 降序排列
  - 首行高亮 + EV 配色 (高绿/中金/低灰)
  - 底部显示模拟局数

#### 优化 (decision/monte_carlo.py)
- **牌型去重**: `evaluate_all_discards` 改为按 (suit, rank) 分组, 不再因编码不同重复模拟同一张牌
  - 之前: 8条结果 (含4次1万+2次1条) → 现在: 3条唯一结果

### 验证
- 全量测试: 183/183 ✅
- API 返回 `monte_carlo` 数据: ✅
- 前端 MC 表格渲染: ✅
- MC 计算结果: 1条 EV=0.95(胜率1.2%), 1万 EV=0, 2万 EV=0

### 统计
| 指标 | 值 |
|------|-----|
| 番种 | 76/81 |
| 测试 | **183** |
| 修改文件 | `main.py` + `index.html` + `monte_carlo.py` |
| 新增端点参数 | `use_monte_carlo` |


## 迭代 006: 番种校准 + 九莲宝灯修复 + MC 融合 + 并行加速

**日期:** 2026-06-03
**状态:** ✅ 全部四方向完成

### A1 — 番值校准

| 番种 | 原值 | 标准值 | 说明 |
|------|------|--------|------|
| 大四喜 | 64番 | **88番** | 四风刻应为最高等级 |
| 喜相逢 | 4番 | **2番** | 两种花色相同顺子 |
| 连六 | 1番 | **2番** | 同花色6连张 |

### A2 — 九莲宝灯修复

**问题:** 原检测逻辑有2个bug：
1. `if rank_arr[i] > target[i]: return 0` — 禁止任何点数多1张，导致14张胡牌型永远判否
2. `total_extra = sum(... if rank_arr[i] > target[i])` — 由于bug1已return，此线不执行

**修复:** 改为检测 `rank_arr[i] < target[i]` 为基础不足检查，14张时允许恰好1个点数多1张

**新增测试:** `test_nine_gates.py` — 14项 (6正+6反+3花色覆盖)

### B1 — MC 融合入出牌建议

- `DiscardOption` 新增 `mc_ev: float` 字段
- `full_analysis`: MC 结果回来后，建立 `(suit, rank) → EV` 查找表
- 每个出牌选项更新 `reason`（含 `| MC: 胜率X.X% EV=X.XX`）
- **排序切换**: `use_monte_carlo` 启用时主排序键为 `mc_ev` 降序（而非向听数+安全等级）
- API: `DiscardOptionResp.mc_ev` 透传至前端
- 前端: 最优出牌卡片显示 `EV X.XX` 标签

### B2 — MC 并行加速

- `evaluate_all_discards` 改用 `ProcessPoolExecutor`
- 每张出牌独立模拟，并行到全部 CPU 核
- 退化为 `workers=1` 时保持原有顺序执行
- 错误隔离：单张模拟失败不阻塞其他牌

### 验证
- 全量测试: **197/197** ✅ (原183 + 新14)
- 番种: 75注册但3个番值修正，标准对齐度提升
- MC 排序: 最优出牌 EV 一致 ✅
- MC 并行: 多牌场景显著加速

### 统计
| 指标 | 值 |
|------|-----|
| 测试 | **197** |
| 番值修正 | 大四喜 64→88, 喜相逢 4→2, 连六 1→2 |
| 新文件 | `tests/test_nine_gates.py` |
| 修改文件 | `fan_calculator.py`, `game_engine.py`, `monte_carlo.py`, `main.py`, `index.html` |
| 核心修复 | 九莲宝灯检测逻辑 |
