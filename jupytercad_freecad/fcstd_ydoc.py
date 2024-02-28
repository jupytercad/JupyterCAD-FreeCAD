from typing import Any, Callable
from functools import partial

from pycrdt import Array, Map, Text
from jupyter_ydoc.ybasedoc import YBaseDoc

from .freecad.loader import FCStd


class YFCStd(YBaseDoc):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ydoc["source"] = self._ysource = Text()
        self._ydoc["objects"] = self._yobjects = Array()
        self._ydoc["options"] = self._yoptions = Map()
        self._ydoc["metadata"] = self._ymetadata = Map()
        self._virtual_file = FCStd()

    @property
    def objects(self) -> Array:
        return self._yobjects

    def version(self) -> str:
        return "0.1.0"

    def get(self):
        fc_objects = self._yobjects.to_py()
        options = self._yoptions.to_py()
        meta = self._ymetadata.to_py()

        self._virtual_file.save(fc_objects, options, meta)
        return self._virtual_file.sources

    def set(self, value):
        virtual_file = self._virtual_file
        virtual_file.load(value)
        objects = []

        for obj in virtual_file.objects:
            objects.append(Map(obj))
        self._yobjects.clear()
        self._yobjects.extend(objects)

        self._yoptions.clear()
        self._yoptions.update(virtual_file.options)

        self._ymetadata.clear()
        self._ymetadata.update(virtual_file.metadata)

    def observe(self, callback: Callable[[str, Any], None]):
        self.unobserve()
        self._subscriptions[self._ystate] = self._ystate.observe(
            partial(callback, "state")
        )
        self._subscriptions[self._ysource] = self._ysource.observe(
            partial(callback, "source")
        )
        self._subscriptions[self._yobjects] = self._yobjects.observe_deep(
            partial(callback, "objects")
        )
        self._subscriptions[self._yoptions] = self._yoptions.observe_deep(
            partial(callback, "options")
        )
        self._subscriptions[self._ymetadata] = self._ymetadata.observe_deep(
            partial(callback, "meta")
        )
