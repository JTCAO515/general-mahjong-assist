"""
国标麻将 — 向听数计算模块

向听数 = 还差几步进入听牌状态（0 = 听牌, 1 = 一上听, ...）

4 类取最小：
  1. 面子手（标准胡牌）：4 面子 + 1 将
  2. 七对子
  3. 十三幺
  4. 组合龙

算法核心：递归拆分手牌，枚举所有可能的完成组 + 部分组，
           用公式 shanten = 8 - 2*完成组 - 部分组 - 将牌
"""

from typing import Dict, List, Tuple, Optional, Set
from collections import Counter
from functools import lru_cache

from core.tile import (
    decode, encode,
    WAN, TIAO, BING, FENG, JIAN,
)
from core.hand_parser import (
    Hand, tiles_to_rank_array,
    find_sequences, find_triplets, find_pairs,
)


# ── 面子手向听数 ─────────────────────────────────────

def calculate_melds_partials(rank_arr: List[int]) -> Tuple[int, int, int]:
    """计算一个花色内的完成组(面子)数和部分组(搭子)数

    使用 DP/回溯：枚举刻子和顺子，找出最大面子数和搭子数组合。

    Args:
        rank_arr: [点数1的张数, ..., 点数9的张数, 哨兵, 哨兵]

    Returns:
        (max_melds, max_partials, has_pair)
    """
    # 使用 memoized 递归
    return _calc_meld_partial_recursive(tuple(rank_arr), False)


@lru_cache(maxsize=100000)
def _calc_meld_partial_recursive(arr: Tuple[int, ...], has_pair: bool) -> Tuple[int, int, bool]:
    """递归：枚举所有面子/搭子组合

    Uses positional encoding for memozation:
    - arr: tile counts per rank (with 2 sentinels)
    - has_pair: whether we've already taken a pair
    """
    arr_list = list(arr)

    # 找到第一个非 0 位置
    start = -1
    for i, cnt in enumerate(arr_list):
        if cnt > 0:
            start = i
            break

    if start == -1:
        # 所有牌用完
        return (0, 0, has_pair)

    best_melds = -1
    best_partials = -1
    best_pair = has_pair

    rank = start
    cnt = arr_list[rank]

    # 1. 刻子（3 张相同）
    if cnt >= 3:
        new_arr = list(arr_list)
        new_arr[rank] -= 3
        m, p, hp = _calc_meld_partial_recursive(tuple(new_arr), has_pair)
        # 刻子算 1 个完成组
        cand = (m + 1, p, hp)
        if _score_key(cand) > _score_key((best_melds, best_partials, best_pair)):
            best_melds, best_partials, best_pair = cand

    # 2. 顺子（3 张连续，限制在点数 1-7 范围内）
    if rank < 7 and arr_list[rank] > 0 and arr_list[rank + 1] > 0 and arr_list[rank + 2] > 0:
        new_arr = list(arr_list)
        new_arr[rank] -= 1
        new_arr[rank + 1] -= 1
        new_arr[rank + 2] -= 1
        m, p, hp = _calc_meld_partial_recursive(tuple(new_arr), has_pair)
        cand = (m + 1, p, hp)
        if _score_key(cand) > _score_key((best_melds, best_partials, best_pair)):
            best_melds, best_partials, best_pair = cand

    # 3. 对子（2 张相同）
    if cnt >= 2 and not has_pair:
        new_arr = list(arr_list)
        new_arr[rank] -= 2
        m, p, hp = _calc_meld_partial_recursive(tuple(new_arr), True)
        cand = (m, p, True)
        if _score_key(cand) > _score_key((best_melds, best_partials, best_pair)):
            best_melds, best_partials, best_pair = cand

    # 4. 搭子/对子作为部分组
    #    b. 两面搭（rank, rank+1）
    if rank < 8 and cnt >= 1 and arr_list[rank + 1] >= 1:
        new_arr = list(arr_list)
        new_arr[rank] -= 1
        new_arr[rank + 1] -= 1
        m, p, hp = _calc_meld_partial_recursive(tuple(new_arr), has_pair)
        cand = (m, p + 1, hp)
        if _score_key(cand) > _score_key((best_melds, best_partials, best_pair)):
            best_melds, best_partials, best_pair = cand

    #    c. 边张搭（rank, rank+2）
    if rank < 7 and cnt >= 1 and arr_list[rank + 2] >= 1:
        new_arr = list(arr_list)
        new_arr[rank] -= 1
        new_arr[rank + 2] -= 1
        m, p, hp = _calc_meld_partial_recursive(tuple(new_arr), has_pair)
        cand = (m, p + 1, hp)
        if _score_key(cand) > _score_key((best_melds, best_partials, best_pair)):
            best_melds, best_partials, best_pair = cand

    # 5. 单张（废弃）
    if cnt >= 1:
        new_arr = list(arr_list)
        new_arr[rank] -= 1
        m, p, hp = _calc_meld_partial_recursive(tuple(new_arr), has_pair)
        cand = (m, p, hp)
        if _score_key(cand) > _score_key((best_melds, best_partials, best_pair)):
            best_melds, best_partials, best_pair = cand

    return (best_melds, best_partials, best_pair)


