# 8BitDo SN30 Pro — modos, identificação e a morte por Bluetooth

Uma página só, sobre UM controle: o 8BitDo SN30 Pro que convive com os DualSense
nesta máquina. O hefesto **não gerencia** esse controle — o daemon só abre
DualSense (filtro Sony `054c` no discovery) e é incapaz de tocar um device
Nintendo (`057e`). Esta página existe porque o controle divide a máquina com o
daemon e o `scripts/doctor.sh` sabe reconhecer a assinatura de morte dele.

Cada afirmação abaixo carrega o seu nível de prova: **PROVADO** (medido nesta
máquina em 2026-07-16), **HIPÓTESE** (plausível, não provada) ou
**EXPERIMENTO** (nunca exercitado aqui).

---

## O essencial

| Modo do controle | Identidade no kernel | Driver | Gyro | Nível de prova |
|---|---|---|---|---|
| Switch **por cabo** | `057e:2009` (bus `0003`) | `hid-nintendo` | sim¹ | **PROVADO estável** (instância USB sem um único timeout) |
| Switch por Bluetooth | `057e:2009` (bus `0005`) | `hid-nintendo` | sim¹ | **PROVADO instável** (mortes medidas em 2026-07-16, com e sem Steam) |
| X-input **por cabo** | `045e:028e` | `xpad` | não² | Xbox 360 real; estabilidade esperada, não medida |
| X-input por Bluetooth | `045e`, PID provável `02e0`/`02fd` | `hid-microsoft`/`hid-generic` | não² | **EXPERIMENTO** — `xpad` é USB-only (zero aliases `hid:`), nunca exercitado aqui |

¹ O gyro existe e é real (**PROVADO**: `using factory cal for IMU` + input
`Pro Controller (IMU)` com `ID_INPUT_ACCELEROMETER=1`) — mas só chega ao
**jogo** com Steam Input ativo; veja o conflito com o guard abaixo.
² Limitação do protocolo XInput (não tem canal de motion), não do controle.

**A única configuração provadamente estável é modo Switch POR CABO.** Para
entrar em X-input, liga-se o controle segurando `X+Start` (modo Switch:
`Y+Start`, segundo o manual da 8BitDo).

---

## Identificar o modo agora (sem sudo)

O controle **se apresenta com VID/PID de outra marca conforme o modo** — o que
não mente é o OUI do MAC. Nunca use um `eventN` decorado: os números renumeram
a cada replug; resolva sempre na hora, por VID:PID.

```bash
# 1) Que instâncias HID existem e com que driver? (bus 0003=cabo, 0005=Bluetooth)
for d in /sys/bus/hid/devices/*; do
  printf '%s driver=%s\n' "$(basename "$d")" "$(basename "$(readlink -f "$d/driver")")"
done
# 057e:2009 + driver=nintendo                  -> modo Switch
# 045e:028e + driver=xpad                      -> modo X-input por cabo
# 045e:02e0/02fd + hid-microsoft/hid-generic   -> modo X-input por Bluetooth
```

```bash
# 2) De quem é o hardware de verdade? (nome + MAC; o OUI do MAC identifica o dono)
grep -H . /sys/bus/hid/devices/*/uevent | grep -E 'HID_NAME|HID_UNIQ'
systemd-hwdb query "OUI:E417D8"
# => ID_OUI_FROM_DATABASE=8BITDO TECHNOLOGY HK LIMITED
# (troque E417D8 pelos 3 primeiros octetos do HID_UNIQ, sem os dois-pontos)
```

```bash
# 3) O node de input, resolvido por VID:PID (nunca eventN fixo)
for e in /sys/class/input/event*/device/id/vendor; do
  v="$(cat "$e")"; p="$(cat "${e%vendor}product")"
  [ "$v:$p" = "057e:2009" ] && echo "/dev/input/$(basename "${e%/device/id/vendor}")"
done
# confirme as propriedades udev do node encontrado:
#   udevadm info /dev/input/eventN
```

Detalhe do firmware (**PROVADO**): no bind aparece `unknown main item tag 0x0`
— descriptor HID malformado, típico de firmware clone; o original não produz
isso. É contexto, não defeito a consertar.

---

## A morte por Bluetooth (o controle "morre sem desconectar")

**PROVADO**: por Bluetooth, em modo Switch, o firmware clone engasga com o
protocolo de subcommands do `hid-nintendo`; o driver estoura o rate-limiter e
desiste — o input morre com o link BT ainda de pé (`bluetoothctl` segue
dizendo `Connected: yes`).

