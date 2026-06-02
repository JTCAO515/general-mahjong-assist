"""
国标麻将 — 全面牌局分析引擎

核心功能：
  1. 根据可见牌（手牌 + 副露 + 各家舍牌）精确计算剩余牌池
  2. 综合分析向听数、进张、听牌
  3. 出牌推荐（含打后向听数 + 进张数 + 防守评分）
  4. 吃/碰/杠决策评估
  5. 防守分析（根据舍牌判断危险牌）
"""
from __future__ import annotations

from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import Counter

from core.tile import (
    encode, decode, tile_name,
    WAN, TIAO, BING, FENG, JIAN,
    TOTAL_TILES, remaining_pool,
)
from core.shanten import calculate_shanten, discard_analysis as core_discard_analysis
from core.fan_calculator import FanContext, calculate_fan
from core.hand_parser import Hand
from core.win_checker import is_any_win
from decision.listen_engine import analyze_listen, ListenOption


# ── 数据类型 ───────────────────────────────────────────

@dataclass
class GameState:
    """完整牌局状态"""
    hand: List[int]                      # 我的手牌
    melds: List[List[int]] = field(default_factory=list)  # 我的副露
    discards: Dict[int, List[int]] = field(default_factory=dict)  # 各家舍牌 {座位: [编码]}
    opponent_melds: Dict[int, List[List[int]]] = field(default_factory=dict)  # 他家副露 {座位: [[面子1], ...]}
    seat_wind: int = 0                   # 座位风 0=东 1=南 2=西 3=北
    round_wind: int = 0                  # 圈风
    is_self_drawn: bool = True           # 是否自摸（刚摸的牌）
    last_discard: Optional[int] = None   # 他家刚打出的牌（用于吃碰杠判断）
    turn: int = 0                        # 当前轮到谁 (0=自家)


@dataclass
class DiscardOption:
    """出牌选项"""
    tile: int
    name: str
    post_shanten: int
    acceptance: int
    danger_level: str   # "低" / "中" / "高"
    reason: str = ""

    def summary(self) -> str:
        return f"打 {self.name} → {self.post_shanten}上听 · 进张{self.acceptance} · 危险{self.danger_level}"


@dataclass
class ActionOption:
    """操作选项（吃/碰/杠/自摸）"""
    action: str           # "chi", "pon", "kan", "tsumo"
    tiles: List[int]      # 操作的牌
    target_tile: int      # 目标牌（他家打的牌）
    new_hand: List[int]   # 操作后的手牌
    new_melds: List[List[int]]  # 操作后的副露
    post_shanten: int     # 操作后向听数
    acceptance: int       # 操作后进张数
    fan: int = 0          # 如果操作后可胡，番数
    fan_items: List[Tuple[str, int]] = field(default_factory=list)  # 番种明细

    def summary(self) -> str:
        names = [tile_name(t) for t in self.tiles]
        action_names = {"chi": "吃", "pon": "碰", "kan": "杠", "tsumo": "胡"}
        return f"{action_names.get(self.action, self.action)} {' '.join(names)} → {self.post_shanten}上听"


@dataclass
class DefenseInfo:
    """防守信息"""
    dangerous_tiles: List[Dict] = field(default_factory=list)  # 危险牌列表
    safe_tiles: List[Dict] = field(default_factory=list)       # 安全牌列表
    summary: str = ""


@dataclass
class GameAnalysis:
    """牌局分析结果"""
    shanten: int                        # 当前向听数
    shanten_types: Dict[str, int]       # 各类向听数
    acceptance: int                     # 当前进张数
    acceptance_tiles: List[int]         # 进张牌
    
    remaining_counts: Dict[int, int]    # 各牌剩余张数
    
    discard_options: List[DiscardOption] = field(default_factory=list)  # 出牌建议
    action_options: List[ActionOption] = field(default_factory=list)    # 吃碰杠建议
    listen_analysis: Optional[Dict] = None   # 听牌分析（如果听牌）
    defense: Optional[DefenseInfo] = None    # 防守信息
    monte_carlo: Optional[List[Dict]] = None  # 蒙特卡洛模拟EV（如果启用）


