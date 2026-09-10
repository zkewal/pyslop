import json

import pytest

from pyslop.cli import main


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "pyslop" in capsys.readouterr().out


def test_self_check_on_src_and_tests_is_clean(capsys):
    code = main(["check", "src", "tests", "--format", "json"])
    findings = json.loads(capsys.readouterr().out)
    assert code == 0
    assert findings == []
