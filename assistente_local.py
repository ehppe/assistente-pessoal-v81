"""Neymar — assistente de voz pessoal para Windows.

Este arquivo só monta a classe principal a partir dos módulos: a interface
(ui_mixin), a voz (voz_mixin), a interpretação de comandos (acoes_mixin), a
automação do Discord/Gamers Club (discord_mixin) e o índice de arquivos
(indice_mixin). Cada módulo cuida de uma parte do assistente e pode ser lido
e ajustado separadamente. Preferências ficam em config.json (veja config.py).
"""
import ctypes
import queue
import threading
import traceback
from pathlib import Path

import tkinter as tk

import config
from acoes_mixin import AcoesMixin
from runtime_mixin import RuntimeMixin
from jogo_mixin import JogoMixin
from conversa_mixin import ConversaMixin
from discord_mixin import DiscordMixin
from indice_mixin import IndiceMixin
from painel_iphone import iniciar_servidor
from ui_mixin import TRANSP, UIMixin
from voz_mixin import VozMixin

BASE = Path(__file__).resolve().parent


class Assistente(JogoMixin, RuntimeMixin, ConversaMixin, UIMixin, VozMixin, AcoesMixin, DiscordMixin, IndiceMixin):
    def __init__(self):
        self.base = BASE
        self.config = config.carregar(BASE)
        self.modelo_vosk = BASE / 'modelos' / 'vosk-pt'
        self.db = BASE / 'dados' / 'indice.db'

        self.root = tk.Tk()
        # Sem isso, qualquer erro dentro de um comando (chamado via
        # root.after) desaparece silenciosamente — o Neymar roda com pythonw.exe,
        # que não tem console para mostrar o erro. Agora ele vai parar,
        # sempre, em dados\historico.log.
        self.root.report_callback_exception = self.registrar_excecao_tk
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg=TRANSP)
        self.root.wm_attributes('-transparentcolor', TRANSP)
        self.root.geometry('320x338+30+30')
        self.root.withdraw()

        self.audio = queue.Queue(maxsize=50)
        self.transcrevendo = threading.Event()
        self.encerrar = threading.Event()
        self.falando = threading.Event()
        self.indexando = threading.Event()
        self.pausado = threading.Event()
        self.ativo_ate = 0
        self.chamada_id = 0
        self.acao_pendente = None
        self.confirmacao_ate = 0
        self.arrasto = (0, 0)
        self.ultimo_status = 'Neymar iniciado.'
        self.estado_visual = 'idle'
        self.quadro_animacao = 0
        self.voz_piper = None
        self.comando_atual = ''
        self.historico_comandos = []

        self.preparar_runtime()
        from atalho_fala import iniciar
        iniciar(self.encerrar,lambda:self.ui(0,self.parar_fala),self.registrar)
        self.configurar_api_windows()
        self.configurar_prioridade()
        self.interface()
        self.bandeja()
        self.servidor_iphone = iniciar_servidor(self, BASE)
        threading.Thread(target=self.preparar_voz, daemon=True).start()
        threading.Thread(target=self.ouvir, daemon=True).start()
        # Adiado: uma varredura de disco completa concorre por CPU com a
        # transcrição local (Whisper/Vosk) se começar junto da abertura do
        # programa. Dar 45s de folga deixa as primeiras chamadas mais responsivas.
        self.ui(45000, self.iniciar_indice)
        self.ui(600, self.abrir_conversa)

    def configurar_api_windows(self):
        from ctypes import wintypes as w
        u=ctypes.windll.user32
        for nome,args in {
            'GetWindowTextLengthW':[w.HWND], 'GetWindowTextW':[w.HWND,w.LPWSTR,ctypes.c_int],
            'GetClassNameW':[w.HWND,w.LPWSTR,ctypes.c_int], 'IsWindowVisible':[w.HWND],
            'GetWindowThreadProcessId':[w.HWND,ctypes.POINTER(w.DWORD)],
            'ShowWindow':[w.HWND,ctypes.c_int], 'SetForegroundWindow':[w.HWND],
            'SetWindowPos':[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT],
            'PostMessageW':[w.HWND,w.UINT,w.WPARAM,w.LPARAM],
        }.items():getattr(u,nome).argtypes=args

    def configurar_prioridade(self):
        try:
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00008000)
        except Exception:
            pass

    def registrar_excecao_tk(self, exc, val, tb):
        # Log curto e direto: tipo do erro, mensagem e onde aconteceu — mais
        # útil no historico.log (que corta linhas longas) do que o traceback
        # inteiro.
        quadros = traceback.extract_tb(tb)
        onde = quadros[-1] if quadros else None
        local = f' em {onde.filename}:{onde.lineno} ({onde.name})' if onde else ''
        self.registrar(f'ERRO (nao tratado) {exc.__name__}: {val}{local}')
        # Sem isso, um erro inesperado faz o Neymar simplesmente ficar em
        # silêncio (o comando "some"). Melhor avisar por voz que algo falhou.
        try:
            if not self.falando.is_set():
                self.falar('Tive um problema interno nesse pedido. Já registrei o erro no histórico.')
        except Exception:
            pass

    def fechar(self):
        if getattr(self,'fechando',False):return
        self.fechando=True
        self.cancelar_tudo()
        self.encerrar.set()
        if self.servidor_iphone:
            threading.Thread(target=self.servidor_iphone.shutdown, daemon=True).start()
        self.ultimo_status='Restaurando ajustes antes de sair…'
        pronto=threading.Event()
        def restaurar():
            try:self.registrar(self.modo_jogo.desativar())
            finally:pronto.set()
        threading.Thread(target=restaurar,daemon=True).start()
        def concluir():
            if not pronto.is_set():self.root.after(100,concluir);return
            if getattr(self,'central_qt',None):self.central_qt.fechar()
            self.tray.stop();self.root.destroy()
        concluir()

    def iniciar(self):
        self.root.mainloop()


if __name__ == '__main__':
    # Uma instância por sessão: evita dois ouvintes e duas respostas simultâneas.
    ctypes.windll.kernel32.CreateMutexW.restype = ctypes.c_void_p
    from versao import TITULO
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, 'Local\\NeymarAssistenteV81')
    if ctypes.windll.kernel32.GetLastError() == 183:
        ctypes.windll.user32.MessageBoxW(None, 'O Neymar já está aberto. Use o ícone perto do relógio.', TITULO, 0)
    else:
        try:Assistente().iniciar()
        except Exception:
            (BASE/'dados').mkdir(exist_ok=True)
            (BASE/'dados'/'inicializacao-erro.log').write_text(traceback.format_exc(), encoding='utf-8')
            ctypes.windll.user32.MessageBoxW(None, 'O Neymar não iniciou. Abra Diagnostico (ver erros).bat.', TITULO, 16)
