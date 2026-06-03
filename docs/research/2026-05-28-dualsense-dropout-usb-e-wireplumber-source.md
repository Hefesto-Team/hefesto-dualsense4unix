# DualSense em Pop!_OS COSMIC — dropout USB `-71` e WirePlumber default-source (2026-05-28)

> **Estudo de campo.** Achados empíricos coletados em sessão de recuperação na
> máquina da mantenedora (Pop!_OS COSMIC, Wayland, DualSense USB, AMD Ryzen
> Matisse). O Hefesto estava **desinstalado** no momento da coleta — logo, tudo
> aqui é comportamento de plataforma (kernel `hid_playstation`, WirePlumber,
> controladores xHCI), não do daemon.
>
> Origina três artefatos de decisão e três sprints:
> [[018-usb-power-scope-vs-dropout]], [[019-wireplumber-default-active-not-configured]],
> `BUG-WIREPLUMBER-FIX-FALSE-SUCCESS-01`, `FEAT-WIREPLUMBER-DISABLE-SOURCE-MODE-01`,
> `FEAT-DOCTOR-USB-DROPOUT-DIAGNOSTIC-01`.

## Sumário executivo

- **Dois problemas USB distintos, frequentemente confundidos.** (a) *autosuspend
  per-device* (`ENODEV` após ~2 s de ociosidade) — já resolvido pelo Hefesto via
  `assets/72-ps5-controller-autosuspend.rules` (ADR-013 / `USB-POWER-01`). (b)
  *dropout `-71` (`EPROTO`) do controlador xHCI* sob AMD Ryzen — **não** coberto
  por nenhuma regra do Hefesto, e fora do escopo de software corrigir. São causas
  diferentes com sintoma parecido ("o controle caiu").
- **A máquina tem dois controladores xHCI físicos separados.** O DualSense e o
  dongle Bluetooth estão ambos no controlador da CPU (Matisse, `0c:00.3`);
  teclado e mouse estão no controlador do chipset (`02:00.0`). O dropout `-71`
  do Ryzen é tipicamente *por controlador* — então **trocar o controle para uma
  porta do outro controlador** é uma mitigação real e testável.
- **O fix do WirePlumber (`FEAT-WIREPLUMBER-DUALSENSE-NOT-DEFAULT-SOURCE-01`)
  reporta sucesso enganoso.** Ele rebaixa a prioridade do mic do DualSense
  (`priority.session/driver = 50`), o que só governa a eleição *automática*.
  Quando o DualSense é a **única fonte de captura disponível** (webcam
  desconectada, jack onboard vazio), o WirePlumber continua — corretamente —
  elegendo-o como default. O script declara "fonte padrão reeleita" mesmo assim,
  e o `doctor.sh` verifica o `default.configured` (preferência) em vez do default
  **ativo** (`pactl get-default-source`) — pode dar `[ OK ]` falso.
- **Boot atual limpo de `-71`** (0 ocorrências em ~23 min de uptime no momento da
  coleta), consistente com a hipótese de que o ajuste de BIOS (Power Supply Idle
  → *Typical Current Idle*) estabilizou o controlador. Não é prova definitiva:
  o `-71` do Ryzen dispara em ociosidade, não no boot.

---

## 1. Topologia USB observada

`lspci` — dois controladores xHCI:

| PCI | Controlador | Origem física |
|---|---|---|
| `02:00.0` | AMD 400 Series Chipset USB 3.1 xHCI | chipset (southbridge) |
| `0c:00.3` | AMD Matisse USB 3.0 Host Controller | die da CPU (Zen 2) |

`lsusb -t` — quatro root hubs (cada controlador expõe um par USB2 + USB3):

```
Bus 001 (xhci_hcd/10p, 480M)   -> teclado + mouse (HID 12M, portas 4 e 5)
Bus 002 (xhci_hcd/4p, 10000M)  -> vazio
Bus 003 (xhci_hcd/4p, 480M)    -> DualSense (HID 480M + Audio, porta 4)
Bus 004 (xhci_hcd/4p, 10000M)  -> dongle Wi-Fi/BT Realtek 8822BU (rtw88_8822bu, porta 3)
```

