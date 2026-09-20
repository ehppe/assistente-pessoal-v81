"""Ativação somente por palavra inicial confirmada, nunca por resultado parcial."""
import re

def palavra_inicial(texto,nome='neymar'):
    nome=(nome or 'neymar').strip()
    return nome.lower() if re.match(r'^\s*'+re.escape(nome)+r'\b',texto,re.I) else None

def confirmada(resultado,habilitada=True,nome='neymar'):
    if not habilitada:return False
    palavras=resultado.get('result') or []
    if not palavras:return False
    primeira=palavras[0]
    nome=(nome or 'neymar').strip().lower()
    return (primeira.get('word','').lower()==nome and
            isinstance(primeira.get('conf'),(float,int)) and primeira['conf']>=.85 and
            bool(palavra_inicial(resultado.get('text',''),nome)))


def verificar_nome_local(reconhecedor,pcm,nome='neymar'):
    """Verificação local sem prompt do nome; nunca usa API ou executa o pedido."""
    if not 6400 <= len(pcm) <= 8*32000:return False
    from array import array
    amostras=array('h',pcm)
    if sum(v*v for v in amostras)/len(amostras)<150**2:return False
    texto=reconhecedor.transcrever(pcm,ativacao=True).strip()
    # Aceite apenas o nome no início, sem aproximação por palavras parecidas.
    return bool(re.match(r'^\s*'+re.escape(nome or 'neymar')+r'\b',texto,re.I))


class TrechoChamada:
    """PCM mono 16 kHz: recorta chamada por pausas sem depender do texto Vosk."""
    def __init__(self):self.reset()

    def reset(self):
        self.pre=bytearray();self.audio=bytearray();self.silencio=0;self.voz=0

    def alimentar(self,pcm):
        from array import array
        amostras=array('h',pcm)
        if not amostras:return None
        tem_som=sum(v*v for v in amostras)/len(amostras)>=150**2
        if not self.audio:
            if not tem_som:
                self.pre.extend(pcm);self.pre=self.pre[-9600:];return None
            self.audio.extend(self.pre);self.pre.clear()
        self.audio.extend(pcm)
        if tem_som:self.voz+=len(pcm);self.silencio=0
        else:self.silencio+=len(pcm)
        if self.silencio>=22400 or len(self.audio)>=192000:
            trecho=bytes(self.audio) if self.voz>=6400 else None
            self.reset();return trecho
        return None


class DetectorChamada:
    """Alimenta Vosk continuamente; oferece trecho local quando há uma pausa."""
    def __init__(self,rec,nome='neymar'):
        self.rec=rec;self.nome=nome;self.rec.SetWords(True);self.trecho=TrechoChamada()

    def reset(self):
        self.rec.Reset();self.trecho.reset()

    def alimentar(self,pcm):
        import json
        if self.rec.AcceptWaveform(pcm):
            resultado=json.loads(self.rec.Result())
            self.rec.Reset()
            if confirmada(resultado,nome=self.nome):
                self.trecho.reset();return True,None
        return False,self.trecho.alimentar(pcm)
