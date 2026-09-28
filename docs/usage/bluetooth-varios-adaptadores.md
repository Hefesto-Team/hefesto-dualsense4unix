# Vários controles por Bluetooth

Como dividir vários DualSense com microfone entre adaptadores Bluetooth, e por
que um adaptador só não comporta cinco controles ao mesmo tempo.

---

## 1. O problema, em uma frase

Bluetooth Classic tem **1.600 slots de tempo por segundo**, e todos os
dispositivos de um mesmo adaptador dividem esses slots. O que falta não é banda
de dados, é vez de falar.

Tudo nesta página decorre disso.

---

## 2. A conta que decide tudo

Medição do projeto, no mesmo controle, com o microfone desligado e ligado
(`daemon/subsystems/bt_mic.py`):

```
mic DESLIGADO   : input 260.4 Hz   audio   0.0 Hz   total 260.4 Hz
mic LIGADO      : input 170.5 Hz   audio 106.2 Hz   total 276.7 Hz
desligado again : input 274.3 Hz   audio   0.0 Hz   total 274.6 Hz
```

O total de pacotes por segundo não se move. O áudio não abre canal novo: ele
ocupa lugar na mesma fila. O gargalo é slot de tempo.

Daí a aritmética:

```
5 controles × 277 pacotes/s   ≈  1.385 transações/s
Um adaptador Bluetooth Classic ≈  1.600 slots/s

→ um adaptador só não comporta cinco controles com microfone.
→ três adaptadores = três piconets = 4.800 slots/s.
```

Com três adaptadores dá para dividir 2 / 2 / 1 e ainda deixar um teclado
Bluetooth fora da disputa com os controles. Teclado e mouse com receptor
próprio de 2,4 GHz não usam o Bluetooth do computador e não entram na conta.

O microfone do DualSense trafega dentro do canal HID, e não por HFP/SCO. Se
fosse SCO, a especificação limitaria a 3 links por piconet, e quatro microfones
ao mesmo tempo seriam impossíveis com qualquer hardware. Sendo HID, o limite é
o número de slots, e mais adaptadores resolvem.

---

## 3. Distribuir os controles entre os adaptadores

O BlueZ não balanceia carga. Cada pareamento fica preso ao adaptador em que foi
criado, em `/var/lib/bluetooth/<endereço do adaptador>/<endereço do controle>/`,
e o controle sempre reconecta onde tem a chave de enlace. Ligar um segundo
adaptador não move ninguém sozinho.

### 3.1 Nunca use `hciN` como identidade

A numeração `hci0`/`hci1` pode inverter entre boots, conforme a ordem de
enumeração USB. Use sempre o endereço do adaptador (BD Address), que é estável.

### 3.2 Descobrir quem é quem

```bash
bluetoothctl list
# Controller XX:XX:XX:XX:XX:XX <nome> [default]
# Controller YY:YY:YY:YY:YY:YY <nome>
```

Com adaptadores idênticos, o endereço é a única forma de distinguir um do
outro. Anote qual endereço ficou em qual porta.

### 3.3 Migrar um controle

```bash
# 1. Tirar do adaptador antigo, com o cache junto
bluetoothctl select <ENDERECO_DO_ADAPTADOR_ANTIGO>
bluetoothctl remove <ENDERECO_DO_CONTROLE>
sudo rm -f /var/lib/bluetooth/*/cache/<ENDERECO_DO_CONTROLE>

# 2. Parear no adaptador de destino, com o controle em PS + Create
bluetoothctl
> select <ENDERECO_DO_ADAPTADOR_DESTINO>
> scan on
> pair <ENDERECO_DO_CONTROLE>
> trust <ENDERECO_DO_CONTROLE>
> scan off
```

Apagar o cache é parte do gesto. Sem isso, o pareamento novo nasce com o
registro SDP vazio e o BlueZ recusa a reconexão como *unknown device*: o link
cai sozinho e parece defeito do controle. O `scripts/doctor.sh` avisa quando um
controle tem pareamento sem registro SDP.

O PS + Create é obrigatório porque ninguém construiu a alternativa, e não
porque o firmware a proíba. O feature report `0x0A` «Set Bluetooth Pairing»
grava o host e a chave de enlace no controle pelo cabo
([dualsense-plataforma-e-identidade.md §3](../protocol/dualsense-plataforma-e-identidade.md)).
Ele nunca foi medido no aparelho, não está implementado, e o próprio documento
desaconselha a escrita.

### 3.4 Divisão sugerida

Divida pelo microfone, que é o que pesa:

| Adaptador | Ocupantes |
|---|---|
| 1 | Controles 1 e 2, com microfone |
| 2 | Controles 3 e 4, com microfone |
| 3 | Controle 5 e o teclado Bluetooth |

Cada par com microfone consome cerca de 554 transações/s de 1.600, um terço do
adaptador. Os três adaptadores podem ficar no mesmo hub USB, desde que ele
tenha fonte própria e haja portas vazias entre eles.

---

## 4. O que o software já resolve

O daemon não depende do adaptador: ele acha os controles por `hidraw` e
`bustype`, sem `hci0` fixo no código Python. Um controle pareado em qualquer
adaptador funciona sem mudar nada no Hefesto.

Vale conferir, uma vez, que o sistema não atrapalha:

| Item | Esperado |
|---|---|
| Autosuspend USB do adaptador | desligado (`power/control = on`) |
| `btusb enable_autosuspend` | `N` |
| `FastConnectable` | `true` |
| `JustWorksRepairing` | `confirm` |
| `hid-playstation` | presente |
| Firmware do adaptador | carrega sem erro no `dmesg` |

---

## 5. Quando der problema

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Desconexão aleatória, nada no log | Queda de tensão no hub | Use um hub com fonte própria |
| Um adaptador some do `bluetoothctl list` | `btusb` sensível a hub | Ligue esse adaptador direto no computador |
| Controle não reconecta, vira *unknown device* | Cache SDP sujo | Apague o cache e pareie de novo (§3.3) |
| A entrada engasga só com o microfone ligado | Adaptador saturado | Mova um controle para outro adaptador (§3.4) |
| Mouse ou teclado falhando | Dois receptores de 2,4 GHz colados | Afaste os receptores |
| Tudo pior depois de um reboot | `hciN` inverteu | Confira pelo endereço, não pelo índice (§3.1) |

### Medir em vez de adivinhar

Compare os reports por segundo de um controle sozinho com os de todos os
controles ligados. Se cair muito abaixo dos ~170 Hz da medição de referência
com microfone ligado, o adaptador daquele controle está cheio, e a cura é
redistribuir, não trocar hardware.
