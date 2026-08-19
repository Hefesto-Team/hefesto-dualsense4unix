<div align="center">

<img src="assets/appimage/Hefesto-Dualsense4Unix.png" width="120" alt="Logo do Hefesto — DualSense4Unix">

# Hefesto — DualSense4Unix

**Seu DualSense no Linux funcionando como funciona no PS5.**

[![Licença](https://img.shields.io/badge/licen%C3%A7a-MIT%20%2B%20GPL--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![GTK](https://img.shields.io/badge/GTK-3.0-green.svg)](https://www.gtk.org/)
[![Versão](https://img.shields.io/badge/vers%C3%A3o-0.9.4.5%20alfa-6a3fb4.svg)](CHANGELOG.md)
[![Testes](https://img.shields.io/badge/testes-mais%20de%207000-brightgreen.svg)](tests/)
[![CI](https://github.com/AndreBFarias/hefesto-dualsense4unix/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AndreBFarias/hefesto-dualsense4unix/actions/workflows/ci.yml)

</div>

---

```
Versão: 0.9.4.5 (alfa)
Alvo:   Linux com systemd-logind · Python 3.10+
Licença: MIT, exceto `assets/dkms/*` (GPL-2.0) — ver LICENSE e NOTICE
```

Gatilhos adaptativos que resistem de verdade. Barra de luz na cor que você
quiser. Vibração no volume que você mandar. Giroscópio, touchpad, LEDs de
jogador, microfone. Plugou outro controle, virou outro jogador — co-op local
sem configurar nada.

E quando o jogo fecha, o mesmo controle vira mouse e teclado para navegar do
sofá.

Por baixo é um daemon em Python com três frentes: uma janela GTK3, uma interface
de terminal e uma linha de comando. Controles Nintendo Pro e 8BitDo também
entram.

> **Alfa.** Funciona e é usado todo dia, mas mexe em regra de udev, módulo de
> kernel, serviço de sistema e configuração da Steam — e a validação em hardware
> cobre uma máquina só. Leia [Limitações conhecidas](#limitações-conhecidas)
> antes de instalar.

## A janela

| | |
|---|---|
| **Início** — quando o jogo abrir | **Status** — tudo o que o controle está fazendo |
| [![Início](docs/usage/assets/readme_inicio.png)](docs/usage/interface.md) | [![Status](docs/usage/assets/readme_status.png)](docs/usage/interface.md) |
| **No jogo** — o que atravessa para o jogo | |
| [![No jogo](docs/usage/assets/readme_no_jogo.png)](docs/usage/interface.md) | |
| **Gatilhos** — os dezenove modos de resistência | **Lightbar** — a cor e o desenho das cinco luzes |
| [![Gatilhos](docs/usage/assets/readme_gatilhos.png)](docs/usage/interface.md) | [![Lightbar](docs/usage/assets/readme_lightbar.png)](docs/usage/interface.md) |
| **Rumble** — a intensidade da vibração dos jogos | **Perfis** — um ajuste por jogo, que entra sozinho |
| [![Rumble](docs/usage/assets/readme_rumble.png)](docs/usage/interface.md) | [![Perfis](docs/usage/assets/readme_perfis.png)](docs/usage/interface.md) |
| **Sistema** — o serviço, a saúde e os jogos da Steam | **Emulação** — como o jogo vê o controle |
| [![Sistema](docs/usage/assets/readme_sistema.png)](docs/usage/interface.md) | [![Emulação](docs/usage/assets/readme_emulacao.png)](docs/usage/interface.md) |
| **Navegação** — o controle como mouse e teclado | |
| [![Navegação](docs/usage/assets/readme_navegacao_dsx.png)](docs/usage/interface.md) | |

Aba por aba em [docs/usage/interface.md](docs/usage/interface.md).

## O que ele entrega

- **Gatilhos adaptativos** — 19 modos numa grade (Rígido, Pulso, Galope,
  Metralhadora, Arco de flecha, Arma automática e os demais), ajustáveis por
  gatilho e salvos no perfil.
- **Um controle virtual por jogador** — o jogo vê um DualSense completo, com
  vibração, gatilhos, luz e giroscópio, ou um Xbox 360. Ver
  [os três modos](docs/usage/modos.md).
- **Perfis por jogo** — trocam sozinhos quando você abre o jogo, com um cadeado
  para quando você não quiser que troquem.
- **Luzes** — cor da lightbar por controle e o desenho das 5 luzes de jogador,
  com os presets do P1 ao P4, no padrão oficial do PS5.
- **Vibração com política** — Economia (30%), Balanceado (100%), Máximo (150%)
  ou Auto por bateria, aplicada antes de chegar ao motor. Um controle deslizante
  vai de 0 a 200 para quem quiser sair dos quatro degraus.
- **Teclado na tela pelo controle** — L3 abre, R3 fecha. É o único caminho de
  fábrica para escrever texto, e o instalador já traz o programa
  (`wvkbd` no Wayland, `onboard` no X11).
- **Protocolo do DSX, em parte** — servidor UDP em `127.0.0.1:6969` que aceita o
  envelope do DualSenseX e as seis instruções principais. Os 12 modos de gatilho
  "prontos" (`Hard`, `Soft`, `Choppy`…) ainda não têm tradução: são curvas
  fechadas, e as tabelas que circulam estão num repositório sem licença. Um mod
  que use só os modos paramétricos funciona. Ver
  [udp-schema.md](docs/protocol/udp-schema.md).
- **Automação** — socket JSON-RPC local para scripts e plugins Python com
  ganchos de tique, botão e bateria.

## Instalação

```bash
git clone https://github.com/AndreBFarias/hefesto-dualsense4unix.git
cd hefesto-dualsense4unix
git checkout v0.9.4.5
./install.sh
```

O instalador mostra um seletor de formato, pede a senha de administrador uma vez
e conduz o resto. Todas as perguntas têm padrão seguro — dá para responder tudo
com Enter. Sem terminal interativo, use `./install.sh --yes`.

Depois, abra pelo menu de aplicativos ou:

```bash
hefesto-dualsense4unix-gui
```

Existem também pacotes `.deb`, Flatpak, AppImage, Arch, Fedora e Nix. Para a
alfa, o caminho testado é o do código-fonte.

### Ligue o controle no cabo da primeira vez

Não para instalar — o `install.sh` provisiona o sistema e não fala com o
controle. Mas **ligue o DualSense no cabo USB antes de abrir a janela pela
primeira vez**: é assim que o Hefesto elege o controle principal, cria o gamepad
virtual e liga a leitura de gatilhos, LEDs, toque, giroscópio e microfone. Só o
cabo dá energia para o rádio interno e o caminho HID completo de uma vez.

O que muda entre cabo e rádio:

| | USB (cabo) | Bluetooth |
|---|---|---|
| Envelope do relatório | `0x02`, sem checksum | `0x31`/`0x32` com CRC-32 e sequência |
| Cor e luzes de jogador | pelo nó do kernel em `/sys` | idem |
| Microfone | canal de captura direto | agente tunelado dentro do próprio HID |
| Custo de ligar o microfone | nenhum | cerca de **35% dos relatórios de input** |

### O que ele toca no sistema

O Hefesto não é aplicativo de espaço de usuário puro. Com os padrões de fábrica
ele grava 15 regras udev, drop-ins de `modprobe` e do BlueZ, serviços em
`/etc/systemd/system`, três módulos de kernel via DKMS (`hid-nintendo`,
`hid-playstation`, `rtw88-usb`), um parâmetro no cmdline do kernel e ajustes na
Steam. Cada um tem flag de opt-out, e todos são revertidos pelo `./uninstall.sh`.
Item por item em [docs/usage/instalacao.md](docs/usage/instalacao.md).

## Como usar

A aba **Início** é a de decisão. No quadro *"Quando o jogo abrir"* você escolhe
o que o controle faz agora e como o jogo o enxerga:

| Modo | O que acontece |
|---|---|
| **Controlar o PC** | o controle vira mouse e teclado |
| **Jogar pelo Hefesto** | o jogo vê um controle virtual — é o padrão, e o único modo com co-op local |
| **Conexão Nativa (Sony)** | o Hefesto solta o controle e o jogo fala direto com ele |

### Atalhos no próprio controle

| Gesto | Ação |
|---|---|
| PS + D-pad cima / baixo | perfil seguinte / anterior |
| PS (toque curto) | abre a Steam (configurável) |
| PS + Options | modo jogo: suspende a emulação de mouse e teclado |
| L3 / R3 | abre / fecha o teclado na tela |
| Botão de microfone | muta o microfone do sistema |

Mais em [docs/usage/hotkeys.md](docs/usage/hotkeys.md).

### Linha de comando

```bash
hefesto-dualsense4unix status                     # estado do daemon e do controle
hefesto-dualsense4unix doctor                     # diagnóstico ponta a ponta (--fix corrige)
hefesto-dualsense4unix battery                    # bateria
hefesto-dualsense4unix profile list               # perfis salvos
hefesto-dualsense4unix profile activate fps
hefesto-dualsense4unix gamepad on --flavor xbox   # o jogo vê um Xbox 360
hefesto-dualsense4unix mouse on                   # controle vira mouse e teclado
hefesto-dualsense4unix native on                  # solta o controle para o jogo
hefesto-dualsense4unix led --color "#FF0080"      # lightbar
hefesto-dualsense4unix mic bt                     # sobe a ponte do mic por Bluetooth
hefesto-dualsense4unix tui                        # interface de terminal
```

O daemon roda como serviço `--user`:

```bash
systemctl --user enable --now hefesto-dualsense4unix.service
journalctl --user -u hefesto-dualsense4unix -f
```

Referência completa em [docs/usage/cli.md](docs/usage/cli.md).

## Limitações conhecidas

**Pareamentos Bluetooth somem, por dois motivos diferentes.** Um é corrupção de
heap no `bluetoothd` do sistema, que reinicia o serviço e apaga pareamentos — é
problema aberto do BlueZ, sem correção upstream, e não dá para consertar daqui.
O outro não tem crash nenhum: acontece quando o controle está pareado por
Bluetooth e sendo usado pelo cabo ao mesmo tempo. O Hefesto fotografa os
pareamentos a cada conexão nova para reduzir o estrago. Detalhe em
[docs/usage/bluetooth.md](docs/usage/bluetooth.md).

**8BitDo por Bluetooth: use o modo DirectInput/PS4, não o modo Switch.** Em modo
Switch ele se anuncia como `057e:2009`, cai no `hid-nintendo` e morre no probe.
Em DirectInput/PS4 ele se anuncia como `054c:05c4`, o `hid-playstation` assume e
conecta de primeira. Por cabo, o modo Switch é o estável. Tabela completa em
[troubleshooting-8bitdo.md](docs/usage/troubleshooting-8bitdo.md).

**Só os DualSense contam como jogadores.** Controles de outra marca entram na
lista de externos, com número e luz próprios, e chegam ao jogo como o gamepad
nativo que já eram — mas não ganham controle virtual próprio nem entram na
contagem do co-op.

**A cor da lightbar por Bluetooth perde para a Steam.** Se a Steam já está aberta
quando o controle conecta, ela repinta a barra de todos os DualSense e a sua cor
não fica. O contorno é ligar os controles antes de abrir a Steam. No cabo o
problema não aparece.

**O microfone por Bluetooth entrega metade do sinal.** O DualSense não fala
A2DP/HFP — manda o áudio como agente dentro dos relatórios HID, e o Hefesto tem a
ponte que decodifica e publica no PipeWire. Duas ressalvas: a ponte é opt-in
(ligá-la custa ~35% dos relatórios de input) e o firmware marca o mic como mudo
boa parte do tempo, sobrando por volta de 40% do sinal. O fone por Bluetooth
está fora de escopo. Por USB, mic e fone funcionam normalmente.

**A troca automática de perfil não vê janelas Wayland nativas.** No COSMIC o
portal ainda não expõe a janela ativa, então o reconhecimento cobre o que roda
sob XWayland — Steam e Proton, entre eles.

**A validação em hardware é de uma máquina só.** Pop!_OS 24.04 com COSMIC é onde
tudo é medido. Ubuntu tem CI sem hardware. Fedora, Arch, Debian e Mint têm
pacotes mantidos, mas nenhum foi rodado com controle real. Versões exatas em
[versoes-validadas.md](docs/usage/versoes-validadas.md).

**Métricas e plugins são opt-in — e as métricas não têm chave para o usuário.**
Os plugins ligam por variável de ambiente
(`HEFESTO_DUALSENSE4UNIX_PLUGINS_ENABLED=1`). Já o endpoint Prometheus depende de
`metrics_enabled` no `DaemonConfig`, e não existe hoje variável de ambiente, flag
nem arquivo de configuração que ligue esse campo: o daemon o constrói com
quatro parâmetros só — `poll_hz`, `auto_reconnect`, `ps_long_press_ms` e
`keyboard_emulation_enabled`. Na prática, subir as métricas exige mexer no
código. Ver [docs/usage/metrics.md](docs/usage/metrics.md).

**Distros sem `systemd-logind`** (Alpine OpenRC, Void runit, Artix) estão fora de
escopo — ver [ADR-009](docs/adr/009-systemd-logind-scope.md).

## Documentação

- **Primeiros passos:** [quickstart.md](docs/usage/quickstart.md)
- **Instalação em detalhe:** [instalação.md](docs/usage/instalacao.md)
- **A janela, aba por aba:** [interface.md](docs/usage/interface.md)
- **Os três modos:** [modos.md](docs/usage/modos.md)
- **Perfis:** [creating-profiles.md](docs/usage/creating-profiles.md)
- **Atalhos no controle:** [hotkeys.md](docs/usage/hotkeys.md)
- **Bluetooth:** [bluetooth.md](docs/usage/bluetooth.md)
- **Linha de comando:** [cli.md](docs/usage/cli.md)
- **COSMIC / Wayland:** [cosmic.md](docs/usage/cosmic.md)
- **Quando dá errado:** [troubleshooting.md](docs/usage/troubleshooting.md) ·
  [8BitDo](docs/usage/troubleshooting-8bitdo.md)
- **O que o DualSense entende:**
  [referência canônica](docs/protocol/dualsense-referencia-canonica.md) — o mapa
  dos 47 bytes do report de saída, os modos de gatilho contra a enum oficial da
  Sony, a rota do áudio e os sensores.
- **Decisões arquiteturais:** [docs/adr/](docs/adr/)
- **Histórico de versões:** [CHANGELOG.md](CHANGELOG.md)

## Contribuindo

Leia [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md) antes de abrir PR. O
essencial: tudo em português do Brasil e com acentuação correta; `pytest`,
`ruff` e `mypy --strict` fechando; e o gate de anonimato passando.

```bash
pip install pre-commit && pre-commit install
```

Relato de uso em distro fora da lista é especialmente bem-vindo: rode
`hefesto-dualsense4unix doctor`, anexe a saída e abra issue com a label
`validation-report`.

## Licença

**MIT, exceto `assets/dkms/*`** — o texto MIT está em [`LICENSE`](LICENSE) e a
exceção, com auditoria arquivo por arquivo, no [`NOTICE`](NOTICE).

Os três módulos de kernel vendorados em `assets/dkms/` são derivados do Linux e
mantêm a licença própria do cabeçalho SPDX: `hid-nintendo` e `hid-playstation`
são **GPL-2.0-or-later**; o `rtw88-usb` é **GPL-2.0 OR BSD-3-Clause**. Eles não
são linkados ao código Python — são distribuídos como fonte separada e
compilados no destino pelo DKMS.
