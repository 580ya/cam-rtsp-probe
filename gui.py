# -*- coding: utf-8 -*-
"""摄像头 RTSP 地址探测 GUI。"""

import argparse
import asyncio
import json
import socket
import sys
import urllib.error
import urllib.request

import uvicorn
from PyQt6.QtCore import QThread, Qt, pyqtSignal
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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from func.debug_log import get_log_path
from main import app as api_app


# 界面支持的语言文案。
LANGUAGES = {
    "zh": {
        "window_title": "摄像头 RTSP 地址探测器",
        "camera_input": "摄像头信息",
        "ip": "IP 地址",
        "port": "端口",
        "onvif_port": "ONVIF 端口",
        "rtsp_port": "RTSP 端口",
        "user": "用户名",
        "password": "密码",
        "brand": "品牌",
        "hik": "1：海康",
        "dahua": "2：大华",
        "onvif": "99：ONVIF 通用",
        "language": "语言",
        "chinese": "中文",
        "english": "English",
        "probe": "探测 RTSP 地址",
        "api": "API 地址：{url}",
        "debug_log": "调试日志：{path}",
        "api_starting": "正在启动本地 API……",
        "api_ready": "本地 API 已启动",
        "api_error": "本地 API 启动失败：{error}",
        "history_note": "历史地址固定探测最近 1 分钟；探测只验证地址可访问，不拉流播放。",
        "live_url": "实时 RTSP 地址",
        "replay_url": "历史 RTSP 地址（最近 1 分钟）",
        "copy": "复制地址",
        "copied": "地址已复制",
        "no_stream": "未返回地址",
        "loading": "正在探测……",
        "probe_success": "探测完成",
        "probe_missing": "探测完成，但未获取：{items}",
        "missing_live": "实时 RTSP 地址",
        "missing_replay": "历史 RTSP 地址",
        "probe_failed": "探测失败：{error}",
        "required_ip": "请输入 IP 地址",
    },
    "en": {
        "window_title": "Camera RTSP Address Probe",
        "camera_input": "Camera information",
        "ip": "IP address",
        "port": "Port",
        "onvif_port": "ONVIF port",
        "rtsp_port": "RTSP port",
        "user": "Username",
        "password": "Password",
        "brand": "Brand",
        "hik": "1: Hikvision",
        "dahua": "2: Dahua",
        "onvif": "99: Generic ONVIF",
        "language": "Language",
        "chinese": "中文",
        "english": "English",
        "probe": "Probe RTSP addresses",
        "api": "API URL: {url}",
        "debug_log": "Debug log: {path}",
        "api_starting": "Starting local API...",
        "api_ready": "Local API is ready",
        "api_error": "Local API failed: {error}",
        "history_note": "Replay always probes the latest 1 minute; probing validates access but does not play the stream.",
        "live_url": "Live RTSP address",
        "replay_url": "Replay RTSP address (latest 1 minute)",
        "copy": "Copy address",
        "copied": "Address copied",
        "no_stream": "No address returned",
        "loading": "Probing...",
        "probe_success": "Probe completed",
        "probe_missing": "Probe completed, but no address was obtained for: {items}",
        "missing_live": "live RTSP address",
        "missing_replay": "replay RTSP address",
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


class MainWindow(QMainWindow):
    """摄像头 RTSP 地址探测主窗口。"""

    def __init__(self, api_url=None):
        """创建主窗口和输入控件。

        参数：可选外部 API 服务根地址；不传时由 GUI 启动本地 API。
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
        # 默认使用中文界面。
        self.language = "zh"
        # 保存探测线程引用，避免线程被提前回收。
        self.probe_worker = None
        # 保存本地 API 线程引用。
        self.api_server = None
        if self.embedded_api:
            # 创建 GUI 内置的本地 API 服务线程。
            self.api_server = ApiServerThread(self.api_port, self)
            self.api_server.ready.connect(self._on_api_ready)
            self.api_server.error.connect(self._on_api_error)
        # 创建 IP 输入框。
        self.ip_input = QLineEdit()
        # 创建端口输入框并设置 ONVIF 服务默认端口。
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(80)
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
        self.brand_input.setCurrentIndex(2)
        self._port_default = 80  # 当前品牌对应的默认端口。
        # 创建语言选择框，默认选中中文。
        self.language_input = QComboBox()
        self.language_input.addItem("", "zh")
        self.language_input.addItem("", "en")
        self.language_input.currentIndexChanged.connect(self._on_language_changed)
        self.brand_input.currentIndexChanged.connect(self._on_brand_changed)
        # 创建探测按钮。
        self.probe_button = QPushButton()
        self.probe_button.clicked.connect(self._start_probe)
        # 创建 API 地址提示。
        self.api_label = QLabel()
        # 创建调试日志路径提示。
        self.debug_label = QLabel()
        # 创建历史时间范围提示。
        self.history_note = QLabel()
        self.history_note.setWordWrap(True)
        # 创建整体状态提示。
        self.status_label = QLabel()
        # 创建结果区域。
        self.live_group, self.live_url_input, self.live_copy_button = self._create_result_group()
        self.replay_group, self.replay_url_input, self.replay_copy_button = self._create_result_group()
        # 绑定复制按钮。
        self.live_copy_button.clicked.connect(lambda: self._copy_url("live"))
        self.replay_copy_button.clicked.connect(lambda: self._copy_url("replay"))
        # 组装窗口布局。
        self._build_layout()
        # 设置初始文案。
        self._retranslate()
        if self.api_server is not None:
            # API 启动期间禁止用户发起探测。
            self.probe_button.setEnabled(False)
            self.status_label.setText(self._text("api_starting"))
            self.api_server.start()

    def _create_result_group(self):
        """创建一个 RTSP 地址结果分组。

        参数：无。
        返回：分组框、只读地址框和复制按钮。
        """
        # 创建结果分组框。
        group = QGroupBox()
        # 创建结果分组布局。
        layout = QVBoxLayout(group)
        # 创建只读 RTSP 地址输入框。
        url_input = QLineEdit()
        url_input.setReadOnly(True)
        url_input.setPlaceholderText("rtsp://...")
        # 创建复制按钮。
        copy_button = QPushButton()
        # 创建地址和按钮的横向布局。
        row_layout = QHBoxLayout()
        row_layout.addWidget(url_input, 1)
        row_layout.addWidget(copy_button)
        # 将地址行加入结果分组。
        layout.addLayout(row_layout)
        return group, url_input, copy_button

    def _build_layout(self):
        """构建输入区域和地址结果区域。

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
        # 创建主布局并加入所有区域。
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.addWidget(self.input_group)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.debug_label)
        main_layout.addWidget(self.history_note)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.live_group)
        main_layout.addWidget(self.replay_group)
        self.setCentralWidget(central_widget)
        # 设置适合显示长 RTSP 地址的初始窗口大小。
        self.resize(1100, 420)

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
        port_key = "onvif_port" if self.brand_input.currentData() == 99 else "rtsp_port"
        self.port_label.setText(self._text(port_key))
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
        self.debug_label.setText(self._text("debug_log", path=str(get_log_path())))
        self.history_note.setText(self._text("history_note"))
        self.live_group.setTitle(self._text("live_url"))
        self.replay_group.setTitle(self._text("replay_url"))
        self.live_copy_button.setText(self._text("copy"))
        self.replay_copy_button.setText(self._text("copy"))

    def _on_api_ready(self):
        """处理内置 API 启动完成事件。

        参数：无。
        返回：无。
        """
        # API 可用后允许用户发起地址探测。
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

    def _on_brand_changed(self, index):
        """根据品牌切换端口默认值和端口标签。

        参数：品牌下拉框索引。
        返回：无。
        """
        # 读取当前品牌值。
        brand = self.brand_input.itemData(index)
        # ONVIF 使用 HTTP 服务端口，海康/大华使用 RTSP 端口。
        new_default = 80 if brand == 99 else 554
        # 只有用户未手动修改默认值时才自动切换端口。
        if self.port_input.value() == self._port_default:
            self.port_input.setValue(new_default)
        # 保存当前品牌默认值，供下一次切换判断。
        self._port_default = new_default
        # 刷新端口标签和其他界面文案。
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
        # 组装 API 请求体。
        payload = {
            "ip": ip,
            "port": self.port_input.value(),
            "user": self.user_input.text(),
            "password": self.password_input.text(),
            "brand": self.brand_input.currentData(),
        }
        # 禁止重复点击并显示探测状态。
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
        # 取出实时地址。
        live_url = result.get("live_url") or ""
        # 取出历史地址。
        replay_url = result.get("replay_url") or ""
        # 只显示探测结果，不创建视频播放连接。
        self.live_url_input.setText(live_url)
        self.replay_url_input.setText(replay_url)
        # 只有返回有效地址时才允许复制。
        self.live_copy_button.setEnabled(bool(live_url))
        self.replay_copy_button.setEnabled(bool(replay_url))
        # 根据缺失的结果明确提示用户是哪一种地址未获取。
        missing_items = []
        if not live_url:
            missing_items.append(self._text("missing_live"))
        if not replay_url:
            missing_items.append(self._text("missing_replay"))
        if missing_items:
            # 中文使用顿号，英文使用逗号分隔缺失项目。
            separator = "、" if self.language == "zh" else ", "
            self.status_label.setText(
                self._text(
                    "probe_missing",
                    items=separator.join(missing_items),
                )
            )
        else:
            # 两种地址都通过验证时显示完整成功状态。
            self.status_label.setText(self._text("probe_success"))

    def _on_probe_error(self, error):
        """显示 API 调用错误。

        参数：错误文本。
        返回：无。
        """
        # 将后台错误显示在主状态栏。
        self.status_label.setText(self._text("probe_failed", error=error))

    def _copy_url(self, kind):
        """复制指定类型的 RTSP 地址。

        参数：地址类型（live/replay）。
        返回：无。
        """
        # 选择需要复制的地址输入框。
        url_input = self.live_url_input if kind == "live" else self.replay_url_input
        # 读取当前探测到的地址。
        url = url_input.text()
        if url:
            # 将地址写入 Qt 系统剪贴板。
            QApplication.clipboard().setText(url)
            # 提示复制完成。
            self.status_label.setText(self._text("copied"))

    def closeEvent(self, event):
        """关闭窗口前停止后台线程。

        参数：Qt 关闭事件。
        返回：无。
        """
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
    parser = argparse.ArgumentParser(description="Camera RTSP address probe GUI")
    # 提供外部 API 服务地址覆盖选项。
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
