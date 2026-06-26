# ADR-018: Fronteira de responsabilidade do Hefesto no USB — autosuspend per-device vs. dropout `-71` do controlador

**Status:** emendado / parcialmente superado (ver **Emenda 2026-06-26**). A parte 1
(autosuspend `ENODEV` per-device) segue válida. A parte 2 (o `-71` é BIOS / Power
Supply Idle Control, não há alavanca de software, recomendar trocar de porta ou
Bluetooth) foi **SUPERADA**: a causa-raiz do `-71` nesta plataforma é a
**enumeração do áudio USB do DualSense** (port-independente, não C-state/BIOS) e
**há duas alavancas de software** suportadas pelo Hefesto. Doc canônico:
`docs/process/discoveries/2026-06-26-storm-audio-pesquisa-profunda-quirk-vs-audiooff.md`.

## Emenda (2026-06-26): a causa-raiz do `-71` é a enumeração do áudio USB — e há alavancas de software

Investigação por eliminação (controle plugado, jogo real PRAGMATA via Proton)
reverteu a conclusão da parte 2 da Decisão original. Registro corrigido:

- **Causa-raiz real.** O storm `-71` é disparado pela **enumeração das interfaces
  de ÁUDIO USB** do DualSense pelo kernel `snd-usb-audio`: uma rajada de
  control-transfers no EP0 (probe: `usb_set_interface`, `get min/max values for
  control`) que, sob carga, tomba o link → `-71` (EPROTO) → re-enumeração. A
  interface HID (If3) enumera "leve" e passa; as 3 interfaces de áudio (If0
  Audio Control, If1/If2 Audio Streaming = alto-falante/microfone) são o probe
  control-heavy que derruba.
