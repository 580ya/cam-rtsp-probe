#!/usr/bin/env bash
set -euo pipefail

# 安装锁定的运行依赖和打包工具。
uv sync --dev

# 使用 macOS 原生 PyInstaller 构建 .app。
uv run pyinstaller --noconfirm --clean --onedir --windowed --name CameraRTSPProbe --add-data "wsdl:wsdl" --collect-all onvif gui.py

# 将 macOS 应用打成可上传的 zip。
ditto -c -k --sequesterRsrc --keepParent dist/CameraRTSPProbe "dist/CameraRTSPProbe-macos-$(uname -m).zip"
