from pathlib import Path
from typing import Optional

from PySide6 import QtCore
from PySide6 import QtWidgets
from origin.environment import PackageConfig
from origin.publish import publish_package

from gui import components
from gui import style
from gui import worker


class PublishPanel(QtWidgets.QWidget):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._thread_pool = QtCore.QThreadPool()
        self._create_widgets()
        self._create_layouts()
        self._create_connections()

    def _create_widgets(self) -> None:
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.header = QtWidgets.QLabel("Publish Package")
        self.header.setObjectName("panel_header")

        _t = "Copy a package from source to a repository and tag the git commit."
        self.desc = QtWidgets.QLabel(_t)
        self.desc.setObjectName("panel_desc")

        self.source_row, self._source_field = components.path_row(
            "Package Source Directory",
            "/path/to/my_package",
            self._browse_source,
        )

        self.repo_row, self._repo_field = components.path_row(
            "Repository",
            "/path/to/repository",
            self._browse_repo,
        )

        self.info_container = QtWidgets.QWidget()
        self.info_layout = QtWidgets.QHBoxLayout(self.info_container)
        self.info_layout.setContentsMargins(28, 0, 28, 0)
        self.info_layout.setSpacing(24)

        self._pkg_name_label = components.make_info_field("Name", "—")
        self._pkg_version_label = components.make_info_field("Version", "—")
        self._pkg_dest_label = components.make_info_field("Destination", "—")

        self.action_container = QtWidgets.QWidget()
        self.action_layout = QtWidgets.QHBoxLayout(self.action_container)
        self.action_layout.setContentsMargins(28, 0, 28, 0)
        self.action_layout.setSpacing(12)

        self._publish_btn = QtWidgets.QPushButton("Publish Package")
        self._publish_btn.setObjectName("btn_success")
        self._publish_btn.setFixedHeight(38)
        self._publish_btn.setEnabled(False)
        self._publish_btn.clicked.connect(self._publish)

        self._status_label = QtWidgets.QLabel("")
        self._status_label.setContentsMargins(28, 8, 28, 0)
        self._status_label.setWordWrap(True)

    def _create_layouts(self) -> None:
        self.layout.addWidget(self.desc)
        self.layout.addWidget(components.make_divider())

        self.layout.addWidget(self.source_row)
        self.layout.addWidget(self.repo_row)

        # Package info preview
        self.layout.addWidget(components.make_section("Package Info"))
        self.info_layout.addWidget(self._pkg_name_label[0])
        self.info_layout.addWidget(self._pkg_version_label[0])
        self.info_layout.addWidget(self._pkg_dest_label[0], stretch=1)
        self.layout.addWidget(self.info_container)

        self.layout.addWidget(components.make_divider())
        self.layout.addSpacing(16)

        self.action_layout.addWidget(self._publish_btn)
        self.action_layout.addStretch()
        self.layout.addWidget(self.action_container)

        self.layout.addWidget(self._status_label)

        self.layout.addStretch()

    def _create_connections(self) -> None:
        self._source_field.textChanged.connect(self._on_source_changed)
        self._repo_field.textChanged.connect(self._on_source_changed)

    def _browse_source(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Package Source Directory"
        )
        if path:
            self._source_field.setText(path)

    def _browse_repo(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Repository")
        if path:
            self._repo_field.setText(path)

    def _on_source_changed(self) -> None:
        source = Path(self._source_field.text())
        repo = Path(self._repo_field.text())
        self._publish_btn.setEnabled(False)
        self._status_label.setText("")

        name_val = self._pkg_name_label[1]
        ver_val = self._pkg_version_label[1]
        dest_val = self._pkg_dest_label[1]

        if not source.exists():
            name_val.setText("—")
            ver_val.setText("—")
            dest_val.setText("—")
            return

        pkg_yaml = source / "package.yaml"
        if not pkg_yaml.exists():
            name_val.setText("No package.yaml found")
            name_val.setStyleSheet(f"color: {style.COLORS['error']}; font-size: 12px;")
            ver_val.setText("—")
            dest_val.setText("—")
            return

        try:
            cfg = PackageConfig.from_file(pkg_yaml)
            name_val.setText(cfg.name)
            name_val.setStyleSheet(
                f"font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px;"
                f"color: {style.COLORS['text_primary']}; background: transparent; border: none;"
            )
            ver_val.setText(cfg.version)
            if repo.exists():
                dest = repo / cfg.name / cfg.version
                dest_val.setText(dest.as_posix())
                self._publish_btn.setEnabled(True)
            else:
                dest_val.setText("—")
        except Exception as e:
            name_val.setText(str(e))
            name_val.setStyleSheet(f"color: {style.COLORS['error']}; font-size: 12px;")

    def _publish(self) -> None:
        source = self._source_field.text()
        repo = self._repo_field.text()

        self._publish_btn.setEnabled(False)
        self._publish_btn.setText("Publishing…")
        self._set_status("", style.COLORS["text_secondary"])

        def _do_publish() -> None:
            publish_package(repository=repo, source_dir=source)

        worker_ = worker.Worker(_do_publish)
        worker_.signals.finished.connect(self._on_publish_success)
        worker_.signals.error.connect(self._on_publish_error)
        self._thread_pool.start(worker_)

    @QtCore.Slot()
    def _on_publish_success(self) -> None:
        self._publish_btn.setText("Publish Package")
        self._publish_btn.setEnabled(True)
        self._set_status("✓  Package published successfully.", style.COLORS["success"])

    @QtCore.Slot(str)
    def _on_publish_error(self, error: str) -> None:
        self._publish_btn.setText("Publish Package")
        self._publish_btn.setEnabled(True)
        self._set_status(f"✗  {error}", style.COLORS["error"])

    def _set_status(self, text: str, color: str) -> None:
        self._status_label.setText(text)
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: 12px; padding: 0px 28px;"
        )
