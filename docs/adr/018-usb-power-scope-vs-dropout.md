# ADR-018: Fronteira de responsabilidade do Hefesto no USB — autosuspend per-device vs. dropout `-71` do controlador

**Status:** aceito

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
