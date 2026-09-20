import sys,threading,tempfile,json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lembretes import Agenda
from controle_fala import identificar
from runtime_mixin import RuntimeMixin
with patch.dict(sys.modules,{'sounddevice':Mock(),'vosk':Mock(),'winsound':Mock()}):
    from voz_mixin import VozMixin
import queue

class TestAgenda(TestCase):
    def test_confirmacao_persiste_e_entrega_uma_vez(self):
        with tempfile.TemporaryDirectory() as d:
            agenda=Agenda(d);p=agenda.oferecer('Corinthians x Santos',10000,'42',agora=100)
            self.assertFalse(agenda.caminho.exists())
            agenda.resolver(p['token'],True,agora=110)
            nova=Agenda(d)
            self.assertEqual(nova.devidos(8200)[0]['titulo'],'Corinthians x Santos')
            self.assertEqual(Agenda(d).devidos(8300),[])

    def test_token_antigo_e_expiracao_nao_agendam(self):
        with tempfile.TemporaryDirectory() as d:
            a=Agenda(d);p=a.oferecer('Jogo A',10000,1,agora=100)
            novo=a.oferecer('Jogo B',11000,2,agora=120)
            with self.assertRaises(RuntimeError):a.resolver(p['token'],True,agora=130)
            with self.assertRaises(RuntimeError):a.resolver(novo['token'],True,agora=301)
            self.assertEqual(a.itens,[])

    def test_recusa_e_jogo_sem_antecedencia(self):
        with tempfile.TemporaryDirectory() as d:
            a=Agenda(d);self.assertIsNone(a.oferecer('Jogo',1500,1,agora=100))
            p=a.oferecer('Jogo',10000,1,agora=100);a.resolver(p['token'],False,agora=101)
            self.assertEqual(a.itens,[])

    def test_atraso_antes_do_jogo_avisa_depois_do_jogo_expira(self):
        with tempfile.TemporaryDirectory() as d:
            a=Agenda(d);p=a.oferecer('Jogo',10000,1,agora=100);a.resolver(p['token'],True,agora=101)
            self.assertEqual(len(a.devidos(9000)),1)
        with tempfile.TemporaryDirectory() as d:
            a=Agenda(d);p=a.oferecer('Jogo',10000,1,agora=100);a.resolver(p['token'],True,agora=101)
            self.assertEqual(a.devidos(10001),[]);self.assertEqual(a.itens[0]['estado'],'expirado')

    def test_erro_de_gravacao_nao_confirma(self):
        with tempfile.TemporaryDirectory() as d:
            a=Agenda(d);p=a.oferecer('Jogo',10000,1,agora=100)
            with patch.object(a,'salvar',side_effect=OSError()):
                with self.assertRaisesRegex(RuntimeError,'não foi agendado'):a.resolver(p['token'],True,agora=101)
            self.assertEqual(a.itens,[])

    def test_arquivo_invalido_preservado(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'dados'/'lembretes.json';p.parent.mkdir();p.write_text('invalido')
            a=Agenda(d);self.assertTrue(a.erro);self.assertIsNone(a.oferecer('Jogo',10000,1,agora=100))
            self.assertEqual(p.read_text(),'invalido')

    def test_cancelamento_persistido(self):
        with tempfile.TemporaryDirectory() as d:
            a=Agenda(d);p=a.oferecer('Jogo',10000,1,agora=100);a.resolver(p['token'],True,agora=101)
            self.assertIsNone(a.oferecer('Jogo',10000,1,agora=105))
            a.cancelar_todos();self.assertEqual(Agenda(d).devidos(8200),[])

class TestControle(TestCase):
    def resultado(self,texto,conf=.95):return {'text':texto,'result':[{'word':p,'conf':conf} for p in texto.split()]}

    def test_comandos_curtos_confirmados(self):
        self.assertEqual(identificar(self.resultado('pode parar')),'parar')
        self.assertEqual(identificar(self.resultado('sim pode agendar')),'confirmar')
        self.assertEqual(identificar(self.resultado('não precisa')),'recusar')

    def test_fala_comum_parcial_e_baixa_confianca_nao_acionam(self):
        for texto in ('sim','confirmar','posso avisar você','você pode parar aqui','abra chrome'):
            self.assertIsNone(identificar(self.resultado(texto)))
        self.assertIsNone(identificar({'partial':'pode parar'}))
        self.assertIsNone(identificar(self.resultado('pode agendar',.2)))

    def objeto(self):
        return SimpleNamespace(pausado=threading.Event(),config={'interromper_por_voz':True},epoca_voz=3,
            parar_fala=Mock(),mostrar=Mock(),agenda=Mock(),responder_oferta=Mock(),acao_pendente=None)

    def test_interrupcao_nao_precisa_de_oferta(self):
        o=self.objeto();RuntimeMixin.controle_durante_fala(o,'parar',3,None)
        o.parar_fala.assert_called_once();o.responder_oferta.assert_not_called()

    def test_confirmar_so_oferta_atual_e_nao_energia(self):
        o=self.objeto();o.agenda.proposta.return_value={'token':'atual'}
        RuntimeMixin.controle_durante_fala(o,'confirmar',3,'antigo');o.responder_oferta.assert_not_called()
        RuntimeMixin.controle_durante_fala(o,'confirmar',3,'atual');o.responder_oferta.assert_called_once_with(True,'atual')
        o.responder_oferta.reset_mock();o.acao_pendente='shutdown'
        RuntimeMixin.controle_durante_fala(o,'confirmar',3,'atual');o.responder_oferta.assert_not_called()

    def test_evento_obsoleto_e_pausa(self):
        o=self.objeto();RuntimeMixin.controle_durante_fala(o,'parar',2,None)
        o.pausado.set();RuntimeMixin.controle_durante_fala(o,'parar',3,None)
        o.parar_fala.assert_not_called()

    def test_callback_permite_audio_durante_fala_so_quando_habilitado(self):
        o=SimpleNamespace(pausado=threading.Event(),transcrevendo=threading.Event(),falando=threading.Event(),config={'interromper_por_voz':True},audio=queue.Queue())
        o.falando.set();VozMixin.callback(o,bytes(3200),None,None,None);self.assertEqual(o.audio.qsize(),1)
        o.config['interromper_por_voz']=False;VozMixin.callback(o,bytes(3200),None,None,None);self.assertEqual(o.audio.qsize(),1)

class TestOfertaFutebol(TestCase):
    def test_oferta_so_com_data_confirmada(self):
        from futebol import consultar
        from datetime import datetime,timezone
        agora=datetime(2026,9,12,12,tzinfo=timezone.utc)
        time={'id':1,'name':'Corinthians','shortName':'Corinthians'}
        jogo={'id':10,'utcDate':'2026-09-13T21:30:00Z','status':'TIMED','homeTeam':time,'awayTeam':{'id':2,'name':'Santos'},'score':{}}
        callback=Mock(return_value='OFERTA ')
        with patch('futebol.buscar',side_effect=[{'teams':[time]},{'matches':[jogo]}]):
            resposta=consultar('.', 'proximo','Corinthians',agora,callback)
        self.assertTrue(resposta.startswith('OFERTA '))
        self.assertEqual(callback.call_args.args[1],datetime(2026,9,13,21,30,tzinfo=timezone.utc).timestamp())
        callback.reset_mock();jogo['status']='SCHEDULED'
        with patch('futebol.buscar',side_effect=[{'teams':[time]},{'matches':[jogo]}]):
            consultar('.', 'proximo','Corinthians',agora,callback)
        callback.assert_not_called()

    def test_confirmar_durante_fala_interrompe_e_salva(self):
        with tempfile.TemporaryDirectory() as d:
            a=Agenda(d)
            import time
            p=a.oferecer('Corinthians x Santos',time.time()+7200,10)
            o=SimpleNamespace(agenda=a,parar_fala=Mock(),falar=Mock())
            RuntimeMixin.responder_oferta(o,True,p['token'])
            o.parar_fala.assert_called_once()
            self.assertIn('Lembrete salvo',o.falar.call_args.args[0])
            self.assertEqual(Agenda(d).itens[0]['estado'],'agendado')
