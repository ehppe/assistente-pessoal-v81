"""Escuta local; síntese em processo separado para conter falhas nativas e permitir parar."""
import json
import queue
import re
import subprocess
import sys
import threading
import time
import math
from array import array
import sounddevice as sd
from vosk import KaldiRecognizer, Model
from desempenho import medir
from util import norm
from ativacao import palavra_inicial, confirmada, verificar_nome_local, DetectorChamada


class VozMixin:
    def palavra_ativacao(self,texto):
        return palavra_inicial(texto,self.config.get('nome_assistente','Neymar'))

    def tratar_texto_ouvido(self,texto):
        n=norm(texto)
        if not n or self.pausado.is_set():return
        if self.acao_pendente:
            self.ui(0,lambda g=self.geracao:self.receber_transcricao(texto,g));return
        chamada=self.palavra_ativacao(n)
        if chamada:
            resto=n.split(norm(chamada),1)[1].strip()
            if resto:self.ui(0,lambda g=self.geracao:self.receber_transcricao(resto,g))
            else:self.ui(0,self.ativar)
        elif time.time()<self.ativo_ate:
            self.ativo_ate=0;self.ui(0,lambda g=self.geracao:self.receber_transcricao(texto,g))

    def callback(self,dados,_f,_t,_status):
        amostras=array('h',bytes(dados))
        self.nivel_microfone=math.sqrt(sum(v*v for v in amostras)/max(1,len(amostras)))/32768
        if self.pausado.is_set() or self.transcrevendo.is_set():return
        if self.falando.is_set() and not self.config.get('interromper_por_voz',True):return
        try:self.audio.put_nowait(bytes(dados))
        except queue.Full:
            try:self.audio.get_nowait();self.audio.put_nowait(bytes(dados))
            except (queue.Empty,queue.Full):pass

    def ouvir(self):
        # Falha no dispositivo não encerra a escuta permanentemente.
        while not self.encerrar.is_set():
            try:
                if self.modelo_vosk.exists():self.ouvir_vosk()
                else:
                    self.status_microfone='Modelo Vosk ausente. Execute 1 - Instalar Assistente.bat.'
                    self.encerrar.wait(5)
            except Exception as e:
                self.status_microfone='Indisponível ('+type(e).__name__+'). Confira Configurações.'
                self.registrar('MICROFONE: '+type(e).__name__)
                self.encerrar.wait(3)

    def ouvir_vosk(self):
        from reconhecimento_whisper import Reconhecedor
        modelo=Model(str(self.modelo_vosk))
        rec=KaldiRecognizer(modelo,16000)
        rec.SetWords(True)
        controle=KaldiRecognizer(modelo,16000);controle.SetWords(True)
        controle_epoca=None
        nome_assistente=self.config.get('nome_assistente','Neymar')
        chamada_audio=DetectorChamada(KaldiRecognizer(modelo,16000),nome_assistente.lower())
        if not hasattr(self,'whisper_local'):self.whisper_local=Reconhecedor(self.base)
        self.whisper_local.perfil=self.config.get('perfil_whisper','precisao')
        self.whisper_local.nome_ativacao=nome_assistente
        self.whisper_local.diagnostico=self.config.get('diagnostico_tempos',False)
        dispositivo=self.config.get('microfone');motor=self.config.get('reconhecimento','whisper')
        rotulo={'whisper':'Whisper local + ativação Vosk','groq':'Groq online + ativação Vosk','vosk':'Vosk local'}[motor]
        with sd.RawInputStream(samplerate=16000,blocksize=1600,dtype='int16',channels=1,callback=self.callback,device=dispositivo):
            self.status_microfone=rotulo+' conectado'
            estava_bloqueado=False;ultimo_parcial='';ultima_chamada=0
            gravacao=bytearray();interessado=False;geracao=self.geracao;excedeu=False;frase_em_andamento=False
            while not self.encerrar.is_set():
                if dispositivo!=self.config.get('microfone') or motor!=self.config.get('reconhecimento','whisper'):return
                if self.falando.is_set() and not self.pausado.is_set() and self.config.get('interromper_por_voz',True) and self.audio_processo is not None:
                    estava_bloqueado=True
                    epoca=getattr(self,'epoca_voz',0)
                    if controle_epoca!=epoca:controle.Reset();controle_epoca=epoca
                    try:bloco=self.audio.get(timeout=.15)
                    except queue.Empty:continue
                    if controle.AcceptWaveform(bloco):
                        from controle_fala import identificar
                        acao=identificar(json.loads(controle.Result()));controle.Reset()
                        if acao:
                            proposta=self.agenda.proposta();token=proposta['token'] if proposta else None
                            self.ui(0,lambda a=acao,e=epoca,t=token:self.controle_durante_fala(a,e,t))
                    continue
                controle.Reset();controle_epoca=None
                if self.falando.is_set() or self.pausado.is_set():
                    estava_bloqueado=True
                    while True:
                        try:self.audio.get_nowait()
                        except queue.Empty:break
                    self.encerrar.wait(.1);continue
                if estava_bloqueado or geracao!=self.geracao:
                    while True:
                        try:self.audio.get_nowait()
                        except queue.Empty:break
                    chamada_audio.reset()
                    rec.Reset();estava_bloqueado=False;ultimo_parcial=''
                    gravacao.clear();interessado=False;excedeu=False;frase_em_andamento=False;geracao=self.geracao
                try:dados=self.audio.get(timeout=.3)
                except queue.Empty:continue
                interessado=interessado or time.time()<self.ativo_ate or bool(self.acao_pendente)
                if not interessado and (self.whisper_local.pasta/'model.bin').is_file():
                    rec.Reset();gravacao.clear();frase_em_andamento=False;excedeu=False
                    if not self.config.get('ativacao_por_voz',True):
                        self.status_microfone='Ativação por voz desativada. Ative a chamada por nome nas Configurações.'
                        chamada_audio.reset();continue
                    rapido,trecho=chamada_audio.alimentar(dados)
                    if rapido:
                        self.status_microfone='Nome '+nome_assistente+' reconhecido pelo Vosk'
                        self.ui(0,lambda g=geracao:self.ativar() if g==self.geracao and self.config.get('ativacao_por_voz',True) else None)
                        continue
                    if trecho:
                        self.transcrevendo.set();self.status_microfone='Verificando chamada localmente…'
                        identificador=self.chamada_id
                        try:
                            chamou=verificar_nome_local(self.whisper_local,trecho,nome_assistente)
                            valido=(geracao==self.geracao and identificador==self.chamada_id and
                                    dispositivo==self.config.get('microfone') and motor==self.config.get('reconhecimento','whisper') and
                                    self.config.get('ativacao_por_voz',True) and not self.pausado.is_set() and not self.encerrar.is_set())
                            if chamou and valido:self.ui(0,lambda g=geracao:self.ativar() if g==self.geracao else None)
                            self.status_microfone=rotulo+' conectado · '+('nome reconhecido' if chamou else 'nome não identificado; use Ouvir pedido')
                        except Exception as e:
                            self.status_microfone='Ativação local falhou. Execute o instalador 5 ou use Ouvir pedido.'
                            self.registrar('ATIVAÇÃO LOCAL: '+type(e).__name__)
                        finally:
                            while True:
                                try:self.audio.get_nowait()
                                except queue.Empty:break
                            self.transcrevendo.clear()
                    continue
                chamada_audio.reset()
                if not interessado and not frase_em_andamento:
                    if len(gravacao)>3*32000:del gravacao[:-3*32000]
                    excedeu=False
                if len(gravacao)+len(dados)<=30*32000:gravacao.extend(dados)
                else:excedeu=True
                if rec.AcceptWaveform(dados):
                    resultado=json.loads(rec.Result());ouvido=resultado.get('text','')
                    chamou=confirmada(resultado,self.config.get('ativacao_por_voz',True))
                    interessado=interessado or chamou
                    if chamou and norm(ouvido).strip()=='neymar':
                        self.ui(0,self.ativar)
                    elif motor=='vosk' and interessado:
                        # A autorização foi verificada no resultado final antes de entregar o texto.
                        texto=re.sub(r'^neymar\b[ ,.:;!?-]*','',ouvido,flags=re.I).strip()
                        if texto:self.ui(0,lambda t=texto,g=geracao:self.receber_transcricao(t,g))
                    elif interessado:
                        if excedeu:
                            self.ui(0,lambda:self.mostrar('Pedido longo demais. Clique Ouvir pedido e fale em até 30 segundos.'))
                        else:
                            self.transcrevendo.set();self.status_microfone='Transcrevendo com '+rotulo+'…'
                            self.ui(0,lambda:self.mostrar('Transcrevendo sua fala… aguarde antes do próximo pedido.'))
                            try:
                                if motor=='groq':
                                    from reconhecimento_groq import transcrever
                                    with medir(self.base,'groq',self.config.get('diagnostico_tempos',False)):
                                        texto=transcrever(self.base,bytes(gravacao))
                                else:
                                    self.whisper_local.perfil=self.config.get('perfil_whisper','precisao')
                                    self.whisper_local.diagnostico=self.config.get('diagnostico_tempos',False)
                                    texto=self.whisper_local.transcrever(bytes(gravacao))
                                if geracao==self.geracao and dispositivo==self.config.get('microfone') and motor==self.config.get('reconhecimento','whisper'):
                                    texto=re.sub(r'^\s*(?:neymar)\b[\s,.:;!?-]*','',texto,flags=re.I).strip()
                                    if texto:self.ui(0,lambda t=texto,g=geracao:self.receber_transcricao(t,g))
                                    elif ouvido and self.palavra_ativacao(norm(ouvido)):self.ui(0,self.ativar)
                                    else:self.ui(0,lambda:self.mostrar('Não reconheci uma frase. Clique Ouvir pedido e tente novamente.'))
                            except Exception as e:
                                aviso=str(e) if isinstance(e,RuntimeError) else 'Reconhecimento falhou. Confira a instalação e o microfone.'
                                self.registrar('TRANSCRIÇÃO: '+type(e).__name__)
                                self.ui(0,lambda t=aviso:self.mostrar(t))
                            finally:
                                while True:
                                    try:self.audio.get_nowait()
                                    except queue.Empty:break
                                self.transcrevendo.clear();self.status_microfone=rotulo+' conectado'
                    rec.Reset();gravacao.clear();interessado=False;excedeu=False;ultimo_parcial='';frase_em_andamento=False
                else:
                    parcial=json.loads(rec.PartialResult()).get('partial','')
                    if not parcial or parcial==ultimo_parcial:continue
                    ultimo_parcial=parcial
                    frase_em_andamento=True
                    if time.time()<self.ativo_ate:
                        self.ativo_ate=time.time()+5
                        if motor=='vosk':self.ui(0,lambda p=parcial:self.mostrar_parcial(p))
                        else:self.ui(0,lambda:self.mostrar_parcial('captando seu pedido…'))
                        self.ui(5500,lambda i=self.chamada_id:self.ocultar_sem_comando(i))

    def preparar_voz(self):
        # Sobe o processo de síntese cedo, com o modelo já carregado, para a
        # primeira resposta falada não pagar o custo de import+carga do zero.
        if not self.config.get('responder_por_voz',True):return
        with self.audio_lock:
            try:self._iniciar_processo_voz()
            except OSError as e:self.registrar('VOZ: preparo antecipado falhou: '+type(e).__name__)

    def _iniciar_processo_voz(self):
        """Garante um processo de síntese vivo (com o modelo já carregado) e devolve
        (processo, fila_de_respostas). Chamar sempre com self.audio_lock adquirido.
        O processo fica vivo entre falas seguidas; só é encerrado e recriado se
        travar, cair sozinho, ou se a fala for interrompida (parar_fala mata o
        processo para garantir corte imediato do áudio)."""
        if self.audio_processo is not None and self.audio_processo.poll() is None:
            return self.audio_processo, self.audio_respostas
        from pathlib import Path
        python=Path(sys.executable).with_name('python.exe') if sys.platform=='win32' else Path(sys.executable)
        args=[str(python),str(self.base/'voz_processo.py')]
        processo=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        respostas=queue.Queue()
        def ler_respostas():
            try:
                for linha in iter(processo.stdout.readline,b''):respostas.put(linha)
            except (OSError,ValueError):pass
        threading.Thread(target=ler_respostas,daemon=True,name='NeymarVozLeitura').start()
        self.audio_processo,self.audio_respostas=processo,respostas
        return processo,respostas

    def falar(self,t):
        if self.encerrar.is_set():return
        if threading.current_thread().name=='NeymarComandos' and getattr(self,'job_geracao',self.geracao)!=self.geracao:return
        t=str(t)
        self.registrar_resposta(t)
        self.estado_visual='speaking';self.ui(0,lambda:self.mostrar(t))
        self.voz_concluida.clear();self.falando.set()
        self.voz_fila.put((t,self.geracao,getattr(self,'epoca_voz',0)))

    def parar_fala(self):
        self.epoca_voz=getattr(self,'epoca_voz',0)+1
        self.parar_audio.set()
        while True:
            try:self.voz_fila.get_nowait();self.voz_fila.task_done()
            except queue.Empty:break
        with self.audio_lock:
            if self.audio_processo and self.audio_processo.poll() is None:
                try:self.audio_processo.terminate()
                except OSError:pass
            # Sempre derruba a referência: o processo persistente não dá para
            # interromper "no meio" (o áudio já está tocando dentro dele), então
            # a única forma de cortar na hora é matar e subir outro na próxima fala.
            self.audio_processo=None
        self.voz_concluida.set()
        if not self.ocupado.is_set():self.falando.clear()

    def trabalhador_voz(self):
        while not self.encerrar.is_set():
            try:texto,geracao,epoca=self.voz_fila.get(timeout=.2)
            except queue.Empty:continue
            try:
                if geracao!=self.geracao or epoca!=getattr(self,'epoca_voz',0):continue
                self.parar_audio.clear()
                if self.config.get('responder_por_voz',True):
                    carga={'texto':texto[:4000],'base':str(self.base),'piper':self.config.get('provedor_voz')=='piper','provedor':self.config.get('provedor_voz','windows'),'velocidade':self.config.get('velocidade_voz',172),'voz_piper':self.config.get('voz_piper','pt_BR-faber-medium'),'voz_windows':self.config.get('voz_windows',''),'ritmo_piper':self.config.get('ritmo_piper',1.08),'voz_edge':self.config.get('voz_edge','Antonio — masculina (Brasil)'),'ritmo_edge':self.config.get('ritmo_edge',0)}
                    with self.audio_lock:
                        if geracao!=self.geracao or epoca!=getattr(self,'epoca_voz',0):continue
                        processo,respostas=self._iniciar_processo_voz()
                    try:
                        processo.stdin.write(json.dumps(carga).encode('utf-8')+b'\n');processo.stdin.flush()
                    except (OSError,ValueError) as e:
                        self.registrar('VOZ: '+type(e).__name__)
                        with self.audio_lock:
                            if self.audio_processo is processo:self.audio_processo=None
                        continue
                    resposta=None;prazo=time.monotonic()+240
                    while time.monotonic()<prazo and not self.parar_audio.is_set():
                        try:resposta=respostas.get(timeout=.2);break
                        except queue.Empty:
                            if processo.poll() is not None:break
                            continue
                    travou=resposta is None and not self.parar_audio.is_set()
                    with self.audio_lock:
                        if self.audio_processo is processo and (travou or processo.poll() is not None):
                            try:processo.kill()
                            except OSError:pass
                            self.audio_processo=None
                    if resposta is not None:
                        try:resultado=json.loads(resposta.decode('utf-8'))
                        except ValueError:resultado={'ok':False,'erro':'A voz falhou. Confira Configurações.'}
                        if not resultado.get('ok') and not self.parar_audio.is_set():
                            detalhe=str(resultado.get('erro') or 'A voz falhou. Confira Configurações.')[:220]
                            self.ui(0,lambda d=detalhe:self.mostrar(d+' A resposta está na conversa.'))
                    elif travou:
                        self.ui(0,lambda:self.mostrar('A voz travou e foi reiniciada. Tente novamente.'))
            except Exception as e:self.registrar('VOZ: '+type(e).__name__)
            finally:
                self.voz_fila.task_done()
                if self.voz_fila.empty():
                    self.voz_concluida.set();self.falando.clear()
                    if self.acao_pendente:
                        self.estado_visual='confirm';self.ativo_ate=self.confirmacao_ate
                    elif geracao==self.geracao:
                        segundos=20 if self.agenda.proposta() else self.config.get('segundos_conversa_continua',6)
                        self.estado_visual='listening';self.ativo_ate=time.time()+segundos
                        self.ui(int(segundos*1000)+500,lambda i=self.chamada_id:self.ocultar_sem_comando(i))
