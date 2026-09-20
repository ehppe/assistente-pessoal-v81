"""Reconhece pedidos de previsão do tempo em frases naturais e descobre para
QUAL DIA a pessoa está perguntando (hoje, amanhã, um dia da semana ou "dia
20"), já que o antigo detector só entendia um punhado de frases fixas e
sempre respondia como se fosse para agora."""
import re
from datetime import datetime

_GATILHO = re.compile(
    r'\b(?:qual\s+(?:e\s+)?(?:a\s+previsao|o\s+clima|o\s+tempo)|'
    r'previsao\s+(?:do|de|para)\s+tempo|previsao\s+para|'
    r'como\s+(?:esta|vai\s+estar)\s+o\s+tempo|vai\s+chover|esta\s+chovendo|'
    r'qual\s+(?:e\s+)?a\s+temperatura|'
    r'clima\s+(?:em|hoje|para|no|na|amanha)|'
    r'tempo\s+(?:em|hoje|para|no|na|amanha))\b')

_DIAS_SEMANA = {
    'segunda-feira': 0, 'segunda': 0, 'terca-feira': 1, 'terca': 1,
    'quarta-feira': 2, 'quarta': 2, 'quinta-feira': 3, 'quinta': 3,
    'sexta-feira': 4, 'sexta': 4, 'sabado': 5, 'domingo': 6,
}


def eh_pedido_clima(texto):
    return bool(_GATILHO.search(texto or ''))


def extrair_dia_climatico(texto, agora=None):
    """Devolve (dias_a_frente, trecho_reconhecido). dias_a_frente=0 é hoje.
    Quando nada específico é dito, devolve (0, '') — hoje, como antes."""
    agora = agora or datetime.now().astimezone()
    n = texto or ''
    m = re.search(r'\bdepois de amanha\b', n)
    if m:
        return 2, m.group(0)
    m = re.search(r'\bamanha\b', n)
    if m:
        return 1, m.group(0)
    m = re.search(r'\bhoje\b', n)
    if m:
        return 0, m.group(0)
    for nome, indice in _DIAS_SEMANA.items():
        m = re.search(r'\b' + nome + r'\b', n)
        if m:
            # O dia da semana mais próximo, podendo ser hoje mesmo — diferente
            # dos lembretes, aqui "domingo" dito num domingo é sobre hoje.
            delta = (indice - agora.weekday()) % 7
            return delta, m.group(0)
    m = re.search(r'\bdia\s+(\d{1,2})\b', n)
    if m:
        alvo = int(m.group(1))
        if 1 <= alvo <= 31:
            try:
                candidato = agora.replace(day=alvo, hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                candidato = None
            if candidato is not None and candidato.date() < agora.date():
                mes, ano = agora.month + 1, agora.year
                if mes > 12:
                    mes, ano = 1, ano + 1
                try:
                    candidato = candidato.replace(year=ano, month=mes)
                except ValueError:
                    candidato = None
            if candidato is not None:
                delta = (candidato.date() - agora.date()).days
                if 0 <= delta <= 15:
                    return delta, m.group(0)
    return 0, ''
