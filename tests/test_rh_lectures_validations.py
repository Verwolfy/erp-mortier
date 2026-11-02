import subprocess
import sys
from pathlib import Path

def test_rh_validation_in_isolated_process():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,'-m','pytest','-q','tests/rh_validation_cases.py'],cwd=root,capture_output=True,text=True,timeout=45)
    assert result.returncode==0,result.stdout+result.stderr
