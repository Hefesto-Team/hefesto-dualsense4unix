# Toque e movimento nos emuladores, pelo servidor DSU

O Hefesto fala o protocolo DSU (cemuhook) em `127.0.0.1:26760`. É por ele que o
Azahar recebe o touchpad do DualSense como a tela de baixo do 3DS e o giro sem
depender do SDL; o Dolphin e o Cemu leem o mesmo servidor. O protocolo está em
[docs/protocol/o-protocolo-dsu.md](../protocol/o-protocolo-dsu.md) e a decisão da porta na
[ADR-022](../adr/022-udp-26760-compat-dsu.md).

## No Hefesto

Nada: o servidor nasce ligado. O número do jogador é o slot (jogador 1 é o
slot 0, e assim por diante); o controle em «Controlar o PC» não publica. Para
desligar, ponha no `~/.config/hefesto-dualsense4unix/maquina.json`:

```json
"servidor_dsu": {"ligado": false}
```

e reinicie o serviço: `systemctl --user restart hefesto-dualsense4unix.service`.
A porta também se troca ali (`"porta": 26760`). Se outro programa já ocupa a
porta (um evdevhook2, um DS4Windows sob Wine), o Hefesto sobe sem o servidor e
o diagnóstico diz de quem é a porta.

**Enquanto um emulador escuta, o dedo no touchpad não move o cursor do PC**:
o Hefesto segura o nó do touchpad para o jogo. Cinco segundos depois que o
emulador para de pedir, o cursor volta.

## No Azahar, à mão (o caminho canônico)

Com o Azahar FECHADO, faça a cópia
(`cp ~/.config/azahar-emu/qt-config.ini ~/.config/azahar-emu/qt-config.ini.antes-do-dsu`)
e, na seção `[Controls]`, **substitua** as linhas do `profiles\1\…` que já
existem, sem acrescentar outras:

```ini
profiles\1\motion_device="engine:cemuhookudp"
profiles\1\motion_device\default=false
profiles\1\touch_device="engine:cemuhookudp,max_x:1920,max_y:1080,min_x:0,min_y:0"
profiles\1\touch_device\default=false
profiles\1\udp_input_address=127.0.0.1
profiles\1\udp_input_address\default=false
profiles\1\udp_input_port=26760
profiles\1\udp_input_port\default=false
profiles\1\udp_pad_index=0
profiles\1\udp_pad_index\default=false
profiles\1\use_touchpad=false
profiles\1\use_touchpad\default=false
```

Cada chave leva `\default=false`, senão o Azahar lê o padrão. O máximo é
1920 por 1080, e não 1919 por 1079 (com o máximo no último valor, a borda vira
x = 320, fora da tela). Sem esses campos vale o do DS4, de (100, 50) a (1800,
850), e os 21% de baixo do touchpad morrem. Para o jogador 2, `udp_pad_index=1`.

**Pela interface** (Emulation, Configure, Controls, Motion / Touch):

1. `Motion Provider` e `Touch Provider` = `CemuhookUDP`.
2. `Server` = `127.0.0.1`. Não use `localhost`: não é IPv4 literal, e o Azahar
   registra erro e cai em `0.0.0.0`.
3. `Port` = `26760`; `Pad N` para o jogador N.
4. `Use controller touchpad` DESMARCADO.
5. `Test` responde em até 8 segundos; `OK` recarrega.

**NÃO rode `Calibration: Configure`**: ela grava como máximo o primeiro ponto
que passa de 100 unidades nos dois eixos, e todo toque além vira x = 320 ou
y = 240. Se calibrou, feche o Azahar e ponha 1920 e 1080 no ini.

**O que muda para quem joga:** o mouse na janela deixa de tocar a tela de
baixo (com o toque no DSU, o Azahar só cai para o toque por botão); o toque por
botão continua. Os botões seguem o mapeamento do Azahar, que não vem deste
servidor: o servidor manda botões neutros.

## No Dolphin

`Controllers`, `Alternate Input Sources`, `DSU Client`: `Server IP` =
`127.0.0.1`, `Port` = `26760`. Os controles aparecem como `DSUClient/0/` e
seguintes, com o toque e o movimento. O Dolphin recria o controle quando muda o
modelo ou a conexão, e o Hefesto os mantém fixos (modelo completo, USB) por
isso, mesmo quando o controle real está no rádio.

## No Cemu

`Options`, `Input settings`, API `DSUController`: `IP` = `127.0.0.1`, `Port` =
`26760`, e o controle do slot desejado. O Cemu descarta pacote com carimbo de
tempo que recua, e o Hefesto garante o carimbo crescente por slot.

## Como conferir sem o emulador

```bash
python3 scripts/ensaios/o_dsu_chega_ao_emulador.py --slot 0 --segundos 10
```

O ensaio é um cliente que pede versão, portas e dados e confere: o dono da
porta, a versão 1001, o MAC do slot, pelo menos 8 pacotes por segundo, o
contador crescente e a aceleração perto de 1 g com o controle parado.

## O que este servidor não faz

Vibração (os tipos de motor do protocolo), bateria, controles externos
(8BitDo, Pro Controller), `0.0.0.0` e IPv6, e a tela do servidor na interface.
