# Toolbar Manager for QGIS

Choose which toolbars are shown in QGIS and which tools appear on each toolbar, all from one dialog.

## Features

- **Show or hide toolbars.** Tick a toolbar to show it, untick it to hide it.
- **Show or hide individual tools.** Untick a tool to take it off its toolbar. It stays available in the menus, and goes back in its original position when you tick it again.
- **Two tabs.** QGIS's built-in toolbars and plugin toolbars (including the *Plugins* toolbar) are listed separately.
- **Filter** to find a toolbar or tool by name, plus bulk buttons (all tools on/off, show/hide all toolbars in a tab).
- **Profiles.** Save named setups (for example *Editing* or *Cartography*) and switch between them. The active profile is applied again every time QGIS starts.
- **Export / Import.** Save all profiles to a `.json` file and load them on another machine or QGIS profile.
- Works with QGIS 3.16+ and QGIS 4 (Qt6).

## Usage

Open the dialog from **Plugins → Toolbar Manager → Toolbar Manager…**, from **View → Toolbar Manager…**, or with the plugin's toolbar button.

Tick or untick toolbars and tools, then press **Apply** or **OK**. **Reset** shows every toolbar and tool again. Turning the plugin off puts all removed tools back.

## Installation

- **From QGIS:** *Plugins → Manage and Install Plugins*, search for *Toolbar Manager*.
- **From a zip:** download a release zip, then *Plugins → Manage and Install Plugins → Install from ZIP*.

## Building the zip

```
python make_zip.py
```

This writes `dist/toolbar_manager-<version>.zip`, ready to upload to [plugins.qgis.org](https://plugins.qgis.org/).

## License

GPL-2.0-or-later. See [LICENSE](LICENSE).
