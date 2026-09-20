"""Interface futurista da Central Neymar, com painel e conversa separados."""
import threading
import time
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime
from PIL import Image, ImageDraw, ImageTk
from calendario_local import data_extenso
from util import leitura_sistema

BG = '#020814'; LATERAL = '#061426'; CARD = '#07182a'; CARD2 = '#0a2035'
FG = '#eafaff'; MUTED = '#7896aa'; ACCENT = '#18d9f4'; BORDA = '#123e5c'
VERDE = '#22e6a7'; AMARELO = '#ffd166'; VERMELHO = '#ff6f91'


def _arredondar(w, h, raio, fundo, borda, largura_borda=1):
    if w < 6 or h < 6: return None
    escala = 2
    img = Image.new('RGBA', (w*escala, h*escala), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((1, 1, w*escala-2, h*escala-2), radius=raio*escala,
                        fill=fundo, outline=borda, width=largura_borda*escala)
    return ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))


def painel(pai, raio=14, fundo=CARD, borda=BORDA, **empacotar):
    canvas = tk.Canvas(pai, bg=BG, highlightthickness=0)
    canvas.pack(**empacotar)
    conteudo = tk.Frame(canvas, bg=fundo)
    fundo_id = canvas.create_image(0, 0, anchor='nw')
    janela_id = canvas.create_window(0, 0, anchor='nw', window=conteudo)
    estado = {'img': None}
    def redesenhar(_=None):
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 6 or h < 6: return
        estado['img'] = _arredondar(w, h, raio, fundo, borda)
        canvas.itemconfig(fundo_id, image=estado['img'])
        canvas.itemconfig(janela_id, width=w, height=h)
    canvas.bind('<Configure>', redesenhar)
    return conteudo


def cartao(pai, titulo, **pack):
    opcoes = dict(side='left', fill='both', expand=True, padx=6, pady=6)
    opcoes.update(pack)
    conteudo = painel(pai, **opcoes)
    tk.Label(conteudo, text=titulo, bg=CARD, fg=ACCENT,
             font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=14, pady=(10, 4))
    corpo = tk.Frame(conteudo, bg=CARD)
    corpo.pack(fill='both', expand=True, padx=14, pady=(0, 11))
    return corpo


def botao(pai, texto, acao, destaque=False, cor=None, fundo=None):
    cor_fundo = fundo or (cor or ACCENT if destaque else CARD2)
    return tk.Button(pai, text=texto, command=acao, bg=cor_fundo,
        fg='#00131a' if destaque else FG, activebackground='#80f1ff' if destaque else '#103451',
        activeforeground='#00131a' if destaque else FG, font=('Segoe UI', 9, 'bold'),
        relief='flat', bd=0, padx=12, pady=8, cursor='hand2')


def linha_servico(pai, rotulo):
    linha = tk.Frame(pai, bg=CARD); linha.pack(fill='x', pady=3)
    tk.Label(linha, text=rotulo, bg=CARD, fg=MUTED, font=('Segoe UI', 9)).pack(side='left')
    valor = tk.Label(linha, bg=CARD, fg=VERDE, font=('Segoe UI', 9, 'bold'))
    valor.pack(side='right'); return valor


def desenhar_gauge(canvas, percent, cor):
    canvas.delete('all')
    canvas.create_oval(5, 5, 67, 67, outline='#12324a', width=7)
    if percent is not None:
        canvas.create_arc(5, 5, 67, 67, start=90, extent=-3.6*max(0, min(100, percent)),
                          style='arc', outline=cor, width=7)
        texto = f'{percent:.0f}%'
    else: texto = 'N/D'
    canvas.create_text(36, 36, text=texto, fill=FG, font=('Segoe UI', 9, 'bold'))


