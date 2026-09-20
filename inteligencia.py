"""Conversa NVIDIA com alternativa local Ollama; nenhum comando é executado aqui."""
from credenciais import ler_chave
import requests
from desempenho import medir_ia
from calendario_local import contexto_relogio
from texto_resposta import resposta_final, contexto_limpo

def identidade(config):
    nome=str(config.get('nome_usuario','')).strip()
    assistente=str(config.get('nome_assistente','Neymar')).strip() or 'Neymar'
    return 'Você é '+assistente+', assistente pessoal'+((' de '+nome) if nome else '')+'. '


@medir_ia('ia_ollama')
def responder_local(base, config, contexto, pergunta):
    instrucoes = (identidade(config)+'Responda em português do Brasil com clareza. '
        'Use o histórico para entender perguntas de continuação. Seja breve, detalhando quando solicitado. '
        'Você está no modo conversa e não executa programas nem vê a tela ou arquivos. '
        'Não afirme ter realizado ações. Para controlar o Windows, sugira uma ordem direta. '
        'Não tem acesso à internet nesta conversa. Não invente fatos atuais. Não ofereça nem prometa agendar lembretes por conta própria; isso depende da função de agenda do programa. Responda em texto, sem JSON.')
    instrucoes=contexto_relogio()+instrucoes
    modelo=config.get('modelo_ollama','qwen2.5:3b')
    try:
        r=requests.post('http://127.0.0.1:11434/api/chat',timeout=(3,120),json={
            'model':modelo,'stream':False,'keep_alive':'10m',
            'messages':[{'role':'system','content':instrucoes}]+contexto_limpo(contexto)+[{'role':'user','content':pergunta}],
            'options':{'num_predict':650}})
        if r.status_code!=200:
            raise RuntimeError('Ollama local: confira se o modelo '+modelo+' está instalado. Execute 3 - Instalar IA local opcional.bat (HTTP '+str(r.status_code)+').')
        texto=r.json().get('message',{}).get('content','')
        if not isinstance(texto,str) or not texto.strip():raise RuntimeError('A inteligência local não retornou uma resposta. Tente novamente.')
        return texto.strip()
    except requests.Timeout:
        raise RuntimeError('O modelo local demorou demais. Feche programas pesados e tente novamente; a primeira resposta pode demorar para carregar.') from None
    except requests.ConnectionError:
        raise RuntimeError('Ollama não está aberto. Abra o Ollama pelo menu Iniciar e tente novamente.') from None
    except ValueError:
        raise RuntimeError('Ollama retornou uma resposta inválida. Tente novamente.') from None


@medir_ia('ia_nvidia')
def responder_nvidia(base,config,contexto,pergunta):
    chave=ler_chave(base)
    mensagens=[{'role':'system','content':
        identidade(config)+'Responda em português brasileiro com clareza. '
        'Entregue somente a resposta final, em português do Brasil. Não narre sua preparação nem escreva um monólogo em inglês. '
        'Fale de forma natural, com frases curtas; evite listas e formatação quando não forem necessárias. '
        'Use de duas a quatro frases por padrão, detalhando quando solicitado. Você apenas conversa: '
        'não executa ações, não vê a tela nem arquivos e não pesquisa na internet. '
        'Não afirme ter feito ações. Não invente fatos atuais. Não ofereça nem prometa agendar lembretes por conta própria; isso depende da função de agenda do programa.'}]+contexto_limpo(contexto)+[{'role':'user','content':pergunta}]
    mensagens[0]['content']=contexto_relogio()+mensagens[0]['content']
    modelo=config.get('modelo_nvidia','nvidia/nemotron-3-super-120b-a12b')
    corpo={'model':modelo,'messages':mensagens,'max_tokens':1024,'temperature':0.5,'stream':False}
    if modelo=='nvidia/nemotron-3-super-120b-a12b':
        corpo.update(temperature=1.0,top_p=0.95,chat_template_kwargs={'enable_thinking':False})
    try:
        r=requests.post('https://integrate.api.nvidia.com/v1/chat/completions',
            headers={'Authorization':'Bearer '+chave,'Accept':'application/json'},
            json=corpo,
            timeout=(5,45),allow_redirects=False)
        erros={401:'Chave NVIDIA inválida ou expirada.',403:'Sua conta não tem acesso a esse modelo NVIDIA.',
               410:'Modelo retirado da API NVIDIA. Use nvidia/nemotron-3-super-120b-a12b.',
               404:'Modelo NVIDIA indisponível. Confira o identificador nas Configurações.',
               429:'Limite de uso da NVIDIA atingido. Aguarde e tente novamente.',
               402:'NVIDIA recusou por cota ou cobrança. Confira sua conta; o Neymar não ativa planos pagos.'}
        if r.status_code!=200:raise RuntimeError(erros.get(r.status_code,'NVIDIA indisponível (HTTP '+str(r.status_code)+').'))
        texto=resposta_final(r.json()['choices'][0]['message'].get('content',''))
        if not isinstance(texto,str) or not texto.strip():raise ValueError()
        return texto.strip()
    except requests.Timeout:raise RuntimeError('NVIDIA demorou demais para responder.') from None
    except requests.RequestException:raise RuntimeError('Não consegui conectar à NVIDIA. Confira a internet.') from None
    except (ValueError,KeyError,IndexError,TypeError):raise RuntimeError('NVIDIA retornou uma resposta inválida ou vazia.') from None


