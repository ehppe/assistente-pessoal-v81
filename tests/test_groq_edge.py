import io
import wave
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock,patch,AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import reconhecimento_groq as groq
import credenciais
import voz_processo
import audio_edge
from config import carregar,salvar

class TestNovosServicos(unittest.TestCase):
    def test_groq_envia_wav_portugues_sem_chave_no_corpo(self):
        r=Mock(status_code=200);r.json.return_value={'text':'RAM e SSD','segments':[{'no_speech_prob':.1}]}
        with patch('reconhecimento_groq.ler_chave',return_value='segredo'),patch('reconhecimento_groq.requests.post',return_value=r) as post:
            self.assertEqual(groq.transcrever('.',bytes(10000)),'RAM e SSD')
        chamada=post.call_args
        self.assertEqual(chamada.args[0],groq.URL)
        self.assertEqual(chamada.kwargs['data']['language'],'pt')
        self.assertNotIn('segredo',str(chamada.kwargs['data']))
        self.assertFalse(chamada.kwargs['allow_redirects'])
        with wave.open(io.BytesIO(chamada.kwargs['files']['file'][1])) as wav:
            self.assertEqual(wav.getframerate(),16000);self.assertEqual(wav.getnchannels(),1);self.assertEqual(wav.readframes(5000),bytes(10000))

    def test_groq_limite_nao_repete_nem_vaza_erro(self):
        with patch('reconhecimento_groq.ler_chave',return_value='segredo'),patch('reconhecimento_groq.requests.post',return_value=Mock(status_code=429,text='segredo')) as post:
            with self.assertRaisesRegex(RuntimeError,'Limite Groq'):groq.transcrever('.',bytes(10000))
            post.assert_called_once()

    def test_audio_curto_nao_chama_rede(self):
        with patch('reconhecimento_groq.requests.post') as post:
            self.assertEqual(groq.transcrever('.',bytes(100)),'');post.assert_not_called()

    def test_chaves_independentes(self):
        crypt=types.SimpleNamespace(CryptProtectData=Mock(side_effect=[b'nvidia-cifrada',b'groq-cifrada']))
        with tempfile.TemporaryDirectory() as d,patch.dict(sys.modules,{'win32crypt':crypt}):
            credenciais.salvar_chave(d,'nvidia')
            credenciais.salvar_chave(d,'groq','groq')
            credenciais.apagar_chave(d,'groq')
            self.assertEqual(credenciais.caminho(d).read_bytes(),b'nvidia-cifrada')
            self.assertFalse(credenciais.caminho(d,'groq').exists())

    def test_config_preserva_novos_servicos(self):
        with tempfile.TemporaryDirectory() as d:
            b=Path(d);salvar(b,{'reconhecimento':'groq','provedor_voz':'edge','voz_edge':'Francisca — feminina (Brasil)'})
            cfg=carregar(b)
            self.assertEqual(cfg['reconhecimento'],'groq');self.assertEqual(cfg['provedor_voz'],'edge')

    def test_processo_usa_edge_escolhido(self):
        import json
        entrada={'texto':'**Olá**','base':'.','provedor':'edge','voz_edge':'Francisca — feminina (Brasil)','ritmo_edge':5}
        with patch.object(sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(json.dumps(entrada).encode()))),patch('audio_edge.reproduzir') as tocar:
            voz_processo.main()
            tocar.assert_called_once_with('Olá','pt-BR-FranciscaNeural',5)

    def test_edge_reune_apenas_audio(self):
        import asyncio
        async def stream():
            yield {'type':'audio','data':b'mp3'}
            yield {'type':'WordBoundary','text':'Olá'}
        comm=Mock(return_value=types.SimpleNamespace(stream=stream))
        with patch.dict(sys.modules,{'edge_tts':types.SimpleNamespace(Communicate=comm)}):
            self.assertEqual(asyncio.run(audio_edge.gerar('Olá','pt-BR-AntonioNeural',5)),b'mp3')
        comm.assert_called_once_with('Olá','pt-BR-AntonioNeural',rate='+5%')
