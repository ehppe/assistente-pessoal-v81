import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock,MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reconhecimento_whisper import Reconhecedor
from conversa_mixin import ConversaMixin
import threading

class TestReconhecimento(unittest.TestCase):
    def test_modelo_ausente_nao_baixa_automaticamente(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'Instale'):Reconhecedor(d).transcrever(bytes(10000))

    def test_portugues_local_e_modelo_reutilizado(self):
        with tempfile.TemporaryDirectory() as d:
            pasta=Path(d)/'modelos'/'whisper-small';pasta.mkdir(parents=True);(pasta/'model.bin').write_bytes(b'modelo')
            modelo=Mock();modelo.transcribe.side_effect=[([types.SimpleNamespace(text=' RAM e SSD.',no_speech_prob=.1)],None),([types.SimpleNamespace(text='ruído',no_speech_prob=.9)],None)]
            classe=Mock(return_value=modelo)
            np=types.SimpleNamespace(frombuffer=Mock(return_value=MagicMock()),float32='float32')
            with patch.dict(sys.modules,{'faster_whisper':types.SimpleNamespace(WhisperModel=classe),'numpy':np}):
                rec=Reconhecedor(d)
                self.assertEqual(rec.transcrever(bytes(16000)),'RAM e SSD.')
                self.assertEqual(rec.transcrever(bytes(16000)),'')
            classe.assert_called_once()
            self.assertTrue(classe.call_args.kwargs['local_files_only'])
            for chamada in modelo.transcribe.call_args_list:
                self.assertEqual(chamada.kwargs['language'],'pt')
                self.assertFalse(chamada.kwargs['condition_on_previous_text'])
                self.assertTrue(chamada.kwargs['vad_filter'])

    def preparar(self,revisar=True):
        obj=types.SimpleNamespace(acao_pendente=None,encerrar=threading.Event(),pausado=threading.Event(),geracao=3,ativo_ate=1,config={'revisar_fala':revisar},abrir_conversa=Mock(),abrir_conversa_classica=Mock(),mostrar_pagina=Mock(),texto_pedido=Mock(),mostrar=Mock(),processar=Mock())
        obj.texto_pedido.get.return_value=''
        return obj

    def test_revisao_nao_executa_pedido(self):
        obj=self.preparar()
        ConversaMixin.receber_transcricao(obj,'Abra a calculadora',3)
        obj.processar.assert_not_called();obj.texto_pedido.insert.assert_called_once_with('1.0','Abra a calculadora')

    def test_cancelamento_descarta_transcricao(self):
        obj=self.preparar(False)
        ConversaMixin.receber_transcricao(obj,'Reinicie',2)
        obj.processar.assert_not_called()

    def test_texto_digitado_nao_e_sobrescrito(self):
        obj=self.preparar();obj.texto_pedido.get.return_value='rascunho'
        ConversaMixin.receber_transcricao(obj,'novo',3)
        obj.texto_pedido.insert.assert_not_called();obj.processar.assert_not_called()

    def test_modo_automatico_entrega_pedido(self):
        obj=self.preparar(False)
        ConversaMixin.receber_transcricao(obj,'Explique RAM',3)
        obj.processar.assert_called_once_with('Explique RAM')

    def test_confirmacao_por_voz_independe_da_revisao(self):
        obj=self.preparar(True);obj.acao_pendente='shutdown'
        ConversaMixin.receber_transcricao(obj,'cancelar',3)
        obj.processar.assert_called_once_with('cancelar')
        obj.texto_pedido.insert.assert_not_called()

    def test_migracao_envio_automatico_apenas_uma_vez(self):
        from config import carregar,salvar
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);salvar(base,{'revisar_fala':True,'palavras_ativacao':['javis']})
            cfg=carregar(base)
            self.assertFalse(cfg['revisar_fala']);self.assertEqual(cfg['palavras_ativacao'],['neymar'])
            cfg['revisar_fala']=True;salvar(base,cfg)
            self.assertTrue(carregar(base)['revisar_fala'])

    def test_nome_curto_sem_segundo_filtro_vad(self):
        with tempfile.TemporaryDirectory() as d:
            pasta=Path(d)/'modelos'/'whisper-small';pasta.mkdir(parents=True);(pasta/'model.bin').write_bytes(b'modelo')
            modelo=Mock();modelo.transcribe.return_value=([types.SimpleNamespace(text='Neymar',no_speech_prob=.3,avg_logprob=-.7)],None)
            np=types.SimpleNamespace(frombuffer=Mock(return_value=MagicMock()),float32='float32')
            with patch.dict(sys.modules,{'faster_whisper':types.SimpleNamespace(WhisperModel=Mock(return_value=modelo)),'numpy':np}):
                self.assertEqual(Reconhecedor(d).transcrever(bytes(16000),ativacao=True),'Neymar')
            self.assertFalse(modelo.transcribe.call_args.kwargs['vad_filter'])
            self.assertIsNone(modelo.transcribe.call_args.kwargs['initial_prompt'])
