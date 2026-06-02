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
