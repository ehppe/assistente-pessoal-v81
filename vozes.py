"""Catálogo local de vozes Piper; arquivos de modelos ficam fora do pacote."""
from pathlib import Path

VOZES = {
    'pt_BR-faber-medium': 'Faber — Português BR',
    'pt_BR-cadu-medium': 'Cadu — Português BR',
    'pt_BR-jeff-medium': 'Jeff — Português BR',
    'pt_BR-edresson-low': 'Edresson — Português BR (leve)',
}

def arquivos_voz(base, identificador):
    if identificador not in VOZES:
        raise ValueError('Escolha uma voz da lista.')
    modelo = Path(base)/'modelos'/'piper'/(identificador+'.onnx')
    return modelo, modelo.with_suffix('.onnx.json')

def instalada(base, identificador):
    return all(p.is_file() and p.stat().st_size > 0 for p in arquivos_voz(base, identificador))
