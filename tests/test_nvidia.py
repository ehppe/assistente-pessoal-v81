import sys
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import inteligencia
import credenciais
from config import carregar, salvar

class TestNvidia(unittest.TestCase):
    def setUp(self):
        self.cfg={'provedor_ia':'nvidia','modelo_nvidia':'meta/llama-3.3-70b-instruct','fallback_ollama':True}

    def test_requisicao_autenticada_e_contexto(self):
        r=Mock(status_code=200);r.json.return_value={'choices':[{'message':{'content':'Resposta NVIDIA'}}]}
        with patch('inteligencia.ler_chave',return_value='segredo-teste'),patch('inteligencia.requests.post',return_value=r) as post:
            self.assertEqual(inteligencia.responder('.',self.cfg,[{'role':'user','content':'antes'}],'agora'),'Resposta NVIDIA')
        args=post.call_args
        self.assertEqual(args.args[0],'https://integrate.api.nvidia.com/v1/chat/completions')
        self.assertEqual(args.kwargs['headers']['Authorization'],'Bearer segredo-teste')
        self.assertEqual(len(args.kwargs['json']['messages']),3)
        self.assertFalse(args.kwargs['allow_redirects'])
        self.assertNotIn('segredo-teste',json.dumps(args.kwargs['json']))

    def test_erro_usa_local_com_aviso_sem_vazar_corpo(self):
        r=Mock(status_code=401);r.text='segredo-teste'
        with patch('inteligencia.ler_chave',return_value='segredo-teste'),patch('inteligencia.requests.post',return_value=r),patch('inteligencia.responder_local',return_value='Olá'):
            texto=inteligencia.responder('.',self.cfg,[],'Oi')
        self.assertIn('Chave NVIDIA inválida',texto);self.assertIn('Ollama local',texto);self.assertNotIn('segredo-teste',texto)

    def test_teste_de_conexao_nao_mascara_erro(self):
        with patch('inteligencia.responder_nvidia',side_effect=RuntimeError('Limite')),patch('inteligencia.responder_local') as local:
            with self.assertRaisesRegex(RuntimeError,'Limite'):inteligencia.responder('.',self.cfg,[],'Oi',permitir_fallback=False)
            local.assert_not_called()

    def test_ollama_nao_le_chave_nem_chama_nvidia(self):
        with patch('inteligencia.responder_nvidia') as nuvem,patch('inteligencia.responder_local',return_value='local'):
            self.assertEqual(inteligencia.responder('.',{'provedor_ia':'ollama'},[],'Oi'),'local')
            nuvem.assert_not_called()

    def test_limite_timeout_e_resposta_vazia(self):
        with patch('inteligencia.ler_chave',return_value='teste'):
            for status in (402,403,404,429,500):
                with self.subTest(status=status),patch('inteligencia.requests.post',return_value=Mock(status_code=status)):
                    with self.assertRaises(RuntimeError):inteligencia.responder_nvidia('.',self.cfg,[],'Oi')
            with patch('inteligencia.requests.post',side_effect=inteligencia.requests.Timeout):
                with self.assertRaisesRegex(RuntimeError,'demorou'):inteligencia.responder_nvidia('.',self.cfg,[],'Oi')
            r=Mock(status_code=200);r.json.return_value={'choices':[]}
            with patch('inteligencia.requests.post',return_value=r):
                with self.assertRaisesRegex(RuntimeError,'inválida'):inteligencia.responder_nvidia('.',self.cfg,[],'Oi')

    def test_config_preserva_nvidia(self):
        with tempfile.TemporaryDirectory() as d:
            b=Path(d);salvar(b,self.cfg);self.assertEqual(carregar(b)['provedor_ia'],'nvidia')

    def test_chave_protegida_e_remocao(self):
        crypt=types.SimpleNamespace(CryptProtectData=Mock(return_value=b'cifrado'),CryptUnprotectData=Mock(return_value=('Neymar',b'chave-teste')))
        with tempfile.TemporaryDirectory() as d,patch.dict(sys.modules,{'win32crypt':crypt}):
            credenciais.salvar_chave(d,'chave-teste')
            self.assertEqual(credenciais.caminho(d).read_bytes(),b'cifrado')
            self.assertEqual(credenciais.ler_chave(d),'chave-teste')
            credenciais.apagar_chave(d)
            with self.assertRaisesRegex(RuntimeError,'Adicione'):credenciais.ler_chave(d)
