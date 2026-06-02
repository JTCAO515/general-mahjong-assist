"""测试 fan_calculator.py — 88 番种算分"""

import pytest
from core.tile import encode, WAN, TIAO, BING, FENG, JIAN
from core.hand_parser import Hand
from core.fan_calculator import (
    FanContext, calculate_fan, list_all_fans, FanResult,
)


def _w(rank: int) -> int: return encode(WAN, rank)
def _t(rank: int) -> int: return encode(TIAO, rank)
def _b(rank: int) -> int: return encode(BING, rank)
def _f(rank: int) -> int: return encode(FENG, rank)
def _j(rank: int) -> int: return encode(JIAN, rank)


def test_list_all_fans():
    """列出所有已注册番种"""
    fans = list_all_fans()
    assert len(fans) >= 30, f"Expected 30+ fans, got {len(fans)}"
    # 检查几个关键番种
    names = [n for n, _ in fans]
    assert "七对" in names
    assert "碰碰和" in names
    assert "混一色" in names
    assert "平和" in names
    assert "断幺九" in names
    assert "自摸" in names


# ── 1 番 ─────────────────────────────────────────────

def test_self_drawn():
    """自摸 1 番"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_w(5), is_self_drawn=True)
    result = calculate_fan(ctx)
    assert any(name == "自摸" for name, _ in result.items)
    assert result.total >= 1


def test_not_self_drawn():
    """点炮没有自摸番"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_w(5), is_self_drawn=False, win_on_discard=True)
    result = calculate_fan(ctx)
    assert all(name != "自摸" for name, _ in result.items)


def test_no_honors():
    """无字 1 番"""
    # 123万 456万 789万 123条 44条 → 无字牌
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_w(7), _w(8), _w(9)] + [_t(1), _t(2), _t(3)] + [_t(4)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_t(4), is_self_drawn=False, win_on_discard=True)
    result = calculate_fan(ctx)
    # 应检测到无字 + 门前清
    names = [n for n, _ in result.items]
    assert "无字" in names


# ── 2 番 ─────────────────────────────────────────────

def test_no_terminals():
    """断幺九 2 番——没有幺九牌和字牌"""
    # 234万 345万 567条 678饼 22条 → 全是 2-8
    tiles = [_w(2), _w(3), _w(4)] + [_w(3), _w(4), _w(5)] + \
            [_t(5), _t(6), _t(7)] + [_b(6), _b(7), _b(8)] + [_t(2)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_t(2))
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "断幺九" in names, f"Expected 断幺九, got {names}"


def test_double_concealed_triplet():
    """双暗刻 2 番"""
    # 111万 222万 345万 678万 99万 = 刻子+刻子+顺子+顺子+对子
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3), _w(4), _w(5)] + \
            [_w(6), _w(7), _w(8)] + [_w(9)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_w(9))
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "双暗刻" in names, f"Expected 双暗刻, got {names}"


# ── 4 番 ─────────────────────────────────────────────

def test_ping_he():
    """平和 4 番"""
    # 全部顺子 + 序数牌对子，门清 + 点炮
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_w(7), _w(8), _w(9)] + [_t(1), _t(2), _t(3)] + [_t(4)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_t(4), win_on_discard=True, is_self_drawn=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "平和" in names, f"Expected 平和, got {names}"


def test_dragon_triplet():
    """箭刻 4 番（需要总分≥8才能通过calculate_fan）"""
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_j(1)] * 3 + [_t(1), _t(2), _t(3)] + [_t(4)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_t(4), is_self_drawn=True)
    result = calculate_fan(ctx)
    # 直接检查箭刻函数
    from core.fan_calculator import _check_dragon_triplet
    assert _check_dragon_triplet(ctx) == 4


def test_fuly_concealed():
    """门前清 4 番：门清+点炮"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_w(5), win_on_discard=True, is_self_drawn=False)
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "门前清" in names, f"Expected 门前清, got {names}"


# ── 6 番 ─────────────────────────────────────────────

def test_all_triplets():
    """碰碰和 6 番"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_w(5))
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "碰碰和" in names, f"Expected 碰碰和, got {names}"


