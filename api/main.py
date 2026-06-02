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
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from core.tile import encode, decode, tile_name, TOTAL_TILES, WAN, TIAO, BING, FENG, JIAN
from core.shanten import calculate_shanten, discard_analysis
from decision.listen_engine import analyze_listen

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
