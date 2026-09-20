from unittest import TestCase
from unittest.mock import Mock,patch
from types import SimpleNamespace
from pathlib import Path
import tempfile
import copy
from config import PADRAO
from preferencias_qt import validar,gravar_jogo,esquema

class Preferencias(TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=SimpleNamespace(base=Path(self.tmp.name),config=copy.deepcopy(PADRAO),
                                 modo_jogo=Mock(ativo=False),ocupado=Mock())
        self.app.ocupado.is_set.return_value=False
        self.app.config['reconhecimento']='vosk'

    def test_limites_de_voz(self):
        for k,v in [('ritmo_edge',80),('ritmo_piper',0),('velocidade_voz',900),('segundos_conversa_continua',90)]:
            with self.assertRaises(ValueError):validar(self.app,{k:v})

    def test_rejeita_campos_nao_permitidos(self):
        with self.assertRaises(ValueError):validar(self.app,{'comando_shell':'x'})

    def test_preserva_modelo_salvo(self):
        self.app.config['modelo_gemini']='gemini-3.5-flash-lite'
        self.assertEqual(validar(self.app,{'cidade_padrao':'Bauru'})['modelo_gemini'],'gemini-3.5-flash-lite')

    def test_segredo_nao_vai_para_config(self):
        self.assertNotIn('chave_gemini',validar(self.app,{'chave_gemini':'segredo'}))

    def test_jogo_nao_aceita_processo_protegido(self):
        with self.assertRaises(ValueError):gravar_jogo(self.app,{'programas':['steam.exe'],'alto':False})

    def test_salvar_jogo_nao_ativa(self):
        with patch('preferencias_qt.salvar') as salvar:
            gravar_jogo(self.app,{'programas':['chrome.exe'],'alto':False})
        salvar.assert_called_once()
        self.app.modo_jogo.ativar.assert_not_called()
        self.assertEqual(self.app.config['modo_jogo_fechar'],['chrome.exe'])
