"""Consultas ao Brasileirão Série A via football-data.org; dados não são placar ao vivo."""
from datetime import datetime,timedelta
import re,time,hashlib
import requests
from calendario_local import norm
from credenciais import ler_chave
CACHE={}


def interpretar(pergunta,favorito='Corinthians'):
    n=norm(pergunta).strip(' ?!.')
    n=re.sub(r'^(?:voce pode |pode |consegue )?(?:me )?(?:dizer|informar) ','',n)
    m=re.fullmatch(r'(?:o )?(.+?) joga (hoje|amanha)',n)
    if m:return m[2],m[1]
    m=re.fullmatch(r'(?:quando|que dia|que horas|com quem) (?:o )?(.+?) joga(?: de novo)?',n)
    if m:return 'proximo',m[1]
    m=re.fullmatch(r'(?:qual (?:e|foi) )?(?:o )?(proximo|ultimo) jogo(?: (?:do|da|de) (.+))?',n)
    if m:return m[1],m[2] or favorito
    m=re.fullmatch(r'(?:qual (?:e|foi) )?(?:o )?resultado (?:do )?(?:ultimo )?jogo (?:do|da) (.+)',n)
    if m:return 'ultimo',m[1]
    return None


def buscar(base,rota,parametros=None,ttl=60):
    chave=ler_chave(base,'futebol')
    identificador=(hashlib.sha256(chave.encode()).hexdigest(),rota,tuple(sorted((parametros or {}).items())))
    cache=CACHE.get(identificador)
    if cache and time.monotonic()-cache[0]<ttl:return cache[1]
    try:
        r=requests.get('https://api.football-data.org/v4/'+rota,headers={'X-Auth-Token':chave},params=parametros,timeout=(5,20),allow_redirects=False)
        if r.status_code!=200:
            erros={401:'Chave de futebol inválida.',403:'Esta competição não está liberada na sua conta de futebol.',429:'Limite de consultas de futebol atingido. Aguarde um minuto.'}
            raise RuntimeError(erros.get(r.status_code,'Serviço de futebol indisponível (HTTP '+str(r.status_code)+').'))
        dados=r.json()
        if not isinstance(dados,dict):raise ValueError()
        if len(CACHE)>50:CACHE.clear()
        CACHE[identificador]=(time.monotonic(),dados)
        return dados
    except requests.RequestException:raise RuntimeError('Não consegui consultar futebol. Confira a internet e tente novamente.') from None
    except ValueError:raise RuntimeError('A API de futebol retornou dados inválidos.') from None


def escolher_time(times,nome):
    nome=norm(nome)
    exatos=[t for t in times if nome in {norm(t.get(k) or '') for k in ('name','shortName','tla')}]
    candidatos=exatos or [t for t in times if nome and re.search(r'\b'+re.escape(nome)+r'\b',norm(t.get('name','')))]
    if len(candidatos)!=1:raise RuntimeError('Não identifiquei um único time da Série A para "'+nome+'". Use o nome completo. Esta consulta cobre o Brasileirão Série A.')
    return candidatos[0]


def selecionar(jogos,time_id,modo,agora):
    encontrados=[]
    for jogo in jogos:
        if time_id not in (jogo.get('homeTeam',{}).get('id'),jogo.get('awayTeam',{}).get('id')):continue
        if not jogo.get('utcDate'):continue
        data=datetime.fromisoformat(jogo['utcDate'].replace('Z','+00:00')).astimezone(agora.tzinfo)
        status=jogo.get('status')
        if modo=='ultimo':aceita=status=='FINISHED' and data<=agora
        elif modo=='proximo':aceita=status in ('TIMED','SCHEDULED') and data>=agora
        else:aceita=data.date()==(agora+timedelta(days=1 if modo=='amanha' else 0)).date()
        if aceita:encontrados.append((data,jogo))
    return sorted(encontrados,key=lambda x:x[0],reverse=modo=='ultimo')


def consultar(base,modo,nome,agora=None,oferecer_lembrete=None):
    agora=agora or datetime.now().astimezone()
    # O elenco da Série A quase não muda de um dia para o outro; um cache mais
    # longo aqui evita gastar metade do limite de requisições do plano
    # gratuito (10/min) só para redescobrir o mesmo time de sempre.
    time_escolhido=escolher_time(buscar(base,'competitions/BSA/teams',ttl=6*3600).get('teams',[]),nome)
    inicio=agora-timedelta(days=90 if modo=='ultimo' else 1)
    fim=agora+timedelta(days=90 if modo=='proximo' else 3)
    dados=buscar(base,'competitions/BSA/matches',{'dateFrom':inicio.date().isoformat(),'dateTo':fim.date().isoformat()})
    jogos=selecionar(dados.get('matches',[]),time_escolhido['id'],modo,agora)
    fonte=' Fonte: football-data.org. Brasileirão Série A; horários e placares podem estar atrasados.'
    if not jogos:return 'Não encontrei partida correspondente de '+time_escolhido['name']+' na Série A no período consultado. Isso não exclui jogos em outras competições.'+fonte
    data,jogo=jogos[0]
    casa=jogo['homeTeam'].get('shortName') or jogo['homeTeam']['name']
    fora=jogo['awayTeam'].get('shortName') or jogo['awayTeam']['name']
    placar=jogo.get('score',{}).get('fullTime',{})
    detalhe=''
    if placar.get('home') is not None and placar.get('away') is not None:detalhe=f" Placar informado: {placar['home']} a {placar['away']}."
    estado={'FINISHED':'Encerrado','IN_PLAY':'Em andamento','PAUSED':'Intervalo','POSTPONED':'Adiado','CANCELLED':'Cancelado','SUSPENDED':'Suspenso','TIMED':'Agendado','SCHEDULED':'Horário a confirmar'}.get(jogo.get('status'),'Situação não informada')
    horario=data.strftime('%d/%m/%Y às %H:%M') if jogo.get('status')!='SCHEDULED' else data.strftime('%d/%m/%Y')+' (horário a confirmar)'
    oferta=''
    if oferecer_lembrete and jogo.get('status')=='TIMED' and data.timestamp()>agora.timestamp()+1800:
        oferta=oferecer_lembrete(f'{casa} x {fora}',data.timestamp(),str(jogo.get('id') or f'{casa}-{fora}-{data.isoformat()}'))
    return oferta+f'{casa} x {fora}, {horario}, no fuso do seu computador. {estado}.{detalhe}'+fonte
