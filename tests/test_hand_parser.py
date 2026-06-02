"""测试 hand_parser.py — 手牌解析"""

import pytest
from core.tile import encode, decode, WAN, TIAO, BING, FENG, JIAN
from core.hand_parser import (
    Hand, parse_hand, hand_to_string, count_by_suit,
    tiles_to_rank_array, find_sequences, find_triplets, find_pairs,
    suit_rank_counts,
)


def _w(rank: int) -> int: return encode(WAN, rank)
def _t(rank: int) -> int: return encode(TIAO, rank)
def _b(rank: int) -> int: return encode(BING, rank)
def _f(rank: int) -> int: return encode(FENG, rank)
def _j(rank: int) -> int: return encode(JIAN, rank)


class TestHand:
    def test_13_tiles(self):
        h = Hand([_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)])
        assert len(h) == 13

    def test_14_tiles_with_meld(self):
        """门清 14 张（摸牌后）"""
        h = Hand([_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)] * 2)
        assert len(h) == 14

    def test_with_melds(self):
        """有副露的 4 面子"""
        melds = [[_w(1), _w(2), _w(3)], [_t(4), _t(5), _t(6)]]
        h = Hand([_w(7), _w(7), _w(7), _w(8), _w(9), _f(1), _f(1)], melds)
        assert len(h.tiles) == 7
        assert h.is_declared

    def test_invalid_size(self):
        with pytest.raises(ValueError):
            Hand([_w(1)] * 16)

    def test_get_counts(self):
        h = Hand([_w(1)] * 3 + [_w(2)] * 2 + [_t(5)])
        assert h.counts[_w(1)] == 3
        assert h.counts[_w(2)] == 2
        assert h.counts[_t(5)] == 1

    def test_add_tile(self):
        h = Hand([_w(1)] * 13)
        h.add_tile(_w(1))
        assert len(h) == 14
        assert h.counts[_w(1)] == 14

    def test_remove_tile(self):
        h = Hand([_w(1)] * 3 + [_w(2)] * 10)
        assert h.remove_tile(_w(1))
        assert h.counts[_w(1)] == 2
        assert len(h) == 12

    def test_remove_nonexistent(self):
        h = Hand([_w(1)] * 13)
        assert not h.remove_tile(_w(9))

    def test_copy_independence(self):
        h = Hand([_w(1)] * 13)
        h2 = h.copy()
        h2.remove_tile(_w(1))
        assert len(h) == 13
        assert len(h2) == 12

    def test_suit_counts(self):
        h = Hand([_w(1)] * 3 + [_t(5)] * 2)
        assert h.suit_counts[WAN][1] == 3
        assert h.suit_counts[TIAO][5] == 2


class TestTileToRankArray:
    def test_basic(self):
        """万花色 → 点数张数数组"""
        counts = {
            _w(1): 3, _w(3): 2, _w(5): 1,
        }
        arr = tiles_to_rank_array(counts, WAN)
        assert arr[0] == 3   # 一万
        assert arr[2] == 2   # 三万
        assert arr[4] == 1   # 五万
        assert arr[8] == 0   # 九万

    def test_feng(self):
        """风牌只有 4 种点数"""
        counts = {_f(1): 2, _f(3): 3}
        arr = tiles_to_rank_array(counts, FENG, tile_count=4)
        assert arr[0] == 2   # 东
        assert arr[2] == 3   # 西
        assert arr[3] == 0   # 北

    def test_jian(self):
        """箭牌只有 3 种点数"""
        counts = {_j(1): 3, _j(3): 2}
        arr = tiles_to_rank_array(counts, JIAN, tile_count=3)
        assert arr[0] == 3   # 中
        assert arr[2] == 2   # 白


class TestFindSequences:
    def test_one_sequence(self):
        arr = [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
        seqs = find_sequences(arr)
        assert len(seqs) == 1
        assert seqs[0] == [1, 2, 3]

    def test_multiple_sequences(self):
        arr = [1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0]
        # 123 234 345 456 567 678 789
        seqs = find_sequences(arr)
        assert len(seqs) == 7

    def test_no_sequence(self):
        arr = [2, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0]
        seqs = find_sequences(arr)
        assert len(seqs) == 0

    def test_sequence_with_gaps(self):
        """135 不算顺子"""
        arr = [1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0]
        seqs = find_sequences(arr)
        assert len(seqs) == 0


class TestFindTriplets:
    def test_find_one(self):
        arr = [3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        assert find_triplets(arr) == [1]

    def test_find_multiple(self):
        arr = [3, 3, 0, 0, 1, 0, 0, 0, 0, 0, 0]
        assert find_triplets(arr) == [1, 2]

    def test_exact_2_not_triplet(self):
        arr = [2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        assert find_triplets(arr) == []


class TestFindPairs:
    def test_find_one(self):
        arr = [2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        assert find_pairs(arr) == [1]

    def test_find_4_as_pair(self):
        """4 张也算对子"""
        arr = [4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        assert find_pairs(arr) == [1]


class TestParseHand:
    def test_parse(self):
        tiles = [_w(1)] * 3 + [_w(2)] * 3 + [_w(3)] * 3 + [_w(4)] * 3 + [_w(5)]
        h = parse_hand(tiles)
        assert isinstance(h, Hand)
        assert len(h) == 13


class TestHandToString:
    def test_single_suit(self):
        s = hand_to_string([_w(1)] * 3 + [_w(2)] * 2)
        assert "1万" in s

    def test_multi_suit(self):
        s = hand_to_string([_w(1)] * 3 + [_t(5)] * 2 + [_f(1)])
        assert "东" in s or "1万" in s
        assert len(s) > 0


class TestCountBySuit:
    def test_basic(self):
        tiles = [_w(1)] * 5 + [_t(3)] * 3 + [_f(1)] * 2
        c = count_by_suit(tiles)
        assert c[WAN] == 5
        assert c[TIAO] == 3
        assert c[FENG] == 2
        assert c[BING] == 0
        assert c[JIAN] == 0


class TestSuitRankCounts:
    def test_basic(self):
        counts = {_w(1): 3, _w(3): 2, _t(5): 1}
        result = suit_rank_counts(counts, WAN)
        assert result[1] == 3
        assert result[3] == 2
        assert 5 not in result
