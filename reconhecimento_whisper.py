"""Whisper local em português, com perfis de busca e medições opcionais."""
from pathlib import Path
import threading
from desempenho import medir

class Reconhecedor:
    def __init__(self,base):
        self.base=Path(base)
        self.pasta=self.base/'modelos'/'whisper-small'
        self.modelo=None
        self.perfil='precisao'
        self.diagnostico=False
        self.nome_ativacao='Neymar'
        self._lock=threading.Lock()

    def transcrever(self,pcm,ativacao=False):
        if not (self.pasta/'model.bin').is_file():
            raise RuntimeError('Instale o reconhecimento pelo arquivo 5 - Instalar reconhecimento Whisper.bat.')
        if len(pcm)%2 or len(pcm)>30*32000:
            raise RuntimeError('Áudio inválido ou maior que 30 segundos.')
        if len(pcm)<6400:return ''
        try:
            import numpy as np
            from faster_whisper import WhisperModel
        except ImportError:raise RuntimeError('Execute 5 - Instalar reconhecimento Whisper.bat para instalar os componentes.') from None
        perfil=self.perfil if self.perfil in ('precisao','rapido') else 'precisao'
        with self._lock:
            if self.modelo is None:
                with medir(self.base,'whisper_carga',self.diagnostico):
                    self.modelo=WhisperModel(str(self.pasta),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
            audio=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768.0
            etapa='whisper_ativacao' if ativacao else 'whisper_'+perfil
            with medir(self.base,etapa,self.diagnostico):
                opcoes=dict(language='pt',task='transcribe',beam_size=1 if perfil=='rapido' and not ativacao else 5,
                    temperature=0.0,best_of=1,vad_filter=not ativacao,condition_on_previous_text=False,
                    initial_prompt=None if ativacao else 'Conversa em português brasileiro. '+self.nome_ativacao+', memória RAM, SSD, computador, Discord, Steam, CS2.')
                if not ativacao:
                    opcoes['vad_parameters']={'min_silence_duration_ms':500,'speech_pad_ms':300}
                segmentos,_=self.modelo.transcribe(audio,**opcoes)
                # Consumir o gerador dentro da medição e do lock: a inferência é preguiçosa.
                return ' '.join(s.text.strip() for s in segmentos if s.text.strip() and s.no_speech_prob<.6 and (not ativacao or getattr(s,'avg_logprob',-99)>-1.0)).strip()
