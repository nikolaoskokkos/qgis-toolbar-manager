import os

from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .manager import ToolbarManager

MENU = "&Toolbar Manager"


class ToolbarManagerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.manager = ToolbarManager(iface)
        self.action = None

    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
        self.action = QAction(icon, "Toolbar Manager…", self.iface.mainWindow())
        self.action.setObjectName("mActionToolbarManager")
        self.action.setToolTip("Choose which toolbars and tools are shown")
        self.action.triggered.connect(self.show_dialog)
        self.iface.addPluginToMenu(MENU, self.action)
        self.iface.addToolBarIcon(self.action)
        # Also expose it under View > Toolbars for discoverability.
        try:
            self.iface.viewMenu().addAction(self.action)
        except AttributeError:
            pass

        # Apply the saved profile once all other plugins have built their toolbars.
        self.iface.initializationCompleted.connect(self.apply_saved)
        QTimer.singleShot(0, self.apply_saved)  # when enabled in a running QGIS

    def unload(self):
        try:
            self.iface.initializationCompleted.disconnect(self.apply_saved)
        except TypeError:
            pass
        self.manager.restore_all()
        self.iface.removePluginMenu(MENU, self.action)
        self.iface.removeToolBarIcon(self.action)
        try:
            self.iface.viewMenu().removeAction(self.action)
        except AttributeError:
            pass
        self.action.deleteLater()
        self.action = None

    def apply_saved(self):
        state = self.manager.load(self.manager.current_profile())
        self.manager.apply(state)

    def show_dialog(self):
        from .dialog import ToolbarManagerDialog
        dlg = ToolbarManagerDialog(self.manager, self.iface.mainWindow())
        dlg.exec()
