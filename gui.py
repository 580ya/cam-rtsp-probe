# -*- coding: utf-8 -*-
"""摄像头 RTSP 探测与播放 GUI。"""

import argparse
import asyncio
import socket
import json
import os
import sys
import urllib.error
import urllib.request

import cv2
import uvicorn

from main import app as api_app
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


# 界面支持的语言文案。
LANGUAGES = {
    "zh": {
        "window_title": "摄像头 RTSP 探测器",
        "camera_input": "摄像头信息",
        "ip": "IP 地址",
        "port": "端口",
        "user": "用户名",
        "password": "密码",
        "brand": "品牌",
        "hik": "1：海康",
        "dahua": "2：大华",
        "onvif": "99：ONVIF 通用",
        "language": "语言",
        "chinese": "中文",
        "english": "English",
        "probe": "获取实时和历史流",
        "api": "API 地址：{url}",
        "api_starting": "正在启动本地 API……",
        "api_ready": "本地 API 已启动",
        "api_error": "本地 API 启动失败：{error}",
        "history_note": "历史流固定请求最近 1 分钟；ONVIF 模式的端口按现有 API 作为服务端口使用。",
        "live": "实时流",
        "replay": "历史流（最近 1 分钟）",
        "waiting": "等待播放",
        "loading": "正在连接……",
        "no_stream": "未返回流地址",
        "stream_error": "播放失败：{error}",
        "probe_success": "探测完成",
        "probe_failed": "探测失败：{error}",
        "required_ip": "请输入 IP 地址",
    },
    "en": {
        "window_title": "Camera RTSP Probe",
        "camera_input": "Camera information",
        "ip": "IP address",
        "port": "Port",
        "user": "Username",
        "password": "Password",
        "brand": "Brand",
        "hik": "1: Hikvision",
        "dahua": "2: Dahua",
        "onvif": "99: Generic ONVIF",
        "language": "Language",
        "chinese": "中文",
        "english": "English",
        "probe": "Get live and replay streams",
        "api": "API URL: {url}",
        "api_starting": "Starting local API...",
        "api_ready": "Local API is ready",
        "api_error": "Local API failed: {error}",
        "history_note": "Replay always requests the latest 1 minute; for ONVIF the port is used as the service port by the existing API.",
        "live": "Live stream",
        "replay": "Replay stream (latest 1 minute)",
        "waiting": "Waiting for stream",
        "loading": "Connecting...",
        "no_stream": "No stream URL returned",
        "stream_error": "Playback failed: {error}",
        "probe_success": "Probe completed",
        "probe_failed": "Probe failed: {error}",
        "required_ip": "Please enter an IP address",
    },
}



def _get_free_port():
    """获取本机可用的临时 TCP 端口。

    参数：无。
    返回：可用端口号。
    """
    # 创建临时 TCP 套接字，向操作系统申请随机端口。
    socket_handle = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # 绑定本地回环地址，避免 API 暴露到局域网。
        socket_handle.bind(("127.0.0.1", 0))
        # 读取系统分配的端口号。
        free_port = socket_handle.getsockname()[1]
        return free_port
    finally:
        # 释放临时端口，让 uvicorn 使用该端口启动。
        socket_handle.close()


class ApiServerThread(QThread):
    """在 GUI 后台线程中运行本地 FastAPI 服务。"""

    ready = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, port, parent=None):
        """初始化本地 API 服务线程。

        参数：监听端口和 Qt 父对象。
        返回：无。
        """
        super().__init__(parent)
        # 保存 API 监听端口。
        self.port = port
        # 保存 uvicorn 服务对象。
        self.server = None

    async def _serve(self):
        """启动并保持 uvicorn 服务运行。

        参数：无。
        返回：无。
        """
        # 创建只监听本机回环地址的 uvicorn 配置。
        config = uvicorn.Config(
            api_app,
            host="127.0.0.1",
            port=self.port,
            log_level="warning",
        )
        # 创建 uvicorn 服务实例。
        self.server = uvicorn.Server(config)
        # 初始化 lifespan，startup() 依赖该对象。
        if not config.loaded:
            config.load()
        self.server.lifespan = config.lifespan_class(config)
        # 完成 socket 绑定和应用启动。
        await self.server.startup()
        # 通知 GUI API 已经可以接收请求。
        self.ready.emit()
        # 运行服务主循环，直到 GUI 请求退出。
        await self.server.main_loop()
        # 仅在服务成功启动后释放 uvicorn 资源。
        if self.server.started:
            await self.server.shutdown()

    def run(self):
        """在线程中运行异步 API 服务。

        参数：无。
        返回：无。
        """
        try:
            # 在线程私有事件循环中启动 FastAPI。
            asyncio.run(self._serve())
        except Exception as exc:
            # 将服务启动或关闭异常传递给 GUI。
            self.error.emit(str(exc))

    def stop(self):
        """请求停止本地 API 服务。

        参数：无。
        返回：无。
        """
        # 设置 uvicorn 退出标志，让主循环安全结束。
        if self.server is not None:
            self.server.should_exit = True


