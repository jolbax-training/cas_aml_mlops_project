import json

import pytest

from codegen_eval.sandbox import ExecutionResult


@pytest.fixture
def inprocess_runner():
    """Trusted stand-in for execute_check that runs source in this process. Test-only:
    it mirrors the status vocabulary of the container path without Podman."""

    def runner(source, function_name, args, limits=None):
        namespace: dict = {}
        exec(compile(source, "<candidate>", "exec"), namespace)
        copied = json.loads(json.dumps(list(args)))
        try:
            value = namespace[function_name](*copied)
        except Exception as error:  # noqa: BLE001 - candidate code may raise anything
            return ExecutionResult("exception", detail=type(error).__name__)
        return ExecutionResult("returned", value=value, args_after=copied)

    return runner
