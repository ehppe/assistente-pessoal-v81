"""Funções pequenas usadas por vários módulos do Neymar."""
import contextlib
import io
import math
import threading
import unicodedata
import winsound
from collections import deque

from PIL import Image, ImageDraw, ImageFilter

# Histórico curto (em memória, não persiste entre execuções) das últimas
# leituras de temperatura, usado para desenhar o mini-gráfico do painel de
# monitoramento. Guardado aqui, e não em cada interface, para que a tela
# clássica e a tela Qt mostrem exatamente o mesmo histórico.
_HISTORICO_TEMP = {'cpu': deque(maxlen=40), 'gpu': deque(maxlen=40)}


def nivel_reativo(bruto):
    """Normaliza o nível de microfone (RMS bruto, em geral ~0.00–0.20 numa
    fala comum) para uma faixa visível de 0 a 1 — usada tanto no pulso do
    holograma da tela clássica quanto na amplitude das ondas na tela Qt, para
    as duas reagirem do mesmo jeito ao volume da voz."""
    try:
        return max(0.0, min(1.0, float(bruto) * 6))
    except (TypeError, ValueError):
        return 0.0


def norm(s):
    """Remove acentos, coloca em minúsculas e tira espaços das pontas."""
    s = unicodedata.normalize('NFD', s.lower())
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').strip()


def leitura_sistema():
    """CPU, memória RAM, disco e temperatura — usado pelo painel "Monitor do
    sistema". CPU e GPU são lidas e mostradas separadamente, cada uma com sua
    própria fonte e um histórico curto para o mini-gráfico. Se nenhuma fonte
    responder, o valor volta None e a tela mostra "indisponível" em vez de
    inventar um número."""
    import psutil
    import os
    import platform
    import socket
    import time
    dados = {'cpu': None, 'ram': None, 'ram_usada': None, 'ram_total': None,
        'disco': None, 'disco_livre': None,
        'temp_cpu': None, 'temp_cpu_fonte': '', 'temp_cpu_historico': [],
        'temp_gpu': None, 'temp_gpu_fonte': '', 'temp_gpu_historico': [],
        'computador': socket.gethostname(), 'windows': platform.platform(),
        'arquitetura': platform.machine(), 'processador': platform.processor() or platform.machine(),
        'nucleos': psutil.cpu_count(logical=False), 'logicos': psutil.cpu_count(logical=True),
        'tempo_ligado': ''}
    try:
        dados['cpu'] = psutil.cpu_percent(interval=None)
    except Exception:
        pass
    try:
        memoria = psutil.virtual_memory()
        dados['ram'] = memoria.percent
        dados['ram_usada'] = memoria.used / (1024 ** 3)
        dados['ram_total'] = memoria.total / (1024 ** 3)
    except Exception:
        pass
    try:
        raiz = os.environ.get('SystemDrive', 'C:') + '\\' if platform.system() == 'Windows' else os.sep
        disco = psutil.disk_usage(raiz)
        dados['disco'] = disco.percent
        dados['disco_livre'] = disco.free / (1024 ** 3)
    except Exception:
        pass
    try:
        dados['temp_cpu'], dados['temp_cpu_fonte'] = temperatura_cpu()
    except Exception:
        pass
    try:
        dados['temp_gpu'], dados['temp_gpu_fonte'] = temperatura_gpu()
    except Exception:
        pass
    if dados['temp_cpu'] is not None:
        _HISTORICO_TEMP['cpu'].append(dados['temp_cpu'])
    if dados['temp_gpu'] is not None:
        _HISTORICO_TEMP['gpu'].append(dados['temp_gpu'])
    dados['temp_cpu_historico'] = list(_HISTORICO_TEMP['cpu'])
    dados['temp_gpu_historico'] = list(_HISTORICO_TEMP['gpu'])
    try:
        segundos = max(0, int(time.time() - psutil.boot_time()))
        dias, resto = divmod(segundos, 86400); horas, resto = divmod(resto, 3600)
        dados['tempo_ligado'] = (f'{dias}d ' if dias else '') + f'{horas}h {resto // 60:02d}min'
    except Exception:
        pass
    return dados


