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
