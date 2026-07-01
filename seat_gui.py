import json
import faulthandler
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

try:
    from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal
    from PyQt5.QtGui import QColor, QFont
    from PyQt5.QtWidgets import (
        QAction,
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QVBoxLayout,
        QWidget,
        QStyle,
    )
    from PyQt5.QtGui import QTextCursor
except ImportError as exc:
    print("缺少 PyQt5，请先运行：pip install -r requirements-gui.txt")
    print(f"原始错误：{exc}")
    raise SystemExit(1)

import seat_tool


faulthandler.enable()

APP_TITLE = "图书馆座位助手"
DEFAULT_CONFIG = Path("seat_accounts.json")


class LogProxy:
    def __init__(self, signal: pyqtSignal):
        self.signal = signal

    def __call__(self, *message: Any, account: Optional[str] = None, write_file: bool = True) -> None:
        original_log(*message, account=account, write_file=write_file)
        text = " ".join(map(str, message))
        if account:
            text = f"[{account}] {text}"
        self.signal.emit(text)


original_log = seat_tool.log


class SeatWorker(QObject):
    log = pyqtSignal(str)
    done = pyqtSignal(bool, str)

    def __init__(
        self,
        command: str,
        config_path: Path,
        account_name: Optional[str],
        interval: float,
        booking_send_mode: str,
        booking_send_time: str,
    ) -> None:
        super().__init__()
        self.command = command
        self.config_path = config_path
        self.account_name = account_name
        self.interval = interval
        self.booking_send_mode = booking_send_mode
        self.booking_send_time = booking_send_time

    def run(self) -> None:
        previous_log = seat_tool.log
        seat_tool.log = LogProxy(self.log)
        try:
            config = seat_tool.load_config(self.config_path)
            accounts = seat_tool.build_accounts(config, self.account_name)

            if self.command == "book" and self.booking_send_mode == "time":
                seat_tool.wait_until_clock_time(self.booking_send_time)

            failures = 0
            for account in accounts:
                token = seat_tool.login(account)
                if not token:
                    failures += 1
                    continue

                if self.command == "book":
                    ok = seat_tool.reserve(account, token, config)
                elif self.command == "status":
                    ok = seat_tool.get_latest_booking(account, token) is not None
                elif self.command == "leave-short":
                    ok = seat_tool.leave(account, token, config, "short")
                elif self.command == "leave-long":
                    ok = seat_tool.leave(account, token, config, "long")
                elif self.command == "signoff":
                    ok = seat_tool.signoff(account, token, config)
                else:
                    raise ValueError(f"未知命令：{self.command}")

                if not ok:
                    failures += 1

                if self.interval > 0:
                    self.log.emit(f"等待 {self.interval:g} 秒后继续下一个账号...")
                    QThread.sleep(int(self.interval))

            if failures:
                self.done.emit(False, f"完成，但有 {failures} 个账号失败")
            else:
                self.done.emit(True, "全部操作完成")
        except Exception as exc:
            self.done.emit(False, str(exc))
        finally:
            seat_tool.log = previous_log


