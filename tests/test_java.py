"""Testes sem ações reais no Windows nem consumo de API. python -m unittest discover -s tests -v"""
import copy
import json
import queue
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if sys.platform!='win32':
    for name in ('winsound','sounddevice','speech_recognition','vosk','winreg'):
        sys.modules[name]=types.ModuleType(name)
    sys.modules['vosk'].KaldiRecognizer=Mock();sys.modules['vosk'].Model=Mock()
from motor import Confirmacao, Memoria, resposta_confirmacao, tipo_pedido
from runtime_mixin import RuntimeMixin
from voz_mixin import VozMixin
from acoes_mixin import AcoesMixin
from discord_mixin import DiscordMixin
from config import PADRAO, carregar, salvar
import inteligencia

class Harness(RuntimeMixin,VozMixin,AcoesMixin,DiscordMixin):
    def __init__(self,base):
        self.base=base;self.config=copy.deepcopy(PADRAO);self.config['responder_por_voz']=False
        self.root=Mock();self.encerrar=threading.Event();self.falando=threading.Event();self.pausado=threading.Event()
        self.chamada_id=0;self.ativo_ate=0;self.estado_visual='idle';self.comando_atual='';self.confirmacao_ate=0
        self.logs=[];self.preparar_runtime()
    def registrar(self,s):self.logs.append(s)
    def mostrar(self,s):self.ultimo_status=s
    def atualizar_chat(self):pass
    def parar(self):self.encerrar.set()

def aguardar(cond):
    limite=time.monotonic()+3
    while time.monotonic()<limite:
        if cond():return
        time.sleep(.01)
    raise AssertionError('Tempo de teste excedido')

