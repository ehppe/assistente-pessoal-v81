"""Instala Vosk português, aceitando os layouts antigo e atual do modelo."""
from pathlib import Path
import tempfile
import urllib.request
import zipfile
import shutil
import time

URL='https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip'

def modelo_valido(pasta):
    pasta=Path(pasta)
    antigo=('final.mdl','HCLr.fst','Gr.fst','mfcc.conf')
    atual=('am/final.mdl','conf/mfcc.conf')
    return all((pasta/p).is_file() and (pasta/p).stat().st_size>0 for p in antigo) or (
        all((pasta/p).is_file() and (pasta/p).stat().st_size>0 for p in atual) and
        ((pasta/'graph'/'HCLG.fst').is_file() or ((pasta/'graph'/'HCLr.fst').is_file() and (pasta/'graph'/'Gr.fst').is_file())))

def instalar(base):
    pasta=Path(base)/'modelos';pasta.mkdir(exist_ok=True)
    destino=pasta/'vosk-pt'
    if modelo_valido(destino):
        print('Reconhecimento Vosk já instalado.');return destino
    # Recupera também um download que tenha sido descompactado com nome original.
    origem_existente=pasta/'vosk-model-small-pt-0.3'
    if modelo_valido(origem_existente):
        if destino.exists():destino.rename(pasta/('vosk-pt-backup-'+str(time.time_ns())))
        origem_existente.rename(destino);return destino
    print('Baixando reconhecimento local de voz em português…')
    # Pasta temporária no mesmo volume para permitir mover sem cópia parcial.
    with tempfile.TemporaryDirectory(prefix='neymar-vosk-',dir=pasta) as t:
        arq=Path(t)/'modelo.zip'
        urllib.request.urlretrieve(URL,arq)
        with zipfile.ZipFile(arq) as z:
            for item in z.infolist():
                p=(Path(t)/item.filename).resolve()
                if not p.is_relative_to(Path(t).resolve()):raise ValueError('Caminho inválido no download')
            if z.testzip() is not None:raise ValueError('Download corrompido. Tente novamente.')
            z.extractall(t)
        origem=Path(t)/'vosk-model-small-pt-0.3'
        if not modelo_valido(origem):raise ValueError('Download não contém um modelo Vosk válido.')
        if destino.exists():destino.rename(pasta/('vosk-pt-backup-'+str(time.time_ns())))
        shutil.move(str(origem),destino)
    print('Reconhecimento local instalado com sucesso.')
    return destino

if __name__=='__main__':instalar(Path(__file__).resolve().parent)
