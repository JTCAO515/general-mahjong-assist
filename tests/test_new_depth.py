"""测试新深度功能：全不靠/七星不靠/一色双龙会 + 新增番种"""

import sys
sys.path.insert(0, '.')

from core.tile import encode, decode, WAN, TIAO, BING, FENG, JIAN
from core.win_checker import (
    is_all_sequences_no_pairs, is_seven_stars,
    is_double_dragon_one_suit, check_all_wins,
)
from core.hand_parser import Hand
from core.fan_calculator import FanContext, calculate_fan, FanResult


# ── 全不靠 ─────────────────────────────────────────────

def test_all_unrelated_valid():
    """全不靠：数牌 147/258/369 各取若干 + 7 种字牌"""
    tiles = [
        encode(WAN, 1), encode(WAN, 4), encode(WAN, 7),
        encode(TIAO, 2), encode(TIAO, 5),
        encode(BING, 3), encode(BING, 6),
        encode(FENG, 1), encode(FENG, 2), encode(FENG, 3), encode(FENG, 4),
        encode(JIAN, 1), encode(JIAN, 2), encode(JIAN, 3),
    ]
    assert is_all_sequences_no_pairs(tiles)


def test_all_unrelated_reject_dup():
    """全不靠：有重复牌则失败"""
    tiles = [
        encode(WAN, 1), encode(WAN, 4), encode(WAN, 7),
        encode(TIAO, 2), encode(TIAO, 5),
        encode(BING, 3), encode(BING, 6),
        encode(FENG, 1), encode(FENG, 2), encode(FENG, 3), encode(FENG, 4),
        encode(JIAN, 1), encode(JIAN, 2), encode(JIAN, 1),  # 重复中
    ]
    assert not is_all_sequences_no_pairs(tiles)


def test_all_unrelated_not_14():
    """全不靠：不是14张则失败"""
    tiles = [encode(WAN, 1), encode(WAN, 4), encode(WAN, 7)]
    assert not is_all_sequences_no_pairs(tiles)


# ── 七星不靠 ──────────────────────────────────────────

def test_seven_stars_valid():
    """七星不靠：数牌 147/258/369 + 7 种字牌各 1"""
    tiles = [
        encode(WAN, 1), encode(WAN, 4), encode(WAN, 7),
        encode(TIAO, 2), encode(TIAO, 5),
        encode(BING, 3), encode(BING, 6),
        encode(FENG, 1), encode(FENG, 2), encode(FENG, 3), encode(FENG, 4),
        encode(JIAN, 1), encode(JIAN, 2), encode(JIAN, 3),
    ]
    assert is_seven_stars(tiles)


def test_seven_stars_missing_honor():
    """七星不靠：缺一种字牌则为全不靠而非七星不靠"""
    tiles = [
        encode(WAN, 1), encode(WAN, 4), encode(WAN, 7),
        encode(TIAO, 2), encode(TIAO, 5),
        encode(BING, 3), encode(BING, 6),
        encode(WAN, 2),  # 补到14张
        encode(FENG, 1), encode(FENG, 2), encode(FENG, 3),
        encode(JIAN, 1), encode(JIAN, 2), encode(JIAN, 3),
    ]  # 缺北风
    assert not is_seven_stars(tiles)
    # 但仍是全不靠（至少5种字牌）
    assert is_all_sequences_no_pairs(tiles)


# ── 一色双龙会 ────────────────────────────────────────

def test_double_dragon_valid():
    """一色双龙会：万 11223355778899"""
    tiles = [
        encode(WAN, 1), encode(WAN, 1),
        encode(WAN, 2), encode(WAN, 2),
        encode(WAN, 3), encode(WAN, 3),
        encode(WAN, 5), encode(WAN, 5),
        encode(WAN, 7), encode(WAN, 7),
        encode(WAN, 8), encode(WAN, 8),
        encode(WAN, 9), encode(WAN, 9),
    ]
    assert is_double_dragon_one_suit(tiles)


def test_double_dragon_wrong_suit():
    """一色双龙会：多花色则失败"""
    tiles = [
        encode(WAN, 1), encode(WAN, 1),
        encode(WAN, 2), encode(WAN, 2),
        encode(WAN, 3), encode(WAN, 3),
        encode(WAN, 5), encode(WAN, 5),
        encode(WAN, 7), encode(WAN, 7),
        encode(WAN, 8), encode(TIAO, 8),  # 不同花色
        encode(WAN, 9), encode(WAN, 9),
    ]
    assert not is_double_dragon_one_suit(tiles)


