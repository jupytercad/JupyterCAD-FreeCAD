import freecad as fc
import base64
import tempfile
from .loader import FCStd
import os


def convert_jcad_to_fcstd(jcad_dict: dict) -> 'fc.Document':
    # 1) Spin up a brand‑new FreeCAD doc and write it out to a temp .FCStd
    blank = fc.app.newDocument("__jcad_blank__")
    blank.recompute()  # ensure it's fully initialized
    with tempfile.NamedTemporaryFile(delete=False, suffix=".FCStd") as tmp_blank:
        blank.saveAs(tmp_blank.name)
        tmp_blank.flush()
    fc.app.closeDocument(blank.Name)

    # 2) Read its bytes, encode as base64, give to FCStd loader
    with open(tmp_blank.name, "rb") as f:
        b64_blank = base64.b64encode(f.read()).decode("utf-8")
    os.remove(tmp_blank.name)

    fcstd = FCStd()
    fcstd._sources = b64_blank

    # 3) Replay your JCAD model into it
    objs     = jcad_dict.get("objects", [])
    opts     = jcad_dict.get("options", {})
    meta     = jcad_dict.get("metadata", {})
    fcstd.save(objs, opts, meta)

    # 4) Dump the new .FCStd and re‑open it
    with tempfile.NamedTemporaryFile(delete=False, suffix=".FCStd") as tmp_out:
        tmp_out.write(base64.b64decode(fcstd.sources))
        tmp_out.flush()

    doc = fc.app.openDocument(tmp_out.name)
    return doc

