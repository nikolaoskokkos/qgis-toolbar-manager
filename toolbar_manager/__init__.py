def classFactory(iface):
    from .plugin import ToolbarManagerPlugin
    return ToolbarManagerPlugin(iface)
