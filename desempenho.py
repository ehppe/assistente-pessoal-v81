"""Medições locais limitadas; nunca grava falas, chaves ou respostas."""
import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from statistics import median

_lock = threading.Lock()
ETAPAS = {'whisper_carga', 'whisper_precisao', 'whisper_rapido',
          'whisper_ativacao', 'groq', 'ia_ollama', 'ia_nvidia', 'ia_total', 'ia_gemini'}

@contextmanager
def medir(base, etapa, habilitado=False):
    inicio = time.perf_counter()
    ok = False
    try:
        yield
        ok = True
    finally:
        if habilitado and etapa in ETAPAS:
            try:
                registro = {'etapa': etapa, 'ms': round((time.perf_counter()-inicio)*1000, 1), 'ok': ok}
                caminho = Path(base)/'dados'/'desempenho.jsonl'
                with _lock:
                    caminho.parent.mkdir(parents=True, exist_ok=True)
                    if caminho.exists() and caminho.stat().st_size > 262144:
                        caminho.replace(caminho.with_suffix('.anterior.jsonl'))
                    with caminho.open('a', encoding='utf-8') as arq:
                        arq.write(json.dumps(registro)+'\n')
            except (OSError, TypeError, ValueError):
                pass  # Diagnóstico não pode impedir um pedido.

def resumo(base):
    caminho = Path(base)/'dados'/'desempenho.jsonl'
    try:
        with _lock:
            linhas = caminho.read_text(encoding='utf-8').splitlines()[-200:]
    except OSError:
        return 'Sem medições. Marque Registrar tempos locais, salve e faça alguns pedidos.'
    grupos = {}
    for linha in linhas:
        try:
            r = json.loads(linha)
            if r['etapa'] in ETAPAS and isinstance(r['ms'], (int, float)):
                grupos.setdefault(r['etapa'], []).append(r)
        except (ValueError, KeyError, TypeError):
            continue
    saida = ['Últimas 200 medições (etapas podem se sobrepor):']
    for etapa, registros in sorted(grupos.items()):
        bons = [r['ms'] for r in registros if r.get('ok') is True]
        falhas = len(registros)-len(bons)
        texto = f'{etapa}: {len(bons)} concluídas, {falhas} falhas'
        if bons:
            texto += f'; mediana {median(bons)/1000:.2f}s; última {bons[-1]/1000:.2f}s'
        saida.append(texto)
    saida.append('Não inclui espera pelo fim da fala, fila, reprodução da voz ou tempo total percebido.')
    return '\n'.join(saida)


def medir_ia(etapa):
    from functools import wraps
    def decorar(funcao):
        @wraps(funcao)
        def executar(base, config, *args, **kwargs):
            with medir(base, etapa, config.get('diagnostico_tempos', False)):
                return funcao(base, config, *args, **kwargs)
        return executar
    return decorar
