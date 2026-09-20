"""Produz próximos trechos enquanto o áudio anterior toca, com memória limitada."""
import queue
import threading

def reproduzir(voz,texto,config):
    import sounddevice as sd
    fila=queue.Queue(maxsize=3)
    def produzir():
        try:
            for trecho in voz.synthesize(texto,syn_config=config):fila.put(trecho)
        except Exception as e:fila.put(e)
        finally:fila.put(None)
    threading.Thread(target=produzir,daemon=True).start()
    primeiro=fila.get()
    if isinstance(primeiro,Exception):raise primeiro
    if primeiro is None:raise RuntimeError('Piper não gerou áudio.')
    formato=(primeiro.sample_rate,primeiro.sample_channels,primeiro.sample_width)
    if primeiro.sample_width!=2:raise RuntimeError('Formato de áudio Piper incompatível.')
    with sd.RawOutputStream(samplerate=primeiro.sample_rate,channels=primeiro.sample_channels,dtype='int16') as saida:
        trecho=primeiro
        while trecho is not None:
            if isinstance(trecho,Exception):raise trecho
            if (trecho.sample_rate,trecho.sample_channels,trecho.sample_width)!=formato:raise RuntimeError('Formato de áudio mudou durante a fala.')
            saida.write(trecho.audio_int16_bytes)
            trecho=fila.get()