# ── 剩余牌池计算 ──────────────────────────────────────

def build_remaining(hand: List[int],
                    melds: List[List[int]],
                    discards: Dict[int, List[int]],
                    opponent_melds: Dict[int, List[List[int]]]) -> Dict[int, int]:
    """从可见牌信息构建剩余牌池"""
    # 构建 discards 字典 {座位: [出牌]}
    all_discards = {0: []}  # 座位0=自家（目前没有出牌）
    for seat, tiles in discards.items():
        all_discards[seat] = tiles

    # 构建 melds 字典 {座位: [副露列表]}
    all_melds = {0: melds}  # 座位0=自家的副露
    for seat, ml in opponent_melds.items():
        all_melds[seat] = ml

    # 剩余牌池（手牌本身通过 all_melds[0] 不包含）
    remaining = remaining_pool(hand, all_discards, all_melds)
    return remaining


# ── 防守分析 ──────────────────────────────────────────

def analyze_defense(discards: Dict[int, List[int]],
                    remaining: Dict[int, int]) -> DefenseInfo:
    """防守分析：基于舍牌判断危险牌和安全牌
    
    基本原则：
    - 生牌（一张没出过的牌）= 危险（可能被荣和）
    - 已经出过2+张的牌 = 安全
    - 字牌没出过 = 相对安全（除非字一色/碰碰和方向）
    - 只出过1张的 = 中等
    """
    dangerous = []
    safe = []
    
    # 统计所有舍牌的出现次数
    discard_counts: Dict[int, int] = {}
    for seat, tiles in discards.items():
        for t in tiles:
            discard_counts[t] = discard_counts.get(t, 0) + 1

    # 逐张分析
    for code in range(TOTAL_TILES):
        if remaining.get(code, 0) == 0:
            continue  # 没剩了
        
        total_discarded = discard_counts.get(code, 0)
        suit, rank = decode(code)
        
        if total_discarded >= 2:
            safe.append({
                "tile": code,
                "name": tile_name(code),
                "reason": f"已出{total_discarded}张",
                "level": "低",
            })
        elif total_discarded == 1:
            safe.append({
                "tile": code,
                "name": tile_name(code),
                "reason": f"已出1张",
                "level": "中",
            })
        elif total_discarded == 0 and suit in (FENG, JIAN):
            # 字牌没出过，不算太危险（可以跟打）
            dangerous.append({
                "tile": code,
                "name": tile_name(code),
                "reason": "生牌(字)",
                "level": "中",
            })
        else:
            dangerous.append({
                "tile": code,
                "name": tile_name(code),
                "reason": "生牌",
                "level": "高",
            })

    # 排序：危险牌按"高→中"（非危险反过来）
    dangerous.sort(key=lambda x: (0 if x["level"] == "高" else 1))
    safe.sort(key=lambda x: (0 if x["level"] == "低" else 1))

    summary = ""
    if dangerous:
        top_danger = [d["name"] for d in dangerous[:5]]
        summary = f"⚡ 危险牌: {' '.join(top_danger)}··· 可能被荣和，避免打出"
    
    return DefenseInfo(
        dangerous_tiles=dangerous[:10],
        safe_tiles=safe[:10],
        summary=summary,
    )


# ── 出牌推荐（含防守评分） ──────────────────────────

