import json

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
import tornado


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


def setup_handlers(web_app):
    host_pattern = ".*$"

    base_url = web_app.settings["base_url"]
    route_pattern = url_path_join(base_url, "jupytercad_freecad", "backend-check")
    handlers = [(route_pattern, BackendCheckHandler)]
    web_app.add_handlers(host_pattern, handlers)
