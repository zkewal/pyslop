import glob
import json
from importlib.metadata import version
from pathlib import Path

import pytest

from pyslop.cli import main


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out == f"pyslop {version('pyslop')}\n"


def test_self_check_on_src_and_tests_is_clean(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Fixture files carry intentional violations, so the gate checks src and
    # the test modules by path. A root [tool.pyslop] exclude cannot do this:
    # excludes resolve per finding file, so they would also silence the
    # CLI-seam tests that assert on those same fixtures.
    root = Path(__file__).parent.parent
    paths = [str(root / "src"), *sorted(glob.glob(str(root / "tests" / "test_*.py")))]
    code = main(["check", *paths, "--format", "json"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 0
    assert findings == []


@pytest.mark.parametrize("doc", ["README.md", "skills/install-pyslop/SKILL.md"])
def test_install_docs_pin_current_release(doc: str) -> None:
    # Bump pyproject's version and these copy-paste install lines together.
    root = Path(__file__).parent.parent
    assert f"pyslop@v{version('pyslop')} " in (root / doc).read_text()
