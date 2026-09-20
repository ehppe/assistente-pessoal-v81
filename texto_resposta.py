"""Separa resposta final e prepara texto simples para leitura em voz alta."""
import re

def resposta_final(texto):
    if not isinstance(texto,str):return ''
    texto=re.sub(r'<think\b[^>]*>.*?</think\s*>','',texto,flags=re.S|re.I)
    texto=re.sub(r'<think\b[^>]*>.*$','',texto,flags=re.S|re.I)
    if '</think>' in texto.lower():texto=re.split(r'</think\s*>',texto,flags=re.I)[-1]
    texto=texto.strip()
    if re.match(r"(?i)^(?:okay,?\s+the user|the user (?:wants|asked)|let me (?:think|start))",texto):return ''
    return texto

def texto_para_fala(texto):
    texto=resposta_final(texto)
    # Avisos como "[NVIDIA falhou... Resposta pelo Ollama local.]" ajudam a
    # entender o que aconteceu no texto da conversa, mas soam estranhos lidos
    # em voz alta com os colchetes; falamos só a resposta em si.
    texto=re.sub(r'^\[[^\]]*\]\s*','',texto)
    texto=re.sub(r'```.*?```',' O código está na conversa. ',texto,flags=re.S)
    texto=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',texto)
    texto=re.sub(r'(?m)^\s*(?:#{1,6}\s+|[-*•]\s+)', '',texto)
    texto=texto.replace('**','').replace('`','').replace('…','.')
    return re.sub(r'\s+',' ',texto).strip()

def contexto_limpo(contexto):
    resultado=[]
    for item in contexto:
        if item.get('role') not in ('user','assistant'):continue
        texto=resposta_final(item.get('content',''))
        # Exclui do contexto respostas antigas que narravam a preparação em inglês.
        if item['role']=='assistant' and re.match(r"(?i)^(?:okay,?\s+the user|the user (?:wants|asked)|let me (?:think|start))",texto):continue
        if texto:resultado.append({'role':item['role'],'content':texto})
    return resultado
