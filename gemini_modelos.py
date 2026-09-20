"""Catálogo oficial consultado somente por solicitação do usuário."""
import re
import requests
from credenciais import ler_chave

def normalizar(nome):
    nome=str(nome).strip().removeprefix('models/')
    if not re.fullmatch(r'gemini-[a-zA-Z0-9._-]+',nome):
        raise RuntimeError('Identificador Gemini inválido. Use Consultar modelos Gemini.')
    return nome

def verificar(resp, chave="", modelo=""):
    if resp.status_code==200:return
    erros={400:'Pedido ou chave Gemini inválidos.',401:'Chave Gemini inválida.',403:'Gemini sem permissão: confira o projeto e as restrições da chave.',404:'Gemini retornou HTTP 404: modelo ou endpoint não encontrado. Consulte os modelos e teste novamente.',429:'Cota ou limite Gemini atingido. Confira o Google AI Studio.'}
    mensagem=erros.get(resp.status_code,'Gemini indisponível (HTTP '+str(resp.status_code)+').')
    if resp.status_code==404 and chave:
        mensagem='Gemini HTTP 404 — geração nativa v1beta; modelo: '+normalizar(modelo)+'.'
        try:
            detalhe=resp.json().get('error',{}).get('message','')
            if isinstance(detalhe,str) and detalhe:
                from urllib.parse import quote
                for segredo in (chave,quote(chave,safe="")):
                    detalhe=detalhe.replace(segredo,'[chave ocultada]')
                detalhe=re.sub(r'AIza[\w-]+','[chave ocultada]',detalhe)
                detalhe=re.sub(r'https?://\S+','[URL ocultada]',detalhe)
                detalhe=' '.join(detalhe.split())[:900]
                mensagem+=' Detalhe do serviço: '+detalhe
        except (ValueError,TypeError,AttributeError):
            pass
    raise RuntimeError(mensagem)

def listar(base):
    chave=ler_chave(base,'gemini');nomes=set();token=None;vistos=set()
    try:
        for _ in range(20):
            params={'pageSize':1000}
            if token:params['pageToken']=token
            r=requests.get('https://generativelanguage.googleapis.com/v1beta/models',
                headers={'x-goog-api-key':chave},params=params,timeout=(5,20),allow_redirects=False)
            verificar(r);dados=r.json()
            for m in dados.get('models',[]):
                nome=m.get('name','')
                if 'generateContent' in m.get('supportedGenerationMethods',[]) and nome.startswith('models/gemini-'):
                    nomes.add(normalizar(nome))
            token=dados.get('nextPageToken')
            if not token:return sorted(nomes)
            if not isinstance(token,str) or token in vistos:raise ValueError()
            vistos.add(token)
        raise RuntimeError('Catálogo Gemini extenso demais. Tente novamente.')
    except requests.RequestException:raise RuntimeError('Não consegui consultar modelos Gemini. Confira a internet.') from None
    except (ValueError,TypeError,AttributeError):raise RuntimeError('Catálogo Gemini inválido.') from None
