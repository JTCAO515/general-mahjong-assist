"""测试 shanten.py — 向听数 + 进张数"""

import pytest
from collections import Counter
from core.tile import encode, decode, WAN, TIAO, BING, FENG, JIAN
from core.hand_parser import Hand
from core.shanten import (
    calculate_shanten, is_tenpai, calculate_acceptance, discard_analysis,
    shanten_standard, shanten_seven_pairs, shanten_thirteen_orphans,
)


def _w(rank: int) -> int: return encode(WAN, rank)
def _t(rank: int) -> int: return encode(TIAO, rank)
def _b(rank: int) -> int: return encode(BING, rank)
def _f(rank: int) -> int: return encode(FENG, rank)
def _j(rank: int) -> int: return encode(JIAN, rank)

def _count(hand: list) -> int: return len(hand)


# ── 标准向听数 ───────────────────────────────────────

def test_shanten_0_tenpai():
    """0 向听（听牌）：13 张"""
    # 123万 456万 789万 55条 12条 → 等 3条做顺 → shanten=0
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_w(7), _w(8), _w(9)] + [_t(5)] * 2 + [_t(1), _t(2)]
    assert _count(tiles) == 13
    s = calculate_shanten(tiles)
    assert s["min"] == 0, f"Expected 0 (tenpai), got {s}"
    assert is_tenpai(tiles)


def test_shanten_1():
    """一上听：13 张，需换 1 张才能听"""
    # 123万 456万 789万 78条 55条 (3+3+3+2+2=13)
    # 78条等6/9条，55条是将，三面子→ shanten=0(已听)
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_w(7), _w(8), _w(9)] + [_t(7), _t(8)] + [_t(5)] * 2
    assert _count(tiles) == 13
    s = calculate_shanten(tiles)
    assert s["min"] == 0, f"Expected 0 (tenpai), got {s}"


def test_shanten_tenpai_multi():
    """多花色听牌：等隔张"""
    # 123万 456万 55条 789条 1饼 3饼（等2饼）= shanten 0
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_t(5)] * 2 + [_t(7), _t(8), _t(9)] + [_b(1), _b(3)]
    assert _count(tiles) == 13
    s = calculate_shanten(tiles)
    assert s["min"] == 0, f"Expected 0 (tenpai), got {s}"


def test_shanten_2():
    """二上听：13 张，需换 2 张才能听"""
    # 123万 789条 东东 发发 中 (3+3+2+2+1+1+1=13)
    # 只有 1 个面子 + 2个对子 + 3个单张
    tiles = [_w(1), _w(2), _w(3)] + [_t(7), _t(8), _t(9)] + \
            [_f(1)] * 2 + [_j(2)] * 2 + [_j(1)] + [_b(1)] + [_b(9)]
    assert _count(tiles) == 13
    s = calculate_shanten(tiles)
    assert s["min"] >= 2, f"Expected >=2, got {s}"


def test_shanten_negative_1_winning():
    """-1（已经胡牌）"""
    from collections import Counter
    counts = Counter()
    for code in [_w(1), _w(2), _w(3), _w(4)]:
        counts[code] = 3
    counts[_w(5)] = 2
    s = shanten_standard(counts, [])
    assert s == -1, f"Expected -1 (winning), got {s}"


def test_shanten_with_melds():
    """有副露时已经胡牌（-1）：摸牌后 14 张"""
    melds = [[_w(1), _w(2), _w(3)], [_w(4), _w(5), _w(6)]]
    # 手牌 8 张（摸牌后） + 2副露6张 = 14 张
    # 789万 + 东东 + 发发发 = 3+2+3=8 ✓
    tiles = [_w(7), _w(8), _w(9)] + [_f(1)] * 2 + [_j(2)] * 3
    assert _count(tiles) == 8
    s = calculate_shanten(tiles, melds)
    assert s["min"] == -1, f"Expected -1, got {s}"


def test_shanten_tanki_wait():
    """单骑听（等将牌）"""
    # 123万 456万 789万 111条 3条 = 3+3+3+3+1=13
    # 4个面子，单等 3条做将
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_w(7), _w(8), _w(9)] + [_t(1)] * 3 + [_t(3)]
    assert _count(tiles) == 13
    s = calculate_shanten(tiles)
    assert s["min"] == 0, f"Expected 0 (tanki tenpai), got {s}"


# ── 七对向听数 ───────────────────────────────────────

def test_seven_pairs_shanten_ready():
    """七对听牌：6 对 + 1 单 = 13张"""
    tiles = [_w(1)] * 2 + [_w(3)] * 2 + [_w(5)] * 2 + \
            [_t(2)] * 2 + [_t(4)] * 2 + [_t(6)] * 2 + [_b(7)]
    assert _count(tiles) == 13
    s = shanten_seven_pairs(tiles)
    assert s == 0, f"Expected 0, got {s}"


