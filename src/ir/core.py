from typing import Optional, Union, List, Tuple
import numpy as np
from ir.lang import Prog, Expr, Opc, Operand
from cgraph.cgraph import CGraph
from ir.fn_library import rnn_lib
from prnn.reservoir import Reservoir

class Core:
    """
    Implements the core of the reservoir language compiler, compiling IR expressions -> NetworkX graph.
    """

    uid = 0

    def __init__(self, prog: Prog, verbose=False):
        self.graph = CGraph()
        self.vars = set()  # set of declared symbols
        self.inps = set()
        self.prog = prog
        self.verbose = verbose  # Set this to True to enable debug prints

    def compile_to_cgraph(self) -> CGraph:
        if self.verbose:
            print("Starting compilation of program:")
            print(self.prog)

        for expr in self.prog.exprs:
            if self.verbose:
                print(f"Processing expression: {expr}")
            self._process_expr(expr)

        return self.graph

    def _process_expr(self, expr: Expr) -> Union[None, Reservoir]:
        if self.verbose:
            print(f"Processing opcode: {expr.op}")
        match expr.op:
            case Opc.LET:
                return self._handle_let(expr.operands)
            case Opc.INPUT:
                return self._handle_input(expr.operands[0])
            case Opc.RET:
                return self._handle_ret(expr.operands[0])
            case _:
                return self._handle_custom_opcode(expr)

    def _handle_let(self, operands: List[Operand]) -> None:
        if len(operands) == 1:
            for name in operands[0]:
                self.graph.add_var(name)
            return

        names, value = operands
        if self.verbose:
            print(f"LET expression with variables {names} and value {value}")
        # Strictest version, assume process_operand always returns a reservoir
        res: Reservoir = self._process_expr(value)
        if self.verbose:
            print(f"Processed LET value, resulting in reservoir: {res.name}")

        for i, name in enumerate(names):
            if self.verbose:
                print(
                    f"Binding variable {name} to reservoir output {res.name}, index {i}"
                )
            self.graph.add_var(name)
            self.graph.add_edge(res.name, name, out_idx=i)

    def _handle_input(self, operand: Operand) -> None:
        if self.verbose:
            print(f"Handling INPUT operand: {operand}")

        for name in operand:
            self.inps.add(name)
            self.graph.add_input(name)
            if self.verbose:
                print(f"Declared input variable: {name}")

    def _handle_ret(self, operand: Operand) -> None:
        if self.verbose:
            print(f"Handling INPUT operand: {operand}")
        for name in operand:
            self.graph.make_return(name)
            if self.verbose:
                print(f"Converted to return variable: {name}")

    def _handle_custom_opcode(self, expr: Expr) -> Reservoir:
        opcode = expr.op
        assert isinstance(opcode, str), "Custom opcode must be a string"
        assert opcode in rnn_lib, f"Opcode {opcode} not found in library"

        inp_dim, out_dim, res_path = rnn_lib[opcode]
        if self.verbose:
            print(
                f"Handling custom opcode: {opcode}, expected input dim: {inp_dim}, output dim: {out_dim}"
            )

        res = Reservoir.load(res_path).copy()
        res.name = self._generate_uid()
        self.graph.add_reservoir(res.name, reservoir=res)

        if self.verbose:
            print(f"Loaded reservoir from path {res_path}, assigned name {res.name}")

        # Check operands
        operands = expr.operands
        for i, sym in enumerate(operands):
            if self.verbose:
                print(f"Processing operand {i}: {sym}")
            if (sym not in self.inps) and (sym not in self.vars):
                ValueError(f"Used undefined symbol {sym}")
            self.graph.add_edge(sym, res.name, in_idx=i)
            if self.verbose:
                print(
                    f"Connected operand {sym} to reservoir {res.name} at input index {i}"
                )
        return res

    def _generate_uid(self) -> str:
        """
        Generates a unique ID for reservoirs.
        """
        Core.uid += 1
        uid = f"res_{Core.uid}"
        if self.verbose:
            print(f"Generated unique reservoir ID: {uid}")
        return uid