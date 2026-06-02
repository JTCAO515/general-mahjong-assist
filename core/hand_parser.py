"""
国标麻将 — 手牌解析模块

输入 13 张手牌 + 副露（吃碰杠），输出：
  - 按花色分组的计数 dict
  - 面子/搭子列表
  - 向听数计算所需的结构
"""

from typing import Dict, List, Tuple, Optional, Counter as CounterType
from collections import Counter

from core.tile import (
    decode, encode, TOTAL_TILES,
    WAN, TIAO, BING, FENG, JIAN,
    SUIT_BOUNDARIES,
)

# ── 牌计数结构 ───────────────────────────────────────

class Hand:
    """手牌对象

    Attributes:
        tiles: 原始牌编码列表（13 或 14 张）
        counts: {编码: 张数} 聚合计数
        suit_counts: {花色: {点数: 张数}} 分花色计数
        melds: 副露列表，每个副露为 [编码1, 编码2, 编码3]
        is_declared: 是否有副露
    """

    def __init__(self, tiles: List[int], melds: Optional[List[List[int]]] = None):
        if not melds:
            melds = []
        self.tiles = sorted(tiles)
        self.melds = melds
        self.is_declared = len(melds) > 0

        # 校验手牌数（门清 13 张，有副露时 13 - 3×副露数）
        total_hand = len(tiles)
        total_meld_tiles = sum(len(m) for m in melds)
        if not (0 <= total_hand <= 14):
            raise ValueError(f"Invalid hand size: {total_hand}, expected 0-14")

        self.counts: Dict[int, int] = Counter(tiles)
        self._build_suit_counts()

    def _build_suit_counts(self):
        """构建 {花色: {点数: 张数}}"""
        self.suit_counts: Dict[int, Dict[int, int]] = {s: {} for s in range(5)}
        for code, cnt in self.counts.items():
            suit, rank = decode(code)
            if cnt > 0:
                self.suit_counts[suit][rank] = self.suit_counts[suit].get(rank, 0) + cnt

    def __len__(self) -> int:
        return len(self.tiles)

    def add_tile(self, code: int):
        """摸牌（14 张）"""
        self.tiles.append(code)
        self.tiles.sort()
        self.counts[code] = self.counts.get(code, 0) + 1
        suit, rank = decode(code)
        self.suit_counts[suit][rank] = self.suit_counts[suit].get(rank, 0) + 1

    def remove_tile(self, code: int) -> bool:
        """打出一张牌"""
        if self.counts.get(code, 0) == 0:
            return False
        self.tiles.remove(code)
        self.counts[code] -= 1
        if self.counts[code] == 0:
            del self.counts[code]
        suit, rank = decode(code)
        self.suit_counts[suit][rank] -= 1
        if self.suit_counts[suit][rank] == 0:
            del self.suit_counts[suit][rank]
        return True

    def copy(self) -> 'Hand':
        return Hand(self.tiles.copy(), [m.copy() for m in self.melds])


# ── 标准牌型分析 ─────────────────────────────────────

def tiles_to_rank_array(counts: Dict[int, int], suit: int, tile_count: int = 9) -> List[int]:
    """将一个花色的计数转为固定长度数组，方便面子检测

    Args:
        counts: {编码: 张数}
        suit: 花色
        tile_count: 该花色最大点数（万条饼 9，风 4，箭 3）

    Returns:
        [点数1的张数, 点数2的张数, ..., 点数N的张数]
    """
    result = [0] * (tile_count + 2)  # +2 用作哨兵（避免边界检查）
    for code, cnt in counts.items():
        s, r = decode(code)
        if s == suit:
            if 1 <= r <= tile_count:
                result[r - 1] = cnt
    return result


def suit_rank_counts(counts: Dict[int, int], suit: int) -> Dict[int, int]:
    """花色内：{点数: 张数}"""
    result: Dict[int, int] = {}
    for code, cnt in counts.items():
        s, r = decode(code)
        if s == suit:
            result[r] = result.get(r, 0) + cnt
    return result


# ── 顺子/刻子/杠子检测 ────────────────────────────────

def find_sequences(rank_arr: List[int]) -> List[List[int]]:
    """找到一个花色内所有可能的顺子

    Args:
        rank_arr: [点数1的张数, ..., 点数9的张数]

    Returns:
        [(rank1, rank2, rank3), ...] 从低到高
    """
    sequences = []
    # 顺子 123~789，可以包含超过 1 张的情况
    for i in range(7):
        if rank_arr[i] > 0 and rank_arr[i + 1] > 0 and rank_arr[i + 2] > 0:
            sequences.append([i + 1, i + 2, i + 3])
    return sequences


def find_triplets(rank_arr: List[int]) -> List[int]:
    """找到所有刻子/杠子（3+ 张相同）"""
    return [i + 1 for i, cnt in enumerate(rank_arr) if cnt >= 3]


def find_pairs(rank_arr: List[int]) -> List[int]:
    """找到所有对子（2+ 张相同）"""
    return [i + 1 for i, cnt in enumerate(rank_arr) if cnt >= 2]


# ── 手牌解析主函数 ────────────────────────────────────

def parse_hand(tiles: List[int], melds: Optional[List[List[int]]] = None) -> Hand:
    """从编码列表构建 Hand 对象"""
    return Hand(tiles, melds)


def hand_to_string(tiles: List[int]) -> str:
    """手牌列表 → 可读字符串（按花色分组排序）

    Example:
        >>> hand_to_string([encode(WAN,1)]*3 + [encode(TIAO,2)]*2)
        '111万 22条'
    """
    from core.tile import tile_name, group_by_suit
    groups = group_by_suit(tiles)
    parts = []
    for suit in [WAN, TIAO, BING, FENG, JIAN]:
        if groups[suit]:
            names = [tile_name(t) for t in sorted(groups[suit])]
            parts.append("".join(names))
    return " ".join(parts)


def count_by_suit(tiles: List[int]) -> Dict[int, int]:
    """每个花色各几张"""
    from core.tile import group_by_suit
    groups = group_by_suit(tiles)
    return {s: len(g) for s, g in groups.items()}
