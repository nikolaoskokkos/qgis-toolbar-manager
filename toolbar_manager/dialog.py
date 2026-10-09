import os
import re

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout,
)
from qgis.core import QgsSettings

from .manager import (
    DEFAULT_PROFILE, SETTINGS_ROOT, ToolbarState, clean_text, is_core_toolbar, toolbar_key,
)

ROLE_KIND = Qt.ItemDataRole.UserRole
ROLE_KEY = Qt.ItemDataRole.UserRole + 1
KIND_TOOLBAR, KIND_TOOL = "toolbar", "tool"
CHECKED, UNCHECKED = Qt.CheckState.Checked, Qt.CheckState.Unchecked
TAB_TITLES = ("QGIS toolbars", "Plugin toolbars")
MB = QMessageBox.StandardButton


def safe_profile_name(name):
    return re.sub(r"[\\/]", "_", name or "").strip()


class ToolbarManagerDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        # State the trees were filled from; keeps entries for toolbars that are
        # not loaded right now (e.g. a disabled plugin) so saving doesn't drop them.
        self._base_state = ToolbarState()
        self.setWindowTitle("Toolbar Manager")
        self.resize(580, 680)

        # --- profile row
        self.profile_combo = QComboBox()
        self.btn_new = QPushButton("New…")
        self.btn_delete = QPushButton("Delete")
        btn_import = QPushButton("Import…")
        btn_export = QPushButton("Export…")
        btn_import.setToolTip("Load profiles from a settings file")
        btn_export.setToolTip("Save all profiles to a settings file you can import later")
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Profile:"))
        prow.addWidget(self.profile_combo, 1)
        prow.addWidget(self.btn_new)
        prow.addWidget(self.btn_delete)
        prow.addSpacing(12)
        prow.addWidget(btn_import)
        prow.addWidget(btn_export)

        # --- filter row
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter toolbars and tools…")
        self.filter_edit.setClearButtonEnabled(True)
        btn_expand = QPushButton("Expand all")
        btn_collapse = QPushButton("Collapse all")
        frow = QHBoxLayout()
        frow.addWidget(self.filter_edit, 1)
        frow.addWidget(btn_expand)
        frow.addWidget(btn_collapse)

        # --- tabs: one tree for QGIS toolbars, one for plugin toolbars
        self.tabs = QTabWidget()
        self.trees = []
        for title in TAB_TITLES:
            tree = QTreeWidget()
            tree.setHeaderLabels(["Toolbar / Tool"])
            tree.setUniformRowHeights(True)
            tree.currentItemChanged.connect(self.update_buttons)
            self.trees.append(tree)
            self.tabs.addTab(tree, title)

        hint = QLabel("Tick a toolbar to show it; tick a tool to keep it on its toolbar. "
                      "Hidden tools remain available in the menus.")
        hint.setWordWrap(True)

        # --- bulk buttons
        self.btn_all_on = QPushButton("All tools on")
        self.btn_all_off = QPushButton("All tools off")
        btn_tb_all = QPushButton("Show all in tab")
        btn_tb_none = QPushButton("Hide all in tab")
        brow = QHBoxLayout()
        brow.addWidget(self.btn_all_on)
        brow.addWidget(self.btn_all_off)
        brow.addStretch(1)
        brow.addWidget(btn_tb_all)
        brow.addWidget(btn_tb_none)

        # --- dialog buttons
        SB = QDialogButtonBox.StandardButton
        self.buttons = QDialogButtonBox(SB.Ok | SB.Apply | SB.Cancel | SB.Reset)
        self.buttons.button(SB.Reset).setText("Reset (show everything)")

        layout = QVBoxLayout(self)
        layout.addLayout(prow)
        layout.addLayout(frow)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(hint)
        layout.addLayout(brow)
        layout.addWidget(self.buttons)

        # --- signals
        self.filter_edit.textChanged.connect(self.apply_filter)
        btn_expand.clicked.connect(lambda: self.current_tree().expandAll())
        btn_collapse.clicked.connect(lambda: self.current_tree().collapseAll())
        self.tabs.currentChanged.connect(self.update_buttons)
        self.btn_all_on.clicked.connect(lambda: self.set_selected_tools(True))
        self.btn_all_off.clicked.connect(lambda: self.set_selected_tools(False))
        btn_tb_all.clicked.connect(lambda: self.set_all_toolbars(True))
        btn_tb_none.clicked.connect(lambda: self.set_all_toolbars(False))
        self.btn_new.clicked.connect(self.new_profile)
        self.btn_delete.clicked.connect(self.delete_profile)
        btn_import.clicked.connect(self.import_settings)
        btn_export.clicked.connect(self.export_settings)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(SB.Apply).clicked.connect(self.apply)
        self.buttons.button(SB.Reset).clicked.connect(self.reset)

        current = self.manager.current_profile()
        self.reload_profiles(current)
        self.profile_combo.currentTextChanged.connect(self.profile_changed)
        self.populate(self.manager.load(current).merged_with(self.manager.capture()))
        self.update_buttons()

    # ------------------------------------------------------------- building
    def current_tree(self):
        return self.trees[self.tabs.currentIndex()]

    def populate(self, state):
        self._base_state = state
        expanded = {it.data(0, ROLE_KEY) for it in self._toolbar_items() if it.isExpanded()}
        for tree in self.trees:
            tree.clear()
        for tb in self.manager.toolbars():
            key = toolbar_key(tb)
            tree = self.trees[0 if is_core_toolbar(tb) else 1]
            parent = QTreeWidgetItem(tree, [clean_text(tb.windowTitle() or key)])
            parent.setData(0, ROLE_KIND, KIND_TOOLBAR)
            parent.setData(0, ROLE_KEY, key)
            parent.setToolTip(0, key)
            parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            visible = state.visible.get(key, tb.isVisible())
            parent.setCheckState(0, CHECKED if visible else UNCHECKED)
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)

            hidden = state.hidden.get(key, set())
            for action, aid in self.manager.action_ids(tb):
                child = QTreeWidgetItem(parent, [self.manager.action_label(action)])
                child.setData(0, ROLE_KIND, KIND_TOOL)
                child.setData(0, ROLE_KEY, aid)
                child.setIcon(0, action.icon())
                child.setToolTip(0, clean_text(action.toolTip() or "") or aid)
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, UNCHECKED if aid in hidden else CHECKED)
                if action.isSeparator():
                    child.setForeground(0, self.palette().mid())
            parent.setExpanded(key in expanded)
        for i, tree in enumerate(self.trees):
            self.tabs.setTabText(i, "%s (%d)" % (TAB_TITLES[i], tree.topLevelItemCount()))
        self.apply_filter(self.filter_edit.text())

    def _toolbar_items(self, tree=None):
        trees = [tree] if tree is not None else self.trees
        return [t.topLevelItem(i) for t in trees for i in range(t.topLevelItemCount())]

    def state_from_tree(self):
        state = ToolbarState()
        for parent in self._toolbar_items():
            key = parent.data(0, ROLE_KEY)
            state.visible[key] = parent.checkState(0) == CHECKED
            state.hidden[key] = {parent.child(i).data(0, ROLE_KEY)
                                 for i in range(parent.childCount())
                                 if parent.child(i).checkState(0) != CHECKED}
        return self._base_state.merged_with(state)

    # -------------------------------------------------------------- filters
    def apply_filter(self, text):
        text = text.strip().lower()
        for parent in self._toolbar_items():
            parent_match = not text or text in parent.text(0).lower()
            any_child = False
            for i in range(parent.childCount()):
                child = parent.child(i)
                match = parent_match or text in child.text(0).lower()
                child.setHidden(not match)
                any_child = any_child or match
            parent.setHidden(not (parent_match or any_child))
            if text and any_child and not parent_match:
                parent.setExpanded(True)

    # -------------------------------------------------------------- bulk ops
    def _current_toolbar_item(self):
        it = self.current_tree().currentItem()
        if it is not None and it.data(0, ROLE_KIND) == KIND_TOOL:
            it = it.parent()
        return it

    def update_buttons(self, *args):
        has = self._current_toolbar_item() is not None
        self.btn_all_on.setEnabled(has)
        self.btn_all_off.setEnabled(has)
        self.btn_delete.setEnabled(self.profile_combo.currentText() != DEFAULT_PROFILE)

    def set_selected_tools(self, on):
        parent = self._current_toolbar_item()
        if parent is None:
            return
        for i in range(parent.childCount()):
            if not parent.child(i).isHidden():
                parent.child(i).setCheckState(0, CHECKED if on else UNCHECKED)

    def set_all_toolbars(self, on):
        for parent in self._toolbar_items(self.current_tree()):
            if not parent.isHidden():
                parent.setCheckState(0, CHECKED if on else UNCHECKED)

    # -------------------------------------------------------------- profiles
    def reload_profiles(self, select):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(self.manager.profiles())
        idx = self.profile_combo.findText(select)
        self.profile_combo.setCurrentIndex(max(idx, 0))
        self.profile_combo.blockSignals(False)

    def profile_changed(self, name):
        if name:
            state = self.manager.load(name)
            if name == self.manager.current_profile():
                state = state.merged_with(self.manager.capture())
            self.populate(state)
        self.update_buttons()

    def new_profile(self):
        name, ok = QInputDialog.getText(self, "New profile",
                                        "Profile name (starts from the current selection):")
        name = safe_profile_name(name)
        if not ok or not name:
            return
        if name in self.manager.profiles():
            QMessageBox.warning(self, "Toolbar Manager", "A profile named '%s' already exists." % name)
            return
        self.manager.save(name, self.state_from_tree())
        self.reload_profiles(name)
        self.update_buttons()

    def delete_profile(self):
        name = self.profile_combo.currentText()
        if name == DEFAULT_PROFILE:
            return
        if QMessageBox.question(self, "Toolbar Manager", "Delete profile '%s'?" % name) != MB.Yes:
            return
        self.manager.delete(name)
        if self.manager.current_profile() == name:
            self.manager.set_current_profile(DEFAULT_PROFILE)
        self.reload_profiles(DEFAULT_PROFILE)
        self.profile_changed(DEFAULT_PROFILE)

    # ---------------------------------------------------- file import/export
    @staticmethod
    def _last_dir():
        return QgsSettings().value(SETTINGS_ROOT + "/lastDir", os.path.expanduser("~"))

    @staticmethod
    def _set_last_dir(path):
        QgsSettings().setValue(SETTINGS_ROOT + "/lastDir", os.path.dirname(path))

    def export_settings(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Toolbar Manager settings",
            os.path.join(self._last_dir(), "toolbar_manager_settings.json"),
            "Toolbar Manager settings (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        # Export what is saved, but use what is on screen for the selected profile.
        selected = self.profile_combo.currentText() or DEFAULT_PROFILE
        profiles = {name: self.manager.load(name) for name in self.manager.profiles()}
        profiles[selected] = self.state_from_tree()
        try:
            self.manager.export_file(path, profiles, selected)
        except OSError as e:
            QMessageBox.critical(self, "Toolbar Manager", "Could not write the file:\n%s" % e)
            return
        self._set_last_dir(path)
        QMessageBox.information(self, "Toolbar Manager",
                                "Exported %d profile(s) to:\n%s" % (len(profiles), path))

    def import_settings(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Toolbar Manager settings", self._last_dir(),
            "Toolbar Manager settings (*.json);;All files (*)")
        if not path:
            return
        try:
            imported, current = self.manager.import_file(path)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Toolbar Manager", "Could not import the file:\n%s" % e)
            return
        self._set_last_dir(path)

        imported = {safe_profile_name(n) or DEFAULT_PROFILE: st for n, st in imported.items()}
        current = safe_profile_name(current) if current else None
        # Only profiles that were actually saved count as clashes.
        existing = set(self.manager.saved_profiles()) & set(imported)
        overwrite = True
        if existing:
            answer = QMessageBox.question(
                self, "Toolbar Manager",
                "These profiles already exist:\n  %s\n\nOverwrite them?\n"
                "(No keeps both, adding the imported ones as \"… (imported)\")"
                % "\n  ".join(sorted(existing)),
                MB.Yes | MB.No | MB.Cancel)
            if answer == MB.Cancel:
                return
            overwrite = answer == MB.Yes

        names = []
        for name, state in imported.items():
            if name in existing and not overwrite:
                new, n = "%s (imported)" % name, 2
                while new in self.manager.profiles():
                    new, n = "%s (imported %d)" % (name, n), n + 1
                if name == current:
                    current = new
                name = new
            self.manager.save(name, state)
            names.append(name)

        select = current if current in names else names[0]
        self.reload_profiles(select)
        self.profile_changed(select)
        QMessageBox.information(
            self, "Toolbar Manager",
            "Imported %d profile(s). Showing '%s'. Press Apply or OK to use it."
            % (len(names), select))

    # --------------------------------------------------------------- actions
    def apply(self):
        state = self.state_from_tree()
        profile = self.profile_combo.currentText() or DEFAULT_PROFILE
        self.manager.apply(state)
        self.manager.save(profile, state)
        self.manager.set_current_profile(profile)
        self._base_state = state

    def accept(self):
        self.apply()
        super().accept()

    def reset(self):
        self.populate(ToolbarState(visible={toolbar_key(tb): True
                                            for tb in self.manager.toolbars()}))
