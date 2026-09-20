"""Data e hora do computador, sem internet e sem dependência do idioma do Windows."""
from datetime import datetime,timedelta
import re
import unicodedata
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn').strip()
DIAS=('segunda-feira','terça-feira','quarta-feira','quinta-feira','sexta-feira','sábado','domingo')
MESES=('janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro')

def data_extenso(data):return f'{DIAS[data.weekday()]}, {data.day} de {MESES[data.month-1]} de {data.year}'

def contexto_relogio(agora=None):
    agora=agora or datetime.now().astimezone()
    return 'Data e hora do computador do usuário: '+data_extenso(agora)+agora.strftime(', %H:%M %z')+'. Use esta referência para hoje, ontem e amanhã. Isso não fornece notícias, jogos ou outros eventos atuais. '

def responder_calendario(pergunta,agora=None):
    n=norm(pergunta).strip(' ?!.;,')
    n=re.sub(r'^(?:neymar[, ]+)?(?:(?:voce )?(?:consegue|pode|poderia) (?:me )?(?:informar|dizer|falar)|me (?:diga|informe|fale))\s+','',n)
    n=re.sub(r'\s+por favor$','',n).strip(' ?!.;,')
    quando='amanha' if re.search(r'\bamanha\b',n) else 'ontem' if re.search(r'\bontem\b',n) else 'hoje'
    base=re.sub(r'\b(?:hoje|amanha|ontem)\b','',n)
    base=re.sub(r'\s+',' ',base).strip()
    base=re.sub(r'^(?:e|era|sera|foi)\s+','',base)
    base=re.sub(r' de$','',base)
    padroes=(r'(?:que|qual)(?: e| era| sera| foi)?(?: o| a)? (?:dia(?: da semana| do mes)?|data)(?: e| era| sera| foi)?',
             r'(?:dia da semana|data)(?: de)?',r'em que dia(?: da semana)? estamos',r'que dia do mes estamos')
    if any(re.fullmatch(p,base) for p in padroes):
        agora=agora or datetime.now().astimezone()
        data=agora+timedelta(days={'hoje':0,'amanha':1,'ontem':-1}[quando])
        inicio={'hoje':'Hoje é','amanha':'Amanhã será','ontem':'Ontem foi'}[quando]
        return inicio+' '+data_extenso(data)+'.'
    if re.fullmatch(r'(?:em )?que ano estamos|qual(?: e)? o ano(?: atual)?',n):
        return 'Estamos em '+str((agora or datetime.now().astimezone()).year)+'.'
    return None
