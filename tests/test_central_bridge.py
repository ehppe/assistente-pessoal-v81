from unittest import TestCase
from unittest.mock import Mock
from types import SimpleNamespace
from central_bridge import CentralBridge

class Ponte(TestCase):
    def setUp(self):
        self.app=Mock()
        self.app.agenda.proposta.return_value={'token':'atual'}
        self.app.confirmacao.estado.return_value=('desligar',23)
        self.ponte=CentralBridge.__new__(CentralBridge);self.ponte.app=self.app

    def test_nao_confirma_oferta_antiga(self):
        self.ponte.executar({'acao':'confirmar','token':'antigo'})
        self.app.responder_oferta.assert_not_called()
        self.ponte.executar({'acao':'confirmar','token':'atual'})
        self.app.responder_oferta.assert_called_once_with(True,'atual')

    def test_energia_requer_token_atual(self):
        self.ponte.executar({'acao':'energia','token':22})
        self.app.resolver_confirmacao.assert_not_called()
        self.ponte.executar({'acao':'energia','token':23})
        self.app.resolver_confirmacao.assert_called_once_with(True,23)

    def test_texto_vai_para_motor_existente(self):
        self.ponte.executar({'acao':'enviar','texto':'abra a calculadora'})
        self.app.processar.assert_called_once_with('abra a calculadora')

    def test_acao_desconhecida_ignorada(self):
        self.ponte.executar({'acao':'executar_shell','texto':'comando'})
        self.assertEqual(self.app.mock_calls,[])

    def test_interrupcao_direta(self):
        self.ponte.executar({'acao':'parar'})
        self.app.parar_fala.assert_called_once()
