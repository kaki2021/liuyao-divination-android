from pathlib import Path
import sys,tempfile,threading,zipfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'android/app/src/main/python'))
import android_entry
with tempfile.TemporaryDirectory() as home:
    root=Path(home)/'code'
    with zipfile.ZipFile(ROOT/'android/app/src/main/assets/content.zip') as z:z.extractall(root)
    url=android_entry.start(str(root),str(Path(home)/'home'),'button-test')
    print(url,flush=True)
    try: threading.Event().wait()
    finally: android_entry.stop()
