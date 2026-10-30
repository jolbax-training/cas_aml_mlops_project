"""The candidate image is pinned by digest per host architecture."""


import pytest

from codegen_eval import sandbox


@pytest.mark.parametrize("machine, digest", [
    ("arm64", "950206c37262"), ("aarch64", "950206c37262"),
    ("x86_64", "44ff437bba87"), ("AMD64", "44ff437bba87"),
])
def test_image_is_pinned_per_architecture_by_digest(machine, digest):
    image = sandbox._select_image(machine)
    assert image.startswith("docker.io/library/python@sha256:") and digest in image


def test_unsupported_architecture_is_refused():
    with pytest.raises(RuntimeError, match="no pinned candidate image"):
        sandbox._select_image("riscv64")


def test_module_image_matches_the_host():
    assert sandbox.IMAGE == sandbox._select_image(sandbox.platform.machine())
