"""
国标麻将 — 蒙特卡洛模拟决策引擎

使用随机模拟评估各出牌选项的期望价值（胜率 × 番数）。
在简单"进张数×番数"评分之外提供更精确的决策依据。

核心流程：
  1. 对每个可能的出牌，模拟 N 局后续摸牌
  2. 每局：从剩余牌池随机摸到 max_draws 张
  3. 检查是否能胡（标准/七对/十三幺/组合龙等）
  4. 统计胜率 + 平均番数 → EV 排序
"""

import random
from concurrent.futures import ProcessPoolExecutor, as_completed
import os
from typing import List, Dict, Tuple, Optional, Set
from collections import Counter

from core.tile import (
    encode, decode, tile_name,
    WAN, TIAO, BING, FENG, JIAN,
    TOTAL_TILES,
)
from core.shanten import calculate_shanten
from core.hand_parser import Hand
from core.win_checker import is_any_win
from core.fan_calculator import FanContext, calculate_fan

# ── 牌池构建 ───────────────────────────────────────────

def build_remaining_pool(all_tiles: List[int],
                         visible: Dict[int, int]) -> List[int]:
    """构建剩余牌池（按 visible 排除已知牌后）

    Args:
        all_tiles: 完整牌池
        visible: 已知牌 {编码: 张数}

    Returns:
        剩余牌编码列表
    """
    pool = list(all_tiles)
    for code, cnt in visible.items():
        for _ in range(cnt):
            if code in pool:
                pool.remove(code)
    return pool


def remaining_to_dict(pool: List[int]) -> Dict[int, int]:
    """将剩余牌列表转为 {编码: 张数}"""
    return dict(Counter(pool))


# ── 单局模拟 ───────────────────────────────────────────

def simulate_one_game(hand: List[int],
                      melds: List[List[int]],
                      remaining: List[int],
                      max_draws: int = 10) -> Tuple[bool, int]:
    """模拟一局：从剩余牌池摸 max_draws 张，检查最终能否胡牌

    简化模型：依次摸牌累积，最终检查完整手牌是否可胡。
    每摸一张后也会立即检查（可能提前胡牌）。

    Args:
        hand: 当前手牌（出牌后）
        melds: 副露
        remaining: 剩余牌池
        max_draws: 最多摸牌次数

    Returns:
        (是否胡牌, 番数)
    """
    pool = list(remaining)
    random.shuffle(pool)

    current_hand = list(hand)
    draws = min(max_draws, len(pool))

    for i in range(draws):
        drawn = pool[i]
        current_hand.append(drawn)
        current_hand.sort()

        # 超过14张就不继续了（麻将最多14张牌）
        if len(current_hand) > 14:
            return False, 0

        # 检查是否胡牌
        if is_any_win(current_hand, melds):
            hand_obj = Hand(current_hand, melds)
            ctx = FanContext(
                hand=hand_obj,
                win_tile=drawn,
                is_self_drawn=True,
            )
            result = calculate_fan(ctx)
            return True, result.total

    return False, 0


# ── 多局模拟 ───────────────────────────────────────────

def simulate_discard(hand: List[int],
                     discard: int,
                     melds: List[List[int]],
                     remaining: List[int],
                     simulations: int = 500,
                     max_draws: int = 10) -> dict:
    """模拟打出某张牌后的 N 局结果

    Args:
        hand: 当前手牌
        discard: 要打出的牌编码
        melds: 副露
        remaining: 剩余牌池
        simulations: 模拟局数
        max_draws: 每局最多摸牌次数

    Returns:
        {
            "tile": discard编码,
            "tile_name": 牌名,
            "simulations": 模拟局数,
            "wins": 胡牌局数,
            "win_rate": 胜率,
            "avg_fan": 平均番数（胡牌局）,
            "ev": 期望值（胜率 × 平均番数）,
        }
    """
    # 模拟打出这张牌
    post_discard = list(hand)
    post_discard.remove(discard)

    wins = 0
    total_fan = 0

    for _ in range(simulations):
        won, fan = simulate_one_game(post_discard, melds, remaining, max_draws)
        if won:
            wins += 1
            total_fan += fan

    win_rate = wins / simulations if simulations > 0 else 0
    avg_fan = total_fan / wins if wins > 0 else 0
    ev = win_rate * avg_fan

    return {
        "tile": discard,
        "tile_name": tile_name(discard),
        "simulations": simulations,
        "wins": wins,
        "win_rate": round(win_rate, 4),
        "avg_fan": round(avg_fan, 1),
        "ev": round(ev, 2),
    }


def evaluate_all_discards(hand: List[int],
                          melds: List[List[int]],
                          remaining: Dict[int, int],
                          simulations: int = 500,
                          max_draws: int = 10,
                          workers: int = 0) -> List[dict]:
    """评估所有可能的出牌（并行加速版）

    Args:
        hand: 当前手牌
        melds: 副露
        remaining: 剩余牌池 {编码: 张数}
        simulations: 每张牌模拟局数
        max_draws: 每局最多摸牌
        workers: 并行进程数，0=自动(CPU核数)

    Returns:
        按 EV 降序排列的出牌评估列表
    """
    # 构建剩余列表
    pool = []
    for code, cnt in remaining.items():
        pool.extend([code] * cnt)

    # 按牌型去重（同一张牌不同编码只算一次）
    unique_by_type: Dict[Tuple[int, int], int] = {}
    for tile in hand:
        suit, rank = decode(tile)
        key = (suit, rank)
        if key not in unique_by_type:
            unique_by_type[key] = tile  # 保留第一个编码

    tiles_to_eval = list(unique_by_type.values())
    if not tiles_to_eval:
        return []

    if workers <= 0:
        workers = min(os.cpu_count() or 4, len(tiles_to_eval))

    # 并行执行
    if workers > 1 and len(tiles_to_eval) > 1:
        results = []
        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(simulate_discard, hand, tile, melds, pool,
                                simulations, max_draws): tile
                for tile in tiles_to_eval
            }
            for future in as_completed(future_map):
                try:
                    results.append(future.result())
                except Exception as e:
                    tile = future_map[future]
                    results.append({
                        "tile": tile, "tile_name": tile_name(tile),
                        "simulations": simulations, "wins": 0,
                        "win_rate": 0, "avg_fan": 0, "ev": 0,
                        "error": str(e),
                    })
    else:
        results = [simulate_discard(hand, tile, melds, pool, simulations, max_draws)
                   for tile in tiles_to_eval]

    results.sort(key=lambda x: x["ev"], reverse=True)
    return results
