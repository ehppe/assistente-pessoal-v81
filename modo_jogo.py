"""Preparação conservadora para jogos: apps escolhidos e energia reversível."""
import ctypes,json,os,re,subprocess,threading,time
from pathlib import Path
import psutil
from motor import preparar_pedido

APLICATIVOS={
    'chrome.exe':'Google Chrome','msedge.exe':'Microsoft Edge','firefox.exe':'Firefox',
    'brave.exe':'Brave','opera.exe':'Opera','spotify.exe':'Spotify',
    'telegram.exe':'Telegram','whatsapp.exe':'WhatsApp','slack.exe':'Slack',
    'teams.exe':'Teams clássico','ms-teams.exe':'Microsoft Teams','zoom.exe':'Zoom',
}
ALTO='8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'
GUID=r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'

def interpretar(texto):
    n=preparar_pedido(texto)
    if n in ('modo jogo','ativar modo jogo','modo de jogos','modo de jogo','ativar modo de jogo','ative modo de jogo','ativar o modo de jogo','ative o modo de jogo','preparar para jogar','prepare para jogar','otimizar para jogar','otimize para jogar'):return 'ativar'
    if n in ('sair do modo de jogo','desativar modo de jogo','desative modo de jogo','desativar o modo de jogo','desative o modo de jogo','modo normal','voltar ao normal','restaurar modo normal'):return 'desativar'
    if n in ('status do modo de jogo','estado do modo de jogo','relatorio do modo de jogo'):return 'status'
    if n in ('configurar modo de jogo','configure modo de jogo','configurar o modo de jogo'):return 'configurar'
    return None

def selecionados(config):
    lista=config.get('modo_jogo_fechar',[])
    return sorted({x.lower() for x in lista if isinstance(x,str) and x.lower() in APLICATIVOS}) if isinstance(lista,list) else []

