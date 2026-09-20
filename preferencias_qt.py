"""Preferências declarativas: somente campos permitidos atravessam a ponte."""
from pathlib import Path
from config import salvar
from credenciais import caminho, salvar_chave
from vozes import VOZES, instalada
from audio_edge import VOZES_EDGE

CAMPOS=[
 ('Sistema','nome_usuario','Como devo chamar você?',[]),
 ('Sistema','nome_assistente','Nome do assistente',[]),
 ('Inteligência','provedor_ia','Inteligência',['ollama','gemini','nvidia']),
 ('Inteligência','modelo_gemini','Modelo Gemini',[]),
 ('Inteligência','modelo_nvidia','Modelo NVIDIA',[]),
 ('Inteligência','modelo_ollama','Modelo Ollama',[]),
 ('Inteligência','chave_gemini','Chave Gemini · vazio mantém','senha'),
 ('Inteligência','chave_nvidia','Chave NVIDIA · vazio mantém','senha'),
 ('Inteligência','fallback_ollama','Usar Ollama se a API falhar','bool'),
 ('Voz','provedor_voz','Voz das respostas',['windows','piper','edge']),
 ('Voz','voz_edge','Voz Edge',list(VOZES_EDGE)),
 ('Voz','voz_piper','Voz Piper',list(VOZES)),
 ('Voz','ritmo_edge','Ritmo Edge · -30 a 30',[]),
 ('Voz','ritmo_piper','Ritmo Piper · 0.8 a 1.3',[]),
 ('Voz','velocidade_voz','Velocidade Windows · 100 a 250',[]),
 ('Voz','responder_por_voz','Falar respostas','bool'),
 ('Voz','perguntar_apos_resposta','Perguntar se preciso de algo mais','bool'),
 ('Microfone','reconhecimento','Reconhecimento',['whisper','vosk','groq']),
 ('Microfone','perfil_whisper','Perfil Whisper',['precisao','rapido']),
 ('Microfone','microfone','Dispositivo de entrada',[]),
 ('Microfone','chave_groq','Chave Groq · vazio mantém','senha'),
 ('Microfone','ativacao_por_voz','Ativar ao dizer o nome do assistente','bool'),
 ('Microfone','interromper_por_voz','Permitir interrupção por voz','bool'),
 ('Microfone','revisar_fala','Revisar transcrição antes de enviar','bool'),
 ('Microfone','segundos_conversa_continua','Conversa contínua · 0 a 30 segundos',[]),
 ('Sistema','cidade_padrao','Cidade para previsão',[]),
 ('Sistema','time_favorito','Time favorito',[]),
 ('Sistema','chave_futebol','Chave football-data.org · vazio mantém','senha'),
 ('Sistema','chave_brave','Chave Brave Search · vazio mantém ou desativa a pesquisa real','senha'),
 ('Sistema','canal_modo_jogar','Apelido do canal Discord',[]),
 ('Sistema','salvar_conversas','Salvar histórico neste computador','bool'),
 ('Sistema','painel_compartilhar_historico','Mostrar histórico no painel do telefone','bool'),
 ('Sistema','diagnostico_tempos','Registrar tempos de resposta','bool')]
SEGREDOS={'chave_gemini':'gemini','chave_nvidia':'nvidia','chave_groq':'groq','chave_futebol':'futebol','chave_brave':'brave'}

def esquema(app):
    mics=[{'nome':'Padrão do Windows','valor':''}]
    try:
        import sounddevice as sd
        for i,d in enumerate(sd.query_devices()):
            if d['max_input_channels']>0:mics.append({'nome':str(i)+' · '+d['name'],'valor':str(i)})
    except Exception:pass
    saida=[]
    for aba,k,label,tipo in CAMPOS:
        valor='' if k in SEGREDOS else app.config.get(k,'')
        if k=='microfone':valor='' if valor is None else str(valor)
        saida.append({'aba':aba,'chave':k,'rotulo':label,'tipo':tipo if isinstance(tipo,str) else ('lista' if tipo else 'texto'),
                     'opcoes':tipo if isinstance(tipo,list) else [],'valor':valor})
    return {'campos':saida,'microfones':mics}

