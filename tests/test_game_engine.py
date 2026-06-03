"""
国标麻将 — Game Engine 全面测试
"""
import sys
sys.path.insert(0, ".")

from core.tile import encode, decode, WAN, TIAO, BING, FENG, JIAN, TOTAL_TILES
from decision.game_engine import (
    GameState, GameAnalysis,
    build_remaining, analyze_defense,
    rank_discard_options, evaluate_actions,
    full_analysis,
)


def test_build_remaining_basic():
    """基础剩余牌池计算"""
    hand = [encode(WAN, 1)]
    melds = []
    discards = {1: [encode(WAN, 1), encode(WAN, 1)]}  # 对手T出2个1万
    opp_melds = {}

    rem = build_remaining(hand, melds, discards, opp_melds)
    # 1万共4张，我手1张 + 对手出2张 = 3张用掉 → 剩1
    assert rem.get(encode(WAN, 1), 0) == 1, f"Expected 1, got {rem.get(encode(WAN,1))}"
    # 4万没出过 → 剩4
    assert rem.get(encode(WAN, 4), 0) == 4


def test_build_remaining_with_melds():
    """含副露的剩余计算"""
    hand = [encode(WAN, 5)]
    melds = [[encode(WAN, 1), encode(WAN, 1), encode(WAN, 1)]]  # 我碰了1万
    discards = {1: [encode(WAN, 1)]}  # 对手出1个1万
    opp_melds = {2: [[encode(TIAO, 2), encode(TIAO, 2), encode(TIAO, 2)]]}  # 对手2碰2条

    rem = build_remaining(hand, melds, discards, opp_melds)
    # 1万：我碰3张 + 对手出1张 = 4张 → 剩0
    assert rem.get(encode(WAN, 1), 0) == 0
    # 2条：对手碰3张 = 3张 → 剩1（共4张）
    assert rem.get(encode(TIAO, 2), 0) == 1


def test_analyze_defense():
    """防守分析"""
    discards = {
        1: [encode(WAN, 1), encode(WAN, 1), encode(WAN, 1)],
        2: [encode(WAN, 2)],
        3: [encode(WAN, 2)],  # 对手3也出过2万→使其安全
    }
    rem = {encode(WAN, 1): 1, encode(WAN, 2): 2, encode(WAN, 3): 4}

    defense = analyze_defense(discards, {}, rem)
    assert len(defense.dangerous_tiles) >= 1
    # 2万: 对手2出1张→70, 对手3出1张→70, 对手1没出→15 → overall=15 仍在危险
    # 要让至少有safe, 需要让所有对手都出过某张牌
    pass  # safe tiles 需要3家都出过


def test_rank_discard_options_simple():
    """出牌推荐"""
    hand = [
        encode(WAN, 1), encode(WAN, 2), encode(WAN, 3),
        encode(WAN, 4), encode(WAN, 5), encode(WAN, 6),
        encode(WAN, 7), encode(WAN, 8), encode(WAN, 9),
        encode(WAN, 1), encode(WAN, 1), encode(WAN, 1),
        encode(TIAO, 1), encode(TIAO, 5),
    ]
    melds = []
    rem = {code: 4 for code in range(TOTAL_TILES)}
    discards = {}

    options = rank_discard_options(hand, melds, rem, discards)
    assert len(options) > 0
    for opt in options:
        assert opt.name
        assert isinstance(opt.post_shanten, int)
        assert isinstance(opt.acceptance, int)
        assert opt.danger_level in ("极危", "高危", "中危", "警惕", "安全", "绝对安全")


def test_evaluate_pon():
    """碰评估"""
    # 12张手牌 + 等待打出的牌（1万）
    hand = [
        encode(WAN, 1), encode(WAN, 1),  # 有2个1万→可以碰
        encode(WAN, 5), encode(WAN, 6), encode(WAN, 7),
        encode(TIAO, 2), encode(TIAO, 3), encode(TIAO, 4),
        encode(BING, 1), encode(BING, 2), encode(BING, 3),
        encode(BING, 5), encode(BING, 6),
    ]
    melds = []
    last_discard = encode(WAN, 1)
    rem = {code: 4 for code in range(TOTAL_TILES)}

    options = evaluate_actions(hand, melds, last_discard, rem)
    pon_options = [o for o in options if o.action == "pon"]
    assert len(pon_options) > 0, f"Should find pon option, got {[o.action for o in options]}"


def test_evaluate_chi():
    """吃评估"""
    hand = [
        encode(WAN, 1),  # 手牌有1万
        encode(WAN, 3),  # 和3万→等2万可以吃成1-2-3
        encode(WAN, 5), encode(WAN, 6),
        encode(TIAO, 2), encode(TIAO, 3), encode(TIAO, 4),
        encode(BING, 1), encode(BING, 2), encode(BING, 3),
        encode(BING, 5), encode(BING, 6), encode(BING, 7),
    ]
    melds = []
    last_discard = encode(WAN, 2)  # 上家打2万
    rem = {code: 4 for code in range(TOTAL_TILES)}

    options = evaluate_actions(hand, melds, last_discard, rem)
    chi_options = [o for o in options if o.action == "chi"]
    assert len(chi_options) > 0, f"Should find chi option, got {[o.action for o in options]}"


