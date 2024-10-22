import numpy as np
from pyres import compile
from _utils.plotters import plt_outputs
from _utils.inputs import high_low_inputs, high_low_inputs_3rows

res = compile("examples/frontend/src_code/ex1.pyres", verbose=False)
# res.print()

if 1:
    # inp = high_low_inputs(4000)[0, :].reshape(1, -1)
    # print(inp)
    # inp = high_low_inputs(4000)
    outputs = res.run(time=4000)
    plt_outputs(outputs, "", res.output_names)