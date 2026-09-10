import glob
import json

import pytest

from pyslop.cli import main


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "pyslop" in capsys.readouterr().out


def test_self_check_on_src_and_tests_is_clean(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Fixture files carry intentional violations, so the gate checks src and
    # the test modules by path. A root [tool.pyslop] exclude cannot do this:
    # excludes resolve per finding file, so they would also silence the
    # CLI-seam tests that assert on those same fixtures.
    paths = ["src", *sorted(glob.glob("tests/test_*.py"))]
    code = main(["check", *paths, "--format", "json"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 0
    assert findings == []
