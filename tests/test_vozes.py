import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import voz_processo
from vozes import arquivos_voz, instalada
from config import carregar

class TestVozes(unittest.TestCase):
    def test_modelo_precisa_par_completo(self):
        with tempfile.TemporaryDirectory() as d:
            modelo,config=arquivos_voz(d,'pt_BR-cadu-medium')
            modelo.parent.mkdir(parents=True);modelo.write_bytes(b'modelo')
            self.assertFalse(instalada(d,'pt_BR-cadu-medium'))
            config.write_text('{}');self.assertTrue(instalada(d,'pt_BR-cadu-medium'))
            with self.assertRaises(ValueError):arquivos_voz(d,'../../arquivo')

    def test_piper_usa_modelo_escolhido(self):
        with tempfile.TemporaryDirectory() as d:
            modelo,config=arquivos_voz(d,'pt_BR-jeff-medium')
            modelo.parent.mkdir(parents=True);modelo.write_bytes(b'modelo');config.write_text('{}')
            voice=Mock();audio=Mock();loader=Mock();loader.get_data_path.return_value='C:/data'
            dados={'texto':'Olá','base':d,'piper':True,'voz_piper':'pt_BR-jeff-medium'}
            with patch.object(sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(json.dumps(dados).encode()))),patch.dict(sys.modules,{'piper':types.SimpleNamespace(PiperVoice=voice),'espeakng_loader':loader,'piper.config':types.SimpleNamespace(SynthesisConfig=Mock())}),patch('audio_piper.reproduzir',audio):
                voz_processo.main()
            voice.load.assert_called_once_with(str(modelo))
            audio.assert_called_once()

    def test_modelo_ausente_nao_troca_silenciosamente(self):
        with tempfile.TemporaryDirectory() as d:
            dados={'texto':'Olá','base':d,'piper':True,'voz_piper':'pt_BR-cadu-medium'}
            with patch.object(sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(json.dumps(dados).encode()))):
                with self.assertRaisesRegex(RuntimeError,'não instalada'):voz_processo.main()

    def test_windows_usa_id_escolhido(self):
        motor=Mock();motor.getProperty.return_value=[types.SimpleNamespace(id='feminina',name='Maria'),types.SimpleNamespace(id='masculina',name='João')]
        dados={'texto':'Olá','base':'.','piper':False,'voz_windows':'masculina'}
        with patch.object(sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(json.dumps(dados).encode()))),patch.dict(sys.modules,{'pyttsx3':types.SimpleNamespace(init=lambda:motor)}):voz_processo.main()
        motor.setProperty.assert_any_call('voice','masculina')

    def test_config_antiga_e_selecao_persistente(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);(base/'config.json').write_text('{"voz_piper":"pt_BR-cadu-medium","voz_windows":"voz-id"}')
            cfg=carregar(base)
            self.assertEqual(cfg['voz_piper'],'pt_BR-cadu-medium');self.assertEqual(cfg['voz_windows'],'voz-id')
