"""
九莲宝灯检测测试 (88番)
"""

from core.tile import WAN, TIAO, BING, FENG, encode
from core.hand_parser import Hand
from core.fan_calculator import FanContext, calculate_fan


def _make_hand(suit: int, dist: list) -> list:
    """根据点数分布构建手牌编码"""
    codes = []
    for i, cnt in enumerate(dist):
        if cnt > 0:
            codes.extend([encode(suit, i + 1)] * cnt)
    return codes


def _has_nine_gates(hand_codes, win_tile) -> bool:
    hand = Hand(hand_codes, [])
    ctx = FanContext(hand=hand, win_tile=win_tile, is_self_drawn=True)
    result = calculate_fan(ctx)
    return any("九莲" in n for n, _ in result.items)


class TestNineGates:
    """九莲宝灯检测"""

    def test_true_standard_extra_1(self):
        """1111 2345678999 万 (1万多1张)"""
        h = _make_hand(WAN, [4, 1, 1, 1, 1, 1, 1, 1, 3])
        assert _has_nine_gates(h, encode(WAN, 1))

    def test_true_standard_extra_9(self):
        """11123456789999 万 (9万多1张)"""
        h = _make_hand(WAN, [3, 1, 1, 1, 1, 1, 1, 1, 4])
        assert _has_nine_gates(h, encode(WAN, 9))

    def test_true_standard_extra_5(self):
        """111234556789999 万 (5万多1张)"""
        h = _make_hand(WAN, [3, 1, 1, 1, 2, 1, 1, 1, 3])
        assert _has_nine_gates(h, encode(WAN, 5))

    def test_true_listening_2(self):
        """1112 345678999 万 + 2万 (听 2 万胡牌)"""
        h = _make_hand(WAN, [3, 2, 1, 1, 1, 1, 1, 1, 3])
        assert _has_nine_gates(h, encode(WAN, 2))

    def test_true_listening_8(self):
        """1112345678999 万 + 8万 (听8万胡牌)"""
        h = _make_hand(WAN, [3, 1, 1, 1, 1, 1, 1, 2, 3])
        assert _has_nine_gates(h, encode(WAN, 8))

    def test_true_listening_9(self):
        """11123456789999 万 (听9万胡牌)"""
        h = _make_hand(WAN, [3, 1, 1, 1, 1, 1, 1, 1, 4])
        assert _has_nine_gates(h, encode(WAN, 9))

    def test_false_not_pure_suit(self):
        """含风牌的不是九莲宝灯"""
        h = _make_hand(WAN, [3, 1, 1, 1, 1, 1, 1, 1, 3])
        h.append(encode(FENG, 1))
        assert not _has_nine_gates(h, encode(FENG, 1))

    def test_false_two_suits(self):
        """两种花色的不是九莲"""
        h = _make_hand(WAN, [3, 1, 1, 1, 1, 1, 1, 1, 3])
        h.append(encode(TIAO, 1))
        assert not _has_nine_gates(h, encode(TIAO, 1))

    def test_false_normal_win(self):
        """正常胡牌不是九莲"""
        h = _make_hand(WAN, [3, 3, 3, 3, 2, 0, 0, 0, 0])
        assert not _has_nine_gates(h, encode(WAN, 5))  # 222 333 444 555 + 55将

    def test_false_bad_shape(self):
        """手牌分布不对 (123456789万各1+其他花色)"""
        # 123456789万(9张) + 111条(3张) + 1条将(2张) = 14
        h = _make_hand(WAN, [1, 1, 1, 1, 1, 1, 1, 1, 1])
        h.extend(_make_hand(TIAO, [3, 2, 0, 0, 0, 0, 0, 0, 0]))
        assert not _has_nine_gates(h, encode(TIAO, 1))

    def test_false_not_thirteen_shape(self):
        """同花色但分布不是 1112345678999 模式"""
        # 111 222 333 444 55万 → 5组顺子(非九莲)
        h = _make_hand(WAN, [3, 3, 3, 3, 2, 0, 0, 0, 0])
        assert not _has_nine_gates(h, encode(WAN, 4))

    def test_true_bing_suit(self):
        """饼子九莲宝灯"""
        h = _make_hand(BING, [3, 1, 1, 1, 1, 1, 1, 1, 4])
        assert _has_nine_gates(h, encode(BING, 9))

    def test_true_tiao_suit(self):
        """条子九莲宝灯"""
        h = _make_hand(TIAO, [4, 1, 1, 1, 1, 1, 1, 1, 3])
        assert _has_nine_gates(h, encode(TIAO, 1))

    def test_missing_foundation(self):
        """缺少基础牌型的不是九莲 (混一色 1112345678999 缺少1张1万)"""
        # 112345678999万 (12张) + 11条将(2张) = 14
        h = _make_hand(WAN, [2, 1, 1, 1, 1, 1, 1, 1, 3])
        h.extend(_make_hand(TIAO, [2, 0, 0, 0, 0, 0, 0, 0, 0]))
        assert not _has_nine_gates(h, encode(TIAO, 1))
