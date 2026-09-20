"""Processo de síntese de voz, isolado do processo principal para conter falhas nativas.

Modo normal (sem argumentos): fica vivo lendo um pedido de fala por linha JSON
na entrada padrão e respondendo uma linha JSON por pedido ({"ok":true} ou
{"ok":false,"erro":"..."}). Isso evita reimportar bibliotecas pesadas e
recarregar o modelo Piper a cada frase — só paga esse custo uma vez, na
primeira fala, e volta a pagar somente se o processo for encerrado (por uma
interrupção "Pode parar"/Esc ou por uma falha nativa). É o próprio Neymar
(voz_mixin.py) quem sobe e mantém esse processo; nunca é chamado à mão.

'--listar' continua um modo à parte, de um único pedido, usado só para listar
as vozes do Windows na tela de Configurações.
"""
import json
import os
import sys
from pathlib import Path
from texto_resposta import texto_para_fala

_VOZES_PIPER = {}
_ENGINE_WINDOWS = None
_ESPEAK_PRONTO = False


def _preparar_espeak():
    """Aponta o ESPEAK_DATA_PATH uma única vez por processo (usado pela voz Piper)."""
    global _ESPEAK_PRONTO
    if _ESPEAK_PRONTO:return
    import espeakng_loader
    import shutil
    origem=espeakng_loader.get_data_path()
    if not origem.isascii():
        # espeak-ng não lida bem com acento no caminho (ex.: pasta "Escritório").
        destino=Path(os.environ.get('PROGRAMDATA','C:/ProgramData'))/'JavaAssistente'/'espeak-ng-data'
        if not destino.exists():shutil.copytree(origem,destino)
        origem=str(destino)
    os.environ['ESPEAK_DATA_PATH']=origem
    _ESPEAK_PRONTO=True


def _voz_piper(base,identificador):
    """Carrega o modelo Piper uma vez por (pasta, voz) e reaproveita nas falas seguintes."""
    from vozes import arquivos_voz, instalada
    if not instalada(base,identificador):raise RuntimeError('Voz não instalada. Execute 4 - Instalar voz Piper opcional.bat.')
    modelo,_=arquivos_voz(base,identificador)
    chave=str(modelo)
    if chave not in _VOZES_PIPER:
        _preparar_espeak()
        from piper import PiperVoice
        _VOZES_PIPER[chave]=PiperVoice.load(str(modelo))
    return _VOZES_PIPER[chave]


def _falar_piper(dados,texto,base):
    try:
        voz=_voz_piper(base,dados.get('voz_piper','pt_BR-faber-medium'))
        from piper.config import SynthesisConfig
        from audio_piper import reproduzir
        ritmo=max(0.8,min(1.3,float(dados.get('ritmo_piper',1.08))))
        reproduzir(voz,texto,SynthesisConfig(length_scale=1.0/ritmo))
    except RuntimeError:raise
    except Exception as e:raise RuntimeError('A voz Piper falhou. Execute o instalador de vozes ou selecione Windows.') from e


def _falar_windows(dados,texto):
    global _ENGINE_WINDOWS
    import pyttsx3
    if _ENGINE_WINDOWS is None:_ENGINE_WINDOWS=pyttsx3.init()
    voz=_ENGINE_WINDOWS;vozes=voz.getProperty('voices')
    selecionada=dados.get('voz_windows','')
    preferida=next((v for v in vozes if v.id==selecionada),None) if selecionada else None
    if selecionada and preferida is None:raise RuntimeError('Voz Windows indisponível. Escolha outra nas configurações.')
    preferida=preferida or next((v for v in vozes if any(x in v.name.lower() for x in ('portuguese','português','brazil','maria'))),None)
    if preferida:voz.setProperty('voice',preferida.id)
    voz.setProperty('rate',int(dados.get('velocidade',172)))
    voz.say(texto);voz.runAndWait()


def sintetizar(dados):
    """Fala um pedido; usada tanto pelo modo persistente quanto pelo modo de compatibilidade (main())."""
    texto=texto_para_fala(dados['texto']);base=Path(dados['base'])
    if not texto:return
    if dados.get('provedor')=='edge':
        from audio_edge import reproduzir, VOZES_EDGE
        nome=dados.get('voz_edge','Antonio — masculina (Brasil)')
        reproduzir(texto,VOZES_EDGE.get(nome,''),dados.get('ritmo_edge',0));return
    if dados.get('piper'):_falar_piper(dados,texto,base);return
    _falar_windows(dados,texto)


def main():
    """Um único pedido por chamada — mantido para os testes automatizados."""
    sintetizar(json.loads(sys.stdin.buffer.read()))


def main_persistente():
    """Loop principal real: um pedido por linha, uma resposta por linha, até o pipe fechar."""
    saida=sys.stdout.buffer
    for linha in iter(sys.stdin.buffer.readline,b''):
        linha=linha.strip()
        if not linha:continue
        try:
            sintetizar(json.loads(linha))
            saida.write(json.dumps({'ok':True}).encode('utf-8')+b'\n')
        except Exception as e:
            mensagem=str(e) if isinstance(e,RuntimeError) else 'Não consegui reproduzir a voz selecionada.'
            saida.write(json.dumps({'ok':False,'erro':mensagem}).encode('utf-8')+b'\n')
        saida.flush()


def listar_vozes():
    try:
        import pyttsx3
        motor=pyttsx3.init()
        sys.stdout.buffer.write(json.dumps([{'id':v.id,'nome':v.name} for v in motor.getProperty('voices')],ensure_ascii=False).encode('utf-8'))
        motor.stop()
        return 0
    except Exception as e:
        sys.stdout.buffer.write(str(e).encode('utf-8'));sys.stdout.buffer.flush();return 1


if __name__=='__main__':
    if '--listar' in sys.argv:
        sys.exit(listar_vozes())
    else:
        main_persistente()
