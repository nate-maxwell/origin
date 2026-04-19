import sys

from PySide6 import QtWidgets

from gui import environment_gui
from gui import style


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(style.STYLESHEET_PATH.read_text())

    window = environment_gui.OriginWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
