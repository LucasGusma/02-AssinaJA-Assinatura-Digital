"""Abre o AssinaJA no navegador e mantém o servidor local em segundo plano."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import build_opener, ProxyHandler
import webbrowser

ROOT = Path(__file__).resolve().parent

def main():
    uploaded_logo = Path(r"C:\Users\f015114\.gemini\antigravity\brain\4c42f1b7-1a09-4439-913b-076db36a5cf6\.user_uploaded\media_1794427999208_31839dac.png")
    if uploaded_logo.is_file():
        try:
            import shutil
            for dest in (ROOT / 'frontend/dist/logo-baleia-ia.png', ROOT / 'frontend/public/logo-baleia-ia.png'):
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(uploaded_logo, dest)
        except Exception:
            pass
    port = int(os.environ.get('PORT','8765'))
    url = f'http://127.0.0.1:{port}/'
    opener = build_opener(ProxyHandler({}))
    def ready():
        try:
            with opener.open(url + 'api/health/live',timeout=2) as response:
                return response.status == 200 and b'"status":"ok"' in response.read(4096)
        except OSError:
            return False
    if not ready():
        (ROOT/'data').mkdir(exist_ok=True)
        python = str(Path(sys.executable).with_name('python.exe'))
        with (ROOT/'data/server-output.log').open('a',encoding='utf-8') as output, (ROOT/'data/server-error.log').open('a',encoding='utf-8') as errors:
            process = subprocess.Popen([python,str(ROOT/'server.py')],cwd=ROOT,
                stdout=output,stderr=errors,stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(15):
            if ready(): break
            if process.poll() is not None: break
            time.sleep(.5)
        if not ready():
            raise RuntimeError('O servidor não iniciou. Consulte data/server-error.log.')
    if not webbrowser.open(url):
        raise RuntimeError(f'Abra este endereço no navegador: {url}')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(None,str(exc),'AssinaJA',0x10)
