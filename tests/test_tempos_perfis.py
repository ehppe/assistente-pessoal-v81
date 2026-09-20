import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desempenho import medir, resumo
from reconhecimento_whisper import Reconhecedor

class TestTempos(unittest.TestCase):
    def test_desligado_nao_grava(self):
        with tempfile.TemporaryDirectory() as d:
            with medir(d,'ia_total'):pass
            self.assertFalse((Path(d)/'dados').exists())

    def test_falha_preservada_sem_texto_sensivel(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'segredo'):
                with medir(d,'ia_total',True):raise RuntimeError('segredo')
            conteudo=(Path(d)/'dados/desempenho.jsonl').read_text()
            self.assertNotIn('segredo',conteudo)
            r=json.loads(conteudo);self.assertFalse(r['ok'])
            self.assertEqual(set(r),{'etapa','ms','ok'})

    def test_disco_bloqueado_nao_interrompe(self):
        with patch('desempenho.Path.mkdir',side_effect=PermissionError):
            with medir('.','ia_total',True):pass

    def test_rotacao_e_resumo_toleram_linha_incompleta(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'dados/desempenho.jsonl';p.parent.mkdir();p.write_text('x'*262145)
            with medir(d,'ia_total',True):pass
            self.assertTrue(p.with_suffix('.anterior.jsonl').exists())
            with p.open('a') as f:f.write('{')
            self.assertIn('1 concluídas',resumo(d))

class TestPerfis(unittest.TestCase):
    def preparar(self,d):
        p=Path(d)/'modelos/whisper-small';p.mkdir(parents=True);(p/'model.bin').touch()
        return Reconhecedor(d)

    def test_rapido_nao_enfraquece_chamada(self):
        with tempfile.TemporaryDirectory() as d:
            rec=self.preparar(d);rec.perfil='rapido'
            model=Mock();model.transcribe.return_value=([types.SimpleNamespace(text='Neymar',no_speech_prob=.1,avg_logprob=-.5)],None)
            np=types.SimpleNamespace(frombuffer=Mock(return_value=MagicMock()),float32='float32')
            with patch.dict(sys.modules,{'numpy':np,'faster_whisper':types.SimpleNamespace(WhisperModel=Mock(return_value=model))}):
                rec.transcrever(bytes(16000));normal=model.transcribe.call_args.kwargs
                rec.transcrever(bytes(16000),ativacao=True);nome=model.transcribe.call_args.kwargs
            self.assertEqual(normal['beam_size'],1);self.assertEqual(normal['temperature'],0)
            self.assertEqual(normal['vad_parameters']['speech_pad_ms'],300)
            self.assertEqual(nome['beam_size'],5);self.assertFalse(nome['vad_filter'])
            self.assertNotIn('vad_parameters',nome)

    def test_falha_no_gerador_e_medida(self):
        with tempfile.TemporaryDirectory() as d:
            rec=self.preparar(d);rec.diagnostico=True;rec.perfil='invalido'
            def segmentos():
                raise RuntimeError('inferência falhou')
                yield
            model=Mock();model.transcribe.return_value=(segmentos(),None)
            np=types.SimpleNamespace(frombuffer=Mock(return_value=MagicMock()),float32='float32')
            with patch.dict(sys.modules,{'numpy':np,'faster_whisper':types.SimpleNamespace(WhisperModel=Mock(return_value=model))}):
                with self.assertRaises(RuntimeError):rec.transcrever(bytes(16000))
            linhas=(Path(d)/'dados/desempenho.jsonl').read_text().splitlines()
            r=json.loads(linhas[-1]);self.assertEqual(r['etapa'],'whisper_precisao');self.assertFalse(r['ok'])
            self.assertEqual(model.transcribe.call_args.kwargs['beam_size'],5)

    def test_audio_invalido_rejeitado(self):
        with tempfile.TemporaryDirectory() as d:
            rec=self.preparar(d)
            for pcm in (bytes(6401),bytes(960002)):
                with self.assertRaisesRegex(RuntimeError,'Áudio inválido'):rec.transcrever(pcm)
