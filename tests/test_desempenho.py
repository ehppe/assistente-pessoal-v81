"""Cobre as mudanças de fluidez: processo de voz persistente (modelo/engine
reaproveitados entre falas) e os caches de geocodificação e de elenco da
Série A que evitam chamadas de rede repetidas."""
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import voz_processo
import futebol
if sys.platform!='win32':sys.modules.setdefault('winsound',types.ModuleType('winsound'))
import acoes_mixin
from acoes_mixin import AcoesMixin
from texto_resposta import texto_para_fala
from vozes import arquivos_voz


class TestVozPersistente(unittest.TestCase):
    def tearDown(self):
        voz_processo._VOZES_PIPER.clear()
        voz_processo._ENGINE_WINDOWS = None
        voz_processo._ESPEAK_PRONTO = False

    def test_persistente_responde_uma_linha_por_pedido(self):
        motor = Mock();motor.getProperty.return_value = []
        entrada = io.BytesIO(
            json.dumps({'texto': 'Olá', 'base': '.', 'piper': False}).encode() + b'\n' +
            json.dumps({'texto': 'Tudo bem?', 'base': '.', 'piper': False}).encode() + b'\n'
        )
        saida = io.BytesIO()
        with patch.object(sys, 'stdin', types.SimpleNamespace(buffer=entrada)), \
             patch.object(sys, 'stdout', types.SimpleNamespace(buffer=saida)), \
             patch.dict(sys.modules, {'pyttsx3': types.SimpleNamespace(init=lambda: motor)}):
            voz_processo.main_persistente()
        linhas = [json.loads(l) for l in saida.getvalue().splitlines() if l]
        self.assertEqual(linhas, [{'ok': True}, {'ok': True}])
        self.assertEqual(motor.say.call_count, 2)

    def test_engine_windows_reaproveitada_entre_falas(self):
        criados = []
        def _init():
            m = Mock();m.getProperty.return_value = [];criados.append(m);return m
        with patch.dict(sys.modules, {'pyttsx3': types.SimpleNamespace(init=_init)}):
            voz_processo.sintetizar({'texto': 'Um', 'base': '.', 'piper': False})
            voz_processo.sintetizar({'texto': 'Dois', 'base': '.', 'piper': False})
        # Uma única chamada a pyttsx3.init() prova que a segunda fala reaproveitou
        # o motor já carregado, em vez de recriar do zero.
        self.assertEqual(len(criados), 1)
        self.assertEqual(criados[0].say.call_count, 2)

    def test_piper_carregado_uma_vez_para_duas_falas(self):
        voz_processo._ESPEAK_PRONTO = True  # evita depender do espeakng_loader real
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            modelo, config = arquivos_voz(base, 'pt_BR-cadu-medium')
            modelo.parent.mkdir(parents=True);modelo.write_bytes(b'modelo');config.write_text('{}')
            voice = Mock()
            with patch.dict(sys.modules, {'piper': types.SimpleNamespace(PiperVoice=voice), 'piper.config': types.SimpleNamespace(SynthesisConfig=Mock())}), \
                 patch('audio_piper.reproduzir'):
                voz_processo.sintetizar({'texto': 'Um', 'base': str(base), 'piper': True, 'voz_piper': 'pt_BR-cadu-medium'})
                voz_processo.sintetizar({'texto': 'Dois', 'base': str(base), 'piper': True, 'voz_piper': 'pt_BR-cadu-medium'})
        voice.load.assert_called_once_with(str(modelo))

    def test_erro_em_uma_fala_nao_interrompe_as_seguintes(self):
        motor = Mock();motor.getProperty.return_value = []
        entrada = io.BytesIO(
            json.dumps({'texto': 'Fala', 'base': '.', 'piper': True, 'voz_piper': 'pt_BR-cadu-medium'}).encode() + b'\n' +
            json.dumps({'texto': 'Outra', 'base': '.', 'piper': False}).encode() + b'\n'
        )
        saida = io.BytesIO()
        with patch.object(sys, 'stdin', types.SimpleNamespace(buffer=entrada)), \
             patch.object(sys, 'stdout', types.SimpleNamespace(buffer=saida)), \
             patch.dict(sys.modules, {'pyttsx3': types.SimpleNamespace(init=lambda: motor)}):
            voz_processo.main_persistente()
        linhas = [json.loads(l) for l in saida.getvalue().splitlines() if l]
        self.assertFalse(linhas[0]['ok']);self.assertIn('não instalada', linhas[0]['erro'])
        self.assertTrue(linhas[1]['ok'])

    def test_main_de_compatibilidade_continua_um_pedido_por_chamada(self):
        # Contrato usado pelos testes mais antigos (test_vozes.py, test_groq_edge.py):
        # lê um único JSON do começo ao fim de stdin, sem protocolo de linhas.
        motor = Mock();motor.getProperty.return_value = []
        dados = {'texto': 'Olá', 'base': '.', 'piper': False}
        with patch.object(sys, 'stdin', types.SimpleNamespace(buffer=io.BytesIO(json.dumps(dados).encode()))), \
             patch.dict(sys.modules, {'pyttsx3': types.SimpleNamespace(init=lambda: motor)}):
            voz_processo.main()
        motor.say.assert_called_once()


