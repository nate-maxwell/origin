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
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QtWidgets.QLabel("Publish Package")
        header.setObjectName("panel_header")
        layout.addWidget(header)

        desc = QtWidgets.QLabel(
            "Copy a package from source to a repository and tag the git commit."
        )
        desc.setObjectName("panel_desc")
        layout.addWidget(desc)

        layout.addWidget(components.make_divider())

        # Source dir
        layout.addWidget(components.make_section("Source"))
        source_row, self._source_field = components.path_row(
            "Package Source Directory",
            "/path/to/my_package",
            self._browse_source,
        )
        layout.addWidget(source_row)

        # Repository
        layout.addWidget(components.make_section("Destination"))
        repo_row, self._repo_field = components.path_row(
            "Repository",
            "/path/to/repository",
            self._browse_repo,
        )
        layout.addWidget(repo_row)

        # Package info preview
        layout.addWidget(components.make_section("Package Info"))

        info_container = QtWidgets.QWidget()
        info_layout = QtWidgets.QHBoxLayout(info_container)
        info_layout.setContentsMargins(28, 0, 28, 0)
        info_layout.setSpacing(24)

        self._pkg_name_label = self._make_info_field("Name", "—")
        self._pkg_version_label = self._make_info_field("Version", "—")
        self._pkg_dest_label = self._make_info_field("Destination", "—")
        info_layout.addWidget(self._pkg_name_label[0])
        info_layout.addWidget(self._pkg_version_label[0])
        info_layout.addWidget(self._pkg_dest_label[0], stretch=1)
        layout.addWidget(info_container)

        self._source_field.textChanged.connect(self._on_source_changed)
        self._repo_field.textChanged.connect(self._on_source_changed)

        layout.addWidget(components.make_divider())
        layout.addSpacing(16)

        # Publish button + status
        action_container = QtWidgets.QWidget()
        action_layout = QtWidgets.QHBoxLayout(action_container)
        action_layout.setContentsMargins(28, 0, 28, 0)
        action_layout.setSpacing(12)

        self._publish_btn = QtWidgets.QPushButton("Publish Package")
        self._publish_btn.setObjectName("btn_success")
        self._publish_btn.setFixedHeight(38)
        self._publish_btn.setEnabled(False)
        self._publish_btn.clicked.connect(self._publish)
        action_layout.addWidget(self._publish_btn)
        action_layout.addStretch()
        layout.addWidget(action_container)

        self._status_label = QtWidgets.QLabel("")
        self._status_label.setContentsMargins(28, 8, 28, 0)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        layout.addStretch()

    def _make_info_field(
        self, label_text: str, value: str
    ) -> tuple[QtWidgets.QWidget, QtWidgets.QLabel]:
        container = QtWidgets.QWidget()
        vl = QtWidgets.QVBoxLayout(container)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)
        lbl = components.make_label(label_text)
        val = QtWidgets.QLabel(value)
        val.setObjectName("value_label")
        val.setStyleSheet(
            f"font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px;"
            f"color: {style.COLORS['text_primary']}; background: transparent; border: none;"
            f"text-transform: none; letter-spacing: 0px; font-weight: 400;"
        )
        vl.addWidget(lbl)
        vl.addWidget(val)
        return container, val

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