@medir_ia('ia_gemini')
def responder_gemini(base,config,contexto,pergunta):
    chave=ler_chave(base,'gemini')
    from gemini_modelos import normalizar, verificar
    modelo=normalizar(config.get('modelo_gemini','gemini-2.5-flash-lite'))
    mensagens=[{'role':'system','content':contexto_relogio()+
        identidade(config)+'Responda somente em português brasileiro, '
        'com duas a quatro frases por padrão, detalhando quando solicitado. '
        'Entregue apenas a resposta final. Você apenas conversa: não executa ações, '
        'não vê arquivos nem a tela e não pesquisa na internet. Não invente fatos atuais '
        'nem afirme ter executado ações. Não ofereça agendar lembretes por conta própria.'}]
    mensagens+=contexto_limpo(contexto)+[{'role':'user','content':pergunta}]
    corpo={'systemInstruction':{'parts':[{'text':mensagens[0]['content']}]},
        'contents':[{'role':'model' if m['role']=='assistant' else 'user',
                     'parts':[{'text':m['content']}]} for m in mensagens[1:]],
        'generationConfig':{'maxOutputTokens':650}}
    if modelo in ('gemini-2.5-flash-lite','gemini-2.5-flash'):
        corpo['generationConfig']['thinkingConfig']={'thinkingBudget':0}
    try:
        resp=requests.post('https://generativelanguage.googleapis.com/v1beta/models/'+modelo+':generateContent',
            headers={'x-goog-api-key':chave,'Content-Type':'application/json'},
            json=corpo,timeout=(5,45),allow_redirects=False)
        verificar(resp, chave=chave, modelo=modelo)
        partes=resp.json()['candidates'][0]['content']['parts']
        texto=''.join(p['text'] for p in partes if not p.get('thought',False) and isinstance(p.get('text'),str))
        texto=resposta_final(texto).strip()
        if not texto:raise ValueError()
        return texto
    except requests.Timeout:raise RuntimeError('Gemini demorou demais para responder.') from None
    except requests.RequestException:raise RuntimeError('Não consegui conectar ao Gemini. Confira a internet.') from None
    except (ValueError,KeyError,IndexError,TypeError,AttributeError):
        raise RuntimeError('Gemini retornou resposta vazia, bloqueada ou inválida.') from None


@medir_ia('ia_total')
def responder(base,config,contexto,pergunta,permitir_fallback=True):
    provedor=config.get('provedor_ia')
    if provedor not in ('nvidia','gemini'):return responder_local(base,config,contexto,pergunta)
    remoto=responder_gemini if provedor=='gemini' else responder_nvidia
    try:return remoto(base,config,contexto,pergunta)
    except RuntimeError as erro:
        if not permitir_fallback or not config.get('fallback_ollama',True):raise
        try:texto=responder_local(base,config,contexto,pergunta)
        except RuntimeError as local:raise RuntimeError(str(erro)+' Também não consegui usar o Ollama: '+str(local)) from None
        return '['+str(erro)+' Resposta pelo Ollama local.]\n\n'+texto
