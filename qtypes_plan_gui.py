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


# TODO: default values
# TODO: Union (including Optional)
# TODO: Sequences (including list)
# TODO: Tuples (Named Tuples)
# TODO: Mappings (Dict)
# TODO: Protocol types: Movable, Readable, Flyable
def get_qtypes_widget(parameter):
    if "annotation" not in parameter or "type" not in parameter["annotation"]:
        print(f"No annotation for {parameter['name']}")
        return qtypes.Null(parameter["name"])
    if parameter["annotation"]["type"] == "int":
        return qtypes.Integer(parameter["name"])
    if parameter["annotation"]["type"] == "float":
        return qtypes.Float(parameter["name"])
    if parameter["annotation"]["type"] == "bool":
        return qtypes.Bool(parameter["name"])
    if parameter["annotation"]["type"] == "str":
        return qtypes.String(parameter["name"])
    print(f"{parameter['annotation']['type']} not yet handled")

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
            self.plan_sel.append(get_qtypes_widget(parm))

def main():
    app = QtWidgets.QApplication(sys.argv)
    widget = PlanWindow()
    widget.show()
    app.exec_()

if __name__ == "__main__":
    main()