def rank_discard_options(tiles: List[int],
                         melds: List[List[int]],
                         remaining: Dict[int, int],
                         discards: Dict[int, List[int]]) -> List[DiscardOption]:
    """出牌推荐（向听数优先 + 进张数 + 防守评分）
    
    Args:
        tiles: 手牌（13-14 张）
        melds: 副露
        remaining: 剩余牌池
        discards: 各家舍牌（用于防守分析）
    """
    # 用已有出牌分析
    raw_advice = core_discard_analysis(tiles, melds, remaining)
    if not raw_advice:
        return []

    # 计算舍牌统计
    discard_counts: Dict[int, int] = {}
    for seat, d_tiles in discards.items():
        for t in d_tiles:
            discard_counts[t] = discard_counts.get(t, 0) + 1

    options = []
    for da in raw_advice:
        tile_code = da["discard"]
        total_discarded = discard_counts.get(tile_code, 0)

        # 危险等级
        if total_discarded >= 2:
            danger_level = "低"
            reason = f"已出{total_discarded}张，安全"
        elif total_discarded == 1:
            danger_level = "中"
            reason = f"已出1张，半生"
        else:
            suit, _ = decode(tile_code)
            if suit in (FENG, JIAN):
                danger_level = "中"
                reason = "生牌(字)"
            else:
                danger_level = "高"
                reason = "生牌，可能点炮"

        options.append(DiscardOption(
            tile=tile_code,
            name=tile_name(tile_code),
            post_shanten=da["post_shanten"],
            acceptance=da["acceptance"],
            danger_level=danger_level,
            reason=reason,
        ))

    # 同向听数内按(危险等级低优先, 进张数高优先)
    level_order = {"低": 0, "中": 1, "高": 2}
    options.sort(key=lambda o: (o.post_shanten, level_order.get(o.danger_level, 3), -o.acceptance))
    return options


# ── 吃碰杠决策评估 ──────────────────────────────────

def evaluate_actions(hand: List[int],
                     melds: List[List[int]],
                     last_discard: int,
                     remaining: Dict[int, int],
                     seat_wind: int = 0,
                     round_wind: int = 0) -> List[ActionOption]:
    """评估吃碰杠选项
    
    Args:
        hand: 手牌（当前 13 张，不含 last_discard）
        melds: 已有副露
        last_discard: 他家刚打出的牌
        remaining: 剩余牌池
        seat_wind: 座位风
        round_wind: 圈风
    
    Returns:
        操作选项列表（按推荐度排序）
    """
    options: List[ActionOption] = []
    counts = Counter(hand)
    suit, rank = decode(last_discard)

    current_shanten = calculate_shanten(hand, melds)["min"]

    # ── 碰 ──
    if counts.get(last_discard, 0) >= 2:
        # 碰后手牌减少 2 张
        new_hand = list(hand)
        for _ in range(2):
            new_hand.remove(last_discard)
        new_melds = list(melds) + [[last_discard, last_discard, last_discard]]
        
        post_shanten = calculate_shanten(new_hand, new_melds)["min"]
        acceptance = _calc_acceptance_simple(new_hand, new_melds, remaining)
        
        # 检查碰后是否胡牌
        fan = 0
        fan_items = []
        if post_shanten == -1:
            ctx = FanContext(
                hand=Hand(new_hand, new_melds),
                win_tile=last_discard,
                is_self_drawn=False,
                seat_wind=seat_wind,
                round_wind=round_wind,
            )
            fan_result = calculate_fan(ctx)
            fan = fan_result.total
            fan_items = fan_result.items
        
        options.append(ActionOption(
            action="pon",
            tiles=[last_discard] * 3,
            target_tile=last_discard,
            new_hand=new_hand,
            new_melds=new_melds,
            post_shanten=post_shanten,
            acceptance=acceptance,
            fan=fan,
            fan_items=fan_items,
        ))

    # ── 杠（明杠：手牌已有 3 张相同） ──
    if counts.get(last_discard, 0) >= 3:
        new_hand = list(hand)
        for _ in range(3):
            new_hand.remove(last_discard)
        new_melds = list(melds) + [[last_discard, last_discard, last_discard, last_discard]]
        
        post_shanten = calculate_shanten(new_hand, new_melds)["min"]
        acceptance = _calc_acceptance_simple(new_hand, new_melds, remaining)
        
        options.append(ActionOption(
            action="kan",
            tiles=[last_discard] * 4,
            target_tile=last_discard,
            new_hand=new_hand,
            new_melds=new_melds,
            post_shanten=post_shanten,
            acceptance=acceptance,
        ))

    # ── 加杠（已有碰，补第 4 张） ──
    for i, meld in enumerate(melds):
        if len(meld) == 3 and meld[0] == last_discard:
            # 已有碰，补第 4 张
            new_hand = list(hand)
            new_hand.remove(last_discard)
            new_melds = list(melds)
            new_melds[i] = [last_discard] * 4
            
            post_shanten = calculate_shanten(new_hand, new_melds)["min"]
            acceptance = _calc_acceptance_simple(new_hand, new_melds, remaining)
            
            options.append(ActionOption(
                action="kan",
                tiles=[last_discard] * 4,
                target_tile=last_discard,
                new_hand=new_hand,
                new_melds=new_melds,
                post_shanten=post_shanten,
                acceptance=acceptance,
            ))
            break

    # ── 吃 ──（只有数牌，且只能吃上家）
    if suit in (WAN, TIAO, BING):
        eat_patterns = _find_eat_patterns(hand, last_discard)
        for pattern in eat_patterns:
            new_hand = list(hand)
            for t in pattern:
                if t != last_discard:
                    new_hand.remove(t)
            new_melds = list(melds) + [sorted(pattern + [last_discard])]
            
            post_shanten = calculate_shanten(new_hand, new_melds)["min"]
            acceptance = _calc_acceptance_simple(new_hand, new_melds, remaining)
            
            options.append(ActionOption(
                action="chi",
                tiles=pattern + [last_discard],
                target_tile=last_discard,
                new_hand=new_hand,
                new_melds=new_melds,
                post_shanten=post_shanten,
                acceptance=acceptance,
            ))

    # 排序：向听数优先，同向听数进张大优先
    options.sort(key=lambda o: (o.post_shanten, -o.acceptance))

    # ── 自摸检查 ──
    if rank_discard_options is not None:  # 修复：检查是否可以直接胡
        test_hand = hand + [last_discard]
        if is_any_win(test_hand, melds):
            ctx = FanContext(
                hand=Hand(test_hand, melds),
                win_tile=last_discard,
                is_self_drawn=False,
                seat_wind=seat_wind,
                round_wind=round_wind,
            )
            fan_result = calculate_fan(ctx)
            options.insert(0, ActionOption(
                action="tsumo",
                tiles=[last_discard],
                target_tile=last_discard,
                new_hand=hand,
                new_melds=melds,
                post_shanten=-1,
                acceptance=0,
                fan=fan_result.total,
                fan_items=fan_result.items,
            ))

    return options


