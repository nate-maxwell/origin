from PySide6 import QtCore


class WorkerSignals(QtCore.QObject):
    finished = QtCore.Signal()
    error = QtCore.Signal(str)


class Worker(QtCore.QRunnable):
    """Generic background task runner."""

    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @QtCore.Slot()
    def run(self) -> None:
        try:
            self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))
