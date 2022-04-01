import ast
import enum
import json
from pprint import pprint
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

def many_different_params(r: protocols.Readable, m: protocols.Movable, fl: protocols.Flyable, i: int=10, f: float=3.14, b: bool=True, s: str="a string", e: RGB=RGB.BLUE):
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
        self.add = qtypes.Button("", value={"text": "add"})
        self.add.updated.connect(self.on_add)
        self.remove = qtypes.Button("", value={"text": "remove"})
        self.remove.updated.connect(self.on_remove)
        self.append(self.add)
        self.append(self.remove)
    
    def on_add(self):
        get_qtypes_widget(self.type_, self.type_, self, self.named_types, -2)

    def on_remove(self):
        try:
            self.removeChild(self.children.pop(-3))
        except IndexError:
            pass  # Nothing to remove

    def get_value(self):
        return [k.get_value() for k in self.children if not isinstance(k, qtypes.Button)]

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
        self.add = qtypes.Button("", value={"text": "add"})
        self.add.updated.connect(self.on_add)
        self.remove = qtypes.Button("", value={"text": "remove"})
        self.remove.updated.connect(self.on_remove)
        self.append(self.add)
        self.append(self.remove)
    
    def on_add(self):
        item = get_qtypes_widget(self.key_type, "key", self, self.named_types, -2)
        get_qtypes_widget(self.value_type, "value", item, self.named_types)

    def on_remove(self):
        try:
            self.removeChild(self.children.pop(-3))
        except IndexError:
            pass  # Nothing to remove

    def get_value(self):
        return {k.get_value(): k.children[0].get_value() for k in self.children if not isinstance(k, qtypes.Button)}


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

    def set_value(self, value):
        for ty in self.type_enum.get()["allowed"]:
            self.type_enum.set_value(ty)
            if value is None and ty in ("None", "NoneType"):
                break
            try:
                self.children[-1].set_value(value)
            except:
                pass
            break
        else:
            print(f"Could not set union value, {value}, for {self.type_enum.get()['allowed']}")

    def get_value(self):
        if self.type_enum.get_value() in ("None", "NoneType"):
            return None
        return self.children[-1].get_value()


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

    def get_value(self):
        return tuple(i.get_value() for i in self.children)


class AnyJson(qtypes.String):
    def __init__(self, name):
        super().__init__(name)
        self.edited.connect(self.validate)

    def validate(self, value):
        try:
            json.loads(value["value"])
        except json.JSONDecodeError:
            escaped = value["value"].replace("\\", "\\\\").replace('"', '\\"')
            self.set({"value": f"\"{escaped}\""})



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
            ret = AnyJson(name)
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
        self.gen_output_button = qtypes.Button("", value={"text": "Generate"})
        self.tw.append(self.gen_output_button)
        self.gen_output_button.updated.connect(self.gen_output)

    def on_plan_updated(self, plan):
        print()
        pprint(ser[plan["value"]])
        self.plan_sel.takeChildren()
        self.plan_sel.children = []
        for parm in ser[plan["value"]]["parameters"]:
            widget = get_parameter_widget(parm, self.plan_sel, ser[plan["value"]]["named_types"])
            if widget and "default" in parm:
                widget.set_value(parm["default"])
            if widget is None:
                print(parm, "No widget")

        self.plan_sel.setExpanded(True)

    def gen_output(self):
        print()
        plan = self.plan_sel.get_value()
        args = []
        kwargs = {}
        kw_only = False
        for parm in ser[plan]["parameters"]:
            parm_name = parm["name"]
            try:
                value = self.get_value(parm_name)
            except ValueError as e:
                kw_only = True
                if "default" not in parm and not parm["kind"]["name"].startswith("VAR"):
                    print(str(a), " and it is required")
                continue
            if parm["kind"]["name"] == "POSITIONAL_ONLY":
                args.append(value)
            elif parm["kind"]["name"] == "POSITIONAL_OR_KEYWORD":
                if kw_only:
                    kwargs[parm_name] = value
                else:
                    args.append(value)
            elif parm["kind"]["name"] == "VAR_POSITIONAL":
                args.extend(value)
            elif parm["kind"]["name"] == "KEYWORD_ONLY":
                kwargs[parm_name] = value
        out = {"name": plan, "args": args, "kwargs": kwargs}
        print(json.dumps(out, indent=2))
        return out
    
    def get_value(self, name):
        for i in self.plan_sel.children:
            if i.label == name:
                return i.get_value()
        raise ValueError(f"No value for {name}")


def main():
    app = QtWidgets.QApplication(sys.argv)
    widget = PlanWindow()
    widget.show()
    app.exec_()

if __name__ == "__main__":
    main()
