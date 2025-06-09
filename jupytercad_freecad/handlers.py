import json
import base64
from pathlib import Path
import os
import shutil

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join, ApiPath, to_os_path
import tornado

from jupytercad_freecad.freecad.loader import FCStd
from jupytercad_freecad.freecad.jcad_converter import export_jcad_to_fcstd


class BackendCheckHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        body = self.get_json_body()
        backend = body.get("backend")
        if backend == "FreeCAD":
            fc_installed = True
            try:
                import freecad  # noqa
            except ImportError:
                fc_installed = False
            self.finish(json.dumps({"installed": fc_installed}))
        elif backend == "JCAD":
            self.finish(json.dumps({"installed": True}))
        else:
            self.finish(json.dumps({"installed": False}))


class JCadExportHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        body = self.get_json_body()

        # Works with both prefixed and unprefixed paths
        path = body.get("path", "")
        parts = path.split(":", 1)

        if len(parts) == 2:
            file_name = parts[1]
        else:
            file_name = parts[0]  # fallback: treat whole thing as path

        export_name = body["newName"]

        root_dir = Path(self.contents_manager.root_dir).resolve()
        file_path = Path(to_os_path(ApiPath(file_name), str(root_dir)))

        try:
            with open(file_path, "rb") as fobj:
                base64_content = base64.b64encode(fobj.read()).decode("utf-8")
        except Exception as e:
            self.log.error(f"Error reading file {file_path}: {e}")
            self.set_status(500)
            self.finish(json.dumps({"error": f"Failed to read file: {str(e)}"}))
            return

        try:
            fcstd = FCStd()
            fcstd.load(base64_content=base64_content)
        except Exception as e:
            self.log.error(f"Error loading FCStd file: {e}")
            self.set_status(500)
            self.finish(json.dumps({"error": f"Failed to load FCStd file: {str(e)}"}))
            return

        jcad = dict(
            schemaVersion="1.0",
            objects=fcstd._objects,
            metadata=fcstd._metadata,
            options=fcstd._guidata,
            outputs={},
        )

        export_path = file_path.parent / export_name
        try:
            with open(export_path, "w") as fobj:
                fobj.write(json.dumps(jcad, indent=2))
        except Exception as e:
            self.log.error(f"Error writing JCAD file: {e}")
            self.set_status(500)
            self.finish(json.dumps({"error": f"Failed to write JCAD file: {str(e)}"}))
            return

        self.finish(json.dumps({"done": True, "exportedPath": str(export_path)}))


class FCStdExportHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        body = self.get_json_body()

        # same path‐splitting logic as JCadExportHandler
        path = body.get("path", "")
        parts = path.split(":", 1)
        file_name = parts[1] if len(parts) == 2 else parts[0]

        new_name = body["newName"]
        root_dir = Path(self.contents_manager.root_dir).resolve()
        in_path = Path(to_os_path(ApiPath(file_name), str(root_dir)))
        out_path = in_path.parent / new_name

        # load JCAD JSON from disk
        try:
            jcad_dict = json.loads(in_path.read_text())
        except Exception as e:
            self.log.error(f"Error reading JCAD file {in_path}: {e}")
            self.set_status(500)
            return self.finish(json.dumps({"error": str(e)}))

        # convert to FreeCAD document
        try:
            doc = export_jcad_to_fcstd(jcad_dict)

            temp_fcstd_path = doc.FileName
            shutil.copy2(temp_fcstd_path, str(out_path))

            # Clean up the temporary file
            if os.path.exists(temp_fcstd_path):
                os.unlink(temp_fcstd_path)

        except Exception as e:
            self.log.error(f"Error converting to FCStd: {e}")
            self.set_status(500)
            return self.finish(json.dumps({"error": str(e)}))

        self.finish(json.dumps({"done": True, "exportedPath": str(out_path)}))


def setup_handlers(web_app):
    host_pattern = ".*$"

    base_url = web_app.settings["base_url"]

    handlers = [
        (
            url_path_join(base_url, "jupytercad_freecad", "backend-check"),
            BackendCheckHandler,
        ),
        (
            url_path_join(base_url, "jupytercad_freecad", "export-jcad"),
            JCadExportHandler,
        ),
        (
            url_path_join(base_url, "jupytercad_freecad", "export-fcstd"),
            FCStdExportHandler,
        ),
    ]
    web_app.add_handlers(host_pattern, handlers)