def test_double_dragon_has_honor():
    """一色双龙会：含字牌则失败"""
    tiles = [
        encode(WAN, 1), encode(WAN, 1),
        encode(WAN, 2), encode(WAN, 2),
        encode(WAN, 3), encode(WAN, 3),
        encode(WAN, 5), encode(WAN, 5),
        encode(WAN, 7), encode(WAN, 7),
        encode(WAN, 8), encode(WAN, 8),
        encode(WAN, 9), encode(FENG, 1),  # 有字牌
    ]
    assert not is_double_dragon_one_suit(tiles)


# ── 四暗刻 ────────────────────────────────────────────

def test_four_hidden_triplets_win():
    """四暗刻 64番：4个暗刻+1对，是标准胡牌"""
    tiles = [
        encode(WAN, 1), encode(WAN, 1), encode(WAN, 1),
        encode(WAN, 9), encode(WAN, 9), encode(WAN, 9),
        encode(TIAO, 5), encode(TIAO, 5), encode(TIAO, 5),
        encode(BING, 3), encode(BING, 3), encode(BING, 3),
        encode(FENG, 1), encode(FENG, 1),
    ]
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=tiles[0], is_self_drawn=True, is_first_draw=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "四暗刻" in names, f"Missing 四暗刻 in {names}"


# ── 一色四同顺 ────────────────────────────────────────

def test_one_suit_quad_sequence():
    """一色四同顺 48番：4组相同顺子"""
    tiles = [
        encode(WAN, 1), encode(WAN, 2), encode(WAN, 3),
        encode(WAN, 1), encode(WAN, 2), encode(WAN, 3),
        encode(WAN, 1), encode(WAN, 2), encode(WAN, 3),
        encode(WAN, 1), encode(WAN, 2), encode(WAN, 3),
        encode(WAN, 5), encode(WAN, 5),
    ]
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=tiles[0], is_self_drawn=True)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "一色四同顺" in names, f"Missing in {names}"


# ── 一色四节高 ────────────────────────────────────────

def test_one_suit_four_steps():
    """一色四节高 48番：4组连续递增刻子"""
    tiles = [
        encode(WAN, 2), encode(WAN, 2), encode(WAN, 2),
        encode(WAN, 3), encode(WAN, 3), encode(WAN, 3),
        encode(WAN, 4), encode(WAN, 4), encode(WAN, 4),
        encode(WAN, 5), encode(WAN, 5), encode(WAN, 5),
        encode(WAN, 6), encode(WAN, 6),
    ]
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=tiles[0])
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "一色四节高" in names, f"Missing in {names}"


# ── 圈风刻 ────────────────────────────────────────────

def test_round_wind_pung():
    """圈风刻 2番：东圈刻东（标准胡牌布局）"""
    # 111万 222万 333万 东东东 99万
    tiles = [
        encode(WAN, 1), encode(WAN, 1), encode(WAN, 1),
        encode(WAN, 2), encode(WAN, 2), encode(WAN, 2),
        encode(WAN, 3), encode(WAN, 3), encode(WAN, 3),
        encode(FENG, 1), encode(FENG, 1), encode(FENG, 1),
        encode(WAN, 9), encode(WAN, 9),
    ]
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=encode(WAN, 1),
                     round_wind=1, seat_wind=2)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "圈风刻" in names, f"Missing in {names}"


def test_seat_wind_pung():
    """门风刻 2番：南圈坐南"""
    tiles = [
        encode(WAN, 1), encode(WAN, 1), encode(WAN, 1),
        encode(WAN, 2), encode(WAN, 2), encode(WAN, 2),
        encode(WAN, 3), encode(WAN, 3), encode(WAN, 3),
        encode(FENG, 2), encode(FENG, 2), encode(FENG, 2),
        encode(WAN, 9), encode(WAN, 9),
    ]
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=encode(WAN, 1),
                     round_wind=1, seat_wind=2)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "门风刻" in names, f"Missing in {names}"


# ── 边张 / 坎张 ──────────────────────────────────────

