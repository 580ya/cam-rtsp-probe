$ErrorActionPreference = "Stop"

# 安装锁定的运行依赖和打包工具。
uv sync --dev

# 使用 Windows 原生 PyInstaller 构建无控制台窗口的目录。
uv run pyinstaller --noconfirm --clean --onedir --windowed --name CameraRTSPProbe --add-data "wsdl;wsdl" --collect-all onvif gui.py

# 将 Windows 应用目录打成 zip。
Compress-Archive -Path "dist/CameraRTSPProbe" -DestinationPath "dist/CameraRTSPProbe-windows.zip" -Force
