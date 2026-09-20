"""Carrega e salva as preferências do Neymar em config.json, na pasta do assistente.

Editar o config.json permite mudar o microfone, o
canal do Discord e outros ajustes sem mexer no código.
"""
import json
import copy

PADRAO = {
    "nome_usuario": "",
    "nome_assistente": "Neymar",
    "configuracao_inicial_concluida": False,
    "painel_compartilhar_historico": False,
    "modelo_gemini": "gemini-2.5-flash-lite",
    "perfil_whisper": "precisao",
    "diagnostico_tempos": False,
    "modo_jogo_configurado": False,
    "modo_jogo_fechar": [],
    "modo_jogo_alto_desempenho": False,
    "provedor_ia": "ollama",
    "modelo_nvidia": "nvidia/nemotron-3-super-120b-a12b",
    "ritmo_piper": 1.08,
    "fallback_ollama": True,
    "provedor_voz": "windows",
    "voz_piper": "pt_BR-faber-medium",
    "voz_windows": "",
    "voz_edge": "Antonio — masculina (Brasil)",
    "ritmo_edge": 0,
    "time_favorito": "Corinthians",
    "modelo_ollama": "qwen2.5:3b",
    "salvar_conversas": True,
    "responder_por_voz": True,
    "velocidade_voz": 172,
    "canal_modo_jogar": "",
    "palavras_ativacao": ["neymar"],
    "microfone": None,
    "reconhecimento": "vosk",
    "revisar_fala": False,
    "usar_voz_piper": False,
    "discord_servidor_id": "",
    "discord_canal_id": "",
    "discord_apelidos_canal": [],
    "discord_canais": [],
    "segundos_conversa_continua": 0,
    "ativacao_por_voz": True,
    "interromper_por_voz": True,
    "segundos_ocultar_janela": 4,
    "tratamento": "",
    "cidade_padrao": "",
    "usar_localizacao_automatica": True,
    "cor_nucleo": [64, 207, 255],
    "usar_windows_search": False,
    "usar_automacao_janelas": True,
}


def carregar(base):
    caminho = base / "config.json"
    config = copy.deepcopy(PADRAO)
    if caminho.exists():
        try:
            salvo = json.loads(caminho.read_text(encoding="utf-8"))
            if isinstance(salvo, dict):
                config.update(salvo)
        except Exception:
            pass
    else:
        salvar(base, config)
    if not config.get('migracao_ativacao_57',False):
        config['segundos_conversa_continua']=0
        config['palavras_ativacao']=['neymar']
        config['migracao_ativacao_57']=True
        salvar(base,config)
    nome_assistente=str(config.get('nome_assistente','Neymar')).strip() or 'Neymar'
    config['nome_assistente']=nome_assistente[:30]
    esperado=[nome_assistente.lower()]
    if config.get('palavras_ativacao') != esperado:
        config['palavras_ativacao']=esperado
        salvar(base,config)
    if not config.get('migracao_envio_60',False):
        config['revisar_fala']=False
        config['migracao_envio_60']=True
        salvar(base,config)
    for chave, padrao in PADRAO.items():
        valor = config.get(chave)
        if padrao is not None and type(valor) is not type(padrao):config[chave]=copy.deepcopy(padrao)
    if config['modelo_nvidia']=='meta/llama-3.3-70b-instruct':config['modelo_nvidia']=PADRAO['modelo_nvidia']
    config['ritmo_piper']=max(0.8,min(1.3,config['ritmo_piper']))
    from vozes import VOZES
    if config['voz_piper'] not in VOZES:config['voz_piper']='pt_BR-faber-medium'
    if config['provedor_ia'] not in ('ollama','nvidia','gemini'):config['provedor_ia']='ollama'
    for chave in ('modelo_openai','voz_openai','OPENAI_API_KEY','api_key'):config.pop(chave,None)
    if config['provedor_voz'] not in ('windows','piper','edge'):config['provedor_voz']='windows'
    if config['reconhecimento'] not in ('whisper','vosk','groq'):config['reconhecimento']='whisper'
    from audio_edge import VOZES_EDGE
    if config['voz_edge'] not in VOZES_EDGE:config['voz_edge']=PADRAO['voz_edge']
    config['ritmo_edge']=max(-30,min(30,config['ritmo_edge']))
    config['segundos_conversa_continua']=max(0,min(30,config['segundos_conversa_continua']))
    config['velocidade_voz']=max(100,min(250,config['velocidade_voz']))
    if not config['palavras_ativacao'] or not all(isinstance(p,str) and p.strip() for p in config['palavras_ativacao']):config['palavras_ativacao']=PADRAO['palavras_ativacao'][:]
    if len(config['cor_nucleo']) != 3 or not all(type(c) is int and 0<=c<=255 for c in config['cor_nucleo']):config['cor_nucleo']=PADRAO['cor_nucleo'][:]
    config['discord_canais']=[c for c in config['discord_canais'] if isinstance(c,dict) and isinstance(c.get('apelidos'),list) and c['apelidos'] and all(isinstance(a,str) for a in c['apelidos'])]
    from modo_jogo import selecionados
    config['modo_jogo_fechar']=selecionados(config)
    return config


def salvar(base, config):
    caminho = base / "config.json"
    temp = caminho.with_suffix('.tmp')
    config = {k:v for k,v in config.items() if k not in ('chave_gemini','GEMINI_API_KEY')}
    temp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(caminho)