- **NÃO é BIOS / C-state / I/O die / cabo / porta.** Provado A/B e ao vivo:
  **áudio off = 0 storm em qualquer porta** (inclusive a do controlador do
  chipset, antes tida como a porta "boa") e **áudio on = storm** mesmo após
  trocar de porta. É **port-independente**. A teoria antiga ("Power Supply Idle
  Control / C-state / mover para o outro controlador / Bluetooth") está
  **superada**.
- **NÃO é software de usuário.** Daemon do Hefesto e WirePlumber foram parados na
  investigação e o flap persistiu — logo não é o daemon nem a config de áudio do
  usuário; é o kernel montando as interfaces de áudio na enumeração.
- **Correção de hardware.** A máquina é **Ryzen 7 5800X (Vermeer)**, não Matisse;
  o xHCI `0c:00.3` aparece rotulado como "Matisse" no `lspci`, mas a CPU é
  Vermeer (Zen 3). O mecanismo do `-71` é o mesmo.

### Duas alavancas de software suportadas pelo Hefesto (uma OU outra, nunca as duas)

- **(A) Quirk de cmdline que PRESERVA o áudio.**
  `usbcore.quirks=054c:0ce6:gn,054c:0df2:gn` (`g` = `USB_QUIRK_DELAY_INIT`,
  `n` = `USB_QUIRK_DELAY_CTRL_MSG`): espaça exatamente a rajada que derruba o
  link — o áudio ainda enumera, só mais devagar, sem tombar. Aplicado por
  `scripts/install_usb_quirk.sh` ou `./install.sh --with-usb-quirk` (opt-in,
  default OFF). Validado ao vivo (PRAGMATA: 0 quedas com quirk + áudio ON).
- **(B) Regra udev 75 que DESLIGA o áudio.** `authorized=0` nas interfaces classe
  01 do `054c:0ce6`/`0df2` → o kernel não bind/probe `snd-usb-audio` → a rajada
  não acontece. Custo: controle sem microfone e sem fone pelo jack. Aplicada por
  `scripts/install_udev.sh --disable-usb-audio`; reversível via
  `HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1`.

São **alternativas**: o quirk preserva o áudio; a regra 75 sacrifica o áudio.
Não usar as duas ao mesmo tempo.

### Diagnóstico

- O `doctor.sh` ganhou `check_usb_quirk`: reporta se o quirk está ativo (cmdline),
  agendado (bootloader, pendente de reboot), armado em runtime (sysfs) ou ausente
  — e aponta a alternativa (quirk preserva áudio vs. regra 75 áudio-off).
- Os drop-ins do WirePlumber (52/53) são **ortogonais** ao storm: impedem o mic do
  DualSense de virar entrada padrão, mas **não** param o `-71`. Não confundir.

O texto abaixo (Contexto/Decisão/Consequências) fica como **registro histórico** da
fronteira per-device — válido para a parte 1 (`ENODEV`); a parte 2 (`-71` = BIOS,
sem alavanca de software) está superada por esta Emenda.

## Contexto

Há dois sintomas de "o controle caiu" que parecem o mesmo evento mas têm
causa-raiz, escopo e dono diferentes. Confundi-los leva a tentar corrigir com a
alavanca errada e a abrir bug no lugar errado.

1. **Autosuspend per-device (`ENODEV`).** O kernel com `CONFIG_USB_RUNTIME_PM=y`
   suspende um device USB ocioso após ~2 s; o próximo `read()` no hidraw devolve
   `ENODEV` e o daemon entra em reconnect loop. É *um device*. Já é resolvido
   pelo Hefesto com `assets/72-ps5-controller-autosuspend.rules`
   (`power/control=on`, `autosuspend_delay_ms=-1`) — ver ADR-013 e `USB-POWER-01`.

2. **Dropout `-71` (`EPROTO`) do controlador xHCI.** Em plataformas AMD Ryzen
   (família Matisse/Zen 2 observada na máquina da mantenedora), o *controlador
   inteiro* entra em estado de baixa energia governado pelo **Power Supply Idle
   Control** (AGESA/BIOS). O kernel registra `error -71` / `device descriptor
   read/64, error -71` e derruba **todos** os devices daquele barramento (já se
   observou derrubar teclado/mouse junto). O ajuste runtime per-device **não
   alcança** esse nível — a decisão é de firmware/BIOS.

O estudo de campo `docs/research/2026-05-28-dualsense-dropout-usb-e-wireplumber-source.md`
mapeou a topologia: dois controladores xHCI (`02:00.0` chipset, `0c:00.3`
Matisse/CPU), com DualSense e dongle BT no Matisse e teclado/mouse no chipset.

Adicionalmente, o `usbcore.autosuspend=-1` global e as `99-usb-*.rules` na
máquina **não** são do Hefesto — pertencem ao toolchain pessoal da mantenedora
(ritual Aurora self-heal), dono do kernel cmdline e do power USB global. Atribuir
isso ao Hefesto, ou o Hefesto passar a mexer nisso, viola a separação de donos.

## Decisão

O Hefesto trata o USB **apenas na camada per-device que ele já domina** e nada
além disso:

- **Cobre (faz):** autosuspend per-VID/PID via udev (`72-ps5-controller-autosuspend.rules`,
  ADR-013). Cirúrgico, idempotente, sob a mesma barreira de sudo de
  `70-ps5-controller.rules`.
- **Não cobre (não faz):** kernel cmdline (`usbcore.autosuspend`, `pcie_aspm`,
  `usbcore.autosuspend_delay_ms` global), tunável global em
  `/sys/module/usbcore/parameters/*`, regras `99-usb-*` de power global, e
  qualquer tentativa de "consertar" Power Supply Idle Control em runtime. Não há
  alavanca de software para o `-71` do controlador; é BIOS.
- **Diagnostica e recomenda (faz, novo):** o `doctor.sh` ganha a capacidade de
  (a) detectar em qual controlador/barramento o DualSense está, (b) contar
  `error -71` no `journalctl -k` do boot, (c) quando há dropout, recomendar mover
  para uma porta do outro controlador ou usar Bluetooth, e (d) um modo
  `--watch-dropout` que vigia o journal. Ver `FEAT-DOCTOR-USB-DROPOUT-DIAGNOSTIC-01`.
  Recomendar ≠ aplicar: o doctor nunca edita BIOS, cmdline ou regras de outro dono.

## Consequências

(+) Bug report e fix vão para o lugar certo: `ENODEV` → regra do Hefesto;
`-71` → BIOS do usuário + recomendação de porta/BT. Sem mascarar sintoma com a
alavanca errada.

(+) Respeita a fronteira com o toolchain Aurora (kernel cmdline / power USB
global) — o Hefesto lê o cabeçalho de origem antes de atribuir, e não invade.

(+) O usuário ganha diagnóstico acionável para o `-71` sem que o Hefesto assuma
responsabilidade que não pode honrar (corrigir firmware).

(−) O `-71` continua exigindo ação manual fora do Hefesto (BIOS/porta/BT) — o
projeto não "resolve" o problema, só orienta. É uma limitação assumida, não uma
dívida a quitar.

(−) A recomendação "mude de porta" depende de mapeamento empírico portacontrolador
que o usuário precisa confirmar; o doctor ajuda, mas não advinha o conector
físico.

(−) Bluetooth como mitigação tem ressalva: na topologia observada o dongle BT
está no mesmo controlador Matisse — contorna a porta do controle, não o
controlador. O transporte L2CAP costuma tolerar glitch melhor que HID-over-USB,
mas não é imunidade. ADR-008 cobre o trade-off de latência BT vs USB.
