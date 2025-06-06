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

    # 1) Sanitize JCAD names in place and build a mapping
    name_mapping = {}
    for obj in jcad_dict.get("objects", []):
        original = obj["name"]
        sanitized = sanitize_object_name(original)
        name_mapping[original] = sanitized
        obj["name"] = sanitized

    update_references(jcad_dict, name_mapping)

    fc_objects = {}
    guidata = {}

    # 2) Separate PartDesign::Body entries from others
    body_objs = [
        o for o in jcad_dict.get("objects", [])
        if o["shape"] == "PartDesign::Body"
    ]
    other_objs = [
        o for o in jcad_dict.get("objects", [])
        if o not in body_objs and o["name"] not in coordinate_names
    ]

    # Helper: determine RGB tuple and visibility flag
    def _color_and_visibility(jcad_obj):
        opts = jcad_dict.get("options", {}).get(jcad_obj["name"], {})
        hexcol = (
            jcad_obj.get("parameters", {}).get("Color")
            or opts.get("color", "#808080")
        )
        rgb = _hex_to_rgb(hexcol)
        visible = opts.get("visible")
        if visible is None:
            visible = jcad_obj.get("visible", True)
        return rgb, visible

    # 3) Create all PartDesign::Body objects
    for body_obj in body_objs:
        body_fc = create_body_and_coordinates(doc, body_obj, fc_objects)
        apply_object_properties(body_fc, body_obj, prop_handlers, doc)

        rgb, visible = _color_and_visibility(body_obj)
        guidata[body_obj["name"]] = {
            "ShapeColor": {"type": "App::PropertyColor", "value": rgb},
            "Visibility": {"type": "App::PropertyBool", "value": visible},
        }

        # Coordinate children inherit the same color but remain hidden
        for coord in coordinate_names:
            if coord in fc_objects:
                guidata[coord] = {
                    "ShapeColor": {"type": "App::PropertyColor", "value": rgb},
                    "Visibility": {"type": "App::PropertyBool", "value": False},
                }

    # 4) Create all other objects
    for obj in other_objs:
        fc_obj = doc.addObject(obj["shape"], obj["name"])
        fc_objects[obj["name"]] = fc_obj
        apply_object_properties(fc_obj, obj, prop_handlers, doc)

        rgb, visible = _color_and_visibility(obj)
        default_camera = (
        "OrthographicCamera {\n"
        "    viewportMapping ADJUST_CAMERA\n"
        "    position 5.0 0.0 10.0\n"
        "    orientation 0.7 0.2 0.4 1.0\n"
        "    nearDistance 0.2\n"
        "    farDistance 20.0\n"
        "    aspectRatio 1.0\n"
        "    focalDistance 8.0\n"
        "    height 16.0\n"
        "}")
        guidata[obj["name"]] = {
            "ShapeColor": {"type": "App::PropertyColor", "value": rgb},
            "Visibility": {"type": "App::PropertyBool", "value": visible},
        }
        guidata["GuiCameraSettings"] = default_camera

    # 5) Recompute so FreeCAD generates any missing children
    doc.recompute()

    # 7) Save with guidata so FreeCAD writes a full GuiDocument.xml
    with tempfile.NamedTemporaryFile(delete=False, suffix=".FCStd") as tmp:
        path = tmp.name
        OfflineRenderingUtils.save(doc, filename=path, guidata=guidata)

    return fc.app.openDocument(path)