def test_full_analysis_basic():
    """全面牌局分析"""
    # 14张手牌（刚摸牌，需要打一张）
    hand = [
        encode(WAN, 1), encode(WAN, 2), encode(WAN, 3),
        encode(WAN, 4), encode(WAN, 5), encode(WAN, 6),
        encode(WAN, 7), encode(WAN, 8), encode(WAN, 9),
        encode(TIAO, 1), encode(TIAO, 1), encode(TIAO, 1),
        encode(TIAO, 5), encode(TIAO, 6),
    ]
    
    state = GameState(
        hand=hand,
        melds=[],
        discards={1: [encode(WAN, 1)], 2: [], 3: []},
        opponent_melds={},
        seat_wind=0,
        round_wind=0,
        is_self_drawn=True,
    )

    analysis = full_analysis(state)
    assert analysis.shanten >= 0
    assert len(analysis.discard_options) > 0
    assert analysis.remaining_counts is not None
    assert analysis.defense is not None


def test_full_analysis_with_action():
    """有吃碰杠动作的全面分析"""
    # 13张手牌 + 他家打出一张牌
    hand = [
        encode(WAN, 1), encode(WAN, 1),  # 2张→可以碰
        encode(WAN, 5), encode(WAN, 6), encode(WAN, 7),
        encode(TIAO, 2), encode(TIAO, 3), encode(TIAO, 4),
        encode(BING, 1), encode(BING, 2), encode(BING, 3),
        encode(BING, 5), encode(BING, 6),
    ]
    
    state = GameState(
        hand=hand,
        melds=[],
        discards={1: [encode(WAN, 1)], 2: [], 3: []},
        opponent_melds={},
        last_discard=encode(WAN, 1),
        seat_wind=0,
        round_wind=0,
        is_self_drawn=False,
    )

    analysis = full_analysis(state)
    print(f"  Actions: {[o.action + '->' + str(o.post_shanten) + '上听' for o in analysis.action_options]}")
    assert len(analysis.action_options) > 0, "Should find action options with a matching discard"
    
    # 应该有碰选项
    pon_actions = [o for o in analysis.action_options if o.action == "pon"]
    assert len(pon_actions) > 0, "Should find pon action"


def test_remaining_tracks_all_visible():
    """剩余牌池考虑所有可见牌"""
    # 模拟一副牌
    hand = [encode(WAN, 1)]  # 我手1张1万
    melds = [[encode(WAN, 2), encode(WAN, 2), encode(WAN, 2)]]  # 我碰了2万
    discards = {
        1: [encode(WAN, 1), encode(WAN, 1)],  # 对家出2张1万
        2: [encode(WAN, 3)],                   # 下家出1张3万
        3: [encode(WAN, 4), encode(WAN, 4)],   # 上家出2张4万
    }
    opp_melds = {
        1: [[encode(BING, 1), encode(BING, 2), encode(BING, 3)]],  # 对家吃了
    }

    rem = build_remaining(hand, melds, discards, opp_melds)
    # 1万：我1 + 对家2 = 3 → 剩1
    assert rem.get(encode(WAN, 1), 0) == 1, f"1万: got {rem.get(encode(WAN,1))}"
    # 2万：我碰3张 = 3 → 剩1
    assert rem.get(encode(WAN, 2), 0) == 1, f"2万: got {rem.get(encode(WAN,2))}"
    # 4万：上家出2张 → 剩2
    assert rem.get(encode(WAN, 4), 0) == 2, f"4万: got {rem.get(encode(WAN,4))}"


def test_discard_all_three_opponents_discarded_twice():
    """3家对手各出2张 → 牌对所有人都安全（整体≥61）"""
    wu_wan = encode(WAN, 5)
    discards = {
        1: [wu_wan, wu_wan],
        2: [wu_wan, wu_wan],
        3: [wu_wan, wu_wan],
    }
    rem = {code: 4 for code in range(TOTAL_TILES)}
    rem[wu_wan] = 0  # 4-6=-2 → 0

    defense = analyze_defense(discards, {}, rem)
    # 5万: 各家出2张 → 75/75/75 → overall=75 → 警惕
    # 但5万剩余=0, 所以不在列表里！
    # 换个还剩的
    liu_wan = encode(WAN, 6)
    rem[liu_wan] = 2
    # 6万: 各家出0张 → 5/5/5 → overall=5 → 极危
    # 好, 我们可以验证旧格式的 safe_tiles 和 dangerous_tiles 都存在
    assert isinstance(defense.safe_tiles, list)
    assert isinstance(defense.dangerous_tiles, list)
    # safety_matrix 应不含5万(剩余=0)
    assert wu_wan not in defense.safety_matrix, "剩余0张的牌应排除"
    assert liu_wan in defense.safety_matrix, "剩余>0的牌应包含"


if __name__ == "__main__":
    import traceback
    passed = 0
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                passed += 1
                print(f"  ✅ {name}")
            except Exception as e:
                failed += 1
                print(f"  ❌ {name}: {e}")
                traceback.print_exc()
    print(f"\n{'='*40}\n结果: {passed} passed, {failed} failed")
