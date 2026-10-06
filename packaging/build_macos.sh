#!/usr/bin/env bash
set -euo pipefail

# 安装锁定的运行依赖和打包工具。
uv sync --dev

# 使用 macOS 原生 PyInstaller 构建 .app。
uv run pyinstaller --noconfirm --clean --onedir --windowed --name CameraRTSPProbe --add-data "wsdl:wsdl" --collect-all onvif --collect-all cv2 gui.py

# 根据 PyInstaller 输出选择应用包路径，兼容 .app 和普通 onedir 目录。
if [[ -d "dist/CameraRTSPProbe.app" ]]; then
    APP_PATH="dist/CameraRTSPProbe.app"  # macOS 应用包路径。
else
    APP_PATH="dist/CameraRTSPProbe"  # 兼容非 .app 形式的应用目录。
fi

# 对应用及其内嵌 Python 扩展做临时签名，避免 Gatekeeper 逐个拦截 .so 文件。
codesign --deep --force --verbose --sign - "$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

# 将完成签名的 macOS 应用打成可上传的 zip。
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "dist/CameraRTSPProbe-macos-$(uname -m).zip"
