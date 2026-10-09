"""Build dist/toolbar_manager-<version>.zip ready for plugins.qgis.org."""
import configparser
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = "toolbar_manager"
SRC = os.path.join(HERE, PLUGIN)

meta = configparser.ConfigParser()
meta.read(os.path.join(SRC, "metadata.txt"), encoding="utf-8")
version = meta["general"]["version"]

os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
out = os.path.join(HERE, "dist", "%s-%s.zip" % (PLUGIN, version))
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for name in sorted(os.listdir(SRC)):
        path = os.path.join(SRC, name)
        if os.path.isfile(path) and not name.endswith(".pyc"):
            z.write(path, "%s/%s" % (PLUGIN, name))
print(out)
