from unittest import TestCase
from unittest.mock import Mock,patch
import gemini_modelos as gm

class Catalogo(TestCase):
    def test_normalizacao(self):
        self.assertEqual(gm.normalizar(' models/gemini-2.5-flash-lite '),'gemini-2.5-flash-lite')
        with self.assertRaises(RuntimeError):gm.normalizar('https://outro/modelo')
    def test_paginacao_filtro_e_chave_em_header(self):
        a=Mock(status_code=200);a.json.return_value={'models':[{'name':'models/gemini-2.5-flash-lite','supportedGenerationMethods':['generateContent']},{'name':'models/embedding','supportedGenerationMethods':['embedContent']}],'nextPageToken':'pagina2'}
        b=Mock(status_code=200);b.json.return_value={'models':[]}
        with patch.object(gm,'ler_chave',return_value='segredo'),patch.object(gm.requests,'get',side_effect=[a,b]) as get:
            self.assertEqual(gm.listar('.'),['gemini-2.5-flash-lite'])
            self.assertEqual(get.call_count,2)
            k=get.call_args.kwargs;self.assertEqual(k['params']['pageToken'],'pagina2')
            self.assertEqual(k['headers']['x-goog-api-key'],'segredo')
            self.assertFalse(k['allow_redirects'])
    def test_erro_nao_expoe_corpo(self):
        r=Mock(status_code=403);r.text='segredo'
        with self.assertRaises(RuntimeError) as cm:gm.verificar(r)
        self.assertNotIn('segredo',str(cm.exception));r.json.assert_not_called()
    def test_loop_paginacao_limitado(self):
        r=Mock(status_code=200);r.json.return_value={'models':[],'nextPageToken':'repetido'}
        with patch.object(gm,'ler_chave',return_value='segredo'),patch.object(gm.requests,'get',return_value=r):
            with self.assertRaisesRegex(RuntimeError,'inválido'):gm.listar('.')

    def test_diagnostico_404_redige_segredo(self):
        r=Mock(status_code=404)
        r.json.return_value={'error':{'message':'Model missing segredo https://example.com/?key=segredo AIza123456'}}
        with self.assertRaises(RuntimeError) as cm:
            gm.verificar(r,chave='segredo',modelo='gemini-2.5-flash-lite')
        texto=str(cm.exception)
        self.assertIn('Model missing',texto)
        self.assertIn('gemini-2.5-flash-lite',texto)
        self.assertNotIn('segredo',texto)
        self.assertNotIn('https://',texto)
        self.assertNotIn('AIza',texto)

    def test_diagnostico_404_html(self):
        r=Mock(status_code=404);r.json.side_effect=ValueError()
        with self.assertRaisesRegex(RuntimeError,'geração nativa'):
            gm.verificar(r,chave='segredo',modelo='gemini-2.5-flash-lite')
