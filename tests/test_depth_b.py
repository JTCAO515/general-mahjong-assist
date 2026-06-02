"""测试迭代 003b：追加 9 个番种"""

import sys
sys.path.insert(0, '.')

from core.tile import encode, decode, WAN, TIAO, BING, FENG, JIAN
from core.win_checker import (
    is_consecutive_seven_pairs, check_all_wins,
)
from core.hand_parser import Hand
from core.fan_calculator import FanContext, calculate_fan


# ── 连七对 ────────────────────────────────────────────

def test_consecutive_seven_pairs_valid():
    """连七对 88番：万 11223344556677"""
    tiles = [encode(WAN, r) for r in [1,1,2,2,3,3,4,4,5,5,6,6,7,7]]
    assert is_consecutive_seven_pairs(tiles)


def test_consecutive_seven_pairs_wrong_suit():
    """连七对：多花色失败"""
    tiles = [encode(WAN, r) for r in [1,1,2,2,3,3,4,4,5,5,6,6,7,7]]
    tiles[0] = encode(TIAO, 1)  # 换一个花色
    tiles[1] = encode(TIAO, 1)
    assert not is_consecutive_seven_pairs(tiles)


def test_consecutive_seven_pairs_not_consecutive():
    """连七对：不连续失败"""
    tiles = [encode(WAN, r) for r in [1,1,2,2,3,3,4,4,5,5,7,7,8,8]]  # 缺6
    assert not is_consecutive_seven_pairs(tiles)


def test_consecutive_seven_pairs_fan():
    """连七对 88番 番数计算"""
    tiles = [encode(WAN, r) for r in [1,1,2,2,3,3,4,4,5,5,6,6,7,7]]
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=tiles[0], is_self_drawn=True, is_first_draw=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "连七对" in names, f"Missing in {names}"
    assert result.total >= 88


# ── 十三幺(fan) ───────────────────────────────────────

def test_thirteen_orphans_fan_calc():
    """十三幺 88番 番数计算"""
    tiles = [
        encode(WAN, 1), encode(WAN, 9),
        encode(TIAO, 1), encode(TIAO, 9),
        encode(BING, 1), encode(BING, 9),
        encode(FENG, 1), encode(FENG, 2), encode(FENG, 3), encode(FENG, 4),
        encode(JIAN, 1), encode(JIAN, 2), encode(JIAN, 3),
        encode(WAN, 1),  # 重复万1当将
    ]
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=tiles[0], is_self_drawn=True, is_first_draw=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "十三幺" in names, f"Missing in {names}"


# ── 一色双龙会(fan) ──────────────────────────────────

def test_double_dragon_fan():
    """一色双龙会 88番 番数计算"""
    tiles = [
        encode(WAN, 1), encode(WAN, 1),
        encode(WAN, 2), encode(WAN, 2),
        encode(WAN, 3), encode(WAN, 3),
        encode(WAN, 5), encode(WAN, 5),
        encode(WAN, 7), encode(WAN, 7),
        encode(WAN, 8), encode(WAN, 8),
        encode(WAN, 9), encode(WAN, 9),
    ]
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=tiles[0], is_self_drawn=True, is_first_draw=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "一色双龙会" in names, f"Missing in {names}"


# ── 清幺九 ────────────────────────────────────────────

def test_pure_terminals():
    """清幺九 64番：只有 1/9 数牌 + 字牌"""
    tiles = [
        encode(WAN, 1), encode(WAN, 1), encode(WAN, 1),
        encode(WAN, 9), encode(WAN, 9), encode(WAN, 9),
        encode(TIAO, 1), encode(TIAO, 1), encode(TIAO, 1),
        encode(BING, 9), encode(BING, 9),
        encode(FENG, 1), encode(FENG, 2), encode(FENG, 2),
    ]  # 刻子+刻子+刻子+将+未完成... 实际需要标准胡牌
    # 标准胡牌布局：111万 999万 111条 99饼 东东
    tiles2 = [
        encode(WAN, 1), encode(WAN, 1), encode(WAN, 1),
        encode(WAN, 9), encode(WAN, 9), encode(WAN, 9),
        encode(TIAO, 1), encode(TIAO, 1), encode(TIAO, 1),
        encode(BING, 9), encode(BING, 9),
        encode(FENG, 1), encode(FENG, 1), encode(FENG, 1),
    ]
    h = Hand(tiles2)
    ctx = FanContext(hand=h, win_tile=tiles2[0], is_self_drawn=True)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "清幺九" in names, f"Missing in {names}"