class SeatCrawlWorker(QObject):
    log = pyqtSignal(str)
    done = pyqtSignal(bool, str, object)

    def __init__(self, config_path: Path, account_name: Optional[str]) -> None:
        super().__init__()
        self.config_path = config_path
        self.account_name = account_name

    def run(self) -> None:
        previous_log = seat_tool.log
        seat_tool.log = LogProxy(self.log)
        try:
            config = seat_tool.load_config(self.config_path)
            accounts = seat_tool.build_accounts(config, self.account_name)
            account = accounts[0]
            token = seat_tool.login(account)
            if not token:
                self.done.emit(False, "登录失败，无法爬取座位", {})
                return

            regions = seat_tool.get_all_regions(token, account.name)
            available_regions = []
            seats_by_region = {}
            total_seat_count = 0
            available_seat_count = 0
            for region in regions:
                region_seats = seat_tool.get_seats_by_region_with_stats(token, region.region_id, account.name)
                seats = region_seats.available_seats
                total_seat_count += region_seats.total_seats
                available_seat_count += len(seats)
                if seats:
                    available_regions.append(region)
                    seats_by_region[region.region_id] = seats
                self.log.emit(f"已爬取 {region.name}：{len(seats)} 个座位")

            occupied_seat_count = max(0, total_seat_count - available_seat_count)
            self.done.emit(True, f"爬取完成：{len(available_regions)} 个区域有可预约座位", {
                "regions": available_regions,
                "seats_by_region": seats_by_region,
                "total_seat_count": total_seat_count,
                "available_seat_count": available_seat_count,
                "occupied_seat_count": occupied_seat_count,
            })
        except Exception as exc:
            self.done.emit(False, str(exc), {})
        finally:
            seat_tool.log = previous_log


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config_path = DEFAULT_CONFIG
        self.thread: Optional[QThread] = None
        self.worker: Optional[SeatWorker] = None
        self.crawl_thread: Optional[QThread] = None
        self.crawl_worker: Optional[SeatCrawlWorker] = None
        self.seats_by_region = {}

        self.setWindowTitle(APP_TITLE)
        self.resize(1120, 760)
        self._build_ui()
        self._apply_style()
        self.load_config()

    def _build_ui(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard_tab = QWidget()
        self.config_tab = QWidget()
        self.log_tab = QWidget()
        self.tabs.addTab(self.dashboard_tab, "控制台")
        self.tabs.addTab(self.config_tab, "账号配置")
        self.tabs.addTab(self.log_tab, "运行日志")

        self._build_toolbar()
        self._build_dashboard()
        self._build_config_tab()
        self._build_log_tab()

        self.statusBar().showMessage("就绪")

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        style = self.style()
        reload_action = QAction(style.standardIcon(style.SP_BrowserReload), "重新加载配置", self)
        save_action = QAction(style.standardIcon(style.SP_DialogSaveButton), "保存配置", self)
        open_action = QAction(style.standardIcon(style.SP_DirOpenIcon), "选择配置文件", self)

        reload_action.triggered.connect(self.load_config)
        save_action.triggered.connect(self.save_config)
        open_action.triggered.connect(self.pick_config)

        toolbar.addAction(reload_action)
        toolbar.addAction(save_action)
        toolbar.addSeparator()
        toolbar.addAction(open_action)

    def _build_dashboard(self) -> None:
        root = QVBoxLayout(self.dashboard_tab)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(12)
        top_grid.setVerticalSpacing(12)
        root.addLayout(top_grid)

        summary = QGroupBox("当前配置")
        summary_layout = QFormLayout(summary)
        self.config_label = QLabel(str(self.config_path))
        self.config_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.account_count_label = QLabel("-")
        self.enabled_count_label = QLabel("-")
        self.default_seats_label = QLabel("-")
        self.library_people_label = QLabel("约 -- 人")
        summary_layout.addRow("配置文件", self.config_label)
        summary_layout.addRow("账号数量", self.account_count_label)
        summary_layout.addRow("启用账号", self.enabled_count_label)
        summary_layout.addRow("默认座位", self.default_seats_label)
        summary_layout.addRow("当前约人数", self.library_people_label)
        top_grid.addWidget(summary, 0, 0)

        run_box = QGroupBox("执行操作")
        run_layout = QFormLayout(run_box)
        self.account_combo = QComboBox()
        self.account_combo.addItem("全部启用账号", "")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(0, 60)
        self.interval_spin.setSuffix(" 秒")
        self.booking_mode_combo = QComboBox()
        self.booking_mode_combo.addItem("直接发送预约指令", "direct")
        self.booking_mode_combo.addItem("指定时间发送预约指令", "time")
        self.booking_time_input = QLineEdit("06:59:30")
        run_layout.addRow("目标账号", self.account_combo)
        run_layout.addRow("账号间隔", self.interval_spin)
        run_layout.addRow("预约发送", self.booking_mode_combo)
        run_layout.addRow("发送时间", self.booking_time_input)
        top_grid.addWidget(run_box, 0, 1)
        top_grid.setColumnStretch(0, 1)
        top_grid.setColumnStretch(1, 1)

        actions = QHBoxLayout()
        root.addLayout(actions)

        self.book_button = self._action_button("预约座位", "book", "SP_DialogApplyButton")
        self.status_button = self._action_button("查询预约", "status", "SP_FileDialogInfoView")
        self.short_button = self._action_button("短暂离开", "leave-short", "SP_ArrowForward")
        self.long_button = self._action_button("长暂离开", "leave-long", "SP_MediaSeekForward")
        self.signoff_button = self._action_button("签退", "signoff", "SP_DialogCloseButton")
        for button in (
            self.book_button,
            self.status_button,
            self.short_button,
            self.long_button,
            self.signoff_button,
        ):
            actions.addWidget(button)

        self.account_overview = QTableWidget(0, 5)
        self.account_overview.setHorizontalHeaderLabels(["启用", "名称", "账号", "座位优先级", "状态"])
        self.account_overview.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.account_overview.verticalHeader().setVisible(False)
        self.account_overview.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.account_overview, 1)

    def _build_config_tab(self) -> None:
        root = QVBoxLayout(self.config_tab)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        defaults = QGroupBox("默认参数")
        defaults_layout = QGridLayout(defaults)
        self.default_seats_input = QLineEdit()
        self.end_time_input = QLineEdit()
        self.rush_seconds_spin = QSpinBox()
        self.rush_seconds_spin.setRange(1, 120)
        self.channel_spin = QSpinBox()
        self.channel_spin.setRange(1, 999999)
        self.leave_channel_spin = QSpinBox()
        self.leave_channel_spin.setRange(1, 999999)

        defaults_layout.addWidget(QLabel("默认座位"), 0, 0)
        defaults_layout.addWidget(self.default_seats_input, 0, 1)
        defaults_layout.addWidget(QLabel("结束时间"), 0, 2)
        defaults_layout.addWidget(self.end_time_input, 0, 3)
        defaults_layout.addWidget(QLabel("抢座秒数"), 1, 0)
        defaults_layout.addWidget(self.rush_seconds_spin, 1, 1)
        defaults_layout.addWidget(QLabel("预约 channel"), 1, 2)
        defaults_layout.addWidget(self.channel_spin, 1, 3)
        defaults_layout.addWidget(QLabel("暂离 channelType"), 2, 0)
        defaults_layout.addWidget(self.leave_channel_spin, 2, 1)
        root.addWidget(defaults)

        account_tools = QHBoxLayout()
        add_button = QPushButton("新增账号")
        remove_button = QPushButton("删除选中")
        add_button.clicked.connect(self.add_account_row)
        remove_button.clicked.connect(self.remove_selected_account)
        account_tools.addWidget(add_button)
        account_tools.addWidget(remove_button)
        account_tools.addStretch(1)
        root.addLayout(account_tools)

        self.accounts_table = QTableWidget(0, 5)
        self.accounts_table.setHorizontalHeaderLabels(["启用", "名称", "账号", "密码", "座位列表"])
        self.accounts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.accounts_table.verticalHeader().setVisible(False)
        root.addWidget(self.accounts_table, 1)

        picker = QGroupBox("从座位列表选择")
        picker_layout = QGridLayout(picker)
        self.region_combo = QComboBox()
        self.seat_combo = QComboBox()
        crawl_button = QPushButton("刷新座位列表")
        add_seat_button = QPushButton("添加到选中账号")
        crawl_button.clicked.connect(self.start_seat_crawl)
        add_seat_button.clicked.connect(self.add_selected_seat_to_account)
        self.region_combo.currentIndexChanged.connect(self.refresh_seat_combo)

        picker_layout.addWidget(QLabel("区域"), 0, 0)
        picker_layout.addWidget(self.region_combo, 0, 1)
        picker_layout.addWidget(crawl_button, 0, 2)
        picker_layout.addWidget(QLabel("座位"), 1, 0)
        picker_layout.addWidget(self.seat_combo, 1, 1)
        picker_layout.addWidget(add_seat_button, 1, 2)
        root.addWidget(picker)

        hint = QLabel("可通过“刷新座位列表”爬取座位，再从下拉框选择座位加入账号配置。")
        hint.setObjectName("hint")
        root.addWidget(hint)

    def _build_log_tab(self) -> None:
        root = QVBoxLayout(self.log_tab)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        bar = QHBoxLayout()
        clear_button = QPushButton("清空日志")
        clear_button.clicked.connect(self.clear_logs)
        bar.addWidget(clear_button)
        bar.addStretch(1)
        root.addLayout(bar)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        font = QFont("Menlo")
        font.setPointSize(11)
        self.log_view.setFont(font)
        root.addWidget(self.log_view, 1)

    def _action_button(self, text: str, command: str, icon_name: str) -> QPushButton:
        button = QPushButton(text)
        icon_id = getattr(QStyle, icon_name)
        button.setIcon(self.style().standardIcon(icon_id))
        button.setMinimumHeight(46)
        button.clicked.connect(lambda: self.start_operation(command))
        return button

    def _apply_style(self) -> None:
        QApplication.instance().setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f7f8fa;
                color: #20242a;
                font-size: 14px;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d9dde3;
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QPushButton {
                background: #1f6feb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2b7df5;
            }
            QPushButton:disabled {
                background: #a8b0bd;
            }
            QLineEdit, QComboBox, QSpinBox, QTextEdit, QTableWidget {
                background: #ffffff;
                border: 1px solid #d9dde3;
                border-radius: 6px;
                padding: 6px;
            }
            QTableWidget {
                gridline-color: #e5e8ee;
                selection-background-color: #dbeafe;
                selection-color: #111827;
            }
            QHeaderView::section {
                background: #eef1f5;
                border: none;
                border-right: 1px solid #d9dde3;
                padding: 8px;
                font-weight: 600;
            }
            QLabel#hint {
                color: #5b6472;
            }
            """
        )

    def pick_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择配置文件",
            str(Path.cwd()),
            "JSON 配置 (*.json);;所有文件 (*)",
        )
        if path:
            self.config_path = Path(path)
            self.load_config()

    def load_config(self) -> None:
        if not self.config_path.exists():
            try:
                seat_tool.init_config(self.config_path)
            except Exception as exc:
                QMessageBox.critical(self, "配置初始化失败", str(exc))
                return

        try:
            self.config = seat_tool.load_config(self.config_path)
        except Exception as exc:
            QMessageBox.critical(self, "配置读取失败", str(exc))
            return

        self.config_label.setText(str(self.config_path))
        defaults = self.config.get("defaults", {})
        self.default_seats_input.setText(self._join_ints(defaults.get("seats", [])))
        self.end_time_input.setText(str(defaults.get("end_time", "22:00:00")))
        self.rush_seconds_spin.setValue(int(defaults.get("rush_seconds", 5)))
        self.channel_spin.setValue(int(defaults.get("channel", 1001)))
        self.leave_channel_spin.setValue(int(defaults.get("leave_channel_type", 1003)))

        self.accounts_table.setRowCount(0)
        for account in self.config.get("accounts", []):
            self.add_account_row(account)

        self.refresh_dashboard()
        self.append_log(f"已加载配置：{self.config_path}")

    def save_config(self) -> bool:
        try:
            config = self.collect_config()
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.config = config
            self.refresh_dashboard()
            self.append_log(f"已保存配置：{self.config_path}")
            self.statusBar().showMessage("配置已保存", 3000)
            return True
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return False

    def collect_config(self) -> dict[str, Any]:
        accounts = []
        for row in range(self.accounts_table.rowCount()):
            enabled_item = self.accounts_table.item(row, 0)
            name_item = self.accounts_table.item(row, 1)
            username_item = self.accounts_table.item(row, 2)
            password_item = self.accounts_table.item(row, 3)
            seats_item = self.accounts_table.item(row, 4)
            accounts.append(
                {
                    "enabled": enabled_item.checkState() == Qt.Checked if enabled_item else True,
                    "name": self._item_text(name_item),
                    "username": self._item_text(username_item),
                    "password": self._item_text(password_item),
                    "seats": self._parse_seats(self._item_text(seats_item)),
                }
            )

        return {
            "defaults": {
                "seats": self._parse_seats(self.default_seats_input.text()),
                "end_time": self.end_time_input.text().strip() or "22:00:00",
                "rush_seconds": self.rush_seconds_spin.value(),
                "channel": self.channel_spin.value(),
                "leave_channel_type": self.leave_channel_spin.value(),
            },
            "accounts": accounts,
        }

    def refresh_dashboard(self) -> None:
        selected_account = self.account_combo.currentData()
        accounts = self.config.get("accounts", [])
        enabled = [account for account in accounts if account.get("enabled", True)]
        defaults = self.config.get("defaults", {})
        self.account_count_label.setText(str(len(accounts)))
        self.enabled_count_label.setText(str(len(enabled)))
        self.default_seats_label.setText(self._join_ints(defaults.get("seats", [])))

        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        self.account_combo.addItem("全部启用账号", "")
        for account in enabled:
            name = str(account.get("name") or account.get("username"))
            self.account_combo.addItem(name, name)
        if selected_account:
            selected_index = self.account_combo.findData(selected_account)
            if selected_index >= 0:
                self.account_combo.setCurrentIndex(selected_index)
        self.account_combo.blockSignals(False)

        self.account_overview.setRowCount(0)
        for account in accounts:
            row = self.account_overview.rowCount()
            self.account_overview.insertRow(row)
            enabled_text = "是" if account.get("enabled", True) else "否"
            values = [
                enabled_text,
                str(account.get("name", "")),
                str(account.get("username", "")),
                self._join_ints(account.get("seats", defaults.get("seats", []))),
                "待操作",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0 and value == "是":
                    item.setForeground(QColor("#137333"))
                if col == 0 and value == "否":
                    item.setForeground(QColor("#8a1c1c"))
                self.account_overview.setItem(row, col, item)

    def add_account_row(self, account: Optional[dict[str, Any]] = None) -> None:
        account = account or {
            "enabled": True,
            "name": f"account_{self.accounts_table.rowCount() + 1}",
            "username": "",
            "password": "",
            "seats": [],
        }
        row = self.accounts_table.rowCount()
        self.accounts_table.insertRow(row)

        enabled_item = QTableWidgetItem("")
        enabled_item.setFlags(enabled_item.flags() | Qt.ItemIsUserCheckable)
        enabled_item.setCheckState(Qt.Checked if account.get("enabled", True) else Qt.Unchecked)
        self.accounts_table.setItem(row, 0, enabled_item)

        values = [
            str(account.get("name", "")),
            str(account.get("username", "")),
            str(account.get("password", "")),
            self._join_ints(account.get("seats", [])),
        ]
        for index, value in enumerate(values, start=1):
            self.accounts_table.setItem(row, index, QTableWidgetItem(value))

    def remove_selected_account(self) -> None:
        rows = sorted({item.row() for item in self.accounts_table.selectedItems()}, reverse=True)
        for row in rows:
            self.accounts_table.removeRow(row)
        if rows:
            self.statusBar().showMessage("已删除选中账号，记得保存配置", 3000)

    def start_operation(self, command: str) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, "正在运行", "当前已有任务在运行，请等待结束。")
            return

        account_name = self.account_combo.currentData() or None
        if not self.save_config():
            return
        booking_send_mode = self.booking_mode_combo.currentData() or "direct"
        booking_send_time = self.booking_time_input.text().strip()
        if command == "book" and booking_send_mode == "time":
            try:
                seat_tool.parse_clock_time(booking_send_time)
            except ValueError as exc:
                QMessageBox.warning(self, "时间格式错误", str(exc))
                return

        self.set_running(True)
        self.tabs.setCurrentWidget(self.log_tab)
        if command == "book" and booking_send_mode == "time":
            self.statusBar().showMessage("等待到达预约时间")
            self.append_log("等待到达预约时间")
            self.append_log(f"开始执行：{command}，将在 {booking_send_time} 发送预约指令")
        else:
            self.append_log(f"开始执行：{command}")

        self.thread = QThread()
        self.worker = SeatWorker(
            command=command,
            config_path=self.config_path,
            account_name=account_name,
            interval=float(self.interval_spin.value()),
            booking_send_mode=booking_send_mode,
            booking_send_time=booking_send_time,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.append_log)
        self.worker.done.connect(self.finish_operation)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.cleanup_worker)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def start_seat_crawl(self) -> None:
        if self.crawl_thread and self.crawl_thread.isRunning():
            QMessageBox.information(self, "正在运行", "当前已有座位爬取任务在运行。")
            return

        account_name = self.account_combo.currentData() or None
        if not self.save_config():
            return

        self.tabs.setCurrentWidget(self.log_tab)
        self.append_log("开始爬取座位列表")
        self.crawl_thread = QThread()
        self.crawl_worker = SeatCrawlWorker(self.config_path, account_name)
        self.crawl_worker.moveToThread(self.crawl_thread)
        self.crawl_thread.started.connect(self.crawl_worker.run)
        self.crawl_worker.log.connect(self.append_log)
        self.crawl_worker.done.connect(self.finish_seat_crawl)
        self.crawl_worker.done.connect(self.crawl_thread.quit)
        self.crawl_worker.done.connect(self.crawl_worker.deleteLater)
        self.crawl_thread.finished.connect(self.cleanup_crawl_worker)
        self.crawl_thread.finished.connect(self.crawl_thread.deleteLater)
        self.crawl_thread.start()

    def finish_seat_crawl(self, success: bool, message: str, payload: object) -> None:
        self.append_log(message)
        self.statusBar().showMessage(message, 5000)
        if not success:
            QMessageBox.warning(self, "爬取失败", message)
            return

        data = payload if isinstance(payload, dict) else {}
        regions = data.get("regions", [])
        self.seats_by_region = data.get("seats_by_region", {})
        total_seat_count = int(data.get("total_seat_count", 0) or 0)
        available_seat_count = int(data.get("available_seat_count", 0) or 0)
        occupied_seat_count = int(data.get("occupied_seat_count", 0) or 0)
        self.region_combo.blockSignals(True)
        self.region_combo.clear()
        for region in regions:
            self.region_combo.addItem(region.name, region)
        self.region_combo.blockSignals(False)
        self.refresh_seat_combo()
        self.update_library_people(occupied_seat_count, total_seat_count, available_seat_count)
        self.tabs.setCurrentWidget(self.config_tab)

    def cleanup_crawl_worker(self) -> None:
        self.crawl_thread = None
        self.crawl_worker = None

    def refresh_seat_combo(self, _index: int = -1) -> None:
        self.seat_combo.clear()
        region = self.region_combo.currentData()
        if not region:
            return

        for seat in self.seats_by_region.get(region.region_id, []):
            status_text = "可预约" if seat.is_can else "不可预约"
            self.seat_combo.addItem(f"{seat.name} | {seat.seat_id} | {status_text}", seat)

    def update_library_people(self, occupied_seat_count: int, total_seat_count: int, available_seat_count: int) -> None:
        if total_seat_count <= 0:
            self.library_people_label.setText("约 -- 人")
            return

        self.library_people_label.setText(f"约 {occupied_seat_count} 人")
        self.append_log(
            f"估算人数：总座位 {total_seat_count} - 可预约 {available_seat_count} = 约 {occupied_seat_count} 人"
        )

    def add_selected_seat_to_account(self) -> None:
        seat = self.seat_combo.currentData()
        if not seat:
            QMessageBox.information(self, "未选择座位", "请先刷新并选择座位。")
            return
        if not seat.is_can:
            QMessageBox.warning(self, "座位不可预约", "该座位当前不可预约，请选择标记为可预约的座位。")
            return

        selected_rows = sorted({item.row() for item in self.accounts_table.selectedItems()})
        if not selected_rows:
            QMessageBox.information(self, "未选择账号", "请先在账号表格中选中一个账号行。")
            return

        row = selected_rows[0]
        seats_item = self.accounts_table.item(row, 4)
        current_seats = self._parse_seats(self._item_text(seats_item))
        if seat.seat_id not in current_seats:
            current_seats.append(seat.seat_id)
        self.accounts_table.setItem(row, 4, QTableWidgetItem(self._join_ints(current_seats)))
        self.statusBar().showMessage(f"已添加座位 {seat.seat_id}", 3000)

    def finish_operation(self, success: bool, message: str) -> None:
        self.set_running(False)
        self.append_log(message)
        self.statusBar().showMessage(message, 5000)
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "需要检查", message)

    def cleanup_worker(self) -> None:
        self.thread = None
        self.worker = None

    def closeEvent(self, event: Any) -> None:
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "任务运行中", "当前还有任务在运行，请等待结束后再关闭窗口。")
            event.ignore()
            return
        if self.crawl_thread and self.crawl_thread.isRunning():
            QMessageBox.warning(self, "任务运行中", "当前还有座位爬取任务在运行，请等待结束后再关闭窗口。")
            event.ignore()
            return

        event.accept()

    def set_running(self, running: bool) -> None:
        for widget in (
            self.book_button,
            self.status_button,
            self.short_button,
            self.long_button,
            self.signoff_button,
            self.accounts_table,
        ):
            widget.setEnabled(not running)

    def append_log(self, text: str) -> None:
        self.log_view.append(text)
        self.log_view.moveCursor(QTextCursor.End)

    def clear_logs(self) -> None:
        self.log_view.clear()
        self.statusBar().showMessage("运行日志已清空", 3000)

    def _item_text(self, item: Optional[QTableWidgetItem]) -> str:
        return item.text().strip() if item else ""

    def _parse_seats(self, text: str) -> list[int]:
        text = text.strip()
        if not text:
            return []
        seats = []
        for part in text.replace("，", ",").split(","):
            part = part.strip()
            if part:
                seats.append(int(part))
        return seats

    def _join_ints(self, values: Any) -> str:
        return ",".join(str(value) for value in values)


def main() -> int:
    app = QApplication(sys.argv)

    def show_uncaught_exception(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        print(details, file=sys.stderr)
        QMessageBox.critical(None, "程序异常", f"{exc}\n\n详细信息已输出到终端。")

    sys.excepthook = show_uncaught_exception

    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