class TestNeymar(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_negativas(self):
        for t in ('não desligue o computador','não abra o Chrome','como reiniciar o Windows?','explique o que é temperatura'):
            self.assertEqual(tipo_pedido(t),'conversa')
        for t in ('não pode confirmar','não confirmar','cancelar','não confirmado'):
            self.assertIs(resposta_confirmacao(t),False)
        self.assertIsNone(resposta_confirmacao('explique como confirmar'))
    def test_prazo_token_repeticao(self):
        clock=[0];c=Confirmacao(lambda:clock[0]);t=c.iniciar('shutdown')
        self.assertIsNone(c.consumir(True,'token-errado'))
        self.assertEqual(c.consumir(True,t),'shutdown')
        self.assertIsNone(c.consumir(True,t))
        t=c.iniciar('restart');clock[0]=31
        self.assertIsNone(c.consumir(True,t))
    def test_confirmacoes_concorrentes(self):
        c=Confirmacao();t=c.iniciar('shutdown');result=[]
        threads=[threading.Thread(target=lambda:result.append(c.consumir(True,t))) for _ in range(8)]
        for th in threads:th.start()
        for th in threads:th.join()
        self.assertEqual(result.count('shutdown'),1)
    def test_memoria_persistencia(self):
        p=self.base/'conversa.json';m=Memoria(p)
        for i in range(70):m.adicionar(str(i),'resposta '+str(i))
        rec=Memoria(p);self.assertEqual(len(rec.lista()),60);self.assertEqual(len(rec.contexto()),16)
        self.assertEqual(rec.contexto()[-1]['content'],'resposta 69');rec.limpar();self.assertFalse(p.exists())
    def test_sem_salvar(self):
        m=Memoria(self.base/'c.json',False);m.adicionar('a','b');self.assertFalse(m.caminho.exists())
    def test_config_preserva_canais(self):
        cfg=copy.deepcopy(PADRAO);cfg['discord_canais']=[{'apelidos':['meu canal'],'servidor_id':'123','canal_id':'456','canal_nome':'teste'}];cfg['segundos_conversa_continua']=999;cfg['migracao_ativacao_57']=True
        salvar(self.base,cfg);c=carregar(self.base)
        self.assertEqual(c['discord_canais'][0]['apelidos'],['meu canal']);self.assertEqual(c['segundos_conversa_continua'],30)
    def test_config_tipos(self):
        (self.base/'config.json').write_text('{"cor_nucleo":[],"palavras_ativacao":null,"discord_canais":[null]}')
        c=carregar(self.base);self.assertTrue(c['palavras_ativacao']);self.assertEqual(len(c['cor_nucleo']),3)
    def test_pergunta_de_continuacao_e_encerramento(self):
        h=Harness(self.base);h.config['responder_por_voz']=True;h.config['perguntar_apos_resposta']=True
        try:
            self.assertTrue(h.deve_perguntar_continuacao('abra o Chrome',h.geracao))
            self.assertFalse(h.deve_perguntar_continuacao('não, obrigado',h.geracao))
            h.falar=Mock()
            self.assertTrue(h.perguntar_continuacao('abra o Chrome',h.geracao))
            self.assertTrue(h.aguardando_continuacao);h.falar.assert_called_once()
        finally:h.parar()
    def test_falha_de_reconhecimento_pede_repeticao(self):
        h=Harness(self.base);h.config['responder_por_voz']=True;h.falar=Mock()
        try:
            h.pedir_repeticao()
            self.assertTrue(h.aguardando_repeticao)
            self.assertEqual(h.chamada_id,1)
            h.falar.assert_called_once_with('Não entendi o que você quis dizer. Pode repetir?',registrar=False)
        finally:h.parar()
    def test_roteamento_discord(self):
        h=Harness(self.base)
        h.config['discord_canais']=[{'apelidos':['equipe','comp1'],'servidor_id':'123','canal_id':'456','canal_nome':'teste'}]
        try:
            self.assertEqual(h.basico('desligue da chamada do Discord')['action'],'discord_leave')
            self.assertEqual(h.basico('não desligue o computador')['action'],'unknown')
            self.assertEqual(h.basico('explique o que é temperatura')['action'],'unknown')
            self.assertEqual(h.basico('entre no equipe')['action'],'discord_join')
            self.assertEqual(h.basico('modo jogar')['action'],'rotina_jogar')
            self.assertEqual(h.localizar_canal_discord('entre no comp1')[1],'456')
            with self.assertRaises(RuntimeError):h.localizar_canal_discord('canal totalmente desconhecido')
        finally:h.parar()
    def test_fila_memoria_ordem(self):
        h=Harness(self.base);contextos=[]
        def responder(b,c,m,p):contextos.append(m);return 'Resposta para '+p
        try:
            with patch('runtime_mixin.responder',side_effect=responder):
                h.processar('Explique o céu azul');h.processar('Agora detalhe isso')
                aguardar(lambda:len(h.memoria.lista())==2 and not h.ocupado.is_set())
            self.assertEqual([d['comando'] for d in h.memoria.lista()],['Explique o céu azul','Agora detalhe isso'])
            self.assertIn('céu azul',contextos[1][0]['content'])
        finally:h.parar()
    def test_cancelar_ia_em_andamento(self):
        h=Harness(self.base);iniciou=threading.Event();liberar=threading.Event()
        def responder(*args):iniciou.set();liberar.wait(2);return 'Resposta cancelada'
        try:
            with patch('runtime_mixin.responder',side_effect=responder):
                h.processar('explique algo');self.assertTrue(iniciou.wait(1));h.processar('outra pergunta');h.cancelar_tudo();liberar.set()
                aguardar(lambda:not h.ocupado.is_set())
            self.assertEqual(h.memoria.lista(),[]);self.assertTrue(h.fila_comandos.empty())
        finally:liberar.set();h.parar()
    def test_confirmar_nunca_roda_sem_token(self):
        h=Harness(self.base)
        try:
            h.confirmacao.iniciar('shutdown')
            with patch('runtime_mixin.subprocess.Popen') as popen:
                h.resolver_confirmacao(True,None);popen.assert_not_called()
                t=h.confirmacao.estado()[1];h.resolver_confirmacao(False,t);popen.assert_not_called()
        finally:h.parar()
    def test_confirmar_uma_vez(self):
        h=Harness(self.base)
        try:
            t=h.confirmacao.iniciar('restart')
            with patch('runtime_mixin.subprocess.Popen') as popen:
                h.resolver_confirmacao(True,t);h.resolver_confirmacao(True,t)
                self.assertEqual(popen.call_count,1);self.assertEqual(popen.call_args.args[0][1],'/r')
        finally:h.parar()
    def test_erro_modelo_local(self):
        cfg=dict(PADRAO,provedor_ia='ollama');r=Mock(status_code=404)
        with patch('inteligencia.requests.post',return_value=r):
            with self.assertRaisesRegex(RuntimeError,'modelo'):inteligencia.responder(self.base,cfg,[],'oi')
    def test_palavra_ativacao(self):
        h=Harness(self.base)
        try:
            self.assertIsNone(h.palavra_ativacao('eu estava viajando'))
            self.assertIsNone(h.palavra_ativacao('javascript'))
            self.assertEqual(h.palavra_ativacao('neymar abra o chrome'),'neymar')
        finally:h.parar()
    def test_ui_fila(self):
        h=Harness(self.base);called=[]
        try:
            th=threading.Thread(target=lambda:h.ui(0,lambda:called.append(threading.get_ident())));th.start();th.join()
            self.assertFalse(called);h.entregar_eventos();self.assertEqual(called,[threading.get_ident()])
        finally:h.parar()




class TestLocal(unittest.TestCase):
    def test_config_forca_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            (base/'config.json').write_text(json.dumps({'provedor_ia':'openai','provedor_voz':'openai','modelo_openai':'antigo'}))
            cfg=carregar(base)
            self.assertEqual(cfg['provedor_ia'],'ollama');self.assertEqual(cfg['provedor_voz'],'windows')
            self.assertNotIn('modelo_openai',cfg)
    def test_endpoint_sempre_local(self):
        r=Mock(status_code=200);r.json.return_value={'message':{'content':'Resposta local'}}
        with patch('inteligencia.requests.post',return_value=r) as post:
            ret=inteligencia.responder(Path('.'),{'provedor_ia':'openai'},[{'role':'user','content':'antes'}],'agora')
            self.assertEqual(ret,'Resposta local')
            self.assertEqual(post.call_args.args[0],'http://127.0.0.1:11434/api/chat')
            self.assertEqual(len(post.call_args.kwargs['json']['messages']),3)
            self.assertNotIn('headers',post.call_args.kwargs)
    def test_modelos_layouts(self):
        from instalar_modelo import modelo_valido
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            self.assertFalse(modelo_valido(p))
            for name in ('final.mdl','HCLr.fst','Gr.fst','mfcc.conf'):(p/name).write_text('teste')
            self.assertTrue(modelo_valido(p))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for name in ('am/final.mdl','conf/mfcc.conf','graph/HCLG.fst'):
                f=p/name;f.parent.mkdir(exist_ok=True);f.write_text('teste')
            self.assertTrue(modelo_valido(p))

if __name__=='__main__':unittest.main()