def test_edge_wait_3():
    """边张 1番：点炮胡3，手牌有12"""
    # 12万等3万 + 234条567条789条 + 99条将 = 13张等3万
    wait_hand = [
        encode(WAN, 1), encode(WAN, 2),  # 等3万
        encode(TIAO, 2), encode(TIAO, 3), encode(TIAO, 4),
        encode(TIAO, 5), encode(TIAO, 6), encode(TIAO, 7),
        encode(TIAO, 7), encode(TIAO, 8), encode(TIAO, 9),
        encode(WAN, 9), encode(WAN, 9),  # 将
    ]
    assert len(wait_hand) == 13, f"wait_hand has {len(wait_hand)} tiles"
    win_tile = encode(WAN, 3)
    all_tiles = wait_hand + [win_tile]
    h = Hand(all_tiles)
    ctx = FanContext(hand=h, win_tile=win_tile, is_self_drawn=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "边张" in names, f"Missing in {names}"


def test_middle_wait():
    """坎张 1番：点炮胡3，手牌有24"""
    # 24万等3万 + 234条567条789条 + 99条将 = 13张等3万
    wait_hand = [
        encode(WAN, 2), encode(WAN, 4),  # 等3万
        encode(TIAO, 2), encode(TIAO, 3), encode(TIAO, 4),
        encode(TIAO, 5), encode(TIAO, 6), encode(TIAO, 7),
        encode(TIAO, 7), encode(TIAO, 8), encode(TIAO, 9),
        encode(WAN, 9), encode(WAN, 9),  # 将
    ]
    assert len(wait_hand) == 13, f"wait_hand has {len(wait_hand)} tiles"
    win_tile = encode(WAN, 3)
    all_tiles = wait_hand + [win_tile]
    h = Hand(all_tiles)
    ctx = FanContext(hand=h, win_tile=win_tile, is_self_drawn=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "坎张" in names, f"Missing in {names}"


# ── 七星不靠 番数计算 ────────────────────────

def test_seven_stars_fan():
    """七星不靠 32番 番数计算"""
    tiles = [
        encode(WAN, 1), encode(WAN, 4), encode(WAN, 7),
        encode(TIAO, 2), encode(TIAO, 5),
        encode(BING, 3), encode(BING, 6),
        encode(FENG, 1), encode(FENG, 2), encode(FENG, 3), encode(FENG, 4),
        encode(JIAN, 1), encode(JIAN, 2), encode(JIAN, 3),
    ]
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=tiles[0], is_self_drawn=True, is_first_draw=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "七星不靠" in names, f"Missing 七星不靠 in {names}"


# ── check_all_wins ──────────────────────────────────

def test_is_any_win_double_dragon():
    """一色双龙会：check_all_wins 返回 True"""
    tiles = [
        encode(WAN, 1), encode(WAN, 1),
        encode(WAN, 2), encode(WAN, 2),
        encode(WAN, 3), encode(WAN, 3),
        encode(WAN, 5), encode(WAN, 5),
        encode(WAN, 7), encode(WAN, 7),
        encode(WAN, 8), encode(WAN, 8),
        encode(WAN, 9), encode(WAN, 9),
    ]
    results = check_all_wins(tiles)
    assert results.get("double_dragon", False), f"一色双龙会 not detected: {results}"


# ── 全不靠 番数计算 ────────────────────────

def test_all_unrelated_fan():
    """全不靠 12番（6种字牌+8张数牌）"""
    tiles = [
        encode(WAN, 1), encode(WAN, 4), encode(WAN, 7),
        encode(TIAO, 2), encode(TIAO, 5),
        encode(BING, 3), encode(BING, 6), encode(BING, 9),
        encode(FENG, 1), encode(FENG, 2), encode(FENG, 3), encode(FENG, 4),
        encode(JIAN, 1), encode(JIAN, 2),
    ]  # 8数牌 + 6字牌 = 14
    assert len(tiles) == 14
    assert is_all_sequences_no_pairs(tiles)
    h = Hand(tiles)
    ctx = FanContext(hand=h, win_tile=tiles[0], is_self_drawn=True, is_first_draw=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "全不靠" in names, f"Missing 全不靠 in {names}"
    assert not any("七星不靠" in n for n, _ in result.items), "不应有七星不靠"
