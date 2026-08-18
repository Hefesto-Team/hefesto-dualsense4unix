# ADR-020: o backend deixou de ser um só — seis camadas falam com o aparelho

**Status:** aceito · **Data:** 2026-08-13
**Emenda:** [ADR-001](001-pydualsense-backend.md) (`pydualsense` como backend HID)

## Contexto

O [ADR-001](001-pydualsense-backend.md) escolheu `pydualsense` como **o**
backend HID e isolou a escolha atrás de uma interface `IController`, *"para
permitir troca futura sem reescrever daemon"*. Foi a decisão certa — e é ela
que tornou possível tudo o que veio depois. Mas quem lê o 001 hoje sai com o
retrato de um produto que **não existe mais**: uma biblioteca Python falando
sozinha com o controle.

Não foi uma troca. Foi um **acréscimo**, camada por camada, cada uma nascida de
um defeito que a anterior não sabia curar:

- o kernel assume o DualSense como joystick, e aí a `pydualsense` **não recebe
  input nenhum** (`src/hefesto_dualsense4unix/core/evdev_reader.py`);
- o report `0x31` que a `pydualsense` monta para Bluetooth é **malformado** — o
  firmware o descarta, e era isso o *"a cor nunca funcionou por BT"*
  (`src/hefesto_dualsense4unix/core/ds_output_report.py`);
- a lightbar e os LEDs de jogador têm **dono no kernel**, e escrever por hidraw
  disputa com ele (`src/hefesto_dualsense4unix/core/sysfs_leds.py`);
- um gamepad virtual de `evdev` **não tem hidraw**, então o SDL não vibra por
  ele (`src/hefesto_dualsense4unix/integrations/uhid_gamepad.py`);
- daemon, Steam e o jogo rodam com o **mesmo uid**, então nada no DAC separa
  quem pode abrir o hidraw do controle físico
  (`src/hefesto_dualsense4unix/broker/hidraw_broker.py`);
- e há defeito que **só se cura dentro do driver** — probe que morre e joga o
  controle inteiro fora (`assets/dkms/`).

`IController` continua no lugar
(`src/hefesto_dualsense4unix/core/controller.py`), com
`PyDualSenseController` como a implementação real e `FakeController`
(`src/hefesto_dualsense4unix/testing/fake_controller.py`) como o dublê da
suíte. O que caducou não é a arquitetura: é a frase *"o backend é a
`pydualsense`"*.

## Decisão

Registrar, como retrato vigente, que o produto fala com o hardware por **seis
camadas**, e que nenhuma delas substitui as outras:

| camada | onde mora | o que ela faz, e por que existe |
|---|---|---|
| **hidraw / `pydualsense`** | `core/backend_pydualsense.py` | o caminho de OUTPUT (gatilhos, vibração, luz, LED do mic). Usa uma subclasse fixada (`_PinnedPyDualSense`) que abre **por caminho** de hidraw, para não depender da varredura da biblioteca |
| **o report OUT montado aqui** | `core/ds_output_report.py` | o buffer `0x02` (USB) e `0x31` (BT) é montado por nós e validado contra o `hid-playstation` do **kernel**, nunca contra a `pydualsense` |
| **evdev** | `core/evdev_reader.py` | o INPUT. Quando o kernel assume o controle, é ele quem tem os eventos — a `pydualsense` fica muda |
| **sysfs LED class** | `core/sysfs_leds.py` | lightbar e LEDs de jogador pelos nós do kernel, que monta o report certo em USB **e** em BT. É a rota que a `regra 77` do udev habilita |
| **uhid** | `integrations/uhid_gamepad.py` | o controle **virtual** é um device HID de verdade: o `hid_playstation` faz bind nele e constrói o DualSense inteiro — touchpad, giroscópio, bateria, hidraw para o SDL vibrar |
| **broker root** | `broker/hidraw_broker.py` | o primeiro serviço de **sistema** do projeto. Esconde e devolve o hidraw do controle físico, e entrega o fd já aberto por `SCM_RIGHTS` |
| **DKMS** | `assets/dkms/` | `hid-nintendo`, `hid-playstation` e `rtw88-usb` patchados. O que morre na probe do driver não tem cura em Python |

E fixar a regra que segue disso: **antes de afirmar que uma feature funciona,
olhe por qual camada ela passa** — a matriz de canais
(`docs/data/mapa-controles.csv`, e o `specs.html` que ela gera) existe
exatamente porque a mesma feature tem sorte diferente em cada uma, e por
transporte.

## Consequências

- **O [ADR-001](001-pydualsense-backend.md) fica EMENDADO, não superado.** A
  decisão de isolar o backend atrás de `IController` continua valendo e foi ela
  que permitiu esta migração acontecer sem reescrever o daemon. Quem for lê-lo
  encontra a nota que aponta para cá.
- **"Trocar de backend" deixou de ser uma operação única.** A pergunta útil
  passou a ser *"qual camada"*: trocar a `pydualsense` não toca no evdev, no
  sysfs, no uhid nem no broker.
- **O produto passou a instalar coisa fora do `HOME`** — serviço de sistema e
  módulos DKMS. É o preço das duas últimas linhas da tabela, e é o que faz o
  `install.sh` precisar de `sudo` **em passos**, pedindo a senha sozinho, em
  vez de ser rodado inteiro como root (rodá-lo com `sudo` faz o `HOME` virar
  `/root`, e a instalação não existe para quem vai jogar).
- **A dependência do kernel virou explícita.** Três camadas — evdev, sysfs LED
  class e uhid — só entregam com o `hid_playstation` carregado. Sem ele o
  daemon sobe e as features somem; por isso o `scripts/doctor.sh` avisa em vez
  de falhar.
