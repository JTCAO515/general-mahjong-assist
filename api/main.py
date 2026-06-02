"""
General Mahjong Assist — FastAPI Web API

端点：
  POST /api/analyze         全面分析（向听数 → 出牌建议 / 听牌评估）
  GET  /api/tiles           获取所有牌面信息
  GET  /api/health          健康检查
"""

from __future__ import annotations
import os, sys, logging, traceback
from pathlib import Path
from typing import List, Optional, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from core.tile import encode, decode, tile_name, TOTAL_TILES, WAN, TIAO, BING, FENG, JIAN
from core.shanten import calculate_shanten, discard_analysis
from decision.listen_engine import analyze_listen
from decision.game_engine import (
    GameState, full_analysis,
    DiscardOption, ActionOption, DefenseInfo,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gmahjong.api")

app = FastAPI(title="General Mahjong Assist API", version="1.1.0")


# ── 输入模型 ─────────────────────────────────────────

class TileInput(BaseModel):
    code: int = Field(..., ge=0, lt=TOTAL_TILES, description="牌编码 0-131")
    count: int = Field(default=1, ge=1, le=4, description="张数")

class AnalyzeRequest(BaseModel):
    hand: List[int] = Field(..., min_length=13, max_length=14,
                            description="手牌编码列表（13-14张）")
    melds: Optional[List[List[int]]] = Field(default=None,
                                             description="副露列表")
    remaining: Optional[dict] = Field(default=None,
                                      description="剩余牌池 {编码: 张数}")
    seat_wind: int = Field(default=1, ge=0, le=3, description="座位风 0=东 1=南 2=西 3=北")
    round_wind: int = Field(default=0, ge=0, le=3, description="圈风")
    is_self_drawn: bool = Field(default=True, description="是否自摸")


# ── 响应模型 ─────────────────────────────────────────

class TileInfo(BaseModel):
    code: int
    name: str
    suit: str
    rank: int

class ShantenInfo(BaseModel):
    min: int
    face_type: int
    face_str: str
    acceptance: List[TileInfo]
    acceptance_count: int

class ListenOption(BaseModel):
    tile: TileInfo
    remaining: int
    fan: int
    fan_items: List[dict]
    score: float

class AnalyzeResponse(BaseModel):
    is_tenpai: bool
    shanten: ShantenInfo
    listen: Optional[List[ListenOption]] = None
    discard_advice: Optional[List[dict]] = None
    raw_hand: str


# ── Game Analyze 输入/响应模型 ───────────────────────

class GameAnalyzeRequest(BaseModel):
    hand: List[int] = Field(..., min_length=13, max_length=14, description="手牌编码列表")
    melds: Optional[List[List[int]]] = Field(default=None, description="自家副露")
    discards: Optional[Dict[str, List[int]]] = Field(
        default=None, description="各家舍牌 {座位: [编码]}，座位0=自家(不填)"
    )
    opponent_melds: Optional[Dict[str, List[List[int]]]] = Field(
        default=None, description="他家副露 {座位([[面子], ...])}"
    )
    seat_wind: int = Field(default=0, ge=0, le=3, description="座位风 0=东 1=南 2=西 3=北")
    round_wind: int = Field(default=0, ge=0, le=3, description="圈风")
    is_self_drawn: bool = Field(default=True, description="是否自摸")
    last_discard: Optional[int] = Field(default=None, description="他家刚打出的牌编码")
    use_monte_carlo: bool = Field(default=False, description="启用蒙特卡洛模拟")


class DiscardOptionResp(BaseModel):
    tile: TileInfo
    post_shanten: int
    acceptance: int
    danger_level: str
    reason: str
    mc_ev: float = 0.0


class ActionOptionResp(BaseModel):
    action: str          # "chi", "pon", "kan", "tsumo"
    tiles: List[TileInfo]
    post_shanten: int
    acceptance: int
    fan: int = 0
    fan_items: List[dict] = Field(default_factory=list)


class DefenseResp(BaseModel):
    dangerous_tiles: List[dict] = Field(default_factory=list)
    safe_tiles: List[dict] = Field(default_factory=list)
    summary: str = ""


class GameAnalyzeResponse(BaseModel):
    shanten: int
    shanten_types: dict
    acceptance: int
    acceptance_tiles: List[TileInfo]

    discard_options: List[DiscardOptionResp]
    action_options: List[ActionOptionResp]
    listen_analysis: Optional[dict] = None
    defense: DefenseResp

    hand_display: str
    monte_carlo: Optional[List[dict]] = None


# ── 辅助函数 ─────────────────────────────────────────

def tile_to_info(code: int) -> TileInfo:
    suit, rank = decode(code)
    suit_names = {0: "万", 1: "条", 2: "饼", 3: "风", 4: "箭"}
    return TileInfo(code=code, name=tile_name(code),
                    suit=suit_names.get(suit, "?"), rank=rank)


# ── API 端点 ─────────────────────────────────────────

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """全面手牌分析"""
    try:
        tiles = req.hand
        melds = req.melds or []
        remaining = req.remaining

        # 1) 向听数
        st = calculate_shanten(tiles, melds)
        shanten_val = st["min"]
        type_names = {"standard": "面子手", "seven_pairs": "七对子",
                      "thirteen_orphans": "十三幺", "composite_dragon": "组合龙"}
        face_type_name = "未知"
        for tk, tn in type_names.items():
            if tk in st and st[tk] == shanten_val:
                face_type_name = tn
                break
        acceptance = st.get("acceptance", [])
        acceptance_info = [tile_to_info(c) for _, c in acceptance] if acceptance else []

        shanten_info = ShantenInfo(
            min=shanten_val,
            face_type=0,
            face_str=face_type_name,
            acceptance=acceptance_info,
            acceptance_count=len(acceptance),
        )

        # 2) 听牌分析
        listen_result = None
        if shanten_val == 0:
            result = analyze_listen(tiles, melds, remaining,
                                    req.seat_wind, req.round_wind, req.is_self_drawn)
            listen_result = []
            for opt in result["options"]:
                fan_items = [{"name": n, "fan": f} for n, f in opt.fan_items]
                listen_result.append(ListenOption(
                    tile=tile_to_info(opt.tile),
                    remaining=opt.remaining,
                    fan=opt.fan,
                    fan_items=fan_items,
                    score=opt.score,
                ))

        # 3) 出牌建议（14+张时）
        discard_advice_result = None
        if len(tiles) >= 14:
            raw_advice = discard_analysis(tiles, melds, remaining)
            if raw_advice:
                discard_advice_result = [
                    {
                        "discard": da["discard"],
                        "name": da["name"],
                        "shanten_after": da["post_shanten"],
                        "acceptance_count": da["acceptance"],
                    }
                    for da in raw_advice
                ]

        # 4) 手牌描述
        raw_hand = " ".join(tile_name(t) for t in tiles)

        return AnalyzeResponse(
            is_tenpai=(shanten_val == 0),
            shanten=shanten_info,
            listen=listen_result,
            discard_advice=discard_advice_result,
            raw_hand=raw_hand,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analyze error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tiles", response_model=List[TileInfo])
async def list_tiles():
    """获取所有牌面信息"""
    return [tile_to_info(c) for c in range(TOTAL_TILES)]


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.1.0", "tests": "128 passing"}


# ── Game Analyze 端点 ────────────────────────────────

ACTION_NAMES = {"chi": "吃", "pon": "碰", "kan": "杠", "tsumo": "胡"}

def _action_option_to_resp(opt: ActionOption) -> ActionOptionResp:
    return ActionOptionResp(
        action=opt.action,
        tiles=[tile_to_info(t) for t in opt.tiles],
        post_shanten=opt.post_shanten,
        acceptance=opt.acceptance,
        fan=opt.fan,
        fan_items=[{"name": n, "fan": f} for n, f in opt.fan_items],
    )

def _discard_option_to_resp(opt: DiscardOption) -> DiscardOptionResp:
    return DiscardOptionResp(
        tile=tile_to_info(opt.tile),
        post_shanten=opt.post_shanten,
        acceptance=opt.acceptance,
        danger_level=opt.danger_level,
        reason=opt.reason,
        mc_ev=opt.mc_ev,
    )


@app.post("/api/game-analyze", response_model=GameAnalyzeResponse)
async def game_analyze(req: GameAnalyzeRequest):
    """全面牌局分析

    根据当前牌局状态，分析：
      - 向听数 / 进张数
      - 出牌建议（含防守评分）
      - 吃碰杠决策
      - 听牌分析（如果听牌）
      - 防守信息（安全牌/危险牌）
    """
    try:
        melds = req.melds or []
        discards = {}
        if req.discards:
            discards = {int(k): v for k, v in req.discards.items()}
        opp_melds = {}
        if req.opponent_melds:
            opp_melds = {int(k): v for k, v in req.opponent_melds.items()}

        state = GameState(
            hand=req.hand,
            melds=melds,
            discards=discards,
            opponent_melds=opp_melds,
            seat_wind=req.seat_wind,
            round_wind=req.round_wind,
            is_self_drawn=req.is_self_drawn,
            last_discard=req.last_discard,
        )

        analysis = full_analysis(state, use_monte_carlo=req.use_monte_carlo)

        return GameAnalyzeResponse(
            shanten=analysis.shanten,
            shanten_types=analysis.shanten_types,
            acceptance=analysis.acceptance,
            acceptance_tiles=[tile_to_info(t) for t in analysis.acceptance_tiles],
            discard_options=[_discard_option_to_resp(o) for o in analysis.discard_options],
            action_options=[_action_option_to_resp(o) for o in analysis.action_options],
            listen_analysis=_serialize_listen(analysis.listen_analysis) if analysis.listen_analysis else None,
            defense=DefenseResp(
                dangerous_tiles=analysis.defense.dangerous_tiles if analysis.defense else [],
                safe_tiles=analysis.defense.safe_tiles if analysis.defense else [],
                summary=analysis.defense.summary if analysis.defense else "",
            ),
            hand_display=" ".join(tile_name(t) for t in req.hand),
            monte_carlo=analysis.monte_carlo,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Game analyze error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


def _serialize_listen(analysis: dict) -> dict:
    """序列化听牌分析结果"""
    if not analysis:
        return {"is_tenpai": False, "options": [], "best": None, "total_fan": 0}

    options = []
    best = analysis.get("best")
    for opt in analysis.get("options", []):
        options.append({
            "tile": tile_to_info(opt.tile),
            "name": opt.name,
            "remaining": opt.remaining,
            "fan": opt.fan,
            "fan_items": [{"name": n, "fan": f} for n, f in opt.fan_items],
            "score": opt.score,
        })

    return {
        "is_tenpai": analysis.get("is_tenpai", False),
        "options": options,
        "best": best.name if best else None,
        "total_fan": analysis.get("total_fan", 0),
    }


# ── 静态文件 ─────────────────────────────────────────

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


def start_server(host: str = "127.0.0.1", port: int = 8778, reload: bool = False):
    """启动开发服务器"""
    import uvicorn
    print()
    print(" 🀄  General Mahjong Assist — Web API")
    print(f"    📍  http://localhost:{port}")
    print(f"    📊  API 文档: http://localhost:{port}/docs")
    print(f"    ⏹  Ctrl+C 停止\n")
    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server()
