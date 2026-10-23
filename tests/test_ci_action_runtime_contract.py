"""Guard against reintroducing deprecated Node.js 20 GitHub Actions in active CI gates."""
from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("workflow", ["pr_tests.yml", "encoding-safety.yml"])
def test_ci_uses_node24_compatible_action_majors(workflow):
    source = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    actions = re.findall(r"(?m)^\\s*-\\s*uses:\\s*(actions/(?:checkout|setup-python)@\\S+)", source)
    assert "actions/checkout@v5" in actions
    assert "actions/setup-python@v6" in actions
    assert all(action in {"actions/checkout@v5", "actions/setup-python@v6"} for action in actions)
