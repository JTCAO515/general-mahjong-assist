"""测试 win_checker.py — 胡牌检测"""

import pytest
from collections import Counter
from core.tile import encode, decode, WAN, TIAO, BING, FENG, JIAN
from core.win_checker import (
    is_standard_win, is_seven_pairs, is_thirteen_orphans,
    is_composite_dragon, check_all_wins, is_any_win,
    THIRTEEN_ORPHANS,
)


def _w(rank: int) -> int: return encode(WAN, rank)
def _t(rank: int) -> int: return encode(TIAO, rank)
def _b(rank: int) -> int: return encode(BING, rank)
def _f(rank: int) -> int: return encode(FENG, rank)
def _j(rank: int) -> int: return encode(JIAN, rank)


# ── 标准胡牌 ─────────────────────────────────────────

def test_standard_win_all_triplets():
    """111万 222万 333万 444万 55万 → 4 刻子 + 1 对子"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)] * 2
    assert is_standard_win(tiles)


def test_standard_win_all_sequences():
    """123万 456万 789万 123条 44条 → 4 顺子 + 1 对子"""
    tiles = [_w(1), _w(2), _w(3)] * 1 + \
            [_w(4), _w(5), _w(6)] * 1 + \
            [_w(7), _w(8), _w(9)] * 1 + \
            [_t(1), _t(2), _t(3)] * 1 + \
            [_t(4), _t(4)]
    assert is_standard_win(tiles)


def test_standard_win_honor_tiles():
    """123万 456万 东东东 中中中 白白 → 2 顺子 + 2 刻子(字牌) + 1 对子"""
    tiles = [_w(1), _w(2), _w(3),
             _w(4), _w(5), _w(6),
             _f(1)] * 3 + \
            [_j(1)] * 3 + \
            [_j(3)] * 2
    assert is_standard_win(tiles)


def test_standard_win_mixed():
    """混合顺子+刻子"""
    tiles = [_w(1)] * 3 + [_w(2), _w(3), _w(4)] + \
            [_t(5), _t(6), _t(7)] + [_b(1), _b(2), _b(3)] + \
            [_f(1), _f(1)]
    assert is_standard_win(tiles)


def test_standard_win_14_tiles():
    """14 张完整手牌"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)] * 2
    assert is_standard_win(tiles)


