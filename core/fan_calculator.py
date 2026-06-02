"""
国标麻将 — 番数算分模块 (1998 规则 / 通行规则)

81 个番种按番值分组，每个番种是一个监听函数。
起胡门槛：8 番
封顶：88 番

使用方式：
    ctx = FanContext(hand=hand, win_tile=..., ...)
    result = calculate_fan(ctx)
    print(f"总番: {result.total}, 细项: {result.items}")
"""

from typing import Dict, List, Tuple, Optional, Set, Callable
from collections import Counter
from dataclasses import dataclass, field

from core.tile import (
    decode, encode,
    WAN, TIAO, BING, FENG, JIAN,
    TOTAL_TILES,
)
from core.hand_parser import Hand, tiles_to_rank_array, suit_rank_counts
from core.win_checker import (
    is_standard_win, is_seven_pairs, is_thirteen_orphans,
    is_composite_dragon, THIRTEEN_ORPHANS,
)


# ── 上下文 ───────────────────────────────────────────

@dataclass
class FanContext:
    """番数计算上下文

    Args:
        hand: 手牌对象
        win_tile: 胡牌牌编码
        is_self_drawn: 是否自摸
        is_first_draw: 是否为第一巡摸牌（天胡/地胡场景）
        is_last_draw: 是否为最后一张牌（海底捞月）
        is_kong_draw: 是否杠上开花
        is_robbing_kong: 是否抢杠胡
        seat_wind: 座位风 (1=东, 2=南, 3=西, 4=北)
        round_wind: 圈风 (1=东, 2=南, 3=西, 4=北)
        is_dealer: 是否庄家
        win_on_discard: 是否点炮胡（不是自摸）
        declared_win: 是否报听/立直后胡牌
        four_melds: 四个面子的编码列表（顺序无关）
        pair_tile: 将牌编码
    """
    hand: Hand
    win_tile: int
    is_self_drawn: bool = True
    is_first_draw: bool = False
    is_last_draw: bool = False
    is_kong_draw: bool = False
    is_robbing_kong: bool = False
    seat_wind: int = 1  # 默认东
    round_wind: int = 1  # 默认东圈
    is_dealer: bool = False
    win_on_discard: bool = False
    declared_win: bool = False
    four_melds: Optional[List[List[int]]] = None
    pair_tile: Optional[int] = None

    def __post_init__(self):
        """自动推断派生字段"""
        if not self.is_self_drawn and not self.win_on_discard:
            self.win_on_discard = True


@dataclass
class FanResult:
    """番数计算结果"""
    items: List[Tuple[str, int]] = field(default_factory=list)
    total: int = 0

    def add(self, name: str, fan: int):
        self.items.append((name, fan))
        self.total += fan

    def summary(self) -> str:
        parts = [f"{name} {fan}番" for name, fan in self.items]
        return f"{' + '.join(parts)} = {self.total}番"


# ── 注册系统 ─────────────────────────────────────────

FanChecker = Callable[[FanContext], int]

_fan_registry: Dict[int, List[Tuple[str, FanChecker]]] = {}

def register_fan(fan_value: int, name: str):
    """装饰器：注册一个番种检查函数"""
    def decorator(func: FanChecker):
        _fan_registry.setdefault(fan_value, []).append((name, func))
        return func
    return decorator


def list_all_fans() -> List[Tuple[str, int]]:
    """列出所有已注册的番种"""
    result = []
    for value in sorted(_fan_registry.keys(), reverse=True):
        for name, _ in _fan_registry[value]:
            result.append((name, value))
    return result


# ═══════════════════════════════════════════════════════
# ── 番种判定函数（按番值排序） ─────────────────────
# ═══════════════════════════════════════════════════════

# ── 辅助函数 ─────────────────────────────────────────

def _split_hand(ctx: FanContext) -> Tuple[Dict[int, int], List[List[int]]]:
    """拆分手牌为 {编码: 张数} + 面子列表"""
    all_tiles = sorted(ctx.hand.tiles)
    if ctx.hand.melds:
        for m in ctx.hand.melds:
            all_tiles.extend(m)
    all_tiles.sort()
    return Counter(all_tiles), ctx.hand.melds


def _suit_rank_set(counts: Dict[int, int]) -> Set[Tuple[int, int]]:
    """{(花色, 点数)} 集合"""
    result = set()
    for code, cnt in counts.items():
        s, r = decode(code)
        result.add((s, r))
    return result


