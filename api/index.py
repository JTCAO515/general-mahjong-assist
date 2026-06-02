"""
Vercel Serverless Function 入口。
FastAPI app 在 api/main.py 中，此处直接 re-export。
"""
import sys
from pathlib import Path

# 确保能找到项目根目录的模块（core/, decision/）
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import app