@lru_cache(maxsize=10000)
def _score_key(value: Tuple[int, int, bool]) -> Tuple[int, int, int]:
    """评分键：将牌优先级 > 部分组数量"""
    m, p, hp = value
    return (m, 1 if hp else 0, p)


def calculate_melds_partials_for_hand(hand: Hand) -> Tuple[int, int, bool]:
    """计算整个手牌（含副露）的完成组数和部分组数

    Returns:
        (melds, partials, has_pair)
    """
    total_melds = len(hand.melds)  # 副露已经是完成组
    total_partials = 0
    has_pair = False

    # 处理手牌
    counts = hand.counts
    if not counts:
        return (total_melds, 0, False)

    # 按花色分组处理
    for suit in [WAN, TIAO, BING]:
        rank_arr = [0] * 11
        for code, cnt in counts.items():
            s, r = decode(code)
            if s == suit and 1 <= r <= 9:
                rank_arr[r - 1] = cnt  # r is 1-based → index r-1
        m, p, hp = calculate_melds_partials(rank_arr)
        total_melds += m
        total_partials += p
        if hp:
            has_pair = True

    # 字牌处理（风/箭）：只能做刻子或对子
    for suit in [FENG, JIAN]:
        # 每种字牌独立处理
        for code, cnt in counts.items():
            s, r = decode(code)
            if s == suit:
                if cnt >= 3:
                    total_melds += 1
                    cnt -= 3
                if cnt >= 2 and not has_pair:
                    has_pair = True
                    cnt -= 2
                # 剩下的牌（单张）不计入部分组（字牌搭子价值很低）

    return (total_melds, total_partials, has_pair)


def shanten_standard(counts: Dict[int, int], melds: List[List[int]]) -> int:
    """面子手向听数

    shanten = 8 - 2*melds - partials - pair

    结果：
        -1 = 已经胡牌
        0  = 听牌
        1  = 一上听
        2  = 二上听
        ...
    """
    hand = Hand(list(counts.elements()), melds)
    meld_count, partial_count, has_pair = calculate_melds_partials_for_hand(hand)

    # 部分组不能超过"还需要完成的面子数"
    melds_needed = 4 - meld_count
    effective_partials = min(partial_count, melds_needed)

    shanten = 8 - 2 * meld_count - effective_partials - (1 if has_pair else 0)

    return max(-1, shanten)


# ── 七对向听数 ───────────────────────────────────────

def shanten_seven_pairs(tiles: List[int]) -> int:
    """七对向听数

    需要 7 个对子。已有 p 个对子时：
    shanten = 6 - p
    （4 张相同的牌算 2 个对子）
    """
    if len(tiles) < 13:
        return 6

    counts = Counter(tiles)
    pairs = 0
    for c in counts.values():
        pairs += c // 2

    # 最多 7 对
    return max(0, 6 - pairs)


# ── 十三幺向听数 ─────────────────────────────────────

THIRTEEN_ORPHANS_SET = {
    encode(WAN, 1), encode(WAN, 9),
    encode(TIAO, 1), encode(TIAO, 9),
    encode(BING, 1), encode(BING, 9),
    encode(FENG, 1), encode(FENG, 2), encode(FENG, 3), encode(FENG, 4),
    encode(JIAN, 1), encode(JIAN, 2), encode(JIAN, 3),
}

def shanten_thirteen_orphans(tiles: List[int]) -> int:
    """十三幺向听数

    需要 13 种幺九牌各至少 1 张 + 其中 1 种重复（做将）。
    shanten = 13 - unique_orphans - (1 if any has 2+ else 0)
    """
    if len(tiles) < 13:
        return 13

    orphans_in_hand = set()
    pair_found = False
    counts = Counter(tiles)

    for code in THIRTEEN_ORPHANS_SET:
        if code in counts:
            orphans_in_hand.add(code)
            if counts[code] >= 2:
                pair_found = True

    # 非幺九牌不计数（这些牌对十三幺无用）
    return 13 - len(orphans_in_hand) - (1 if pair_found else 0)


# ── 组合龙向听数 ─────────────────────────────────────

