"""Detecta e interpreta pedidos de lembrete pessoal em português falado.

`pedido_de_agendamento` só diz se o texto TEM CARA de pedido de lembrete
(usado pra não jogar isso pro modelo conversacional, que inventaria uma
resposta). `interpretar` tenta entender de verdade o dia, o horário e o
título — só devolve algo quando tem certeza do dia E do horário; se faltar
qualquer um dos dois, devolve None, e quem chamou deve pedir pra pessoa
repetir de um jeito mais claro, em vez de arriscar marcar na hora errada.
Nada aqui salva sozinho: o Neymar sempre confirma o horário em voz alta
antes de gravar (fluxo de oferta/confirmação já usado para os jogos)."""
import re
from datetime import datetime, timedelta

GATILHO = re.compile(
    r'\b(?:me (?:lembre|lembra|avise|avisa)|lembre[ -]me|'
    r'(?:crie|criar|cria|adicione|adicionar|adiciona|registre|registrar|registra|'
    r'coloque|colocar|coloca|salve|salvar|salva) (?:um |o |esse |este )?lembrete|'
    r'agende|agendar|agenda (?:um|uma|para|pra)|'
    r'lembrete (?:para|pra|amanha|hoje)|'
    r'(?:marque|marcar) (?:um |uma )?(?:alarme|lembrete|compromisso))\b', re.IGNORECASE)


def pedido_de_agendamento(texto):
    return bool(GATILHO.search(texto or ''))


DIAS_SEMANA = {
    'segunda-feira': 0, 'segunda': 0, 'terça-feira': 1, 'terca-feira': 1, 'terça': 1, 'terca': 1,
    'quarta-feira': 2, 'quarta': 2, 'quinta-feira': 3, 'quinta': 3,
    'sexta-feira': 4, 'sexta': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6,
}
PERIODOS = {
    'de manhã': (9, 0), 'de manha': (9, 0), 'pela manhã': (9, 0), 'pela manha': (9, 0),
    'de tarde': (15, 0), 'à tarde': (15, 0), 'a tarde': (15, 0),
    'de noite': (20, 0), 'à noite': (20, 0), 'a noite': (20, 0), 'à noitinha': (19, 0), 'a noitinha': (19, 0),
}


def _extrair_hora(texto):
    """Devolve (hora, minuto, trecho_para_remover_do_titulo) ou None."""
    m = re.search(r'meio[ -]?dia(?:\s+e\s+meia)?', texto)
    if m:
        return 12, (30 if 'meia' in m.group(0) else 0), m.group(0)
    m = re.search(r'meia[ -]?noite', texto)
    if m:
        return 0, 0, m.group(0)
    m = re.search(r'\b(?:as|às)\s+(\d{1,2})\s*(?:h|hs|horas?)?(?:\s*(?:e\s+)?(\d{1,2})\s*(?:min(?:utos)?)?)?\b', texto)
    if m:
        hora = int(m.group(1))
        minuto = int(m.group(2)) if m.group(2) else 0
        if 0 <= hora <= 23 and 0 <= minuto <= 59:
            return hora, minuto, m.group(0)
    for frase, (h, mi) in PERIODOS.items():
        if frase in texto:
            return h, mi, frase
    return None


def _extrair_relativo(texto, agora):
    """'daqui a 30 minutos' / 'em 2 horas' — devolve (datetime, trecho) ou None."""
    m = re.search(r'\b(?:daqui\s+a|em)\s+(\d{1,3})\s*(minutos?|min\b|horas?|h\b)', texto)
    if not m:
        return None
    quantidade = int(m.group(1))
    unidade = m.group(2)
    delta = timedelta(minutes=quantidade) if unidade.startswith('m') else timedelta(hours=quantidade)
    return agora + delta, m.group(0)


def interpretar(texto, agora=None):
    """Tenta entender um pedido de lembrete pessoal. Devolve (titulo, epoch)
    quando consegue, ou None quando não tem certeza do dia/horário."""
    if not texto or not texto.strip():
        return None
    agora = agora or datetime.now().astimezone()
    n = ' ' + re.sub(r'\s+', ' ', texto.strip().lower()) + ' '

    relativo = _extrair_relativo(n, agora)
    if relativo:
        candidato, trecho = relativo
        titulo = _titulo_sem(texto, [trecho])
        return titulo, candidato.timestamp(), _recorrencia(n)

    dia_base = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    dia_encontrado = None
    trecho_dia = ''
    if re.search(r'\bdepois de amanh[ãa]\b', n):
        dia_encontrado = dia_base + timedelta(days=2)
        trecho_dia = 'depois de amanhã'
    elif re.search(r'\bamanh[ãa]\b', n):
        dia_encontrado = dia_base + timedelta(days=1)
        trecho_dia = 'amanhã'
    elif re.search(r'\bhoje\b', n):
        dia_encontrado = dia_base
        trecho_dia = 'hoje'
    else:
        for nome, indice in DIAS_SEMANA.items():
            if re.search(r'\b' + nome + r'\b', n):
                delta = (indice - agora.weekday()) % 7
                # Dito no próprio dia da semana, entende como "essa semana que vem"
                # (evita marcar sem querer daqui a poucos minutos).
                dia_encontrado = dia_base + timedelta(days=delta or 7)
                trecho_dia = nome
                break

    hora_info = _extrair_hora(n)
    if hora_info is None:
        return None
    hora, minuto, trecho_hora = hora_info

    sem_dia_explicito = dia_encontrado is None
    if sem_dia_explicito:
        dia_encontrado = dia_base
    candidato = dia_encontrado.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if sem_dia_explicito and candidato <= agora:
        candidato += timedelta(days=1)

    titulo = _titulo_sem(texto, [trecho_dia, trecho_hora])
    return titulo, candidato.timestamp(), _recorrencia(n)

def _recorrencia(texto):
    if re.search(r'\b(?:todo dia|todos os dias|diariamente)\b',texto):return 'diaria'
    if re.search(r'\b(?:toda semana|semanalmente|toda segunda|toda terça|toda terca|toda quarta|toda quinta|toda sexta|todo sábado|todo sabado|todo domingo)\b',texto):return 'semanal'
    return None


def _titulo_sem(texto_original, trechos):
    """Tira o gatilho e os trechos de dia/horário do texto, sobrando o
    assunto do lembrete ('ligar pro dentista', por exemplo)."""
    titulo = GATILHO.sub('', texto_original, count=1)
    titulo = re.sub(r'\b(?:todo dia|todos os dias|diariamente|toda semana|semanalmente|toda segunda(?:-feira)?|toda terça(?:-feira)?|toda terca(?:-feira)?|toda quarta(?:-feira)?|toda quinta(?:-feira)?|toda sexta(?:-feira)?|todo sábado|todo sabado|todo domingo)\b','',titulo,flags=re.IGNORECASE)
    for trecho in trechos:
        if trecho:
            titulo = re.sub(re.escape(trecho), '', titulo, flags=re.IGNORECASE)
    titulo = re.sub(r'\s+', ' ', titulo).strip(' ,.;:!?')
    titulo = re.sub(r'^(?:de|para|pra|que|e)\s+', '', titulo, flags=re.IGNORECASE).strip()
    titulo = re.sub(r'\s+(?:de|para|pra)$', '', titulo, flags=re.IGNORECASE).strip()
    return titulo or 'lembrete'
