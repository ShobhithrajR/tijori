"""CLI proof tests: ``python -m privacy`` end-to-end on the PS-02 sample."""

from __future__ import annotations

from privacy import __main__ as cli


def test_cli_main_returns_zero() -> None:
    assert cli.main() == 0
