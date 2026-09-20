import sys
import types
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from texto_resposta import resposta_final,texto_para_fala,contexto_limpo
from audio_piper import reproduzir
import inteligencia

class TestFluidez(unittest.TestCase):
    def test_somente_resposta_final(self):
        self.assertEqual(resposta_final('<think>draft</think>A RAM é temporária.'),'A RAM é temporária.')
        self.assertEqual(resposta_final('<think>draft incompleto'),'')
        self.assertEqual(resposta_final('draft</think>Resposta.'),'Resposta.')

    def test_texto_falado_sem_formatacao(self):
        self.assertEqual(texto_para_fala('## Memória\n\n**RAM** é rápida.\n- Veja [SSD](https://example.com).'),'Memória RAM é rápida. Veja SSD.')
        self.assertNotIn('print',texto_para_fala('```python\nprint(1)\n```'))

    def test_contexto_antigo_sem_monologo(self):
        contexto=[{'role':'user','content':'Explique RAM.'},{'role':'assistant','content':'Okay, the user wants an explanation.'}]
        self.assertEqual(contexto_limpo(contexto),contexto[:1])

    def test_nemotron_sem_thinking(self):
        cfg={'provedor_ia':'nvidia','modelo_nvidia':'nvidia/nemotron-3-super-120b-a12b'}
        r=Mock(status_code=200);r.json.return_value={'choices':[{'message':{'content':'<think>draft</think>A RAM guarda dados temporários.','reasoning_content':'não mostrar'}}]}
        with patch('inteligencia.ler_chave',return_value='teste'),patch('inteligencia.requests.post',return_value=r) as post:
            self.assertEqual(inteligencia.responder_nvidia('.',cfg,[],'Explique RAM'),'A RAM guarda dados temporários.')
        corpo=post.call_args.kwargs['json']
        self.assertFalse(corpo['chat_template_kwargs']['enable_thinking'])
        self.assertIn('português do Brasil',corpo['messages'][0]['content'])

    def test_toca_antes_de_gerar_tudo(self):
        tocou=threading.Event();saida=Mock();saida.__enter__=Mock(return_value=saida);saida.__exit__=Mock(return_value=False)
        saida.write.side_effect=lambda _:tocou.set()
        def gerar(*a,**kw):
            yield types.SimpleNamespace(sample_rate=22050,sample_channels=1,sample_width=2,audio_int16_bytes=b'\x00\x00')
            if not tocou.wait(2):raise RuntimeError('Esperou todo áudio antes de tocar')
            yield types.SimpleNamespace(sample_rate=22050,sample_channels=1,sample_width=2,audio_int16_bytes=b'\x01\x00')
        voz=types.SimpleNamespace(synthesize=gerar)
        with patch.dict(sys.modules,{'sounddevice':types.SimpleNamespace(RawOutputStream=Mock(return_value=saida))}):reproduzir(voz,'Texto',None)
        self.assertEqual(saida.write.call_count,2)

    def test_erro_sintese_propaga(self):
        voz=Mock();voz.synthesize.side_effect=RuntimeError('falha')
        with patch.dict(sys.modules,{'sounddevice':Mock()}):
            with self.assertRaisesRegex(RuntimeError,'falha'):reproduzir(voz,'Texto',None)

    def test_parar_fala_interrompe_processo_e_limpa_fila(self):
        import queue
        from voz_mixin import VozMixin
        processo=Mock();processo.poll.return_value=None
        obj=types.SimpleNamespace(epoca_voz=0,parar_audio=threading.Event(),voz_fila=queue.Queue(),audio_lock=threading.Lock(),audio_processo=processo,voz_concluida=threading.Event(),ocupado=threading.Event(),falando=threading.Event())
        obj.voz_fila.put(('fala',0,0));obj.falando.set()
        VozMixin.parar_fala(obj)
        processo.terminate.assert_called_once()
        self.assertTrue(obj.voz_fila.empty());self.assertEqual(obj.epoca_voz,1)
        self.assertTrue(obj.parar_audio.is_set())
