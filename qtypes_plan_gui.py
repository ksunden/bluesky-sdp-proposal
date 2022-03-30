import ast
import sys

from ophyd import sim
import bluesky
from bluesky import protocols
from bluesky.plan_serialize import serialize_plan
from bluesky.plans import count, grid_scan

import qtypes
from qtpy import QtWidgets

def many_different_params(i: int, f: float, b: bool, s: str, r: protocols.Readable, m: protocols.Movable, fl: protocols.Flyable):
    yield bluesky.Msg("null")


plans = [count, grid_scan, many_different_params]

ser = {x.__name__: serialize_plan(x) for x in plans}

readables = {k: v for k, v in sim.__dict__.items() if isinstance(v, protocols.Readable) and not isinstance(v, type)}
movables = {k: v for k, v in sim.__dict__.items() if isinstance(v, protocols.Movable) and not isinstance(v, type)}
flyables = {k: v for k, v in sim.__dict__.items() if isinstance(v, protocols.Flyable) and not isinstance(v, type)}


class Sequence(qtypes.Null):
    def __init__(self, name, type_):
        super().__init__(name)
        self.type_ = type_
        self.add = qtypes.Button("add")
        self.add.updated.connect(self.on_add)
        self.remove = qtypes.Button("remove")
        self.remove.updated.connect(self.on_remove)
        self.append(self.add)
        self.append(self.remove)
    
    def on_add(self):
        self.insert(get_qtypes_widget(self.type_, "item"), -2)

    def on_remove(self):
        self.removeChild(-2)

# TODO: default values
# TODO: Union (including Optional)
# TODO: Sequences (including list)
# TODO: Tuples (Named Tuples)
# TODO: Mappings (Dict)
def get_parameter_widget(parameter):
    if "annotation" not in parameter or "type" not in parameter["annotation"]:
        print(f"No annotation for {parameter['name']}")
        return qtypes.Null(parameter["name"])
    return get_qtypes_widget(parameter["annotation"]["type"], parameter["name"])

def get_qtypes_widget(type_, name):
    expr = ast.parse(type_).body[0].value
    if isinstance(expr, ast.Name):
        if expr.id == "int":
            return qtypes.Integer(name)
        if expr.id == "float":
            return qtypes.Float(name)
        if expr.id == "bool":
            return qtypes.Bool(name)
        if expr.id == "str":
            return qtypes.String(name)
    elif isinstance(expr, ast.Attribute):
        if ast.unparse(expr) == "bluesky.protocols.Readable":
            return qtypes.Enum(name, value={"allowed": list(readables.keys())})
        if ast.unparse(expr) == "bluesky.protocols.Movable":
            return qtypes.Enum(name, value={"allowed": list(movables.keys())})
        if ast.unparse(expr) == "bluesky.protocols.Flyable":
            return qtypes.Enum(name, value={"allowed": list(flyables.keys())})
    elif isinstance(expr, ast.Subscript):
        class_ = ast.unparse(expr.value)
        params = expr.slice
        if class_ in ("typing.Sequence", "typing.List", "list"):
            return Sequence(name, ast.unparse(params))
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

    def on_plan_updated(self, plan):
        self.plan_sel.takeChildren()
        for parm in ser[plan["value"]]["parameters"]:
            self.plan_sel.append(get_parameter_widget(parm))

def main():
    app = QtWidgets.QApplication(sys.argv)
    widget = PlanWindow()
    widget.show()
    app.exec_()

if __name__ == "__main__":
    main()
