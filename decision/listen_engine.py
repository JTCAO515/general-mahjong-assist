"""
国标麻将 — 听牌推荐引擎

核心流程：
  1. 输入 13 张手牌（听牌状态，向听数 = 0）
  2. 遍历所有可胡牌
  3. 对每张胡牌计算番数 + 剩余张数
  4. 按综合得分排序输出
"""

from typing import Dict, List, Tuple, Optional
from collections import Counter
from dataclasses import dataclass

from core.tile import (
    encode, decode,
    WAN, TIAO, BING, FENG, JIAN,
    TOTAL_TILES, tile_name,
)
from core.shanten import calculate_shanten
from core.fan_calculator import FanContext, calculate_fan
from core.hand_parser import Hand


# ── 听牌枚举 ─────────────────────────────────────────

def enumerate_winning_tiles(tiles: List[int],
                            melds: Optional[List[List[int]]] = None,
                            remaining: Optional[Dict[int, int]] = None) -> List[int]:
    """枚举所有可能的胡牌

    Args:
        tiles: 当前手牌（13 张，必须听牌）
        melds: 副露列表
        remaining: 剩余牌池 {编码: 张数}

    Returns:
        可胡牌的编码列表（按剩余张数排序）
    """
    if melds is None:
        melds = []

    # 验证确实是听牌
    shanten_info = calculate_shanten(tiles, melds)
    if shanten_info["min"] != 0:
        return []  # 没听牌

    winning = []
    seen_ranks = set()  # 按 (花色, 点数) 去重

    for code in range(TOTAL_TILES):
        suit, rank = decode(code)
        key = (suit, rank)

        # 跳过已处理的花色+点数（只测每个点数的一个编码）
        if key in seen_ranks:
            continue
        seen_ranks.add(key)

        # 检查剩余张数
        if remaining is not None and remaining.get(code, 0) == 0:
            continue

        # 模拟摸到这张牌
        test_hand = tiles + [code]
        test_melds = list(melds)

        # 检测是否胡牌
        from core.win_checker import is_any_win
        if is_any_win(test_hand, test_melds):
            winning.append(code)

    return winning


# ── 听牌评分 ─────────────────────────────────────────

@dataclass
class ListenOption:
    """一个听牌选择"""
    tile: int                    # 胡牌编码
    name: str                    # 牌名
    remaining: int               # 剩余张数
    fan: int                     # 番数
    fan_items: List[Tuple[str, int]]  # 番种明细
    score: float                 # 综合评分

    def summary(self) -> str:
        return f"{self.name} ×{self.remaining} → {self.fan}番 ({self.score:.1f})"


def score_listen_tile(tile_code: int,
                      hand_tiles: List[int],
                      melds: Optional[List[List[int]]],
                      remaining: Optional[Dict[int, int]],
                      seat_wind: int = 1,
                      round_wind: int = 1,
                      is_self_drawn: bool = True) -> Optional[ListenOption]:
    """对单张胡牌计算评分

    Args:
        tile_code: 胡牌编码
        hand_tiles: 原手牌（13 张）
        melds: 副露
        remaining: 剩余牌池
        seat_wind: 座位风
        round_wind: 圈风

    Returns:
        ListenOption 或 None（不可胡）
    """
    if melds is None:
        melds = []

    # 验证胡牌
    test_hand = hand_tiles + [tile_code]
    from core.win_checker import is_any_win
    if not is_any_win(test_hand, melds):
        return None

    # 计算剩余张数
    remains = remaining.get(tile_code, 0) if remaining else 4
    suit, r = decode(tile_code)
    if suit == FENG:
        remains = min(remains, 3)

    # 计算番数
    ctx = FanContext(
        hand=Hand(test_hand, melds),
        win_tile=tile_code,
        is_self_drawn=False,   # 按点炮胡算分（自摸额外+1番）
        seat_wind=seat_wind,
        round_wind=round_wind,
    )
    fan_result = calculate_fan(ctx)

    # 不起胡的牌不算有效听牌
    if fan_result.total == 0:
        return None

    # 评分：番数 × 剩余张数（简单期望值）
    score = fan_result.total * remains

    return ListenOption(
        tile=tile_code,
        name=tile_name(tile_code),
        remaining=remains,
        fan=fan_result.total,
        fan_items=fan_result.items,
        score=score,
    )


def analyze_listen(tiles: List[int],
                   melds: Optional[List[List[int]]] = None,
                   remaining: Optional[Dict[int, int]] = None,
                   seat_wind: int = 1,
                   round_wind: int = 1,
                   is_self_drawn: bool = True) -> Dict:
    """完整听牌分析

    Args:
        tiles: 手牌（13 张，必须听牌）
        melds: 副露
        remaining: 剩余牌池
        seat_wind: 座位风
        round_wind: 圈风
        is_self_drawn: 是否自摸

    Returns:
        {
            "is_tenpai": bool,
            "options": [ListenOption, ...],
            "best": ListenOption or None,
            "total_fan": max fan,
        }
    """
    if melds is None:
        melds = []

    shanten_info = calculate_shanten(tiles, melds)
    is_tenpai = shanten_info["min"] == 0

    if not is_tenpai:
        return {"is_tenpai": False, "options": [], "best": None, "total_fan": 0}

    winning_tiles = enumerate_winning_tiles(tiles, melds, remaining)

    options = []
    for tile_code in winning_tiles:
        opt = score_listen_tile(
            tile_code, tiles, melds, remaining,
            seat_wind, round_wind, is_self_drawn,
        )
        if opt:
            options.append(opt)

    # 按综合评分排序（番数 × 张数）
    options.sort(key=lambda o: -o.score)

    best = options[0] if options else None
    total_fan = best.fan if best else 0

    return {
        "is_tenpai": True,
        "options": options,
        "best": best,
        "total_fan": total_fan,
    }


# ── 出牌分析（非听牌时） ─────────────────────────────

def discard_advice(tiles: List[int],
                   melds: Optional[List[List[int]]] = None,
                   remaining: Optional[Dict[int, int]] = None) -> List[Dict]:
    """出牌建议：每次出牌的打后向听数 + 进张数分析

    Args:
        tiles: 手牌（14 张，摸牌后）
        melds: 副露
        remaining: 剩余牌池

    Returns:
        按优先级排序的出牌建议
    """
    from core.shanten import discard_analysis
    return discard_analysis(tiles, melds, remaining)
