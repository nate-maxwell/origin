"""Origin UI - Package browser and publish tool."""

import sys

from PySide6 import QtCore
from PySide6 import QtWidgets

from gui import style
from gui.browser import PackageBrowserPanel
from gui.publisher import PublishPanel


class OriginWindow(QtWidgets.QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Origin")
        self.setMinimumSize(QtCore.QSize(960, 640))
        self.resize(QtCore.QSize(1200, 720))
        self._build_ui()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = QtWidgets.QWidget()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        title = QtWidgets.QLabel("ORIGIN")
        title.setObjectName("app_title")
        subtitle = QtWidgets.QLabel("PIPELINE")
        subtitle.setObjectName("app_subtitle")
        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(subtitle)

        self._nav_buttons: list[QtWidgets.QPushButton] = []
        self._stack = QtWidgets.QStackedWidget()

        panels = [
            ("⬡  Packages", PackageBrowserPanel()),
            ("↑  Publish", PublishPanel()),
        ]

        for i, (label, panel) in enumerate(panels):
            btn = QtWidgets.QPushButton(label)
            btn.setObjectName("nav_btn")
            btn.setCheckable(False)
            btn.clicked.connect(lambda checked, idx=i: self._switch_panel(idx))
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)
            self._stack.addWidget(panel)

        sidebar_layout.addStretch()
        root.addWidget(sidebar)

        root.addWidget(self._stack, stretch=1)

        status = QtWidgets.QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Ready")

        self._switch_panel(0)

    def _switch_panel(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
