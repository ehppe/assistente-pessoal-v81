import sys,tempfile,json
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import inteligencia as ia
from config import carregar,salvar
from credenciais import caminho

class Gemini(TestCase):
    cfg={'provedor_ia':'gemini','modelo_gemini':'gemini-2.5-flash-lite','fallback_ollama':False}
    def test_request(self):
        r=Mock(status_code=200);r.json.return_value={'candidates':[{'content':{'parts':[{'text':'Olá.'}]}}]}
        with patch.object(ia,'ler_chave',return_value='teste') as chave,patch.object(ia.requests,'post',return_value=r) as post:
            self.assertEqual(ia.responder('.',self.cfg,[],'Oi'),'Olá.')
        chave.assert_called_once_with('.','gemini')
        self.assertTrue(post.call_args.args[0].startswith('https://generativelanguage.googleapis.com/'))
        k=post.call_args.kwargs
        self.assertFalse(k['allow_redirects']);self.assertEqual(k['json']['generationConfig']['thinkingConfig']['thinkingBudget'],0)
        self.assertEqual(k['json']['generationConfig']['maxOutputTokens'],650)
        self.assertNotIn('teste',json.dumps(k['json']))
    def test_http_errors_redacted(self):
        for code in (400,401,403,404,429,500):
            with self.subTest(code=code),patch.object(ia,'ler_chave',return_value='segredo'),patch.object(ia.requests,'post',return_value=Mock(status_code=code)):
                with self.assertRaises(RuntimeError) as cm:ia.responder('.',self.cfg,[],'Oi')
                self.assertNotIn('segredo',str(cm.exception))
    def test_bad_payloads(self):
        for data in ({}, {'choices':[]}, {'choices':[{'message':{'content':None}}]}):
            r=Mock(status_code=200);r.json.return_value=data
            with patch.object(ia,'ler_chave',return_value='teste'),patch.object(ia.requests,'post',return_value=r):
                with self.assertRaisesRegex(RuntimeError,'inválida'):ia.responder('.',self.cfg,[],'Oi')
    def test_fallback_only_local(self):
        with patch.object(ia,'responder_gemini',side_effect=RuntimeError('Cota')),patch.object(ia,'responder_local',return_value='local') as local,patch.object(ia,'responder_nvidia') as nvidia:
            self.assertIn('local',ia.responder('.',dict(self.cfg,fallback_ollama=True),[],'Oi'))
            local.assert_called_once();nvidia.assert_not_called()
    def test_connection_test_no_fallback(self):
        with patch.object(ia,'responder_gemini',side_effect=RuntimeError('Cota')),patch.object(ia,'responder_local') as local:
            with self.assertRaises(RuntimeError):ia.responder('.',dict(self.cfg,fallback_ollama=True),[],'Oi',permitir_fallback=False)
            local.assert_not_called()
    def test_config_and_secret(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);salvar(base,dict(self.cfg,chave_gemini='segredo'))
            self.assertEqual(carregar(base)['provedor_ia'],'gemini')
            self.assertNotIn('segredo',(base/'config.json').read_text())
            self.assertEqual(caminho(base,'gemini').name,'gemini-chave.dpapi')
    def test_timeout(self):
        with patch.object(ia,'ler_chave',return_value='teste'),patch.object(ia.requests,'post',side_effect=ia.requests.Timeout):
            with self.assertRaisesRegex(RuntimeError,'demorou'):ia.responder('.',self.cfg,[],'Oi')
