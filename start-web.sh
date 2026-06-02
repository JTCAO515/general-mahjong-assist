#!/usr/bin/env bash
# General Mahjong Assist — 启动 Web 服务
set -e
cd "$(dirname "$0")"
python3 -m api.main "$@"
