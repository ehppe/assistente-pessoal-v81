import sys,tempfile,threading,time,json
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modo_jogo import ModoJogo,WindowsJogo,interpretar,selecionados,ALTO
from runtime_mixin import RuntimeMixin
from jogo_mixin import JogoMixin
BAL='381b4222-f694-41f0-9685-ff5bb260df2e'
OUTRO='a1841308-3541-4fab-bc81-f71556f20b4a'

def sistema():
    s=Mock();s.plano=BAL;s.prio=32768
    s.plano_atual.side_effect=lambda:s.plano
    s.aplicar_plano.side_effect=lambda g:setattr(s,'plano',g)
    s.prioridade.side_effect=lambda v=None:s.prio if v is None else setattr(s,'prio',v)
    s.prioridade_normal.return_value=32
    s.alto_disponivel.return_value=True;s.memoria.return_value=4*2**30
    s.processos.return_value=[];s.fechar_janelas.return_value=1
    return s

class TestModoJogo(TestCase):
    def test_comandos_nao_confundem_rotina_existente_nem_negacao(self):
        for t in ('Neymar, ative o modo de jogo','modo de jogo','pode ativar modo de jogo'):
            self.assertEqual(interpretar(t),'ativar')
        self.assertEqual(interpretar('saír do modo de jogo'),'desativar')
        for t in ('não ative modo de jogo','como ativar modo de jogo?','modo jogar','explique modo de jogo'):
            self.assertIsNone(interpretar(t))

    def test_somente_catalogo_explicito(self):
        cfg={'modo_jogo_fechar':['CHROME.EXE','chrome.exe','discord.exe','steam.exe','svchost.exe','msmpeng.exe','pythonw.exe','cs2.exe','tailscale.exe','obs64.exe','C:/chrome.exe',None]}
        self.assertEqual(selecionados(cfg),['chrome.exe'])
        self.assertEqual(selecionados({'modo_jogo_fechar':'chrome.exe'}),[])

    def test_fecha_apenas_selecionado_e_reporta_app_que_ficou(self):
        with tempfile.TemporaryDirectory() as d:
            s=sistema();chrome={'pid':5,'nome':'chrome.exe','criado':1,'rss':100}
            discord={'pid':6,'nome':'discord.exe','criado':2,'rss':200}
            s.processos.return_value=[chrome,discord]
            modo=ModoJogo(d,s);r=modo.ativar({'modo_jogo_fechar':['chrome.exe','discord.exe']})
            s.fechar_janelas.assert_called_once_with(chrome)
            self.assertIn('Ainda abertos',r);self.assertNotIn('Fechados:',r);self.assertTrue(modo.ativo)
            s.aplicar_plano.assert_not_called()

    def test_fechamento_confirmado_sem_matar_processos(self):
        with tempfile.TemporaryDirectory() as d:
            s=sistema();s.processos.side_effect=[[{'pid':5,'nome':'chrome.exe','criado':1,'rss':100}],[]]
            r=ModoJogo(d,s).ativar({'modo_jogo_fechar':['chrome.exe']})
            self.assertIn('Fechados: Google Chrome',r)

    def test_backup_antes_de_mudar_e_restauracao(self):
        with tempfile.TemporaryDirectory() as d:
            s=sistema();m=ModoJogo(d,s)
            def aplicar(g):
                self.assertTrue(m.arquivo.exists());self.assertEqual(json.loads(m.arquivo.read_text())['anterior'],BAL);s.plano=g
            s.aplicar_plano.side_effect=aplicar
            m.ativar({'modo_jogo_alto_desempenho':True});self.assertEqual(s.plano,ALTO)
            m.desativar();self.assertEqual(s.plano,BAL);self.assertFalse(m.arquivo.exists());self.assertEqual(s.prio,32768)

    def test_ativar_duas_vezes_nao_perde_backup(self):
        with tempfile.TemporaryDirectory() as d:
            s=sistema();m=ModoJogo(d,s)
            m.ativar({'modo_jogo_alto_desempenho':True});m.ativar({'modo_jogo_alto_desempenho':True})
            self.assertEqual(m.energia['anterior'],BAL);s.aplicar_plano.assert_called_once_with(ALTO)

    def test_plano_indisponivel_nao_cria_nem_altera(self):
        with tempfile.TemporaryDirectory() as d:
            s=sistema();s.alto_disponivel.return_value=False
            r=ModoJogo(d,s).ativar({'modo_jogo_alto_desempenho':True})
            self.assertIn('não está disponível',r);s.aplicar_plano.assert_not_called()

    def test_falha_de_backup_impede_troca(self):
        with tempfile.TemporaryDirectory() as d:
            s=sistema();m=ModoJogo(d,s)
            with patch.object(m,'guardar_energia',side_effect=OSError('sem acesso')):m.ativar({'modo_jogo_alto_desempenho':True})
            s.aplicar_plano.assert_not_called()

    def test_plano_manual_preservado(self):
        with tempfile.TemporaryDirectory() as d:
            s=sistema();m=ModoJogo(d,s);m.ativar({'modo_jogo_alto_desempenho':True});s.plano=OUTRO
            m.desativar();self.assertEqual(s.plano,OUTRO);self.assertIsNone(m.energia)

    def test_recupera_apos_reinicio(self):
        with tempfile.TemporaryDirectory() as d:
            s=sistema();m=ModoJogo(d,s);m.ativar({'modo_jogo_alto_desempenho':True})
            outro=ModoJogo(d,s);self.assertFalse(outro.ativo);outro.desativar()
            self.assertEqual(s.plano,BAL)

    def test_falha_restauracao_mantem_backup_para_tentar_novamente(self):
        with tempfile.TemporaryDirectory() as d:
            s=sistema();m=ModoJogo(d,s);m.ativar({'modo_jogo_alto_desempenho':True})
            s.aplicar_plano.side_effect=RuntimeError('negado');r=m.desativar()
            self.assertTrue(m.arquivo.exists());self.assertIn('tente',r)
            s.aplicar_plano.side_effect=lambda g:setattr(s,'plano',g)
            m.desativar();self.assertFalse(m.arquivo.exists())

    def test_backup_corrompido_nao_sobrescrito(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'dados'/'modo-jogo-energia.json';p.parent.mkdir();p.write_text('invalido')
            s=sistema();m=ModoJogo(d,s);m.ativar({'modo_jogo_alto_desempenho':True});m.desativar()
            self.assertEqual(p.read_text(),'invalido');s.aplicar_plano.assert_not_called()

    def test_cancelamento_nao_fecha_mais_apps_e_restaura(self):
        with tempfile.TemporaryDirectory() as d:
            s=sistema();s.processos.return_value=[{'nome':'chrome.exe'}]
            flag=threading.Event()
            def aplicar(g):s.plano=g;flag.set()
            s.aplicar_plano.side_effect=aplicar
            m=ModoJogo(d,s);m.ativar({'modo_jogo_fechar':['chrome.exe'],'modo_jogo_alto_desempenho':True},flag.is_set)
            s.fechar_janelas.assert_not_called();self.assertFalse(m.ativo);self.assertEqual(s.plano,BAL)

    def test_primeira_vez_abre_configuracao_sem_fechar(self):
        o=Mock();o.config={};o.recuperando_jogo=False
        r=JogoMixin.executar_modo_jogo(o,'ativar')
        o.modo_jogo.ativar.assert_not_called();self.assertIn('primeira vez',r)
        o.ui.assert_called_once_with(0,o.abrir_modo_jogo)

    def test_rota_nova_e_antiga_distintas(self):
        o=Mock()
        self.assertEqual(RuntimeMixin.basico(o,'modo de jogo'),{'action':'game_mode','target':'ativar'})
        self.assertEqual(RuntimeMixin.basico(o,'modo jogar'),{'action':'rotina_jogar','target':''})

    def test_pid_reutilizado_ou_outro_usuario_nao_fecha(self):
        s=WindowsJogo();p=Mock();p.name.return_value='chrome.exe';p.create_time.return_value=999;p.username.return_value='eu'
        with patch('modo_jogo.psutil.Process',return_value=p):
            self.assertFalse(s.mesmo_processo({'pid':5,'nome':'chrome.exe','criado':1}))
            self.assertEqual(s.fechar_janelas({'pid':5,'nome':'chrome.exe','criado':1}),0)

    def test_plano_guid_invalido_nao_executa(self):
        s=WindowsJogo()
        with patch.object(s,'powercfg') as comando:
            with self.assertRaises(ValueError):s.aplicar_plano('x & shutdown')
            comando.assert_not_called()

    def test_indexacao_aguarda_modo_e_respeita_saida(self):
        from indice_mixin import IndiceMixin
        from types import SimpleNamespace
        o=SimpleNamespace(modo_jogo=SimpleNamespace(ativo=True),encerrar=threading.Event())
        resultado=[];t=threading.Thread(target=lambda:resultado.append(IndiceMixin.aguardar_indexacao(o)))
        t.start();self.assertTrue(t.is_alive());o.encerrar.set();t.join(1)
        self.assertEqual(resultado,[False])
