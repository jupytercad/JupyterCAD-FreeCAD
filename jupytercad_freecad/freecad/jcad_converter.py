import freecad as fc
import OfflineRenderingUtils  # type: ignore[import]
import base64
import tempfile
# from .loader import FCStd
import os

from .loader import _hex_to_rgb
from .props.base_prop import BaseProp
from . import props as Props


def export_jcad_to_fcstd(jcad_dict: dict) -> 'fc.Document':
    doc = fc.app.newDocument("__jcad_export__")
    doc.Meta = jcad_dict.get("metadata", {})
    
    prop_handlers = {
        Cls.name(): Cls
        for Cls in Props.__dict__.values()
        if isinstance(Cls, type) and issubclass(Cls, BaseProp)
    }

    # LOCAL variable for guidata (no function attribute)
    guidata = {}

    for jcad_obj in jcad_dict.get("objects", []):
        shape_type = jcad_obj["shape"]
        name = jcad_obj["name"]
        params = jcad_obj.get("parameters", {})
        opts = jcad_dict.get("options", {}).get(name, {})

        fc_obj = doc.addObject(shape_type, name)

        for prop, jval in params.items():
            if prop == "Color":
                continue
            if hasattr(fc_obj, prop):
                t = fc_obj.getTypeIdOfProperty(prop)
                Handler = prop_handlers.get(t)
                if Handler:
                    try:
                        new_val = Handler.jcad_to_fc(
                            jval,
                            jcad_object=jcad_obj,
                            fc_prop=getattr(fc_obj, prop),
                            fc_object=fc_obj,
                            fc_file=doc
                        )
                        if new_val is not None:
                            setattr(fc_obj, prop, new_val)
                    except Exception as e:
                        print(f"Error setting {prop} on {name}: {e}")

        # Build guidata entry
        hexcol = params.get("Color") or opts.get("color") or "#808080"
        rgb = _hex_to_rgb(hexcol)
        guidata[name] = {
            "ShapeColor": {"type": "App::PropertyColor", "value": rgb},
            "Visibility": {"type": "App::PropertyBool", "value": opts.get("visible", True)}
        }

    doc.recompute()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".FCStd") as tmp:
        tmp_path = tmp.name

    OfflineRenderingUtils.save(
        doc,
        filename=tmp_path,
        guidata=guidata
    )

    return fc.app.openDocument(tmp_path)