O DualSense registra em `usb-0000:0c:00.3-4` (kernel: `Registered DualSense
controller hw_version=0x00000710 fw_version=0x0110002a`), `hidraw4`, 480 Mbps.
Ou seja: **Bus 003/004 ≈ controlador Matisse (`0c:00.3`); Bus 001/002 ≈ chipset
(`02:00.0`)**.

Consequências:
- **DualSense e Bluetooth compartilham o controlador Matisse.** Se o `-71` for
  do Matisse, o Bluetooth (que é um dongle USB Realtek no mesmo controlador) não
  é um porto automaticamente seguro — embora o transporte L2CAP do BT seja mais
  resiliente a glitch de barramento que o HID-over-USB.
- **Teclado/mouse no chipset não relataram dropout** nesta sessão. Isso aponta o
  chipset como destino candidato para o controle.
- O mapeamento *porta física  controlador* não é dedutível do conector; exige
  teste empírico: mover o cabo e reler `lsusb -t` / o `usb-0000:XX:00.Y-...` no
  `journalctl -k`. Daí a sprint `FEAT-DOCTOR-USB-DROPOUT-DIAGNOSTIC-01`.

## 2. Dois problemas USB, um sintoma

| | autosuspend per-device | dropout `-71` do controlador |
|---|---|---|
| Erro no kernel | `ENODEV` | `error -71` (`EPROTO`) / `device descriptor read/64, error -71` |
| Gatilho | ~2 s de ociosidade do device | ociosidade do **controlador** (C-state / Power Supply Idle) |
| Escopo | um device | barramento inteiro (derruba vizinhos) |
| Cobertura Hefesto | **sim** — `72-ps5-controller-autosuspend.rules` (ADR-013) | **não** |
| Correção real | `power/control=on`, `autosuspend_delay_ms=-1` | **BIOS**: Power Supply Idle → *Typical Current Idle* |

O `usbcore.autosuspend=-1` global observado na máquina **não** é do Hefesto — é
do toolchain pessoal da mantenedora (ritual Aurora self-heal, dono do kernel
cmdline e das `99-usb-*.rules`). O Hefesto deliberadamente *não* mexe em cmdline
nem em tunável global; ver [[018-usb-power-scope-vs-dropout]].

Por que o C-state runtime / autosuspend não resolve o `-71`: o `-71` nasce do
controlador inteiro entrando em estado de baixa energia (Power Supply Idle
Control no AGESA), e o ajuste runtime per-device não alcança esse nível — é uma
decisão de firmware/BIOS. Confirmação cruzada com o histórico da mantenedora
(reset loop `-71` no Ryzen, derrubando também teclado/mouse no mesmo barramento).

## 3. WirePlumber: o fix rebaixa, mas não pode vencer a escassez

### 3.1 O que foi observado

Estado após `fix_wireplumber_default_source.sh --install` + `wpctl set-default`
para a onboard + `systemctl --user restart wireplumber`:

```
pactl get-default-source        -> alsa_input.usb-...DualSense...iec958-stereo   (!!)
wpctl status (Sources, '*')     -> * DualSense  /  (onboard sem '*')
state default.configured...source -> alsa_input.pci-0000_0c_00.4.analog-stereo  (onboard)
```

Ou seja: a **preferência** (`configured`) passou a apontar para a onboard, mas o
default **ativo** voltou ao DualSense no restart.

### 3.2 Por quê — prioridades

```
wpctl inspect <DualSense>:  priority.session = 50   priority.driver = 50   node.dont-reconnect = true
wpctl inspect <onboard>:    priority.session = 2009 priority.driver = 2009
```

O drop-in `51-hefesto-dualsense-no-default-source.conf` **pegou** (DualSense em
50, abaixo de tudo). A onboard tem prioridade 2009, altíssima. Pela lógica de
prioridade, a onboard deveria ganhar — **mas não ganhou**. A única explicação
consistente: a onboard (jack de mic frontal `front:2`) está **indisponível**
como fonte de captura real (nada plugado no jack), e a **webcam C920 — o mic
real da mantenedora — estava desconectada** (`lsusb` confirma ausência). Restou
o DualSense como **a única fonte de captura available**, e o WirePlumber, por
design, usa o que existe.

### 3.3 Implicações

1. **O rebaixamento está correto e funciona** — quando há outra fonte
   *available* (webcam plugada, ou jack onboard com mic), ela vence o DualSense
   (50) com folga. O sintoma "o controle vira o microfone" some assim que a
   webcam volta.
