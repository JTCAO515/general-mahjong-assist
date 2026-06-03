"""
国标麻将 — 牌编码模块

编码方案（单字节，0–135）：
  高 4 位 = 花色 (0=万, 1=条, 2=饼, 3=风, 4=箭)
  低 4 位 = 点数 (1–9 为数牌, 1–4=东南西北, 1–3=中发白)

  136 张索引：
    0–35:   万 1–9 × 4 张     (花色 0, 点数 1–9)
    36–71:  条 1–9 × 4 张     (花色 1, 点数 1–9)
    72–107: 饼 1–9 × 4 张     (花色 2, 点数 1–9)
    108–119: 风 东/南/西/北 × 3 张  (花色 3, 点数 1–4)
    120–131: 箭 中/发/白 × 4 张    (花色 4, 点数 1–3)
"""

from typing import List, Dict, Tuple, Optional

# ── 编码常量 ─────────────────────────────────────────
TILE_MASK   = 0x0F  # 低 4 位遮罩
SUIT_MASK   = 0xF0  # 高 4 位遮罩
SUIT_SHIFT  = 4

# 花色
WAN   = 0
TIAO  = 1
BING  = 2
FENG  = 3
JIAN  = 4

SUIT_NAMES = {WAN: "万", TIAO: "条", BING: "饼", FENG: "风", JIAN: "箭"}
SUIT_COUNT = 9  # 万/条/饼 各 9 种

# 各花色种类数 × 每种张数
WAN_TILES  = 9 * 4  # 36
TIAO_TILES = 9 * 4  # 36
BING_TILES = 9 * 4  # 36
FENG_TILES = 4 * 3  # 12 (东3 南3 西3 北3)
JIAN_TILES = 3 * 4  # 12 (中4 发4 白4)

TOTAL_TILES = WAN_TILES + TIAO_TILES + BING_TILES + FENG_TILES + JIAN_TILES  # 132

assert TOTAL_TILES == 132, f"Expected 132 tiles, got {TOTAL_TILES}"

# 花色边界索引
SUIT_BOUNDARIES = {
    WAN:  (0, 35),
    TIAO: (36, 71),
    BING: (72, 107),
    FENG: (108, 119),
    JIAN: (120, 131),
}

# 风牌名称映射
FENG_NAMES = {1: "东", 2: "南", 3: "西", 4: "北"}
# 箭牌名称映射
JIAN_NAMES = {1: "中", 2: "发", 3: "白"}


# ── 编解码 ────────────────────────────────────────────

def encode(suit: int, rank: int) -> int:
    """编码一张牌：花色 0-4, 点数 1-9/1-4/1-3

    Args:
        suit: 花色 (0=万, 1=条, 2=饼, 3=风, 4=箭)
        rank: 点数

    Returns:
        0-131 的代码

    Raises:
        ValueError: 参数越界
    """
    if not (WAN <= suit <= JIAN):
        raise ValueError(f"Invalid suit: {suit}, expected 0-4")
    if suit == FENG and not (1 <= rank <= 4):
        raise ValueError(f"Invalid feng rank: {rank}, expected 1-4")
    if suit == JIAN and not (1 <= rank <= 3):
        raise ValueError(f"Invalid jian rank: {rank}, expected 1-3")
    if suit in (WAN, TIAO, BING) and not (1 <= rank <= 9):
        raise ValueError(f"Invalid number rank: {rank}, expected 1-9")

    base_per_tile = {WAN: 4, TIAO: 4, BING: 4, FENG: 3, JIAN: 4}[suit]

    offset = {
        WAN: 0,
        TIAO: 36,
        BING: 72,
        FENG: 108,
        JIAN: 120,
    }[suit]

    return offset + (rank - 1) * base_per_tile


