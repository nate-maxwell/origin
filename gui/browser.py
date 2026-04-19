from pathlib import Path
from typing import Optional

from PySide6 import QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets
from origin import Package
from origin import ResolvedEnvironment
from origin import EnvironmentConfig
from origin import EnvironmentResolver
from origin import EnvironmentConfigError

from gui import components
from gui import style


class PackageBrowserPanel(QtWidgets.QWidget):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._resolved: Optional[ResolvedEnvironment] = None
        self._create_widgets()
        self._create_layouts()
        self._create_connections()

    def _create_widgets(self) -> None:
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.header = QtWidgets.QLabel("Package Browser")
        self.header.setObjectName("panel_header")

        _t = "Resolve an environment config to inspect packages and environment variables."
        self.desc = QtWidgets.QLabel(_t)
        self.desc.setObjectName("panel_desc")

        # Config path
        self.layout.addWidget(components.make_section("Environment Config"))
        self.config_row, self._config_field = components.path_row(
            "Config Path",
            "/path/to/environment.yaml",
            self._browse_config,
        )

        # Loadout selector
        self.loadout_container = QtWidgets.QWidget()
        self.loadout_layout = QtWidgets.QVBoxLayout(self.loadout_container)
        self.loadout_layout.setContentsMargins(28, 0, 28, 0)
        self.loadout_layout.setSpacing(6)

        self.loadout_row = QtWidgets.QHBoxLayout()
        self.loadout_row.setSpacing(8)

        self._loadout_combo = QtWidgets.QComboBox()
        self._loadout_combo.setPlaceholderText("Select a loadout...")
        self._loadout_combo.setEnabled(False)
        self._resolve_btn = QtWidgets.QPushButton("Resolve")
        self._resolve_btn.setObjectName("btn_primary")
        self._resolve_btn.setFixedHeight(36)
        self._resolve_btn.setEnabled(False)

        # Results splitter
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setContentsMargins(28, 0, 28, 16)
        self.splitter.setHandleWidth(1)

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

        # Env vars (right)
        self.right = QtWidgets.QWidget()
        self.right_layout = QtWidgets.QVBoxLayout(self.right)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)

        self._env_label = QtWidgets.QLabel("ENV VARS")
        self._env_label.setObjectName("section_label")
        self._env_label.setContentsMargins(0, 0, 0, 6)

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

    def _create_layouts(self) -> None:
        self.layout.addWidget(self.header)
        self.layout.addWidget(self.desc)
        self.layout.addWidget(components.make_divider())

        self.layout.addWidget(self.config_row)

        self.loadout_layout.addWidget(components.make_label("Loadout"))
        self.loadout_row.addWidget(self._loadout_combo)
        self.loadout_row.addWidget(self._resolve_btn)
        self.loadout_layout.addLayout(self.loadout_row)
        self.layout.addWidget(self.loadout_container)

        self.layout.addWidget(components.make_section("Resolved Packages"))
        self.splitter.addWidget(self._pkg_tree)
        self.right_layout.addWidget(self._env_label)
        self.right_layout.addWidget(self._env_table)
        self.splitter.addWidget(self.right)
        self.splitter.setSizes([340, 460])
        self.layout.addWidget(self.splitter, stretch=1)

    def _create_connections(self) -> None:
        self._resolve_btn.clicked.connect(self._resolve)
        self._config_field.textChanged.connect(self._on_config_changed)
        self._pkg_tree.itemSelectionChanged.connect(self._on_package_selected)

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
        except EnvironmentConfigError:
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
            self._populate_env_table(pkg.env)

    def _populate_env_table(self, env: dict) -> None:
        mono_font = QtGui.QFont("Cascadia Code, Consolas, Courier New")
        mono_font.setPointSize(11)

        self._env_table.setRowCount(0)

        def _is_version_component(key_: str) -> bool:
            return any(
                key_.endswith(s)
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
