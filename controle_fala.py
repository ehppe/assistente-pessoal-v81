"""Comandos curtos durante a síntese. Nenhuma chamada remota."""
from calendario_local import norm
COMANDOS={
    'pode parar':'parar','pare de falar':'parar','neymar pare':'parar',
    'pode agendar':'confirmar','sim pode agendar':'confirmar','pode confirmar':'confirmar',
    'confirmar lembrete':'confirmar','nao precisa':'recusar','cancelar lembrete':'recusar',
}

def identificar(resultado):
    texto=norm(resultado.get('text','')).strip(' .!?,')
    acao=COMANDOS.get(texto)
    palavras=resultado.get('result') or []
    if not acao or not palavras:return None
    if any(not isinstance(p.get('conf'),(int,float)) or p['conf']<.8 for p in palavras):return None
    return acao
