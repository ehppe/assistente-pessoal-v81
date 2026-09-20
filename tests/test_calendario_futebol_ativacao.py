import unittest
import tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch,Mock
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from calendario_local import responder_calendario
from ativacao import confirmada,palavra_inicial
from config import carregar,salvar
from futebol import interpretar,selecionar,escolher_time,consultar

class TestNovidades(unittest.TestCase):
    def test_datas_e_dia_da_semana(self):
        agora=datetime(2026,9,11,15,tzinfo=timezone(timedelta(hours=-3)))
        for pergunta in ['Que dia é hoje?','Consegue informar qual o dia da semana?','Qual a data de hoje?','Hoje é que dia?']:
            with self.subTest(pergunta=pergunta):self.assertIn('sexta-feira, 11 de setembro de 2026',responder_calendario(pergunta,agora))

    def test_virada_de_ano(self):
        self.assertIn('1 de janeiro de 2027',responder_calendario('Que dia será amanhã?',datetime(2026,12,31)))
        self.assertIn('31 de dezembro de 2025',responder_calendario('Que dia foi ontem?',datetime(2026,1,1)) or '')

    def test_data_nao_intercepta_evento(self):
        self.assertIsNone(responder_calendario('Que dia o Corinthians joga?'))
        self.assertIsNone(responder_calendario('Explique o que é um dia da semana'))

    def test_ativacao_confirmada(self):
        resultado={'text':'neymar explique ram','result':[{'word':'neymar','conf':.95}]}
        self.assertTrue(confirmada(resultado));self.assertFalse(confirmada(resultado,False))
        for palavra in ['java','japa','jaba','chava','javascript','neymarto']:
            self.assertFalse(confirmada({'text':palavra,'result':[{'word':palavra,'conf':1}]}))
        self.assertFalse(confirmada({'text':'neymar','result':[{'word':'neymar','conf':.4}]}))
        self.assertFalse(confirmada({'partial':'neymar'}))
        self.assertIsNone(palavra_inicial('eu estudo neymar'))

    def test_migracao_desativa_conversa_continua_uma_vez(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);salvar(p,{'segundos_conversa_continua':6,'palavras_ativacao':['japa']})
            cfg=carregar(p);self.assertEqual(cfg['segundos_conversa_continua'],0)
            cfg['segundos_conversa_continua']=3;salvar(p,cfg)
            self.assertEqual(carregar(p)['segundos_conversa_continua'],3)

    def test_consulta_futebol(self):
        self.assertEqual(interpretar('O Corinthians joga hoje?'),('hoje','corinthians'))
        self.assertEqual(interpretar('Qual é o próximo jogo do Corinthians?'),('proximo','corinthians'))
        self.assertIsNone(interpretar('Como jogar futebol?'))

    def test_futebol_data_local(self):
        agora=datetime(2026,9,11,20,tzinfo=timezone(timedelta(hours=-3)))
        jogo={'utcDate':'2026-09-12T01:00:00Z','homeTeam':{'id':1},'awayTeam':{'id':2},'status':'TIMED'}
        self.assertEqual(len(selecionar([jogo],1,'hoje',agora)),1)
        self.assertEqual(len(selecionar([jogo],1,'amanha',agora)),0)

    def test_time_ambiguo_nao_escolhe_primeiro(self):
        with self.assertRaises(RuntimeError):escolher_time([{'name':'Atlético Um'},{'name':'Atlético Dois'}],'Atlético')

    def test_sem_jogo_nao_afirma_ausencia_em_todas_competicoes(self):
        with patch('futebol.buscar',side_effect=[{'teams':[{'id':1,'name':'Corinthians'}]},{'matches':[]}]):
            texto=consultar('.','hoje','Corinthians')
        self.assertIn('não exclui jogos em outras competições',texto)
        self.assertIn('football-data.org',texto)
