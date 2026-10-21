from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from ..schemas import TestResult
from ..security import redact

class RunnerUnavailable(RuntimeError): pass

HARNESS=Path(__file__).with_name("harness.py")

class TestRunner:
    def __init__(self,mode: str="trusted-demo",image: str="patchpilot-runner:local",timeout_s: float=15,output_limit: int=100000):
        if mode not in {"trusted-demo","docker"}: raise ValueError("Unknown runner")
        self.mode,self.image,self.timeout_s,self.output_limit=mode,image,timeout_s,output_limit

    def docker_command(self,root: Path,pattern: str,name: str) -> list[str]:
        if "," in str(root): raise ValueError("Docker mount path cannot contain a comma")
        return ["docker","run","--rm","--name",name,"--network=none","--read-only",
                "--cap-drop=ALL","--security-opt=no-new-privileges:true","--pids-limit=64",
                "--memory=256m","--memory-swap=256m","--cpus=1","--user=65532:65532",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=32m","--env=PYTHONDONTWRITEBYTECODE=1",
                "--mount",f"type=bind,src={root.resolve()},dst=/workspace,readonly",
                self.image,"--root","/workspace","--pattern",pattern]

    def run(self,root: Path,pattern: str="test_public.py",*,trusted_fixture: bool=False) -> TestResult:
        if not re.fullmatch(r"test_[A-Za-z0-9_*]+\.py",pattern):
            raise ValueError("Invalid test filename pattern")
        if not (root/"tests").is_dir(): raise ValueError("Workspace has no tests directory")
        name="patchpilot-"+uuid.uuid4().hex[:12]
        if self.mode=="trusted-demo":
            if not trusted_fixture: raise RunnerUnavailable("Untrusted code requires Docker. Host execution is limited to bundled, verified fixtures.")
            command=[sys.executable,"-I","-S","-B",str(HARNESS),"--root",str(root.resolve()),"--pattern",pattern]
        else:
            if not shutil.which("docker"): raise RunnerUnavailable("Docker CLI not found; no host fallback is permitted")
            command=self.docker_command(root,pattern,name)
        env={"PATH":os.environ.get("PATH",""),"SYSTEMROOT":os.environ.get("SYSTEMROOT",""),
             "HOME":str(root),"PYTHONDONTWRITEBYTECODE":"1","PYTHONHASHSEED":"0","LANG":"C.UTF-8"}
        # Docker's client may need its own config/context; never pass cloud/model secrets.
        if self.mode=="docker":
            for k in ("DOCKER_HOST","DOCKER_CONTEXT","DOCKER_CONFIG","XDG_RUNTIME_DIR"):
                if k in os.environ: env[k]=os.environ[k]
            env["HOME"]=os.environ.get("HOME",str(root))
        start=time.monotonic()
        proc=subprocess.Popen(command,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL,start_new_session=os.name!="nt")
        data=bytearray(); overflow=threading.Event()
        def consume():
            assert proc.stdout is not None
            while True:
                chunk=proc.stdout.read(4096)
                if not chunk: break
                if len(data)+len(chunk)>self.output_limit:
                    data.extend(chunk[:max(0,self.output_limit-len(data))]); overflow.set(); break
                data.extend(chunk)
        reader=threading.Thread(target=consume,daemon=True);reader.start()
        timed_out=False
        try:
            while proc.poll() is None:
                if overflow.is_set() or time.monotonic()-start>self.timeout_s:
                    timed_out=not overflow.is_set()
                    if os.name!="nt": os.killpg(proc.pid,signal.SIGKILL)
                    else: proc.kill()
                    break
                time.sleep(0.01)
            proc.wait(timeout=3)
        finally:
            if proc.poll() is None: proc.kill();proc.wait()
            reader.join(timeout=2)
            if proc.stdout: proc.stdout.close()
            if self.mode=="docker":
                try: subprocess.run(["docker","rm","-f",name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,check=False)
                except (OSError,subprocess.TimeoutExpired): pass
        text=redact(data.decode("utf-8",errors="replace"))
        common={"runner":self.mode,"exit_code":proc.returncode,"duration_s":round(time.monotonic()-start,6)}
        if timed_out or overflow.is_set():
            return TestResult(status="timeout" if timed_out else "output_limit",output=text[-20000:],**common)
        result_line=next((l for l in reversed(text.splitlines()) if l.startswith("PATCHPILOT_RESULT=")),None)
        if not result_line:
            return TestResult(status="runner_error",output=text[-20000:],**common)
        try:
            value=json.loads(result_line.split("=",1)[1]);value.update(common)
            result=TestResult.model_validate(value)
            if result.tests != result.passed+result.failed+result.errors+result.skipped or result.tests<0:
                raise ValueError("Inconsistent test counts")
            if proc.returncode!=0 and result.status=="passed": result.status="failed"
            return result
        except (ValueError,TypeError):
            return TestResult(status="runner_error",output="Malformed test report\n"+text[-12000:],**common)
