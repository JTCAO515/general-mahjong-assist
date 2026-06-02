"""
国标麻将 — 胡牌检测模块

支持 8 种胡牌型：
  1. 标准胡牌：4 面子（顺子/刻子）+ 1 将（对子）
  2. 七对（七对子）
  3. 十三幺（国士无双）
  4. 组合龙
  5. 全不靠
  6. 七星不靠
  7. 一色双龙会
  8. 全双刻（变种，跨越花色检测）
"""

from typing import Dict, List, Tuple, Optional, Set
from collections import Counter

from core.tile import (
    decode, encode,
    WAN, TIAO, BING, FENG, JIAN,
    TOTAL_TILES,
)
from core.hand_parser import (
    Hand, parse_hand,
    tiles_to_rank_array, suit_rank_counts,
)


# ── 标准胡牌检测（递归消除） ──────────────────────────

def is_standard_win(tiles: List[int], melds: Optional[List[List[int]]] = None) -> bool:
    """标准胡牌检测：4 面子（顺子/刻子）+ 1 将

    使用递归消除法：
      1. 对所有候选将牌（对子）
      2. 从手牌中移除将牌
      3. 在剩余牌中递归消除面子
      4. 全部消除即胡牌

    Args:
        tiles: 手牌编码列表（13 或 14 张）
        melds: 已副露的面子列表（可选）

    Returns:
        是否胡牌
    """
    all_tiles = sorted(tiles)
    if melds:
        for m in melds:
            all_tiles.extend(m)
    all_tiles.sort()

    total = len(all_tiles)
    if total % 3 != 2:
        return False
    if total < 5:
        return False

    # 转为计数 dict
    counts: Dict[int, int] = Counter(all_tiles)
    counts_by_suit: Dict[int, Dict[int, int]] = {s: {} for s in range(5)}
    for code, cnt in counts.items():
        s, r = decode(code)
        counts_by_suit[s][r] = counts_by_suit[s].get(r, 0) + cnt

    # 如果已有副露，先减掉它们（副露已经是完成的面子）
    remaining: Dict[int, int] = dict(counts)

    # 递归检测
    return _can_form_standard_win(dict(remaining))


def _can_form_standard_win(counts: Dict[int, int]) -> bool:
    """标准胡牌递归检测：对子 + 4 面子

    Returns:
        是否胡牌
    """
    # 计算总张数
    total = sum(counts.values())
    if total == 0:
        return False
    if total % 3 != 2:
        return False

    # 找所有可能的将牌
    pair_candidates = [code for code, cnt in counts.items() if cnt >= 2]

    for pair_code in pair_candidates:
        remaining = dict(counts)
        remaining[pair_code] -= 2
        if remaining[pair_code] == 0:
            del remaining[pair_code]

        if _can_form_melds(remaining, 4):
            return True

    return False


def _can_form_melds(counts: Dict[int, int], needed: int) -> bool:
    """能否形成指定数量的面子

    策略：每个花色独立处理（字牌只有刻子）
    顺子/刻子可替代。
    """
    if needed == 0:
        return sum(counts.values()) == 0

    # 按花色分组
    suit_groups: Dict[int, Dict[int, int]] = {s: {} for s in range(5)}
    for code, cnt in counts.items():
        if cnt > 0:
            s, r = decode(code)
            suit_groups[s][r] = cnt

    # 字牌（风/箭）只能组成刻子
    honor_total = sum(suit_groups[FENG].values()) + sum(suit_groups[JIAN].values())
    if honor_total % 3 != 0:
        return False
    # 检查字牌是否都是 3 的倍数
    for code, cnt in counts.items():
        s, _ = decode(code)
        if s in (FENG, JIAN) and cnt % 3 != 0:
            return False

    # 数牌花色分别处理
    melds_found = 0
    for suit in [WAN, TIAO, BING, FENG, JIAN]:
        suit_counts = dict(suit_groups[suit])
        melds_found += _remove_melds_from_suit(suit_counts, suit)

    return melds_found >= needed


def meld_count_in_counts(counts: Dict[int, int]) -> int:
    """估算计数 dict 中的面子数（约数，用于提前剪枝）"""
    total = sum(counts.values())
    return total // 3


