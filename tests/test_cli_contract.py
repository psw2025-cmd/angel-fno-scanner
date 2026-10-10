from pathlib import Path
import subprocess,sys,ast
ROOT=Path(__file__).resolve().parents[1]
def test_parser_registration():
    s=(ROOT/"agent_cli.py").read_text(encoding="utf-8-sig")
    ast.parse(s)
    assert 'add_argument("--json-only"' in s
def test_cli_help():
    p=subprocess.run([sys.executable,"agent_cli.py","--help"],cwd=ROOT,capture_output=True,timeout=45)
    assert p.returncode==0,p.stderr[-500:]
    assert b"--json-only" in p.stdout
def test_unknown_argument_exit_2():
    p=subprocess.run([sys.executable,"agent_cli.py","--not-an-option"],cwd=ROOT,capture_output=True,timeout=45)
    assert p.returncode==2
