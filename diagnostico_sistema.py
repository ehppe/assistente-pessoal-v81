"""Diagnóstico local legível, sem copiar chaves ou conteúdo de conversas."""
from pathlib import Path
import importlib.util, json, os, platform, shutil, sys

from config import carregar
from versao import TITULO

BASE=Path(__file__).resolve().parent

def sim_nao(v):return 'sim' if v else 'não'

def gerar():
    cfg=carregar(BASE)
    modulos=['requests','psutil','sounddevice','vosk','PIL','pystray','PySide6']
    linhas=[TITULO+' — Diagnóstico seguro',
            'Sistema: '+platform.platform(),
            'Python: '+sys.version.split()[0],
            'Executável: '+sys.executable,
            'Windows: '+sim_nao(os.name=='nt'),
            'Ollama encontrado: '+sim_nao(bool(shutil.which('ollama'))),
            'Tailscale encontrado: '+sim_nao(bool(shutil.which('tailscale'))),
            '', 'Componentes:']
    linhas += ['- '+m+': '+('instalado' if importlib.util.find_spec(m) else 'ausente') for m in modulos]
    linhas += ['', 'Configuração (sem segredos):',
        '- IA: '+str(cfg.get('provedor_ia')),
        '- Voz: '+str(cfg.get('provedor_voz')),
        '- Reconhecimento: '+str(cfg.get('reconhecimento')),
        '- Histórico local: '+sim_nao(cfg.get('salvar_conversas')),
        '- Histórico no telefone: '+sim_nao(cfg.get('painel_compartilhar_historico')),
        '- Modo jogo configurado: '+sim_nao(cfg.get('modo_jogo_configurado'))]
    dados=BASE/'dados'
    linhas += ['', 'Arquivos de erro:']
    erros=list(dados.glob('*erro*.log')) if dados.exists() else []
    linhas += ['- '+p.name for p in erros] or ['- nenhum']
    return '\n'.join(linhas)+'\n'

if __name__=='__main__':
    texto=gerar();saida=BASE/'dados'/'diagnostico-seguro.txt';saida.parent.mkdir(exist_ok=True);saida.write_text(texto,encoding='utf-8');print(texto);print('Salvo em:',saida)