def temperatura_hardware():
    """Mantido por compatibilidade (diagnóstico da linha de comando): devolve
    só a temperatura da CPU, igual à função antiga de nome único."""
    return temperatura_cpu()


def temperatura_cpu():
    """CPU via Libre/Open Hardware Monitor (WMI); se indisponível, tenta os
    sensores que o próprio psutil conseguir enxergar."""
    cpu, fonte = temperatura_wmi(detalhes=True)
    if cpu is not None:
        return cpu, fonte
    # Linux e algumas ferramentas de monitoramento expõem sensores pelo
    # psutil. No Windows normalmente a lista fica vazia, mas a tentativa é
    # barata e amplia a compatibilidade sem instalar outra dependência.
    try:
        import psutil
        grupos = psutil.sensors_temperatures(fahrenheit=False)
        candidatos = []
        for grupo, sensores in grupos.items():
            for sensor in sensores:
                texto = f'{grupo} {getattr(sensor, "label", "")}'.lower()
                valor = float(sensor.current)
                if 0 < valor < 130:
                    prioridade = 0 if any(p in texto for p in ('package','tctl','tdie','cpu')) else 1
                    candidatos.append((prioridade, -valor, valor))
        if candidatos:
            return sorted(candidatos)[0][2], 'CPU · sensor do sistema'
    except (AttributeError, ValueError, TypeError):
        pass
    return None, ''


