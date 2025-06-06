from io import StringIO
from typing import Any

from .base_prop import BaseProp


class Part_PropertyPartShape(BaseProp):
    @staticmethod
    def name() -> str:
        return "Part::PropertyPartShape"

    @staticmethod
    def fc_to_jcad(prop_value: Any, **kwargs) -> Any:
        buffer = StringIO()
        prop_value.exportBrep(buffer)
        return buffer.getvalue()

    @staticmethod
    def jcad_to_fc(prop_value: str, **kwargs) -> Any:
        try:
            import freecad as fc
            import Part as Part
        except ImportError:
            print("Error: FreeCAD or Part module could not be imported in jcad_to_fc.")
            return None

        if not prop_value:
            print("Warning: jcad_to_fc received empty prop_value for PartShape.")
            return None

        try:
            shape = Part.Shape()
            shape.importBrepFromString(prop_value) 
            
            if shape.isNull():
                print(f"Warning: Reconstructed shape is Null after importBrepFromString. Input (first 100 chars): {prop_value[:100]}...")
                return None 

            return shape
        except Exception as e:
            print(f"Failed to rebuild BRep shape with importBrepFromString: {e}. Input (first 100 chars): {prop_value[:100]}...")
            return None