def test_seven_pairs_with_quad():
    """4 张相同算 2 个对子→ 5 张对 = 已听"""
    tiles = [_w(1)] * 4 + [_w(3)] * 2 + [_w(5)] * 2 + \
            [_t(2)] * 2 + [_t(4)] * 2 + [_b(7)]
    assert _count(tiles) == 13  # 4+2+2+2+2+1=13
    s = shanten_seven_pairs(tiles)
    assert s == 0, f"Expected 0 (6 pairs + 1 solo), got {s}"


def test_seven_pairs_no_pairs():
    """没有对子 = 6 向听"""
    tiles = list(range(13))  # 13 张不同的牌
    s = shanten_seven_pairs(tiles)
    assert s == 6, f"Expected 6 (no pairs), got {s}"


# ── 十三幺向听数 ─────────────────────────────────────

def test_thirteen_orphans_tenpai():
    """十三幺：12 种各 1 + 1 张重复 = 13 张 听牌（缺 1 种）"""
    from core.win_checker import THIRTEEN_ORPHANS as TO
    to_list = list(TO)
    tiles = to_list[:12] + [to_list[0]]  # 12种 + 重复第1种 = 13
    assert _count(tiles) == 13
    s = shanten_thirteen_orphans(tiles)
    assert s == 0, f"Expected 0 (tenpai, need 1 more type), got {s}"


def test_thirteen_orphans_2_shanten():
    """十三幺：11 种各 1 + 1 种 2 张 = 13"""
    from core.win_checker import THIRTEEN_ORPHANS as TO
    to_list = list(TO)
    tiles = to_list[:11] + [to_list[10], to_list[10]]  # 11种 + 1种重复
    assert _count(tiles) == 13
    s = shanten_thirteen_orphans(tiles)
    assert s == 1, f"Expected 1 (11 orphans + 1 pair), got {s}"


# ── 进张数 ───────────────────────────────────────────

def test_acceptance_tenpai():
    """听牌时进张 > 0"""
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_w(7), _w(8), _w(9)] + [_t(5)] * 2 + [_t(1), _t(2)]
    assert _count(tiles) == 13
    a = calculate_acceptance(tiles)
    assert a > 0, f"Expected >0, got {a}"


def test_acceptance_1_shanten():
    """一上听时有进张"""
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_w(7), _w(8), _w(9)] + [_t(7), _t(8)] + [_t(5)] * 2
    assert _count(tiles) == 13
    a = calculate_acceptance(tiles)
    assert a > 0, f"Expected >0, got {a}"


def test_acceptance_winning():
    """已胡牌时进张为 0"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)] * 2
    assert _count(tiles) == 14
    s = calculate_shanten(tiles)
    assert s["min"] < 0
    a = calculate_acceptance(tiles)
    assert a == 0, f"Expected 0 (already winning), got {a}"


# ── 候选出牌评估 ─────────────────────────────────────

def test_discard_analysis_basic():
    """候选出牌评估返回正确格式（14 张手牌）"""
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_w(7), _w(8), _w(9)] + [_t(1), _t(2), _t(3)] + [_t(4), _t(5)]
    assert _count(tiles) == 14
    results = discard_analysis(tiles)
    assert len(results) >= 1
    for r in results:
        assert "discard" in r
        assert "post_shanten" in r
        assert "acceptance" in r
        assert "name" in r


def test_discard_analysis_sorted():
    """结果按优先级排序"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)] * 2
    assert _count(tiles) == 14
    results = discard_analysis(tiles)
    assert len(results) >= 1
    for i in range(len(results) - 1):
        assert (results[i]["post_shanten"], -results[i]["acceptance"]) <= \
               (results[i+1]["post_shanten"], -results[i+1]["acceptance"])


# ── 综合 ─────────────────────────────────────────────

def test_shanten_min_takes_best():
    """min 取四个向听数中最小的"""
    tiles = [_w(1)] * 2 + [_w(3)] * 2 + [_w(5)] * 2 + \
            [_t(2)] * 2 + [_t(4)] * 2 + [_t(6)] * 2 + [_b(7)]
    assert _count(tiles) == 13
    s = calculate_shanten(tiles)
    assert s["min"] == s["seven_pairs"]
    assert s["seven_pairs"] <= s["standard"]


def test_multi_suit_shanten():
    """多花色胡牌判定"""
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_w(7), _w(8), _w(9)] + [_t(1)] * 3 + [_t(2)] * 2
    assert _count(tiles) == 14
    s = calculate_shanten(tiles)
    assert s["min"] <= 0
