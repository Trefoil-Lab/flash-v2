import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
)
from MainWindow import Ui_MainWindow
import DC.gui
import AC.gui

MAIN_WINDOW_TITLE = 'flash-v1'


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        ###############################
        # custom initialization below #
        ###############################

        self.setWindowTitle(MAIN_WINDOW_TITLE)

        # connect buttons to handlers
        self.DCpushButton.pressed.connect(self.DC_press)
        self.ACpushButton.pressed.connect(self.AC_press)

    def DC_press(self):
        new_window = DC.gui.MainWindow()
        new_window.show()
        self.close()

    def AC_press(self):
        new_window = AC.gui.MainWindow()
        new_window.show()
        self.close()

if __name__ == "__main__":
    main()