class ProbeWorker(QThread):
    """在后台线程中调用探测 API，避免阻塞 GUI。"""

    result_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, api_url, payload, parent=None):
        """初始化 API 请求线程。

        参数：API 地址、请求数据和 Qt 父对象。
        返回：无。
        """
        super().__init__(parent)
        # 保存 API 地址，供后台请求使用。
        self.api_url = api_url
        # 保存摄像头探测请求体。
        self.payload = payload

    def run(self):
        """发送探测请求并发出结果信号。

        参数：无。
        返回：无。
        """
        try:
            # 将请求模型序列化为 UTF-8 JSON。
            request_data = json.dumps(self.payload).encode("utf-8")
            # 构造 API POST 请求。
            request = urllib.request.Request(
                f"{self.api_url}/api/v1/rtsp/probe",
                data=request_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            # 发起请求，探测过程可能包含多个 RTSP 连接尝试。
            with urllib.request.urlopen(request, timeout=90) as response:
                # 解析 API 返回的 JSON 数据。
                response_data = json.loads(response.read().decode("utf-8"))
            self.result_ready.emit(response_data)
        except urllib.error.HTTPError as exc:
            # 读取 FastAPI 的错误响应，便于用户定位输入问题。
            detail = exc.read().decode("utf-8", errors="replace")
            self.error.emit(f"HTTP {exc.code}: {detail}")
        except Exception as exc:
            # 将网络和 JSON 等异常转换为 GUI 可显示文本。
            self.error.emit(str(exc))


class StreamWorker(QThread):
    """在后台线程中读取 RTSP 帧并发送给 Qt 界面。"""

    frame_ready = pyqtSignal(QImage)
    error = pyqtSignal(str)

    def __init__(self, url, parent=None):
        """初始化 RTSP 播放线程。

        参数：RTSP 地址和 Qt 父对象。
        返回：无。
        """
        super().__init__(parent)
        # 保存当前播放地址。
        self.url = url
        # 用于通知读取循环停止。
        self._stopping = False

    def stop(self):
        """请求停止 RTSP 读取。

        参数：无。
        返回：无。
        """
        # 设置停止标志，读取循环将在下一帧结束。
        self._stopping = True

    def run(self):
        """持续读取 RTSP 帧并转换为 QImage。

        参数：无。
        返回：无。
        """
        # 让 OpenCV 优先使用 TCP，适合跨网段摄像头连接。
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000"
        # 创建 OpenCV 视频捕获对象。
        capture = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        if not capture.isOpened():
            self.error.emit("unable to open RTSP stream")
            capture.release()
            return

        try:
            # 读取直到用户停止、回放结束或设备断开。
            while not self._stopping:
                # 从 RTSP 连接读取一帧 BGR 图像。
                ok, frame = capture.read()
                if not ok:
                    self.error.emit("no more frames or connection lost")
                    break
                # 将 OpenCV 的 BGR 图像转换为 Qt 使用的 RGB 图像。
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # 读取图像尺寸和通道信息。
                height, width, channels = rgb_frame.shape
                # 复制图像数据，确保信号跨线程后仍然有效。
                image = QImage(
                    rgb_frame.data,
                    width,
                    height,
                    channels * width,
                    QImage.Format.Format_RGB888,
                ).copy()
                self.frame_ready.emit(image)
                # 限制 GUI 更新频率，避免占满主线程事件循环。
                self.msleep(30)
        except Exception as exc:
            # 将 OpenCV 解码异常传递给界面。
            self.error.emit(str(exc))
        finally:
            # 无论连接如何结束都释放摄像头句柄。
            capture.release()


class MainWindow(QMainWindow):
    """摄像头 RTSP 探测和双流预览主窗口。"""

    def __init__(self, api_url=None):
        """创建主窗口和输入控件。

        参数：API 服务根地址。
        返回：无。
        """
        super().__init__()
        # 标记是否由 GUI 自己启动本地 API。
        self.embedded_api = api_url is None
        # 获取外部 API 地址或准备本地 API 端口。
        self.api_port = _get_free_port() if self.embedded_api else None
        self.api_url = (
            f"http://127.0.0.1:{self.api_port}"
            if self.embedded_api
            else api_url.rstrip("/")
        )
        # 保存本地 API 线程引用。
        self.api_server = None
        # 默认使用中文界面。
        self.language = "zh"
        # 保存探测线程引用，避免线程被提前回收。
        self.probe_worker = None
        # 保存实时播放线程引用。
        self.live_worker = None
        # 保存历史播放线程引用。
        self.replay_worker = None
        if self.embedded_api:
            # 创建 GUI 内置的本地 API 服务线程。
            self.api_server = ApiServerThread(self.api_port, self)
            self.api_server.ready.connect(self._on_api_ready)
            self.api_server.error.connect(self._on_api_error)
        # 创建 IP 输入框。
        self.ip_input = QLineEdit()
        # 创建端口输入框并设置用户要求的默认值。
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(554)
        # 创建用户名输入框并设置默认用户。
        self.user_input = QLineEdit("admin")
        # 创建密码输入框并隐藏密码字符。
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        # 创建品牌选择框，ONVIF 对外使用 99。
        self.brand_input = QComboBox()
        self.brand_input.addItem("", 1)
        self.brand_input.addItem("", 2)
        self.brand_input.addItem("", 99)
        # 创建语言选择框，默认选中中文。
        self.language_input = QComboBox()
        self.language_input.addItem("", "zh")
        self.language_input.addItem("", "en")
        self.language_input.currentIndexChanged.connect(self._on_language_changed)
        # 创建探测按钮。
        self.probe_button = QPushButton()
        self.probe_button.clicked.connect(self._start_probe)
        # 创建 API 地址提示。
        self.api_label = QLabel()
        # 创建历史时间范围提示。
        self.history_note = QLabel()
        self.history_note.setWordWrap(True)
        # 创建整体状态提示。
        self.status_label = QLabel()
        # 创建实时视频标签。
        self.live_view = self._create_video_view()
        # 创建历史视频标签。
        self.replay_view = self._create_video_view()
        # 创建实时流状态标签。
        self.live_status = QLabel()
        # 创建历史流状态标签。
        self.replay_status = QLabel()
        # 组装窗口布局。
        self._build_layout()
        # 设置初始文案。
        self._retranslate()
        if self.api_server is not None:
            # API 启动期间禁止用户发起探测。
            self.probe_button.setEnabled(False)
            self.status_label.setText(self._text("api_starting"))
            self.api_server.start()

    def _create_video_view(self):
        """创建一个用于显示视频帧的 QLabel。

        参数：无。
        返回：配置好的视频标签。
        """
        # 创建黑色背景的视频显示区域。
        view = QLabel()
        view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        view.setMinimumSize(480, 270)
        view.setStyleSheet("background: #111; color: #ddd;")
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return view

    def _build_layout(self):
        """构建输入区域和双视频区域。

        参数：无。
        返回：无。
        """
        # 创建摄像头输入分组。
        self.input_group = QGroupBox()
        # 创建表单布局。
        form_layout = QFormLayout(self.input_group)
        # 创建每个表单字段的标签。
        self.ip_label = QLabel()
        self.port_label = QLabel()
        self.user_label = QLabel()
        self.password_label = QLabel()
        self.brand_label = QLabel()
        self.language_label = QLabel()
        # 按用户要求排列摄像头输入项。
        form_layout.addRow(self.ip_label, self.ip_input)
        form_layout.addRow(self.port_label, self.port_input)
        form_layout.addRow(self.user_label, self.user_input)
        form_layout.addRow(self.password_label, self.password_input)
        form_layout.addRow(self.brand_label, self.brand_input)
        form_layout.addRow(self.language_label, self.language_input)
        # 创建控制区域。
        control_layout = QHBoxLayout()
        control_layout.addWidget(self.probe_button)
        control_layout.addWidget(self.api_label, 1)
        # 创建实时视频分组。
        self.live_group = QGroupBox()
        live_layout = QVBoxLayout(self.live_group)
        live_layout.addWidget(self.live_view)
        live_layout.addWidget(self.live_status)
        # 创建历史视频分组。
        self.replay_group = QGroupBox()
        replay_layout = QVBoxLayout(self.replay_group)
        replay_layout.addWidget(self.replay_view)
        replay_layout.addWidget(self.replay_status)
        # 使用水平布局并排展示实时与历史流。
        video_layout = QHBoxLayout()
        video_layout.addWidget(self.live_group)
        video_layout.addWidget(self.replay_group)
        # 创建主布局并加入所有区域。
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.addWidget(self.input_group)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.history_note)
        main_layout.addWidget(self.status_label)
        main_layout.addLayout(video_layout, 1)
        self.setCentralWidget(central_widget)
        # 设置一个适合双视频预览的初始窗口大小。
        self.resize(1280, 760)

    def _text(self, key, **values):
        """读取当前语言的界面文案。

        参数：文案键和值格式化参数。
        返回：当前语言的文案字符串。
        """
        # 从当前语言字典获取文案。
        text = LANGUAGES[self.language][key]
        # 使用传入值完成动态文案格式化。
        return text.format(**values) if values else text

    def _retranslate(self):
        """刷新全部可见界面文案。

        参数：无。
        返回：无。
        """
        # 更新窗口和输入分组标题。
        self.setWindowTitle(self._text("window_title"))
        self.input_group.setTitle(self._text("camera_input"))
        # 更新表单标签。
        self.ip_label.setText(self._text("ip"))
        self.port_label.setText(self._text("port"))
        self.user_label.setText(self._text("user"))
        self.password_label.setText(self._text("password"))
        self.brand_label.setText(self._text("brand"))
        self.language_label.setText(self._text("language"))
        # 更新品牌选项和语言选项。
        self.brand_input.setItemText(0, self._text("hik"))
        self.brand_input.setItemText(1, self._text("dahua"))
        self.brand_input.setItemText(2, self._text("onvif"))
        self.language_input.setItemText(0, self._text("chinese"))
        self.language_input.setItemText(1, self._text("english"))
        # 更新控制和说明文案。
        self.probe_button.setText(self._text("probe"))
        self.api_label.setText(self._text("api", url=self.api_url))
        self.history_note.setText(self._text("history_note"))
        self.live_group.setTitle(self._text("live"))
        self.replay_group.setTitle(self._text("replay"))
        # 仅在未播放时刷新等待文案。
        if self.live_worker is None or not self.live_worker.isRunning():
            self.live_status.setText(self._text("waiting"))
        if self.replay_worker is None or not self.replay_worker.isRunning():
            self.replay_status.setText(self._text("waiting"))


    def _on_api_ready(self):
        """处理内置 API 启动完成事件。

        参数：无。
        返回：无。
        """
        # API 可用后允许用户发起摄像头探测。
        self.probe_button.setEnabled(True)
        # 显示本地服务已经就绪。
        self.status_label.setText(self._text("api_ready"))

    def _on_api_error(self, error):
        """显示内置 API 启动错误。

        参数：错误文本。
        返回：无。
        """
        # API 启动失败时保持探测按钮禁用。
        self.probe_button.setEnabled(False)
        # 将错误显示在主状态栏。
        self.status_label.setText(self._text("api_error", error=error))

    def _on_language_changed(self, index):
        """响应语言切换。

        参数：语言下拉框索引。
        返回：无。
        """
        # 读取下拉框中的语言代码。
        self.language = self.language_input.itemData(index)
        # 刷新界面文案。
        self._retranslate()

    def _start_probe(self):
        """校验输入并异步调用探测 API。

        参数：无。
        返回：无。
        """
        # 读取并清理摄像头 IP。
        ip = self.ip_input.text().strip()
        if not ip:
            self.status_label.setText(self._text("required_ip"))
            return
        # 停止上一次残留的播放线程。
        self._stop_stream("live")
        self._stop_stream("replay")
        # 组装 API 请求体。
        payload = {
            "ip": ip,
            "port": self.port_input.value(),
            "user": self.user_input.text(),
            "password": self.password_input.text(),
            "brand": self.brand_input.currentData(),
        }
        # 禁止重复点击并显示连接状态。
        self.probe_button.setEnabled(False)
        self.status_label.setText(self._text("loading"))
        # 创建后台探测线程。
        self.probe_worker = ProbeWorker(self.api_url, payload, self)
        self.probe_worker.result_ready.connect(self._on_probe_result)
        self.probe_worker.error.connect(self._on_probe_error)
        self.probe_worker.finished.connect(self._on_probe_finished)
        self.probe_worker.start()

    def _on_probe_finished(self):
        """恢复探测按钮状态。

        参数：无。
        返回：无。
        """
        # 探测线程结束后允许再次发起请求。
        self.probe_button.setEnabled(True)

    def _on_probe_result(self, result):
        """处理 API 返回的实时和历史地址。

        参数：API 返回的字典数据。
        返回：无。
        """
        # 取出实时流地址。
        live_url = result.get("live_url")
        # 取出历史流地址。
        replay_url = result.get("replay_url")
        # 清空旧的视频画面。
        self.live_view.clear()
        self.replay_view.clear()
        # 根据 API 返回结果启动两个独立播放线程。
        self._start_stream("live", live_url)
        self._start_stream("replay", replay_url)
        # 显示探测完成状态。
        self.status_label.setText(self._text("probe_success"))

    def _on_probe_error(self, error):
        """显示 API 调用错误。

        参数：错误文本。
        返回：无。
        """
        # 将后台错误显示在主状态栏。
        self.status_label.setText(self._text("probe_failed", error=error))

    def _start_stream(self, kind, url):
        """为指定流创建并启动播放线程。

        参数：流类型（live/replay）和 RTSP 地址。
        返回：无。
        """
        # 选择对应的显示控件和线程属性。
        view = self.live_view if kind == "live" else self.replay_view
        status = self.live_status if kind == "live" else self.replay_status
        attribute = "live_worker" if kind == "live" else "replay_worker"
        if not url:
            # API 没有返回可用地址时给出明确提示。
            view.setText(self._text("no_stream"))
            status.setText(self._text("no_stream"))
            return
        # 创建 RTSP 播放线程。
        worker = StreamWorker(url, self)
        worker.frame_ready.connect(
            lambda image, target=view: target.setPixmap(
                QPixmap.fromImage(image).scaled(
                    target.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )
        )
        worker.error.connect(
            lambda error, target=status: target.setText(
                self._text("stream_error", error=error)
            )
        )
        worker.started.connect(
            lambda target=status: target.setText(self._text("loading"))
        )
        worker.finished.connect(
            lambda target=status: target.setText(self._text("waiting"))
        )
        # 保存线程引用并开始读取。
        setattr(self, attribute, worker)
        worker.start()

    def _stop_stream(self, kind):
        """停止指定的视频线程。

        参数：流类型（live/replay）。
        返回：无。
        """
        # 选择对应的线程属性。
        attribute = "live_worker" if kind == "live" else "replay_worker"
        # 读取当前线程引用。
        worker = getattr(self, attribute)
        if worker is not None and worker.isRunning():
            # 请求线程停止并等待释放摄像头资源。
            worker.stop()
            worker.wait(3000)
        # 清除线程引用，便于下一次探测重新创建。
        setattr(self, attribute, None)

    def closeEvent(self, event):
        """关闭窗口前停止所有后台线程。

        参数：Qt 关闭事件。
        返回：无。
        """
        # 停止两个视频线程。
        self._stop_stream("live")
        self._stop_stream("replay")
        # 停止探测线程并等待其退出。
        if self.probe_worker is not None and self.probe_worker.isRunning():
            self.probe_worker.quit()
            self.probe_worker.wait(3000)
        # 停止内置 API 服务线程。
        if self.api_server is not None and self.api_server.isRunning():
            self.api_server.stop()
            self.api_server.wait(3000)
        # 继续 Qt 默认关闭流程。
        event.accept()


def main():
    """启动 PyQt6 GUI。

    参数：无，可选 --api-url 指定外部 API 地址；不指定时内置 API。
    返回：Qt 应用退出码。
    """
    # 创建命令行参数解析器。
    parser = argparse.ArgumentParser(description="Camera RTSP probe GUI")
    # 提供 API 服务地址覆盖选项。
    parser.add_argument("--api-url", default=None, help="use an external API service")
    # 解析命令行参数。
    args = parser.parse_args()
    # 创建 Qt 应用对象。
    application = QApplication(sys.argv)
    # 创建并显示主窗口。
    window = MainWindow(args.api_url)
    window.show()
    # 进入 Qt 事件循环并返回退出码。
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
