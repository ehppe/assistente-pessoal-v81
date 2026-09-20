# Instalador único do Neymar

O arquivo `Neymar-Setup-v81.exe` instala o assistente sem exigir Python ou comandos no PowerShell.

## O que o instalador faz

- instala o aplicativo somente para o usuário atual;
- inclui Python, bibliotecas, interface QML e reconhecimento Vosk;
- oferece atalhos no menu Iniciar e na área de trabalho;
- oferece inicialização automática com o Windows;
- abre a configuração do nome e perfil na primeira execução;
- preserva configurações, chaves protegidas, conversas e modelos ao atualizar.

As chaves de API nunca são incorporadas. Cada pessoa adiciona suas próprias chaves em **Configurações**.

## Gerar pelo GitHub

Abra **Actions → Gerar instalador do Windows → Run workflow**. Ao terminar, baixe o artefato `Neymar-Setup-v81`. Quando o fluxo for executado por uma tag, o instalador também é anexado automaticamente à Release.

## Gerar em um Windows local

Instale Python 3.12 e Inno Setup 6. Depois clique com o botão direito em `build_installer.ps1`, escolha **Executar com PowerShell** e aguarde. O resultado ficará em `dist\Neymar-Setup-v81.exe`.

## Limitações opcionais

- Ollama e os modelos de IA local continuam sendo instalações separadas por serem muito grandes.
- A temperatura da CPU ainda depende do Libre/Open Hardware Monitor disponível no computador.
- Voz Piper e Whisper local continuam opcionais para evitar um instalador excessivamente grande.