def validar(app,entrada):
    if not isinstance(entrada,dict):raise ValueError('Preferências inválidas.')
    permitidos={k for _,k,_,_ in CAMPOS}
    if set(entrada)-permitidos:raise ValueError('Campo não permitido.')
    nova=dict(app.config)
    for _,k,label,tipo in CAMPOS:
        if k not in entrada or k in SEGREDOS:continue
        v=entrada[k]
        if tipo=='bool':
            if not isinstance(v,bool):raise ValueError('Confira '+label)
        else:
            v=str(v).strip()
            if len(v)>250:raise ValueError('Campo muito longo: '+label)
            if isinstance(tipo,list) and tipo and v not in tipo:raise ValueError('Confira '+label)
        nova[k]=v
    if len(nova.get('nome_usuario',''))>60:raise ValueError('Nome muito longo.')
    nome_assistente=nova.get('nome_assistente','').strip()
    if not nome_assistente or len(nome_assistente)>30 or not nome_assistente.replace(' ','').isalpha():raise ValueError('Use um nome de assistente com até 30 letras.')
    nova['palavras_ativacao']=[nome_assistente.lower()]
    for k,lo,hi,converter in [('ritmo_edge',-30,30,int),('ritmo_piper',.8,1.3,float),
                             ('velocidade_voz',100,250,int),('segundos_conversa_continua',0,30,int)]:
        try:v=converter(str(nova[k]).replace(',','.'))
        except (ValueError,TypeError):raise ValueError('Número inválido: '+k)
        if not lo<=v<=hi:raise ValueError('Fora do intervalo: '+k)
        nova[k]=v
    mic=nova.get('microfone')
    if mic in ('',None):nova['microfone']=None
    else:
        try:nova['microfone']=int(mic)
        except (ValueError,TypeError):raise ValueError('Microfone inválido.')
        import sounddevice as sd
        if sd.query_devices(nova['microfone'])['max_input_channels']<=0:raise ValueError('Selecione um microfone de entrada.')
    for k in ('modelo_gemini','modelo_nvidia','modelo_ollama'):
        if not nova.get(k):raise ValueError('Informe '+k)
    if nova['provedor_voz']=='piper' and not instalada(app.base,nova['voz_piper']):
        raise ValueError('Instale a voz Piper selecionada pelo instalador 4.')
    if nova['reconhecimento']=='whisper' and not (app.base/'modelos/whisper-small/model.bin').is_file():
        raise ValueError('Instale o Whisper pelo instalador 5.')
    for prov,necessario in [('gemini',nova['provedor_ia']=='gemini'),('nvidia',nova['provedor_ia']=='nvidia'),('groq',nova['reconhecimento']=='groq')]:
        if necessario and not entrada.get('chave_'+prov,'').strip() and not caminho(app.base,prov).exists():
            raise ValueError('Informe a chave '+prov)
    return nova

def gravar(app,entrada):
    if app.ocupado.is_set() or not app.voz_concluida.is_set() or not app.fila_comandos.empty():
        raise ValueError('Aguarde o pedido e a fala terminarem.')
    nova=validar(app,entrada)
    for k,prov in SEGREDOS.items():
        segredo=entrada.get(k,'')
        if not isinstance(segredo,str):raise ValueError('Chave inválida.')
        if segredo.strip():salvar_chave(app.base,segredo.strip(),prov)
    salvar(app.base,nova)
    app.config=nova
    app.memoria.persistir=nova['salvar_conversas']
    if nova['salvar_conversas']:app.memoria.salvar()
    elif app.memoria.caminho.exists():app.memoria.caminho.unlink()
    return 'Salvo. Reinicie o Neymar para aplicar alterações do microfone e da ativação por voz.'

def gravar_jogo(app,entrada):
    from modo_jogo import APLICATIVOS
    if app.modo_jogo.ativo or app.ocupado.is_set():raise ValueError('Saia do modo de jogo e aguarde o pedido terminar.')
    nomes=entrada.get('programas')
    alto=entrada.get('alto')
    gamebar=entrada.get('gamebar',False)
    indexacao=entrada.get('indexacao',False)
    if (not isinstance(nomes,list) or any(not isinstance(n,str) or n not in APLICATIVOS for n in nomes)
            or not isinstance(alto,bool) or not isinstance(gamebar,bool) or not isinstance(indexacao,bool)):
        raise ValueError('Seleção de programas inválida.')
    nova=dict(app.config,modo_jogo_fechar=sorted(set(nomes)),modo_jogo_alto_desempenho=alto,
              modo_jogo_gamebar=gamebar,modo_jogo_pausar_indexacao=indexacao,modo_jogo_configurado=True)
    salvar(app.base,nova);app.config=nova
    return 'Seleção salva. Apenas os programas marcados poderão ser fechados.'
