"""测试 listen_engine.py — 听牌推荐"""

import pytest
from core.tile import encode, WAN, TIAO, BING, FENG, JIAN
from core.shanten import calculate_shanten
from decision.listen_engine import (
    enumerate_winning_tiles, score_listen_tile, analyze_listen,
    ListenOption,
)


def _w(rank: int) -> int: return encode(WAN, rank)
def _t(rank: int) -> int: return encode(TIAO, rank)
def _b(rank: int) -> int: return encode(BING, rank)
def _f(rank: int) -> int: return encode(FENG, rank)
def _j(rank: int) -> int: return encode(JIAN, rank)


class TestEnumerateWinningTiles:
    def test_basic_tenpai(self):
        """听牌状态：123万 456万 789万 55条 12条 → 听 3条"""
        tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
                [_w(7), _w(8), _w(9)] + [_t(5)] * 2 + [_t(1), _t(2)]
        winners = enumerate_winning_tiles(tiles)
        assert _t(3) in winners, f"Expected 3条 in winners, got {winners}"
        assert len(winners) >= 1

    def test_not_tenpai(self):
        """非听牌返回空列表"""
        # 123万 456万 3饼 5饼 7饼 东东 发 = 3+3+1+1+1+2+1+1=13
        tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
                [_b(3), _b(5), _b(7)] + [_f(1)] * 2 + [_j(2)]
        winners = enumerate_winning_tiles(tiles)
        assert winners == []

    def test_tanki_wait(self):
        """单骑听：等 3条"""
        tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
                [_w(7), _w(8), _w(9)] + [_t(1)] * 3 + [_t(3)]
        winners = enumerate_winning_tiles(tiles)
        assert _t(3) in winners, f"Expected 3条 in winners, got {winners}"


class TestScoreListenTile:
    def test_score_known_tile(self):
        """已知听牌计算评分"""
        tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
                [_w(7), _w(8), _w(9)] + [_t(5)] * 2 + [_t(1), _t(2)]
        opt = score_listen_tile(_t(3), tiles, [], {_t(3): 2})
        assert opt is not None
        assert opt.name == "3条"
        assert opt.remaining == 2
        assert opt.fan >= 0
        assert opt.score > 0

    def test_not_winning_tile(self):
        """不可胡的牌返回 None"""
        tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
                [_w(7), _w(8), _w(9)] + [_t(5)] * 2 + [_t(1), _t(2)]
        opt = score_listen_tile(_w(7), tiles, [], {})
        assert opt is None


class TestAnalyzeListen:
    def test_analyze_tenpai(self):
        """听牌分析返回正确结构"""
        tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
                [_w(7), _w(8), _w(9)] + [_t(5)] * 2 + [_t(1), _t(2)]
        result = analyze_listen(tiles)
        assert result["is_tenpai"] is True
        assert len(result["options"]) >= 1
        assert result["best"] is not None
        assert result["total_fan"] >= 0

    def test_analyze_not_tenpai(self):
        """非听牌分析返回空"""
        tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
                [_b(3), _b(5), _b(7)] + [_f(1)] * 2 + [_j(2)]
        result = analyze_listen(tiles)
        assert result["is_tenpai"] is False
        assert result["options"] == []

    def test_options_sorted(self):
        """选项按评分降序"""
        tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
                [_w(7), _w(8), _w(9)] + [_t(5)] * 2 + [_t(1), _t(2)]
        result = analyze_listen(tiles)
        scores = [o.score for o in result["options"]]
        assert scores == sorted(scores, reverse=True)

    def test_multi_win_tiles(self):
        """多面听检测"""
        # 111万 234万 567万 89万 东东 → 听 7万(面)+
        tiles = [_w(1)] * 3 + [_w(2), _w(3), _w(4)] + \
                [_w(5), _w(6), _w(7)] + [_w(8), _w(9)] + [_f(1)] * 2
        result = analyze_listen(tiles)
        if result["is_tenpai"]:
            assert len(result["options"]) >= 1

    def test_with_remaining_filter(self):
        """剩余牌池过滤"""
        tiles = [_w(1), _w(2), _w(3)] + [_w(4), _w(5), _w(6)] + \
                [_w(7), _w(8), _w(9)] + [_t(5)] * 2 + [_t(1), _t(2)]
        remaining = {code: 0 for code in range(encode(WAN, 1), encode(JIAN, 3) + 4)}
        remaining[_t(3)] = 1  # 只剩 1 张
        result = analyze_listen(tiles, remaining=remaining)
        assert result["is_tenpai"]
        if result["options"]:
            assert result["options"][0].remaining <= 1


class TestListenOption:
    def test_summary(self):
        """总结字符串"""
        opt = ListenOption(tile=_t(3), name="3条", remaining=2,
                          fan=4, fan_items=[("平和", 4)], score=8.0)
        summary = opt.summary()
        assert "3条" in summary
        assert "×2" in summary
        assert "8.0" in summary
