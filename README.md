<div align="center">

<img src="assets/appimage/Hefesto-Dualsense4Unix.png" width="120" alt="Logo do Hefesto — DualSense4Unix">

# Hefesto — DualSense4Unix

**Gerenciador DualSense para Linux**

[![Licença](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![GTK](https://img.shields.io/badge/GTK-3.0-green.svg)](https://www.gtk.org/)
[![Release](https://img.shields.io/github/v/release/AndreBFarias/hefesto-dualsense4unix?color=6a3fb4&label=release)](https://github.com/AndreBFarias/hefesto-dualsense4unix/releases/latest)
[![Testes](https://img.shields.io/badge/testes-4867-brightgreen.svg)](tests/)
[![CI](https://github.com/AndreBFarias/hefesto-dualsense4unix/actions/workflows/ci.yml/badge.svg)](https://github.com/AndreBFarias/hefesto-dualsense4unix/actions/workflows/ci.yml)

</div>

---

```
Versão: 0.1.1 (alfa)
Alvo:   Linux com systemd-logind · Python 3.10+
Licença: MIT
```

> **Alfa — software em maturação.** O Hefesto funciona e é usado todo dia na
> máquina em que é desenvolvido, mas ele mexe em partes sensíveis do sistema
> (regras udev, módulos de kernel, serviços e a configuração da Steam), e a
> validação em hardware cobre uma máquina só. Nada aqui promete estabilidade que
> ainda não foi medida. Leia [Limitações conhecidas](#limitações-conhecidas)
> antes de instalar.

## O que é

O Hefesto faz o DualSense do PS5 se comportar no Linux como se comporta no
console: **gatilhos adaptativos**, barra de luz, vibração na força que você
escolher, LEDs de jogador, giroscópio e touchpad. Com mais de um controle
plugado, cada um vira um jogador — co-op local sem configurar nada.

Fora do jogo, o mesmo controle vira mouse e teclado, para navegar do sofá.

Por baixo é um daemon em Python com três frentes de comando: uma janela GTK3, uma
interface de terminal e uma linha de comando. Controles de outras marcas
(Nintendo Pro, 8BitDo em modo Switch) entram como jogadores adicionais.

### O que ele entrega

- **Gatilhos adaptativos** — 19 modos (Rigid, Pulse, Galloping, Machine, Bow,
  Automatic Gun e os demais), ajustáveis por gatilho e salvos no perfil.
- **Um controle virtual por jogador** — o jogo vê um DualSense completo (com
  vibração, gatilhos, luz e giroscópio) ou um Xbox 360, conforme a máscara que
  você escolher. Ver [os três modos](docs/usage/modos.md).
- **Perfis por jogo** — trocam sozinhos quando você abre a janela do jogo, com um
  cadeado para quando você não quiser que troquem.
- **Luzes** — cor da lightbar por controle (com cores automáticas de jogador) e
  os cinco LEDs de jogador no padrão oficial do PS5.
- **Vibração com política** — Economia, Balanceado, Máximo ou Auto por bateria,
  aplicada ao que o jogo pede antes de chegar ao motor.
- **Compatibilidade com o DSX** — servidor UDP em `127.0.0.1:6969` no formato do
  DualSenseX; jogos e mods que já falam esse protocolo funcionam sem adaptação.
- **Automação** — socket JSON-RPC local para scripts e um sistema de plugins
  Python com ganchos de tique, botão e bateria.

## Instalação

```bash
git clone https://github.com/AndreBFarias/hefesto-dualsense4unix.git
cd hefesto-dualsense4unix
./install.sh
```

O instalador mostra um seletor de formato, pede a senha de administrador uma vez
e conduz o resto. As perguntas têm padrão seguro — dá para responder tudo com
Enter. Sem terminal interativo, use `./install.sh --yes`.

Depois, abra pelo menu de aplicativos ("Hefesto — DualSense4Unix") ou:

```bash
hefesto-dualsense4unix-gui
```

**Antes de instalar, saiba o que ele toca.** O Hefesto não é um aplicativo de
espaço de usuário puro: boa parte das curas mora em regra de udev, módulo de
kernel e serviço de sistema. Com os padrões de fábrica ele grava 13 regras udev,
drop-ins de `modprobe` e do BlueZ, serviços em `/etc/systemd/system`, dois
módulos de kernel via DKMS, um parâmetro no cmdline do kernel e ajustes na
configuração da Steam — cada um com sua flag de opt-out, e todos revertidos pelo
`./uninstall.sh`. A lista completa, item por item, está em
**[docs/usage/instalacao.md](docs/usage/instalacao.md)**.

Existem também pacotes `.deb`, Flatpak, AppImage, Arch, Fedora e Nix; para a
alfa, o caminho testado é o do código-fonte.

## Como usar

### A janela

Nove abas. A primeira, **Início**, é a de decisão: escolha ali *o que o controle
faz agora*.

| Modo | O que acontece |
|---|---|
| **Controlar o PC** | o controle vira mouse e teclado |
| **Jogar pelo Hefesto** | o jogo enxerga um controle virtual — é o padrão para jogar, e o único modo com co-op local |
| **Jogar direto (Sony)** | o Hefesto solta o controle e o jogo fala direto com ele |

As outras oito abas — Status, Gatilhos, Lightbar, Rumble, Perfis, Sistema,
Emulação e Navegação DSX — estão descritas uma a uma em
**[docs/usage/interface.md](docs/usage/interface.md)**.

### Atalhos no próprio controle

| Gesto | Ação |
|---|---|
| PS + D-pad cima / baixo | perfil seguinte / anterior |
| PS (toque curto) | abre a Steam (configurável) |
| PS + Options | modo jogo: suspende a emulação de mouse e teclado |
| Botão de microfone | muta o microfone do sistema |

Detalhes e configuração em [docs/usage/hotkeys.md](docs/usage/hotkeys.md).

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
hefesto-dualsense4unix tui                        # interface de terminal
```

O daemon roda como serviço `--user`:

```bash
systemctl --user enable --now hefesto-dualsense4unix.service
journalctl --user -u hefesto-dualsense4unix -f
```

Referência completa dos comandos em [docs/usage/cli.md](docs/usage/cli.md).

## Capturas de tela

Ainda não há. A janela foi redesenhada e os prints antigos não valem mais; os
novos exigem controle conectado e tela livre, o que não estava disponível quando
esta página foi escrita.

As imagens entram em `docs/usage/assets/`, e o lugar de cada uma já está marcado
em [docs/usage/interface.md](docs/usage/interface.md), em comentário, uma por
aba. Falta capturar:

- [ ] `readme_inicio.png` — Início, com os três modos e os cards dos controles
- [ ] `readme_status.png` — Status, com sticks, gatilhos, giroscópio, microfone e touchpad
- [ ] `readme_gatilhos.png` — Gatilhos, com L2 e R2 lado a lado
- [ ] `readme_lightbar.png` — Lightbar, com cor, luminosidade e LEDs de jogador
- [ ] `readme_rumble.png` — Rumble, com a política e o teste dos motores
- [ ] `readme_perfis.png` — Perfis, com a lista e o editor
- [ ] `readme_sistema.png` — Sistema, com a saúde do sistema e os botões da Steam
- [ ] `readme_emulacao.png` — Emulação, com a máscara ativa
- [ ] `readme_navegacao_dsx.png` — Navegação DSX, mouse e teclado em duas colunas

## Limitações conhecidas

**O `bluetoothd` derruba pareamentos.** Corrupção de heap no serviço de Bluetooth
do sistema (`malloc_consolidate(): unaligned fastbin chunk detected`) faz o
serviço reiniciar e **apagar pareamentos**. O gatilho medido aqui é a reconexão
de dois controles Nintendo-class em poucos segundos — o Pro Controller genuíno e
um 8BitDo em modo Switch se apresentam com o mesmo identificador. É um problema
aberto do BlueZ, sem correção upstream conhecida, e **não temos como consertá-lo
daqui**. O que fizemos foi reduzir o estrago: o Hefesto fotografa os pareamentos
na borda de cada conexão nova. Mitigação em
[docs/usage/bluetooth.md](docs/usage/bluetooth.md).

**8BitDo por Bluetooth cai sob carga.** Conecta e funciona, mas derruba em sessão
sustentada. O caminho confiável para ele hoje é o cabo.

**A validação em hardware é de uma máquina só.** Pop!\_OS 24.04 com COSMIC é o
ambiente onde tudo é medido. Ubuntu tem cobertura de integração contínua, sem
hardware. Fedora, Arch, Debian e Mint têm pacotes mantidos, mas **nenhum foi
rodado com controle real** nesta linha.

**A troca automática de perfil não vê janelas Wayland nativas.** No COSMIC, o
portal ainda não expõe a janela ativa, então o reconhecimento cobre o que roda
sob XWayland — Steam e Proton, entre eles. Para os demais, troque de perfil pela
janela, pela linha de comando ou pelo combo no controle.

**Áudio do DualSense por Bluetooth está fora de escopo** — protocolo proprietário.
Por USB, o áudio funciona.

**Distros sem `systemd-logind`** (Alpine OpenRC, Void runit, Artix) estão fora de
escopo — ver [ADR-009](docs/adr/009-systemd-logind-scope.md).

**Métricas e plugins são opt-in.** Os plugins ligam por variável de ambiente; o
endpoint Prometheus hoje só sobe por código, sem chave na linha de comando.

## Documentação

- **Primeiros passos:** [docs/usage/quickstart.md](docs/usage/quickstart.md)
- **Instalação em detalhe:** [docs/usage/instalacao.md](docs/usage/instalacao.md)
- **A janela, aba por aba:** [docs/usage/interface.md](docs/usage/interface.md)
- **Os três modos e a máscara:** [docs/usage/modos.md](docs/usage/modos.md)
- **Perfis:** [docs/usage/creating-profiles.md](docs/usage/creating-profiles.md)
- **Atalhos no controle:** [docs/usage/hotkeys.md](docs/usage/hotkeys.md)
- **Bluetooth:** [docs/usage/bluetooth.md](docs/usage/bluetooth.md)
- **Linha de comando:** [docs/usage/cli.md](docs/usage/cli.md)
- **COSMIC / Wayland:** [docs/usage/cosmic.md](docs/usage/cosmic.md)
- **Quando dá errado:** [docs/usage/troubleshooting.md](docs/usage/troubleshooting.md)
  · [8BitDo](docs/usage/troubleshooting-8bitdo.md)
- **Decisões arquiteturais:** [docs/adr/](docs/adr/)
- **Protocolos (UDP, JSON-RPC, gatilhos):** [docs/protocol/](docs/protocol/)
- **Pesquisas e medições:** [docs/research/](docs/research/)
- **Histórico de versões:** [CHANGELOG.md](CHANGELOG.md)

O histórico de desenvolvimento — sprints, estudos, diário de descobertas — não
fica na `main`: está preservado inteiro na tag `arquivo/processo-pre-1.0`.
Qualquer caminho `docs/process/...` citado em comentário ou documento se resolve
por ali:

```bash
git show arquivo/processo-pre-1.0:docs/process/ROADMAP.md   # ler um arquivo
git checkout arquivo/processo-pre-1.0 -- docs/process       # trazer a árvore
```

## Contribuindo

Leia [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md) antes de abrir PR. O
essencial: tudo em português do Brasil e com acentuação correta; `pytest`,
`ruff` e `mypy --strict` fechando; e o gate de anonimato passando
(`scripts/check_anonymity.sh`).

```bash
pip install pre-commit && pre-commit install
```

Os ganchos barram na sua máquina o que o CI barraria depois: acentuação faltando,
`ruff` reprovado, gate de anonimato violado.

Relato de uso em distro fora da lista é especialmente bem-vindo: rode
`hefesto-dualsense4unix doctor`, anexe a saída e abra issue com a label
`validation-report`.

## Licença

MIT — veja [`LICENSE`](LICENSE).

---

*"A forja não revela o ferreiro. Só a espada."*
