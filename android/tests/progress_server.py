"""Isolated progress fixture; this controller is never bundled into the app."""
from pathlib import Path
import json, sys, tempfile, threading, time, zipfile

project=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(project/'android/app/src/main/python'))
import android_entry
with tempfile.TemporaryDirectory() as home:
    root=Path(home)/'code'
    with zipfile.ZipFile(project/'android/app/src/main/assets/content.zip') as z:z.extractall(root)
    url=android_entry.start(str(root),str(Path(home)/'home'),'progress-test',json.dumps({'DEEPSEEK_API_KEY':'offline-placeholder'}))
    import liuyao_app
    liuyao_app.__path__.append(str(project/'liuyao_app'))
    from liuyao_app.pipeline import run_analysis
    from liuyao_app.test_v5 import NewReportProvider
    from liuyao_app.providers import ProviderError
    gate=threading.Semaphore(0)
    controls={'mode':'success','runs':0,'calls':0}
    def pipeline(*args,**kwargs):
        controls['runs']+=1
        fixture=NewReportProvider()
        mode=controls['mode'];number=0
        def call(*values,**options):
            nonlocal number
            number+=1;controls['calls']+=1
            started=time.monotonic()
            if not gate.acquire(timeout=90):raise ProviderError('timeout','合成测试请求等待超时。')
            if mode=='fail' and number==1:
                raise ProviderError('authentication_failed','AI 凭据或模型访问权限校验失败，请检查配置。',metadata={'http_status':401,'elapsed_ms':1000})
            response=fixture(*values,**options)
            if mode=='repair' and number==1:response['raw_text']='synthetic invalid JSON'
            response.update(http_status=200,elapsed_ms=int((time.monotonic()-started)*1000))
            return response
        return run_analysis(*args,provider_call=call,**kwargs)
    android_entry._app.pipeline=pipeline
    original=android_entry._server.RequestHandlerClass
    class Controlled(original):
        def do_POST(self):
            if self.path!='/api/test-control':return super().do_POST()
            self.guard(True);self.actor()
            value=self.body()
            if value.get('mode') in ('success','fail','repair'):controls['mode']=value['mode']
            if value.get('release') is True:gate.release()
            self.send_json(controls)
    android_entry._server.RequestHandlerClass=Controlled
    print(url,flush=True)
    try:threading.Event().wait()
    finally:android_entry.stop()
