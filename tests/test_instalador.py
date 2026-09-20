from pathlib import Path
import unittest


RAIZ = Path(__file__).resolve().parents[1]


class InstaladorUnico(unittest.TestCase):
    def test_principal_e_trabalhador_tem_subsistemas_separados(self):
        spec = (RAIZ / 'build' / 'Neymar.spec').read_text(encoding='utf-8')
        self.assertIn("name='Neymar'", spec)
        self.assertIn('console=False', spec)
        self.assertIn("name='NeymarWorker'", spec)
        self.assertIn('console=True', spec)

    def test_subprocessos_usam_trabalhador_quando_empacotados(self):
        for arquivo in ('central_bridge.py', 'voz_mixin.py', 'conversa_mixin.py'):
            fonte = (RAIZ / arquivo).read_text(encoding='utf-8')
            self.assertIn('NeymarWorker.exe', fonte)
            self.assertIn("getattr(sys,'frozen',False)", fonte)

    def test_instalacao_e_por_usuario_e_preserva_dados(self):
        script = (RAIZ / 'build' / 'Neymar.iss').read_text(encoding='utf-8')
        self.assertIn('DefaultDirName={localappdata}', script)
        self.assertIn('PrivilegesRequired=lowest', script)
        self.assertNotIn('UninstallDelete', script)

    def test_workflow_publica_apenas_instalador(self):
        fluxo = (RAIZ / '.github' / 'workflows' / 'instalador-windows.yml').read_text(encoding='utf-8')
        self.assertIn('dist/Neymar-Setup-v81.exe', fluxo)
        self.assertNotIn('config.json', fluxo)
        self.assertNotIn('dados/', fluxo)

    def test_catalogo_contem_sites_oficiais_pedidos(self):
        fonte = (RAIZ / 'indice_mixin.py').read_text(encoding='utf-8')
        self.assertIn("'netflix': ('https://www.netflix.com/br/'", fonte)
        self.assertIn("'globo esporte': ('https://ge.globo.com/'", fonte)

    def test_destino_desconhecido_pesquisa_site_oficial(self):
        fonte = (RAIZ / 'indice_mixin.py').read_text(encoding='utf-8')
        self.assertIn("quote_plus(n + ' site oficial')", fonte)
        self.assertIn("return 'pesquisa por ' + t", fonte)


if __name__ == '__main__':
    unittest.main()
