# Solução de problemas

Comece sempre por:

```bash
hefesto-dualsense4unix doctor          # confere a instalação; --fix corrige o que puder
journalctl --user -u hefesto-dualsense4unix.service -n 100 --no-pager
```

Para o que não estiver aqui, abra uma
[issue](https://github.com/Hefesto-Team/hefesto-dualsense4unix/issues) com o
[diagnóstico geral](#diagnóstico-geral).

## O controle não aparece pelo cabo

`hefesto-dualsense4unix status` mostra `connected: False` com o cabo ligado.

```bash
lsusb | grep -i 054c                   # o DualSense é 054c:0ce6 (o Edge, 054c:0df2)
ls -l /dev/hidraw*
```

- **Faltam as regras udev**: reaplique ([instalacao.md](instalacao.md), «Reaplicar
  as regras udev») e desconecte e reconecte o controle.
- **Sem `systemd-logind`**: a permissão da sessão depende dele
  ([ADR-009](../adr/009-systemd-logind-scope.md)).
- **O controle conecta e desconecta em laço** (`dmesg` mostra `error -71` ou
  `device descriptor read/64`): é o áudio USB do controle se enumerando sob
  carga. O instalador já põe no boot o `usbcore.quirks` que resolve isso sem
  perder o microfone e o fone, e ele vale depois de reiniciar. A alternativa é
  desligar o áudio USB do controle:
  `sudo bash scripts/install_udev.sh --disable-usb-audio` (sem microfone e fone
  pelo cabo). Use uma das duas, nunca as duas.

## O controle não aparece pelo Bluetooth

`bluetoothctl info <endereço>` diz `Connected: yes` e o Hefesto não vê o controle.

- Reinicie o serviço: `systemctl --user restart hefesto-dualsense4unix.service`.
- Pareie de novo, pela aba Conexões ou pelo `bluetoothctl`
  ([bluetooth.md](bluetooth.md)).
- Com o controle no cabo e no Bluetooth ao mesmo tempo, desconecte o cabo.

O pareamento que some sozinho está em «Quando o pareamento some», em
[bluetooth.md](bluetooth.md).

## O ícone da bandeja não aparece

- **GNOME**: ligue a extensão de indicadores e saia e entre na sessão de novo:

  ```bash
  gnome-extensions enable ubuntu-appindicators@ubuntu.com         # Ubuntu, Pop!_OS
  gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com  # as outras
  ```

  O instalador liga a primeira sozinho.
- **COSMIC**: ver [cosmic.md](cosmic.md).

## O serviço não sobe

`systemctl --user status hefesto-dualsense4unix.service` mostra `failed`.

```bash
systemctl --user reset-failed hefesto-dualsense4unix.service
systemctl --user restart hefesto-dualsense4unix.service
```

Se o diário falar de outra instância ou de um socket preso, apague os restos e
suba de novo:

```bash
rm -f "$XDG_RUNTIME_DIR"/hefesto-dualsense4unix/*.pid "$XDG_RUNTIME_DIR"/hefesto-dualsense4unix/*.sock
systemctl --user restart hefesto-dualsense4unix.service
```

## O perfil do jogo não entra

O perfil existe e o jogo abre com outro.

1. **Um `process_name` na regra.** Os campos da regra precisam casar todos, e
   com o Proton o nome do processo é o do Wine, nunca o `.exe` do jogo. Tire o
   `process_name` do arquivo do perfil e deixe a classe da janela
   (`steam_app_<número>`), ou refaça a regra com o botão «Detectar» da aba
   Perfis, com o jogo aberto ([creating-profiles.md](creating-profiles.md)).
2. **O Modo Freestyle está ligado** na aba Jogar: com ele, o perfil ativo vale
   em qualquer jogo.
3. **Uma janela Wayland nativa**: a troca automática só enxerga janelas X11 e
   XWayland ([cosmic.md](cosmic.md)).
4. **Você acabou de trocar de perfil à mão**: a troca automática espera 30
   segundos para não desfazer a sua escolha, e volta sozinha depois disso.
   Trocar de novo reinicia a espera.

## A vibração do jogo dura um instante e morre

O serviço em memória pode ser mais velho que o instalado: reinicie-o (aba
Sistema, **Reiniciar**). Se continuar, abra uma issue com o nome do jogo.

## A barra de luz não pega a cor pelo Bluetooth

A barra nasce apagada, ou com outra cor, e não aceita a sua; no cabo, o mesmo
controle obedece.

A Steam aberta repinta a barra de todo DualSense a cada conexão nova, e a cor
que fica é a da Steam. O instalador fecha o controle físico para a
Steam não o pegar na conexão (a opção `--no-fechar-o-no` desfaz isso), e o
Hefesto repinta a cor depois que as conexões sossegam.

Se ainda acontecer:

1. Ligue os controles antes de abrir a Steam.
2. Com a Steam aberta, feche a Steam, desligue o controle (segure o PS até a
   barra apagar) e ligue de novo.
3. Confira com `hefesto-dualsense4unix doctor` se o serviço que entrega o
   controle físico ao Hefesto está de pé.

## O Steam Input pega o controle

Os botões do controle viram teclas em qualquer janela, mesmo com a Steam
minimizada, ou o aviso de microfone liga e desliga em laço.

É a Steam com o suporte a controle PlayStation ligado, que pega o controle e o
transforma em teclado e mouse. O instalador desliga isso nos jogos, e o vigia do
Steam Input mantém desligado ([instalacao.md](instalacao.md)). À mão:

```bash
bash scripts/disable_steam_input.sh --status    # só olha
bash scripts/disable_steam_input.sh --apply     # fecha a Steam, desliga e reabre
bash scripts/disable_steam_input.sh --restore   # volta à cópia de segurança
```

O touchpad mover o cursor do computador não é esse defeito: é o comportamento
padrão, em qualquer modo ([modos.md](modos.md)). O ponteiro do touchpad é
relativo, como o de um notebook; o da Steam leva o cursor a uma posição fixa da
tela.

## O teclado do controle não escreve letras

O teclado emulado está ligado e nenhuma letra sai. Os atalhos de fábrica não
digitam letras (são Super, PrintScreen, Alt+Tab e parecidos), e a maioria dos
botões nasce sem tecla. Para escrever texto, use o teclado na tela (L3, no modo
Navegação). Para dar uma tecla a um botão, use a lista de botões da aba
Navegação.

## O L3 não abre o teclado na tela

O teclado na tela é um programa do sistema:

```bash
echo "$XDG_SESSION_TYPE"     # wayland ou x11
sudo apt install wvkbd       # Wayland (COSMIC, GNOME Wayland, KDE Wayland)
sudo apt install onboard     # X11
```

O serviço acha o programa sozinho, em até dez segundos. Não instale o
`onboard` numa sessão Wayland: ele abre e não digita. No Flatpak, o `wvkbd` já
vem no pacote.

## O cursor anda sozinho

- Com o mouse do controle ligado, o analógico esquerdo move o cursor: PS +
  Options pausa o mouse e o teclado do controle.
- Pelo Bluetooth, com o microfone ligado, o driver de fábrica lê o som como
  botões e mexe o cursor. O módulo do Hefesto corrige isso; reinicie o
  computador depois de instalar ([bluetooth.md](bluetooth.md)).

## O pydantic do sistema é antigo

`AttributeError: module 'pydantic' has no attribute 'ConfigDict'`, no Ubuntu e
no Pop!_OS 22.04 e 24.04: o `python3-pydantic` do apt é o 1.x, e o Hefesto
precisa do 2.x. O `./install.sh`, o Flatpak e o AppImage trazem a versão certa;
para o `.deb`, rode antes `pip install --user 'pydantic>=2'`.

## Flatpak: o controle não aparece

As regras udev precisam estar no sistema, fora do sandbox:

```bash
flatpak run --command=install-host-udev.sh io.github.hefesto_team.hefesto_dualsense4unix
```

Depois, reconecte o controle e feche o Hefesto por inteiro antes de abrir de
novo ([flatpak.md](flatpak.md)).

## Diagnóstico geral

Para anexar a uma issue:

```bash
{ grep PRETTY_NAME /etc/os-release; uname -r; echo "$XDG_CURRENT_DESKTOP / $XDG_SESSION_TYPE"
  hefesto-dualsense4unix version; lsusb | grep -i 054c; ls -l /dev/hidraw* /dev/uinput
  hefesto-dualsense4unix doctor
  journalctl --user -u hefesto-dualsense4unix.service -n 30 --no-pager; } > diagnostico.txt 2>&1
```

Tire do arquivo o que for da sua máquina (nome de usuário, endereços dos
controles) antes de publicar.

Veja também [as dez abas](AS-DEZ-ABAS-o-que-cada-uma-faz.md) e
[o 8BitDo](troubleshooting-8bitdo.md).
