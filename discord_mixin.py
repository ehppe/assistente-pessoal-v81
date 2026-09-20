"""Automação de janelas: entrar/sair de chamada do Discord e abrir o CS2 pela Gamers Club.

Tudo aqui usa a acessibilidade do Windows (pywinauto/UI Automation), que por
baixo dos panos depende de COM — por isso cada função roda dentro de
util.com_thread(), inicializando o COM antes de usar essas bibliotecas.
"""
import ctypes
import difflib
import os
import time
import webbrowser
from ctypes import wintypes

from util import com_thread, norm


class DiscordMixin:
    def _pontuacao_apelido(self, apelido_norm, palavras_texto):
        """Compara o apelido com o que foi ouvido palavra por palavra (em vez
        de string inteira) — assim uma palavra reconhecida errada não derruba
        a pontuação toda, e frases sem nenhuma relação não batem por
        coincidência de caracteres."""
        palavras_apelido = apelido_norm.split()
        if not palavras_apelido:
            return 0.0
        pontos = []
        for pa in palavras_apelido:
            if pa in palavras_texto:
                pontos.append(1.0)
            else:
                melhor = max((difflib.SequenceMatcher(None, pa, pt).ratio() for pt in palavras_texto), default=0.0)
                pontos.append(melhor if melhor >= 0.72 else 0.0)
        return sum(pontos) / len(pontos)

    def localizar_canal_discord(self, texto=''):
        """Escolhe qual servidor/canal usar a partir do que foi dito, olhando
        a lista "discord_canais" do config.json. A comparação é tolerante a
        erros do reconhecimento de voz: compara palavra por palavra, não a
        frase inteira, então um apelido de duas palavras ainda é reconhecido
        mesmo que uma delas saia um pouco errada. Se nada bater bem, ou a
        lista estiver vazia, cai para o servidor/canal fixo (compatibilidade
        com configurações antigas, de antes de existir múltiplos canais).

        Retorna (servidor_id, canal_id, apelido_falado, nome_no_discord). O
        "nome_no_discord" é o que deve ser digitado no seletor rápido do
        Discord (Ctrl+K) — pode ser diferente do apelido que você fala, já
        que o apelido é só um jeito de chamar o canal por voz, enquanto o
        seletor rápido busca pelo nome real do canal dentro do Discord."""
        texto = norm(texto or '')
        canais = self.config.get('discord_canais') or []
        if not canais:
            return self.config.get('discord_servidor_id'), self.config.get('discord_canal_id'), 'COMP1', 'comp1'
        palavras_texto = texto.split()
        melhor_item, melhor_apelido, melhor_pontuacao = None, '', 0.0
        for item in canais:
            for apelido in item.get('apelidos', []):
                a = norm(apelido)
                if not a:
                    continue
                pontuacao = self._pontuacao_apelido(a, palavras_texto)
                if pontuacao > melhor_pontuacao:
                    melhor_item, melhor_apelido, melhor_pontuacao = item, apelido, pontuacao
        if melhor_item is None or melhor_pontuacao < 0.8:
            raise RuntimeError('Não identifiquei o canal. Diga um apelido cadastrado, como COMP1, ou adicione o canal nas Configurações.')
        concorrentes = [item for item in canais if item is not melhor_item and any(self._pontuacao_apelido(norm(a),palavras_texto) >= melhor_pontuacao-.1 for a in item.get('apelidos',[]))]
        if concorrentes:
            raise RuntimeError('Encontrei mais de um canal parecido. Diga o apelido completo.')
        item = melhor_item
        rotulo = item.get('apelidos', [melhor_apelido])[0] or melhor_apelido
        nome_busca = item.get('canal_nome') or rotulo
        return item.get('servidor_id'), item.get('canal_id'), rotulo, nome_busca

    def entrar_discord(self, texto=''):
        servidor, canal, rotulo, nome_busca = self.localizar_canal_discord(texto)
        if not servidor or not canal:
            raise RuntimeError('não encontrei um servidor/canal configurado para esse pedido — confira o discord_canais no config.json')
        destino = f'discord://-/channels/{servidor}/{canal}'
        try:
            os.startfile(destino)
        except Exception:
            webbrowser.open(f'https://discord.com/channels/{servidor}/{canal}')
        if not self.config.get('usar_automacao_janelas', True):
            return f'Abri o Discord no canal {rotulo} pelo link direto (automação de janelas desligada nas configurações).'
        limite = time.time() + 15
        janela = None
        try:
            with com_thread():
                from pywinauto import Desktop
                from pywinauto.keyboard import send_keys
                while time.time() < limite and janela is None:
                    for candidata in Desktop(backend='uia').windows():
                        if 'discord' in norm(candidata.window_text()):
                            janela = candidata
                            break
                    if janela is None:
                        time.sleep(.5)
                if janela is None:
                    raise RuntimeError('A janela do Discord não apareceu')
                janela.set_focus()
                time.sleep(1)
                # O link já abre no canal certo, mas o Discord nem sempre entra
                # na voz sozinho. O seletor rápido busca pelo NOME REAL do
                # canal dentro do Discord (não pelo apelido falado, que pode
                # ser diferente) e seleciona, como se o usuário tivesse clicado.
                send_keys('^k')
                time.sleep(.5)
                nome_seguro = ''.join('{'+c+'}' if c in '+^%~(){}' else c for c in nome_busca)
                send_keys('{!}' + nome_seguro, with_spaces=True, pause=.06)
                time.sleep(1)
                send_keys('{ENTER}')
                time.sleep(2)
                # Confirma pelo botão de desconexão; se a interface não expuser o
                # botão, ainda assim o comando de entrada já foi enviado pelo
                # próprio Discord.
                for controle in janela.descendants():
                    nome = norm((controle.window_text() or '') + ' ' + str(getattr(controle.element_info, 'name', '') or ''))
                    if any(x in nome for x in ('desconectar', 'disconnect from voice', 'disconnect')):
                        return f'Selecionei {rotulo} e encontrei uma conexão de voz ativa. Confira no Discord se está no canal correto.'
                self.registrar('DISCORD: seletor rapido executado; botao de desconexao nao ficou acessivel')
                return f'Selecionei o canal {rotulo} no Discord, mas não consegui confirmar se a voz conectou.'
        except Exception as e:
            self.registrar('ERRO discord_join: ' + repr(e))
            raise RuntimeError(f'O Discord abriu, mas não consegui acionar o canal {rotulo}: ' + str(e))

    def sair_discord(self):
        if not self.config.get('usar_automacao_janelas', True):
            raise RuntimeError('a automação de janelas está desligada nas configurações; saia da chamada manualmente')
        try:
            with com_thread():
                from pywinauto import Desktop
                janelas = [j for j in Desktop(backend='uia').windows() if 'discord' in norm(j.window_text())]
                if not janelas:
                    raise FileNotFoundError('Discord não está aberto')
                janela = janelas[0]
                janela.set_focus()
                time.sleep(.3)
                nomes = ('desconectar', 'disconnect', 'sair da chamada', 'disconnect from voice')
                for controle in janela.descendants():
                    texto = norm((controle.window_text() or '') + ' ' + str(getattr(controle.element_info, 'name', '') or ''))
                    if any(nome in texto for nome in nomes):
                        controle.click_input()
                        return 'Saí da chamada do Discord.'
                raise RuntimeError('Não encontrei o botão para sair da chamada')
        except Exception as e:
            self.registrar('ERRO discord_leave: ' + repr(e))
            raise RuntimeError('Não consegui sair automaticamente do Discord: ' + str(e))

    def abrir_gc_cs2(self):
        try:
            nome = self.abrir_app('gamers club')
        except Exception:
            nome = self.abrir_app('gc')
        if not self.config.get('usar_automacao_janelas', True):
            return 'Abri ' + nome + ' (automação de janelas desligada nas configurações — inicie o CS2 manualmente).'
        limite = time.time() + 18
        janela = None
        try:
            with com_thread():
                from pywinauto import Desktop
                while time.time() < limite and janela is None:
                    for candidata in Desktop(backend='uia').windows():
                        titulo = norm(candidata.window_text())
                        if 'gamersclub' in titulo or 'gamers club' in titulo or 'anti-cheat' in titulo or 'anti cheat' in titulo:
                            janela = candidata
                            break
                    if janela is None:
                        time.sleep(.6)
                if janela is not None:
                    janela.set_focus()
                    time.sleep(.5)
                    while time.time() < limite:
                        for controle in janela.descendants():
                            texto = norm(controle.window_text())
                            if 'abrir counter strike' in texto or 'abrir cs2' in texto:
                                controle.click_input()
                                return 'Abri ' + nome + ' e acionei o Counter-Strike pelo Anti-Cheat da Gamers Club.'
                        time.sleep(.5)
        except Exception as e:
            self.registrar('AVISO abrir_gc_cs2 (via acessibilidade): ' + repr(e))
        raise RuntimeError('Não identifiquei o botão de iniciar o CS2. A Gamers Club está aberta; confira o Anti-Cheat e tente novamente.')
