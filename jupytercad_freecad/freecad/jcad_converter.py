import freecad as fc
import OfflineRenderingUtils  # type: ignore[import]
import base64
import tempfile
import os
import re

from .loader import _hex_to_rgb
from .props.base_prop import BaseProp
from . import props as Props


def sanitize_object_name(name: str) -> str:
    """Convert object names to FreeCAD-compatible format."""
    # Replace spaces or hyphens with underscores, then drop any other non-word
    sanitized = name.replace(" ", "_").replace("-", "_")
    return re.sub(r"[^\w_]", "_", sanitized)


def export_jcad_to_fcstd(jcad_dict: dict) -> "fc.Document":
    doc = fc.app.newDocument("__jcad_export__")
    doc.Meta = jcad_dict.get("metadata", {})

    # Build Prop handler lookup
    prop_handlers = {
        Cls.name(): Cls
        for Cls in Props.__dict__.values()
        if isinstance(Cls, type) and issubclass(Cls, BaseProp)
    }

    # 1) Build a simple original→sanitized name map
    name_mapping = {
        obj["name"]: sanitize_object_name(obj["name"])
        for obj in jcad_dict.get("objects", [])
    }

    # 2) Rename each object in place, and fix any string or list references in parameters
    for obj in jcad_dict.get("objects", []):
        orig = obj["name"]
        obj["name"] = name_mapping[orig]

        params = obj.get("parameters", {})
        for key, val in params.items():
            # If it’s a string reference to another object, rewrite it:
            if isinstance(val, str) and val in name_mapping:
                params[key] = name_mapping[val]

            # If it’s a list of references, rewrite every entry that matches a key:
            elif isinstance(val, list):
                params[key] = [
                    name_mapping[item] if (isinstance(item, str) and item in name_mapping) else item
                    for item in val
                ]

    # 3) Replay sanitized objects into FreeCAD
    guidata = {}
    for jcad_obj in jcad_dict.get("objects", []):
        shape_type = jcad_obj["shape"]
        name       = jcad_obj["name"]
        params     = jcad_obj.get("parameters", {})
        opts       = jcad_dict.get("options", {}).get(name, {})

        # Add object to FreeCAD
        fc_obj = doc.addObject(shape_type, name)

        # Apply all non-color props via handlers
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
                            fc_file=doc,
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
            "Visibility": {"type": "App::PropertyBool", "value": opts.get("visible", True)},
        }

    doc.recompute()

    # 4) Write out a temp FCStd, then apply colors/visibility
    with tempfile.NamedTemporaryFile(delete=False, suffix=".FCStd") as tmp:
        tmp_path = tmp.name
        doc.saveAs(tmp_path)

    OfflineRenderingUtils.save(
        doc,
        filename=tmp_path,
        guidata=guidata
    )

    return fc.app.openDocument(tmp_path)