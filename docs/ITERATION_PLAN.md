# General Mahjong Assist — 四方向深度迭代计划

## 当前基线
- 番种: 75/81 (官方缺口仅 花牌+单钓将番值)
- 测试: 183
- 策略: 贪心消除法（有已知缺陷）
- 部署: 手动

## 迭代顺序

### Phase 1: 补番到81 → 花牌 + 单钓将番值调整
改动: 极小，不影响现有测试

### Phase 2: 性能优化
目标: 向听数/听牌枚举/番数计算 加缓存
- shanten.py: LRU cache 缓存中间结果
- listen_engine.py: 剪枝不重复计算
- win_checker.py: memoize 同牌型的递归结果
验证: 速度提升 + 正确性保留

### Phase 3: 蒙特卡洛模拟决策引擎
目标: 出牌 EV 排序（代替简单 番数×张数）
- 新建 `decision/monte_carlo.py`
- 每次模拟: 随机摸牌 N 轮 → 胡牌检测 → 统计胜率
- 积分到 game_engine 的出牌推荐中

### Phase 4: CI/CD
- .github/workflows/test.yml
- git push 后自动跑 pytest
