"""Interpretação do que foi dito (regras rápidas + IA local de apoio) e execução das ações."""
import ctypes
import json
import os
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime

import requests

import frases
from util import norm

_CACHE_GEOCODIFICACAO = {}
_GEOCODIFICACAO_TTL = 6 * 3600  # coordenadas de uma cidade não mudam; só evita repetir a chamada


class AcoesMixin:
    def basico_legado(self, c):
        n = norm(c)
        n = re.sub(r'\b(cromo|chome|crhome|grome)\b', 'chrome', n)
        if any(x in n for x in ('que horas', 'que hora', 'horas sao', 'hora e essa')):
            return {'action': 'hora', 'target': ''}
        if any(x in n for x in (
            'previsao do tempo', 'previsao de tempo', 'como esta o tempo', 'vai chover',
            'clima em', 'tempo em', 'clima hoje', 'clima', 'chuva', 'chovendo', 'vai chuver',
            'esta chovendo', 'tempo hoje', 'temperatura',
        )):
            m = re.search(r'\b(?:em|de|na|no)\s+(?!minha regiao\b)(.+)$', n)
            return {'action': 'clima', 'target': m.group(1).strip() if m else ''}
        if 'deslig' in n:
            return {'action': 'shutdown', 'target': ''}
        if 'reinici' in n:
            return {'action': 'restart', 'target': ''}
        if 'volume' in n and ('aument' in n or 'sub' in n):
            return {'action': 'volume_up', 'target': ''}
        if 'volume' in n and ('dimin' in n or 'baix' in n):
            return {'action': 'volume_down', 'target': ''}
        if any(x in n for x in ('silencie', 'silenciar', 'mudo', 'sem som')):
            return {'action': 'mute', 'target': ''}
        if any(x in n for x in ('pause', 'pausar', 'continue a musica', 'continuar a musica')):
            return {'action': 'media_pause', 'target': ''}
        if any(x in n for x in ('proxima musica', 'proxima faixa', 'pule a musica')):
            return {'action': 'media_next', 'target': ''}
        if any(x in n for x in ('bloqueie', 'bloquear computador', 'trave o computador')):
            return {'action': 'lock', 'target': ''}
        apelidos = list(self.config.get('discord_apelidos_canal', []))
        for item in (self.config.get('discord_canais') or []):
            apelidos.extend(item.get('apelidos', []))
        palavras_n = set(n.split())

        def bate_parcial(apelido):
            palavras_a = norm(apelido).split()
            if not palavras_a:
                return False
            acertos = sum(1 for p in palavras_a if p in palavras_n)
            return acertos / len(palavras_a) >= 0.5

        destino_discord = 'discord' in n or any(norm(x) in n for x in apelidos)
        if destino_discord and any(x in n for x in ('saia', 'sair', 'desconecte', 'desconectar', 'desligue da chamada')):
            return {'action': 'discord_leave', 'target': ''}
        if destino_discord and any(x in n for x in ('entre', 'entrar', 'conecte', 'conectar', 'abra', 'abrir', 'acesse')):
            return {'action': 'discord_join', 'target': n}
        termo_aba = any(re.search(r'\b' + x + r'\b', n) for x in ('aba', 'agua', 'guia', 'pagina'))
        if termo_aba and re.search(r'\b(abra|abre|abrir|crie|criar)\b', n) and (any(x in n for x in ('nova', 'outra', 'mais uma')) or 'chrome' in n):
            return {'action': 'browser_new_tab', 'target': ''}
        if termo_aba and re.search(r'\b(feche|fecha|fechar|encerre)\b', n):
            alvo = re.sub(r'\b(feche|fecha|fechar|encerre|a|aba|agua|guia|pagina|do|da|no|na|chrome|navegador|atual|essa|esta)\b', ' ', n)
            return {'action': 'browser_close_tab', 'target': re.sub(r'\s+', ' ', alvo).strip()}
        if ('gamers club' in n or re.search(r'\bgc\b', n)) and any(x in n for x in ('cs2', 'cs dois', 'c s dois', 'sc2', 'counter strike')):
            return {'action': 'launch_gc_cs2', 'target': ''}
        if re.search(r'\b(feche|fecha|fechar|encerre|encerrar)\b', n):
            return {'action': 'close_app', 'target': re.sub(r'\b(feche|fecha|fechar|encerre|encerrar|o|a|programa|aplicativo|app|jogo)\b', ' ', n).strip()}
        if re.search(r'\b(abra|abre|abrir)\b', n):
            alvo = re.sub(r'\b(abra|abre|abrir|o|a)\b', '', n).strip()
            return {'action': 'open_file' if any(x in n for x in ('arquivo', 'pasta', 'documento', 'foto', 'pdf', 'planilha')) else 'open_app', 'target': alvo}
        if re.search(r'\b(toque|tocar|coloque)\b', n):
            alvo = re.sub(r'^(toque|tocar|coloque)\s+', '', n)
            return {'action': 'play_spotify' if 'spotify' in n else 'play_youtube', 'target': re.sub(r'\b(no|na|pelo|spotify|youtube)\b', ' ', alvo).strip()}
        if re.search(r'\b(pesquise|pesquisar|procure|busque|buscar)\b', n):
            return {'action': 'search_web', 'target': re.sub(r'\b(pesquise|pesquisar|procure|busque|buscar|na internet|por)\b', ' ', n).strip()}
        return {'action': 'unknown', 'target': ''}

    def executar(self, p):
        if not isinstance(p, dict):
            p = {'action': 'unknown', 'target': ''}
        a, t = p.get('action', 'unknown'), str(p.get('target', '') or '').strip()
        if not isinstance(a, str):
            a = 'unknown'
        trat = self.config.get('tratamento', '')
        try:
            if a == 'game_mode':
                ret = self.executar_modo_jogo(t)
            elif a == 'rotina_jogar':
                ret = self.rotina_jogar()
            elif a == 'discord_join':
                ret = self.entrar_discord(t)
            elif a == 'discord_leave':
                ret = self.sair_discord()
            elif a == 'launch_gc_cs2':
                ret = self.abrir_gc_cs2()
            elif a == 'open_app':
                ret = frases.variar(frases.ABRIR, trat, n=self.abrir_app(t))
            elif a == 'close_app':
                ret = frases.variar(frases.FECHAR, trat, n=self.fechar_app(t))
            elif a == 'open_file':
                ret = frases.variar(frases.ARQUIVO, trat, n=self.abrir_arquivo(t))
            elif a == 'browser_new_tab':
                ret = self.nova_aba_chrome()
            elif a == 'browser_close_tab':
                ret = self.fechar_aba_chrome(t)
            elif a == 'play_youtube':
                self.youtube(t)
                ret = frases.variar(frases.YOUTUBE, trat)
            elif a == 'play_spotify':
                os.startfile('spotify:search:' + urllib.parse.quote(t))
                ret = frases.variar(frases.SPOTIFY, trat)
            elif a == 'search_web':
                ret = self.pesquisar_web(t, trat)
            elif a == 'hora':
                ret = frases.variar(frases.HORA, trat, h=datetime.now().strftime('%H:%M'))
            elif a == 'clima':
                ret = self.buscar_clima(t, int(p.get('dias', 0) or 0))
            elif a == 'volume_up':
                [self.tecla(0xAF) for _ in range(5)]
                ret = frases.variar(frases.VOLUME_MAIS, trat)
            elif a == 'volume_down':
                [self.tecla(0xAE) for _ in range(5)]
                ret = frases.variar(frases.VOLUME_MENOS, trat)
            elif a == 'mute':
                self.tecla(0xAD)
                ret = frases.variar(frases.MUDO, trat)
            elif a == 'media_pause':
                self.tecla(0xB3)
                ret = frases.variar(frases.PAUSAR_MIDIA, trat)
            elif a == 'media_next':
                self.tecla(0xB0)
                ret = frases.variar(frases.PROXIMA_MUSICA, trat)
            elif a == 'lock':
                self.falando.clear()
                ctypes.windll.user32.LockWorkStation()
                return
            elif a in ('shutdown', 'restart'):
                self.pedir_confirmacao(a)
                return
            elif a == 'answer':
                ret = t or frases.variar(frases.SEM_RESPOSTA, trat)
            else:
                ret = frases.variar(frases.NAO_ENTENDI, trat)
        except Exception as e:
            self.registrar('ERRO ' + a + ': ' + repr(e))
            detalhe = str(e).strip()
            ret = frases.variar(frases.ERRO_GENERICO, trat) + (' ' + detalhe if detalhe else '')
        self.falar(ret)

    def localizar_cidade_por_ip(self):
        """Descobre a cidade aproximada pela rede (sem GPS, sem depender do
        Windows) — só um pedido HTTPS comum, usando o mesmo requests que já
        é usado para o clima. Menos preciso que o GPS, mas não tem risco
        nenhum de travar o programa, ao contrário da localização nativa do
        Windows (que usa COM por baixo dos panos)."""
        try:
            r = requests.get('https://ipapi.co/json/', timeout=5).json()
            cidade = r.get('city')
            if cidade:
                self.registrar(f'LOCALIZACAO: cidade detectada pela rede: {cidade}')
                return cidade
        except Exception as e:
            self.registrar('AVISO localizacao por rede falhou: ' + repr(e))
        return None

    def geocodificar_cidade(self, nome):
        chave = norm(nome)
        cache = _CACHE_GEOCODIFICACAO.get(chave)
        if cache and time.monotonic() - cache[0] < _GEOCODIFICACAO_TTL:
            return cache[1]
        try:
            geo = requests.get(
                'https://geocoding-api.open-meteo.com/v1/search',
                params={'name': nome, 'count': 1, 'language': 'pt'}, timeout=8,
            ).json()
            resultados = geo.get('results') or []
        except Exception as e:
            self.registrar('ERRO geocodificar_cidade: ' + repr(e))
            return []
        if resultados:
            if len(_CACHE_GEOCODIFICACAO) > 200:_CACHE_GEOCODIFICACAO.clear()
            _CACHE_GEOCODIFICACAO[chave] = (time.monotonic(), resultados)
        return resultados

    def buscar_clima(self, cidade, dias_offset=0):
        pedido_bruto = cidade
        cidade = (cidade or '').strip()
        pediu_regiao = norm(cidade) in ('', 'minha regiao', 'minha cidade', 'aqui', 'minha area', 'minha localizacao')
        if pediu_regiao:
            cidade = self.config.get('cidade_padrao', '').strip()
        if pediu_regiao and not cidade and self.config.get('usar_localizacao_automatica', True):
            cidade = self.localizar_cidade_por_ip() or ''
        self.registrar(f'CLIMA: alvo_recebido="{pedido_bruto}" cidade_padrao="{self.config.get("cidade_padrao", "")}" cidade_usada="{cidade}" dias_a_frente={dias_offset}')
        try:
            if cidade:
                resultados = self.geocodificar_cidade(cidade)
                if not resultados:
                    # "Paranapanema-SP" ou "Paranapanema/SP" não é entendido pela
                    # busca — tenta de novo só com o nome da cidade, sem a sigla
                    # do estado grudada.
                    sem_sigla = re.sub(r'[\s\-/]+[A-Za-z]{2}$', '', cidade).strip()
                    if sem_sigla and sem_sigla.lower() != cidade.lower():
                        self.registrar(f'CLIMA: "{cidade}" nao encontrada, tentando "{sem_sigla}"')
                        resultados = self.geocodificar_cidade(sem_sigla)
                if not resultados:
                    return 'Não encontrei essa cidade para checar o tempo.'
                lat, lon = resultados[0]['latitude'], resultados[0]['longitude']
                nome_cidade = resultados[0]['name']
            else:
                return (
                    'Não sei qual é a sua região ainda — diga o nome de uma cidade, ou '
                    'configure "cidade_padrao" no config.json (ou pelo menu da bandeja, '
                    'em "Configurar minha cidade") para eu saber por padrão.'
                )
            previsao = requests.get(
                'https://api.open-meteo.com/v1/forecast',
                params={
                    'latitude': lat, 'longitude': lon,
                    'current': 'temperature_2m,precipitation',
                    'daily': 'temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum',
                    'timezone': 'auto',
                    'forecast_days': 16,
                },
                timeout=8,
            ).json()
            diario = previsao.get('daily', {})
            maximos = diario.get('temperature_2m_max') or []
            minimos = diario.get('temperature_2m_min') or []
            probabilidades = diario.get('precipitation_probability_max') or []
            datas = diario.get('time') or []
            if dias_offset <= 0:
                atual = previsao.get('current', {})
                temperatura = atual.get('temperature_2m')
                chuva_agora = atual.get('precipitation', 0)
                prob_chuva = probabilidades[0] if probabilidades else None
                if temperatura is None:
                    return 'Não consegui obter a previsão agora.'
                resposta = f'Em {nome_cidade}, a temperatura agora é {round(temperatura)} graus.'
                if chuva_agora and chuva_agora > 0:
                    resposta += ' Está chovendo no momento.'
                sufixo_dia = 'hoje'
            else:
                if dias_offset >= len(maximos) or dias_offset >= len(minimos):
                    return f'Só tenho previsão de até {max(0, len(maximos) - 1)} dias à frente; ainda não dá para saber o tempo tão longe.'
                minimo, maximo = minimos[dias_offset], maximos[dias_offset]
                if minimo is None or maximo is None:
                    return 'Não consegui obter a previsão para esse dia.'
                data_extenso_str = ''
                if dias_offset < len(datas):
                    try:
                        from datetime import datetime as _dt
                        from calendario_local import data_extenso
                        data_extenso_str = data_extenso(_dt.strptime(datas[dias_offset], '%Y-%m-%d'))
                    except (ValueError, TypeError):
                        pass
                resposta = f'Em {nome_cidade}' + (f', {data_extenso_str}' if data_extenso_str else '') + f': mínima de {round(minimo)} e máxima de {round(maximo)} graus.'
                prob_chuva = probabilidades[dias_offset] if dias_offset < len(probabilidades) else None
                sufixo_dia = 'nesse dia'
            if prob_chuva is not None:
                prob_chuva = round(prob_chuva)
                if prob_chuva >= 60:
                    resposta += f' A chance de chuva {sufixo_dia} é alta, {prob_chuva}%.'
                elif prob_chuva >= 25:
                    resposta += f' Existe uma chance de chuva {sufixo_dia}, de {prob_chuva}%.'
                else:
                    resposta += f' A chance de chuva {sufixo_dia} é baixa, {prob_chuva}%.'
            return resposta
        except Exception as e:
            self.registrar('ERRO buscar_clima: ' + repr(e))
            return 'Não consegui consultar a previsão do tempo agora.'

    def pesquisar_web(self, termo, trat):
        """Pesquisa de verdade (Brave Search) quando há uma chave salva; sem
        chave, mantém o comportamento antigo de só abrir o navegador — não
        inventa uma resposta sem ter buscado nada de verdade."""
        from credenciais import caminho
        termo = (termo or '').strip()
        tem_chave = False
        try:
            tem_chave = caminho(self.base, 'brave').exists()
        except Exception:
            pass
        if not tem_chave:
            if termo:
                webbrowser.open('https://google.com/search?q=' + urllib.parse.quote_plus(termo))
            return frases.variar(frases.PESQUISANDO, trat)
        from busca_web import pesquisar
        try:
            resultados = pesquisar(self.base, termo)
        except RuntimeError as e:
            self.registrar('ERRO pesquisar_web: ' + str(e))
            if termo:
                webbrowser.open('https://google.com/search?q=' + urllib.parse.quote_plus(termo))
            return str(e) + ' Abri a busca no navegador.'
        if termo:
            webbrowser.open('https://google.com/search?q=' + urllib.parse.quote_plus(termo))
        if not resultados:
            return 'Não encontrei resultados na pesquisa. Abri a busca no navegador.'
        partes = [r['titulo'] + (' — ' + r['descricao'] if r['descricao'] else '') for r in resultados[:3]]
        return 'Pesquisei na internet: ' + ' '.join(partes)

    def youtube(self, t):
        q = urllib.parse.quote_plus(t)
        req = urllib.request.Request(
            'https://youtube.com/results?search_query=' + q,
            headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'pt-BR'},
        )
        pag = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', 'ignore')
        m = re.search(r'"videoRenderer"\s*:\s*\{\s*"videoId"\s*:\s*"([\w-]{11})"', pag)
        webbrowser.open('https://youtube.com/watch?v=' + m.group(1) + '&autoplay=1' if m else 'https://youtube.com/results?search_query=' + q)

    @staticmethod
    def tecla(c):
        ctypes.windll.user32.keybd_event(c, 0, 0, 0)
        ctypes.windll.user32.keybd_event(c, 0, 2, 0)
