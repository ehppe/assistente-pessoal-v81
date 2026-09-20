# Assistente pessoal 81 para Windows

Assistente de voz com conversa local ou online, reconhecimento de voz, lembretes, futebol, previsão do tempo, controle conservador do Windows, painel privado pelo Tailscale e modo de jogo reversível.

## Instalação

### Instalação recomendada

Baixe `Neymar-Setup-v81.exe` na página de Releases, execute-o e siga as telas. O instalador único já inclui o programa, a interface e o reconhecimento básico; não exige Python nem comandos no PowerShell.

### Instalação manual pelo ZIP

1. Extraia todo o ZIP para uma pasta comum, fora de `Arquivos de Programas`.
2. Execute `1 - Instalar Assistente.bat`.
3. Preencha o perfil inicial.
4. Execute `Iniciar Assistente.bat`.

O instalador principal prepara Python, ambiente virtual, interface Qt, dependências, reconhecimento básico, IA local opcional e inicialização automática. Os instaladores numerados restantes servem para reparo ou componentes opcionais.

As instruções para gerar o executável estão em `INSTALADOR-UNICO.md`.

## Privacidade

- Recursos locais incluem Ollama, Whisper, Vosk, Piper e voz do Windows.
- Serviços online só são usados quando configurados ou solicitados.
- Chaves de API ficam protegidas pelo DPAPI e não são gravadas no `config.json`.
- O histórico no painel do telefone vem desativado por padrão.
- IDs de Discord e nome do usuário não fazem parte do código distribuído.
- `Diagnóstico seguro.bat` gera um relatório sem chaves nem conversas.

## Modo de jogo

Fecha apenas janelas de aplicativos explicitamente selecionados e não encerra processos à força. Alterações opcionais de energia, Game Bar e indexação são registradas antes da mudança e restauradas ao sair quando possível. Aplicativos fechados não são reabertos automaticamente.

## Configuração

Abra **Configurações** na janela ou na bandeja. Também é possível executar `Configurar meu perfil.bat`. Campos de chave vazios preservam as chaves existentes.

## Testes

```sh
python -m pip install -r requirements-test.txt
python -m compileall -q .
python -m unittest discover -s tests -v
```

A versão 81 contém 156 testes automatizados. Eles simulam rede, áudio, empacotamento e recursos do Windows; sensores, microfone, DPAPI, drivers e fechamento real de janelas ainda precisam ser validados no computador Windows.

## Nome e agenda pessoal

O nome do assistente pode ser alterado em **Configurações > Sistema** ou por comando: “mude seu nome para Jarvis”. Reinicie depois para recarregar a chamada por voz. Não é preciso editar nenhum código.

Exemplos da agenda:

- “Me lembre amanhã às 15h de ligar para o dentista.”
- “Me lembre todo dia às 9h de tomar o remédio.”
- “Me lembre toda sexta às 18h de encerrar o trabalho.”
- “Quais são meus lembretes?”
- “Cancelar lembrete do dentista.”
- “Adiar lembrete do remédio por 20 minutos.”
- “Cancelar todos os lembretes.”

Novos lembretes continuam exigindo confirmação antes de serem gravados.

## Atualização

Feche o assistente, faça backup e copie os arquivos da v81 sobre a instalação. Preserve `config.json`, `dados`, `modelos`, `vozes` e `.venv`. Execute novamente o instalador principal para atualizar dependências. Consulte `CHANGELOG.md` para as mudanças.
