"""Chave NVIDIA protegida com DPAPI do usuário Windows; nunca no config.json."""
from pathlib import Path

def caminho(base,provedor='nvidia'):
    if provedor not in ('nvidia','groq','futebol','gemini','brave'):raise ValueError('Provedor inválido.')
    return Path(base)/'dados'/(provedor+'-chave.dpapi')

def salvar_chave(base,chave,provedor='nvidia'):
    chave=chave.strip()
    if not chave or any(c.isspace() for c in chave):raise ValueError('Chave inválida.')
    import win32crypt
    protegido=win32crypt.CryptProtectData(chave.encode('utf-8'),'Neymar '+provedor.upper(),None,None,None,1)
    p=caminho(base,provedor);p.parent.mkdir(exist_ok=True)
    temp=p.with_suffix('.tmp');temp.write_bytes(protegido);temp.replace(p)

def ler_chave(base,provedor='nvidia'):
    p=caminho(base,provedor)
    if not p.exists():raise RuntimeError('Adicione sua chave '+provedor.upper()+' nas Configurações e salve.')
    try:
        import win32crypt
        return win32crypt.CryptUnprotectData(p.read_bytes(),None,None,None,1)[1].decode('utf-8')
    except Exception:raise RuntimeError('Não consegui abrir a chave '+provedor.upper()+'. Cole a chave novamente nas Configurações deste Windows.') from None

def apagar_chave(base,provedor='nvidia'):caminho(base,provedor).unlink(missing_ok=True)
