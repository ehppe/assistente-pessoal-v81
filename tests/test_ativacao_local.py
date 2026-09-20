import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import Mock
from array import array
from ativacao import verificar_nome_local

class TestAtivacaoLocal(unittest.TestCase):
    def setUp(self):
        self.pcm=array('h',[1000,-1000]*8000).tobytes()

    def test_nome_antes_de_liberar_escuta(self):
        for texto in ['Neymar.', 'Neymar, explique RAM']:
            rec=Mock();rec.transcrever.return_value=texto
            self.assertTrue(verificar_nome_local(rec,self.pcm))
            rec.transcrever.assert_called_once_with(self.pcm,ativacao=True)

    def test_audio_sem_chamada_nao_ativa(self):
        for texto in ['qual dia é hoje', 'java', 'japa', 'eu ouvi Neymar', 'neymarto', '']:
            rec=Mock();rec.transcrever.return_value=texto
            self.assertFalse(verificar_nome_local(rec,self.pcm))

    def test_silencio_e_limites_nao_transcrevem(self):
        rec=Mock()
        for pcm in [b'',bytes(16000),self.pcm[:100],self.pcm*20]:
            self.assertFalse(verificar_nome_local(rec,pcm))
        rec.transcrever.assert_not_called()


class TestRecorteChamada(unittest.TestCase):
    def test_nome_curto_entregue_apos_pausa_sem_vosk(self):
        from ativacao import TrechoChamada
        recorte=TrechoChamada();voz=array('h',[1000,-1000]*800).tobytes();silencio=bytes(3200)
        for _ in range(100):self.assertIsNone(recorte.alimentar(silencio))
        for _ in range(4):self.assertIsNone(recorte.alimentar(voz))
        for _ in range(6):self.assertIsNone(recorte.alimentar(silencio))
        trecho=recorte.alimentar(silencio)
        self.assertIsNotNone(trecho);self.assertIn(voz,trecho)
        self.assertIsNone(recorte.alimentar(silencio))

    def test_ruido_curto_e_gravacao_limitada(self):
        from ativacao import TrechoChamada
        recorte=TrechoChamada();voz=array('h',[1000,-1000]*800).tobytes()
        recorte.alimentar(voz)
        for _ in range(8):self.assertIsNone(recorte.alimentar(bytes(3200)))
        trechos=[recorte.alimentar(voz) for _ in range(60)]
        self.assertEqual(len([x for x in trechos if x]),1)
        self.assertLessEqual(len(next(x for x in trechos if x)),192000)

class TestDetectorContinuo(unittest.TestCase):
    def test_vosk_recebe_blocos_sem_reset_a_cada_bloco(self):
        import json
        from ativacao import DetectorChamada
        rec=Mock();rec.AcceptWaveform.side_effect=[False,False,True]
        rec.Result.return_value=json.dumps({'text':'neymar','result':[{'word':'neymar','conf':.97}]})
        detector=DetectorChamada(rec)
        self.assertFalse(detector.alimentar(bytes(3200))[0])
        self.assertFalse(detector.alimentar(bytes(3200))[0]);rec.Reset.assert_not_called()
        self.assertEqual(detector.alimentar(bytes(3200)),(True,None))
        self.assertEqual(rec.AcceptWaveform.call_count,3)

    def test_texto_generico_nao_ativa(self):
        import json
        from ativacao import DetectorChamada
        rec=Mock();rec.AcceptWaveform.return_value=True
        rec.Result.return_value=json.dumps({'text':'bom dia','result':[{'word':'bom','conf':1}]})
        self.assertFalse(DetectorChamada(rec).alimentar(bytes(3200))[0])
