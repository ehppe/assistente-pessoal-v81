"""Assistente gráfico de primeira configuração, sem exigir edição de JSON."""
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from config import carregar, salvar
from versao import TITULO

BASE = Path(__file__).resolve().parent

def main():
    cfg=carregar(BASE)
    root=tk.Tk();root.title(TITULO+' — Primeira configuração');root.geometry('560x500');root.resizable(False,False)
    corpo=ttk.Frame(root,padding=28);corpo.pack(fill='both',expand=True)
    ttk.Label(corpo,text='Bem-vindo ao '+TITULO,font=('Segoe UI',18,'bold')).pack(anchor='w')
    ttk.Label(corpo,text='Defina seu perfil. Chaves de API continuam sendo configuradas dentro do Neymar.',wraplength=490).pack(anchor='w',pady=(6,20))
    valores={}
    for chave,rotulo in [('nome_usuario','Como devo chamar você?'),('nome_assistente','Como o assistente deve se chamar?'),('cidade_padrao','Cidade para previsão do tempo'),('time_favorito','Time favorito')]:
        ttk.Label(corpo,text=rotulo).pack(anchor='w',pady=(8,3))
        v=tk.StringVar(value=str(cfg.get(chave,'')));valores[chave]=v
        ttk.Entry(corpo,textvariable=v).pack(fill='x')
    salvar_hist=tk.BooleanVar(value=bool(cfg.get('salvar_conversas',True)))
    remoto_hist=tk.BooleanVar(value=bool(cfg.get('painel_compartilhar_historico',False)))
    ttk.Checkbutton(corpo,text='Salvar conversas neste computador',variable=salvar_hist).pack(anchor='w',pady=(18,4))
    ttk.Checkbutton(corpo,text='Mostrar histórico no painel do telefone',variable=remoto_hist).pack(anchor='w')
    ttk.Label(corpo,text='Privacidade: o painel do telefone vem sem histórico por padrão. Credenciais online são protegidas pelo Windows.',wraplength=490).pack(anchor='w',pady=(15,20))
    def concluir():
        for chave,var in valores.items():cfg[chave]=var.get().strip()[:80]
        nome=cfg.get('nome_assistente') or 'Neymar';cfg['nome_assistente']=nome;cfg['palavras_ativacao']=[nome.lower()]
        cfg['salvar_conversas']=salvar_hist.get();cfg['painel_compartilhar_historico']=remoto_hist.get();cfg['configuracao_inicial_concluida']=True
        salvar(BASE,cfg);messagebox.showinfo(TITULO,'Perfil salvo. Agora você pode iniciar o Neymar.');root.destroy()
    ttk.Button(corpo,text='Salvar e concluir',command=concluir).pack(anchor='e',pady=10)
    root.mainloop()

if __name__=='__main__':main()
