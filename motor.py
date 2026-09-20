"""Regras e memória independentes da interface e das bibliotecas do Windows."""
import json
import re
import threading
import time
import unicodedata
from pathlib import Path


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn').strip()


def preparar_pedido(texto):
    n = normalizar(texto)
    n = re.sub(r'^[\s,.:;!?]+|[\s,.:;!?]+$', '', n)
    n = re.sub(r'^(?:neymar[, ]+)?(?:por favor[, ]+)?', '', n)
    n = re.sub(r'^(?:voce pode|pode|poderia|consegue)\s+(?:por favor\s+)?', '', n)
    return n.strip()


def resposta_confirmacao(texto):
    n = preparar_pedido(texto)
    if re.search(r'\b(nao|nunca|cancela|cancelar|cancele)\b', n):
        return False
    if n in ('sim', 'confirmo', 'confirmar', 'confirmado', 'confirme', 'pode confirmar', 'pode desligar', 'pode reiniciar'):
        return True
    return None


def tipo_pedido(texto):
    n = preparar_pedido(texto)
    if re.search(r'\b(nao|nunca)\b', n):
        return 'conversa'
    if re.match(r'^(como|por que|porque|explique|qual|quais|quando|onde|o que|me explique|me diga|quanto)\b', n):
        return 'conversa'
    if n in ('modo jogar', 'ativar modo jogar', 'ative modo jogar'):
        return 'rotina'
    if re.match(r'^(desligue|desligar|desliga|reinicie|reiniciar|reinicia)\s+(?:(?:o|meu|este|esse)\s+)?(?:computador|pc|windows)(?:\s+agora)?$', n):
        return 'energia'
    if n in ('desligue', 'desligar', 'desliga', 'reinicie', 'reiniciar', 'reinicia'):
        return 'energia'
    if re.match(r'^(abra|abre|abrir|inicie|iniciar|feche|fecha|fechar|encerre|encerrar|entre|entra|entrar|conecte|conecta|conectar|saia|sair|desconecte|desconectar|desligue da chamada|toque|tocar|coloque|pesquise|pesquisar|procure|aumente|aumentar|diminua|diminuir|abaixe|suba|silencie|silenciar|pause|pausar|continue a musica|continuar a musica|proxima musica|proxima faixa|pule a musica|bloqueie|bloquear|trave)\b', n):
        return 'comando'
    return 'conversa'


class Confirmacao:
    def __init__(self, relogio=time.monotonic):
        self.relogio = relogio
        self.lock = threading.RLock()
        self.acao = None
        self.prazo = 0
        self.token = None

    def iniciar(self, acao):
        import secrets
        if acao not in ('shutdown', 'restart'):
            raise ValueError('Ação de energia inválida')
        with self.lock:
            self.acao, self.prazo, self.token = acao, self.relogio() + 30, secrets.token_hex(16)
            return self.token

    def estado(self):
        with self.lock:
            if self.relogio() >= self.prazo:
                self.acao = self.token = None
            return self.acao, self.token

    def consumir(self, sim, token):
        with self.lock:
            acao, atual = self.estado()
            if not acao or not token or token != atual:
                return None
            self.acao = self.token = None
            return acao if sim else None

    def cancelar(self):
        with self.lock:
            self.acao = self.token = None


class Memoria:
    def __init__(self, caminho, persistir=True):
        self.caminho = Path(caminho)
        self.lock = threading.RLock()
        self.persistir = persistir
        self.itens = []
        if persistir and self.caminho.exists():
            try:
                dados = json.loads(self.caminho.read_text(encoding='utf-8'))
                if isinstance(dados, list):
                    self.itens = [d for d in dados if isinstance(d, dict) and isinstance(d.get('comando'), str) and isinstance(d.get('resposta'), str)][-60:]
            except (OSError, ValueError):
                # Preserve the damaged file for manual recovery; do not silently overwrite it.
                self.caminho.replace(self.caminho.with_name('conversas-recuperar-'+str(time.time_ns())+'.json'))

    def contexto(self):
        with self.lock:
            saida = []
            for d in self.itens[-8:]:
                saida.extend([{'role':'user','content':d['comando'][:4000]}, {'role':'assistant','content':d['resposta'][:4000]}])
            return saida

    def lista(self):
        with self.lock:
            return [dict(x) for x in self.itens]

    def salvar(self):
        with self.lock:
            if self.persistir:
                self.caminho.parent.mkdir(parents=True, exist_ok=True)
                temp = self.caminho.with_suffix('.tmp')
                temp.write_text(json.dumps(self.itens, ensure_ascii=False, indent=2), encoding='utf-8')
                temp.replace(self.caminho)

    def adicionar(self, comando, resposta):
        with self.lock:
            self.itens.append({'comando':comando,'resposta':resposta})
            self.itens = self.itens[-60:]
            self.salvar()

    def limpar(self):
        with self.lock:
            self.itens = []
            if self.caminho.exists():
                self.caminho.unlink()