def test_half_flush():
    """混一色 6 番：万字 + 字牌"""
    # 123万 456万 789万 东东东 发发
    tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
            [_w(7), _w(8), _w(9)] + [_f(1)] * 3 + [_j(2)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_j(2))
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "混一色" in names, f"Expected 混一色, got {names}"


def test_five_gates():
    """五门齐 6 番：万条饼风箭都有"""
    tiles = [_w(1)] * 3 + [_t(1)] * 3 + [_b(1)] * 3 + [_f(1)] * 3 + [_j(1)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_j(1))
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "五门齐" in names, f"Expected 五门齐, got {names}"


def test_double_dragon_triplet():
    """双箭刻 6 番：两个箭刻子"""
    # 111万 222万 中中中 发发发 白白 → 注意：3+3+3+3+2=14
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + \
            [_j(1)] * 3 + [_j(2)] * 3 + [_j(3)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_j(3))
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "双箭刻" in names, f"Expected 双箭刻, got {names}"


# ── 12 番 ────────────────────────────────────────────

def test_greater_than_five():
    """大于五 12 番"""
    tiles = [_w(6)] * 3 + [_w(7)] * 3 + [_w(8)] * 3 + [_w(9)] * 3 + [_t(6)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_t(6))
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "大于五" in names, f"Expected 大于五, got {names}"


def test_less_than_five():
    """小于五 12 番"""
    tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_t(1)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_t(1))
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "小于五" in names, f"Expected 小于五, got {names}"


# ── 24 番 ────────────────────────────────────────────

def test_seven_pairs_24_fan():
    """七对 24 番"""
    tiles = [_w(1)] * 2 + [_w(3)] * 2 + [_w(5)] * 2 + \
            [_t(2)] * 2 + [_t(4)] * 2 + [_t(6)] * 2 + [_b(7)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_b(7))
    result = calculate_fan(ctx)
    names = [n for n, _ in result.items]
    assert "七对" in names, f"Expected 七对, got {names}"
    # 七对应该有 24 番
    assert any(fan == 24 for name, fan in result.items if name == "七对")


# ── 非胡牌 ───────────────────────────────────────────

def test_not_a_winning_hand():
    """不是胡牌 → 0 番"""
    tiles = [_w(1)] * 13
    ctx = FanContext(hand=Hand(tiles), win_tile=_w(1))
    result = calculate_fan(ctx)
    assert result.total == 0


def test_less_than_8_fan():
    """小于 8 番不起胡"""
    # 111万 345万 678万 999条 55条 → 幺九刻2+双暗刻2+无字1+自摸1=6 < 8
    tiles = [_w(1)] * 3 + [_w(3), _w(4), _w(5)] + [_w(6), _w(7), _w(8)] + \
            [_t(9)] * 3 + [_t(5)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_t(5), is_self_drawn=True)
    result = calculate_fan(ctx)
    assert result.total == 0, f"Expected 0 (under 8), got {result.total} {result.items}"


# ── 组合扇区 ─────────────────────────────────────────

def test_ping_he_scores():
    """平和 + 无字 + 自摸 = 6 番 → 不够 8 起步"""
    # 这门清平和自摸只有 4+1+1 = 6 番（平和+无字+自摸）
    tiles = [_w(2), _w(3), _w(4)] + [_w(5), _w(6), _w(7)] + \
            [_t(1), _t(2), _t(3)] + [_t(4), _t(5), _t(6)] + [_t(7)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_t(7), is_self_drawn=True)
    result = calculate_fan(ctx)
    # 如果不够 8 番，应该返回 0
    names = [n for n, _ in result.items]
    # 可能不够起步番
    if result.total > 0:
        assert result.total >= 8


def test_half_flush_all_triplets():
    """碰碰和 6 + 断幺九 2 + 无字 1 = 9 番"""
    # 全部万 2-8 的刻子+对子（没有字牌→是清一色而非混一色）
    tiles = [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(6)] * 3 + [_w(8)] * 2
    ctx = FanContext(hand=Hand(tiles), win_tile=_w(8))
    result = calculate_fan(ctx)
    assert result.total >= 9, f"Expected >=9, got {result.total} {result.items}"
    names = [n for n, _ in result.items]
    assert "碰碰和" in names, f"Expected 碰碰和, got {names}"
    assert "断幺九" in names, f"Expected 断幺九, got {names}"
