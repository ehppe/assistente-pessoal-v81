import json
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from util import nucleo_png_bytes

PORTA = 8765
LIMITE_TENTATIVAS = 6
BLOQUEIO_SEGUNDOS = 300


def _ip_tailscale():
    comandos = [
        ["tailscale", "ip", "-4"],
        [r"C:\Program Files\Tailscale\tailscale.exe", "ip", "-4"],
    ]
    for comando in comandos:
        try:
            saida = subprocess.check_output(
                comando, text=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).strip()
            if saida.startswith("100."):
                return saida.splitlines()[0]
        except Exception:
            pass
    return None


def _credenciais(base):
    arquivo = Path(base) / "dados" / "acesso_iphone.json"
    arquivo.parent.mkdir(exist_ok=True)
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        if len(str(dados.get("pin", ""))) == 6:
            return arquivo, str(dados["pin"])
    except Exception:
        pass
    pin = f"{secrets.randbelow(1_000_000):06d}"
    arquivo.write_text(json.dumps({"pin": pin}), encoding="utf-8")
    return arquivo, pin


PAGINA = r'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07101f"><link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" href="/icone.png">
<title>Neymar</title><style>
:root{color-scheme:dark;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 50% 5%,#123c73 0,#07101f 38%,#030711 100%);color:#eef7ff;padding:max(22px,env(safe-area-inset-top)) 16px max(24px,env(safe-area-inset-bottom))}main{max-width:520px;margin:auto}.cab{text-align:center}.robo{width:142px;height:142px;object-fit:contain;filter:drop-shadow(0 0 18px #168cff);animation:holo 3s ease-in-out infinite;transform-origin:50% 80%}@keyframes holo{0%,100%{transform:translateY(3px) scale(.98);filter:drop-shadow(0 0 12px #168cff);opacity:.88}50%{transform:translateY(-8px) scale(1.03);filter:drop-shadow(0 0 28px #42dfff);opacity:1}}h1{font-size:30px;margin:0;text-shadow:0 0 14px #1ca8ff}.sub{color:#68cfff;margin:6px 0 22px}.cartao{background:#0e192bdb;border:1px solid #24466e;border-radius:20px;padding:15px;box-shadow:0 15px 40px #0008}.linha{display:flex;gap:9px}input{min-width:0;flex:1;border:1px solid #345b84;border-radius:14px;background:#07101f;color:#fff;padding:14px;font-size:17px}button{border:0;border-radius:14px;background:#1976d2;color:white;padding:13px;font-size:15px;font-weight:650;touch-action:manipulation}.enviar{width:92px}.mic{width:50px;background:#173453}.status{min-height:45px;color:#a9dfff;padding:12px 2px 2px}.grade{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:15px}.grade button{background:#142944;border:1px solid #28527c}.perigo{color:#ffb6b6!important;border-color:#713f4b!important}.confirmacao{display:none;margin-top:14px;background:#32151c;border:1px solid #8a3d4d;border-radius:16px;padding:14px}.confirmacao .linha{margin-top:10px}.confirmacao button{flex:1}.sim{background:#c9344f}.nao{background:#334155}.login{position:fixed;inset:0;background:#030711ee;display:flex;align-items:center;padding:22px;z-index:4}.login .cartao{width:100%;max-width:390px;margin:auto;text-align:center}.login input{width:100%;text-align:center;letter-spacing:8px;margin:12px 0}.oculto{display:none!important}.nota{font-size:12px;color:#7891ad;text-align:center;margin-top:16px}.historico{margin-top:18px}.historico h2{font-size:13px;color:#68cfff;text-transform:uppercase;letter-spacing:.05em;margin:0 0 8px}.item{border-top:1px solid #1c3554;padding:9px 0;font-size:14px}.item .cmd{color:#9fd8ff}.item .resp{color:#c9d8e8;margin-top:2px}
</style></head><body>
<section id="login" class="login"><div class="cartao"><h2>Acesso ao Neymar</h2><p>Digite o código de 6 números mostrado no computador.</p><input id="pin" inputmode="numeric" maxlength="6" placeholder="000000"><button onclick="entrar()">Conectar</button><div id="erro"></div></div></section>
<main><div class="cab"><img class="robo" src="/icone.png" alt="Robô Neymar"><h1>Neymar</h1><div class="sub">Controle do computador</div></div>
<div class="cartao"><div class="linha"><input id="comando" placeholder="O que você deseja?" enterkeyhint="send"><button class="mic" onclick="ouvir()">🎙️</button><button class="enviar" onclick="enviar()">Enviar</button></div><div id="status" class="status">Verificando computador...</div>
<div id="confirmacao" class="confirmacao"><b id="pergunta">Confirma esta ação?</b><div class="linha"><button class="sim" onclick="confirmar(true)">Confirmar</button><button class="nao" onclick="confirmar(false)">Cancelar</button></div></div>
<div class="grade"><button onclick="rapido('abra a Steam')">Abrir Steam</button><button onclick="rapido('abra a Gamers Club e inicie o CS2')">GC + CS2</button><button onclick="rapido('abra uma nova aba no Chrome')">Nova aba</button><button onclick="rapido('feche a aba atual do Chrome')">Fechar aba</button><button onclick="rapido('aumente o volume')">Volume +</button><button onclick="rapido('diminua o volume')">Volume −</button><button onclick="rapido('pause a música')">Pausar</button><button onclick="rapido('próxima música')">Próxima</button><button onclick="rapido('bloqueie o computador')">Bloquear</button><button class="perigo" onclick="rapido('desligue o computador')">Desligar</button><button class="perigo" onclick="rapido('reinicie o computador')">Reiniciar</button></div>
<div class="historico" id="historico"><h2>Últimos comandos</h2><div id="lista-historico"></div></div>
</div>
<div class="nota">Conexão privada pelo Tailscale. Para ditar, use o microfone ou o ditado do teclado do iPhone.</div></main>
<script>
let confirmationToken=null;
let token=localStorage.getItem('java_pin')||''; const $=x=>document.getElementById(x);
async function api(caminho,opcoes={}){opcoes.headers={...(opcoes.headers||{}),'X-Java-PIN':token};let r=await fetch(caminho,opcoes);if(r.status===401){$('login').classList.remove('oculto');throw Error('Código incorreto.')}if(r.status===429){throw Error('Muitas tentativas. Aguarde alguns minutos.')}return await r.json()}
async function entrar(){token=$('pin').value.trim();try{await api('/api/status');localStorage.setItem('java_pin',token);$('login').classList.add('oculto');atualizar()}catch(e){$('erro').textContent=e.message}}
async function enviar(){let c=$('comando').value.trim();if(!c)return; $('status').textContent='Enviando: '+c;try{let r=await api('/api/comando',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({comando:c})});$('status').textContent=r.mensagem;$('comando').value='';setTimeout(atualizar,900)}catch(e){$('status').textContent='Não foi possível conectar ao computador.'}}
function rapido(c){$('comando').value=c;enviar()}
async function confirmar(sim){try{let r=await api('/api/confirmar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmar:sim,token:confirmationToken})});$('status').textContent=r.mensagem;$('confirmacao').style.display='none'}catch(e){$('status').textContent=e.message}}
function renderHistorico(lista){const el=$('lista-historico');el.replaceChildren();for(const h of (lista||[]).slice(-8).reverse()){const item=document.createElement('div');item.className='item';const c=document.createElement('div');c.className='cmd';c.textContent=h.comando;const r=document.createElement('div');r.className='resp';r.textContent=h.resposta;item.append(c,r);el.append(item)}}
async function atualizar(){try{let r=await api('/api/status');$('status').textContent=r.status||'Neymar conectado.';confirmationToken=r.confirmacao_token;$('confirmacao').style.display=r.pendente?'block':'none';if(r.pendente)$('pergunta').textContent='Confirma '+(r.pendente==='shutdown'?'desligar':'reiniciar')+' o computador?';renderHistorico(r.historico)}catch(e){$('status').textContent='Computador indisponível.'}}
function ouvir(){$('comando').focus();$('status').textContent='Digite seu pedido. O ditado do teclado do iPhone é controlado pelo próprio iOS.'}
$('comando').addEventListener('keydown',e=>{if(e.key==='Enter')enviar()});if(token){$('login').classList.add('oculto');atualizar()}setInterval(atualizar,5000);
</script></body></html>'''


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def iniciar_servidor(assistente, base):
    ip = _ip_tailscale()
    if not ip:
        return None
    _, pin = _credenciais(base)
    tentativas = {}
    tentativas_lock = threading.Lock()

    def limpar_expirados():
        agora=time.time()
        for endereco,registro in list(tentativas.items()):
            if registro[1] and registro[1] <= agora:tentativas.pop(endereco,None)

    def bloqueado(endereco):
        with tentativas_lock:
            limpar_expirados();registro = tentativas.get(endereco)
            return bool(registro and registro[1] > time.time())

    def registrar_falha(endereco):
        with tentativas_lock:
            limpar_expirados();contagem, _ate = tentativas.get(endereco, (0, 0))
            contagem += 1
            ate = time.time() + BLOQUEIO_SEGUNDOS if contagem >= LIMITE_TENTATIVAS else 0
            tentativas[endereco] = (contagem, ate)

    def limpar_tentativas(endereco):
        with tentativas_lock:tentativas.pop(endereco, None)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def _cabecalhos(self, tipo="application/json; charset=utf-8", codigo=200):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers()

        def _json(self, dados, codigo=200):
            self._cabecalhos(codigo=codigo)
            self.wfile.write(json.dumps(dados, ensure_ascii=False).encode("utf-8"))

        def _autorizado(self):
            # Retorna True (ok), False (PIN incorreto) ou None (bloqueado por
            # excesso de tentativas erradas recentes).
            endereco = self.client_address[0]
            if bloqueado(endereco):
                return None
            ok = secrets.compare_digest(self.headers.get("X-Java-PIN", ""), pin)
            if ok:
                limpar_tentativas(endereco)
                return True
            registrar_falha(endereco)
            return False

        def _corpo(self):
            tamanho = int(self.headers.get('Content-Length', '0'))
            if tamanho < 0 or tamanho > 4096:raise ValueError('Tamanho inválido')
            return json.loads(self.rfile.read(tamanho) or b"{}")

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._cabecalhos("text/html; charset=utf-8")
                self.wfile.write(PAGINA.encode("utf-8")); return
            if self.path == "/manifest.webmanifest":
                manifesto = {"name":"Neymar — Assistente","short_name":"Neymar","start_url":"/","display":"standalone","background_color":"#030711","theme_color":"#07101f","icons":[{"src":"/icone.png","sizes":"512x512","type":"image/png"}]}
                self._cabecalhos("application/manifest+json")
                self.wfile.write(json.dumps(manifesto, ensure_ascii=False).encode("utf-8")); return
            if self.path == "/icone.png":
                try:
                    cor = tuple(getattr(assistente, "config", {}).get("cor_nucleo", [64, 207, 255])[:3])
                    conteudo = nucleo_png_bytes(512, cor)
                    self._cabecalhos("image/png"); self.wfile.write(conteudo)
                except Exception:self._json({"erro":"ícone indisponível"},404)
                return
            if self.path == "/api/status":
                autorizado = self._autorizado()
                if autorizado is None:self._json({"erro":"muitas tentativas, aguarde"},429);return
                if not autorizado:self._json({"erro":"não autorizado"},401);return
                acao, confirmation_token = assistente.confirmacao.estado()
                self._json({
                    "status": getattr(assistente, "ultimo_status", "Neymar conectado."),
                    "pendente": acao,
                    "confirmacao_token": confirmation_token,
                    "historico": assistente.memoria.lista()[-8:] if getattr(assistente,'config',{}).get('painel_compartilhar_historico',False) else [],
                })
                return
            self._json({"erro":"não encontrado"},404)

        def do_POST(self):
            autorizado = self._autorizado()
            if autorizado is None:self._json({"erro":"muitas tentativas, aguarde"},429);return
            if not autorizado:self._json({"erro":"não autorizado"},401);return
            try:dados=self._corpo()
            except Exception:self._json({"erro":"pedido inválido"},400);return
            if not isinstance(dados,dict):self._json({"erro":"pedido inválido"},400);return
            if self.path == "/api/comando":
                comando=str(dados.get("comando", "")).strip()[:300]
                if not comando:self._json({"erro":"comando vazio"},400);return
                assistente.ui(0, lambda c=comando: assistente.processar(c))
                self._json({"mensagem":"Pedido recebido: "+comando});return
            if self.path == "/api/confirmar":
                if not assistente.acao_pendente:self._json({"mensagem":"Não existe uma ação aguardando confirmação."});return
                confirmar=dados.get("confirmar") is True
                assistente.ui(0,lambda:assistente.resolver_confirmacao(confirmar,dados.get("token")))
                self._json({"mensagem":"Confirmação recebida; aguardando validação." if confirmar else "Cancelamento recebido."});return
            self._json({"erro":"não encontrado"},404)

    try:
        servidor = _Servidor((ip, PORTA), Handler)
    except OSError:
        return None
    servidor.ip_tailscale, servidor.pin = ip, pin
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor
