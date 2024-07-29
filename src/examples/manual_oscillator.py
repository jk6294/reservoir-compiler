# add reservoir.py to import path
import sys
import os
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

from reservoir import *
from prnn_method import circuit, prnn_method
from utils import inputs, plotters

# define symbolic equations (naming is not constrained) -----------------
nand_res = Reservoir.loadFile("nand")

# Manual circuit: Oscillator
n = 30
A = nand_res.A
B = nand_res.B
W = nand_res.W

O = np.zeros((n, n))
OB = np.zeros((n, 1))
b1 = B[:, 0]
b2 = B[:, 1]

# Construct circuit
AC = np.block([
    [A,                  O,                  np.outer(b1+b2, W)],
    [np.outer(b1+b2, W), A,                  O],
    [O,                  np.outer(b1+b2, W), A]
])

BC = np.tile(OB, (3, 1))


RAD = Reservoir(AC, 
                BC, 
                np.tile(nand_res.r_init, (3, 1)), 
                0, 
                nand_res.global_timescale, 
                nand_res.gamma, 
                np.tile(nand_res.d, (3, 1)), 
                None)
W = nand_res.W

# Run for no input.
time = 7000
input_data = np.zeros((1, time, 4))
radp = RAD.run4input(input_data, np.identity(3*n))

# Find o=Wr
outputs = np.vstack([
    W @ radp[0:30, :],  # first nand
    W @ radp[30:60, :],  # second nand
    W @ radp[60:90, :]   # third nand
])

# plot using 'outputs' to see all three signals
exposed_output = outputs[2, :].reshape(1, -1)
print(exposed_output.shape)

plotters.InOutSplit(input_data, exposed_output, "Oscillator")