import ast
import enum
import sys

from ophyd import sim
import bluesky
from bluesky import protocols
from bluesky.plan_serialize import serialize_plan
from bluesky.plans import count, grid_scan

import qtypes
from qtpy import QtWidgets


class RGB(enum.Enum):
    RED=1
    GREEN=2
    BLUE=3

def many_different_params(i: int, f: float, b: bool, s: str, r: protocols.Readable, m: protocols.Movable, fl: protocols.Flyable, e: RGB):
    yield bluesky.Msg("null")


plans = [many_different_params, count, grid_scan]

ser = {x.__name__: serialize_plan(x) for x in plans}

readables = {k: v for k, v in sim.__dict__.items() if isinstance(v, protocols.Readable) and not isinstance(v, type)}
movables = {k: v for k, v in sim.__dict__.items() if isinstance(v, protocols.Movable) and not isinstance(v, type)}
flyables = {k: v for k, v in sim.__dict__.items() if isinstance(v, protocols.Flyable) and not isinstance(v, type)}


class Sequence(qtypes.Null):
    def __init__(self, name, type_, parent, named_types, at=None):
        super().__init__(name)
        if at is None:
            parent.append(self)
        else:
            parent.insert(at, self)
        self.named_types = named_types
        self.type_ = type_
        self.add = qtypes.Button("add")
        self.add.updated.connect(self.on_add)
        self.remove = qtypes.Button("remove")
        self.remove.updated.connect(self.on_remove)
        self.append(self.add)
        self.append(self.remove)
    
    def on_add(self):
        get_qtypes_widget(self.type_, "item", self, self.named_types, -2)

    def on_remove(self):
        try:
            self.removeChild(self.children.pop(-3))
        except IndexError:
            pass  # Nothing to remove

class Mapping(qtypes.Null):
    def __init__(self, name, key_type, value_type, parent, named_types, at=None):
        super().__init__(name)
        if at is None:
            parent.append(self)
        else:
            parent.insert(at, self)
        self.named_types = named_types
        self.key_type = key_type
        self.value_type = value_type
        self.add = qtypes.Button("add")
        self.add.updated.connect(self.on_add)
        self.remove = qtypes.Button("remove")
        self.remove.updated.connect(self.on_remove)
        self.append(self.add)
        self.append(self.remove)
    
    def on_add(self):
        item = qtypes.Null("item")
        self.insert(-2, item)
        get_qtypes_widget(self.key_type, "key", item, self.named_types)
        get_qtypes_widget(self.value_type, "value", item, self.named_types)

    def on_remove(self):
        try:
            self.removeChild(self.children.pop(-3))
        except IndexError:
            pass  # Nothing to remove


class Union(qtypes.Null):
    def __init__(self, name, type_options, parent, named_types, at=None):
        super().__init__(name)
        if at is None:
            parent.append(self)
        else:
            parent.insert(at, self)
        self.named_types = named_types
        self.type_enum = qtypes.Enum("type", value={"allowed": type_options})
        self.type_enum.updated.connect(self.on_type_updated)
        self.append(self.type_enum)
        self.type_enum.updated.emit(self.type_enum.get())

    
    def on_type_updated(self, value):
        self.takeChild(1)
        if value["value"] not in ("None", "NoneType"):
            get_qtypes_widget(value["value"], "value", self, self.named_types)


class NamedTuple(qtypes.Null):
    def __init__(self, name, type_map, parent, named_types, at=None):
        super().__init__(name)
        if at is None:
            parent.append(self)
        else:
            parent.insert(at, self)
        self.named_types = named_types
        for k, v in type_map.items():
            get_qtypes_widget(v, k, self, self.named_types)




