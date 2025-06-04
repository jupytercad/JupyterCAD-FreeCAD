import re
import tempfile

import freecad as fc
import OfflineRenderingUtils  # type: ignore[import]

from .loader import _hex_to_rgb
from .props.base_prop import BaseProp
from . import props as Props


def sanitize_object_name(name: str) -> str:
    """Convert object names to FreeCAD-compatible format."""
    s = name.replace(" ", "_").replace("-", "_")
    return re.sub(r"[^\w_]", "_", s)


def build_prop_handlers():
    return {
        Cls.name(): Cls
        for Cls in Props.__dict__.values()
        if isinstance(Cls, type) and issubclass(Cls, BaseProp)
    }


def update_references(jcad_dict, name_mapping):
    """Walk all parameters and rewrite any string/list references using name_mapping."""
    for obj in jcad_dict.get("objects", []):
        params = obj.get("parameters", {})
        for key, val in params.items():
            if isinstance(val, str) and val in name_mapping:
                params[key] = name_mapping[val]
            elif isinstance(val, list):
                params[key] = [
                    name_mapping.get(item, item) if isinstance(item, str) else item
                    for item in val
                ]


def create_body_and_coordinates(doc, body_obj, fc_objects):
    """Create a PartDesign::Body so that FreeCAD auto-creates Origin & axes."""
    body_name = body_obj["name"]
    body_fc = doc.addObject("PartDesign::Body", body_name)
    fc_objects[body_name] = body_fc

    # Once the Body is created, FreeCAD auto-adds an Origin with child axes & planes.
    if not body_fc.Origin:
        return body_fc

    fc_objects["Origin"] = body_fc.Origin
    for child in body_fc.Origin.Group:
        role = getattr(child, "Role", "")
        # Role is typically "X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", etc.
        if role in {"X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane"}:
            fc_objects[role] = child

    return body_fc


def apply_object_properties(fc_obj, jcad_obj, prop_handlers, doc):
    """Run through all non‐color parameters and use the Prop handlers to set them."""
    params = jcad_obj.get("parameters", {})
    for prop, jval in params.items():
        if prop == "Color" or not hasattr(fc_obj, prop):
            continue
        prop_type = fc_obj.getTypeIdOfProperty(prop)
        Handler = prop_handlers.get(prop_type)
        if not Handler:
            continue
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
            print(f"Error setting {prop} on {fc_obj.Name}: {e}")


def export_jcad_to_fcstd(jcad_dict: dict) -> "fc.Document":
    doc = fc.app.newDocument("__jcad_export__")
    doc.Meta = jcad_dict.get("metadata", {})

    prop_handlers = build_prop_handlers()
    coordinate_names = {
        "Origin", "X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane"
    }

    # 1) Sanitize all JCAD object names and build a mapping
    name_mapping = {
        obj["name"]: sanitize_object_name(obj["name"])
        for obj in jcad_dict.get("objects", [])
    }
    for obj in jcad_dict.get("objects", []):
        obj["name"] = name_mapping[obj["name"]]
    update_references(jcad_dict, name_mapping)

    fc_objects = {}
    guidata = {}  # objectName → { "ShapeColor": (r,g,b), "Visibility": bool }

    # 2) Separate out any PartDesign::Body objects
    body_objs = [
        o for o in jcad_dict.get("objects", [])
        if o["shape"] == "PartDesign::Body"
    ]
    other_objs = [
        o for o in jcad_dict.get("objects", [])
        if o not in body_objs and o["name"] not in coordinate_names
    ]

    # 3) Create bodies (so that coordinate system objects appear)
    for body_obj in body_objs:
        body_fc = create_body_and_coordinates(doc, body_obj, fc_objects)
        apply_object_properties(body_fc, body_obj, prop_handlers, doc)

        # Record body color
        hexcol = body_obj.get("parameters", {}).get("Color") or \
                 (jcad_dict.get("options", {}).get(body_obj["name"], {}).get("color") or "#808080")
        rgb = _hex_to_rgb(hexcol)

        # Instead of just building color_map, build a complete guidata dictionary
        body_opts = jcad_dict.get("options", {}).get(body_obj["name"], {})
        # Check visibility: prioritize options, then object-level visible, default to True
        visible = body_opts.get("visible")
        if visible is None:
            visible = body_obj.get("visible", True)
        
        guidata[body_obj["name"]] = {
            "ShapeColor": {"type": "App::PropertyColor", "value": rgb},
            "Visibility": {"type": "App::PropertyBool", "value": visible},
        }

        # Any coordinate‐system objects that now exist should inherit the same color
        for coord_name in coordinate_names:
            if coord_name in fc_objects:
                guidata[coord_name] = {
                    "ShapeColor": {"type": "App::PropertyColor", "value": rgb},
                    "Visibility": {"type": "App::PropertyBool", "value": False},  # Usually coordinate objects are hidden
                }

    # 4) Create all other (non-body, non-coordinate) objects
    for obj in other_objs:
        fc_obj = doc.addObject(obj["shape"], obj["name"])
        fc_objects[obj["name"]] = fc_obj
        apply_object_properties(fc_obj, obj, prop_handlers, doc)

        # Instead of just building color_map, build a complete guidata dictionary
        obj_opts = jcad_dict.get("options", {}).get(obj["name"], {})
        hexcol = obj.get("parameters", {}).get("Color") or obj_opts.get("color", "#808080")
        # Check visibility: prioritize options, then object-level visible, default to True
        visible = obj_opts.get("visible")
        if visible is None:
            visible = obj.get("visible", True)

        # Build guidata entry with both color and visibility
        guidata[obj["name"]] = {
            "ShapeColor": {"type": "App::PropertyColor", "value": _hex_to_rgb(hexcol)},
            "Visibility": {"type": "App::PropertyBool", "value": visible},
        }

    # 5) Recompute so that FreeCAD has generated any missing children
    doc.recompute()

    # 6) Save to a temp FCStd using guidata instead of colors
    with tempfile.NamedTemporaryFile(delete=False, suffix=".FCStd") as tmp:
        tmp_path = tmp.name

        # Default camera settings
        default_camera = 'OrthographicCamera { viewportMapping ADJUST_CAMERA position 8.5470247 -1.1436439 9.9673195 orientation 0.86492187 0.23175442 0.44519675 1.0835806 nearDistance 0.19726367 farDistance 17.140171 aspectRatio 1 focalDistance 8.6602545 height 17.320509 }'

         # Add camera to guidata - try the direct string approach
        guidata["GuiCameraSettings"] = default_camera

        # Use guidata to include both color, visibility, AND camera
        OfflineRenderingUtils.save(
            doc,
            filename=tmp_path,
            guidata=guidata
        )

    # 7) Finally, open that new FCStd in FreeCAD and return the Document handle
    return fc.app.openDocument(tmp_path)
