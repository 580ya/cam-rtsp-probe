#!/usr/bin/env bash
set -euo pipefail

# 安装锁定的运行依赖和打包工具。
uv sync --dev

# 使用 Linux 原生 PyInstaller 构建可分发目录。
uv run pyinstaller --noconfirm --clean --onedir --windowed --name CameraRTSPProbe --add-data "wsdl:wsdl" --collect-all onvif gui.py

# 将目录打成 Linux 分发压缩包。
tar -czf "dist/CameraRTSPProbe-linux-$(uname -m).tar.gz" -C dist CameraRTSPProbe
