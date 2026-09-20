"""Busca de arquivos, pastas e programas.

Primeiro tenta o Windows Search (rápido e sempre atualizado pelo próprio
Windows). Se não estiver disponível, cai para um índice próprio em sqlite,
construído varrendo o disco uma vez por semana (ou quando pedido pela
bandeja, em "Atualizar arquivos e programas").
"""
import csv
import psutil
import ctypes
import difflib
import os
import re
import sqlite3
import subprocess
import threading
import time
import urllib.parse
import webbrowser
import winreg
from ctypes import wintypes
from pathlib import Path

from util import com_thread, norm

IGNORAR_PASTAS = {
    'windows', '$recycle.bin', 'system volume information', 'winsxs',
    'node_modules', '.git', 'cache', 'caches', 'temp', 'tmp',
}


class IndiceMixin:
    def buscar_windows_search(self, nome, tipo=None, limite=25):
        if not self.config.get('usar_windows_search', False):
            return None
        try:
            import win32com.client
        except ImportError:
            return None
        try:
            with com_thread():
                conexao = win32com.client.Dispatch('ADODB.Connection')
                conexao.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
                termo = nome.replace("'", "''")
                filtro_pasta = " AND System.ItemType <> 'Directory'" if tipo == 'programa' else ''
                consulta = (
                    f"SELECT TOP {limite} System.ItemNameDisplay, System.ItemPathDisplay "
                    f"FROM SYSTEMINDEX WHERE CONTAINS(System.FileName, '\"{termo}*\"'){filtro_pasta}"
                )
                conjunto = win32com.client.Dispatch('ADODB.Recordset')
                conjunto.Open(consulta, conexao)
                candidatos = []
                n = norm(nome)
                while not conjunto.EOF:
                    rotulo = conjunto.Fields.Item('System.ItemNameDisplay').Value
                    caminho = conjunto.Fields.Item('System.ItemPathDisplay').Value
                    if rotulo and caminho:
                        ext = Path(rotulo).suffix.lower()
                        if tipo == 'programa' and ext not in ('.exe', '.lnk', '.bat', '.cmd', '.com', '.msi'):
                            conjunto.MoveNext()
                            continue
                        r = norm(Path(rotulo).stem)
                        score = 1.0 if n == r else .95 if n in r or r in n else difflib.SequenceMatcher(None, n, r).ratio()
                        if score >= .55:
                            candidatos.append((score, rotulo, caminho))
                    conjunto.MoveNext()
                conjunto.Close()
                conexao.Close()
            if not candidatos:
                return None
            candidatos.sort(reverse=True)
            return candidatos[0][1], candidatos[0][2]
        except Exception as e:
            self.registrar('AVISO Windows Search indisponível, usando índice próprio: ' + repr(e))
            return None

    def iniciar_indice(self, forcar=False):
        if getattr(getattr(self,'modo_jogo',None),'ativo',False):return
        if self.indexando.is_set():
            return
        if not forcar and self.db.exists() and time.time() - self.db.stat().st_mtime < 7 * 86400:
            return
        self.indexando.set()
        threading.Thread(target=self.indexar_computador, daemon=True).start()

    def indexar_computador(self):
        self.indexando.set()
        self.db.parent.mkdir(exist_ok=True)
        temporario = self.db.with_suffix('.novo.db')
        try:
            if temporario.exists():
                temporario.unlink()
            con = sqlite3.connect(temporario)
            con.execute('CREATE TABLE itens(nome TEXT, normalizado TEXT, caminho TEXT PRIMARY KEY, tipo TEXT)')
            con.execute('CREATE INDEX busca_nome ON itens(normalizado)')
            lote = []
            total = 0
            unidades = []
            for letra in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                raiz = letra + ':\\'
                if os.path.exists(raiz) and ctypes.windll.kernel32.GetDriveTypeW(raiz) == 3:
                    unidades.append(raiz)
            for unidade in unidades:
                for atual, pastas, arquivos in os.walk(unidade, topdown=True, onerror=lambda _e: None):
                    if not self.aguardar_indexacao():con.close();return
                    pastas[:] = [p for p in pastas if p.lower() not in IGNORAR_PASTAS]
                    for pasta in pastas:
                        caminho = os.path.join(atual, pasta)
                        lote.append((pasta, norm(pasta), caminho, 'pasta'))
                        total += 1
                    for nome in arquivos:
                        caminho = os.path.join(atual, nome)
                        ext = Path(nome).suffix.lower()
                        tipo = 'programa' if ext in ('.exe', '.lnk', '.bat', '.cmd', '.com', '.msi') else 'arquivo'
                        lote.append((nome, norm(Path(nome).stem), caminho, tipo))
                        total += 1
                        if len(lote) >= 1000:
                            if not self.aguardar_indexacao():con.close();return
                            con.executemany('INSERT OR IGNORE INTO itens VALUES(?,?,?,?)', lote)
                            con.commit()
                            lote = []
                            # Cede um instante de CPU/disco entre lotes: a varredura
                            # completa não precisa ser instantânea, mas não pode
                            # deixar a escuta de voz "engasgada" enquanto roda.
                            time.sleep(.01)
            if lote:
                con.executemany('INSERT OR IGNORE INTO itens VALUES(?,?,?,?)', lote)
            con.commit()
            con.close()
            os.replace(temporario, self.db)
            self.ui(0, lambda: self.mostrar(f'Índice de apoio atualizado: {total} itens encontrados.'))
            self.ui(5000, self.root.withdraw)
        except Exception as e:
            self.registrar('ERRO indexar_computador: ' + repr(e))
            self.ui(0, lambda msg=str(e): self.mostrar('Não consegui concluir o índice: ' + msg))
        finally:
            self.indexando.clear()

    def aguardar_indexacao(self):
        while getattr(getattr(self,'modo_jogo',None),'ativo',False):
            if self.encerrar.wait(.25):return False
        return not self.encerrar.is_set()

    def buscar_indice(self, nome, tipo=None):
        rapido = self.buscar_windows_search(nome, tipo)
        if rapido:
            return rapido
        if not self.db.exists():
            return None
        n = norm(nome)
        palavras = [p for p in n.split() if len(p) > 1]
        if not palavras:
            return None
        con = sqlite3.connect(self.db)
        where = ' AND '.join('normalizado LIKE ?' for _ in palavras)
        params = ['%' + p + '%' for p in palavras]
        if tipo:
            where += ' AND tipo=?'
            params.append(tipo)
        linhas = con.execute('SELECT nome,normalizado,caminho FROM itens WHERE ' + where + ' LIMIT 100', params).fetchall()
        con.close()
        if not linhas:
            return None
        avaliados = []
        for rotulo, normalizado, caminho in linhas:
            score = 1.0 if n == normalizado else .95 if n in normalizado or normalizado in n else difflib.SequenceMatcher(None, n, normalizado).ratio()
            avaliados.append((score, rotulo, caminho))
        avaliados.sort(reverse=True)
        return avaliados[0][1], avaliados[0][2]

    def abrir_arquivo(self, nome):
        achado = self.buscar_indice(nome)
        if not achado:
            raise FileNotFoundError('Arquivo não encontrado: ' + nome)
        rotulo, caminho = achado
        os.startfile(caminho)
        return rotulo

    def localizar_atalho(self, nome):
        pastas = [
            Path(os.environ.get('APPDATA', '')) / 'Microsoft/Windows/Start Menu/Programs',
            Path(os.environ.get('PROGRAMDATA', '')) / 'Microsoft/Windows/Start Menu/Programs',
            Path.home() / 'Desktop',
            Path(os.environ.get('PUBLIC', 'C:/Users/Public')) / 'Desktop',
        ]
        candidatos = []
        for pasta in pastas:
            if pasta.exists():
                for arq in pasta.rglob('*.lnk'):
                    rotulo = norm(arq.stem)
                    score = 1.0 if nome == rotulo else .92 if nome in rotulo or rotulo in nome else difflib.SequenceMatcher(None, nome, rotulo).ratio()
                    if score >= .68:
                        candidatos.append((score, arq))
        if not candidatos:
            return None
        candidatos.sort(key=lambda x: x[0], reverse=True)
        if len(candidatos) > 1 and candidatos[0][0] - candidatos[1][0] < .04 and candidatos[0][0] < .9:
            return None
        return candidatos[0][1]

    def localizar_jogo_steam(self, nome):
        raizes = []
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as chave:
                raizes.append(Path(winreg.QueryValueEx(chave, 'SteamPath')[0]))
        except OSError:
            pass
        comum = Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Steam'
        if comum.exists():
            raizes.append(comum)
        bibliotecas = []
        for raiz in raizes:
            bibliotecas.append(raiz)
            arquivo = raiz / 'steamapps' / 'libraryfolders.vdf'
            if arquivo.exists():
                try:
                    texto = arquivo.read_text(encoding='utf-8', errors='ignore')
                    bibliotecas.extend(Path(x.replace('\\\\', '\\')) for x in re.findall(r'"path"\s+"([^"]+)"', texto))
                except OSError:
                    pass
        jogos = []
        for biblioteca in dict.fromkeys(bibliotecas):
            for manifesto in (biblioteca / 'steamapps').glob('appmanifest_*.acf'):
                try:
                    texto = manifesto.read_text(encoding='utf-8', errors='ignore')
                    mid = re.search(r'"appid"\s+"(\d+)"', texto)
                    mnome = re.search(r'"name"\s+"([^"]+)"', texto)
                    if mid and mnome:
                        rotulo = norm(mnome.group(1))
                        score = 1.0 if nome == rotulo else .94 if nome in rotulo or rotulo in nome else difflib.SequenceMatcher(None, nome, rotulo).ratio()
                        if score >= .58:
                            jogos.append((score, mnome.group(1), mid.group(1)))
                except OSError:
                    pass
        if not jogos:
            return None
        jogos.sort(reverse=True)
        if len(jogos) > 1 and jogos[0][0] - jogos[1][0] < .04 and jogos[0][0] < .88:
            return None
        return jogos[0][1], jogos[0][2]

    def abrir_app(self, t):
        n = norm(t)
        if not n:raise RuntimeError('Diga o nome do programa que deseja abrir.')
        n = re.sub(r'\b(programa|aplicativo|app|jogo|game|site|pagina|da|do|na|no)\b', ' ', n)
        n = re.sub(r'\s+', ' ', n).strip()
        mapa = {
            'chrome': ('https://google.com', 'Chrome'), 'google': ('https://google.com', 'Google Chrome'),
            'navegador': ('https://google.com', 'navegador'), 'youtube': ('https://youtube.com', 'YouTube'),
            'spotify': ('spotify:', 'Spotify'), 'calculadora': ('calc.exe', 'calculadora'),
            'bloco de notas': ('notepad.exe', 'Bloco de Notas'), 'arquivos': ('explorer.exe', 'Explorador de Arquivos'),
            'explorador': ('explorer.exe', 'Explorador de Arquivos'), 'steam': ('steam://open/main', 'Steam'),
            'stem': ('steam://open/main', 'Steam'),
        }
        # Catálogo seguro de endereços oficiais. Não usa o primeiro resultado
        # de uma busca, evitando abrir por engano anúncios ou páginas falsas.
        sites = {
            'netflix': ('https://www.netflix.com/br/', 'Netflix'),
            'globo esporte': ('https://ge.globo.com/', 'Globo Esporte'),
            'ge': ('https://ge.globo.com/', 'Globo Esporte'),
            'globoplay': ('https://globoplay.globo.com/', 'Globoplay'),
            'instagram': ('https://www.instagram.com/', 'Instagram'),
            'facebook': ('https://www.facebook.com/', 'Facebook'),
            'whatsapp web': ('https://web.whatsapp.com/', 'WhatsApp Web'),
            'whatsapp': ('https://web.whatsapp.com/', 'WhatsApp Web'),
            'gmail': ('https://mail.google.com/', 'Gmail'),
            'outlook': ('https://outlook.live.com/mail/', 'Outlook'),
            'twitch': ('https://www.twitch.tv/', 'Twitch'),
            'prime video': ('https://www.primevideo.com/', 'Prime Video'),
            'amazon prime': ('https://www.primevideo.com/', 'Prime Video'),
            'disney plus': ('https://www.disneyplus.com/', 'Disney Plus'),
            'hbo max': ('https://www.max.com/br/pt', 'Max'),
            'max': ('https://www.max.com/br/pt', 'Max'),
            'tiktok': ('https://www.tiktok.com/', 'TikTok'),
            'twitter': ('https://x.com/', 'X'),
            'mercado livre': ('https://www.mercadolivre.com.br/', 'Mercado Livre'),
            'amazon': ('https://www.amazon.com.br/', 'Amazon'),
        }
        site = next((v for k, v in sites.items() if n == k or (len(k) > 3 and k in n)), None)
        if site:
            endereco, nome = site
            webbrowser.open(endereco)
            return nome
        item = next((v for k, v in mapa.items() if k in n), None)
        if item:
            d, nome = item
            if d.startswith('http'):
                webbrowser.open(d)
            elif ':' in d:
                os.startfile(d)
            else:
                subprocess.Popen([d])
            return nome
        jogo = self.localizar_jogo_steam(n)
        if jogo:
            nome, appid = jogo
            os.startfile('steam://rungameid/' + appid)
            return nome
        atalho = self.localizar_atalho(n)
        if atalho:
            os.startfile(str(atalho))
            return atalho.stem
        instalado = self.buscar_indice(n, 'programa')
        if instalado:
            rotulo, caminho = instalado
            os.startfile(caminho)
            return rotulo
        qualquer = self.buscar_indice(n)
        if qualquer:
            rotulo, caminho = qualquer
            os.startfile(caminho)
            return rotulo
        # Se não for aplicativo, atalho, arquivo ou site conhecido, abre uma
        # pesquisa pelo site oficial. Isso permite dizer “abra [nome]” sem
        # cadastrar tudo e sem confiar automaticamente no primeiro resultado.
        webbrowser.open('https://www.google.com/search?q=' + urllib.parse.quote_plus(n + ' site oficial'))
        return 'pesquisa por ' + t

    def fechar_app(self, t):
        alvo = norm(t)
        alvo = re.sub(r'\b(programa|aplicativo|app|jogo|game|da|do|na|no)\b', ' ', alvo)
        alvo = re.sub(r'\s+', ' ', alvo).strip()
        if not alvo:
            raise FileNotFoundError('Nome do programa ou jogo não informado')
        compactado = lambda s: re.sub(r'[^a-z0-9]', '', norm(s))
        qa = compactado(alvo)
        candidatos = []
        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def janela(hwnd, _):
            if not ctypes.windll.user32.IsWindowVisible(hwnd):
                return True
            tam = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if not tam:
                return True
            buf = ctypes.create_unicode_buffer(tam + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, tam + 1)
            titulo = buf.value.strip()
            if not titulo:
                return True
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            rotulo = compactado(titulo)
            score = 1 if qa == rotulo else .96 if qa in rotulo or rotulo in qa else difflib.SequenceMatcher(None, qa, rotulo).ratio()
            if score >= .58:
                candidatos.append((score, hwnd, titulo, pid.value))
            return True

        ctypes.windll.user32.EnumWindows(EnumProc(janela), 0)
        if candidatos:
            candidatos.sort(key=lambda x: x[0], reverse=True)
            score, hwnd, titulo, _pid = candidatos[0]
            if len(candidatos) > 1 and score - candidatos[1][0] < .035 and score < .88:
                raise RuntimeError('Encontrei mais de uma janela parecida')
            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
            return titulo
        saida = subprocess.check_output(
            ['tasklist.exe', '/FO', 'CSV', '/NH'], text=True, encoding='utf-8', errors='ignore',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        processos = []
        proibidos = {'system', 'registry', 'smss', 'csrss', 'wininit', 'services', 'lsass', 'svchost', 'winlogon', 'explorer', 'dwm', 'python', 'pythonw'}
        for linha in csv.reader(saida.splitlines()):
            if len(linha) < 2:
                continue
            nome = Path(linha[0]).stem
            normal = compactado(nome)
            if normal in proibidos:
                continue
            score = 1 if qa == normal else .94 if qa in normal or normal in qa else difflib.SequenceMatcher(None, qa, normal).ratio()
            if score >= .67:
                processos.append((score, linha[1], nome))
        if not processos:
            raise FileNotFoundError('Programa ou jogo aberto não encontrado: ' + t)
        processos.sort(reverse=True)
        score, pid, nome = processos[0]
        if len(processos) > 1 and score - processos[1][0] < .035 and score < .9:
            raise RuntimeError('Encontrei mais de um processo parecido')
        subprocess.run(['taskkill.exe', '/PID', pid, '/T'], check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return nome

    def janelas_chrome(self):
        janelas = []
        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def coletar(hwnd, _):
            if not ctypes.windll.user32.IsWindowVisible(hwnd):
                return True
            classe = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, classe, 256)
            if classe.value != 'Chrome_WidgetWin_1':
                return True
            tam = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            titulo = ctypes.create_unicode_buffer(tam + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, titulo, tam + 1)
            pid=ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            try:
                if psutil.Process(pid.value).name().lower() != 'chrome.exe':return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):return True
            if titulo.value:
                janelas.append((hwnd, titulo.value))
            return True

        ctypes.windll.user32.EnumWindows(EnumProc(coletar), 0)
        return janelas

    def focar_janela(self, hwnd):
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(.18)

    @staticmethod
    def atalho(*teclas):
        for tecla in teclas:
            ctypes.windll.user32.keybd_event(tecla, 0, 0, 0)
        for tecla in reversed(teclas):
            ctypes.windll.user32.keybd_event(tecla, 0, 2, 0)

    def nova_aba_chrome(self):
        janelas = self.janelas_chrome()
        if not janelas:
            webbrowser.open('https://google.com')
            return 'Abrindo o Chrome.'
        self.focar_janela(janelas[0][0])
        self.atalho(0x11, 0x54)
        return 'Abri uma nova aba no Chrome.'

    def fechar_aba_chrome(self, alvo=''):
        janelas = self.janelas_chrome()
        if not janelas:
            raise FileNotFoundError('Chrome não está aberto')
        hwnd, _titulo = janelas[0]
        self.focar_janela(hwnd)
        alvo = norm(alvo)
        if not alvo:
            self.atalho(0x11, 0x57)
            return 'Fechei a aba atual do Chrome.'
        primeiro = ''
        visitados = set()
        for _ in range(35):
            tam = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(tam + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, tam + 1)
            atual = buf.value
            chave = norm(atual)
            if not primeiro:
                primeiro = chave
            elif chave == primeiro:
                break
            if chave in visitados:
                break
            visitados.add(chave)
            if alvo in chave:
                nome = re.sub(r'\s*-\s*Google Chrome\s*$', '', atual, flags=re.I)
                self.atalho(0x11, 0x57)
                return 'Fechei a aba ' + nome + '.'
            self.atalho(0x11, 0x09)
            time.sleep(.16)
        raise FileNotFoundError('Aba do Chrome não encontrada: ' + alvo)

    def registrar(self, texto):
        try:
            pasta = self.base / 'dados'
            pasta.mkdir(exist_ok=True)
            with (pasta / 'historico.log').open('a', encoding='utf-8') as arq:
                arq.write(time.strftime('%Y-%m-%d %H:%M:%S ') + texto.replace('\n', ' ')[:500] + '\n')
        except Exception:
            pass
