import os
import pickle as pkl
import numpy as np
import sympy as sp
import matlab.engine

"""
Reservoir Structure:
    * n = latent dim
    * k = input dim
    * m = output dim
* r: n x 1
* x: k x 1
* d: n x 1
* A: n x n
* B: n x k
* W: m x n
"""


class Reservoir:
    """
    Core
    """

    def __init__(
        self,
        A,
        B,
        r_init,
        x_init,
        global_timescale=0.1,
        gamma=100,
        d=None,
        W=None,
        name=None,
        input_names=[],
        output_names=[],
        r=None,
    ):
        self.name: str = name
        self.input_names: list[str] = input_names
        self.output_names: list[str] = output_names

        self.A: np.ndarray = A
        self.B: np.ndarray = B
        self.r_init: np.ndarray = (
            r_init if r_init is not None else np.zeros((A.shape[0], 1))
        )
        #TODO: not specifying r doesn't work (symmetry?)
        self.r: np.ndarray = r if r is not None else np.zeros((A.shape[0], 1))

        assert isinstance(x_init, np.ndarray), "x_init must be an array"
        self.x_init: np.ndarray = x_init.reshape(-1, 1)
        self.global_timescale: float = global_timescale
        self.gamma: float = gamma

        """ 
         o = i1 and True ... takes and 'and' res and tweaks its d and removes an input from x/B. in __init__, pass e, d = calc_d() + e
         #TODO: setting d directly will break things
         self.e, self._d  = calcd() + self.e
         self.update_d(e), or on self.e update
          
        """

        self.d = (
            d
            if d is not None
            else (
                np.arctanh(self.r_init)
                - (self.A @ self.r_init)
                - (self.B @ self.x_init)
                if r_init is not None
                else np.zeros((A.shape[0], 1))
            )
        )

        self.W: np.ndarray = W

        # for circuitry
        self.usedInputs = set()
        self.usedOutputs = set()

    def copy(self):
        # Ensure that usedOutputs and usedInputs are copied as sets
        copied_res = Reservoir(
            self.A,
            self.B,
            self.r_init,
            self.x_init,
            self.global_timescale,
            self.gamma,
            self.d,
            self.W,
        )
        copied_res.usedOutputs = set(self.usedOutputs)  # Properly copy the set
        copied_res.usedInputs = set(self.usedInputs)  # Properly copy the set
        return copied_res

    """
    Solver Tools
    """

    @staticmethod
    def gen_baseRNN(latent_dim, input_dim, global_timescale=0.001, gamma=100):
        np.random.seed(0)
        A = np.zeros((latent_dim, latent_dim))  # Adjacency matrix
        B = (np.random.rand(latent_dim, input_dim) - 0.5) * 0.05  # Input weight matrix
        r_init = np.random.rand(latent_dim, 1) - 0.5
        x_init = np.zeros((input_dim, 1))
        return Reservoir(A, B, r_init, x_init, global_timescale, gamma)

    @staticmethod
    def solve(sym_eqs, verbose=False) -> "Reservoir":
        """
        Solves a system of equations using a baseRNN (Reservoir) of the correct size,
        solves via call to Jason's code via MatLab Engine.

        Args:
            sym_eqs (list): A list of symbolic equations representing the system to solve.

        Returns:
            Reservoir: Reservoir solved for symeqs.

        """

        # determine number of baseRNN inputs -- init latents at 10x inputs
        x = set()
        for eq in sym_eqs:
            for symbol in eq.rhs.free_symbols:
                x.add(symbol)
        num_x = len(x)

        # TODO: determine correct number of latents (currently using 10x input space)
        baseRNN = Reservoir.gen_baseRNN(num_x * 10, num_x)

        print("Solving for reservoir. This may take a moment!")

        # start and configure matlab engine
        eng = matlab.engine.start_matlab()
        if verbose:
            print("* matlab engine started")
        path = r"src/_prnn/matlab_dependencies"
        eng.addpath(path, nargout=0)
        eng.cd(path, nargout=0)
        if verbose:
            print("* added scripts to matlab path")

        # convert to matlab format, run
        A, B, r_init, x_init, global_timescale, gamma = baseRNN.py2mat()
        matlab_eqs = [sp.octave_code(eq) for eq in sym_eqs]
        A, B, r_init, x_init, d, O, R = eng.runMethod(
            A,
            B,
            r_init,
            x_init,
            global_timescale,
            gamma,
            matlab_eqs,
            verbose,
            nargout=7,
        )  # add nargout=0 if ignoring output

        eng.quit()

        # solve for W
        O = np.array(O, dtype=float)
        R = np.array(R, dtype=float)
        W, _, _, _ = np.linalg.lstsq(R.T, O.T)
        W = W.T

        return Reservoir.mat2py(
            A, B, r_init, x_init, baseRNN.global_timescale, baseRNN.gamma, d, W
        )

    """
    Engine: run a network forward
    """

    def del_r(self, r: np.ndarray, x: np.ndarray) -> np.ndarray:
        # Ensure r and x are column vectors
        r = r.reshape(-1, 1)
        x = x.reshape(-1, 1)
        dr = self.gamma * (-r + np.tanh(self.A @ r + self.B @ x + self.d))
        return dr

    def propagate(self, x: np.ndarray):
        # x is expected to be a 3D array with shape (n, 1, 4)
        x = x.reshape(-1, 1, 4)  # Ensure x is in the correct shape

        k1 = self.global_timescale * self.del_r(self.r, x[:, 0, 0].reshape(-1, 1))
        k2 = self.global_timescale * self.del_r(
            self.r + k1 / 2, x[:, 0, 1].reshape(-1, 1)
        )
        k3 = self.global_timescale * self.del_r(
            self.r + k2 / 2, x[:, 0, 2].reshape(-1, 1)
        )
        k4 = self.global_timescale * self.del_r(self.r + k3, x[:, 0, 3].reshape(-1, 1))

        self.r = self.r + (k1 + (2 * k2) + 2 * (k3 + k4)) / 6
        return self.r

    def run(
        self,
        inputs: np.ndarray = None,
        time=None,
        W=None,
        verbose=False,
        ret_states=False,
    ):
        # user specified W case
        W = W if W is not None else self.W
        assert (
            W is not None
        ), "error: run: W must be defined, either by argument or in reservoir object"

        # void input case
        if inputs is None:
            assert (
                time is not None
            ), "error: run: if reservoir has no inputs, run requires 'time' argument"
            assert np.all(
                self.B == 0
            ), "error: in void input case, B must be a vector or matrix of zeros"
            assert (
                np.sum(self.x_init == 0) == 1
            ), "error: input void input case, x must contain exactly one zero"
            inputs = np.zeros((1, time))
        # ensure input dim matches res
        else:
            assert (
                inputs.shape[0] == self.x_init.shape[0]
            ), f"input dimension mismatch: passed {inputs.shape[0]} but expected {self.x_init.shape[0]}"

        # Ensure 4 dim inputs on z axis
        inputs = inputs.reshape(inputs.shape[0], inputs.shape[1], 1)
        inputs = np.repeat(inputs, 4, axis=2)

        nInd = 0
        nx = inputs.shape[1]
        states = np.zeros((self.A.shape[0], nx))
        states[:, 0] = self.r.flatten()

        if verbose:
            print("." * 100)

        for i in range(1, nx):
            if i > nInd * nx:
                nInd += 0.01
                if verbose:
                    print("+", end="")
            self.propagate(inputs[:, i - 1, :])
            states[:, i] = self.r.flatten()

        return W @ states if not ret_states else states

    """  
    Rsvr Files: pickles a reservoir and saves it to the src/presets dir
    """

    def save(self, filename, directory="src/_std/presets"):

        # check dir exists
        if not os.path.exists(directory):
            raise FileNotFoundError(
                f"The directory '{directory}' does not exist. Please create the directory or navigate to the root 'compiler' directory."
            )

        os.makedirs(directory, exist_ok=True)

        # save object to res file
        filepath = os.path.join(directory, f"{filename}.rsvr")
        with open(filepath, "wb") as f:
            pkl.dump(self, f)

        if os.path.isfile(filepath):
            print("save: created", filepath)
        else:
            raise FileNotFoundError("error: save: dumped file, then couldn't find it")

    @classmethod
    def load(cls, filename, directory="src/_std/presets") -> "Reservoir":
        filepath = os.path.join(directory, f"{filename}.rsvr")

        # check dir exists
        if not os.path.exists(directory):
            raise FileNotFoundError(
                f"The directory '{directory}' does not exist. Please ensure the correct directory structure is in place."
            )

        # find file
        if not os.path.isfile(filepath):
            raise FileNotFoundError(
                f"The file '{filepath}' does not exist. Please check the filename or ensure the file has been created in the 'src/presets' directory."
            )

        # load reservoir
        with open(filepath, "rb") as f:
            obj = pkl.load(f)
        return obj

    """
    Dev Utils
    """

    def print(self, precision=2):
        print("--------------------")
        print("Reservoir Parameters")
        print("A:\n", np.round(self.A, precision))
        print("B:\n", np.round(self.B, precision))
        print("r_init:\n", np.round(self.r_init, precision))
        print("x_init:\n", np.round(self.x_init, precision))
        print("d:\n", np.round(self.d, precision))
        print("r:\n", np.round(self.r, precision))
        print("global_timescale: ", np.round(self.global_timescale, precision))
        print("1/gamma: ", np.round(1 / self.gamma, precision))
        if self.W is not None:
            print("W:\n", np.round(self.W, precision))
        print("--------------------")

    def printDims(self):
        print("A: ", self.A.shape)
        print("B: ", self.B.shape)
        print("r_init: ", self.r_init.shape)
        print("x_init: ", self.x_init.shape)
        print("d: ", self.d.shape)
        print("r: ", self.r.shape)
        print("global_timescale: ", self.global_timescale)
        print("gamma: ", self.gamma)
        if self.W is not None:
            print("W: ", self.W.shape)

    def py2mat(self):
        # save reservoir to matlab readable format
        A = matlab.double(self.A.tolist())
        B = matlab.double(self.B.tolist())
        r_init = matlab.double(self.r_init.tolist())
        x_init = matlab.double(self.x_init.tolist())
        global_timescale = matlab.double([self.global_timescale])
        gamma = matlab.double([self.gamma])
        return A, B, r_init, x_init, global_timescale, gamma

    @staticmethod
    def mat2py(
        A, B, r_init, x_init, global_timescale, gamma, d=None, W=None
    ) -> "Reservoir":
        A = np.array(A, dtype=float)
        B = np.array(B, dtype=float)
        d = np.array(d, dtype=float) if d is not None else None
        r_init = np.array(r_init, dtype=float)
        x_init = np.array(x_init, dtype=float)
        global_timescale = float(global_timescale)
        gamma = float(gamma)
        W = np.array(W, dtype=float) if W is not None else None
        return Reservoir(A, B, r_init, x_init, global_timescale, gamma, d, W)

    def doubleOutput(self, output_idx):
        if output_idx <= 0 and output_idx > self.W.shape[0]:
            return ValueError(f"invalid output; cannot double")
        self.W = np.vstack((self.W, self.W[output_idx, :]))
        return self