class WindowsJogo:
    def memoria(self):return psutil.virtual_memory().available

    def processos(self):
        dono=psutil.Process().username();saida=[]
        for p in psutil.process_iter(['pid','name','username','create_time','memory_info']):
            try:
                d=p.info;nome=(d['name'] or '').lower()
                if nome not in APLICATIVOS or d['username']!=dono or d['pid']==os.getpid():continue
                saida.append({'pid':d['pid'],'nome':nome,'criado':d['create_time'],'rss':d['memory_info'].rss if d['memory_info'] else 0})
            except (psutil.Error,KeyError):continue
        return saida

    def mesmo_processo(self,item):
        try:
            p=psutil.Process(item['pid'])
            return (p.name().lower()==item['nome'] and item['nome'] in APLICATIVOS and
                    p.create_time()==item['criado'] and p.username()==psutil.Process().username() and p.pid!=os.getpid())
        except psutil.Error:return False

    def fechar_janelas(self,item):
        # Identidade do processo e associação da janela são conferidas novamente.
        if not self.mesmo_processo(item):return 0
        from ctypes import wintypes as w
        u=ctypes.WinDLL('user32',use_last_error=True)
        callback=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
        u.EnumWindows.argtypes=[callback,w.LPARAM];u.EnumWindows.restype=w.BOOL
        u.IsWindowVisible.argtypes=[w.HWND];u.IsWindowVisible.restype=w.BOOL
        u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)];u.GetWindowThreadProcessId.restype=w.DWORD
        u.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];u.PostMessageW.restype=w.BOOL
        enviados=0
        def visitar(hwnd,_):
            nonlocal enviados
            if not u.IsWindowVisible(hwnd):return True
            pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value==item['pid'] and self.mesmo_processo(item):
                if u.PostMessageW(hwnd,0x0010,0,0):enviados+=1
            return True
        u.EnumWindows(callback(visitar),0)
        return enviados

    def aguardar(self):time.sleep(.8)

    def powercfg(self,*args):
        if os.name!='nt':raise RuntimeError('Este recurso requer Windows.')
        exe=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'/'powercfg.exe'
        ret=subprocess.run([str(exe),*args],capture_output=True,text=True,errors='replace',timeout=8,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if ret.returncode:raise RuntimeError('O Windows não aceitou a consulta ou troca do plano de energia.')
        return ret.stdout

    def plano_atual(self):
        m=re.search(GUID,self.powercfg('/getactivescheme'))
        if not m:raise RuntimeError('Não consegui identificar o plano de energia atual.')
        return m[0].lower()

    def alto_disponivel(self):return ALTO in self.powercfg('/list').lower()

    def aplicar_plano(self,guid):
        if not isinstance(guid,str) or not re.fullmatch(GUID,guid):raise ValueError('Plano inválido.')
        self.powercfg('/setactive',guid)
        if self.plano_atual()!=guid.lower():raise RuntimeError('A troca do plano de energia não foi confirmada.')

    def prioridade(self,valor=None):
        p=psutil.Process()
        if valor is None:return p.nice()
        p.nice(valor)

    def prioridade_normal(self):return getattr(psutil,'NORMAL_PRIORITY_CLASS',0x20)

    def gamebar_estado(self):
        """Lê o valor atual de GameDVR_Enabled do registro (None quando a
        chave/valor ainda não existe — o Windows então já se comporta como
        se estivesse ativado, então tratamos None como "estava ligado")."""
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'System\GameConfigStore') as chave:
                valor, _ = winreg.QueryValueEx(chave, 'GameDVR_Enabled')
                return int(valor)
        except (FileNotFoundError, OSError):
            return None

    def gamebar_definir(self, ativo):
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'System\GameConfigStore') as chave:
            winreg.SetValueEx(chave, 'GameDVR_Enabled', 0, winreg.REG_DWORD, 1 if ativo else 0)

    def indexador_ativo(self):
        """Consulta o serviço "Windows Search" (WSearch) — indexa arquivos em
        segundo plano; pausar durante o jogo libera um pouco de disco/CPU."""
        if os.name != 'nt':raise RuntimeError('Este recurso requer Windows.')
        r = subprocess.run(['sc', 'query', 'WSearch'], capture_output=True, text=True,
            errors='replace', timeout=8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return 'RUNNING' in r.stdout

    def indexador_definir(self, ativo):
        if os.name != 'nt':raise RuntimeError('Este recurso requer Windows.')
        r = subprocess.run(['net', 'start' if ativo else 'stop', 'WSearch'], capture_output=True,
            text=True, errors='replace', timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if r.returncode != 0:
            raise RuntimeError('O Windows não aceitou ' + ('retomar' if ativo else 'pausar') + ' o Indexador de Pesquisa.')

class ModoJogo:
    def __init__(self,base,sistema=None):
        self.base=Path(base);self.sistema=sistema or WindowsJogo();self.lock=threading.RLock()
        self.arquivo=self.base/'dados'/'modo-jogo-energia.json';self.ativo=False
        self.energia=None;self.erro_estado='';self.prioridade_anterior=None
        self.ultimo='Modo de jogo desativado.'
        if self.arquivo.exists():
            try:
                d=json.loads(self.arquivo.read_text(encoding='utf-8'))
                if not isinstance(d,dict) or not all(isinstance(d.get(k),str) and re.fullmatch(GUID,d[k]) for k in ('anterior','aplicado')):raise ValueError()
                self.energia=d
            except (OSError,ValueError):self.erro_estado='O backup de energia está inválido. Confira dados/modo-jogo-energia.json; não alterei o plano.'
        # Backup separado (mesmo esquema de "persistir antes de mudar, restaurar
        # depois") para os dois ajustes opcionais de desempenho: Game Bar e
        # Indexador de Pesquisa. Fica num arquivo à parte porque não tem nada a
        # ver com o plano de energia — cada um se recupera sozinho de uma queda.
        self.arquivo_tweaks=self.base/'dados'/'modo-jogo-tweaks.json';self.tweaks=None;self.erro_tweaks=''
        if self.arquivo_tweaks.exists():
            try:
                d=json.loads(self.arquivo_tweaks.read_text(encoding='utf-8'))
                if not isinstance(d,dict) or 'gamedvr_anterior' not in d or 'indexador_anterior' not in d:raise ValueError()
                self.tweaks=d
            except (OSError,ValueError):self.erro_tweaks='O backup de ajustes do modo de jogo está inválido. Confira dados/modo-jogo-tweaks.json; não mexi no Game Bar nem no Indexador.'

    def guardar_energia(self,anterior):
        estado={'anterior':anterior,'aplicado':ALTO}
        self.arquivo.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.arquivo.with_suffix('.tmp');tmp.write_text(json.dumps(estado),encoding='utf-8');tmp.replace(self.arquivo)
        self.energia=estado

    def restaurar_energia(self):
        if self.erro_estado:return self.erro_estado
        if not self.energia:return ''
        d=self.energia;atual=self.sistema.plano_atual()
        if atual==d['aplicado'] and atual!=d['anterior']:
            self.sistema.aplicar_plano(d['anterior']);mensagem='Plano de energia anterior restaurado.'
        elif atual==d['anterior']:mensagem='Plano de energia anterior mantido.'
        else:mensagem='O plano foi alterado fora do Neymar; mantive sua escolha atual.'
        self.arquivo.unlink(missing_ok=True);self.energia=None
        return mensagem

    def _guardar_tweak(self,chave,valor):
        estado=dict(self.tweaks or {'gamedvr_anterior':None,'indexador_anterior':None})
        estado[chave]=valor
        self.arquivo_tweaks.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.arquivo_tweaks.with_suffix('.tmp2');tmp.write_text(json.dumps(estado),encoding='utf-8');tmp.replace(self.arquivo_tweaks)
        self.tweaks=estado

    def restaurar_tweaks(self):
        if self.erro_tweaks:return self.erro_tweaks
        if not self.tweaks:return ''
        d=self.tweaks;mensagens=[]
        anterior_gdvr=d.get('gamedvr_anterior')
        if anterior_gdvr is not None:
            try:
                self.sistema.gamebar_definir(bool(anterior_gdvr));mensagens.append('Game Bar restaurado.')
            except Exception:mensagens.append('Não consegui restaurar o Game Bar; confira em Configurações do Windows > Jogos.')
        if d.get('indexador_anterior'):
            try:
                self.sistema.indexador_definir(True);mensagens.append('Indexador de Pesquisa retomado.')
            except Exception:mensagens.append('Não consegui retomar o Indexador de Pesquisa; ligue o serviço "Windows Search" manualmente.')
        self.arquivo_tweaks.unlink(missing_ok=True);self.tweaks=None
        return ' '.join(mensagens)

    def ativar(self,config,cancelado=lambda:False):
        with self.lock:
            if self.ativo:return 'O modo de jogo já está ativo. '+self.ultimo
            if cancelado():return 'Ativação cancelada.'
            if self.energia:
                try:self.restaurar_energia()
                except Exception:return 'Não ativei: restaure o plano pendente usando Sair do modo de jogo.'
            if self.tweaks:
                try:self.restaurar_tweaks()
                except Exception:return 'Não ativei: restaure os ajustes pendentes usando Sair do modo de jogo.'
            self.ativo=True;notas=[]
            try:
                self.prioridade_anterior=self.sistema.prioridade()
                self.sistema.prioridade(self.sistema.prioridade_normal())
            except Exception:notas.append('Não foi possível ajustar a prioridade do Neymar.')
            if config.get('modo_jogo_alto_desempenho',False):
                try:
                    if self.erro_estado:raise RuntimeError(self.erro_estado)
                    if not self.sistema.alto_disponivel():notas.append('Alto desempenho não está disponível neste Windows; plano mantido.')
                    else:
                        anterior=self.sistema.plano_atual()
                        if anterior!=ALTO:
                            self.guardar_energia(anterior)  # Persistir ANTES de modificar o Windows.
                            self.sistema.aplicar_plano(ALTO)
                        notas.append('Plano de alto desempenho ativo.')
                except Exception as e:notas.append('Energia: '+str(e))
            if config.get('modo_jogo_gamebar',False):
                try:
                    if self.erro_tweaks:raise RuntimeError(self.erro_tweaks)
                    anterior_gdvr=self.sistema.gamebar_estado()
                    if anterior_gdvr!=0:
                        self._guardar_tweak('gamedvr_anterior',1 if anterior_gdvr is None else anterior_gdvr)
                        self.sistema.gamebar_definir(False)
                    notas.append('Game Bar/gravação desativados para o jogo.')
                except Exception as e:notas.append('Game Bar: '+str(e))
            if config.get('modo_jogo_pausar_indexacao',False):
                try:
                    if self.erro_tweaks:raise RuntimeError(self.erro_tweaks)
                    if self.sistema.indexador_ativo():
                        self._guardar_tweak('indexador_anterior',True)
                        self.sistema.indexador_definir(False)
                        notas.append('Indexador de Pesquisa pausado.')
                except Exception as e:notas.append('Indexador: '+str(e))
            try:
                antes=self.sistema.memoria();itens=self.sistema.processos();nomes=selecionados(config);pedidos=set();sem_janela=set()
                for item in itens:
                    if cancelado():
                        self.desativar();return 'Ativação interrompida; ajustes restaurados quando possível. Programas já fechados não são reabertos. '+self.ultimo
                    if item['nome'] not in nomes:continue
                    try:
                        if self.sistema.fechar_janelas(item):pedidos.add(item['nome'])
                        else:sem_janela.add(item['nome'])
                    except Exception:sem_janela.add(item['nome'])
                if pedidos:self.sistema.aguardar()
                restantes={p['nome'] for p in self.sistema.processos()}
                terminados=pedidos-restantes;abertos=(pedidos|sem_janela)&restantes
                if terminados:notas.append('Fechados: '+', '.join(APLICATIVOS[n] for n in sorted(terminados))+'.')
                if abertos:notas.append('Ainda abertos ou em segundo plano: '+', '.join(APLICATIVOS[n] for n in sorted(abertos))+'. Confira avisos para salvar; não forcei o encerramento.')
                if not pedidos and not sem_janela:notas.append('Nenhum aplicativo selecionado estava aberto.' if nomes else 'Nenhum aplicativo escolhido para fechar; selecione na tela Modo de jogo.')
                depois=self.sistema.memoria();notas.append(f'RAM disponível: {antes/2**30:.1f} → {depois/2**30:.1f} GB. A variação inclui outros processos.')
            except Exception as e:notas.append('Não concluí a verificação dos aplicativos: '+type(e).__name__+'.')
            if cancelado():self.desativar();return 'Ativação interrompida. '+self.ultimo
            self.ultimo='Modo de jogo ativo: indexação do Neymar pausada e interface com menos atualizações. '+' '.join(notas)
            return self.ultimo

    def desativar(self):
        with self.lock:
            self.ativo=False;notas=[]
            if self.prioridade_anterior is not None:
                try:
                    if self.sistema.prioridade()==self.sistema.prioridade_normal():self.sistema.prioridade(self.prioridade_anterior)
                    self.prioridade_anterior=None
                except Exception:notas.append('Não consegui restaurar a prioridade do Neymar.')
            try:
                aviso=self.restaurar_energia()
                if aviso:notas.append(aviso)
            except Exception:notas.append('Não consegui restaurar o plano de energia. O backup foi mantido; tente Sair do modo de jogo novamente.')
            try:
                aviso=self.restaurar_tweaks()
                if aviso:notas.append(aviso)
            except Exception:notas.append('Não consegui restaurar o Game Bar/Indexador. O backup foi mantido; tente Sair do modo de jogo novamente.')
            self.ultimo='Modo de jogo desativado. Indexação e interface retomadas. '+' '.join(notas)+' Os aplicativos fechados não são reabertos automaticamente.'
            return self.ultimo