def shanten_composite_dragon(tiles: List[int]) -> int:
    """组合龙向听数（简化版）

    组合龙需要：3 个 147/258/369 的序列（跨花色）。
    向听数 = 9 - 已获得的点数组合数

    TODO: Phase 2 完整实现
    """
    return 8  # 保守估计，不会比面子手好


# ── 统一入口 ─────────────────────────────────────────

def calculate_shanten(tiles: List[int],
                      melds: Optional[List[List[int]]] = None,
                      draw_tile: Optional[int] = None) -> Dict[str, int]:
    """计算所有向听数值（带缓存）"""
    key = (tuple(sorted(tiles)),
           tuple(tuple(sorted(m)) for m in (melds or [])),
           draw_tile)
    return dict(_calculate_shanten_cached(*key))


@lru_cache(maxsize=5000)
def _calculate_shanten_cached(tiles_tuple: Tuple[int, ...],
                               melds_tuple: Tuple[Tuple[int, ...], ...] = (),
                               draw_tile: Optional[int] = None) -> Tuple[Tuple[str, int], ...]:
    """缓存的向听数计算"""
    tiles = list(tiles_tuple)
    melds = [list(m) for m in melds_tuple] if melds_tuple else []
    if melds is None:
        melds = []

    all_tiles = sorted(tiles)
    if draw_tile is not None:
        all_tiles.append(draw_tile)
        all_tiles.sort()

    # 牌计数
    counts = Counter(all_tiles)

    results = {
        "standard": shanten_standard(counts, melds),
        "seven_pairs": shanten_seven_pairs(all_tiles),
        "thirteen_orphans": shanten_thirteen_orphans(all_tiles),
        "composite_dragon": shanten_composite_dragon(all_tiles),
    }

    results["min"] = min(results.values())
    return results


def is_tenpai(tiles: List[int], melds: Optional[List[List[int]]] = None) -> bool:
    """是否听牌（任意向听数 = 0）"""
    shanten = calculate_shanten(tiles, melds)
    return shanten["min"] == 0


# ── 进张数计算 ───────────────────────────────────────

def calculate_acceptance(tiles: List[int],
                         melds: Optional[List[List[int]]] = None,
                         remaining: Optional[Dict[int, int]] = None) -> int:
    """计算进张数：能降低向听数的剩余牌数

    Args:
        tiles: 当前手牌（13 张）
        melds: 副露
        remaining: 剩余牌池 {编码: 张数}，None=全量

    Returns:
        进张张数
    """
    if melds is None:
        melds = []

    current_shanten = calculate_shanten(tiles, melds)["min"]

    if current_shanten == -1:
        return 0

    acceptance = 0
    # 遍历所有可能摸到的牌
    for code in range(encode(WAN, 1), encode(JIAN, 3) + 4):  # 所有可能的牌
        if remaining is not None:
            available = remaining.get(code, 0)
        else:
            suit, r = decode(code)
            if suit == FENG:
                available = 3
            else:
                available = 4

        if available == 0:
            continue

        # 用 draw_tile 参数（不修改 tiles 长度）
        new_shanten = calculate_shanten(tiles, melds, draw_tile=code)["min"]

        if new_shanten < current_shanten:
            acceptance += available

    return acceptance


# ── 候选出牌评估 ──────────────────────────────────────

def discard_analysis(tiles: List[int],
                     melds: Optional[List[List[int]]] = None,
                     remaining: Optional[Dict[int, int]] = None) -> List[Dict]:
    """候选出牌评估：对每张可打出的牌，计算打后向听数 + 进张数

    Args:
        tiles: 手牌（13 或 14 张）
        melds: 副露
        remaining: 剩余牌池

    Returns:
        [(出牌编码, 打后向听数, 进张数, 牌名), ...]，按评分排序
    """
    if melds is None:
        melds = []

    current_shanten = calculate_shanten(tiles, melds)["min"]

    results = []
    unique_tiles = set(tiles)

    for discard in unique_tiles:
        # 模拟打出这张牌
        new_tiles = list(tiles)
        new_tiles.remove(discard)
        new_tiles.sort()

        # 计算打后向听数
        post_discard_shanten = calculate_shanten(new_tiles, melds)["min"]

        # 如果打后向听数变差，跳过
        if post_discard_shanten > current_shanten + 1 and post_discard_shanten > 0:
            continue

        # 计算进张数（打后听牌/上听的牌数量）
        acceptance = calculate_acceptance(new_tiles, melds, remaining)

        from core.tile import tile_name
        results.append({
            "discard": discard,
            "name": tile_name(discard),
            "post_shanten": post_discard_shanten,
            "acceptance": acceptance,
        })

    # 先按向听数（小→大），再按进张数（大→小）
    results.sort(key=lambda r: (r["post_shanten"], -r["acceptance"]))
    return results
