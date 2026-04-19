from PySide6 import QtWidgets

from gui import style


def make_label(text: str) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text)
    return lbl


def make_section(text: str) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text)
    lbl.setObjectName("section_label")
    return lbl


def make_divider() -> QtWidgets.QFrame:
    f = QtWidgets.QFrame()
    f.setObjectName("divider")
    f.setFrameShape(QtWidgets.QFrame.Shape.HLine)
    return f


def path_row(
    label_text: str, placeholder: str, browse_fn
) -> tuple[QtWidgets.QWidget, QtWidgets.QLineEdit]:
    """A label + path field + browse button row."""
    container = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(container)
    layout.setContentsMargins(28, 0, 28, 0)
    layout.setSpacing(6)

    lbl = make_label(label_text)
    layout.addWidget(lbl)

    row = QtWidgets.QHBoxLayout()
    row.setSpacing(8)
    field = QtWidgets.QLineEdit()
    field.setPlaceholderText(placeholder)
    field.setObjectName("mono")
    field.setStyleSheet(
        f"background-color: {style.COLORS['bg_raised']}; border: 1px solid {style.COLORS['border']};"
        f"border-radius: 6px; padding: 8px 12px;"
        f"font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px;"
        f"color: {style.COLORS['text_primary']};"
    )
    btn = QtWidgets.QPushButton("Browse")
    btn.setObjectName("btn_browse")
    btn.setFixedHeight(36)
    btn.clicked.connect(browse_fn)
    row.addWidget(field)
    row.addWidget(btn)
    layout.addLayout(row)
    return container, field