def temperatura_gpu():
    """GPU via Libre/Open Hardware Monitor (WMI); se indisponível, tenta o
    nvidia-smi (só existe com placas NVIDIA e os drivers instalados)."""
    gpu, fonte = temperatura_wmi_gpu()
    if gpu is not None:
        return gpu, fonte
    try:
        import subprocess
        import os
        comandos = ['nvidia-smi']
        pasta = os.environ.get('ProgramW6432') or os.environ.get('ProgramFiles')
        if pasta:
            comandos.append(os.path.join(pasta, 'NVIDIA Corporation', 'NVSMI', 'nvidia-smi.exe'))
        for comando in comandos:
            try:
                r = subprocess.run([comando, '--query-gpu=temperature.gpu', '--format=csv,noheader,nounits'],
                    capture_output=True, text=True, timeout=2, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if r.returncode == 0:
                    valor = float(r.stdout.strip().splitlines()[0])
                    if 0 < valor < 130:return valor, 'GPU · NVIDIA (nvidia-smi)'
            except OSError:
                continue
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        pass
    return None, ''


_NAMESPACES_SENSOR = ('LibreHardwareMonitor', 'OpenHardwareMonitor')
_PALAVRAS_CPU_PRINCIPAL = ('package', 'tctl', 'average', 'total', 'die')
_PALAVRAS_GPU_PRINCIPAL = ('core', 'hot spot', 'hotspot', 'gpu')


def _sensores_temperatura_wmi(namespace):
    """Consulta bruta dos sensores de temperatura de um namespace (Libre ou
    Open Hardware Monitor); devolve a lista de linhas ou [] se indisponível."""
    import win32com.client
    conector = win32com.client.GetObject('winmgmts:\\\\.\\root\\' + namespace)
    return list(conector.ExecQuery(
        "SELECT Name, Identifier, Parent, Value FROM Sensor WHERE SensorType='Temperature'"))


def temperatura_wmi(detalhes=False):
    """Lê sensores identificados de CPU via Libre/Open Hardware Monitor.
    Zonas térmicas ACPI não identificam a CPU e não são utilizadas."""
    resultado = (None, '') if detalhes else None
    try:
        import win32com.client  # noqa: F401 — só para confirmar que existe
    except ImportError:
        return resultado
    with com_thread():
        for namespace in _NAMESPACES_SENSOR:
            try:
                # O Identifier é mais confiável que Name: em algumas versões
                # do Libre Hardware Monitor o nome é só "Package" ou
                # "Core Max", enquanto o caminho contém /intelcpu/ ou /amdcpu/.
                sensores = _sensores_temperatura_wmi(namespace)
            except Exception:
                continue
            if not sensores:
                continue
            candidatos = []
            for sensor in sensores:
                nome = str(getattr(sensor, 'Name', '') or '')
                identificador = str(getattr(sensor, 'Identifier', '') or '')
                pai = str(getattr(sensor, 'Parent', '') or '')
                texto = f'{nome} {identificador} {pai}'.lower()
                if not any(p in texto for p in ('cpu', 'intelcpu', 'amdcpu')):
                    continue
                try: valor = float(sensor.Value)
                except (TypeError, ValueError): continue
                if not 0 < valor < 130: continue
                principal = any(p in texto for p in _PALAVRAS_CPU_PRINCIPAL + ('core max',))
                candidatos.append((0 if principal else 1, -valor, valor, nome))
            if candidatos:
                _, _, valor, nome = sorted(candidatos)[0]
                fonte = ('Libre Hardware Monitor' if namespace == 'LibreHardwareMonitor'
                         else 'Open Hardware Monitor')
                resposta = (round(valor, 1), f'CPU · {fonte} · {nome}')
                return resposta if detalhes else resposta[0]
    return resultado


def temperatura_wmi_gpu():
    """Mesma ideia de temperatura_wmi(), mas filtrando os sensores da GPU
    (nvidiagpu/atigpu/amdgpu no Identifier, "gpu" no nome) em vez da CPU."""
    resultado = (None, '')
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return resultado
    with com_thread():
        for namespace in _NAMESPACES_SENSOR:
            try:
                sensores = _sensores_temperatura_wmi(namespace)
            except Exception:
                continue
            if not sensores:
                continue
            candidatos = []
            for sensor in sensores:
                nome = str(getattr(sensor, 'Name', '') or '')
                identificador = str(getattr(sensor, 'Identifier', '') or '')
                pai = str(getattr(sensor, 'Parent', '') or '')
                texto = f'{nome} {identificador} {pai}'.lower()
                if not any(p in texto for p in ('gpu', 'nvidiagpu', 'atigpu', 'amdgpu')):
                    continue
                try: valor = float(sensor.Value)
                except (TypeError, ValueError): continue
                if not 0 < valor < 130: continue
                principal = any(p in texto for p in _PALAVRAS_GPU_PRINCIPAL)
                candidatos.append((0 if principal else 1, -valor, valor, nome))
            if candidatos:
                _, _, valor, nome = sorted(candidatos)[0]
                fonte = ('Libre Hardware Monitor' if namespace == 'LibreHardwareMonitor'
                         else 'Open Hardware Monitor')
                return round(valor, 1), f'GPU · {fonte} · {nome}'
    return resultado


def bipe(frequencia=880, duracao_ms=110):
    """Toca um bipe curto em segundo plano, sem travar a interface."""
    def tocar():
        try:
            winsound.Beep(frequencia, duracao_ms)
        except Exception:
            pass
    threading.Thread(target=tocar, daemon=True).start()


@contextlib.contextmanager
def com_thread():
    """Inicializa o COM do Windows nesta thread antes de usar pywinauto ou
    win32com, e libera ao final. Chamar código baseado em COM (automação de
    janelas, Windows Search) sem isso pode derrubar o processo inteiro, em
    vez de gerar um erro comum do Python — por isso todo lugar que usa COM
    passa por aqui primeiro."""
    try:
        import pythoncom
    except ImportError:
        yield
        return
    iniciado = False
    try:
        pythoncom.CoInitialize()
        iniciado = True
    except Exception:
        pass
    try:
        yield
    finally:
        if iniciado:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def _paralelo(tamanho, raio, cor, fracao_altura, largura, alpha=140):
    """Uma linha de latitude do globo: um círculo horizontal do "planeta",
    visto em perspectiva (mais estreito perto do topo/base, largo no
    equador) — como as linhas horizontais de um globo giroscópico."""
    cx = cy = tamanho / 2
    fracao_altura = max(-0.97, min(0.97, fracao_altura))
    y = cy + raio * fracao_altura
    raio_local = raio * math.sqrt(max(0.0, 1 - fracao_altura ** 2))
    achatamento = 0.30
    altura = max(1.2, raio_local * achatamento)
    camada = Image.new('RGBA', (tamanho, tamanho), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    d.ellipse((cx - raio_local, y - altura, cx + raio_local, y + altura), outline=cor + (alpha,), width=largura)
    return camada


def _meridiano(tamanho, raio, cor, fase_graus, largura, alpha=160):
    """Uma linha de longitude (círculo máximo vertical) vista girando em
    torno do eixo do globo: fica larga de frente e vira uma linha fina de
    perfil, como os meridianos de um globo terrestre em rotação."""
    cx = cy = tamanho / 2
    fator = abs(math.cos(math.radians(fase_graus)))
    largura_elipse = max(1.0, raio * fator)
    alpha_efetivo = int(alpha * (0.35 + 0.65 * fator))
    camada = Image.new('RGBA', (tamanho, tamanho), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    d.ellipse((cx - largura_elipse, cy - raio, cx + largura_elipse, cy + raio), outline=cor + (alpha_efetivo,), width=largura)
    return camada


def gerar_nucleo(tamanho=220, cor=(64, 207, 255), angulo=0.0, pulso=0.5):
    """Desenha um quadro do núcleo holográfico como um globo giroscópico em
    pseudo-3D (linhas de latitude e longitude girando em torno de um núcleo
    brilhante, com poeira de estrelas ao redor) — no estilo de um HUD de IA
    genérico, sem copiar nenhum logo ou personagem específico."""
    img = Image.new('RGBA', (tamanho, tamanho), (0, 0, 0, 0))
    cx = cy = tamanho / 2
    raio = tamanho * 0.40

    # Brilho volumétrico atrás de tudo, para dar sensação de profundidade
    glow = Image.new('RGBA', (tamanho, tamanho), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    raio_glow = tamanho * (0.22 + pulso * 0.03)
    dg.ellipse((cx - raio_glow, cy - raio_glow, cx + raio_glow, cy + raio_glow), fill=cor + (85,))
    glow = glow.filter(ImageFilter.GaussianBlur(tamanho * 0.08))
    img.alpha_composite(glow)

    largura_linha = max(1, int(tamanho * 0.004))

    # Poeira de estrelas/partículas ao redor do globo (posições fixas por
    # índice, para não "tremer" de um quadro para o outro; só o brilho pulsa)
    d = ImageDraw.Draw(img)
    for i in range(26):
        a = math.radians(i * 13.85)
        r = raio * (1.18 + 0.22 * ((i * 37) % 9) / 9)
        px, py = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.62
        t = (i * 53 + int(angulo)) % 100 / 100
        pr = 0.6 + 1.1 * abs(math.sin(t * math.pi + pulso))
        d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=cor + (int(90 + 100 * t),))

    # Linhas de latitude (paralelos), fixas — dão o "corpo" esférico do globo
    for fracao in (-0.62, -0.30, 0.0, 0.30, 0.62):
        camada = _paralelo(tamanho, raio, cor, fracao, largura_linha)
        img.alpha_composite(camada)

    # Contorno externo do globo
    d.ellipse((cx - raio, cy - raio, cx + raio, cy + raio), outline=cor + (110,), width=largura_linha)

    # Linhas de longitude (meridianos), girando com o ângulo da animação
    for i in range(6):
        fase = angulo + i * 30
        camada = _meridiano(tamanho, raio, cor, fase, largura_linha)
        img.alpha_composite(camada)

    # Núcleo brilhante no centro: várias camadas concêntricas simulam
    # sombreado, mais um brilho especular deslocado, como um reator de vidro.
    nucleo_raio = tamanho * (0.085 + pulso * 0.025)
    passos = 12
    for i in range(passos, 0, -1):
        fator = i / passos
        r = nucleo_raio * fator
        alpha = int(80 + 175 * (1 - fator) ** 0.6)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=cor + (alpha,))
    raio_brilho = nucleo_raio * 0.32
    bx, by = cx - nucleo_raio * 0.35, cy - nucleo_raio * 0.4
    cor_brilho = tuple(min(255, int(c * .5 + 255 * .5)) for c in cor)
    d.ellipse((bx - raio_brilho, by - raio_brilho, bx + raio_brilho, by + raio_brilho), fill=cor_brilho + (150,))

    return img


def nucleo_png_bytes(tamanho=512, cor=(64, 207, 255)):
    """Gera um PNG estático do núcleo (usado como ícone do painel do iPhone)."""
    img = gerar_nucleo(tamanho, cor, angulo=25, pulso=1.0)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()
