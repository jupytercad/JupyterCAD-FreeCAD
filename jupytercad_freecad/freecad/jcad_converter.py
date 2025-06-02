import freecad as fc
import OfflineRenderingUtils  # type: ignore[import]
import tempfile
import re

from .loader import _hex_to_rgb
from .props.base_prop import BaseProp
from . import props as Props

def sanitize_object_name(name: str) -> str:
    """Convert object names to FreeCAD-compatible format."""
    sanitized = name.replace(" ", "_").replace("-", "_")
    return re.sub(r"[^\w_]", "_", sanitized)

def build_prop_handlers():
    return {
        Cls.name(): Cls for Cls in Props.__dict__.values()
        if isinstance(Cls, type) and issubclass(Cls, BaseProp)
    }

def update_references(jcad_dict, name_mapping):
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
    body_name = body_obj["name"]
    body_fc = doc.addObject("PartDesign::Body", body_name)
    fc_objects[body_name] = body_fc

    if not body_fc.Origin:
        return body_fc

    fc_objects["Origin"] = body_fc.Origin
    role_map = {
        'X_Axis': "X_Axis",
        'Y_Axis': "Y_Axis",
        'Z_Axis': "Z_Axis",
        'XY_Plane': "XY_Plane",
        'XZ_Plane': "XZ_Plane",
        'YZ_Plane': "YZ_Plane"
    }
    for child in body_fc.Origin.Group:
        role = getattr(child, 'Role', '')
        if role in role_map:
            fc_objects[role_map[role]] = child
    return body_fc

def apply_object_properties(fc_obj, jcad_obj, prop_handlers, doc):
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

def build_guidata_entry(name, params, opts):
    hexcol = params.get("Color") or opts.get("color", "#808080")
    return {
        "ShapeColor": {"type": "App::PropertyColor", "value": _hex_to_rgb(hexcol)},
        "Visibility": {"type": "App::PropertyBool", "value": opts.get("visible", True)},
    }

def export_jcad_to_fcstd(jcad_dict: dict) -> "fc.Document":
    doc = fc.app.newDocument("__jcad_export__")
    doc.Meta = jcad_dict.get("metadata", {})
    prop_handlers = build_prop_handlers()
    coordinate_names = {"Origin", "X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane"}

    # Create name mapping and update references
    name_mapping = {obj["name"]: sanitize_object_name(obj["name"]) for obj in jcad_dict.get("objects", [])}
    for obj in jcad_dict["objects"]:
        obj["name"] = name_mapping[obj["name"]]
    update_references(jcad_dict, name_mapping)

    fc_objects = {}
    guidata = {}
    body_objs = [o for o in jcad_dict.get("objects", []) if o["shape"] == "PartDesign::Body"]
    other_objs = [o for o in jcad_dict["objects"] if o not in body_objs and o["name"] not in coordinate_names]

    # Process bodies and coordinates
    for body_obj in body_objs:
        body_fc = create_body_and_coordinates(doc, body_obj, fc_objects)
        apply_object_properties(body_fc, body_obj, prop_handlers, doc)
        
        # Get body properties for coordinates
        body_params = body_obj.get("parameters", {})
        body_opts = jcad_dict.get("options", {}).get(body_obj["name"], {})
        guidata[body_obj["name"]] = build_guidata_entry(body_obj["name"], body_params, body_opts)
        
        # Add coordinate objects to guidata
        for coord_name in coordinate_names:
            if coord_name in fc_objects:
                guidata[coord_name] = build_guidata_entry(coord_name, body_params, body_opts)

    # Process other objects
    for obj in other_objs:
        fc_obj = doc.addObject(obj["shape"], obj["name"])
        fc_objects[obj["name"]] = fc_obj
        apply_object_properties(fc_obj, obj, prop_handlers, doc)
        obj_opts = jcad_dict.get("options", {}).get(obj["name"], {})
        guidata[obj["name"]] = build_guidata_entry(obj["name"], obj.get("parameters", {}), obj_opts)

    doc.recompute()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".FCStd") as tmp:
        OfflineRenderingUtils.save(doc, filename=tmp.name, guidata=guidata)
        return fc.app.openDocument(tmp.name)