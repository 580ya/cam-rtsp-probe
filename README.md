# cam-rtsp-probe

## 中文

这是一个用于探测摄像头实时 RTSP 地址和最近一分钟历史 RTSP 地址的 FastAPI 项目，附带 PyQt6 中英双语桌面 GUI。

程序负责连接摄像头、验证 RTSP 地址是否能够读取到视频帧，并返回可用地址；GUI 不负责播放视频。

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

GUI 默认使用中文，可切换为 English。

品牌值：

- `1`：海康
- `2`：大华
- `99`：ONVIF 通用
- `3`、`4`、`5`：预留给后续品牌

端口约定：

- ONVIF 默认使用 HTTP 端口 `80`
- 海康和大华默认使用 RTSP 端口 `554`
- 用户名默认值为 `admin`

海康历史流使用 `Streaming/tracks` 回放格式，大华历史流使用 `cam/playback` 回放格式；两者都会自动请求最近一分钟的历史地址，并验证地址是否有效。

### 当前测试说明

- ONVIF：使用带 SD 卡且已经保存历史录像的摄像头测试，实时流和历史流探测均正常。
- 海康、大华：当前测试摄像头未接硬盘录像机（NVR），且摄像头不支持 SD 卡，因此没有可供测试的历史录像；实时流探测正常，历史流暂时无法验证。
- 如需验证海康或大华的历史流，请接入硬盘录像机或可用的 SD 卡，并确认测试时间窗口内已经产生录像。
- 程序只负责探测并返回 RTSP 地址，不负责播放视频。

### 跨平台一键运行与构建

目标是支持 macOS、Linux、Windows，用户点击应用即可启动地址探测 GUI，并自动启动本机 API 服务。

实现说明：

1. GUI 已内置本地 FastAPI 服务，直接启动 GUI 即可运行；只有使用 `--api-url` 时才连接外部 API。
2. 使用 PyInstaller 的 `onedir` 模式分别构建 macOS、Linux、Windows 版本。PyInstaller 不能可靠地跨操作系统交叉打包，因此每个平台都应在对应系统上构建。
3. 打包时会显式携带 `wsdl/` 目录、Qt 平台插件以及 OpenCV/PyAV 运行库。
4. 构建结果为可压缩分发包：macOS `.app`、Windows 文件夹、Linux tar.gz。
5. GitHub Actions 可自动生成各平台发布包；应在有实际摄像头条件的环境中验证摄像头连接、实时流、历史流和 ONVIF。

注意：当前项目使用 PyQt6 6.7.1。PyQt6 采用 GPL 或商业许可；如果最终应用需要闭源分发，应评估切换到 LGPL 许可的 PySide6，或购买 PyQt 商业许可。

#### 本地构建前提

先在目标系统安装 Python 3.10+ 和 uv。PyInstaller 必须在目标操作系统上构建，不能用 Linux 构建 Windows 或 macOS 包。

#### Linux

```bash
uv sync --dev
bash packaging/build_linux.sh
```

输出：

```
dist/CameraRTSPProbe-linux-<架构>.tar.gz
```

#### macOS

```bash
uv sync --dev
bash packaging/build_macos.sh
```

输出：

```
dist/CameraRTSPProbe-macos-<架构>.zip
```

首次运行 macOS 应用时，可能需要在系统安全设置中允许应用。

#### Windows PowerShell

```powershell
uv sync --dev
Set-ExecutionPolicy -Scope Process Bypass
.\packaging\build_windows.ps1
```

输出：

```
dist/CameraRTSPProbe-windows.zip
```

#### GitHub Actions

推送 `v*` 标签，或在 Actions 页面手动运行 **Build desktop packages**，会分别生成 Linux、macOS、Windows 构建产物。

Linux ARM64 仍应在 ARM64 构建机上执行；GitHub 默认 runner 主要是 x86_64。

## English

This project provides a FastAPI service for probing live RTSP addresses and historical RTSP addresses from the most recent one-minute window. It also includes a bilingual PyQt6 desktop GUI.

The application connects to the camera, verifies whether an RTSP address can actually read video frames, and returns usable addresses. The GUI does not play video.

### Start the API

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### Start the GUI

Run the following command in a graphical desktop environment:

```bash
uv run python gui.py
```

If the API is running on another host:

```bash
uv run python gui.py --api-url http://API_HOST:8000
```

The GUI uses Chinese by default and can be switched to English.

Brand values:

- `1`: Hikvision
- `2`: Dahua
- `99`: Generic ONVIF
- `3`, `4`, `5`: Reserved for future brands

Port conventions:

- ONVIF uses HTTP port `80` by default
- Hikvision and Dahua use RTSP port `554` by default
- The default username is `admin`

Hikvision historical streams use the `Streaming/tracks` playback format. Dahua historical streams use the `cam/playback` format. Both are requested for the most recent one-minute window, and the returned addresses are validated.

### Current test status

- ONVIF: tested successfully with a camera that has an SD card containing recorded footage; both live and historical stream probing work.
- Hikvision and Dahua: the current test cameras are not connected to an NVR and do not support an SD card, so no recorded footage is available for historical-stream testing. Live-stream probing works; historical-stream probing cannot currently be verified.
- To verify historical streams for Hikvision or Dahua, connect an NVR or a supported SD card and make sure recordings exist in the requested time window.
- The application probes and returns RTSP addresses; it does not play video.

### Cross-platform one-click running and building

The goal is to support macOS, Linux, and Windows so that users can launch the address-probing GUI by clicking the application. The GUI automatically starts the local API service.

Implementation notes:

1. The GUI includes a local FastAPI service and can run directly. It connects to an external API only when `--api-url` is specified.
2. macOS, Linux, and Windows packages are built separately with PyInstaller in `onedir` mode. PyInstaller should not be expected to cross-build reliably between operating systems, so each package should be built on its target operating system.
3. The build explicitly includes the `wsdl/` directory, Qt platform plugins, and the OpenCV/PyAV runtime libraries.
4. The build outputs are compressed distributable packages: a macOS `.app`, a Windows directory, and a Linux tar.gz archive.
5. GitHub Actions can generate packages for each platform. Camera connectivity, live streams, historical streams, and ONVIF should be tested on a system with access to real cameras.

Note: this project currently uses PyQt6 6.7.1. PyQt6 is licensed under the GPL or a commercial license. If the final application needs closed-source distribution, consider switching to LGPL-licensed PySide6 or purchasing a commercial PyQt license.

#### Local build prerequisites

Install Python 3.10+ and uv on the target system first. PyInstaller must build on the target operating system; Linux cannot reliably build Windows or macOS packages.

#### Linux

```bash
uv sync --dev
bash packaging/build_linux.sh
```

Output:

```
dist/CameraRTSPProbe-linux-<architecture>.tar.gz
```

#### macOS

```bash
uv sync --dev
bash packaging/build_macos.sh
```

Output:

```
dist/CameraRTSPProbe-macos-<architecture>.zip
```

When the macOS application is launched for the first time, macOS may require permission in the system security settings.

#### Windows PowerShell

```powershell
uv sync --dev
Set-ExecutionPolicy -Scope Process Bypass
.\packaging\build_windows.ps1
```

Output:

```
dist/CameraRTSPProbe-windows.zip
```

#### GitHub Actions

Push a `v*` tag, or manually run **Build desktop packages** from the Actions page, to generate Linux, macOS, and Windows build artifacts.

Linux ARM64 must still be built on an ARM64 machine. GitHub-hosted runners are primarily x86_64.
