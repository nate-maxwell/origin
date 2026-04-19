from pathlib import Path
from typing import Optional

from PySide6 import QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets
from origin import Package
from origin import ResolvedEnvironment
from origin import EnvironmentConfig
from origin import EnvironmentResolver

from gui import components
from gui import style


class PackageBrowserPanel(QtWidgets.QWidget):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._resolved: Optional[ResolvedEnvironment] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QtWidgets.QLabel("Package Browser")
        header.setObjectName("panel_header")
        layout.addWidget(header)

        desc = QtWidgets.QLabel(
            "Resolve an environment config to inspect packages and environment variables."
        )
        desc.setObjectName("panel_desc")
        layout.addWidget(desc)

        layout.addWidget(components.make_divider())

        # Config path
        layout.addWidget(components.make_section("Environment Config"))
        config_row, self._config_field = components.path_row(
            "Config Path",
            "/path/to/environment.yaml",
            self._browse_config,
        )
        layout.addWidget(config_row)

        # Loadout selector
        loadout_container = QtWidgets.QWidget()
        loadout_layout = QtWidgets.QVBoxLayout(loadout_container)
        loadout_layout.setContentsMargins(28, 0, 28, 0)
        loadout_layout.setSpacing(6)
        loadout_layout.addWidget(components.make_label("Loadout"))
        loadout_row = QtWidgets.QHBoxLayout()
        loadout_row.setSpacing(8)
        self._loadout_combo = QtWidgets.QComboBox()
        self._loadout_combo.setPlaceholderText("Select a loadout...")
        self._loadout_combo.setEnabled(False)
        self._resolve_btn = QtWidgets.QPushButton("Resolve")
        self._resolve_btn.setObjectName("btn_primary")
        self._resolve_btn.setFixedHeight(36)
        self._resolve_btn.setEnabled(False)
        self._resolve_btn.clicked.connect(self._resolve)
        loadout_row.addWidget(self._loadout_combo)
        loadout_row.addWidget(self._resolve_btn)
        loadout_layout.addLayout(loadout_row)
        layout.addWidget(loadout_container)

        self._config_field.textChanged.connect(self._on_config_changed)

        # Results splitter
        layout.addWidget(components.make_section("Resolved Packages"))

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setContentsMargins(28, 0, 28, 16)
        splitter.setHandleWidth(1)

        # Package list (left)
        self._pkg_tree = QtWidgets.QTreeWidget()
        self._pkg_tree.setHeaderLabels(["Package", "Version", "Root"])
        self._pkg_tree.setAlternatingRowColors(True)
        self._pkg_tree.setRootIsDecorated(False)
        self._pkg_tree.header().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self._pkg_tree.header().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self._pkg_tree.header().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self._pkg_tree.itemSelectionChanged.connect(self._on_package_selected)
        splitter.addWidget(self._pkg_tree)

        # Env vars (right)
        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self._env_label = QtWidgets.QLabel("ENV VARS")
        self._env_label.setObjectName("section_label")
        self._env_label.setContentsMargins(0, 0, 0, 6)
        right_layout.addWidget(self._env_label)
        self._env_table = QtWidgets.QTableWidget()
        self._env_table.setColumnCount(2)
        self._env_table.setHorizontalHeaderLabels(["Variable", "Value"])
        self._env_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self._env_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self._env_table.verticalHeader().setVisible(False)
        self._env_table.setAlternatingRowColors(True)
        self._env_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._env_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        right_layout.addWidget(self._env_table)
        splitter.addWidget(right)

        splitter.setSizes([340, 460])
        layout.addWidget(splitter, stretch=1)

    def _browse_config(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Environment Config", "", "YAML Files (*.yaml *.yml)"
        )
        if path:
            self._config_field.setText(path)

    def _on_config_changed(self, text: str) -> None:
        self._loadout_combo.clear()
        self._loadout_combo.setEnabled(False)
        self._resolve_btn.setEnabled(False)
        self._pkg_tree.clear()
        self._env_table.setRowCount(0)

        path = Path(text)
        if not path.exists():
            return
        try:
            cfg = EnvironmentConfig.from_file(path)
            for name in cfg.loadouts:
                self._loadout_combo.addItem(name)
            self._loadout_combo.setEnabled(True)
            self._resolve_btn.setEnabled(True)
        except Exception:
            pass

    def _resolve(self) -> None:
        config_path = Path(self._config_field.text())
        loadout = self._loadout_combo.currentText()
        if not loadout:
            return

        self._resolve_btn.setEnabled(False)
        self._resolve_btn.setText("Resolving…")
        self._pkg_tree.clear()
        self._env_table.setRowCount(0)

        try:
            cfg = EnvironmentConfig.from_file(config_path)
            resolver = EnvironmentResolver(cfg)
            self._resolved = resolver.resolve([loadout], base_env={})
            self._populate_results(self._resolved)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Resolve Error", str(e))
        finally:
            self._resolve_btn.setEnabled(True)
            self._resolve_btn.setText("Resolve")

    def _populate_results(self, resolved: ResolvedEnvironment) -> None:
        self._pkg_tree.clear()
        for pkg in resolved.packages:
            item = QtWidgets.QTreeWidgetItem(
                [
                    pkg.name,
                    pkg.version,
                    pkg.root.as_posix(),
                ]
            )
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, pkg)
            self._pkg_tree.addTopLevelItem(item)

        self._populate_env_table(resolved.env)

    def _on_package_selected(self) -> None:
        items = self._pkg_tree.selectedItems()
        if not items:
            if self._resolved:
                self._populate_env_table(self._resolved.env)
            return
        pkg: Package = items[0].data(0, QtCore.Qt.ItemDataRole.UserRole)
        if pkg:
            self._populate_env_table(pkg.env, highlight=True)

    def _populate_env_table(self, env: dict, highlight: bool = False) -> None:
        mono_font = QtGui.QFont("Cascadia Code, Consolas, Courier New")
        mono_font.setPointSize(11)

        self._env_table.setRowCount(0)

        def _is_version_component(key: str) -> bool:
            return any(
                key.endswith(s)
                for s in ("_MAJOR_VERSION", "_MINOR_VERSION", "_PATCH_VERSION")
            )

        origin_vars = {
            k: v
            for k, v in env.items()
            if k.startswith("ORIGIN_") and not _is_version_component(k)
        }
        other_vars = {k: v for k, v in env.items() if not k.startswith("ORIGIN_")}

        rows = list(origin_vars.items()) + list(other_vars.items())
        self._env_table.setRowCount(len(rows))

        for i, (key, value) in enumerate(rows):
            k_item = QtWidgets.QTableWidgetItem(key)
            k_item.setFont(mono_font)
            v_item = QtWidgets.QTableWidgetItem(str(value))
            v_item.setFont(mono_font)

            if key.startswith("ORIGIN_"):
                k_item.setForeground(QtGui.QColor(style.COLORS["accent"]))

            self._env_table.setItem(i, 0, k_item)
            self._env_table.setItem(i, 1, v_item)

        self._env_table.resizeRowsToContents()