class TestCacheDeRede(unittest.TestCase):
    def setUp(self):
        futebol.CACHE.clear()
        acoes_mixin._CACHE_GEOCODIFICACAO.clear()

    def test_elenco_da_serie_a_fica_em_cache_por_horas(self):
        with patch('futebol.ler_chave', return_value='chave'), patch('futebol.requests.get') as get:
            get.return_value = Mock(status_code=200, json=Mock(return_value={'teams': []}))
            futebol.buscar('.', 'competitions/BSA/teams', ttl=6 * 3600)
            futebol.buscar('.', 'competitions/BSA/teams', ttl=6 * 3600)
        get.assert_called_once()

    def test_partidas_continuam_com_cache_curto(self):
        with patch('futebol.ler_chave', return_value='chave'), patch('futebol.requests.get') as get:
            get.return_value = Mock(status_code=200, json=Mock(return_value={'matches': []}))
            futebol.buscar('.', 'competitions/BSA/matches', {'dateFrom': '2026-01-01'})
            futebol.buscar('.', 'competitions/BSA/matches', {'dateFrom': '2026-01-01'})
        # Mesma chamada duas vezes ainda cai no cache de 60s padrão (comportamento já existente).
        get.assert_called_once()

    def test_geocodificacao_da_mesma_cidade_nao_repete_a_chamada(self):
        obj = types.SimpleNamespace(registrar=lambda *a, **k: None)
        with patch('acoes_mixin.requests.get') as get:
            get.return_value = Mock(json=Mock(return_value={'results': [{'latitude': 1, 'longitude': 2, 'name': 'Paranapanema'}]}))
            primeiro = AcoesMixin.geocodificar_cidade(obj, 'Paranapanema')
            segundo = AcoesMixin.geocodificar_cidade(obj, 'paranapanema')  # mesma cidade, caixa diferente
        get.assert_called_once()
        self.assertEqual(primeiro, segundo)

    def test_cidade_nao_encontrada_nao_fica_em_cache(self):
        obj = types.SimpleNamespace(registrar=lambda *a, **k: None)
        with patch('acoes_mixin.requests.get') as get:
            get.return_value = Mock(json=Mock(return_value={'results': []}))
            AcoesMixin.geocodificar_cidade(obj, 'Lugarnenhum')
            AcoesMixin.geocodificar_cidade(obj, 'Lugarnenhum')
        # Sem resultado não vale a pena guardar — tenta de novo da próxima vez.
        self.assertEqual(get.call_count, 2)


class TestTextoFalado(unittest.TestCase):
    def test_aviso_de_fallback_nao_e_lido_com_colchetes(self):
        texto = '[NVIDIA indisponível. Resposta pelo Ollama local.]\n\nA RAM é temporária.'
        self.assertEqual(texto_para_fala(texto), 'A RAM é temporária.')

    def test_colchete_no_meio_da_frase_nao_e_afetado(self):
        # Só o aviso de sistema no INÍCIO do texto é removido; colchetes que
        # fazem parte da própria resposta continuam intactos.
        self.assertEqual(texto_para_fala('A RAM [memória] é temporária.'), 'A RAM [memória] é temporária.')


if __name__ == '__main__':
    unittest.main()
