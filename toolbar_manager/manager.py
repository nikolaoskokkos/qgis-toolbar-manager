"""Core logic: discover toolbars/tools, hide/restore them, persist choices.

Tools are hidden by *removing* the action from the toolbar (not by calling
QAction.setVisible), so the same action stays available in menus. The original
order of every toolbar is remembered so a tool can be re-inserted exactly where
it was.
"""
import json

from qgis.PyQt import sip
from qgis.PyQt.QtWidgets import QToolBar, QWidgetAction
from qgis.core import QgsSettings

SETTINGS_ROOT = "ToolbarManager"
DEFAULT_PROFILE = "Default"
FILE_FORMAT = "qgis-toolbar-manager"
FILE_VERSION = 1

# Object names of QGIS's built-in main-window toolbars (taken from qgis_app for
# QGIS 3.44 / 4.2). Anything else, plus the "Plugins" toolbar, counts as a plugin toolbar.
CORE_TOOLBARS = {
    "mFileToolBar", "mLayerToolBar", "mDigitizeToolBar", "mAdvancedDigitizeToolBar",
    "mShapeDigitizeToolBar", "mMapNavToolBar", "mAttributesToolBar", "mSelectionToolBar",
    "mHelpToolBar", "mRasterToolBar", "mLabelToolBar", "mVectorToolBar",
    "mDatabaseToolBar", "mWebToolBar", "mSnappingToolBar", "mDataSourceManagerToolBar",
    "mMeshToolBar", "mAnnotationsToolBar", "mGpsToolBar", "mBookmarkToolbar",
    "mIdentifyToolbar", "mNavigationToolbar", "mToolsToolbar", "mActionsToolbar",
}


def toolbar_key(tb):
    return tb.objectName() or tb.windowTitle()


def is_core_toolbar(tb):
    return tb.objectName() in CORE_TOOLBARS


def clean_text(text):
    return text.replace("&&", "\x00").replace("&", "").replace("\x00", "&").strip()


class ToolbarState:
    """Per-profile configuration: hidden tools per toolbar + toolbar visibility."""

    def __init__(self, hidden=None, visible=None):
        self.hidden = {k: set(v) for k, v in (hidden or {}).items()}
        self.visible = dict(visible or {})

    def to_json(self):
        return json.dumps({
            "hidden": {k: sorted(v) for k, v in self.hidden.items() if v},
            "visible": self.visible,
        })

    def to_dict(self):
        return json.loads(self.to_json())

    @classmethod
    def from_dict(cls, data):
        data = data if isinstance(data, dict) else {}
        hidden = data.get("hidden") if isinstance(data.get("hidden"), dict) else {}
        visible = data.get("visible") if isinstance(data.get("visible"), dict) else {}
        return cls({k: v for k, v in hidden.items() if isinstance(v, list)},
                   {k: bool(v) for k, v in visible.items()})

    @classmethod
    def from_json(cls, text):
        try:
            data = json.loads(text) if text else {}
        except ValueError:
            data = {}
        return cls.from_dict(data)

    def merged_with(self, other):
        """Copy of self with other's entries taking precedence."""
        hidden = {k: set(v) for k, v in self.hidden.items()}
        hidden.update({k: set(v) for k, v in other.hidden.items()})
        visible = dict(self.visible)
        visible.update(other.visible)
        return ToolbarState(hidden, visible)


