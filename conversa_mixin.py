"""Conversa e ajustes no Windows, sem navegador."""
import threading
import json
import subprocess
import sys
from pathlib import Path
from vozes import VOZES, instalada
from audio_edge import VOZES_EDGE
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import config as config_arquivo
from inteligencia import responder
from credenciais import salvar_chave, apagar_chave, caminho as caminho_chave

BG='#000000'
FG='#e5efff'


from visual_conversa import ChatVisualMixin

class ConversaMixin(ChatVisualMixin):
    def confirmar_no_chat(self):self.resolver_confirmacao(True,getattr(self,'token_chat',None))

    def enviar_chat(self,event=None):
        texto=self.texto_pedido.get('1.0','end').strip()
        if texto:self.processar(texto);self.texto_pedido.delete('1.0','end')
        return 'break'

    def receber_transcricao(self,texto,geracao):
        if self.encerrar.is_set() or self.pausado.is_set() or geracao!=self.geracao:return
        self.ativo_ate=0
        if self.acao_pendente or (getattr(self,'agenda',None) and self.agenda.proposta()):
            self.processar(texto);return
        if self.config.get('revisar_fala',False):
            self.abrir_conversa_classica()
            self.mostrar_pagina("conversa")
            if self.texto_pedido.get('1.0','end').strip():
                self.mostrar('Há um texto aguardando envio. Envie ou apague antes de gravar outro pedido.');return
            self.texto_pedido.insert('1.0',texto);self.texto_pedido.focus_set()
            self.mostrar('Ouvi: '+texto+' — Confira o texto e pressione Enter para enviar.')
        else:self.processar(texto)

    def apagar_chat(self):
        if messagebox.askyesno('Apagar conversa','Apagar o histórico local e começar uma conversa nova?',parent=getattr(self,"chat",self.root)):self.limpar_memoria()

    def abrir_configuracoes(self):
        if hasattr(self,'ajustes') and self.ajustes.winfo_exists():self.ajustes.lift();return
        from versao import TITULO
        w=self.ajustes=tk.Toplevel(self.root);w.title(TITULO+' — Configurações');w.geometry('760x820');w.minsize(620,620);w.configure(bg=BG)
        style=ttk.Style(w);style.theme_use('clam')
        style.configure('TFrame',background=BG)
        style.configure('TLabel',background=BG,foreground=FG,font=('Segoe UI',10))
        style.configure('TCheckbutton',background=BG,foreground=FG,font=('Segoe UI',10))
        style.map('TCheckbutton',background=[('active','#17253d')])
        style.configure('TButton',padding=7,font=('Segoe UI',10))
        canvas=tk.Canvas(w,highlightthickness=0,bg=BG);scroll=ttk.Scrollbar(w,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        frame=ttk.Frame(canvas,padding=20);window=canvas.create_window((0,0),window=frame,anchor='nw')
        frame.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        ttk.Label(frame,text='Conversa, voz e conexão',font=('Segoe UI',16,'bold')).grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,14))
        campos={};linha=1
        def campo(chave,rotulo,opcoes=None,senha=False):
            nonlocal linha
            ttk.Label(frame,text=rotulo).grid(row=linha,column=0,sticky='w',pady=5)
            v=tk.StringVar(value='' if senha else str(self.config.get(chave,'')));campos[chave]=v
            inp=ttk.Combobox(frame,textvariable=v,values=opcoes,state='readonly') if opcoes else ttk.Entry(frame,textvariable=v,show='•' if senha else '')
            inp.grid(row=linha,column=1,sticky='ew',pady=5);linha+=1
        campo('provedor_ia','Inteligência',['ollama','nvidia','gemini'])
        campo('modelo_nvidia','Modelo NVIDIA')
        campo('chave_nvidia','Chave NVIDIA (vazio mantém)',senha=True)
        campo('modelo_gemini','Modelo Gemini')
        campo('chave_gemini','Chave Gemini (vazio mantém)',senha=True)
        campo('modelo_ollama','Modelo Ollama')
        campo('provedor_voz','Voz das respostas',['windows','piper','edge'])
        campo('voz_edge','Voz Edge (online)',list(VOZES_EDGE))
        campo('ritmo_edge','Velocidade Edge (-30 a 30 %)')
        opcoes_piper={rotulo:chave for chave,rotulo in VOZES.items()}
        voz_piper=tk.StringVar(value=VOZES.get(self.config.get('voz_piper'),VOZES['pt_BR-faber-medium']))
        ttk.Label(frame,text='Voz Piper').grid(row=linha,column=0,sticky='w',pady=5)
        ttk.Combobox(frame,textvariable=voz_piper,values=list(opcoes_piper),state='readonly').grid(row=linha,column=1,sticky='ew');linha+=1
        opcoes_windows={'Automática (português, se disponível)':''}
        voz_windows=tk.StringVar(value=next(iter(opcoes_windows)))
        ttk.Label(frame,text='Voz Windows').grid(row=linha,column=0,sticky='w',pady=5)
        lista_windows=ttk.Combobox(frame,textvariable=voz_windows,values=list(opcoes_windows),state='readonly')
        lista_windows.grid(row=linha,column=1,sticky='ew');linha+=1
        windows_pronto=False
        def listar_windows():
            try:
                comando=([str(Path(sys.executable).with_name('NeymarWorker.exe')),'--voice-process','--listar'] if getattr(sys,'frozen',False)
                         else [str(Path(sys.executable).with_name('python.exe') if sys.platform=='win32' else Path(sys.executable)),str(self.base/'voz_processo.py'),'--listar'])
                ret=subprocess.run(comando,capture_output=True,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if ret.returncode:raise RuntimeError()
                vozes=json.loads(ret.stdout.decode('utf-8'))
            except Exception:vozes=[]
            def aplicar():
                nonlocal windows_pronto
                if not w.winfo_exists():return
                for i,v in enumerate(vozes):opcoes_windows[f"{v['nome']} ({i+1})"]=v['id']
                lista_windows.configure(values=list(opcoes_windows))
                voz_windows.set(next((n for n,i in opcoes_windows.items() if i==self.config.get('voz_windows','')),next(iter(opcoes_windows))))
                windows_pronto=bool(vozes)
            self.ui(0,aplicar)
        threading.Thread(target=listar_windows,daemon=True).start()
        campo('reconhecimento','Reconhecimento',['whisper','vosk','groq'])
        campo('perfil_whisper','Whisper: precisão ou velocidade',['precisao','rapido'])
        campo('chave_groq','Chave Groq (vazio mantém)',senha=True)
        campo('time_favorito','Time favorito (Série A)')
        campo('chave_futebol','Chave football-data.org',senha=True)
        campo('cidade_padrao','Cidade para previsão')
        campo('canal_modo_jogar','Apelido do canal no modo jogar')
        campo('segundos_conversa_continua','Segundos para continuar falando')
        campo('velocidade_voz','Velocidade Windows (100–250)')
        campo('ritmo_piper','Ritmo Piper (0.8–1.3; padrão 1.08)')
        import sounddevice as sd
        microfones={'Padrão do Windows':None}
        try:
            for i,d in enumerate(sd.query_devices()):
                if d['max_input_channels']>0:microfones[str(i)+' — '+d['name']]=i
        except Exception:pass
        mic=tk.StringVar(value=next((n for n,i in microfones.items() if i==self.config.get('microfone')),'Padrão do Windows'))
        ttk.Label(frame,text='Microfone').grid(row=linha,column=0,sticky='w')
        ttk.Combobox(frame,textvariable=mic,values=list(microfones),state='readonly').grid(row=linha,column=1,sticky='ew');linha+=1
        flags={}
        for nome,rotulo in [('diagnostico_tempos','Registrar tempos locais (sem gravar falas)'),('interromper_por_voz','Ouvir comandos curtos enquanto fala (preferir fones)'),('ativacao_por_voz','Ativar ao dizer Neymar (desmarque para usar só o botão)'),('revisar_fala','Revisar o que ouvi antes de enviar'),('fallback_ollama','Usar Ollama se a NVIDIA ou Gemini falhar'),('responder_por_voz','Falar respostas'),('perguntar_apos_resposta','Perguntar se preciso de algo mais'),('salvar_conversas','Salvar conversa neste computador')]:
            v=tk.BooleanVar(value=self.config.get(nome,False));flags[nome]=v
            ttk.Checkbutton(frame,text=rotulo,variable=v).grid(row=linha,column=0,columnspan=2,sticky='w',pady=5);linha+=1
        ttk.Label(frame,text='NVIDIA ou Gemini recebem a pergunta e o histórico recente na nuvem. Testar conexão faz uma consulta à API. Ollama é local.\nGroq recebe o áudio do pedido; Edge recebe o texto para falar. Ambos usam internet.\nPara este teste: execute o instalador 6, selecione groq e edge e salve.\nRitmo Piper: 1.0 é normal; 1.08 é um pouco mais rápido. Selecione piper para usar voz neural.',wraplength=580).grid(row=linha,column=0,columnspan=2,sticky='w',pady=8);linha+=1
        info=tk.StringVar(value=('Chave NVIDIA salva. ' if caminho_chave(self.base).exists() else 'Chave NVIDIA não cadastrada. ')+'Microfone: '+self.status_microfone)
        ttk.Label(frame,textvariable=info,wraplength=570).grid(row=linha,column=0,columnspan=2,sticky='w',pady=8);linha+=1
        def salvar():
            if self.ocupado.is_set() or not self.voz_concluida.is_set() or not self.fila_comandos.empty():info.set('Aguarde o pedido atual terminar para salvar.');return
            try:
                nova=dict(self.config)
                for k,v in campos.items():
                    if k not in ('chave_nvidia','chave_groq','chave_futebol','chave_gemini'):nova[k]=v.get().strip()
                nova['segundos_conversa_continua']=int(nova['segundos_conversa_continua'])
                nova['velocidade_voz']=int(nova['velocidade_voz'])
                nova['ritmo_edge']=int(nova['ritmo_edge'])
                if not -30<=nova['ritmo_edge']<=30:raise ValueError()
                nova['ritmo_piper']=float(nova['ritmo_piper'].replace(',','.'))
                if not 0.8<=nova['ritmo_piper']<=1.3:raise ValueError()
                if not 0<=nova['segundos_conversa_continua']<=30 or not 100<=nova['velocidade_voz']<=250:raise ValueError()
                if not nova['modelo_ollama'] or not nova['modelo_nvidia']:raise ValueError()
                nova['voz_piper']=opcoes_piper[voz_piper.get()]
                if windows_pronto:nova['voz_windows']=opcoes_windows[voz_windows.get()]
                if nova['provedor_voz']=='piper' and not instalada(self.base,nova['voz_piper']):
                    info.set('Voz não instalada. Execute 4 - Instalar voz Piper opcional.bat e tente salvar novamente.');return False
                chave=campos['chave_nvidia'].get().strip()
                if nova['provedor_ia']=='nvidia' and not chave and not caminho_chave(self.base).exists():
                    info.set('Cole sua chave NVIDIA para ativar a conversa online.');return False
                chave_gemini=campos['chave_gemini'].get().strip()
                if nova['provedor_ia']=='gemini':
                    if not nova['modelo_gemini']:raise ValueError()
                    if not chave_gemini and not caminho_chave(self.base,'gemini').exists():
                        info.set('Cole sua chave Gemini e salve.');return False
                for k,v in flags.items():nova[k]=v.get()
                nova['microfone']=microfones[mic.get()]
                if nova['reconhecimento']=='whisper' and not (self.base/'modelos'/'whisper-small'/'model.bin').is_file():
                    info.set('Execute 5 - Instalar reconhecimento Whisper.bat antes de selecionar whisper.');return False
                chave_groq=campos['chave_groq'].get().strip()
                if nova['reconhecimento']=='groq' and not chave_groq and not caminho_chave(self.base,'groq').exists():
                    info.set('Cole sua chave Groq para usar o reconhecimento online.');return False
                if chave_groq:salvar_chave(self.base,chave_groq,'groq');campos['chave_groq'].set('')
                if chave:salvar_chave(self.base,chave);campos['chave_nvidia'].set('')
                chave_futebol=campos['chave_futebol'].get().strip()
                if chave_futebol:salvar_chave(self.base,chave_futebol,'futebol');campos['chave_futebol'].set('')
                if chave_gemini:salvar_chave(self.base,chave_gemini,'gemini');campos['chave_gemini'].set('')
                config_arquivo.salvar(self.base,nova);self.config=nova
                self.memoria.persistir=nova['salvar_conversas']
                if nova['salvar_conversas']:self.memoria.salvar()
                elif self.memoria.caminho.exists():self.memoria.caminho.unlink()
                info.set('Salvo. Inteligência: '+nova['provedor_ia']+'. Use Testar conexão.');return True
            except ValueError:info.set('Confira os modelos e ritmos: Edge -30 a 30; Piper 0.8 a 1.3; Windows 100 a 250.')
            except Exception:info.set('Não consegui salvar. Confira permissão de escrita e instalação do pywin32.')
        def testar():
            if getattr(self,'testando_conexao',False):return
            if not salvar():return
            cfg=dict(self.config)
            self.testando_conexao=True
            info.set('Testando '+cfg['provedor_ia']+'…')
            def run():
                try:
                    texto=responder(self.base,cfg,[],'Responda apenas: conexão funcionando.',permitir_fallback=False)
                    resultado='Conexão '+cfg['provedor_ia']+' OK: '+texto[:150]+' | Microfone: '+self.status_microfone
                except Exception as e:resultado=str(e)
                def concluir():
                    self.testando_conexao=False
                    if w.winfo_exists():info.set(resultado)
                self.ui(0,concluir)
            threading.Thread(target=run,daemon=True).start()
        botoes=ttk.Frame(frame);botoes.grid(row=linha,column=0,columnspan=2,sticky='ew',pady=10)
        ttk.Button(botoes,text='Salvar',command=salvar).pack(side='left')
        ttk.Button(botoes,text='Testar conexão',command=testar).pack(side='left',padx=6)
        def testar_voz():
            if self.ocupado.is_set() or not self.voz_concluida.is_set():info.set('Aguarde o pedido ou a fala terminar.');return
            if not salvar():return
            if not self.config.get('responder_por_voz',True):info.set('Marque Falar respostas e tente novamente.');return
            info.set('Preferências salvas. Testando a voz escolhida…')
            nome=str(self.config.get('nome_usuario','')).strip()
            self.falar('Boa noite'+((', '+nome) if nome else '')+'. Neymar à disposição. O que vamos fazer agora?')
        ttk.Button(botoes,text='Testar voz',command=testar_voz).pack(side='left')
        ttk.Button(botoes,text='Canais Discord',command=self.adicionar_canal_discord).pack(side='left',padx=6)
        ttk.Button(frame,text='Parar fala — Ctrl + Alt + Espaço',command=self.parar_fala).grid(row=linha+2,column=0,columnspan=2,sticky='w',pady=6)
        w.bind('<Escape>',lambda e:self.parar_fala())
        def remover_chave():
            try:
                apagar_chave(self.base);campos['chave_nvidia'].set('');info.set('Chave removida. Selecione ollama para conversar localmente.')
            except OSError:info.set('Não consegui remover a chave. Confira a permissão da pasta.')
        ttk.Button(frame,text='Remover chave NVIDIA salva',command=remover_chave).grid(row=linha+1,column=0,columnspan=2,sticky='w',pady=6)
        def testar_groq():
            if getattr(self,'testando_groq',False):return
            if not salvar():return
            self.testando_groq=True;info.set('Verificando chave e modelo na Groq…')
            def run():
                try:
                    from reconhecimento_groq import testar_chave
                    resultado=testar_chave(self.base)
                except Exception as e:resultado=str(e) if isinstance(e,RuntimeError) else 'Falha ao verificar Groq.'
                def fim():
                    self.testando_groq=False
                    if w.winfo_exists():info.set(resultado)
                self.ui(0,fim)
            threading.Thread(target=run,daemon=True).start()
        def remover_groq():
            try:
                apagar_chave(self.base,'groq');campos['chave_groq'].set('');info.set('Chave Groq removida. Selecione whisper ou vosk para reconhecer localmente.')
            except OSError:info.set('Não consegui remover a chave Groq.')
        ttk.Button(frame,text='Testar chave Groq',command=testar_groq).grid(row=linha+3,column=0,sticky='w',pady=6)
        ttk.Button(frame,text='Remover chave Groq',command=remover_groq).grid(row=linha+3,column=1,sticky='w',pady=6)
        def remover_futebol():
            try:
                apagar_chave(self.base,'futebol');campos['chave_futebol'].set('');info.set('Chave de futebol removida.')
            except OSError:info.set('Não consegui remover a chave de futebol.')
        ttk.Button(frame,text='Configurar modo de jogo',command=self.abrir_modo_jogo).grid(row=linha+5,column=0,columnspan=2,sticky='w',pady=6)
        ttk.Button(frame,text='Remover chave de futebol',command=remover_futebol).grid(row=linha+4,column=0,columnspan=2,sticky='w',pady=6)
        def ver_tempos():
            from desempenho import resumo
            from tkinter import messagebox
            messagebox.showinfo('Tempos do Neymar',resumo(self.base),parent=w)
        ttk.Button(frame,text='Ver tempos de resposta',command=ver_tempos).grid(row=linha+6,column=0,columnspan=2,sticky='w',pady=6)
        def remover_gemini():
            try:
                apagar_chave(self.base,'gemini');campos['chave_gemini'].set('');info.set('Chave Gemini removida. Selecione ollama para conversar localmente.')
            except OSError:info.set('Não consegui remover a chave Gemini.')
        ttk.Button(frame,text='Remover chave Gemini',command=remover_gemini).grid(row=linha+7,column=0,columnspan=2,sticky='w',pady=6)
        def consultar_modelos():
            if getattr(self,'consultando_gemini',False):return
            if not salvar():return
            self.consultando_gemini=True;info.set('Consultando o catálogo Gemini…')
            def run():
                try:
                    from gemini_modelos import listar
                    nomes=listar(self.base);erro=None
                except Exception as e:
                    nomes=[];erro=str(e) if isinstance(e,RuntimeError) else 'Não consegui consultar o catálogo.'
                def concluir():
                    self.consultando_gemini=False
                    if not w.winfo_exists():return
                    if erro:info.set(erro);return
                    if not nomes:info.set('Nenhum modelo Gemini com geração de conteúdo foi retornado.');return
                    janela=tk.Toplevel(w);janela.title('Modelos retornados pelo Google');janela.geometry('650x400')
                    ttk.Label(janela,text='Escolha um modelo de texto. Preço e suporte a áudio/imagens variam.\nA lista não garante cota para gerar respostas. Depois use Testar conexão.').pack(padx=10,pady=10)
                    lista=tk.Listbox(janela);lista.pack(fill='both',expand=True,padx=10)
                    for nome in nomes:lista.insert('end',nome)
                    def escolher():
                        sel=lista.curselection()
                        if not sel:return
                        campos['modelo_gemini'].set(nomes[sel[0]])
                        info.set('Modelo selecionado. Clique Salvar e Testar conexão.');janela.destroy()
                    ttk.Button(janela,text='Usar modelo selecionado',command=escolher).pack(pady=10)
                    info.set('Catálogo carregado. Nenhum modelo foi trocado automaticamente.')
                self.ui(0,concluir)
            threading.Thread(target=run,daemon=True).start()
        ttk.Button(frame,text='Consultar modelos Gemini',command=consultar_modelos).grid(row=linha+8,column=0,columnspan=2,sticky='w',pady=6)
        frame.columnconfigure(1,weight=1)