def _find_eat_patterns(hand: List[int], discard: int) -> List[List[int]]:
    """找吃牌组合：discard 可以组成哪些顺子
    
    Returns:
        [[手牌中的2张牌], ...]
    """
    suit, rank = decode(discard)
    if suit not in (WAN, TIAO, BING):
        return []

    hand_ranks = Counter()
    for t in hand:
        s, r = decode(t)
        if s == suit:
            hand_ranks[r] += 1

    patterns = []

    # discard 作为第 1 张： (discard, discard+1, discard+2)
    if rank <= 7 and hand_ranks.get(rank+1, 0) >= 1 and hand_ranks.get(rank+2, 0) >= 1:
        patterns.append([encode(suit, rank+1), encode(suit, rank+2)])

    # discard 作为第 2 张： (discard-1, discard, discard+1)
    if 2 <= rank <= 8 and hand_ranks.get(rank-1, 0) >= 1 and hand_ranks.get(rank+1, 0) >= 1:
        patterns.append([encode(suit, rank-1), encode(suit, rank+1)])

    # discard 作为第 3 张： (discard-2, discard-1, discard)
    if rank >= 3 and hand_ranks.get(rank-2, 0) >= 1 and hand_ranks.get(rank-1, 0) >= 1:
        patterns.append([encode(suit, rank-2), encode(suit, rank-1)])

    return patterns


def _calc_acceptance_simple(tiles: List[int],
                            melds: List[List[int]],
                            remaining: Dict[int, int]) -> int:
    """简单进张计算（只算能降低向听数的剩余牌数）"""
    from core.shanten import calculate_shanten
    current_shanten = calculate_shanten(tiles, melds)["min"]
    if current_shanten <= -1:
        return 0

    total = 0
    for code in range(TOTAL_TILES):
        avail = remaining.get(code, 0)
        if avail == 0:
            continue
        new_shanten = calculate_shanten(tiles, melds, draw_tile=code)["min"]
        if new_shanten < current_shanten:
            total += avail
    return total