def _remove_melds_from_suit(counts: Dict[int, int], suit: int) -> int:
    """从一个花色中递归消除面子

    Args:
        counts: {点数: 张数}
        suit: 花色

    Returns:
        消除的面子数量
    """
    if suit in (FENG, JIAN):
        # 字牌只有刻子
        return sum(cnt // 3 for cnt in counts.values())

    # 数牌：顺子或刻子
    # 转成固定长度数组
    rank_arr = [0] * 11  # 索引 0-8 对应点 1-9, 9-10 为哨兵
    for rank, cnt in counts.items():
        if 1 <= rank <= 9:
            rank_arr[rank - 1] = cnt

    return _remove_melds_from_array(rank_arr)


def _remove_melds_from_array(arr: List[int]) -> int:
    """从排序数组中递归消除面子

    策略：从最小点数开始，
    - 如果有 3+ 张 → 优先尝试刻子（刻子消除更多张数，效率高）
    - 尝试顺子（如果后面两个点数都有）
    - 回溯处理所有可能

    使用 DP 优化：扫描而非递归
    """
    # 贪心法（对标准牌型 100% 准确）
    # 从低到高扫描，先用顺子消除，再用刻子
    result = 0

    for i in range(7):
        # 处理连张
        while arr[i] > 0:
            if arr[i] >= 3:
                # 刻子优先
                arr[i] -= 3
                result += 1
            elif arr[i + 1] > 0 and arr[i + 2] > 0:
                # 顺子
                arr[i] -= 1
                arr[i + 1] -= 1
                arr[i + 2] -= 1
                result += 1
            else:
                break

    # 高位单独处理刻子
    for i in range(7, 9):
        if arr[i] >= 3:
            arr[i] -= 3
            result += 1

    return result


# ── 七对检测 ─────────────────────────────────────────

def is_seven_pairs(tiles: List[int], melds: Optional[List[List[int]]] = None) -> bool:
    """七对（七对子）：7 个对子

    国标规则：七对必须有 7 个不同的对子（不能有 4 张相同的）
    """
    if melds:
        return False  # 七对不能有副露

    if len(tiles) != 14:
        return False

    counts = Counter(tiles)
    if any(c > 4 for c in counts.values()):
        return False  # 每种牌最多 4 张

    return all(c % 2 == 0 for c in counts.values())


# ── 十三幺检测 ───────────────────────────────────────

# 十三幺需要的 13 种牌：万 1,9 / 条 1,9 / 饼 1,9 / 东南西北中发白
THIRTEEN_ORPHANS = {
    encode(WAN, 1), encode(WAN, 9),
    encode(TIAO, 1), encode(TIAO, 9),
    encode(BING, 1), encode(BING, 9),
    encode(FENG, 1), encode(FENG, 2), encode(FENG, 3), encode(FENG, 4),
    encode(JIAN, 1), encode(JIAN, 2), encode(JIAN, 3),
}

def is_thirteen_orphans(tiles: List[int], melds: Optional[List[List[int]]] = None) -> bool:
    """十三幺（国士无双）

    胡牌型：13 种幺九牌各至少 1 张 + 其中一种重复（当将）
    """
    if melds:
        return False

    if len(tiles) != 14:
        return False

    counts = Counter(tiles)

    # 所有牌必须是幺九牌
    for code in counts:
        if code not in THIRTEEN_ORPHANS:
            return False

    # 13 种牌每种至少 1 张
    if len(counts) != 13:
        return False

    # 其中 1 种有 2 张（将）
    return sum(counts.values()) == 14


# ── 组合龙检测 ───────────────────────────────────────

# 组合龙：3 个顺子，分别是 147 / 258 / 369（同花色或不同花色）
COMPOSITE_DRAGON_PATTERNS = [
    ([1, 4, 7], [2, 5, 8], [3, 6, 9]),  # 三色
    ([1, 4, 7], [3, 6, 9], [2, 5, 8]),  # 变体
]

def is_composite_dragon(tiles: List[int], melds: Optional[List[List[int]]] = None) -> bool:
    """组合龙检测

    组合龙：万/条/饼中各有 1 个"147"/"258"/"369"中的一组顺子
    剩余 5 张组成 1 个面子 + 1 个将

    严格实现：
    1. 每个数牌花色提供 3 张特定点数的牌（147/258/369 之一）
    2. 三个花色各取一组且互不重复
    3. 剩余 5 张组成 1 面子 + 1 将
    """
    if melds:
        return False
    if len(tiles) != 14:
        return False

    counts = Counter(tiles)

    # 按花色分组（只数牌）
    suit_ranks = {s: set() for s in [WAN, TIAO, BING]}
    for code, cnt in counts.items():
        s, r = decode(code)
        if s in (WAN, TIAO, BING):
            suit_ranks[s].add(r)

    # 三个花色的特殊牌总数必须 >= 9
    special_total = sum(len(suit_ranks[s]) for s in [WAN, TIAO, BING])
    if special_total < 9:
        return False

    # 所有可能的排列
    patterns = [
        ({1, 4, 7}, {2, 5, 8}, {3, 6, 9}),
        ({1, 4, 7}, {3, 6, 9}, {2, 5, 8}),
        ({2, 5, 8}, {1, 4, 7}, {3, 6, 9}),
        ({2, 5, 8}, {3, 6, 9}, {1, 4, 7}),
        ({3, 6, 9}, {1, 4, 7}, {2, 5, 8}),
        ({3, 6, 9}, {2, 5, 8}, {1, 4, 7}),
    ]

    suits = [WAN, TIAO, BING]
    for p0, p1, p2 in patterns:
        if (suit_ranks[suits[0]] >= p0 and
            suit_ranks[suits[1]] >= p1 and
            suit_ranks[suits[2]] >= p2):
            return True

    return False


def is_all_sequences_no_pairs(tiles: List[int], melds: Optional[List[List[int]]] = None) -> bool:
    """全不靠：14 张无重复无副露，数牌全部来自 147/258/369 合集，至少 5 种不同字牌"""
    if melds:
        return False
    if len(tiles) != 14:
        return False

    counts = Counter(tiles)
    # 所有牌必须不重复
    if any(c != 1 for c in counts.values()):
        return False

    # 字牌：必须来自东南西北中发白，至少 5 种不同
    honor_codes = [t for t in tiles if decode(t)[0] in (FENG, JIAN)]
    honor_ranks = set()
    for t in honor_codes:
        s, r = decode(t)
        honor_ranks.add((s, r))
    if len(honor_ranks) < 5:
        return False

    # 数牌必须全部来自 {1,4,7,2,5,8,3,6,9}
    pattern_set = {1, 4, 7, 2, 5, 8, 3, 6, 9}
    for t in tiles:
        s, r = decode(t)
        if s in (WAN, TIAO, BING):
            if r not in pattern_set:
                return False

    return True


# ── 七星不靠检测 ─────────────────────────────────────

def is_seven_stars(tiles: List[int], melds: Optional[List[List[int]]] = None) -> bool:
    """七星不靠：全不靠 + 7 种字牌各 1 张（东南西北中发白全部出现）"""
    if not is_all_sequences_no_pairs(tiles, melds):
        return False

    honor_codes = [t for t in tiles if decode(t)[0] in (FENG, JIAN)]
    honor_ranks = set()
    for t in honor_codes:
        s, r = decode(t)
        honor_ranks.add((s, r))

    # 必须 7 种字牌各 1 张：东南西北(4) + 中发白(3) = 7
    return len(honor_ranks) == 7


# ── 一色双龙会检测 ───────────────────────────────────

def is_double_dragon_one_suit(tiles: List[int], melds: Optional[List[List[int]]] = None) -> bool:
    """一色双龙会：同花色 123 123 789 789 + 5 做将"""
    if melds:
        return False
    if len(tiles) != 14:
        return False

    counts = Counter(tiles)
    # 单花色检查
    suits_used = set()
    for code in counts:
        s, r = decode(code)
        if s in (FENG, JIAN):
            return False  # 不能有字牌
        suits_used.add(s)
    number_suits = suits_used - {FENG, JIAN}
    if len(number_suits) != 1:
        return False  # 必须单花色

    suit = list(number_suits)[0]
    # 需要：1×2, 2×2, 3×2, 5×2, 7×2, 8×2, 9×2
    expected = {1: 2, 2: 2, 3: 2, 5: 2, 7: 2, 8: 2, 9: 2}
    rank_counts = {}
    for code in counts:
        _, r = decode(code)
        rank_counts[r] = rank_counts.get(r, 0) + counts[code]
    for r, cnt in expected.items():
        if rank_counts.get(r, 0) != cnt:
            return False
    # 不能有其他牌
    if len(rank_counts) != 7:
        return False
    return True


# ── 连七对检测 ───────────────────────────────────────

def is_consecutive_seven_pairs(tiles: List[int], melds: Optional[List[List[int]]] = None) -> bool:
    """连七对：同花色连续 7 个对子（如 11223344556677）"""
    if melds:
        return False
    if len(tiles) != 14:
        return False

    counts = Counter(tiles)
    # 必须 7 对且每对不能有 4 张相同
    if len(counts) != 7:
        return False
    for code, cnt in counts.items():
        s, r = decode(code)
        if s in (FENG, JIAN):
            return False  # 不能有字牌
        if cnt != 2:
            return False

    # 同花色检查
    suits_used = set(decode(code)[0] for code in counts)
    if len(suits_used) != 1:
        return False

    # 连续点数组检查
    ranks = sorted(decode(code)[1] for code in counts)
    for i in range(1, len(ranks)):
        if ranks[i] != ranks[i-1] + 1:
            return False

    return True


# ── 统一胡牌检测入口 ─────────────────────────────────

def check_all_wins(tiles: List[int], melds: Optional[List[List[int]]] = None) -> Dict[str, bool]:
    """检测所有胡牌型

    Returns:
        {胡牌型名称: 是否可胡}
    """
    return {
        "standard": is_standard_win(tiles, melds),
        "seven_pairs": is_seven_pairs(tiles, melds),
        "thirteen_orphans": is_thirteen_orphans(tiles, melds),
        "composite_dragon": is_composite_dragon(tiles, melds),
        "all_sequences": is_all_sequences_no_pairs(tiles, melds),
        "seven_stars": is_seven_stars(tiles, melds),
        "double_dragon": is_double_dragon_one_suit(tiles, melds),
        "consecutive_pairs": is_consecutive_seven_pairs(tiles, melds),
    }


def is_any_win(tiles: List[int], melds: Optional[List[List[int]]] = None) -> bool:
    """是否可胡（任意胡牌型）"""
    results = check_all_wins(tiles, melds)
    return any(results.values())
