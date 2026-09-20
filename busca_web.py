"""Pesquisa real na internet via Brave Search API.

Só é usada quando o usuário mesmo cola uma chave do Brave Search nas
Configurações — sem chave, o pedido de pesquisa continua abrindo o
navegador como antes, sem cobrar nada nem chamar nenhuma API. A Brave
Search API tem uma camada gratuita mensal; acima dela passa a cobrar, por
isso o Neymar nunca a chama sozinho: só quando a pessoa pede uma pesquisa
por voz ou texto, uma chamada por pedido."""
import re

import requests

from credenciais import ler_chave

_URL = 'https://api.search.brave.com/res/v1/web/search'


def pesquisar(base, termo, max_resultados=4):
    """Devolve uma lista de {'titulo','descricao','url'} com os resultados
    reais da busca, ou levanta RuntimeError com uma mensagem em português
    explicando o que deu errado (chave ausente/inválida, limite, rede)."""
    termo = (termo or '').strip()
    if not termo:
        raise RuntimeError('Diga o que você quer pesquisar.')
    chave = ler_chave(base, 'brave')
    try:
        r = requests.get(_URL,
            headers={'Accept': 'application/json', 'X-Subscription-Token': chave},
            params={'q': termo, 'count': max_resultados, 'country': 'BR', 'search_lang': 'pt'},
            timeout=(5, 15))
    except requests.Timeout:
        raise RuntimeError('A pesquisa na internet demorou demais.') from None
    except requests.RequestException:
        raise RuntimeError('Não consegui conectar à internet para pesquisar.') from None
    erros = {401: 'Chave do Brave Search inválida ou expirada.',
             403: 'Essa chave do Brave Search não tem permissão para pesquisar.',
             429: 'Limite mensal gratuito do Brave Search foi atingido.'}
    if r.status_code != 200:
        raise RuntimeError(erros.get(r.status_code, 'Brave Search indisponível (HTTP ' + str(r.status_code) + ').'))
    try:
        resultados = (r.json().get('web') or {}).get('results') or []
    except ValueError:
        raise RuntimeError('Brave Search retornou uma resposta inválida.') from None
    saida = []
    for item in resultados[:max_resultados]:
        titulo = (item.get('title') or '').strip()
        if not titulo:
            continue
        descricao = re.sub('<[^>]+>', '', item.get('description') or '').strip()
        saida.append({'titulo': titulo, 'descricao': descricao, 'url': item.get('url') or ''})
    return saida
