import pytest

from qfit.solvers import *


class TestForcedNoSolvers:
    import qfit.solvers

    # Manually set CPLEX, OSQP to False
    qfit.solvers.CPLEX = False
    qfit.solvers.OSQP = False

    # QPSolver.__new__ should raise ImportError
    # since both CPLEX, OSQP flags are false
    def test_QPSolvers_fail(self):
        with pytest.raises(ImportError):
            QPSolver(None, None, use_cplex=False)
        with pytest.raises(ImportError):
            QPSolver(None, None, use_cplex=True)

    # MIQPSolver.__new__ should raise ImportError
    # since both CPLEX, OSQP flags are false
    def test_MIQPSolvers_fail(self):
        with pytest.raises(ImportError):
            MIQPSolver(None, None, use_cplex=False)
        with pytest.raises(ImportError):
            MIQPSolver(None, None, use_cplex=True)
