## cam-rtsp-probe

这是一个用于探测摄像头实时 RTSP 和最近一分钟历史 RTSP 地址的 FastAPI 项目，附带 PyQt6 中英双语桌面 GUI。

### 启动 API

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### 启动 GUI

在有图形桌面的环境中执行：

```bash
uv run python gui.py
```

如果 API 不在本机：

```bash
uv run python gui.py --api-url http://API主机:8000
```

GUI 默认使用中文，可切换为 English。品牌值为 1（海康）、2（大华）、99（ONVIF 通用），3、4、5 预留给后续品牌；ONVIF 品牌默认端口 80，用户名默认 admin；海康和大华的 RTSP 端口通常为 554。

海康历史流使用 `Streaming/tracks` 回放格式，大华历史流使用 `cam/playback` 回放格式；两者都自动请求最近一分钟，并与实时流同时显示。

### 当前测试说明（中文）

- ONVIF：使用带 SD 卡且已经保存历史录像的摄像头测试，实时流和历史流探测均正常。
- 海康、大华：当前测试摄像头未接硬盘录像机（NVR），且摄像头不支持 SD 卡，因此没有可供测试的历史录像；实时流探测正常，历史流暂时无法验证。
- 如需验证海康或大华的历史流，请接入硬盘录像机或可用的 SD 卡，并确认测试时间窗口内已经产生录像。程序只负责探测并返回 RTSP 地址，不负责播放视频。

### Current test status (English)

- ONVIF: tested successfully with a camera that has an SD card containing recorded footage; both live and historical stream probing work.
- Hikvision and Dahua: the current test cameras are not connected to an NVR and do not support an SD card, so there is no recorded footage available for historical-stream testing. Live-stream probing works; historical-stream probing cannot currently be verified.
- To verify historical streams for Hikvision or Dahua, connect an NVR or a supported SD card and make sure recordings exist in the requested time window. The application probes and returns RTSP addresses; it does not play video.

### 跨平台一键运行与构建

目标：支持 macOS、Linux、Windows，用户点击应用即可启动地址探测 GUI，并自动启动本机 API 服务；GUI 不承担视频播放。

建议方案：

1. GUI 已内置本地 FastAPI 服务，直接启动 GUI 即可运行；只有使用 --api-url 时才连接外部 API。
2. 使用 PyInstaller 的 `onedir` 模式分别构建 macOS、Linux、Windows 版本；PyInstaller 不能可靠地跨操作系统交叉打包，因此每个平台都在对应系统构建。
3. 打包时显式携带 `wsdl/` 目录、Qt 平台插件和 OpenCV/FFmpeg 运行库。
4. 第一阶段输出可压缩分发包：macOS `.app`、Windows 文件夹或安装包、Linux tar.gz；稳定后再补 DMG、Windows Installer 和 AppImage。
5. 用 GitHub Actions 或各平台构建机自动生成发布包，并在干净系统上验证摄像头连接、实时流、历史流和 ONVIF。

注意：当前项目使用 PyQt6 6.7.1。PyQt6 采用 GPL 或商业许可；如果最终应用需要闭源分发，应评估切换到 LGPL 许可的 PySide6，或购买 PyQt 商业许可。

#### 本地构建前提

先在目标系统安装 Python 3.10+ 和 uv。PyInstaller 必须在目标操作系统上构建，不能用 Linux 构建 Windows 或 macOS 包。

#### Linux

~~~bash
uv sync --dev
bash packaging/build_linux.sh
~~~

输出：dist/CameraRTSPProbe-linux-<架构>.tar.gz。

#### macOS

~~~bash
uv sync --dev
bash packaging/build_macos.sh
~~~

输出：dist/CameraRTSPProbe-macos-<架构>.zip。首次运行可能需要在系统安全设置中允许应用。

#### Windows PowerShell

~~~powershell
uv sync --dev
Set-ExecutionPolicy -Scope Process Bypass
.\packaging\build_windows.ps1
~~~

输出：dist/CameraRTSPProbe-windows.zip。

#### GitHub Actions

推送 v* 标签或在 Actions 页面手动运行 Build desktop packages，会分别生成 Linux、macOS、Windows 构建产物。Linux ARM64 仍应在 ARM64 构建机上执行，GitHub 默认 runner 主要是 x86_64。
