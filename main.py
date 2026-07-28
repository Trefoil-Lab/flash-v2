import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
)
from gui.ui.LauncherMainWindow import Ui_MainWindow
import gui.dc
import gui.ac
import gui.mm

MAIN_WINDOW_TITLE = 'flash-v2'

def main():
    """
    Main entry point.
    """
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()

class MainWindow(QMainWindow, Ui_MainWindow):
    """
    GUI for main launcher window.
    """
    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        ###############################
        # custom initialization below #
        ###############################

        self.setWindowTitle(MAIN_WINDOW_TITLE)
        self.windows = []

        # connect buttons to handlers
        self.DCpushButton.pressed.connect(self.DC_press)
        self.ACpushButton.pressed.connect(self.AC_press)
        self.MultimeterPushButton.pressed.connect(self.MM_press)

    def DC_press(self):
        """
        Handle DC button press: open DC flash GUI in new window
        """
        new_window = gui.dc.MainWindow()
        new_window.show()
        self.windows.append(new_window)
        # self.close()

    def AC_press(self):
        """
        Handle AC button press: open AC flash GUI in new window
        """
        new_window = gui.ac.MainWindow()
        new_window.show()
        self.windows.append(new_window)
        # self.close()

    def MM_press(self):
        """
        Handle multimeter button press: open multimeter GUI in new window
        """
        new_window = gui.mm.MainWindow()
        new_window.show()
        self.windows.append(new_window)
        # self.close()

if __name__ == "__main__":
    main()
