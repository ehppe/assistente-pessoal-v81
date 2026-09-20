"""Ponte privada por pipes entre o motor Tk e a interface Qt, sem servidor."""
import os
import json
import queue
import subprocess
import sys
import threading
import time

class CentralBridge:
    def __init__(self, app):
        self.app=app
        self.saida=queue.Queue(maxsize=1)
        self.eventos=queue.Queue(maxsize=32)
        self.sensor={}
        self.sensor_em_andamento=False
        self.proximo_sensor=0
        self.visivel=True
        self.preferencias={}
        self.jogo_opcoes={}
        self.aviso=""
        self.revisao=0
        self.pronto=False
        self.inicio=time.monotonic()
        self.fechado=False
        logdir=app.base/'dados';logdir.mkdir(exist_ok=True)
        self.log=open(logdir/'interface-qt.log','a',encoding='utf-8')
        try:
            self.processo=subprocess.Popen([sys.executable,str(app.base/'central_qt.py')],
                env=dict(os.environ,PYTHONIOENCODING="utf-8",PYTHONUTF8="1"),
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,
                text=True,encoding='utf-8',bufsize=1,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except Exception:
            self.log.close();raise
        threading.Thread(target=self._ler,daemon=True).start()
        threading.Thread(target=self._escrever,daemon=True).start()
        app.ui(100,self.pulso)

    def _ler(self):
        try:
            for linha in self.processo.stdout:
                if len(linha)>40000:continue
                try:
                    evento=json.loads(linha)
                    if isinstance(evento,dict):self.eventos.put_nowait(evento)
                except (ValueError,queue.Full):pass
        finally:
            self.processo.stdout.close()

    def _escrever(self):
        try:
            while True:
                dados=self.saida.get()
                if dados is None:break
                self.processo.stdin.write(json.dumps(dados,ensure_ascii=False,allow_nan=False)+'\n')
                self.processo.stdin.flush()
        except (OSError,ValueError):pass
        finally:
            try:self.processo.stdin.close()
            except OSError:pass

    def enviar(self,dados):
        try:self.saida.put_nowait(dados)
        except queue.Full:
            try:self.saida.get_nowait()
            except queue.Empty:pass
            try:self.saida.put_nowait(dados)
            except queue.Full:pass

    def mostrar(self):
        self.visivel=True
        self.mostrar_pendente=True

    def sensores(self):
        from util import leitura_sistema
        try:self.sensor=leitura_sistema()
        except Exception:self.sensor={}
        finally:self.sensor_em_andamento=False

    def carregar_preferencias(self):
        from preferencias_qt import esquema
        from modo_jogo import APLICATIVOS,selecionados
        self.preferencias=esquema(self.app)
        self.jogo_opcoes={'programas':[{'nome':n,'rotulo':r} for n,r in APLICATIVOS.items()],
                         'selecionados':selecionados(self.app.config),
                         'alto':self.app.config.get('modo_jogo_alto_desempenho',False),
                         'gamebar':self.app.config.get('modo_jogo_gamebar',False),
                         'indexacao':self.app.config.get('modo_jogo_pausar_indexacao',False)}
        self.revisao+=1

    def executar(self,e):
        a=self.app
        acao=e.get('acao')
        if acao=='pronto':
            self.pronto=True;self.carregar_preferencias()
        elif acao in ('salvar_config','salvar_jogo','ativar_jogo'):
            from preferencias_qt import gravar,gravar_jogo
            try:
                entrada=e.get('dados',{})
                self.aviso=gravar(a,entrada) if acao=='salvar_config' else gravar_jogo(a,entrada)
                self.carregar_preferencias()
                if acao=='ativar_jogo':a.processar('ativar modo de jogo')
            except ValueError as erro:self.aviso=str(erro)
            except Exception:self.aviso='Não consegui concluir o salvamento. Confira as permissões e os dados.'
        elif acao=='desativar_jogo':a.processar('sair do modo de jogo')
        elif acao=='recarregar_config':self.carregar_preferencias()
        elif acao=='testar_voz':
            if a.ocupado.is_set() or not a.voz_concluida.is_set():self.aviso='Aguarde o pedido terminar.'
            elif not a.config.get('responder_por_voz'):self.aviso='Ative Falar respostas e salve.'
            else:
                nome=str(a.config.get('nome_usuario','')).strip()
                a.falar('Olá'+((', '+nome) if nome else '')+'. Neymar à disposição.')

        elif acao=='visivel':self.visivel=bool(e.get('valor'))
        elif acao=='ouvir':a.ativar()
        elif acao=='parar':a.parar_fala()
        elif acao=='cancelar':a.cancelar_tudo()
        elif acao=='config':a.abrir_configuracoes()
        elif acao=='jogo':a.abrir_modo_jogo()
        elif acao=='classica':a.abrir_conversa_classica()
        elif acao=='nova':a.apagar_chat()
        elif acao=='enviar' and isinstance(e.get('texto'),str):a.processar(e['texto'][:8000])
        elif acao=='confirmar':
            proposta=a.agenda.proposta()
            if proposta and e.get('token')==proposta['token']:
                a.responder_oferta(True,proposta['token'])
        elif acao=='energia':
            token=e.get('token')
            if token is not None and token==a.confirmacao.estado()[1]:
                a.resolver_confirmacao(True,token)

    def fechar(self):
        if self.fechado:return
        self.fechado=True
        self.enviar(None)
        if self.processo.poll() is None:self.processo.terminate()
        self.log.close()

    def pulso(self):
        a=self.app
        if a.encerrar.is_set():self.fechar();return
        if self.processo.poll() is not None or (not self.pronto and time.monotonic()-self.inicio>20):
            self.fechar()
            a.central_qt=None
            a.registrar('Interface Qt indisponível; usando a interface clássica. Consulte dados/interface-qt.log.')
            a.abrir_conversa_classica()
            return
        for _ in range(32):
            try:e=self.eventos.get_nowait()
            except queue.Empty:break
            try:self.executar(e)
            except Exception as erro:a.registrar('Central: '+type(erro).__name__)
        agora=time.monotonic()
        if self.visivel and not self.sensor_em_andamento and agora>=self.proximo_sensor:
            self.proximo_sensor=agora+8;self.sensor_em_andamento=True
            threading.Thread(target=self.sensores,daemon=True).start()
        if self.visivel:
            from util import nivel_reativo
            estado=('Pausado' if a.pausado.is_set() else 'Ouvindo' if a.ativo_ate>time.time()
                    else 'Transcrevendo' if a.transcrevendo.is_set() else 'Falando' if not a.voz_concluida.is_set()
                    else 'Pensando' if a.ocupado.is_set() else 'Pronto')
            proposta=a.agenda.proposta()
            pendente,token=a.confirmacao.estado()
            dados={'preferencias':self.preferencias,'jogoOpcoes':self.jogo_opcoes,'revisao':self.revisao,'aviso':self.aviso,'jogoStatus':a.modo_jogo.ultimo,'estado':estado,'falando':not a.voz_concluida.is_set(),'jogo':a.modo_jogo.ativo,
                'provedor':a.config.get('provedor_ia','ollama'),'voz':a.config.get('provedor_voz','windows'),
                'nomeUsuario':a.config.get('nome_usuario',''),'nomeAssistente':a.config.get('nome_assistente','Neymar'),
                'microfone':str(getattr(a,'status_microfone',''))[:200],
                'microfoneNivel':nivel_reativo(getattr(a,'nivel_microfone',0)),
                'historico':a.historico_comandos[-40:],'sensor':self.sensor,
                'proposta':proposta or {},'energia':bool(pendente),'tokenEnergia':token,
                'status':a.ultimo_status[:220],
                'mostrar':getattr(self,'mostrar_pendente',False)}
            self.mostrar_pendente=False
            self.enviar(dados)
        a.ui(300,self.pulso)
