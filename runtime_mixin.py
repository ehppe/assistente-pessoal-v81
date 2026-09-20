"""Fila única de comandos, entrega de eventos à interface e confirmações atômicas."""
import queue
import subprocess
import threading
import time
from motor import Confirmacao, Memoria, preparar_pedido, resposta_confirmacao, tipo_pedido
from inteligencia import responder


class RuntimeMixin:
    def preparar_runtime(self):
        self.thread_ui = threading.get_ident()
        self.eventos_ui = queue.Queue()
        self.fila_comandos = queue.Queue(maxsize=5)
        self.confirmacao = Confirmacao()
        self.memoria = Memoria(self.base/'dados'/'conversas.json', self.config.get('salvar_conversas', True))
        self.historico_comandos = self.memoria.lista()
        self.geracao = 0
        self.ocupado = threading.Event()
        self.voz_fila = queue.Queue()
        self.parar_audio = threading.Event()
        self.audio_processo = None
        self.audio_respostas = queue.Queue()
        self.audio_lock = threading.Lock()
        self.voz_concluida = threading.Event(); self.voz_concluida.set()
        from lembretes import Agenda
        self.agenda=Agenda(self.base)
        from modo_jogo import ModoJogo
        self.modo_jogo=ModoJogo(self.base)
        self.recuperando_jogo=bool(self.modo_jogo.energia)
        if self.recuperando_jogo:self.ui(0,self.recuperar_modo_jogo)
        self.ui(2000,self.verificar_lembretes)
        self.status_microfone = 'Iniciando…'
        self.root.after(30, self.entregar_eventos)
        threading.Thread(target=self.trabalhador, name="NeymarComandos", daemon=True).start()
        threading.Thread(target=self.trabalhador_voz, daemon=True).start()

    @property
    def acao_pendente(self):
        return self.confirmacao.estado()[0]

    @acao_pendente.setter
    def acao_pendente(self, valor):
        if hasattr(self, 'confirmacao'):
            if valor is None:self.confirmacao.cancelar()
            else:self.confirmacao.iniciar(valor)

    def ui(self, atraso, funcao):
        if not self.encerrar.is_set():self.eventos_ui.put((atraso, funcao))

    def entregar_eventos(self):
        if self.encerrar.is_set():return
        for _ in range(100):
            try:atraso, funcao = self.eventos_ui.get_nowait()
            except queue.Empty:break
            if atraso:self.root.after(atraso, funcao)
            else:
                try:funcao()
                except Exception as e:self.registrar('INTERFACE: '+type(e).__name__)
        self.root.after(30, self.entregar_eventos)

    def processar(self, c):
        c = str(c).strip()[:8000]
        if not c:return
        n = preparar_pedido(c)
        if n in ('pare de falar','parar de falar','cancelar','cancele','cancela'):
            self.cancelar_tudo();return
        acao, token = self.confirmacao.estado()
        if acao:
            sim = resposta_confirmacao(c)
            if sim is not None:self.resolver_confirmacao(sim, token)
            else:self.ui(0, lambda:self.mostrar('Existe uma confirmação pendente. Diga confirmar ou cancelar.'))
            return
        proposta=self.agenda.proposta()
        if proposta and n in ('sim','confirmar','confirmo','pode confirmar','pode agendar','sim pode agendar','confirmar lembrete','nao','nao precisa','cancelar lembrete'):
            self.responder_oferta(n not in ('nao','nao precisa','cancelar lembrete'),proposta['token']);return
        if n in ('pode agendar','sim pode agendar','pode confirmar','confirmar lembrete'):
            self.mostrar('Não há uma oferta de lembrete pendente. Pergunte pelo próximo jogo.');return
        if n in ('confirmar','confirmo','sim'):
            self.ui(0,lambda:self.mostrar('Nenhuma ação aguardando confirmação.'));return
        try:self.fila_comandos.put_nowait((c,self.geracao))
        except queue.Full:
            self.ui(0,lambda:self.mostrar('A fila está cheia. Aguarde ou use Cancelar.'));return
        self.chamada_id += 1
        self.ativo_ate = 0
        self.ui(0,lambda:self.mostrar('Pedido recebido: '+c[:150]))

    def cancelar_tudo(self):
        self.geracao += 1
        self.confirmacao.cancelar()
        with self.agenda.lock:self.agenda.pendente=None
        while True:
            try:self.fila_comandos.get_nowait();self.fila_comandos.task_done()
            except queue.Empty:break
        self.parar_fala()
        self.ui(0,lambda:self.mostrar('Cancelado. Ações já executadas não são desfeitas.'))

    def deve_perguntar_continuacao(self, comando, geracao):
        if (not self.config.get('perguntar_apos_resposta',True)
                or not self.config.get('responder_por_voz',True)
                or geracao!=self.geracao or self.encerrar.is_set()
                or self.pausado.is_set() or self.acao_pendente
                or self.agenda.proposta() or not self.fila_comandos.empty()):
            return False
        import re
        n=re.sub(r'[^a-z0-9\s]',' ',preparar_pedido(comando))
        n=re.sub(r'\s+',' ',n).strip()
        encerramentos={
            'nao','nao obrigado','nao obrigada','nada','nada mais','so isso',
            'era so isso','obrigado','obrigada','valeu','pode parar',
        }
        return n not in encerramentos

    def perguntar_continuacao(self, comando, geracao):
        if not self.deve_perguntar_continuacao(comando,geracao):return False
        import frases
        self.aguardando_continuacao=True
        self.falar(frases.variar(frases.CONTINUAR,self.config.get('tratamento','')),registrar=False)
        return True

    def trabalhador(self):
        while not self.encerrar.is_set():
            try:c, geracao = self.fila_comandos.get(timeout=.25)
            except queue.Empty:continue
            try:
                if geracao != self.geracao:continue
                if self.acao_pendente:
                    self.ui(0,lambda:self.mostrar('Pedido ignorado enquanto há confirmação de energia pendente.'));continue
                self.ocupado.set();self.falando.set()
                self.comando_atual=c;self.estado_visual='thinking'
                self.ui(0,lambda c=c:self.mostrar('Entendendo: '+c[:150]))
                self.job_geracao=geracao
                p=self.basico(c)
                if p['action']=='unknown':
                    resposta=responder(self.base,dict(self.config),self.memoria.contexto(),c)
                    p={'action':'answer','target':resposta}
                if geracao != self.geracao:continue
                self.executar(p)
                while not self.voz_concluida.wait(.2):
                    if self.encerrar.is_set():return
                if self.perguntar_continuacao(c,geracao):
                    while not self.voz_concluida.wait(.2):
                        if self.encerrar.is_set():return
            except Exception as e:
                self.registrar('PEDIDO: '+type(e).__name__)
                if geracao==self.geracao:
                    self.falar(str(e) if isinstance(e,RuntimeError) else 'Não consegui concluir o pedido. Consulte o diagnóstico.')
                    while not self.voz_concluida.wait(.2):
                        if self.encerrar.is_set():return
            finally:
                self.ocupado.clear()
                if self.voz_concluida.is_set():self.falando.clear()
                self.fila_comandos.task_done()

    def basico(self,c):
        import re
        from modo_jogo import interpretar as interpretar_jogo
        jogo_acao=interpretar_jogo(c)
        if jogo_acao:return {'action':'game_mode','target':jogo_acao}
        from calendario_local import responder_calendario
        n=preparar_pedido(c)
        m=re.match(r'^(?:mude|troque|altere) (?:seu nome|o nome do assistente) para ([a-zà-ÿ ]{2,30})$',n,re.I)
        if m:
            nome=m.group(1).strip().title()
            if not nome.replace(' ','').isalpha():return {'action':'answer','target':'Use somente letras no nome do assistente.'}
            from config import salvar
            self.config['nome_assistente']=nome;self.config['palavras_ativacao']=[nome.lower()];salvar(self.base,self.config)
            return {'action':'answer','target':'Meu nome agora é '+nome+'. Reinicie o assistente para aplicar a nova chamada por voz.'}
        if n in ('meus lembretes','listar lembretes','quais sao meus lembretes'):return {'action':'answer','target':self.agenda.listar()}
        if n=='cancelar todos os lembretes':return {'action':'answer','target':self.agenda.cancelar_todos()}
        m=re.match(r'^cancelar lembrete (?:de |do |da )?(.+)$',n)
        if m:return {'action':'answer','target':self.agenda.cancelar(m.group(1))}
        m=re.match(r'^adiar lembrete (?:de |do |da )?(.+?)(?: por (\d+) minutos?)?$',n)
        if m:return {'action':'answer','target':self.agenda.adiar(m.group(1),int(m.group(2) or 10))}
        from pedido_lembrete import pedido_de_agendamento, interpretar as interpretar_lembrete
        if pedido_de_agendamento(n):
            achado=interpretar_lembrete(c)
            if not achado:
                return {'action':'answer','target':'Entendi que você quer um lembrete, mas não peguei o dia e o horário direito. Tente algo como "me lembre amanhã às 15h de ligar pro dentista".'}
            titulo,quando,recorrencia=achado
            pergunta=self.oferecer_lembrete_pessoal(titulo,quando,recorrencia)
            if not pergunta:
                return {'action':'answer','target':'Esse horário já passou. Diga o pedido de novo com um horário no futuro.'}
            return {'action':'answer','target':pergunta}
        calendario=responder_calendario(c)
        if calendario:return {'action':'answer','target':calendario}
        from futebol import interpretar, consultar
        jogo=interpretar(c,self.config.get('time_favorito','Corinthians'))
        if jogo:return {'action':'answer','target':consultar(self.base,*jogo,oferecer_lembrete=self.oferecer_lembrete)}
        n=preparar_pedido(c);tipo=tipo_pedido(c)
        if tipo=='energia':return {'action':'shutdown' if n.startswith('deslig') else 'restart','target':''}
        if tipo=='rotina':return {'action':'rotina_jogar','target':''}
        # Intenções de consulta específicas, não palavras soltas como "temperatura".
        if n in ('que horas sao','que horas','que hora e agora'):return {'action':'hora','target':''}
        import re
        from previsao_dia import eh_pedido_clima, extrair_dia_climatico
        if eh_pedido_clima(n):
            dias,trecho_dia=extrair_dia_climatico(n)
            n_sem_dia=n.replace(trecho_dia,' ') if trecho_dia else n
            m=re.search(r'\b(?:em|na|no)\s+(.+)$',n_sem_dia)
            cidade=re.sub(r'\s+',' ',m.group(1)).strip() if m else ''
            return {'action':'clima','target':cidade,'dias':dias}
        if tipo!='comando':return {'action':'unknown','target':''}
        n=re.sub(r'^(inicie|iniciar)\b','abra',n)
        n=re.sub(r'^entra\b','entre',n)
        n=re.sub(r'^conecta\b','conecte',n)
        if n.startswith('desligue da chamada'):return {'action':'discord_leave','target':''}
        p=self.basico_legado(n)
        if p['action'] in ('shutdown','restart','clima'):return {'action':'unknown','target':''}
        return p

    def pedir_confirmacao(self,acao):
        token=self.confirmacao.iniciar(acao)
        self.confirmacao_ate=time.time()+30
        self.falar('Deseja '+('desligar' if acao=='shutdown' else 'reiniciar')+' o computador? Diga confirmar ou cancelar em até 30 segundos.')
        self.ui(0,self.atualizar_confirmacao)
        def expirar():
            atual, _token=self.confirmacao.estado()
            if not atual and self.estado_visual=='confirm':
                self.estado_visual='idle';self.mostrar('O prazo de confirmação terminou.');self.atualizar_confirmacao()
        self.ui(30500,expirar)

    def resolver_confirmacao(self,confirmado,token=None):
        # Chamadores remotos SEMPRE passam o token correspondente ao pedido mostrado.
        pendente, atual=self.confirmacao.estado()
        if pendente and token==atual and not confirmado:self.parar_fala()
        acao=self.confirmacao.consumir(confirmado,token)
        self.ui(0,self.atualizar_confirmacao)
        if not acao:
            self.ui(0,lambda:self.mostrar('Confirmação cancelada, expirada ou já utilizada.'));return
        self.parar_fala()
        try:
            subprocess.Popen(['shutdown.exe','/s' if acao=='shutdown' else '/r','/t','0'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except OSError:
            self.ui(0,lambda:self.mostrar('O Windows não aceitou o comando de energia.'))

    def rotina_jogar(self):
        geracao=self.geracao
        ret=self.abrir_gc_cs2()
        if geracao!=self.geracao:return 'Rotina cancelada.'
        # Verifica o processo em vez de presumir que clicar iniciou o jogo.
        prazo=time.monotonic()+45
        while time.monotonic()<prazo:
            if geracao!=self.geracao or self.encerrar.is_set():return 'Rotina cancelada.'
            p=subprocess.run(['tasklist.exe','/FI','IMAGENAME eq cs2.exe','/FO','CSV','/NH'],capture_output=True,text=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if 'cs2.exe' in p.stdout.lower():break
            time.sleep(.5)
        else:return ret+' Não confirmei o CS2 aberto; interrompi a rotina antes do Discord.'
        if geracao!=self.geracao:return 'Rotina cancelada.'
        return 'CS2 está aberto. '+self.entrar_discord(self.config.get('canal_modo_jogar','comp1'))

    def limpar_memoria(self):
        if self.ocupado.is_set() or not self.fila_comandos.empty():
            from tkinter import messagebox
            messagebox.showinfo('Neymar','Aguarde o pedido terminar antes de apagar a conversa.');return
        try:self.memoria.limpar()
        except OSError:
            self.mostrar('Não foi possível apagar a conversa salva.');return
        self.historico_comandos=[];self.atualizar_chat()

    def atualizar_confirmacao(self):
        if hasattr(self,'painel_confirmacao') and self.painel_confirmacao.winfo_exists():
            if self.acao_pendente:self.painel_confirmacao.pack(fill='x',padx=0,pady=5,before=self.ancora_confirmacao)
            else:self.painel_confirmacao.pack_forget()

    def registrar_resposta(self,texto):
        # Avisos da interface não são enviados de volta como respostas de pedidos.
        if self.ocupado.is_set() and self.comando_atual:
            try:self.memoria.adicionar(self.comando_atual,texto)
            except OSError:self.ui(0,lambda:self.mostrar('Resposta pronta, mas não consegui salvar o histórico.'))
            self.historico_comandos=self.memoria.lista()
        self.ui(0,self.atualizar_chat)


    def oferecer_lembrete(self,titulo,inicio,identificador):
        if getattr(self,'job_geracao',self.geracao)!=self.geracao:return ''
        proposta=self.agenda.oferecer(titulo,inicio,identificador)
        if not proposta:return ''
        return 'Posso avisar você 30 minutos antes deste jogo? '

    def oferecer_lembrete_pessoal(self,titulo,quando,recorrencia=None):
        import uuid
        from datetime import datetime
        proposta=self.agenda.oferecer_pessoal(titulo,quando,uuid.uuid4().hex,recorrencia=recorrencia)
        if not proposta:return ''
        horario=datetime.fromtimestamp(quando).astimezone().strftime('%d/%m às %H:%M')
        repeticao={'diaria':' e repetir todo dia','semanal':' e repetir toda semana'}.get(recorrencia,'')
        return 'Posso agendar "'+titulo+'" para '+horario+repeticao+'? Diga confirmar ou cancelar.'

    def responder_oferta(self,aceitar,token=None):
        # O token vincula a confirmação à oferta exibida ou ouvida.
        if token is None:
            proposta=self.agenda.proposta();token=proposta['token'] if proposta else None
        self.parar_fala()
        try:mensagem=self.agenda.resolver(token,aceitar)
        except RuntimeError as e:mensagem=str(e)
        self.falar(mensagem)

    def controle_durante_fala(self,acao,epoca,token):
        if self.pausado.is_set() or not self.config.get('interromper_por_voz',True) or epoca!=getattr(self,'epoca_voz',0):return
        if acao=='parar':
            self.parar_fala();self.mostrar('Fala interrompida.');return
        # Não confirma desligamento/reinício. Só a oferta de lembrete capturada.
        if self.acao_pendente:return
        proposta=self.agenda.proposta()
        if not proposta or token!=proposta['token']:return
        self.responder_oferta(acao=='confirmar',token)

    def verificar_lembretes(self):
        if self.encerrar.is_set():return
        try:
            if not self.ocupado.is_set() and not self.falando.is_set() and not self.pausado.is_set() and not self.acao_pendente:
                avisos=self.agenda.devidos()
                if avisos:
                    from datetime import datetime
                    partes=[];algum_jogo=False
                    for i in avisos:
                        if i['inicio']>i['aviso']:
                            algum_jogo=True
                            partes.append(i['titulo']+' começa às '+datetime.fromtimestamp(i['inicio']).astimezone().strftime('%H:%M'))
                        else:
                            partes.append(i['titulo'])
                    texto='Lembrete: '+'; '.join(partes)+'.'
                    if algum_jogo:texto+=' Horário consultado ao agendar.'
                    self.falar(texto)
        except Exception as e:self.registrar('LEMBRETE: '+type(e).__name__)
        finally:self.ui(2000,self.verificar_lembretes)