# ── 听牌分析 ──────────────────────────────────────────

def analyze_listen_state(hand: List[int],
                         melds: List[List[int]],
                         remaining: Dict[int, int],
                         seat_wind: int = 0,
                         round_wind: int = 0,
                         is_self_drawn: bool = True) -> Optional[Dict]:
    """听牌分析（封装 listen_engine.analyze_listen）"""
    shanten_info = calculate_shanten(hand, melds)
    if shanten_info["min"] != 0:
        return None

    return analyze_listen(hand, melds, remaining, seat_wind, round_wind, is_self_drawn)


# ── 全面分析入口 ──────────────────────────────────────

def full_analysis(state: GameState, use_monte_carlo: bool = False,
                 mc_simulations: int = 500, mc_draws: int = 8) -> GameAnalysis:
    """全面牌局分析

    Args:
        state: 牌局状态
        use_monte_carlo: 是否启用蒙特卡洛模拟
        mc_simulations: 每张牌的模拟局数
        mc_draws: 每局摸牌次数

    Returns:
        GameAnalysis 包含完整分析结果
    """
    
    # 1. 计算剩余牌池
    remaining = build_remaining(
        state.hand, state.melds,
        state.discards, state.opponent_melds,
    )

    # 2. 向听数 + 进张
    shanten_info = calculate_shanten(state.hand, state.melds)
    shanten_val = shanten_info["min"]

    # 计算进张（14张时先分析出牌，不考虑进张）
    from core.shanten import calculate_acceptance
    hand_for_acceptance = state.hand[:13] if len(state.hand) > 13 else state.hand
    acceptance = calculate_acceptance(hand_for_acceptance, state.melds, remaining)
    
    # 进张牌
    acceptance_tiles = []
    for code in range(TOTAL_TILES):
        avail = remaining.get(code, 0)
        if avail == 0:
            continue
        if len(state.hand) > 13:
            break  # 14张需先出牌，不计算进张牌
        test_shanten = calculate_shanten(state.hand, state.melds, draw_tile=code)["min"]
        if test_shanten < shanten_val:
            acceptance_tiles.append(code)

    # 3. 出牌建议
    discard_options = rank_discard_options(
        state.hand, state.melds, remaining, state.discards,
    ) if len(state.hand) >= 14 or (len(state.hand) >= 13 and not state.is_self_drawn) else []

    # 4. 听牌分析
    listen_analysis = None
    if shanten_val == 0:
        listen_analysis = analyze_listen(
            state.hand, state.melds, remaining,
            state.seat_wind, state.round_wind, state.is_self_drawn,
        )

    # 5. 吃碰杠分析
    action_options = []
    if state.last_discard is not None:
        action_options = evaluate_actions(
            state.hand, state.melds, state.last_discard,
            remaining, state.seat_wind, state.round_wind,
        )

    # 6. 防守分析
    defense = analyze_defense(state.discards, remaining)

    # 7. 蒙特卡洛模拟
    mc_results = None
    if use_monte_carlo and len(state.hand) >= 14:
        try:
            from decision.monte_carlo import evaluate_all_discards
            mc_results = evaluate_all_discards(
                state.hand, state.melds, remaining,
                simulations=mc_simulations, max_draws=mc_draws,
            )
        except Exception as e:
            mc_results = [{"error": str(e)}]

    # 8. 去掉 shanten_types 里重复的信息
    shanten_types = {k: v for k, v in shanten_info.items() if k != "min"}

    return GameAnalysis(
        shanten=shanten_val,
        shanten_types=shanten_types,
        acceptance=acceptance,
        acceptance_tiles=acceptance_tiles,
        remaining_counts=remaining,
        discard_options=discard_options,
        action_options=action_options,
        listen_analysis=listen_analysis,
        defense=defense,
        monte_carlo=mc_results,
    )
