"""RegressionGuard: avaliacao e deteccao de regressoes para sistemas com LLMs.

API publica estavel (versionamento semantico; usada pelo PromptOps):
  - `compare(baseline, candidate, gates)`: comparacao emparelhada e gates;
  - `GatesConfig`, `GateSpec`, `load_gates`: gates versionados;
  - `register`, `EvalContext`, `EvalResult`, `get_evaluator`, `evaluator_names`:
    registo de avaliadores;
  - `load_dataset`, `Dataset`, `Case`, `DatasetError`: datasets golden;
  - `RunRecord`, `ComparisonReport`, `ComparisonError`: modelos de resultado.
"""

from regressionguard.comparison.engine import ComparisonError, ComparisonReport, compare
from regressionguard.comparison.gates import GatesConfig, GateSpec, load_gates
from regressionguard.datasets import Case, Dataset, DatasetError, load_dataset
from regressionguard.evaluators import names as evaluator_names
from regressionguard.evaluators.registry import (
    EvalContext,
    EvalResult,
    register,
)
from regressionguard.evaluators.registry import (
    get as get_evaluator,
)
from regressionguard.runner.records import RunRecord

__version__ = "0.1.0"

__all__ = [
    "Case",
    "ComparisonError",
    "ComparisonReport",
    "Dataset",
    "DatasetError",
    "EvalContext",
    "EvalResult",
    "GateSpec",
    "GatesConfig",
    "RunRecord",
    "__version__",
    "compare",
    "evaluator_names",
    "get_evaluator",
    "load_dataset",
    "load_gates",
    "register",
]