A assinatura no journal do kernel é a **CASCATA**, na MESMA instância hid:

```text
nintendo 0005:057E:2009.0014: timeout waiting for input report     (dezenas)
nintendo 0005:057E:2009.0014: joycon_enforce_subcmd_rate: exceeded max attempts
```

Duas honestidades importantes:

- **A linha isolada não é morte.** Houve `exceeded max attempts` medido que
  NÃO foi terminal (estourou na conexão e o controle viveu mais ~8 minutos).
  Só a cascata — série de timeouts culminando no `exceeded` — diagnostica.
- **A morte aconteceu SEM Steam rodando** (primeira morte às 12:38:46; Steam
  só subiu às 12:46:51). Portanto **fechar o Steam não é cura** de nada aqui.

Como olhar (sem sudo — o grupo `adm` dá acesso ao journal do kernel; o
`dmesg` cru é restrito nesta máquina por `kernel.dmesg_restrict=1`):

```bash
journalctl -b -k --no-pager | grep -aE 'nintendo|joycon'
```

O `scripts/doctor.sh` faz essa leitura sozinho: se o boot atual tiver a
cascata, ele imprime o diagnóstico citando a instância; com journal limpo (ou
só linhas isoladas), fica em silêncio.

O hefesto está fora da cadeia causal (**PROVADO no código**): filtro
Sony-only no discovery, zero referências a Nintendo/8BitDo em `src/`, e as
launch options de jogos não participam — as mortes foram em BT, fora de jogo.

---

## Gyro × Steam Input × o guard do hefesto (o conflito, com todas as letras)

O gyro do SN30 Pro só é exposto em modo Switch, e só chega ao **jogo** com o
**Steam Input ativo** para aquele app. Só que o hefesto trabalha contra isso,
de propósito: o `hefesto-steam-input-guard` reaplica Steam Input OFF, e jogos
já configurados podem ter `UseSteamControllerConfig=0` persistido — que
desliga o Steam Input do app para TODOS os controles.

Ou seja: **para ter gyro do 8BitDo num jogo, é preciso reativar o Steam Input
daquele jogo, sabendo que o guard do hefesto pode desfazer a escolha
sozinho.** Não há configuração que dê gyro + guard ao mesmo tempo hoje. Dito
isso, a escolha é sua — o hefesto não quebra o controle em nenhum dos casos;
ele só não participa.

---

## "Aparece como Xbox" — HIPÓTESE, não fato

O kernel **nunca viu** um device `045e`/xpad/Xbox no ciclo medido — o rótulo
"Xbox" que aparece em jogos vem de camada acima do kernel. Duas hipóteses,
nenhuma provada:

- **A**: o vpad XInput do Steam Input para o Pro Controller (conflita com o
  `UseSteamControllerConfig=0` persistido nos jogos onde o guard atuou);
- **B** (mais parcimoniosa): a ponte winebus/XInput do Proton, que apresenta
  QUALQUER controle como "Xbox 360" sem Steam Input nenhum.

Não conclua o modo do controle a partir do rótulo que o jogo mostra — use os
comandos da seção de identificação.

---

## Quem segura o hidraw (e por que isso é normal)

**PROVADO**: o Steam mantém aberto o hidraw de TODO controle suportado — o do
8BitDo E os dos DualSense saudáveis, mesmo com PSSupport desligado. **Fd
aberto é estado normal, não assinatura de conflito.** A sonda, se quiser ver
com os próprios olhos (só processos seus, sem sudo):

```bash
for pid in $(pgrep -x steam); do
  ls -l "/proc/$pid/fd" 2>/dev/null | grep -o 'hidraw[0-9]*' | sort -u \
    | sed "s|^|steam($pid) segura |"
done
```

**HIPÓTESE** (não provada; o contra-exemplo vivo são os DualSense, que
coabitam sem corromper): dois mestres escrevendo subcommands no mesmo hidraw
do clone (driver de Switch do Steam × `hid-nintendo`) poderiam agravar o
"descontrolado". Quem fecha ou derruba essa hipótese é a validação humana com
o modo escolhido — não um aviso automático.

---

## O que NÃO fazer

- **Não blackliste o `hid_nintendo`**: mata o controle para qualquer app fora
  do Steam — quebra em vez de proteger, com efeito colateral no sistema todo.
- **Não trate "fechar o Steam" como cura**: a morte por BT está provada sem
  Steam rodando.
- **Não culpe o hefesto nem launch options de jogos**: o daemon é incapaz de
  abrir devices `057e`, e as mortes aconteceram fora de jogo.
