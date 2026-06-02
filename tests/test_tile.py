"""测试 tile.py — 牌编码/解码/牌池"""

import pytest
from core.tile import (
    encode, decode, tile_name, display, group_by_suit,
    full_pool, remaining_pool, count_available, TOTAL_TILES,
    WAN, TIAO, BING, FENG, JIAN,
)


class TestEncodeDecode:
    def test_encode_wan(self):
        """万 1-9 编码正确"""
        assert encode(WAN, 1) == 0
        assert encode(WAN, 9) == 32
        assert decode(0) == (WAN, 1)
        assert decode(32) == (WAN, 9)

    def test_encode_tiao(self):
        """条 1-9 编码正确"""
        assert encode(TIAO, 1) == 36
        assert encode(TIAO, 9) == 68
        assert decode(36) == (TIAO, 1)
        assert decode(68) == (TIAO, 9)

    def test_encode_bing(self):
        """饼 1-9 编码正确"""
        assert encode(BING, 1) == 72
        assert encode(BING, 9) == 104
        assert decode(72) == (BING, 1)
        assert decode(104) == (BING, 9)

    def test_encode_feng(self):
        """风牌编码正确"""
        assert encode(FENG, 1) == 108  # 东
        assert encode(FENG, 4) == 117  # 北
        assert decode(108) == (FENG, 1)
        assert decode(117) == (FENG, 4)

    def test_encode_jian(self):
        """箭牌编码正确"""
        assert encode(JIAN, 1) == 120  # 中
        assert encode(JIAN, 3) == 128  # 白
        assert decode(120) == (JIAN, 1)
        assert decode(128) == (JIAN, 3)

    def test_4_copies_per_tile(self):
        """每种万/条/饼 4 张, 风 3 张"""
        # 一万: 0, 1, 2, 3
        for code in range(0, 4):
            assert decode(code) == (WAN, 1)
        # 东: 108, 109, 110 (3张)
        for code in range(108, 111):
            assert decode(code) == (FENG, 1)

    def test_encode_decode_roundtrip(self):
        """所有编码解码回环正确——考虑风牌 3 张"""
        for code in range(TOTAL_TILES):
            suit, rank = decode(code)
            base = encode(suit, rank)
            count = 3 if suit == FENG else 4
            assert base <= code < base + count, \
                f"Roundtrip failed at code={code}: ({suit},{rank}) base={base} count={count}"

    def test_invalid_suit(self):
        with pytest.raises(ValueError):
            encode(5, 1)
        with pytest.raises(ValueError):
            encode(-1, 1)

    def test_invalid_rank(self):
        with pytest.raises(ValueError):
            encode(WAN, 0)
        with pytest.raises(ValueError):
            encode(WAN, 10)
        with pytest.raises(ValueError):
            encode(FENG, 5)
        with pytest.raises(ValueError):
            encode(JIAN, 4)

    def test_decode_out_of_range(self):
        with pytest.raises(ValueError):
            decode(-1)
        with pytest.raises(ValueError):
            decode(TOTAL_TILES)
        with pytest.raises(ValueError):
            decode(99999)


class TestTileName:
    def test_name_number_suits(self):
        assert tile_name(encode(WAN, 3)) == "3万"
        assert tile_name(encode(TIAO, 5)) == "5条"
        assert tile_name(encode(BING, 7)) == "7饼"

    def test_name_feng(self):
        assert tile_name(encode(FENG, 1)) == "东"
        assert tile_name(encode(FENG, 4)) == "北"

    def test_name_jian(self):
        assert tile_name(encode(JIAN, 1)) == "中"
        assert tile_name(encode(JIAN, 2)) == "发"
        assert tile_name(encode(JIAN, 3)) == "白"


class TestDisplay:
    def test_basic(self):
        hand = [encode(WAN, 1), encode(WAN, 1), encode(WAN, 5), encode(FENG, 1)]
        result = display(hand)
        assert "1万" in result
        assert "5万" in result
        assert "东" in result


class TestGroupBySuit:
    def test_group_all_suits(self):
        tiles = [
            encode(WAN, 1), encode(WAN, 2),
            encode(TIAO, 3),
            encode(BING, 5),
            encode(FENG, 1),
            encode(JIAN, 1),
        ]
        groups = group_by_suit(tiles)
        assert len(groups[WAN]) == 2
        assert len(groups[TIAO]) == 1
        assert len(groups[BING]) == 1
        assert len(groups[FENG]) == 1
        assert len(groups[JIAN]) == 1

    def test_empty_suit(self):
        tiles = [encode(WAN, 1)]
        groups = group_by_suit(tiles)
        assert len(groups[BING]) == 0


class TestFullPool:
    def test_total_count(self):
        pool = full_pool()
        # 万36×4 + 条36×4 + 饼36×4 + 风12×3 + 箭12×4 = 516
        assert len(pool) == 516, f"Expected 516, got {len(pool)}"

    def test_each_tile_four_times(self):
        pool = full_pool()
        from collections import Counter
        counts = Counter(pool)
        for code in range(TOTAL_TILES):
            suit, _ = decode(code)
            expected = 3 if suit == FENG else 4
            assert counts[code] == expected, f"Tile {code} has {counts[code]} copies"


class TestRemainingPool:
    def test_basic(self):
        hand = [encode(WAN, 1)] * 4  # 4张一万
        remaining = remaining_pool(hand)
        assert remaining[encode(WAN, 1)] == 0

    def test_with_discards(self):
        discards = {0: [encode(WAN, 1), encode(WAN, 2)]}
        remaining = remaining_pool([], discards)
        assert remaining[encode(WAN, 1)] == 3
        assert remaining[encode(WAN, 2)] == 3

    def test_no_negative(self):
        hand = [encode(WAN, 1)] * 5  # 超过4张（异常，但不应该返回负数）
        remaining = remaining_pool(hand)
        assert remaining[encode(WAN, 1)] == 0

    def test_count_available(self):
        remaining = {encode(WAN, 1): 2}
        assert count_available(encode(WAN, 1), remaining) == 2
        assert count_available(encode(WAN, 3), remaining) == 0


class TestTotalTiles:
    def test_total(self):
        # 万36 + 条36 + 饼36 + 风12 + 箭12 = 132
        assert TOTAL_TILES == 132, f"Expected 132, got {TOTAL_TILES}"

    def test_all_suits_covered(self):
        """所有编码都能 decode，且覆盖所有花色"""
        seen_suits = set()
        for code in range(TOTAL_TILES):
            suit, rank = decode(code)
            seen_suits.add(suit)
            assert 1 <= rank <= 9 if suit in (WAN, TIAO, BING) else \
                   1 <= rank <= 4 if suit == FENG else \
                   1 <= rank <= 3
        assert seen_suits == {WAN, TIAO, BING, FENG, JIAN}