# ── 一色四步高 ────────────────────────────────────────

def test_one_suit_four_step_sequences():
    """一色四步高 32番：同花色顺子起始点递增"""
    # 123万 234万 345万 456万 + 77万做将 = 14张
    tiles = [
        encode(WAN, 1), encode(WAN, 2), encode(WAN, 3),
        encode(WAN, 2), encode(WAN, 3), encode(WAN, 4),
        encode(WAN, 3), encode(WAN, 4), encode(WAN, 5),
        encode(WAN, 4), encode(WAN, 5), encode(WAN, 6),
        encode(WAN, 7), encode(WAN, 7),
    ]
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=tiles[0], is_self_drawn=True)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "一色四步高" in names, f"Missing in {names}"


# ── 三杠 ──────────────────────────────────────────────

def test_triple_kong():
    """三杠 32番：3个杠"""
    # 用副露模拟 3 个明杠
    melds = [
        [encode(WAN, 1)] * 4,
        [encode(WAN, 9)] * 4,
        [encode(TIAO, 5)] * 4,
    ]
    tiles = [encode(BING, 3), encode(BING, 3), encode(BING, 3),
             encode(BING, 7), encode(BING, 7)]  # 1刻 + 1将
    h = Hand(tiles, melds)
    ctx = FanContext(hand=h, win_tile=tiles[0], is_self_drawn=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "三杠" in names, f"Missing in {names}"


# ── 组合龙 ────────────────────────────────────────────

def test_composite_dragon_fan():
    """组合龙 12番 番数计算"""
    # 万147 + 条258 + 饼369 + 345万 + 77万 = 14
    tiles = [
        encode(WAN, 1), encode(WAN, 4), encode(WAN, 7),
        encode(TIAO, 2), encode(TIAO, 5), encode(TIAO, 8),
        encode(BING, 3), encode(BING, 6), encode(BING, 9),
        encode(WAN, 3), encode(WAN, 4), encode(WAN, 5),
        encode(WAN, 7), encode(WAN, 7),
    ]
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=tiles[0], is_self_drawn=True)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "组合龙" in names, f"Missing in {names}"


# ── 推不倒 ────────────────────────────────────────────

def test_undroppable():
    """推不倒 8番：全饼（243饼各3 + 5饼将 + 789饼顺子）"""
    tiles = [
        encode(BING, 2), encode(BING, 2), encode(BING, 2),
        encode(BING, 4), encode(BING, 4), encode(BING, 4),
        encode(BING, 5), encode(BING, 5),
        encode(BING, 7), encode(BING, 8), encode(BING, 9),
        encode(BING, 1), encode(BING, 2), encode(BING, 3),
    ]  # 222 444 123 789 + 55将
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=tiles[0], is_self_drawn=True)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "推不倒" in names, f"Missing in {names}"


# ── 和绝张 ────────────────────────────────────────────

def test_last_tile_win():
    """和绝张 4番：胡的牌手牌中已有 3 张"""
    # 111万 999万 123条 123条 + 1万 = 胡1万（已有3张）
    tiles = [
        encode(WAN, 1), encode(WAN, 1), encode(WAN, 1),  # 3张1万
        encode(WAN, 9), encode(WAN, 9), encode(WAN, 9),
        encode(TIAO, 1), encode(TIAO, 2), encode(TIAO, 3),
        encode(TIAO, 1), encode(TIAO, 2), encode(TIAO, 3),
        encode(WAN, 7), encode(WAN, 7),
    ]
    win_tile = encode(WAN, 1)
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=win_tile, is_self_drawn=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "和绝张" in names, f"Missing in {names}"