def _count_sequences_in_suit(counts: Dict[int, int], suit: int) -> int:
    """计算一个花色中的顺子数量"""
    rank_arr = tiles_to_rank_array(counts, suit)
    seq_count = 0
    i = 0
    while i < 7:
        if rank_arr[i] > 0 and rank_arr[i+1] > 0 and rank_arr[i+2] > 0:
            seq_count += 1
            rank_arr[i] -= 1
            rank_arr[i+1] -= 1
            rank_arr[i+2] -= 1
        else:
            i += 1
    return seq_count


def _count_triplets_in_suit(counts: Dict[int, int], suit: int) -> int:
    """计算一个花色中的刻子数量"""
    rank_arr = tiles_to_rank_array(counts, suit)
    return sum(cnt // 3 for cnt in rank_arr if cnt >= 3)


def _has_terminal_or_honor(counts: Dict[int, int]) -> bool:
    """手牌中是否有幺九牌或字牌"""
    for code in counts:
        s, r = decode(code)
        if s in (FENG, JIAN):
            return True
        if r in (1, 9):
            return True
    return False


def _count_honor_triplets(counts: Dict[int, int]) -> int:
    """字牌刻子数量"""
    result = 0
    for code, cnt in counts.items():
        s, _ = decode(code)
        if s in (FENG, JIAN) and cnt >= 3:
            result += 1
    return result


def _is_all_sequences(ctx: FanContext) -> bool:
    """是否全是顺子（没有刻子/杠子）"""
    counts, melds = _split_hand(ctx)
    for code, cnt in counts.items():
        # 字牌不能全是顺子
        s, _ = decode(code)
        if s in (FENG, JIAN) and cnt > 0:
            return False
        if cnt >= 3:
            return False  # 有刻子
    for m in melds:
        if m[0] == m[1]:  # 刻子/杠子
            return False
    return True


def _is_concealed(ctx: FanContext) -> bool:
    """是否门清（没有吃碰杠）"""
    return len(ctx.hand.melds) == 0


# ═══════════════════════════════════════════════════════
# 88 番
# ═══════════════════════════════════════════════════════

@register_fan(88, "天胡")
def _check_heaven(ctx: FanContext) -> int:
    """庄家起手 14 张直接胡牌"""
    return 88 if ctx.is_dealer and ctx.is_first_draw and ctx.is_self_drawn else 0


@register_fan(88, "地胡")
def _check_earth(ctx: FanContext) -> int:
    """闲家起手第一巡点炮胡"""
    return 88 if not ctx.is_dealer and ctx.is_first_draw and not ctx.is_self_drawn else 0


@register_fan(88, "人胡")
def _check_human(ctx: FanContext) -> int:
    """闲家第一巡自摸"""
    return 88 if not ctx.is_dealer and ctx.is_first_draw and ctx.is_self_drawn else 0


@register_fan(88, "四杠子")
def _check_four_kongs(ctx: FanContext) -> int:
    """4 个杠子"""
    melds = ctx.hand.melds
    if len(melds) != 4:
        return 0
    # 每个面子长度 4 才是杠子
    return 88 if all(len(m) == 4 for m in melds) else 0


@register_fan(88, "九莲宝灯")
def _check_nine_gates(ctx: FanContext) -> int:
    """同花色 1112345678999 + 同花色任意 1 张"""
    counts, melds = _split_hand(ctx)
    # 九莲必须门清
    if melds:
        return 0
    # 必须只有 1 个花色
    suits_used = set()
    for code in counts:
        s, _ = decode(code)
        suits_used.add(s)
    number_suits = suits_used - {FENG, JIAN}
    if len(number_suits) != 1 or len(suits_used - number_suits) > 0:
        return 0

    suit = list(number_suits)[0]
    rank_arr = tiles_to_rank_array(counts, suit)
    # 1112345678999 模式：1:3, 9:3, 2-8:1
    target = [3, 1, 1, 1, 1, 1, 1, 1, 3]
    for i in range(9):
        if rank_arr[i] > target[i]:
            return 0
    # 所有牌都要匹配
    total_extra = sum(rank_arr[i] - target[i] for i in range(9) if rank_arr[i] > target[i])
    return 88 if total_extra == 0 else 0


@register_fan(88, "绿一色")
def _check_all_green(ctx: FanContext) -> int:
    """全是绿色牌：2,3,4,6,8条 + 发"""
    green_ranks = {2, 3, 4, 6, 8}
    counts, melds = _split_hand(ctx)
    for code in counts:
        s, r = decode(code)
        if s == TIAO:
            if r not in green_ranks:
                return 0
        elif s == JIAN:
            if r != 2:  # 发财
                return 0
        else:
            return 0
    return 88


# ═══════════════════════════════════════════════════════
# 64 番
# ═══════════════════════════════════════════════════════

@register_fan(64, "小四喜")
def _check_little_four_winds(ctx: FanContext) -> int:
    """3 个风刻子 + 1 个风对子"""
    counts, melds = _split_hand(ctx)
    wind_triplets = 0
    wind_pair = False
    for rank in range(1, 5):
        code = encode(FENG, rank)  # 任何一种风（取第一个副本）
        real_code = encode(FENG, rank)  # 编码都一样
        # 检查手牌中的风
        cnt = sum(c for c_code, c in counts.items() if decode(c_code)[0] == FENG and decode(c_code)[1] == rank)
        if cnt >= 3:
            wind_triplets += 1
        elif cnt == 2:
            wind_pair = True
    return 64 if wind_triplets == 3 and wind_pair else 0


@register_fan(64, "小三元")
def _check_little_three_dragons(ctx: FanContext) -> int:
    """2 个箭刻子 + 1 个箭对子"""
    counts, melds = _split_hand(ctx)
    dragon_triplets = 0
    dragon_pair = False
    for rank in range(1, 4):
        cnt = sum(c for c_code, c in counts.items() if decode(c_code)[0] == JIAN and decode(c_code)[1] == rank)
        if cnt >= 3:
            dragon_triplets += 1
        elif cnt == 2:
            dragon_pair = True
    return 64 if dragon_triplets == 2 and dragon_pair else 0


# ═══════════════════════════════════════════════════════
# 48 番
# ═══════════════════════════════════════════════════════

def _check_identical_sequences(ctx: FanContext, count: int) -> int:
    """同花色 N 组相同顺子"""
    if not _is_concealed(ctx):
        return 0
    counts, melds = _split_hand(ctx)
    for suit in [WAN, TIAO, BING, FENG, JIAN]:
        rank_arr = tiles_to_rank_array(counts, suit)
        for i in range(7):
            if rank_arr[i] >= count and rank_arr[i+1] >= count and rank_arr[i+2] >= count:
                return 1  # 标记找到即可
    return 0


# ═══════════════════════════════════════════════════════
# 32 番
# ═══════════════════════════════════════════════════════

@register_fan(32, "七星不靠")
def _check_seven_stars(ctx: FanContext) -> int:
    """7 种字牌各 1 + 数牌间格 2+"""
    # TODO: Phase 2 完整实现
    return 0


# ═══════════════════════════════════════════════════════
# 24 番
# ═══════════════════════════════════════════════════════

@register_fan(24, "七对")
def _check_seven_pairs_fan(ctx: FanContext) -> int:
    """七对子"""
    return 24 if is_seven_pairs(ctx.hand.tiles, ctx.hand.melds) else 0


@register_fan(24, "一色三同顺")
def _check_one_suit_triple_sequence(ctx: FanContext) -> int:
    """同花色 3 组相同顺子"""
    counts, melds = _split_hand(ctx)
    if not _is_concealed(ctx):
        return 0
    for suit in [WAN, TIAO, BING]:
        rank_arr = tiles_to_rank_array(counts, suit)
        for i in range(7):
            if rank_arr[i] >= 3 and rank_arr[i+1] >= 3 and rank_arr[i+2] >= 3:
                return 24
    return 0


# ═══════════════════════════════════════════════════════
# 16 番
# ═══════════════════════════════════════════════════════

@register_fan(16, "青龙")
def _check_green_dragon(ctx: FanContext) -> int:
    """同花色 123 456 789 三副顺子"""
    counts, melds = _split_hand(ctx)
    for suit in [WAN, TIAO, BING]:
        rank_arr = tiles_to_rank_array(counts, suit)
        # 检查是否同时包含 123, 456, 789
        if (rank_arr[0] > 0 and rank_arr[1] > 0 and rank_arr[2] > 0 and
            rank_arr[3] > 0 and rank_arr[4] > 0 and rank_arr[5] > 0 and
            rank_arr[6] > 0 and rank_arr[7] > 0 and rank_arr[8] > 0):
            return 16
    return 0


# ═══════════════════════════════════════════════════════
# 12 番
# ═══════════════════════════════════════════════════════

@register_fan(12, "全不靠")
def _check_all_unrelated(ctx: FanContext) -> int:
    """全不靠：3 种花色各 1-4-7, 2-5-8, 3-6-9 + 7 张字牌"""
    # TODO: Phase 2
    return 0


@register_fan(12, "大于五")
def _check_greater_than_five(ctx: FanContext) -> int:
    """所有数牌 > 5（6,7,8,9），无字牌"""
    counts, melds = _split_hand(ctx)
    for code in counts:
        s, r = decode(code)
        if s in (FENG, JIAN):
            return 0
        if r <= 5:
            return 0
    return 12


@register_fan(12, "小于五")
def _check_less_than_five(ctx: FanContext) -> int:
    """所有数牌 < 5（1,2,3,4），无字牌"""
    counts, melds = _split_hand(ctx)
    for code in counts:
        s, r = decode(code)
        if s in (FENG, JIAN):
            return 0
        if r >= 5:
            return 0
    return 12


# ═══════════════════════════════════════════════════════
# 8 番
# ═══════════════════════════════════════════════════════

@register_fan(8, "花龙")
def _check_flower_dragon(ctx: FanContext) -> int:
    """三种花色各一个顺子组成 1-9"""
    counts, melds = _split_hand(ctx)
    suits_with_123 = 0
    suits_with_456 = 0
    suits_with_789 = 0
    for suit in [WAN, TIAO, BING]:
        rank_arr = tiles_to_rank_array(counts, suit)
        if rank_arr[0] > 0 and rank_arr[1] > 0 and rank_arr[2] > 0:
            suits_with_123 += 1
        if rank_arr[3] > 0 and rank_arr[4] > 0 and rank_arr[5] > 0:
            suits_with_456 += 1
        if rank_arr[6] > 0 and rank_arr[7] > 0 and rank_arr[8] > 0:
            suits_with_789 += 1
    return 8 if suits_with_123 >= 1 and suits_with_456 >= 1 and suits_with_789 >= 1 else 0


@register_fan(8, "杠上开花")
def _check_kong_bloom(ctx: FanContext) -> int:
    """杠后补牌胡"""
    return 8 if ctx.is_kong_draw else 0


@register_fan(8, "抢杠和")
def _check_rob_kong(ctx: FanContext) -> int:
    """抢别人加杠的牌胡"""
    return 8 if ctx.is_robbing_kong else 0


# ═══════════════════════════════════════════════════════
# 6 番
# ═══════════════════════════════════════════════════════

@register_fan(6, "碰碰和")
def _check_all_triplets(ctx: FanContext) -> int:
    """碰碰和：全部是刻子/杠子 + 将牌"""
    counts, melds = _split_hand(ctx)
    # 检查面子：不能有顺子
    for m in melds:
        if len(set(m)) > 1:  # 顺子的编码不同
            return 0
    # 手牌：每张牌必须是 3 的倍数，最多 1 种剩 2 张（将牌）
    pair_found = False
    for code, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        while cnt >= 3:
            cnt -= 3
        if cnt == 2:
            if pair_found:
                return 0
            pair_found = True
        elif cnt > 0:
            return 0
    return 6 if pair_found else 0


@register_fan(6, "混一色")
def _check_half_flush(ctx: FanContext) -> int:
    """一种数牌 + 字牌"""
    counts, melds = _split_hand(ctx)
    number_suits = set()
    has_honor = False
    for code in counts:
        s, r = decode(code)
        if s in (FENG, JIAN):
            has_honor = True
        elif s in (WAN, TIAO, BING):
            number_suits.add(s)
        else:
            return 0
    return 6 if len(number_suits) == 1 and has_honor else 0


@register_fan(6, "五门齐")
def _check_five_gates(ctx: FanContext) -> int:
    """万条饼风箭五种花色齐全"""
    counts, melds = _split_hand(ctx)
    suits_used = set()
    for code in counts:
        s, r = decode(code)
        suits_used.add(s)
    return 6 if len(suits_used) == 5 else 0


@register_fan(6, "双箭刻")
def _check_double_dragon_triplet(ctx: FanContext) -> int:
    """两个箭刻子"""
    counts, melds = _split_hand(ctx)
    dragon_triplets = 0
    for rank in range(1, 4):
        cnt = sum(c for c_code, c in counts.items() if decode(c_code)[0] == JIAN and decode(c_code)[1] == rank)
        if cnt >= 3:
            dragon_triplets += 1
    return 6 if dragon_triplets >= 2 else 0


# ═══════════════════════════════════════════════════════
# 4 番
# ═══════════════════════════════════════════════════════

@register_fan(4, "全带幺")
def _check_pure_terminals(ctx: FanContext) -> int:
    """每个面子和对子都包含幺九牌或字牌"""
    counts, melds = _split_hand(ctx)
    for code in counts:
        s, r = decode(code)
        if s == WAN and r not in (1, 9):
            return 0
        if s == TIAO and r not in (1, 9):
            return 0
        if s == BING and r not in (1, 9):
            return 0
    return 4


@register_fan(4, "门前清")
def _check_fully_concealed(ctx: FanContext) -> int:
    """门清 + 点炮胡"""
    return 4 if _is_concealed(ctx) and ctx.win_on_discard else 0


@register_fan(4, "平和")
def _check_peace(ctx: FanContext) -> int:
    """平和：4 顺子 + 一对序数牌（非字牌），无刻子，门清"""
    if not _is_concealed(ctx):
        return 0
    counts, melds = _split_hand(ctx)
    # 必须全是顺子
    for suit in [WAN, TIAO, BING, FENG, JIAN]:
        rank_arr = tiles_to_rank_array(counts, suit)
        for i in range(9):
            if rank_arr[i] >= 3:
                return 0
    # 将牌不能是字牌
    for code, cnt in counts.items():
        s, r = decode(code)
        if cnt == 2:
            if s in (FENG, JIAN):
                return 0
    return 4


@register_fan(4, "箭刻")
def _check_dragon_triplet(ctx: FanContext) -> int:
    """箭刻子（中/发/白）"""
    counts, melds = _split_hand(ctx)
    for rank in range(1, 4):
        cnt = sum(c for c_code, c in counts.items() if decode(c_code)[0] == JIAN and decode(c_code)[1] == rank)
        if cnt >= 3:
            return 4
    return 0


# ═══════════════════════════════════════════════════════
# 2 番
# ═══════════════════════════════════════════════════════

@register_fan(2, "断幺九")
def _check_no_terminals(ctx: FanContext) -> int:
    """没有幺九牌和字牌（只有 2-8 的数牌）"""
    counts, melds = _split_hand(ctx)
    for code in counts:
        s, r = decode(code)
        if s in (FENG, JIAN):
            return 0
        if r in (1, 9):
            return 0
    return 2


@register_fan(2, "双暗刻")
def _check_double_concealed_triplet(ctx: FanContext) -> int:
    """2 个暗刻"""
    counts, melds = _split_hand(ctx)
    # 从 melds 中找暗刻（没有吃碰的刻子）
    # 暗刻在手牌中：count ≥ 3
    concealed = 0
    for code, cnt in counts.items():
        if cnt >= 3:
            concealed += 1
    return 2 if concealed >= 2 else 0


@register_fan(2, "一般高")
def _check_pure_sequence_double(ctx: FanContext) -> int:
    """同花色两组相同顺子（如 123 123 万）"""
    counts, melds = _split_hand(ctx)
    for suit in [WAN, TIAO, BING]:
        rank_arr = tiles_to_rank_array(counts, suit)
        for i in range(7):
            if rank_arr[i] >= 2 and rank_arr[i+1] >= 2 and rank_arr[i+2] >= 2:
                return 2
    return 0


@register_fan(2, "幺九刻")
def _check_terminal_honor_triplet(ctx: FanContext) -> int:
    """幺九牌或字牌的刻子"""
    counts, melds = _split_hand(ctx)
    for code, cnt in counts.items():
        s, r = decode(code)
        if cnt >= 3:
            if s in (FENG, JIAN) or r in (1, 9):
                return 2
    return 0


# ═══════════════════════════════════════════════════════
# 1 番
# ═══════════════════════════════════════════════════════

@register_fan(1, "自摸")
def _check_self_drawn(ctx: FanContext) -> int:
    """自摸胡牌"""
    return 1 if ctx.is_self_drawn else 0


@register_fan(1, "无字")
def _check_no_honors(ctx: FanContext) -> int:
    """没有字牌"""
    counts, melds = _split_hand(ctx)
    for code in counts:
        s, r = decode(code)
        if s in (FENG, JIAN):
            return 0
    return 1


# ═══════════════════════════════════════════════════════
# ── 新增番种（2026-06-02） ─────────────────────────
# ═══════════════════════════════════════════════════════

def _count_triplets_family(counts: Dict[int, int], suit: int) -> List[int]:
    """返回一个花色中有刻子的点数列表"""
    rank_arr = tiles_to_rank_array(counts, suit)
    return [i + 1 for i, c in enumerate(rank_arr) if c >= 3]


@register_fan(64, "大四喜")
def _check_great_four_winds(ctx: FanContext) -> int:
    """东南西北各一刻（或杠）"""
    counts, melds = _split_hand(ctx)
    triplets = _count_honor_triplets_by_suit(counts, FENG)
    for m in melds:
        s, _ = decode(m[0])
        if s == FENG and len(set(m)) == 1:
            triplets += 1
    return 64 if triplets >= 4 else 0


def _count_honor_triplets_by_suit(counts: Dict[int, int], suit: int) -> int:
    """计算某字牌花色的刻子数（按点数计）"""
    triplets = 0
    for code, cnt in counts.items():
        s, r = decode(code)
        if s == suit and cnt >= 3:
            triplets += 1
    return triplets


@register_fan(48, "大三元")
def _check_great_three_dragons(ctx: FanContext) -> int:
    """中发白各一刻（或杠）"""
    counts, melds = _split_hand(ctx)
    triplets = _count_honor_triplets_by_suit(counts, JIAN)
    for m in melds:
        s, _ = decode(m[0])
        if s == JIAN and len(set(m)) == 1:
            triplets += 1
    return 48 if triplets >= 3 else 0


@register_fan(32, "混幺九")
def _check_mixed_terminals(ctx: FanContext) -> int:
    """只有幺九牌和字牌"""
    counts, melds = _split_hand(ctx)
    for code in counts:
        s, r = decode(code)
        if s in (WAN, TIAO, BING) and r not in (1, 9):
            return 0
    for m in melds:
        s, r = decode(m[0])
        if s in (WAN, TIAO, BING) and r not in (1, 9):
            return 0
    return 32


@register_fan(24, "清一色")
def _check_full_flush(ctx: FanContext) -> int:
    """全部一种花色（万/条/饼），无字牌"""
    counts, melds = _split_hand(ctx)
    suits_in_hand = set()
    for code in counts:
        s, r = decode(code)
        if s in (FENG, JIAN):
            return 0
        suits_in_hand.add(s)
    for m in melds:
        s, r = decode(m[0])
        if s in (FENG, JIAN):
            return 0
        suits_in_hand.add(s)
    return 24 if len(suits_in_hand) == 1 else 0


@register_fan(24, "一色三节高")
def _check_one_suit_triple_steps(ctx: FanContext) -> int:
    """同花色三个连续点数的刻子"""
    counts, melds = _split_hand(ctx)
    for suit in [WAN, TIAO, BING]:
        rank_arr = tiles_to_rank_array(counts, suit)
        for i in range(7):
            if rank_arr[i] >= 3 and rank_arr[i+1] >= 3 and rank_arr[i+2] >= 3:
                return 24
    return 0


@register_fan(24, "全大")
def _check_all_big(ctx: FanContext) -> int:
    """所有数牌 ≥ 7，无字牌"""
    counts, melds = _split_hand(ctx)
    for code in counts:
        s, r = decode(code)
        if s in (FENG, JIAN):
            return 0
        if r < 7:
            return 0
    return 24


@register_fan(24, "全中")
def _check_all_middle(ctx: FanContext) -> int:
    """所有数牌 4-6，无字牌"""
    counts, melds = _split_hand(ctx)
    for code in counts:
        s, r = decode(code)
        if s in (FENG, JIAN):
            return 0
        if r < 4 or r > 6:
            return 0
    return 24


@register_fan(24, "全小")
def _check_all_small(ctx: FanContext) -> int:
    """所有数牌 ≤ 3，无字牌"""
    counts, melds = _split_hand(ctx)
    for code in counts:
        s, r = decode(code)
        if s in (FENG, JIAN):
            return 0
        if r > 3:
            return 0
    return 24


@register_fan(16, "三色同刻")
def _check_three_suit_same_pung(ctx: FanContext) -> int:
    """三种花色相同点数的刻子"""
    counts, melds = _split_hand(ctx)
    for rank in range(1, 10):
        count_suits = 0
        for suit in [WAN, TIAO, BING]:
            cnt = sum(c for c_code, c in counts.items()
                      if decode(c_code)[0] == suit and decode(c_code)[1] == rank)
            if cnt >= 3:
                count_suits += 1
        if count_suits >= 3:
            return 16
    return 0


@register_fan(8, "三色同顺")
def _check_three_suit_same_sequence(ctx: FanContext) -> int:
    """三种花色同一顺子（门清）"""
    if not _is_concealed(ctx):
        return 0
    counts, melds = _split_hand(ctx)
    for start in range(1, 8):
        count_suits = 0
        for suit in [WAN, TIAO, BING]:
            rank_arr = tiles_to_rank_array(counts, suit)
            if rank_arr[start-1] >= 1 and rank_arr[start] >= 1 and rank_arr[start+1] >= 1:
                count_suits += 1
        if count_suits >= 3:
            return 8
    return 0


@register_fan(8, "海底捞月")
def _check_last_draw(ctx: FanContext) -> int:
    """摸最后一张牌胡牌（自摸）"""
    return 8 if ctx.is_last_draw and ctx.is_self_drawn else 0


@register_fan(6, "全求人")
def _check_all_melds_from_others(ctx: FanContext) -> int:
    """全部吃碰杠 + 单钓点炮胡"""
    tiles, melds = ctx.hand.tiles, len(ctx.hand.melds)
    if melds < 4:
        return 0
    if ctx.is_self_drawn:
        return 0
    # 手牌必须是单钓（只有 2 张相同的牌）
    if len(tiles) != 2 or tiles[0] != tiles[1]:
        return 0
    return 6


# ═══════════════════════════════════════════════════════
# ── 新增番种 Batch 2（2026-06-02） ────────────────
# ═══════════════════════════════════════════════════════

def _wait_pattern(counts: Dict[int, int], suit: int,
                  win_tile: int) -> str:
    """判断听牌形状：边张/坎张/单钓"""
    s, r = decode(win_tile)
    # 单钓：将牌
    if s == suit:
        if counts.get(win_tile, 0) == 2:
            return "pair"
    # TODO: 完整判断需要知道面子结构
    return "other"


@register_fan(24, "全双刻")
def _check_all_even_pungs(ctx: FanContext) -> int:
    """全是偶数点数的刻子+将"""
    counts, melds = _split_hand(ctx)
    for m in melds:
        s, r = decode(m[0])
        if s in (WAN, TIAO, BING):
            if r % 2 == 1:
                return 0
    for code, cnt in counts.items():
        if cnt == 0:
            continue
        s, r = decode(code)
        if s in (WAN, TIAO, BING):
            if cnt >= 3 and r % 2 == 1:
                return 0
            if cnt == 2 and r % 2 == 1:
                return 0
    return 24


@register_fan(16, "一色三步高")
def _check_one_suit_three_steps(ctx: FanContext) -> int:
    """同花色 3 个递增顺子（如 123 234 345）"""
    if not _is_concealed(ctx):
        return 0
    counts, melds = _split_hand(ctx)
    for suit in [WAN, TIAO, BING]:
        base = tiles_to_rank_array(counts, suit)
        for start in range(1, 6):
            # 尝试提取 3 个连续递增顺子（从相同花色）
            arr = list(base)
            ok = True
            for offset in range(3):
                i = start - 1 + offset
                if arr[i] >= 1 and arr[i+1] >= 1 and arr[i+2] >= 1:
                    arr[i] -= 1
                    arr[i+1] -= 1
                    arr[i+2] -= 1
                else:
                    ok = False
                    break
            if ok:
                return 16
    return 0


@register_fan(16, "三暗刻")
def _check_three_concealed_pungs(ctx: FanContext) -> int:
    """3 个暗刻（门清时所有刻子都是暗刻）"""
    counts, melds = _split_hand(ctx)
    if _is_concealed(ctx):
        # 门清时，所有刻子都是暗刻
        concealed = 0
        for code, cnt in counts.items():
            s, r = decode(code)
            if cnt >= 3:
                concealed += 1
        return 16 if concealed >= 3 else 0
    # 有副露时，计算未副露的刻子
    concealed = 0
    for code, cnt in counts.items():
        if cnt >= 3:
            concealed += 1
    return 16 if concealed >= 3 else 0


@register_fan(12, "三风刻")
def _check_three_wind_pungs(ctx: FanContext) -> int:
    """3 个风牌刻子（东南西北任选 3）"""
    counts, melds = _split_hand(ctx)
    wind_triplets = _count_honor_triplets_by_suit(counts, FENG)
    for m in melds:
        s, _ = decode(m[0])
        if s == FENG and len(set(m)) == 1:
            wind_triplets += 1
    return 12 if wind_triplets >= 3 else 0


@register_fan(6, "三色三步高")
def _check_three_suit_three_steps(ctx: FanContext) -> int:
    """三种花色各一个递增顺子：如 123万 234条 345饼"""
    if not _is_concealed(ctx):
        return 0
    counts, melds = _split_hand(ctx)
    # 每种花色找一个顺子，起始点数依次 +1
    suits = [WAN, TIAO, BING]
    for start in range(1, 8):
        ok = True
        for i, suit in enumerate(suits):
            rank_arr = tiles_to_rank_array(counts, suit)
            s = start + i
            if s > 7:
                ok = False
                break
            if not (rank_arr[s-1] >= 1 and rank_arr[s] >= 1 and rank_arr[s+1] >= 1):
                ok = False
                break
        if ok:
            return 6
    return 0


@register_fan(4, "不求人")
def _check_self_drawn_concealed(ctx: FanContext) -> int:
    """门清自摸"""
    return 4 if _is_concealed(ctx) and ctx.is_self_drawn else 0


@register_fan(4, "喜相逢")
def _check_identical_sequence_two_suits(ctx: FanContext) -> int:
    """两种花色相同顺子（如 123万 123条）"""
    if not _is_concealed(ctx):
        return 0
    counts, melds = _split_hand(ctx)
    for start in range(1, 8):
        suits_have = 0
        for suit in [WAN, TIAO, BING]:
            rank_arr = tiles_to_rank_array(counts, suit)
            if rank_arr[start-1] >= 1 and rank_arr[start] >= 1 and rank_arr[start+1] >= 1:
                suits_have += 1
        if suits_have >= 2:
            return 4
    return 0


@register_fan(2, "双同刻")
def _check_two_suit_same_pung(ctx: FanContext) -> int:
    """两种花色相同点数的刻子"""
    counts, melds = _split_hand(ctx)
    for rank in range(1, 10):
        count_suits = 0
        for suit in [WAN, TIAO, BING]:
            cnt = sum(c for c_code, c in counts.items()
                      if decode(c_code)[0] == suit and decode(c_code)[1] == rank)
            if cnt >= 3:
                count_suits += 1
        if count_suits >= 2:
            return 2
    return 0


@register_fan(1, "连六")
def _check_six_consecutive(ctx: FanContext) -> int:
    """同花色 6 张连续点数（如 1-6 或 4-9）"""
    counts, melds = _split_hand(ctx)
    for suit in [WAN, TIAO, BING]:
        rank_arr = tiles_to_rank_array(counts, suit)
        for i in range(4):
            if all(rank_arr[i + j] >= 1 for j in range(6)):
                return 1
    return 0


@register_fan(1, "老少副")
def _check_young_old_side(ctx: FanContext) -> int:
    """同花色 123 + 789 """
    counts, melds = _split_hand(ctx)
    for suit in [WAN, TIAO, BING]:
        rank_arr = tiles_to_rank_array(counts, suit)
        if (rank_arr[0] >= 1 and rank_arr[1] >= 1 and rank_arr[2] >= 1 and
            rank_arr[6] >= 1 and rank_arr[7] >= 1 and rank_arr[8] >= 1):
            return 1
    return 0


@register_fan(1, "明杠")
def _check_exposed_kong(ctx: FanContext) -> int:
    """有明杠"""
    for m in ctx.hand.melds:
        if len(m) == 4:  # 杠
            # 明杠：碰后再摸到第4张
            return 1
    return 0


@register_fan(1, "单钓")
def _check_single_wait(ctx: FanContext) -> int:
    """单钓将：等一张牌当将"""
    if not _is_concealed(ctx):
        return 0
    # 手牌13张 + 点炮那张 = 14张胡牌
    # 单钓：等待的牌与手牌中已有的某张相同，组成将
    # 简单判断：手牌中只有 1 种牌数量为 1，且胡的就是那张牌
    counts, melds = _split_hand(ctx)
    # 不要胡牌那张
    tiles_no_win = list(ctx.hand.tiles)
    if ctx.win_tile in tiles_no_win:
        tiles_no_win.remove(ctx.win_tile)
    counts_no_win = Counter(tiles_no_win)
    singles = [code for code, cnt in counts_no_win.items() if cnt == 1]
    if len(singles) == 1 and singles[0] == ctx.win_tile:
        return 1
    return 0


# ═══════════════════════════════════════════════════════
# ── 计算入口 ───────────────────────────────────────
# ═══════════════════════════════════════════════════════

def calculate_fan(ctx: FanContext) -> FanResult:
    """计算总番数

    Args:
        ctx: 胡牌上下文

    Returns:
        FanResult: 包含所有符合的番种和总番数
    """
    result = FanResult()

    # 先检查是否是胡牌（非胡牌返回 0）
    all_tiles = sorted(ctx.hand.tiles)
    if ctx.hand.melds:
        for m in ctx.hand.melds:
            all_tiles.extend(m)

    if not is_any_win_fast(all_tiles, ctx.hand.melds):
        return result

    # 检测所有番种
    for fan_value in sorted(_fan_registry.keys(), reverse=True):
        for name, checker in _fan_registry[fan_value]:
            fan = checker(ctx)
            if fan > 0:
                result.add(name, fan)
                if result.total >= 88:
                    pass  # 到达上限仍继续检测
    # 起胡门槛
    if result.total < 8:
        result.items = []
        result.total = 0

    return result


def is_any_win_fast(tiles: List[int], melds: Optional[List[List[int]]] = None) -> bool:
    """快速胡牌检测（只检查标准/七对/十三幺）"""
    from core.win_checker import is_standard_win, is_seven_pairs, is_thirteen_orphans
    return (is_standard_win(tiles, melds) or
            is_seven_pairs(tiles, melds) or
            is_thirteen_orphans(tiles, melds))
