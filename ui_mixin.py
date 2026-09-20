"""Interface visual: núcleo holográfico (estilo HUD), bandeja e animação.

O visual é todo desenhado por código (veja util.gerar_nucleo) — não depende
de nenhuma imagem externa. Isso permite trocar a cor e o estilo só editando
"cor_nucleo" no config.json.
"""
import ctypes
import math
import re
import threading
import time

import tkinter as tk
from tkinter import messagebox, simpledialog

import pystray
from PIL import ImageTk

import config as config_arquivo
import frases
from util import bipe, gerar_nucleo, nivel_reativo, norm

TRANSP = '#010203'

CORES_ESTADO = {
    'idle': (40, 180, 255),
    'listening': (20, 235, 255),
    'thinking': (174, 92, 255),
    'speaking': (45, 255, 174),
    'confirm': (255, 164, 55),
    'pausado': (110, 118, 130),
}

QUADROS_POR_ESTADO = 24


class UIMixin:
    def interface(self):
        self.frames_holograma = self.criar_frames_holograma(220)
        self.frames_holograma_grande = self.criar_frames_holograma(120)
        self.img = self.frames_holograma['idle'][0]
        self.img_grande = self.frames_holograma_grande['idle'][0]
        self.robo = tk.Label(self.root, image=self.img, bg=TRANSP, bd=0)
        self.robo.pack(pady=(8, 0))
        self.status = tk.Label(
            self.root, text='', bg='#172133', fg='#72d7ff',
            font=('Segoe UI Semibold', 10), wraplength=255, padx=12, pady=8,
        )
        self.status.pack()
        for w in (self.root, self.robo, self.status):
            w.bind('<Button-1>', self.inicio_arrasto)
            w.bind('<B1-Motion>', self.arrastar)
            w.bind('<Double-Button-1>', lambda _e: self.ativar())
        self.ui(90, self.animar_robo)

    def criar_frames_holograma(self, tamanho=220):
        # A cor base vem do config.json ("cor_nucleo"); cada estado usa uma
        # variação dela, exceto os estados com cor própria (pensando, etc).
        # Chamado duas vezes: um jogo de quadros pequeno (bandeja/widget) e
        # outro grande (núcleo central da janela "Vamos conversar").
        cor_base = tuple(self.config.get('cor_nucleo', [64, 207, 255])[:3])
        cores = dict(CORES_ESTADO)
        cores['idle'] = cor_base
        cores['listening'] = tuple(min(255, c + 30) for c in cor_base)
        self.cores_holograma = cores
        frames = {}
        for estado, cor in cores.items():
            frames[estado] = []
            velocidade = 2.4 if estado in ('listening', 'thinking', 'speaking') else 1
            for i in range(QUADROS_POR_ESTADO):
                pulso = (1 + math.sin(i * math.pi / (QUADROS_POR_ESTADO / 2))) / 2
                angulo = (360 / QUADROS_POR_ESTADO) * i * velocidade
                quadro = gerar_nucleo(tamanho, cor, angulo=angulo, pulso=pulso)
                frames[estado].append(ImageTk.PhotoImage(quadro))
        return frames

    def animar_robo(self):
        if self.encerrar.is_set():
            return
        if getattr(getattr(self,'modo_jogo',None),'ativo',False):
            self.ui(500,self.animar_robo);return
        if self.pausado.is_set():
            estado = 'pausado'
        else:
            estado = 'confirm' if self.acao_pendente else self.estado_visual
        if estado not in self.frames_holograma:
            estado = 'idle'
        self.quadro_animacao = (self.quadro_animacao + 1) % QUADROS_POR_ESTADO
        if estado in ('listening', 'speaking'):
            # As ondas do holograma acompanham o volume real captado pelo
            # microfone (ouvindo o pedido, ou o eco da própria fala do
            # Neymar) em vez do pulso fixo em seno — só nesses dois estados,
            # renderizando na hora em vez de usar os quadros pré-gerados, que
            # são um ciclo fixo e não sabem o volume de agora.
            velocidade = 1.7
            angulo = (360 / QUADROS_POR_ESTADO) * self.quadro_animacao * velocidade
            cor = self.cores_holograma.get(estado, (64, 207, 255))
            pulso = nivel_reativo(getattr(self, 'nivel_microfone', 0))
            self.img = ImageTk.PhotoImage(gerar_nucleo(220, cor, angulo=angulo, pulso=pulso))
            self.img_grande = ImageTk.PhotoImage(gerar_nucleo(120, cor, angulo=angulo, pulso=pulso))
        else:
            self.img = self.frames_holograma[estado][self.quadro_animacao]
            self.img_grande = self.frames_holograma_grande[estado][self.quadro_animacao]
        self.robo.config(image=self.img)
        # Espelha a mesma animação, em tamanho maior, no núcleo central da
        # janela principal (visual_conversa.py), quando ela está aberta.
        holo = getattr(self, 'holo_label', None)
        if holo is not None and holo.winfo_exists():
            holo.config(image=self.img_grande)
        velocidade = 1.7 if estado in ('listening', 'thinking', 'speaking') else 1
        onda = math.sin(self.quadro_animacao * math.pi / 6 * velocidade)
        self.robo.pack_configure(pady=(8 + round(onda * 4), 0))
        cores = {
            'idle': '#72d7ff', 'listening': '#40eaff', 'thinking': '#bd7cff',
            'speaking': '#45ffae', 'confirm': '#ffb347', 'pausado': '#8f97a3',
        }
        self.status.config(fg=cores[estado])
        self.ui(90, self.animar_robo)

    def bandeja(self):
        ico = gerar_nucleo(64, tuple(self.config.get('cor_nucleo', [64, 207, 255])[:3]), angulo=15, pulso=.85)
        menu = pystray.Menu(
            pystray.MenuItem('Parar fala (Ctrl+Alt+Espaço)', lambda: self.ui(0, self.parar_fala)),
            pystray.MenuItem('Conversar', lambda: self.ui(0, self.abrir_conversa)),
            pystray.MenuItem('Modo de jogo', lambda: self.ui(0, self.abrir_modo_jogo)),
            pystray.MenuItem('Configurações', lambda: self.ui(0, self.abrir_configuracoes)),
            pystray.MenuItem('Chamar Neymar', lambda: self.ui(0, self.ativar)),
            pystray.MenuItem('Mostrar robô', lambda: self.ui(0, self.mostrar)),
            pystray.MenuItem('Acesso pelo iPhone', lambda: self.ui(0, self.mostrar_acesso_iphone)),
            pystray.MenuItem('Adicionar canal do Discord', lambda: self.ui(0, self.adicionar_canal_discord)),
            pystray.MenuItem('Configurar minha cidade', lambda: self.ui(0, self.configurar_cidade)),
            pystray.MenuItem(
                'Pausar escuta', lambda: self.ui(0, self.alternar_pausa),
                checked=lambda _item: self.pausado.is_set(),
            ),
            pystray.MenuItem('Atualizar arquivos e programas', lambda: self.iniciar_indice(True)),
            pystray.MenuItem('Sair', lambda: self.ui(0, self.fechar)),
        )
        from versao import TITULO
        nome=str(self.config.get('nome_usuario','')).strip()
        self.tray = pystray.Icon('NeymarAssistente', ico, TITULO+(' — assistente de '+nome if nome else ' — assistente pessoal'), menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def alternar_pausa(self):
        if self.pausado.is_set():
            self.pausado.clear()
            self.mostrar('Escuta retomada.')
        else:
            self.pausado.set()
            self.acao_pendente = None
            self.mostrar('Escuta pausada. Use o ícone da bandeja para retomar.')
        self.ui(3000, self.root.withdraw)

    def inicio_arrasto(self, e):
        self.arrasto = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def arrastar(self, e):
        self.root.geometry(f'+{e.x_root - self.arrasto[0]}+{e.y_root - self.arrasto[1]}')

    def mostrar(self, texto='Pronto. Diga: Neymar'):
        if threading.get_ident() != self.thread_ui:
            self.ui(0, lambda:self.mostrar(texto));return
        self.ultimo_status = texto
        self.status.config(text=texto[:220])
        self.root.deiconify()
        self.root.lift()
        self.reforcar_topo()

    def mostrar_parcial(self, texto):
        if self.pausado.is_set() or self.acao_pendente:
            return
        self.status.config(text='Ouvindo: ' + texto)
        self.root.deiconify()
        self.root.lift()

    def reforcar_topo(self):
        try:
            self.root.attributes('-topmost', True)
            self.root.lift()
            hwnd = self.root.winfo_id()
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
        except Exception:
            pass

    def mostrar_acesso_iphone(self):
        if not self.servidor_iphone:
            messagebox.showwarning('Neymar no iPhone', 'Não encontrei uma conexão ativa do Tailscale. Abra o Tailscale e reinicie o Neymar.')
            return
        url = f'http://{self.servidor_iphone.ip_tailscale}:8765'
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        messagebox.showinfo('Neymar no iPhone', f'No iPhone, abra:\n\n{url}\n\nCódigo de acesso: {self.servidor_iphone.pin}\n\nO endereço foi copiado. Não compartilhe esse código.')

    def adicionar_canal_discord(self):
        self.reforcar_topo()
        apelido = simpledialog.askstring(
            'Adicionar canal do Discord',
            'Como você vai chamar esse canal por voz?\n(ex: trabalho, comp1, familia)',
            parent=self.root,
        )
        if not apelido or not apelido.strip():
            return
        apelido = norm(apelido.strip())
        link = simpledialog.askstring(
            'Adicionar canal do Discord',
            'Agora cole o link do canal de voz.\n\n'
            'No Discord: botão direito no canal > "Copiar link do canal".\n'
            '(Se essa opção não aparecer, ative primeiro em Configurações > '
            'Avançado > Modo desenvolvedor.)',
            parent=self.root,
        )
        if not link:
            return
        m = re.search(r'channels/(\d+)/(\d+)', link)
        if not m:
            messagebox.showerror(
                'Adicionar canal do Discord',
                'Não reconheci esse link. Ele deve ser parecido com:\n'
                'https://discord.com/channels/SERVIDOR/CANAL',
            )
            return
        servidor_id, canal_id = m.group(1), m.group(2)
        canal_nome = simpledialog.askstring(
            'Adicionar canal do Discord',
            'Por último: como esse canal aparece DENTRO do Discord?\n'
            '(o nome de verdade na lista de canais — pode ser diferente do '
            f'apelido "{apelido}" que você acabou de escolher. Ex: LOBBY 1)',
            parent=self.root,
        )
        canal_nome = canal_nome.strip() if canal_nome else apelido
        canais = list(self.config.get('discord_canais') or [])
        existente = next((item for item in canais if apelido in [norm(a) for a in item.get('apelidos', [])]), None)
        if existente:
            existente['servidor_id'] = servidor_id
            existente['canal_id'] = canal_id
            existente['canal_nome'] = canal_nome
        else:
            canais.append({'apelidos': [apelido], 'servidor_id': servidor_id, 'canal_id': canal_id, 'canal_nome': canal_nome})
        self.config['discord_canais'] = canais
        config_arquivo.salvar(self.base, self.config)
        messagebox.showinfo('Adicionar canal do Discord', f'Pronto! Agora é só dizer "entra no {apelido}".')

    def configurar_cidade(self):
        self.reforcar_topo()
        atual = self.config.get('cidade_padrao', '')
        cidade = simpledialog.askstring(
            'Configurar minha cidade',
            'Qual cidade o Neymar deve usar quando você perguntar sobre o\n'
            'tempo/clima "aqui" ou "na minha região", sem dizer o nome dela?',
            initialvalue=atual,
            parent=self.root,
        )
        if cidade is None:
            return
        self.config['cidade_padrao'] = cidade.strip()
        config_arquivo.salvar(self.base, self.config)
        if cidade.strip():
            messagebox.showinfo('Configurar minha cidade', f'Pronto! Agora "como está o tempo aqui" vai usar {cidade.strip()}.')
        else:
            messagebox.showinfo('Configurar minha cidade', 'Cidade padrão removida — você vai precisar dizer o nome da cidade a cada vez.')

    def ativar(self):
        if self.ocupado.is_set():return
        if self.pausado.is_set():
            return
        bipe(880, 90)
        self.chamada_id += 1
        identificador = self.chamada_id
        self.ativo_ate = time.time() + 5
        self.estado_visual = 'listening'
        self.mostrar(frases.variar(frases.OUVINDO, self.config.get('tratamento', '')))
        self.ui(120, self.reforcar_topo)
        self.ui(450, self.reforcar_topo)
        self.ui(5000, lambda i=identificador: self.ocultar_sem_comando(i))

    def ocultar_sem_comando(self, identificador):
        if identificador != self.chamada_id or self.estado_visual != 'listening' or self.acao_pendente or time.time() < self.ativo_ate:
            return
        self.ativo_ate = 0
        self.estado_visual = 'idle'
        self.root.withdraw()
