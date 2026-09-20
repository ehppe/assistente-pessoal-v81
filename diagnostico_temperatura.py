"""Diagnóstico simples dos sensores usados pela Central Neymar."""
from util import temperatura_cpu, temperatura_gpu


def _mostrar(rotulo, valor, fonte):
    if valor is not None:
        print(f'{rotulo}: {valor:.1f} °C')
        print(f'Origem: {fonte}\n')
    else:
        print(f'{rotulo}: sensor não disponibilizado ao Windows.\n')


def main():
    print('\n=== DIAGNOSTICO DE TEMPERATURA ===\n')
    cpu_valor, cpu_fonte = temperatura_cpu()
    gpu_valor, gpu_fonte = temperatura_gpu()
    _mostrar('CPU', cpu_valor, cpu_fonte)
    _mostrar('GPU', gpu_valor, gpu_fonte)
    if cpu_valor is not None or gpu_valor is not None:
        print('A Central Neymar deve exibir essas mesmas leituras.')
    else:
        print('Deixe o Libre Hardware Monitor aberto e execute-o como administrador.')
        print('Depois feche e abra novamente a Central Neymar.')
        print('Se o assistente também estiver como administrador, os dois programas')
        print('terão o mesmo nível de permissão para acessar o WMI.')


if __name__ == '__main__':
    main()
