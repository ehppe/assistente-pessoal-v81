"""Conjuntos de frases variadas para as respostas do Neymar.

Em vez de sempre repetir o mesmo texto para a mesma ação, o Neymar sorteia
uma entre várias formas de dizer a mesma coisa. Isso, mais o tom escolhido
com "tratamento" no config.json, deixa as respostas menos "automáticas".
"""
import random


def variar(opcoes, tratamento='', **campos):
    frase = random.choice(opcoes).format(**campos)
    if tratamento and random.random() < 0.25 and not frase.rstrip().endswith('?'):
        frase = frase.rstrip('.') + f', {tratamento}.'
    return frase


ABRIR = [
    'Abrindo {n}.',
    'Certo, iniciando {n}.',
    '{n} a caminho.',
    'Já estou abrindo {n}.',
    'Pronto, {n} já vai abrir.',
]

FECHAR = [
    'Fechando {n}.',
    'Encerrando {n} agora.',
    '{n} fechado em instantes.',
    'Certo, encerrando {n}.',
]

ARQUIVO = [
    'Abrindo {n}.',
    'Aqui está: {n}.',
    'Encontrei e já abri {n}.',
]

VOLUME_MAIS = ['Aumentei o volume.', 'Volume mais alto.', 'Subindo o som.']
VOLUME_MENOS = ['Diminuí o volume.', 'Volume mais baixo.', 'Baixando o som.']
MUDO = ['Som alternado.', 'Pronto, ajustei o mudo.', 'Feito.']
PAUSAR_MIDIA = ['Pronto.', 'Feito.', 'Música pausada ou retomada.']
PROXIMA_MUSICA = ['Próxima música.', 'Pulando para a próxima faixa.', 'Trocando de música.']

PESQUISANDO = ['Pesquisando.', 'Já busquei isso para você.', 'Procurando agora.']
YOUTUBE = ['Abrindo no YouTube.', 'Tocando no YouTube.', 'Já coloquei no YouTube.']
SPOTIFY = ['Abrindo no Spotify.', 'Já busquei no Spotify.', 'Tocando no Spotify.']

HORA = ['Agora são {h}.', 'São {h} agora.', 'O relógio marca {h}.']

OUVINDO = ['Estou ouvindo...', 'Pode falar.', 'Diga o que precisa.', 'Sou todo ouvidos.']
CONTINUAR = [
    'Precisa de mais alguma coisa?',
    'Quer pedir mais alguma coisa?',
    'Posso ajudar com algo mais?',
]

NAO_ENTENDI = [
    'Não entendi. Pode pedir de outra forma?',
    'Não captei esse pedido, pode repetir?',
    'Isso eu ainda não sei fazer.',
]

SEM_RESPOSTA = ['Não encontrei uma resposta.', 'Não consegui responder isso agora.']

ERRO_GENERICO = [
    'Não consegui executar isso.',
    'Algo deu errado nessa tentativa.',
    'Não consegui concluir esse pedido.',
]
