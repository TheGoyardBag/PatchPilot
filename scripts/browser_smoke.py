"""Exercise the shipped dashboard against a real loopback FastAPI server."""
from pathlib import Path
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]

def main():
    with tempfile.TemporaryDirectory(prefix='patchpilot-browser-') as d:
        token='browser-only-'+__import__('secrets').token_hex(24)
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PATCHPILOT_STATE':d,'PATCHPILOT_TOKEN':token}
        proc=subprocess.Popen([sys.executable,'-m','patchpilot.cli','serve','--port',str(port)],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        checks=[];errors=[];base=f'http://127.0.0.1:{port}'
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(base+'/health',timeout=.2);break
                except OSError:time.sleep(.1)
            else:raise RuntimeError('Preview server did not start')
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1512,'height':1140},device_scale_factor=1)
                page.on('pageerror',lambda e:errors.append(str(e)))
                bridge=os.environ.get('PATCHPILOT_BROWSER_BRIDGE')=='1'
                if bridge:
                    # Offline DOM test transport. No browser network navigation is
                    # attempted. Browser fetch is bridged to the real local API.
                    def forward(path,options):
                        if not str(path).startswith('/api/'):
                            raise ValueError('Test bridge only accepts local API paths')
                        headers=options.get('headers',{})
                        body=options.get('body')
                        request=urllib.request.Request(base+path,data=body.encode() if body else None,headers=headers,method=options.get('method','GET'))
                        try:response=urllib.request.urlopen(request,timeout=30)
                        except urllib.error.HTTPError as exc:response=exc
                        with response:
                            return {'status':response.status,'body':response.read().decode(),'headers':dict(response.headers)}
                    page.expose_function('__apiBridge',forward)
                    html=(ROOT/'src/patchpilot/web/index.html').read_text()
                    html=html.replace('<link rel="stylesheet" href="/static/styles.css">','')
                    html=html.replace('<script type="module" src="/static/app.js"></script>','')
                    page.set_content(html)
                    page.add_style_tag(content=(ROOT/'src/patchpilot/web/styles.css').read_text())
                    page.add_script_tag(content="""
                    const memory=new Map();
                    Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)}});
                    window.fetch=async(path,options={})=>{const r=await window.__apiBridge(path,options);return new Response(r.body,{status:r.status,headers:r.headers});};
                    """)
                    utils=(ROOT/'src/patchpilot/web/utils.mjs').read_text().replace('export function','function')
                    app=(ROOT/'src/patchpilot/web/app.js').read_text().split('\n',1)[1]
                    page.add_script_tag(content=utils+'\nconst e=escapeHTML;\n'+app)
                else:
                    page.goto(base,wait_until='networkidle')
                assert page.locator('#login').is_visible();checks.append('login_gate')
                page.fill('#token',token);page.click('#connect')
                try:page.wait_for_selector('#workspace',state='visible',timeout=8000)
                except Exception:
                    print('BROWSER ERRORS',errors)
                    print('TOAST',page.locator('#toast').inner_text());print('PROVIDER',page.locator('#provider').evaluate('(el)=>el.outerHTML'));print('RUN',page.locator('#run').count())
                    raise
                assert page.locator('#task option').count()==24;checks.append('authenticated_catalog')
                page.select_option('#task','pagination');page.click('#run')
                page.wait_for_function("document.querySelector('#stat-status').textContent === 'Ready for review'",timeout=30000)
                assert page.locator('.candidate').count()==6;checks.append('run_real_fixture_tests')
                assert page.locator('#activity .activity-row').count()>6;checks.append('event_stream_content')
                page.locator('.candidate').filter(has_text='Focused implementation').click()
                assert page.locator('.diff-add').count()>0;checks.append('diff_rendering')
                page.click('[data-tab="tests"]');assert 'Ran 3 tests' in page.locator('#patch-content').inner_text();checks.append('test_evidence')
                page.click('[data-tab="details"]');assert 'public_pass_fraction' in page.locator('#patch-content').inner_text();checks.append('model_features')
                page.click('[data-tab="diff"]')
                page.locator('.candidate').filter(has_text='Original implementation').click();assert page.locator('#approve').is_disabled();checks.append('blocked_patch_not_approvable')
                page.locator('.candidate').filter(has_text='Focused implementation').click()
                page.fill('#review-note','Reviewed final-page and empty-input behavior; original tests remain unchanged.')
                # Screenshot is the real running bundled UI, before approving.
                (ROOT/'docs').mkdir(exist_ok=True)
                page.screenshot(path=str(ROOT/'docs/dashboard.png'),full_page=True)
                page.click('#approve');page.wait_for_selector('#download',state='visible');checks.append('human_review')
                with page.expect_download() as event:page.click('#download')
                download=event.value
                download.save_as(str(Path(d)/'export.diff'))
                assert '--- a/src/subject.py' in (Path(d)/'export.diff').read_text();checks.append('approved_diff_export')
                page.click('#nav-metrics');page.wait_for_selector('#metrics',state='visible')
                assert 'logistic regression' in page.locator('#metrics-content').inner_text();checks.append('evaluation_view')
                page.click('#nav-work')
                if not bridge:
                    page.reload(wait_until='networkidle');page.wait_for_selector('#workspace',state='visible');checks.append('tab_session_restored')
                page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(200)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1');checks.append('mobile_no_horizontal_overflow')
                if not bridge:
                    page.click('#logout');page.wait_for_selector('#login',state='visible');checks.append('logout_clears_session')
                assert not errors,errors
                checks.append('no_browser_javascript_errors')
                browser.close()
            report={'checks_passed':len(checks),'checks':checks,'browser_errors':errors,'frontend':'Bundled no-build JavaScript dashboard','backend':'Real FastAPI server via in-memory fetch bridge; buffered SSE, shimmed session storage, no browser network/CSP validation' if bridge else 'Real FastAPI server over direct loopback','nextjs_tested':False,'test_transport_bridge':bridge}
            (ROOT/'reports/browser_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            if proc.stderr:proc.stderr.close()
if __name__=='__main__':main()