2. **"Rebaixar" não pode resolver o caso de escassez.** Se o DualSense é o único
   mic, nenhuma prioridade o desbanca — é degradação graciosa esperada, não bug.
3. **Mas o relatório é desonesto.** O script imprime "fonte padrão reeleita
   para o id N" e segue; e `doctor.sh check_wireplumber_source` inspeciona
   `~/.local/state/wireplumber/default-nodes` (a chave `configured`) em vez de
   `pactl get-default-source` (o ativo). Resultado: pode aparecer
   `[ OK ] WirePlumber não fixa o DualSense` enquanto o controle É o mic ativo.
   → `BUG-WIREPLUMBER-FIX-FALSE-SUCCESS-01`.
4. **Quem quer paz independente de webcam precisa desabilitar, não rebaixar.** O
   drop-in já documenta a variante `node.disabled = true` (comentada). Falta
   expô-la como modo opt-in. → `FEAT-WIREPLUMBER-DISABLE-SOURCE-MODE-01` e a
   decisão [[019-wireplumber-default-active-not-configured]].

### 3.4 Relação com a sprint original

`FEAT-WIREPLUMBER-DUALSENSE-NOT-DEFAULT-SOURCE-01` está marcada **DONE**, porém:
- O critério de aceite *"Após o fix, `wpctl status` mostra `Audio/Source` !=
  DualSense"* **não se sustenta** quando o DualSense é a única fonte.
- A própria "Nota para o executor" da sprint **antecipou** este risco: *"Se o WP
  0.5.12 ainda promover o DualSense, ajustar os `update-props` (o reset da chave
  persistida é o efeito imediato garantido)."* — o "efeito imediato garantido"
  é justamente o `configured`, que não é o ativo.

A FEAT não precisa ser reaberta: o rebaixamento é a decisão correta. O que falta
é (i) honestidade de relatório, (ii) checagem do ativo no doctor, (iii) o modo
disable opt-in.

## 4. Estado de mitigação do dropout no momento da coleta

- BIOS: Power Supply Idle já em *Typical Current Idle* (confirmado pela
  mantenedora — "já estava tudo ativado").
- `usbcore.autosuspend=-1` global ativo (Aurora).
- Boot atual: **0** ocorrências de `error -71` em ~23 min de uptime.
- Vigia ad-hoc montado na sessão: `journalctl -kf -o cat --since now | grep -m1
  -iE 'error -71|device descriptor read/64, error|not accepting address|device
  not responding'` — termina (e notifica) no primeiro sinal de dropout. Vira o
  modo `--watch-dropout` na sprint `FEAT-DOCTOR-USB-DROPOUT-DIAGNOSTIC-01`.

## 5. Recomendações acionáveis (ordem de custo)

1. **Continuar com o ajuste de BIOS** (Power Supply Idle → *Typical Current
   Idle*) — única correção de causa-raiz do `-71`. Já aplicado.
2. **Se o `-71` reaparecer: mover o controle para uma porta do controlador do
   chipset** (`02:00.0`, onde teclado/mouse convivem sem dropout). Preferir porta
   USB 2.0 traseira; confirmar via `lsusb -t` que mudou de Bus.
3. **Bluetooth como plano B** — `hid_playstation` suporta DualSense por BT sem o
   Hefesto, e o BT também remove o mic-USB do controle (mata o problema da §3 de
   brinde). Ressalva: o dongle BT está no mesmo controlador Matisse.
4. **Para o mic:** manter o rebaixamento (default) e plugar a webcam; ou optar
   pelo modo disable quando a webcam não for garantida.

## 6. Não-objetivos

- Hefesto **não** vai mexer em kernel cmdline, `99-usb-*.rules` ou tunável
  global `usbcore.autosuspend` — território do usuário/BIOS/Aurora
  ([[018-usb-power-scope-vs-dropout]]).
- Hefesto **não** vai tentar "consertar" o `-71` em runtime — não há alavanca de
  software para Power Supply Idle Control. O papel do daemon/doctor é
  **diagnosticar e recomendar**, não corrigir.
- Política de *sink* (saída de áudio) do DualSense permanece fora de escopo (como
  na FEAT original) — o foco é a *source* (microfone).
