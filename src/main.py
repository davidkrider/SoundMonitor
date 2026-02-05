import argparse
import os
import sys

from PyQt5 import QtCore, QtWidgets

from .audio import AudioProcessor, load_config
from .ui_widgets import DbDisplayWidget, RangeBarWidget, SpectrumWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.setWindowTitle("Decibel Meter")

        self.audio = AudioProcessor(config)

        self.db_widget = DbDisplayWidget()
        self.range_widget = RangeBarWidget(
            low_db=config.get("range_low_db", 70.0),
            high_db=config.get("range_high_db", 85.0),
        )
        self.spectrum_widget = SpectrumWidget()

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.db_widget)
        self.stack.addWidget(self.range_widget)
        self.stack.addWidget(self.spectrum_widget)

        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.setMinimumHeight(40)
        self.close_button.setStyleSheet("font-size: 18px;")
        self.close_button.clicked.connect(self.close)

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addStretch(1)
        top_layout.addWidget(self.close_button)

        button_layout = QtWidgets.QHBoxLayout()
        self.db_button = self._make_button("dBA")
        self.range_button = self._make_button("Range")
        self.spectrum_button = self._make_button("Spectrum")
        button_layout.addWidget(self.db_button)
        button_layout.addWidget(self.range_button)
        button_layout.addWidget(self.spectrum_button)

        self.db_button.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.range_button.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.spectrum_button.clicked.connect(lambda: self.stack.setCurrentIndex(2))

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.addLayout(top_layout)
        layout.addWidget(self.stack, 1)
        layout.addLayout(button_layout)
        self.setCentralWidget(central)

        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self._refresh_meter)
        self.update_timer.start(500)

        self.spectrum_timer = QtCore.QTimer(self)
        self.spectrum_timer.timeout.connect(self._refresh_spectrum)
        self.spectrum_timer.start(250)

        self.audio.start()

    def _make_button(self, label):
        button = QtWidgets.QPushButton(label)
        button.setMinimumHeight(60)
        button.setStyleSheet("font-size: 20px;")
        return button

    def _refresh_meter(self):
        value = self.audio.get_last_db()
        self.db_widget.set_value(value)
        self.range_widget.set_value(value)

    def _refresh_spectrum(self):
        self.audio.compute_spectrum()
        self.spectrum_widget.set_levels(self.audio.get_spectrum())

    def closeEvent(self, event):
        self.audio.stop()
        event.accept()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None, help="Path to config.json")
    parser.add_argument("--windowed", action="store_true", help="Disable full-screen")
    return parser.parse_args()


def main():
    args = parse_args()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_config = os.path.join(base_dir, "..", "config.json")
    config_path = args.config or default_config
    config = load_config(os.path.abspath(config_path))

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(config)
    if args.windowed:
        window.resize(900, 600)
        window.show()
    else:
        window.showFullScreen()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