# TODO: default values
# TODO: Tuples (Named Tuples)
def get_parameter_widget(parameter, parent, named_types):
    if "annotation" not in parameter or "type" not in parameter["annotation"]:
        print(f"No annotation for {parameter['name']}")
        ret = qtypes.Null(parameter["name"])
        parent.append(ret)
        return ret
    if parameter["kind"]["name"] == "VAR_POSITIONAL":
        return Sequence(parameter["name"], parameter["annotation"]["type"], parent, named_types)
    return get_qtypes_widget(parameter["annotation"]["type"], parameter["name"], parent, named_types)

def get_qtypes_widget(type_, name, parent, named_types, at=None):
    expr = ast.parse(type_).body[0].value
    if isinstance(expr, ast.Name):
        ret = None
        if expr.id == "int":
            ret = qtypes.Integer(name)
        elif expr.id == "float":
            ret = qtypes.Float(name)
        elif expr.id == "bool":
            ret = qtypes.Bool(name)
        elif expr.id == "str":
            ret = qtypes.String(name)
        elif expr.id in named_types and isinstance(named_types[expr.id], list):
            ret = qtypes.Enum(name, value={"allowed": named_types[expr.id]})
        elif expr.id in named_types and isinstance(named_types[expr.id], dict):
            ret = NamedTuple(name, named_types[expr.id], parent, named_types, at)
        if ret is not None:
            if at is None:
                parent.append(ret)
            else:
                parent.insert(at, ret)
            return ret
    elif isinstance(expr, ast.Attribute):
        ret = None
        if ast.unparse(expr) == "bluesky.protocols.Readable":
            ret = qtypes.Enum(name, value={"allowed": list(readables.keys())})
        elif ast.unparse(expr) == "bluesky.protocols.Movable":
            ret = qtypes.Enum(name, value={"allowed": list(movables.keys())})
        elif ast.unparse(expr) == "bluesky.protocols.Flyable":
            ret = qtypes.Enum(name, value={"allowed": list(flyables.keys())})
        elif ast.unparse(expr) == "typing.Any":
            ret = qtypes.String(name)
        if ret is not None:
            if at is None:
                parent.append(ret)
            else:
                parent.insert(at, ret)
            return ret
    elif isinstance(expr, ast.Subscript):
        class_ = ast.unparse(expr.value)
        params = expr.slice
        if class_ in ("typing.Sequence", "typing.List", "typing.Iterable", "list"):
            return Sequence(name, ast.unparse(params), parent, named_types, at)
        elif class_ in ("typing.Mapping", "typing.Dict", "dict"):
            kt, vt = params.elts
            return Mapping(name, ast.unparse(kt), ast.unparse(vt), parent, named_types, at)
        elif class_ == "typing.Optional":
            if isinstance(params, ast.Name):
                return Union(name, ["None", ast.unparse(params)], parent, named_types, at)
            return Union(name, ["None", ast.unparse(params)], parent, named_types, at)
        elif class_ == "typing.Union":
            if not isinstance(params, ast.Tuple):
                # Only one option in union, don't bother with type selector enum
                return get_qtypes_item(ast.unparse(params), name, parent, named_types, at)
            return Union(name, [ast.unparse(x) for x in params.elts], parent, named_types, at)

    print(f"{type_} not yet handled")

class PlanWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plan widget")
        self.tw = qtypes.TreeWidget()
        self.setCentralWidget(self.tw)
        self.plan_sel = qtypes.Enum("Plan", value={"allowed": list(ser.keys())})
        self.plan_sel.updated.connect(self.on_plan_updated)

        self.tw.append(self.plan_sel)
        self.plan_sel.updated.emit(self.plan_sel.get())

    def on_plan_updated(self, plan):
        print()
        from pprint import pprint
        pprint(ser[plan["value"]])
        self.plan_sel.takeChildren()
        for parm in ser[plan["value"]]["parameters"]:
            get_parameter_widget(parm, self.plan_sel, ser[plan["value"]]["named_types"])
        self.plan_sel.setExpanded(True)

def main():
    app = QtWidgets.QApplication(sys.argv)
    widget = PlanWindow()
    widget.show()
    app.exec_()

if __name__ == "__main__":
    main()
