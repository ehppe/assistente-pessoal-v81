"""Síntese Edge online e reprodução no processo de voz, interrompível pelo Neymar."""
import asyncio
import io

VOZES_EDGE={
    'Antonio — masculina (Brasil)':'pt-BR-AntonioNeural',
    'Francisca — feminina (Brasil)':'pt-BR-FranciscaNeural',
}

async def gerar(texto,voz,ritmo):
    import edge_tts
    audio=bytearray()
    async for item in edge_tts.Communicate(texto,voz,rate=f'{ritmo:+d}%').stream():
        if item['type']=='audio':audio.extend(item['data'])
    if not audio:raise RuntimeError('Edge-TTS não retornou áudio.')
    return bytes(audio)

def reproduzir(texto,voz,ritmo=0):
    if voz not in VOZES_EDGE.values():raise RuntimeError('Escolha uma voz Edge da lista.')
    try:
        import av
        import sounddevice as sd
        async def executar():return await asyncio.wait_for(gerar(texto,voz,max(-30,min(30,int(ritmo)))),timeout=45)
        audio=asyncio.run(executar())
        with av.open(io.BytesIO(audio),format='mp3') as arquivo:
            conversor=av.AudioResampler(format='s16',layout='mono',rate=24000)
            with sd.RawOutputStream(samplerate=24000,channels=1,dtype='int16') as saida:
                for frame in arquivo.decode(audio=0):
                    for convertido in conversor.resample(frame):saida.write(convertido.to_ndarray().tobytes())
                for convertido in conversor.resample(None):saida.write(convertido.to_ndarray().tobytes())
    except ImportError:raise RuntimeError('Execute 6 - Instalar teste Groq e Edge.bat antes de usar Edge-TTS.') from None
    except Exception:raise RuntimeError('Edge-TTS falhou. Confira a internet ou escolha piper/windows nas configurações.') from None
