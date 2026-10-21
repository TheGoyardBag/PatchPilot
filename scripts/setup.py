"""Create a local secret; never commit it or paste it into screenshots."""
from pathlib import Path
import os
import secrets
ROOT=Path(__file__).resolve().parents[1]
state=Path(os.environ.get('PATCHPILOT_STATE',str(ROOT/'.patchpilot')))
state.mkdir(parents=True,exist_ok=True)
path=state/'token'
if not path.exists():
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32)+'\n')
print('PatchPilot is configured for LOCAL AUTHORED-FIXTURE mode.')
print('API token (enter in the dashboard; do not commit): '+path.read_text().strip())
print('Start: python -m patchpilot.cli serve')
print('Open: http://127.0.0.1:8000')
