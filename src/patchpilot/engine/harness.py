"""Stdlib-only test entrypoint, copied into the isolated runner image.

Tests and application code share a process: reported test results are useful
signals, NOT attestations that arbitrary adversarial Python behaved honestly.
"""
import argparse
import io
import json
from pathlib import Path
import sys
import time
import unittest

class Capture(unittest.TextTestResult):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.passed = 0
    def addSuccess(self,test):
        super().addSuccess(test)
        self.passed += 1

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root",default="/workspace")
    p.add_argument("--pattern",default="test_public.py")
    args = p.parse_args()
    root = Path(args.root).resolve()
    sys.path[:0] = [str(root / "src"),str(root)]
    started=time.monotonic()
    capture=io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(root / "tests"),pattern=args.pattern)
    result=unittest.TextTestRunner(stream=capture,verbosity=2,resultclass=Capture).run(suite)
    output={"status":"passed" if result.wasSuccessful() and result.testsRun>0 and not result.skipped else "failed",
            "tests":result.testsRun,"passed":result.passed,"failed":len(result.failures),
            "errors":len(result.errors),"skipped":len(result.skipped),"duration_s":round(time.monotonic()-started,6),
            "output":capture.getvalue()[-20000:],
            "failures":[{"test":str(t),"detail":v[-2500:]} for t,v in (result.failures+result.errors)[:8]]}
    print("PATCHPILOT_RESULT="+json.dumps(output),flush=True)
    return 0 if output["status"]=="passed" else 1

if __name__=="__main__":
    sys.exit(main())
