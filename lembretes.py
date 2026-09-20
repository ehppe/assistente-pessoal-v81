"""Agenda local persistente, com oferta expirada, confirmação e entrega única."""
import json,time,threading,uuid
from pathlib import Path
from datetime import datetime, timedelta

class Agenda:
    def __init__(self,base):
        self.caminho=Path(base)/'dados'/'lembretes.json'
        self.lock=threading.RLock();self.pendente=None;self.itens=[];self.erro=''
        if self.caminho.exists():
            try:
                self.itens=json.loads(self.caminho.read_text(encoding='utf-8'))
                if not isinstance(self.itens,list) or any(not isinstance(i,dict) or not all(k in i for k in ('id','titulo','inicio','aviso','estado')) or not isinstance(i['inicio'],(int,float)) or not isinstance(i['aviso'],(int,float)) for i in self.itens):raise ValueError()
            except (OSError,ValueError):self.erro='Não consegui ler dados/lembretes.json; restaure seu backup antes de agendar.';self.itens=[]

    def salvar(self):
        if self.erro:raise RuntimeError(self.erro)
        self.caminho.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.caminho.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.itens,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(self.caminho)

    def proposta(self,agora=None):
        with self.lock:
            if self.pendente and self.pendente['expira']<=(time.time() if agora is None else agora):self.pendente=None
            return dict(self.pendente) if self.pendente else None

    def oferecer(self,titulo,inicio,identificador,agora=None):
        agora=time.time() if agora is None else agora
        with self.lock:
            if self.erro:return None
            if inicio-1800<=agora:return None
            if any(i['id']==str(identificador) and i['inicio']==inicio and i['estado']=='agendado' for i in self.itens):return None
            self.pendente={'id':str(identificador),'titulo':titulo,'inicio':inicio,'aviso':inicio-1800,'token':uuid.uuid4().hex,'expira':agora+180}
            return dict(self.pendente)

    def oferecer_pessoal(self,titulo,quando,identificador,agora=None,recorrencia=None):
        """Lembrete pessoal ('me lembre amanhã ao meio-dia de X'): o aviso
        dispara NO horário pedido, não 30 minutos antes como nos jogos."""
        agora=time.time() if agora is None else agora
        with self.lock:
            if self.erro:return None
            if quando<=agora:return None
            self.pendente={'id':str(identificador),'titulo':titulo,'inicio':quando,'aviso':quando,'token':uuid.uuid4().hex,'expira':agora+180,'recorrencia':recorrencia,'tipo':'pessoal'}
            return dict(self.pendente)

    def resolver(self,token,aceitar,agora=None):
        agora=time.time() if agora is None else agora
        with self.lock:
            p=self.proposta(agora)
            if not p or p['token']!=token:raise RuntimeError('Não há oferta de lembrete válida para confirmar. Pergunte pelo próximo jogo novamente.')
            if not aceitar:self.pendente=None;return 'Não vou agendar esse lembrete.'
            if p['aviso']<=agora:self.pendente=None;raise RuntimeError('O horário do aviso já passou. Consulte o jogo novamente.')
            item={k:p[k] for k in ('id','titulo','inicio','aviso')};item['estado']='agendado'
            if p.get('recorrencia'):item['recorrencia']=p['recorrencia']
            if p.get('tipo'):item['tipo']=p['tipo']
            anterior=self.itens[:];self.itens=[i for i in self.itens if i['id']!=item['id']]+[item]
            try:self.salvar()
            except Exception:
                self.itens=anterior;raise RuntimeError('Não consegui salvar o lembrete. Ele não foi agendado.') from None
            self.pendente=None
            horario=datetime.fromtimestamp(p['aviso']).astimezone().strftime('%d/%m às %H:%M')
            if p['inicio']>p['aviso']:
                return 'Lembrete salvo para '+horario+', 30 minutos antes de '+p['titulo']+'. Deixe o computador ligado e o Neymar aberto.'
            return 'Lembrete salvo: '+p['titulo']+', para '+horario+'. Deixe o computador ligado e o Neymar aberto.'

    def devidos(self,agora=None):
        agora=time.time() if agora is None else agora
        with self.lock:
            if self.erro:return []
            antes=[dict(i) for i in self.itens];avisos=[];mudou=False
            for i in self.itens:
                if i['estado']=='agendado' and i['aviso']<=agora:
                    if i.get('tipo')=='pessoal' and agora-i['aviso']<=12*3600 or i.get('tipo')!='pessoal' and i['inicio']>agora:avisos.append(dict(i))
                    mudou=True
                    recorrencia=i.get('recorrencia')
                    if recorrencia in ('diaria','semanal'):
                        passo=86400 if recorrencia=='diaria' else 7*86400
                        while i['aviso']<=agora:i['aviso']+=passo;i['inicio']+=passo
                    else:i['estado']='avisado' if i.get('tipo')=='pessoal' or i['inicio']>agora else 'expirado'
            if mudou:
                try:self.salvar()
                except Exception:self.itens=antes;raise
            return avisos

    def listar(self):
        with self.lock:
            if self.erro:return self.erro
            linhas=[i['titulo']+' — '+datetime.fromtimestamp(i['aviso']).astimezone().strftime('%d/%m às %H:%M')+({'diaria':' (todo dia)','semanal':' (toda semana)'}.get(i.get('recorrencia'),'')) for i in self.itens if i['estado']=='agendado']
            return 'Lembretes agendados: '+('; '.join(linhas) if linhas else 'nenhum.')

    def cancelar_todos(self):
        with self.lock:
            antes=[dict(i) for i in self.itens]
            for i in self.itens:
                if i['estado']=='agendado':i['estado']='cancelado'
            try:self.salvar()
            except Exception:self.itens=antes;raise RuntimeError('Não consegui cancelar os lembretes.') from None
            self.pendente=None
            return 'Lembretes cancelados.'

    def cancelar(self,trecho):
        trecho=trecho.strip().lower()
        with self.lock:
            candidatos=[i for i in self.itens if i['estado']=='agendado' and trecho in i['titulo'].lower()]
            if not candidatos:return 'Não encontrei lembrete agendado com esse nome.'
            if len(candidatos)>1:return 'Encontrei mais de um lembrete. Diga uma parte mais específica do título.'
            candidatos[0]['estado']='cancelado';self.salvar()
            return 'Lembrete cancelado: '+candidatos[0]['titulo']+'.'

    def adiar(self,trecho,minutos=10):
        trecho=trecho.strip().lower()
        with self.lock:
            candidatos=[i for i in self.itens if i['estado']=='agendado' and trecho in i['titulo'].lower()]
            if len(candidatos)!=1:return 'Não encontrei um único lembrete com esse nome.'
            candidatos[0]['aviso']+=minutos*60;candidatos[0]['inicio']=max(candidatos[0]['inicio'],candidatos[0]['aviso']);self.salvar()
            return 'Lembrete adiado por '+str(minutos)+' minutos.'
