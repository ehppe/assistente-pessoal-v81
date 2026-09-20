"""Tela de seleção e integração do modo de jogo com a fila de comandos."""
import os,threading
import tkinter as tk
from tkinter import ttk
import config as config_arquivo
from modo_jogo import APLICATIVOS,selecionados

class JogoMixin:
    def executar_modo_jogo(self,acao):
        if acao=='configurar':
            self.ui(0,self.abrir_modo_jogo);return 'Escolha os aplicativos na tela Modo de jogo. Salve para usar por voz.'
        if acao=='status':return self.modo_jogo.ultimo
        if getattr(self,'recuperando_jogo',False):return 'Estou restaurando o plano da sessão anterior. Aguarde alguns segundos.'
        if acao=='desativar':
            resposta=self.modo_jogo.desativar();self.ui(0,self.iniciar_indice);return resposta
        if not self.config.get('modo_jogo_configurado',False):
            self.ui(0,self.abrir_modo_jogo)
            return 'Na primeira vez, escolha os aplicativos que posso fechar na tela Modo de jogo. Depois use Salvar e ativar.'
        geracao=self.geracao
        return self.modo_jogo.ativar(dict(self.config),lambda:self.encerrar.is_set() or self.geracao!=geracao)

    def recuperar_modo_jogo(self):
        def run():
            try:
                mensagem=self.modo_jogo.desativar()
                self.registrar('RECUPERAÇÃO MODO JOGO: '+mensagem)
            finally:self.recuperando_jogo=False
        threading.Thread(target=run,daemon=True,name='NeymarRecuperarEnergia').start()

    def abrir_modo_jogo(self):
        if hasattr(self,'janela_jogo') and self.janela_jogo.winfo_exists():self.janela_jogo.deiconify();self.janela_jogo.lift();return
        from versao import TITULO
        w=self.janela_jogo=tk.Toplevel(self.root);w.title(TITULO+' — Modo de jogo');w.geometry('680x760');w.minsize(570,520)
        bg='#000000';fg='#e5efff';w.configure(bg=bg)
        rodape=tk.Frame(w,bg=bg);rodape.pack(side='bottom',fill='x',padx=18,pady=12)
        canvas=tk.Canvas(w,bg=bg,highlightthickness=0);scroll=ttk.Scrollbar(w,orient='vertical',command=canvas.yview)
        scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
        frame=tk.Frame(canvas,bg=bg);ident=canvas.create_window((0,0),window=frame,anchor='nw')
        frame.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(ident,width=e.width))
        def texto(t,fonte=10):
            tk.Label(frame,text=t,bg=bg,fg=fg,font=('Segoe UI',fonte),wraplength=570,justify='left',anchor='w').pack(fill='x',padx=18,pady=6)
        texto('Prepare o computador para jogar',18)
        texto('Marque apenas os aplicativos que você aceita fechar. Ao ativar por voz, a seleção salva será aplicada. Salve seu trabalho antes de começar.')
        texto('Steam, Discord, Gamers Club, jogos, OBS, Tailscale, antivírus e serviços do Windows ficam fora desta lista.')
        escolhas={};labels={};marcados=selecionados(self.config)
        for nome,rotulo in APLICATIVOS.items():
            linha=tk.Frame(frame,bg=bg);linha.pack(fill='x',padx=18)
            v=tk.BooleanVar(value=nome in marcados);escolhas[nome]=v
            tk.Checkbutton(linha,text=rotulo,variable=v,bg=bg,fg=fg,selectcolor='#17253d',activebackground=bg,activeforeground=fg).pack(side='left')
            label=tk.Label(linha,text='Consultando…',bg=bg,fg='#8da8bd');label.pack(side='right');labels[nome]=label
        alto=tk.BooleanVar(value=self.config.get('modo_jogo_alto_desempenho',False))
        tk.Checkbutton(frame,text='Usar plano Alto desempenho, se já existir no Windows',variable=alto,bg=bg,fg=fg,selectcolor='#17253d',activebackground=bg,activeforeground=fg).pack(anchor='w',padx=18,pady=(12,0))
        texto('Opcional: pode aumentar consumo e aquecimento. Ao sair, o plano anterior será restaurado, desde que você não tenha escolhido outro manualmente.')
        texto('O Neymar pausa sua indexação, reduz as atualizações da interface e usa prioridade normal. Não há garantia de aumento de FPS. Aplicativos fechados não serão reabertos automaticamente.')
        info=tk.StringVar(value=self.modo_jogo.ultimo)
        tk.Label(rodape,textvariable=info,bg=bg,fg='#8edfcc',wraplength=610,justify='left').pack(fill='x',pady=(0,8))
        def salvar(ativar=False):
            if self.modo_jogo.ativo or self.ocupado.is_set():info.set('Saia do modo de jogo e aguarde o pedido atual antes de alterar a seleção.');return
            nova=dict(self.config);nova['modo_jogo_fechar']=[n for n,v in escolhas.items() if v.get()]
            nova['modo_jogo_alto_desempenho']=alto.get();nova['modo_jogo_configurado']=True
            try:config_arquivo.salvar(self.base,nova)
            except OSError:info.set('Não consegui salvar as preferências.');return
            self.config=nova;info.set('Seleção salva. Diga Neymar, ativar modo de jogo.')
            if ativar:self.processar('ativar modo de jogo')
        botoes=tk.Frame(rodape,bg=bg);botoes.pack(fill='x')
        ttk.Button(botoes,text='Salvar',command=salvar).pack(side='left')
        ttk.Button(botoes,text='Salvar e ativar',command=lambda:salvar(True)).pack(side='left',padx=6)
        ttk.Button(botoes,text='Sair do modo de jogo',command=lambda:self.processar('sair do modo de jogo')).pack(side='left')
        def nativo():
            try:os.startfile('ms-settings:gaming-gamemode')
            except OSError:info.set('Não consegui abrir o Modo de Jogo do Windows. Procure Jogos nas Configurações do Windows.')
        ttk.Button(rodape,text='Abrir Modo de Jogo do Windows',command=nativo).pack(anchor='w',pady=(8,0))
        def carregar():
            try:
                totais={}
                for p in self.modo_jogo.sistema.processos():totais[p['nome']]=totais.get(p['nome'],0)+p['rss']
                erro=False
            except Exception:totais={};erro=True
            def aplicar():
                if not w.winfo_exists():return
                for nome,label in labels.items():label.config(text='Indisponível' if erro else f'{totais[nome]/2**20:.0f} MB em processos' if nome in totais else 'Não está aberto')
            self.ui(0,aplicar)
        threading.Thread(target=carregar,daemon=True).start()