def desenhar_grafico_temp(canvas, historico, cor):
    """Mini-gráfico de linha com o histórico recente de temperatura (últimas
    leituras, ~2s entre cada uma), no lugar do medidor circular de
    porcentagem — temperatura não é uma fração de 0 a 100."""
    canvas.delete('all')
    w, h = int(canvas['width']), int(canvas['height'])
    if not historico or len(historico) < 2:
        canvas.create_text(w/2, h/2, text='Coletando…', fill=MUTED, font=('Segoe UI', 8))
        return
    minimo, maximo = min(historico), max(historico)
    if maximo - minimo < 2: minimo -= 1; maximo += 1
    margem = 4
    pontos = []
    for i, valor in enumerate(historico):
        x = margem + (w - 2*margem) * i / (len(historico) - 1)
        y = h - margem - (valor - minimo) / (maximo - minimo) * (h - 2*margem)
        pontos.extend((x, y))
    canvas.create_line(*pontos, fill=cor, width=2, smooth=True)
    canvas.create_text(w/2, 10, text=f'{historico[-1]:.0f} °C', fill=FG, font=('Segoe UI', 9, 'bold'))


class ChatVisualMixin:
    def abrir_conversa(self):
        import os
        if os.environ.get('NEYMAR_CLASSICO')=='1':
            return self.abrir_conversa_classica()
        central=getattr(self,'central_qt',None)
        if central and not central.fechado:
            central.mostrar();return
        try:
            import importlib.util
            if importlib.util.find_spec('PySide6') is None:
                return self.abrir_conversa_classica()
            from central_bridge import CentralBridge
            self.central_qt=CentralBridge(self)
        except (OSError,ImportError):
            self.abrir_conversa_classica()

    def abrir_conversa_classica(self):
        if hasattr(self, 'chat') and self.chat.winfo_exists():
            self.chat.deiconify(); self.chat.lift(); return
        self.chat = tk.Toplevel(self.root)
        self.chat.title('Neymar — Central de comando')
        self.chat.geometry('1380x850'); self.chat.minsize(1120, 700); self.chat.configure(bg=BG)
        self.chat.protocol('WM_DELETE_WINDOW', self.chat.withdraw)
        self.chat.bind('<Escape>', lambda e: self.parar_fala())
        self._prox_monitor = 0; self._pagina_atual = ''

        self.lateral = tk.Frame(self.chat, bg=LATERAL, width=205)
        self.lateral.pack(side='left', fill='y'); self.lateral.pack_propagate(False)
        tk.Label(self.lateral, text='◉  N E Y M A R', bg=LATERAL, fg=ACCENT,
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=18, pady=(20, 1))
        tk.Label(self.lateral, text='COMMAND CENTER', bg=LATERAL, fg=MUTED,
                 font=('Segoe UI', 7)).pack(anchor='w', padx=43, pady=(0, 20))
        self.nav_botoes = {}
        self._item_nav('central', '▦', 'Central de comando')
        self._item_nav('conversa', '▣', 'Conversa')
        self._item_nav('config', '⚙', 'Configurações', self.abrir_configuracoes)
        self._item_nav('jogo', '⌁', 'Modo de jogo', self.abrir_modo_jogo)
        self._item_nav('nova', '＋', 'Nova conversa', self.apagar_chat)
        self.jogo_status = tk.Label(self.lateral, text='MODO NORMAL', bg=LATERAL, fg=MUTED,
                                    font=('Segoe UI', 8, 'bold'))
        self.jogo_status.pack(anchor='w', padx=22, pady=(4, 0))

        voz_wrap = tk.Frame(self.lateral, bg=LATERAL, height=190)
        voz_wrap.pack(side='bottom', fill='x', padx=10, pady=12); voz_wrap.pack_propagate(False)
        voz = painel(voz_wrap, fill='both', expand=True)
        tk.Label(voz, text='VOICE STATUS', bg=CARD, fg=ACCENT,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=13, pady=(11, 5))
        self.chat_status = tk.Label(voz, bg=CARD, fg=MUTED, font=('Segoe UI', 8),
                                    justify='left', anchor='w', wraplength=165)
        self.chat_status.pack(fill='x', padx=13)
        botao(voz, '🎙  FALAR COM NEYMAR', self.ativar, True).pack(fill='x', padx=13, pady=(10, 5))
        botao(voz, 'Parar fala · Esc', self.parar_fala).pack(fill='x', padx=13)

        self.direita = tk.Frame(self.chat, bg=BG); self.direita.pack(side='left', fill='both', expand=True)
        topo = tk.Frame(self.direita, bg=BG, height=56); topo.pack(fill='x', padx=18); topo.pack_propagate(False)
        self.estado_label = tk.Label(topo, text='● SISTEMA PRONTO', bg=BG, fg=VERDE,
                                     font=('Segoe UI', 9, 'bold'))
        self.estado_label.pack(side='left', pady=19)
        bloco_data = tk.Frame(topo, bg=BG); bloco_data.pack(side='right', pady=9)
        self.relogio_label = tk.Label(bloco_data, bg=BG, fg=ACCENT, font=('Segoe UI', 16, 'bold'))
        self.relogio_label.pack(anchor='e')
        self.data_label = tk.Label(bloco_data, bg=BG, fg=MUTED, font=('Segoe UI', 8)); self.data_label.pack(anchor='e')
        self.area_paginas = tk.Frame(self.direita, bg=BG); self.area_paginas.pack(fill='both', expand=True)
        self.paginas = {'central': tk.Frame(self.area_paginas, bg=BG),
                        'conversa': tk.Frame(self.area_paginas, bg=BG)}
        self._montar_central(self.paginas['central']); self._montar_conversa(self.paginas['conversa'])
        self.mostrar_pagina('central')
        if getattr(self, 'img_grande', None) is not None: self.holo_label.config(image=self.img_grande)
        self.atualizar_chat(); self.atualizar_barra()

    def _item_nav(self, chave, glifo, texto, acao=None):
        acao = acao or (lambda c=chave: self.mostrar_pagina(c))
        b = tk.Button(self.lateral, text=f'{glifo}   {texto}', command=acao, anchor='w', relief='flat', bd=0,
                      bg=LATERAL, fg=FG, activebackground='#0b2941', activeforeground=ACCENT,
                      font=('Segoe UI', 9), padx=14, pady=10, cursor='hand2')
        b.pack(fill='x', padx=9, pady=2); self.nav_botoes[chave] = b

    def mostrar_pagina(self, nome):
        if nome not in self.paginas: return
        for p in self.paginas.values(): p.pack_forget()
        self.paginas[nome].pack(fill='both', expand=True)
        self._pagina_atual = nome
        for chave, b in self.nav_botoes.items():
            b.config(bg='#0b2941' if chave == nome else LATERAL,
                     fg=ACCENT if chave == nome else FG,
                     font=('Segoe UI', 9, 'bold' if chave == nome else 'normal'))
        if nome == 'conversa': self.atualizar_chat(); self.texto_pedido.focus_set()

    def _montar_central(self, pagina):
        linha1 = tk.Frame(pagina, bg=BG, height=258); linha1.pack(fill='x', padx=10); linha1.pack_propagate(False)
        status = cartao(linha1, 'AI CORE OVERVIEW')
        self.servicos_labels = {}
        for nome in ('Conversa', 'Reconhecimento', 'Voz'):
            self.servicos_labels[nome] = linha_servico(status, nome)
        linha_servico(status, 'Sistema').config(text='Ótimo')
        botao(status, 'Abrir conversa', lambda: self.mostrar_pagina('conversa'), True).pack(fill='x', pady=(12, 0))

        nucleo = cartao(linha1, 'NÚCLEO CENTRAL ANIMADO')
        self.holo_label = tk.Label(nucleo, bg=CARD, bd=0); self.holo_label.pack(expand=True)
        tk.Label(nucleo, text='NEYMAR  •  AI CORE ONLINE', bg=CARD, fg=ACCENT,
                 font=('Segoe UI', 9, 'bold')).pack()

        info = cartao(linha1, 'INFORMAÇÕES DO COMPUTADOR')
        self.info_pc = tk.Label(info, bg=CARD, fg=FG, justify='left', anchor='nw', wraplength=300,
                                font=('Segoe UI', 9), text='Coletando informações…')
        self.info_pc.pack(fill='both', expand=True)

        linha2 = tk.Frame(pagina, bg=BG, height=184); linha2.pack(fill='x', padx=10); linha2.pack_propagate(False)
        lemb = cartao(linha2, 'PRÓXIMOS LEMBRETES')
        self.lembretes_frame = tk.Frame(lemb, bg=CARD); self.lembretes_frame.pack(fill='both', expand=True)
        atalhos = cartao(linha2, 'COMANDOS RÁPIDOS')
        comandos = (('Abrir Chrome', 'abra o chrome'), ('Abrir YouTube', 'abra o youtube'),
                    ('Data e hora', 'que horas são'), ('Próximo jogo', 'qual é o próximo jogo'))
        for i, (nome, pedido) in enumerate(comandos):
            b = botao(atalhos, nome, lambda p=pedido: self.processar(p))
            b.grid(row=i//2, column=i%2, sticky='nsew', padx=4, pady=4)
        atalhos.grid_columnconfigure(0, weight=1); atalhos.grid_columnconfigure(1, weight=1)

        linha3 = tk.Frame(pagina, bg=BG, height=178); linha3.pack(fill='x', padx=10); linha3.pack_propagate(False)
        self.gauges = {}
        for chave, rotulo, cor in (('cpu','PROCESSADOR',ACCENT), ('ram','MEMÓRIA RAM',VERDE),
                                   ('disco','DISCO',AMARELO)):
            corpo = cartao(linha3, rotulo)
            canvas = tk.Canvas(corpo, width=74, height=74, bg=CARD, highlightthickness=0); canvas.pack(side='left')
            info = tk.Label(corpo, bg=CARD, fg=MUTED, font=('Segoe UI', 8), justify='left', anchor='w')
            info.pack(side='left', padx=8); self.gauges[chave] = (canvas, cor, info)
        self.graficos_temp = {}
        for chave, rotulo, cor in (('temp_cpu','TEMP. CPU',VERMELHO), ('temp_gpu','TEMP. GPU','#ff9e4a')):
            corpo = cartao(linha3, rotulo)
            canvas = tk.Canvas(corpo, width=120, height=52, bg=CARD, highlightthickness=0)
            canvas.pack(fill='both', expand=True, pady=(2, 0))
            fonte = tk.Label(corpo, bg=CARD, fg=MUTED, font=('Segoe UI', 8), anchor='w')
            fonte.pack(fill='x'); self.graficos_temp[chave] = (canvas, cor, fonte)

        confirm = tk.Frame(pagina, bg=BG); confirm.pack(fill='both', expand=True, padx=16)
        self.ancora_confirmacao = tk.Frame(confirm, bg=BG, height=0); self.ancora_confirmacao.pack(fill='x')
        self.painel_confirmacao = tk.Frame(confirm, bg='#49202b')
        tk.Label(self.painel_confirmacao, text='Confirmação de energia pendente', bg='#49202b', fg=FG).pack(side='left', padx=8, pady=7)
        botao(self.painel_confirmacao, 'Confirmar', self.confirmar_no_chat).pack(side='left', padx=4)
        botao(self.painel_confirmacao, 'Cancelar', self.cancelar_tudo).pack(side='left')

    def _montar_conversa(self, pagina):
        wrap = tk.Frame(pagina, bg=BG); wrap.pack(fill='both', expand=True, padx=16, pady=(4, 8))
        area = painel(wrap, fill='both', expand=True)
        tk.Label(area, text='CONVERSA COM NEYMAR', bg=CARD, fg=ACCENT,
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=16, pady=(12, 8))
        self.historico_chat = scrolledtext.ScrolledText(area, wrap='word', bg='#04101e', fg=FG,
            insertbackground=FG, selectbackground='#145a76', relief='flat', bd=0,
            font=('Segoe UI', 10), padx=16, pady=14, state='disabled')
        self.historico_chat.pack(fill='both', expand=True, padx=14, pady=(0, 10))
        self.historico_chat.tag_configure('usuario', foreground=ACCENT, font=('Segoe UI', 10, 'bold'))
        self.historico_chat.tag_configure('ney', foreground=VERDE, font=('Segoe UI', 10, 'bold'))
        self.historico_chat.tag_configure('texto', foreground=FG, spacing3=10)

        self.botao_lembrete = botao(area, 'Nenhum lembrete aguardando confirmação',
            lambda: self.responder_oferta(True, getattr(self, 'token_lembrete', None)))
        self.botao_lembrete.config(bg=CARD, fg=MUTED, font=('Segoe UI', 8))
        self.botao_lembrete.pack(fill='x', padx=14, pady=(0, 5))
        caixa = tk.Frame(area, bg=CARD2, highlightthickness=1, highlightbackground=BORDA)
        caixa.pack(fill='x', padx=14, pady=(0, 14))
        self.texto_pedido = tk.Text(caixa, height=2, wrap='word', font=('Segoe UI', 11),
                                    bg=CARD2, fg=FG, insertbackground=FG, relief='flat', padx=12, pady=9)
        self.texto_pedido.pack(side='left', fill='both', expand=True)
        self.texto_pedido.bind('<Return>', self.enviar_chat)
        self.texto_pedido.bind('<Shift-Return>', lambda e: None)
        botao(caixa, 'ENVIAR  ➜', self.enviar_chat, True).pack(side='right', padx=7, pady=7)

    def preencher_sugestao(self, texto):
        if self.texto_pedido.get('1.0', 'end').strip(): return
        self.texto_pedido.insert('1.0', texto); self.texto_pedido.focus_set()

    def atualizar_chat(self):
        if not hasattr(self, 'historico_chat') or not self.historico_chat.winfo_exists(): return
        itens = getattr(self, 'historico_comandos', []) or []
        self.historico_chat.config(state='normal'); self.historico_chat.delete('1.0', 'end')
        if not itens:
            self.historico_chat.insert('end', 'Neymar\n', 'ney')
            self.historico_chat.insert('end', 'Central pronta. Digite um comando ou use o microfone.\n', 'texto')
        for item in itens[-40:]:
            self.historico_chat.insert('end', 'Você\n', 'usuario')
            self.historico_chat.insert('end', str(item.get('comando', ''))+'\n', 'texto')
            self.historico_chat.insert('end', 'Neymar\n', 'ney')
            self.historico_chat.insert('end', str(item.get('resposta', ''))+'\n', 'texto')
        self.historico_chat.config(state='disabled'); self.historico_chat.see('end')

    def atualizar_lembretes(self):
        if not hasattr(self, 'lembretes_frame') or not self.lembretes_frame.winfo_exists(): return
        atuais = sorted((i for i in self.agenda.itens if i.get('estado') == 'agendado'), key=lambda i:i['aviso'])[:3]
        assinatura = [(i['id'], i['aviso']) for i in atuais]
        if getattr(self, '_lembretes_assinatura', None) == assinatura: return
        self._lembretes_assinatura = assinatura
        for w in self.lembretes_frame.winfo_children(): w.destroy()
        if not atuais:
            tk.Label(self.lembretes_frame, text='Nenhum lembrete agendado.', bg=CARD, fg=MUTED,
                     font=('Segoe UI', 9)).pack(anchor='w'); return
        for item in atuais:
            horario = datetime.fromtimestamp(item['aviso']).astimezone().strftime('%d/%m às %H:%M')
            tk.Label(self.lembretes_frame, text=f'◉  {horario}  •  {item["titulo"]}', bg=CARD,
                     fg=FG, font=('Segoe UI', 9), anchor='w').pack(fill='x', pady=4)

    def atualizar_monitor(self):
        if not hasattr(self, 'gauges'): return
        agora = time.time()
        if agora < getattr(self, '_prox_monitor', 0) or getattr(self, '_monitor_em_andamento', False): return
        self._prox_monitor = agora + 2; self._monitor_em_andamento = True
        def coletar():
            try: dados = leitura_sistema()
            except Exception: dados = {k:None for k in ('cpu','ram','disco','temp_cpu','temp_gpu')}
            def aplicar():
                self._monitor_em_andamento = False
                if not hasattr(self, 'gauges'): return
                for chave, (canvas, cor, info) in self.gauges.items():
                    if not canvas.winfo_exists(): continue
                    valor = dados.get(chave); desenhar_gauge(canvas, valor, cor)
                    if chave == 'ram' and valor is not None:
                        detalhe = f'{dados.get("ram_usada",0):.1f} de {dados.get("ram_total",0):.1f} GB\nem uso'
                    elif chave == 'disco' and valor is not None:
                        detalhe = f'{valor:.0f}% ocupado\n{dados.get("disco_livre",0):.1f} GB livres'
                    elif chave == 'cpu' and valor is not None: detalhe = f'{valor:.0f}% em uso\nem tempo real'
                    else: detalhe = 'Leitura indisponível'
                    info.config(text=detalhe)
                for chave, (canvas, cor, fonte) in getattr(self, 'graficos_temp', {}).items():
                    if not canvas.winfo_exists(): continue
                    desenhar_grafico_temp(canvas, dados.get(chave+'_historico') or [], cor)
                    fonte.config(text=dados.get(chave+'_fonte') or 'Sensor não disponível')
                if hasattr(self, 'info_pc') and self.info_pc.winfo_exists():
                    self.info_pc.config(text=(f'Computador  {dados.get("computador") or "N/D"}\n'
                        f'Sistema       {dados.get("windows") or "N/D"}\n'
                        f'Arquitetura   {dados.get("arquitetura") or "N/D"}\n'
                        f'Processador   {dados.get("processador") or "N/D"}\n'
                        f'Núcleos       {dados.get("nucleos") or "N/D"} físicos / {dados.get("logicos") or "N/D"} lógicos\n'
                        f'Ligado há     {dados.get("tempo_ligado") or "N/D"}'))
            self.ui(0, aplicar)
        threading.Thread(target=coletar, daemon=True, name='NeymarMonitorSistema').start()

    def atualizar_barra(self):
        if self.encerrar.is_set() or not self.chat.winfo_exists(): return
        online = self.config.get('provedor_ia') in ('nvidia', 'gemini')
        nome = 'Gemini' if self.config.get('provedor_ia') == 'gemini' else 'NVIDIA'
        self.servicos_labels['Conversa'].config(text=nome if online else 'Ollama · local')
        self.servicos_labels['Reconhecimento'].config(text=self.config.get('reconhecimento', 'vosk').capitalize())
        self.servicos_labels['Voz'].config(text=self.config.get('provedor_voz', 'windows').capitalize())
        agora = datetime.now().astimezone(); self.relogio_label.config(text=agora.strftime('%H:%M:%S'))
        self.data_label.config(text=data_extenso(agora))
        estado = ('Pausado' if self.pausado.is_set() else 'Transcrevendo' if getattr(self, 'transcrevendo', None) and self.transcrevendo.is_set()
                  else 'Falando' if not self.voz_concluida.is_set() else 'Preparando resposta' if self.ocupado.is_set() else 'Pronto')
        self.estado_label.config(text='●  SISTEMA '+estado.upper(), fg=AMARELO if estado != 'Pronto' else VERDE)
        jogo_ativo = self.modo_jogo.ativo
        self.jogo_status.config(text='MODO DE JOGO ATIVO' if jogo_ativo else 'MODO NORMAL', fg=ACCENT if jogo_ativo else MUTED)
        proposta = self.agenda.proposta(); self.token_lembrete = proposta['token'] if proposta else None
        self.botao_lembrete.config(state='normal' if proposta else 'disabled',
            text=('Confirmar aviso: '+proposta['titulo']) if proposta else 'Nenhum lembrete aguardando confirmação',
            fg=ACCENT if proposta else MUTED)
        mic = getattr(self, 'status_microfone', 'Iniciando microfone…')
        if not self.config.get('ativacao_por_voz', True): mic = 'Chamada pelo nome desativada'
        elif self.pausado.is_set(): mic = 'PAUSADO — retome pela bandeja'
        nivel = getattr(self, 'nivel_microfone', 0)
        self.chat_status.config(text=f'{mic}\nNível: {min(100, round(nivel*1000))}%\n{self.ultimo_status[:90]}')
        self.atualizar_lembretes(); self.atualizar_monitor(); self.atualizar_confirmacao()
        self.token_chat = self.confirmacao.estado()[1]
        self.ui(1200 if jogo_ativo else 400, self.atualizar_barra)
