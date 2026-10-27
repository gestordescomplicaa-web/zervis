"""Autorização do fetch no Chromium, com o servidor real e sem câmera ou modelo."""

import asyncio
import json
import subprocess
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import websockets

from zervis.imersivo import servidor


async def verificar(tmp_path, monkeypatch):
    pagina = (servidor.HERE / "stage.html").read_text()
    web = tmp_path / "web"
    web.mkdir()
    # Executa o cabeçalho real que prepara a autorização, sem iniciar mãos, áudio ou avatar.
    (web / "stage.html").write_text(
        pagina[:pagina.index("<title>")] + "</head><body>Teste HTTP</body></html>"
    )
    estado = tmp_path / "estado"
    estado.mkdir()
    monkeypatch.setattr(servidor, "HERE", web)
    monkeypatch.setattr(servidor, "ESTADO", estado)
    monkeypatch.setattr(servidor, "TOKEN", "token-sintetico-do-browser")
    externo = []

    class OutroServidor(BaseHTTPRequestHandler):
        def do_GET(self):
            externo.append(dict(self.headers))
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Handler)
    outro = ThreadingHTTPServer(("127.0.0.1", 0), OutroServidor)
    for s in (http, outro):
        threading.Thread(target=s.serve_forever, daemon=True).start()
    perfil = tmp_path / "chromium"
    perfil.mkdir()
    processo = subprocess.Popen([
        "/usr/bin/chromium", "--headless=new", "--remote-debugging-port=0",
        f"--user-data-dir={perfil}", "--no-first-run", "--disable-background-networking",
        f"http://127.0.0.1:{http.server_port}/stage.html",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        porta = perfil / "DevToolsActivePort"
        for _ in range(100):
            if porta.exists():
                break
            await asyncio.sleep(.1)
        with urllib.request.urlopen(
            f"http://127.0.0.1:{int(porta.read_text().splitlines()[0])}/json/list", timeout=5
        ) as resposta:
            alvo = next(p for p in json.load(resposta) if p["type"] == "page")
        async with websockets.connect(alvo["webSocketDebuggerUrl"]) as ws:
            seq = 0

            async def avaliar(texto):
                nonlocal seq
                seq += 1
                await ws.send(json.dumps({"id": seq, "method": "Runtime.evaluate", "params": {
                    "expression": texto, "awaitPromise": True, "returnByValue": True,
                }}))
                while True:
                    evento = json.loads(await asyncio.wait_for(ws.recv(), 10))
                    if evento.get("id") == seq:
                        resultado = evento["result"]
                        assert "exceptionDetails" not in resultado, resultado
                        return resultado.get("result", {}).get("value")

            for _ in range(50):
                if await avaliar("location.pathname === '/stage.html' && document.readyState === 'complete' && !!document.querySelector('meta[name=ze-token]')"):
                    break
                await asyncio.sleep(.1)
            assert await avaliar("fetch('/config').then(r => r.status)") == 200
            assert await avaliar("""fetch('/teclado', {method:'POST',
                headers:{'Content-Type':'application/json'}, body:'{"texto":"Abra o guia"}'})
                .then(r => r.status)""") == 200
            assert json.loads((estado / "teclado.json").read_text())["texto"] == "Abra o guia"
            assert await avaliar("""fetch(new Request(location.origin + '/teclado', {
                method:'POST',headers:{'Content-Type':'application/json'},body:'{"texto":"Request"}'
                })).then(r => r.status)""") == 200
            assert json.loads((estado / "teclado.json").read_text())["texto"] == "Request"
            assert await avaliar(
                f"fetch('http://127.0.0.1:{outro.server_port}/').then(r => r.text())"
            ) == "ok"
            assert len(externo) == 1 and not any(k.lower() == "x-ze-token" for k in externo[0])
    finally:
        processo.terminate()
        try:
            processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait(timeout=5)
        for s in (http, outro):
            s.shutdown()
            s.server_close()


def test_fetch_autoriza_pedidos_locais_sem_enviar_token_a_outro_servidor(tmp_path, monkeypatch):
    asyncio.run(verificar(tmp_path, monkeypatch))
