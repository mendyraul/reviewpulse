"""Verify an installed wheel away from the source checkout."""

import os
from pathlib import Path
import subprocess
import tempfile
import venv


def main():
    wheel = sorted(Path("dist").glob("reviewpulse-*.whl"))[-1].resolve()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        python = (
            root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        subprocess.run(
            [str(python), "-m", "pip", "install", str(wheel), "httpx"], check=True
        )
        code = """from pathlib import Path
from fastapi.testclient import TestClient
from src.server import create_app
from src.normalize import load_schema
assert load_schema()['type'] == 'object'
app = create_app(demo=True, state_dir='state', allowed_hosts=('testserver',))
with TestClient(app) as client:
    for path in ['/dashboard/active', '/dashboard/done', '/dashboard/risk', '/findings/demo-retry', '/static/dashboard.css', '/static/dashboard.js']:
        result = client.get(path)
        assert result.status_code == 200, (path, result.text)
    assert 'DEMO MODE' in client.get('/dashboard/active').text
"""
        subprocess.run(
            [str(python), "-c", code],
            cwd=root,
            check=True,
            env={
                key: value for key, value in os.environ.items() if key != "PYTHONPATH"
            },
        )
    print("Installed wheel dashboard, assets and schema smoke passed")


if __name__ == "__main__":
    main()
