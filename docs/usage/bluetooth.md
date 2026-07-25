# Bluetooth

O Hefesto trata USB e Bluetooth do mesmo jeito — o backend é agnóstico ao
transporte. Lightbar, gatilhos adaptativos, vibração, LED de microfone e LEDs de
jogador funcionam nos dois. A diferença é o pareamento inicial, que ainda é
manual: não há tela dedicada na janela.

## Parear um DualSense

```bash
bluetoothctl
# dentro do prompt:
power on
agent on
default-agent
scan on
# no controle: segure PS + Create por ~3 s até a barra de luz piscar rápido
# espere a entrada "Wireless Controller" aparecer com o endereço MAC
pair  AA:BB:CC:DD:EE:FF      # troque pelo endereço que apareceu
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
exit
```

Depois de pareado, o daemon detecta em até 5 segundos. Para conferir:

```bash
hefesto-dualsense4unix status
#   connected  = True
#   transport  = bt
```

Nas próximas sessões basta ligar o controle com um toque no PS — o `bluetoothd`
reaproveita o `trust` salvo.

## O que o instalador faz pelo Bluetooth

Com os padrões de fábrica, o `install.sh` deixa no sistema:

- Dois drop-ins do BlueZ: conexão mais rápida (`FastConnectable`) e
  re-pareamento sem confirmação (`JustWorksRepairing`).
- Um drop-in de modprobe que impede o adaptador USB de dormir no meio do jogo.
- Um agente Bluetooth de sistema.
- Dois timers: um que **fotografa os pareamentos** e outro de vigia de saúde da
  conexão. As fotos ficam em `/var/lib/hefesto-dualsense4unix/bt-bonds/`.
- Uma regra udev que tira uma foto extra **na borda de cada conexão nova** — sem
  ela, um pareamento feito logo depois de uma foto ficaria sem cópia até o
  próximo ciclo do timer.

Tudo isso sai com o `uninstall.sh`.

## Limitação conhecida: o `bluetoothd` derruba pareamentos

Esta é a limitação mais séria do projeto hoje, e ela **não é nossa** — é
corrupção de heap no `bluetoothd`:

```
malloc_consolidate(): unaligned fastbin chunk detected
bluetooth.service: Main process exited, code=dumped, status=6/ABRT
```

Quando isso acontece, o serviço reinicia e **pareamentos desaparecem**. O sintoma
que você vê é o controle acendendo, tentando conectar e desistindo: no log,
`Refusing input device connect` / `unknown device`. De fora parece "o controle
desconecta sozinho" ou "conecta e desliga".

**O gatilho medido** foi a reconexão de dois controles Nintendo-class em poucos
segundos — o Pro Controller genuíno e um 8BitDo em modo Switch, que se apresenta
com o mesmo VID:PID e o mesmo nome do genuíno. Isso pertence à família de um
problema aberto no BlueZ ("random crash on device reconnect"), e a pesquisa do
projeto **não encontrou correção upstream** para a corrupção de heap na via
kernel-HIDP. Nós não temos como consertar isso a partir daqui.

**O que dá para fazer:**

- Não ligue dois controles Nintendo-class na mesma janela de segundos. Ligue um,
  espere ele adotar, e só então o outro.
- As fotos de pareamento existem exatamente para este caso. O restaurador
  (`bt_bonds_restore.sh`) é **manual por decisão de projeto**: se o controle já
  girou a própria chave, reimpor a chave antiga gera um laço de falha de
  autenticação — a mesma classe de gatilho do crash. Quem decide restaurar é você.
- Se acontecer, re-parear pelo `bluetoothctl` sempre resolve.

## Limitação conhecida: 8BitDo por Bluetooth

O 8BitDo SN30 Pro conecta, mas cai sob carga sustentada por Bluetooth. O caminho
confiável para ele hoje é **o cabo**. O histórico da investigação está em
[`troubleshooting-8bitdo.md`](troubleshooting-8bitdo.md).

## Fora de escopo

Áudio do DualSense por Bluetooth (fone e microfone do controle sem fio) usa
protocolo proprietário e continua fora de escopo. Por USB o áudio funciona.
