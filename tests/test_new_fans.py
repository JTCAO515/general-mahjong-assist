"""测试新增番种（Batch 1: 11种）"""

import pytest
from core.tile import encode, WAN, TIAO, BING, FENG, JIAN
from core.hand_parser import Hand
from core.fan_calculator import (
    FanContext, calculate_fan,
)


def _w(rank: int) -> int: return encode(WAN, rank)
def _t(rank: int) -> int: return encode(TIAO, rank)
def _b(rank: int) -> int: return encode(BING, rank)
def _f(rank: int) -> int: return encode(FENG, rank)
def _j(rank: int) -> int: return encode(JIAN, rank)


class TestNewFans:

    def test_full_flush(self):
        """清一色 24番：全部万子"""
        tiles = [_w(1), _w(2), _w(3)] + [_w(3), _w(4), _w(5)] + \
                [_w(5), _w(6), _w(7)] + [_w(7), _w(8), _w(9)] + [_w(5)] * 2
        ctx = FanContext(hand=Hand(tiles), win_tile=_w(5))
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "清一色" in names

    def test_great_three_dragons(self):
        """大三元 48番：中发白各一刻"""
        tiles = [_j(1)] * 3 + [_j(2)] * 3 + [_j(3)] * 3 + \
                [_w(1), _w(2), _w(3)] + [_w(7)] * 2
        ctx = FanContext(hand=Hand(tiles), win_tile=_w(7))
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "大三元" in names

    def test_great_four_winds(self):
        """大四喜 64番：东南西北各一刻"""
        tiles = [_f(1)] * 3 + [_f(2)] * 3 + [_f(3)] * 3 + \
                [_f(4)] * 3 + [_t(5)] * 2
        ctx = FanContext(hand=Hand(tiles), win_tile=_t(5))
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "大四喜" in names

    def test_three_suit_same_sequence(self):
        """三色同顺 8番：123万 123条 123饼"""
        tiles = [_w(1), _w(2), _w(3)] + [_t(1), _t(2), _t(3)] + \
                [_b(1), _b(2), _b(3)] + [_w(5), _w(6), _w(7)] + [_w(9)] * 2
        ctx = FanContext(hand=Hand(tiles), win_tile=_w(9))
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "三色同顺" in names

    def test_three_suit_same_pung(self):
        """三色同刻 16番：111万 111条 111饼"""
        tiles = [_w(1)] * 3 + [_t(1)] * 3 + [_b(1)] * 3 + \
                [_w(8)] * 3 + [_w(5)] * 2
        ctx = FanContext(hand=Hand(tiles), win_tile=_w(5))
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "三色同刻" in names

    def test_one_suit_triple_steps(self):
        """一色三节高 24番：222万 333万 444万"""
        tiles = [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + \
                [_w(6), _w(7), _w(8)] + [_w(9)] * 2
        ctx = FanContext(hand=Hand(tiles), win_tile=_w(9))
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "一色三节高" in names

    def test_mixed_terminals(self):
        """混幺九 32番：只有幺九牌和字牌"""
        tiles = [_w(1)] * 3 + [_w(9)] * 3 + [_t(1)] * 3 + \
                [_b(9)] * 3 + [_f(1)] * 2
        ctx = FanContext(hand=Hand(tiles), win_tile=_f(1))
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "混幺九" in names

    def test_all_big(self):
        """全大 24番：全≥7"""
        tiles = [_w(7)] * 3 + [_b(8)] * 3 + [_t(9)] * 3 + \
                [_w(7), _w(8), _w(9)] + [_t(7)] * 2
        ctx = FanContext(hand=Hand(tiles), win_tile=_t(7))
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "全大" in names

    def test_all_middle(self):
        """全中 24番：全4-6"""
        tiles = [_w(4)] * 3 + [_w(5)] * 3 + [_w(6)] * 3 + \
                [_w(4), _w(5), _w(6)] + [_w(4)] * 2
        ctx = FanContext(hand=Hand(tiles), win_tile=_w(4))
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "全中" in names

    def test_all_small(self):
        """全小 24番：全≤3"""
        tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + \
                [_w(1), _w(2), _w(3)] + [_w(1)] * 2
        ctx = FanContext(hand=Hand(tiles), win_tile=_w(1))
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "全小" in names

    def test_all_melds_from_others(self):
        """全求人 6番：4副露+单钓点炮"""
        tiles = [_t(5), _t(5)]  # 单钓 + 点炮胡牌
        melds = [[_w(1)] * 3, [_w(2)] * 3, [_w(3), _w(4), _w(5)], [_b(7), _b(8), _b(9)]]
        ctx = FanContext(hand=Hand(tiles, melds), win_tile=_t(5),
                        is_self_drawn=False)
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "全求人" in names

    def test_all_melds_from_others_self_draw(self):
        """自摸不算全求人"""
        tiles = [_t(5), _t(5)]  # 2 identical = pair, 但自摸不算全求人
        melds = [[_w(1)] * 3, [_w(2)] * 3, [_w(3)] * 3, [_w(4)] * 3]
        ctx = FanContext(hand=Hand(tiles, melds), win_tile=_t(5),
                        is_self_drawn=True)
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "全求人" not in names

    def test_sea_floor_fish(self):
        """海底捞月 8番：最后一张自摸"""
        tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
                [_w(7), _w(8), _w(9)] + [_t(1), _t(2), _t(3)] + [_t(5)] * 2
        ctx = FanContext(hand=Hand(tiles), win_tile=_t(5),
                        is_last_draw=True, is_self_drawn=True)
        result = calculate_fan(ctx)
        names = [n for n, _ in result.items]
        assert "海底捞月" in names