class ToolbarManager:
    def __init__(self, iface):
        self.iface = iface
        # toolbar key -> list of QAction in original order (present or removed)
        self._order = {}

    # ------------------------------------------------------------ discovery
    def toolbars(self):
        mw = self.iface.mainWindow()
        result = [tb for tb in mw.findChildren(QToolBar)
                  if tb.parent() is mw and toolbar_key(tb)]
        result.sort(key=lambda tb: clean_text(tb.windowTitle() or tb.objectName()).lower())
        return result

    def ordered_actions(self, tb):
        """All actions this toolbar has ever had (in original order)."""
        key = toolbar_key(tb)
        order = [a for a in self._order.get(key, []) if not sip.isdeleted(a)]
        prev = None
        for a in tb.actions():
            if a not in order:
                if prev is None:
                    order.insert(0, a)
                else:
                    order.insert(order.index(prev) + 1, a)
            prev = a
        self._order[key] = order
        return order

    def action_ids(self, tb):
        """List of (action, stable_id) pairs for a toolbar."""
        result = []
        seen = {}
        for a in self.ordered_actions(tb):
            if a.isSeparator():
                base = "sep"
            elif a.objectName():
                base = "name:" + a.objectName()
            elif isinstance(a, QWidgetAction) and a.defaultWidget() is not None:
                w = a.defaultWidget()
                base = "widget:" + (w.objectName() or type(w).__name__)
            elif a.text():
                base = "text:" + clean_text(a.text())
            else:
                base = "unnamed"
            n = seen.get(base, 0)
            seen[base] = n + 1
            result.append((a, base if n == 0 and base != "sep" else "%s#%d" % (base, n)))
        return result

    @staticmethod
    def action_label(a):
        if a.isSeparator():
            return "──────  separator  ──────"
        text = clean_text(a.text() or a.toolTip() or "")
        if not text and isinstance(a, QWidgetAction) and a.defaultWidget() is not None:
            w = a.defaultWidget()
            text = w.toolTip() or w.objectName() or type(w).__name__
        return text or a.objectName() or "(unnamed tool)"

    # ------------------------------------------------------------- applying
    def set_tool_shown(self, tb, action, shown):
        present = action in tb.actions()
        if not shown and present:
            tb.removeAction(action)
        elif shown and not present:
            order = self.ordered_actions(tb)
            current = tb.actions()
            before = None
            for a in order[order.index(action) + 1:]:
                if a in current:
                    before = a
                    break
            if before is None:
                tb.addAction(action)
            else:
                tb.insertAction(before, action)

    def apply(self, state, apply_visibility=True):
        for tb in self.toolbars():
            key = toolbar_key(tb)
            hidden = state.hidden.get(key, set())
            for action, aid in self.action_ids(tb):
                self.set_tool_shown(tb, action, aid not in hidden)
            if apply_visibility and key in state.visible:
                tb.setVisible(bool(state.visible[key]))

    def restore_all(self):
        for tb in self.toolbars():
            for action, _ in self.action_ids(tb):
                self.set_tool_shown(tb, action, True)

    def capture(self):
        """Current live state of the UI as a ToolbarState."""
        state = ToolbarState()
        for tb in self.toolbars():
            key = toolbar_key(tb)
            current = tb.actions()
            hidden = {aid for a, aid in self.action_ids(tb) if a not in current}
            if hidden:
                state.hidden[key] = hidden
            state.visible[key] = tb.isVisible()
        return state

    # ---------------------------------------------------------- persistence
    @staticmethod
    def saved_profiles():
        s = QgsSettings()
        s.beginGroup(SETTINGS_ROOT + "/profiles")
        names = s.childKeys()
        s.endGroup()
        return names

    @classmethod
    def profiles(cls):
        names = cls.saved_profiles()
        if DEFAULT_PROFILE not in names:
            names.insert(0, DEFAULT_PROFILE)
        return names

    @staticmethod
    def current_profile():
        return QgsSettings().value(SETTINGS_ROOT + "/current", DEFAULT_PROFILE)

    @staticmethod
    def set_current_profile(name):
        QgsSettings().setValue(SETTINGS_ROOT + "/current", name)

    @staticmethod
    def load(profile):
        return ToolbarState.from_json(
            QgsSettings().value("%s/profiles/%s" % (SETTINGS_ROOT, profile), ""))

    @staticmethod
    def save(profile, state):
        QgsSettings().setValue("%s/profiles/%s" % (SETTINGS_ROOT, profile), state.to_json())

    @staticmethod
    def delete(profile):
        QgsSettings().remove("%s/profiles/%s" % (SETTINGS_ROOT, profile))

    # --------------------------------------------------------- file export
    @staticmethod
    def export_file(path, profiles, current):
        """profiles: {name: ToolbarState}"""
        data = {
            "format": FILE_FORMAT,
            "version": FILE_VERSION,
            "current": current,
            "profiles": {name: st.to_dict() for name, st in profiles.items()},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def import_file(path):
        """Returns ({name: ToolbarState}, current_name). Raises ValueError if invalid."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("format") != FILE_FORMAT:
            raise ValueError("This is not a Toolbar Manager settings file.")
        profiles = data.get("profiles")
        if not isinstance(profiles, dict) or not profiles:
            raise ValueError("The file contains no profiles.")
        return ({str(n): ToolbarState.from_dict(st) for n, st in profiles.items()},
                data.get("current"))
