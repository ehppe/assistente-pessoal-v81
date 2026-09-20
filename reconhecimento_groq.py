"""Envia somente o trecho ativado, como WAV em memória, para transcrição em português."""
import io
import wave
import requests
from credenciais import ler_chave

URL='https://api.groq.com/openai/v1/audio/transcriptions'

def verificar_status(status):
    erros={401:'Chave Groq inválida ou expirada.',403:'Conta Groq sem permissão.',
           429:'Limite Groq atingido. Aguarde ou selecione whisper local.',
           402:'Groq recusou por cota/cobrança. Confira sua conta; o Neymar não compra créditos.'}
    if status!=200:raise RuntimeError(erros.get(status,'Groq indisponível (HTTP '+str(status)+').'))

def testar_chave(base):
    try:
        r=requests.get('https://api.groq.com/openai/v1/models',headers={'Authorization':'Bearer '+ler_chave(base,'groq')},timeout=(5,15),allow_redirects=False)
        verificar_status(r.status_code)
        modelos=[m.get('id') for m in r.json().get('data',[])]
        if 'whisper-large-v3-turbo' not in modelos:raise RuntimeError('Chave aceita, mas Whisper Turbo não apareceu na conta Groq.')
        return 'Chave Groq aceita. Agora use Ouvir pedido para testar a transcrição real.'
    except requests.RequestException:raise RuntimeError('Não consegui conectar à Groq. Confira a internet.') from None
    except (ValueError,TypeError,AttributeError):raise RuntimeError('Groq retornou dados inválidos.') from None

def transcrever(base,pcm):
    if len(pcm)<6400:return ''
    if len(pcm)>30*32000 or len(pcm)%2:raise RuntimeError('Áudio inválido ou maior que 30 segundos.')
    chave=ler_chave(base,'groq')
    arq=io.BytesIO()
    with wave.open(arq,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(pcm)
    try:
        r=requests.post(URL,headers={'Authorization':'Bearer '+chave},
            files={'file':('pedido.wav',arq.getvalue(),'audio/wav')},
            data={'model':'whisper-large-v3-turbo','language':'pt','temperature':'0',
                  'response_format':'verbose_json','prompt':'Neymar, memória RAM, SSD, Discord, Steam, CS2.'},
            timeout=(5,30),allow_redirects=False)
        verificar_status(r.status_code)
        dados=r.json();texto=dados.get('text','')
        if not isinstance(texto,str):raise ValueError()
        segmentos=dados.get('segments',[])
        if segmentos and all(s.get('no_speech_prob',0)>=0.6 for s in segmentos):return ''
        return texto.strip()
    except requests.Timeout:raise RuntimeError('Groq demorou para transcrever. Tente novamente ou use whisper local.') from None
    except requests.RequestException:raise RuntimeError('Não consegui conectar à Groq. Confira a internet.') from None
    except (ValueError,TypeError,AttributeError):raise RuntimeError('Groq retornou transcrição inválida.') from None
