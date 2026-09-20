from pathlib import Path
from faster_whisper.utils import download_model
from faster_whisper import WhisperModel

if __name__=='__main__':
    pasta=Path(__file__).resolve().parent/'modelos'/'whisper-small'
    print('Baixando Whisper small multilíngue. Aguarde; o download tem centenas de MB.')
    download_model('small',output_dir=str(pasta))
    WhisperModel(str(pasta),device='cpu',compute_type='int8',local_files_only=True)
    print('Modelo Whisper instalado e carregado com sucesso.')