def test_standard_not_win_13_no_meld():
    """13 张门清（未胡）"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)]
    assert not is_standard_win(tiles)


def test_standard_not_win_waiting():
    """听牌状态（缺 1 张）"""
    # 123 456 789 123 45万 (听3/6万)
    tiles = [_w(1), _w(2), _w(3),
             _w(4), _w(5), _w(6),
             _w(7), _w(8), _w(9),
             _t(1), _t(2), _t(3),
             _w(4), _w(5)]
    assert not is_standard_win(tiles)


def test_standard_win_with_melds():
    """有副露的胡牌"""
    melds = [[_w(1), _w(2), _w(3)], [_w(4), _w(5), _w(6)]]
    tiles = [_w(7), _w(8), _w(9)] + [_f(1)] * 3 + [_j(1), _j(1)]
    assert is_standard_win(tiles, melds)


def test_standard_win_double_sequence():
    """123万 123万 (两组相同顺子)"""
    tiles = [_w(1)] * 2 + [_w(2)] * 2 + [_w(3)] * 2 + \
            [_t(4), _t(5), _t(6)] * 1 + \
            [_b(7), _b(8), _b(9)] * 1 + \
            [_f(1), _f(1)]
    assert is_standard_win(tiles)


def test_standard_win_with_gang_material():
    """4 张相同的牌（1111万 222万 333万 55万 66万）→ 可胡"""
    # 1111万 = 对子(1万×2) + 刻子(1万×2... )... 不对
    # 1111万 = 刻子+单张，要用这个赢需要能配对
    # 1111万 222万 333万 44万 55万 = 4+3+3+2+2 = 14张
    tiles = [_w(1)] * 4 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 2 + [_w(5)] * 2
    assert is_standard_win(tiles)


# ── 非胡牌（边界） ────────────────────────────────────

def test_not_enough_tiles():
    """5 张牌不可能胡"""
    assert not is_standard_win([_w(1)] * 3 + [_w(2)] * 2)


def test_too_many_tiles():
    """15 张牌不可能胡"""
    assert not is_standard_win([_w(1)] * 15)


def test_no_pair():
    """有面子但没有对子（每张牌只有 1 张）"""
    # 1万-9万 1条-4条 = 9+4=13张 → 加1张5条 = 14张
    # 每张牌只有1张，没有对子
    tiles_no_pair = [_w(1), _w(2), _w(3), _w(4), _w(5), _w(6), _w(7), _w(8), _w(9),
                     _t(1), _t(2), _t(3), _t(4), _t(5)]
    assert not is_standard_win(tiles_no_pair)


def test_broken_sequence():
    """缺张的序列不算顺子"""
    # 12_ 45_ 78_ ... 缺 3/6/9
    tiles = [_w(1), _w(2), _w(4), _w(5), _w(7), _w(8)] * 3
    assert not is_standard_win(tiles)


# ── 七对 ─────────────────────────────────────────────

def test_seven_pairs():
    """7 个不同的对子"""
    tiles = [_w(1)] * 2 + [_w(3)] * 2 + [_w(5)] * 2 + \
            [_t(2)] * 2 + [_t(4)] * 2 + [_t(6)] * 2 + \
            [_b(7)] * 2
    assert is_seven_pairs(tiles)


def test_seven_pairs_not_14():
    """不是 14 张就不是七对"""
    assert not is_seven_pairs([_w(1)] * 2)


def test_seven_pairs_with_quad():
    """4 张相同的牌算 2 个对子（有争议但国标允许）"""
    tiles = [_w(1)] * 4 + [_w(2)] * 2 + [_w(3)] * 2 + \
            [_t(4)] * 2 + [_t(5)] * 2 + [_t(6)] * 2
    assert is_seven_pairs(tiles)


def test_seven_pairs_with_meld():
    """七对不能有副露"""
    assert not is_seven_pairs([_w(1)] * 2 + [_w(2)] * 2 + [_w(3)] * 2 +
                               [_w(4)] * 2 + [_w(5)] * 2 + [_w(6)] * 2 +
                               [_w(7)] * 2,
                               melds=[[_t(1), _t(2), _t(3)]])


def test_seven_pairs_not_identical():
    """7 个对子，不是 14 张相同牌"""
    assert not is_seven_pairs([_w(1)] * 14)


# ── 十三幺 ───────────────────────────────────────────

def test_thirteen_orphans():
    """十三幺：13 种幺九牌各 1 张 + 其中 1 张重复"""
    tiles = list(THIRTEEN_ORPHANS) + [list(THIRTEEN_ORPHANS)[0]]
    assert is_thirteen_orphans(tiles)


def test_thirteen_orphans_not_enough():
    """缺 1 种不算十三幺"""
    tiles = list(THIRTEEN_ORPHANS)[:-1] + [list(THIRTEEN_ORPHANS)[0]] * 2
    assert not is_thirteen_orphans(tiles)


def test_thirteen_orphans_with_extra():
    """多 1 种不算十三幺"""
    tiles = list(THIRTEEN_ORPHANS) + [list(THIRTEEN_ORPHANS)[0]]
    tiles.append(encode(WAN, 2))  # 2万不是幺九
    assert not is_thirteen_orphans(tiles)


def test_thirteen_orphans_with_meld():
    """十三幺不能有副露"""
    tiles = list(THIRTEEN_ORPHANS) + [list(THIRTEEN_ORPHANS)[0]]
    assert not is_thirteen_orphans(tiles, melds=[[_t(1), _t(2), _t(3)]])


# ── 统一入口 ─────────────────────────────────────────

def test_check_all_wins():
    """check_all_wins 返回所有胡牌型"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)] * 2
    results = check_all_wins(tiles)
    assert results["standard"] is True
    assert all(isinstance(v, bool) for v in results.values())


def test_is_any_win():
    """胡牌时返回 True"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)] * 2
    assert is_any_win(tiles)


def test_is_any_win_not_win():
    """没胡时返回 False"""
    tiles = [_w(1)] * 13
    assert not is_any_win(tiles)


def test_seven_pairs_also_standard_win():
    """七对可能也是标准胡（看具体牌型）"""
    tiles = [_w(1)] * 2 + [_w(3)] * 2 + [_w(5)] * 2 + \
            [_t(2)] * 2 + [_t(4)] * 2 + [_t(6)] * 2 + \
            [_b(7)] * 2
    results = check_all_wins(tiles)
    assert results["seven_pairs"]
    # 七对不一定是标准胡（对子间无面子关系）