def decode(code: int) -> Tuple[int, int]:
    """解码一张牌 → (花色, 点数)

    Args:
        code: 0-131 的牌编码

    Returns:
        (花色, 点数)

    Raises:
        ValueError: code 越界
    """
    if not (0 <= code < TOTAL_TILES):
        raise ValueError(f"Tile code out of range: {code}, expected 0-{TOTAL_TILES-1}")

    if code < 36:
        return (WAN, code // 4 + 1)
    elif code < 72:
        return (TIAO, (code - 36) // 4 + 1)
    elif code < 108:
        return (BING, (code - 72) // 4 + 1)
    elif code < 120:
        return (FENG, (code - 108) // 3 + 1)
    else:
        return (JIAN, (code - 120) // 4 + 1)


# ── 可视化 ────────────────────────────────────────────

def tile_name(code: int, short: bool = False) -> str:
    """牌的文字表示

    Args:
        code: 牌编码
        short: 短格式（如 "1万" 而非 "一万"）

    Returns:
        牌名
    """
    suit, rank = decode(code)
    suit_str = SUIT_NAMES[suit]

    if suit == FENG:
        return FENG_NAMES[rank]
    elif suit == JIAN:
        return JIAN_NAMES[rank]
    else:
        return f"{rank}{SUIT_NAMES[suit]}"


def display(hand: List[int]) -> str:
    """将手牌列表转为可读字符串

    Args:
        hand: 牌编码列表

    Returns:
        "一万 一万 一条 ..." 格式字符串
    """
    return " ".join(tile_name(t) for t in sorted(hand))


def group_by_suit(tiles: List[int]) -> Dict[int, List[int]]:
    """按花色分组

    Returns:
        {花色: [编码列表]}
    """
    groups: Dict[int, List[int]] = {s: [] for s in range(5)}
    for t in tiles:
        suit, rank = decode(t)
        groups[suit].append(t)
    return groups


def tile_counts_to_ranks(counts: Dict[int, int], suit: int) -> Dict[int, int]:
    """将牌编码计数转为点数计数（同一花色内）

    Args:
        counts: {编码: 张数}
        suit: 花色

    Returns:
        {点数: 张数}
    """
    result: Dict[int, int] = {}
    for code, cnt in counts.items():
        s, r = decode(code)
        if s == suit:
            result[r] = result.get(r, 0) + cnt
    return result


# ── 牌池/剩余张数 ─────────────────────────────────────

def full_pool() -> List[int]:
    """生成完整牌池（136 张，每种 4 张）

    Returns:
        按编码排序的完整牌列表 [0, 0, 0, 0, 1, 1, ...]
    """
    pool = []
    for code in range(TOTAL_TILES):
        suit, _ = decode(code)
        count = 3 if suit == FENG else 4
        pool.extend([code] * count)
    return pool


def remaining_pool(hand: List[int], discards: Dict[int, List[int]] = None,
                   melds: Dict[int, List[List[int]]] = None) -> Dict[int, int]:
    """计算剩余牌池（总牌池 - 手牌 - 已出 - 副露）

    Args:
        hand: 手牌列表
        discards: {座位: [出牌列表]}  0=自家
        melds: {座位: [[面子/杠牌]]}

    Returns:
        {编码: 剩余张数}
    """
    remaining = {code: 4 for code in range(TOTAL_TILES)}

    # 减手牌
    for t in hand:
        remaining[t] -= 1

    # 减已出牌
    if discards:
        for seat, tiles in discards.items():
            for t in tiles:
                remaining[t] -= 1

    # 减副露
    if melds:
        for seat, meld_list in melds.items():
            for meld in meld_list:
                for t in meld:
                    remaining[t] -= 1

    # 校验：不应出现负数
    for code, cnt in remaining.items():
        if cnt < 0:
            remaining[code] = 0

    return remaining


# ── 牌分类 ────────────────────────────────────────────

def classify_tile_type(code: int) -> str:
    """判断牌的类型：字牌 / 幺九 / 中张

    Args:
        code: 牌编码 0-131

    Returns:
        "字牌" — 风牌 (东南西北) 或 箭牌 (中发白)
        "幺九" — 数牌 1 或 9 点
        "中张" — 数牌 2-8 点
    """
    suit, rank = decode(code)
    if suit in (FENG, JIAN):
        return "字牌"
    if rank in (1, 9):
        return "幺九"
    return "中张"


def count_available(tile_code: int, remaining: Dict[int, int]) -> int:
    """单张牌的剩余张数"""
    return remaining.get(tile_code, 0)
