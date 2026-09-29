# O BlueZ corrigido

O BlueZ do Ubuntu 24.04 e do Pop!_OS 24.04 é o 5.72, que trava com vários
controles pelo Bluetooth. O Hefesto oferece um BlueZ 5.86 com duas correções
próprias. O instalador e o `hefesto-dualsense4unix doctor` mandam para cá
quando o BlueZ da máquina não as tem.

## Em uma linha

```bash
scripts/construir_bluez_backport.sh
```

Constrói o `5.86-0ubuntu0.1~hefesto24.04.4` e entrega `libbluetooth3`, `bluez`
e `bluez-cups`, com o `SHA256SUMS`, em
`~/.cache/hefesto-dualsense4unix/bluez-backport/`, onde o instalador procura.
**Não instala nada e não usa sudo.** Com as dependências de build presentes,
leva uns três minutos. Depois, rode `./install.sh` de novo.

## De onde vem cada peça

| Peça | De onde | Quem fixa |
|---|---|---|
| o BlueZ 5.86 | `kernel.org/pub/linux/bluetooth/` | SHA-256 em `assets/bluez-backport/BASELINE` |
| o empacotamento `5.85-4ubuntu0.1` do Ubuntu 26.04 | Launchpad | SHA-256 em `assets/bluez-backport/BASELINE` |
| as correções `hefesto-NNNN` | `assets/bluez-backport/patches/` | o SHA-256 do `device.c` que cada revisão produz, no `BASELINE` |
| o changelog das revisões | `assets/bluez-backport/debian/changelog.hefesto` | a versão alvo, conferida pelo `dpkg-parsechangelog` |

O empacotamento do 5.85 pede três ajustes para servir ao 5.86, e o script os
faz, parando se não achar o alvo de algum: o patch
`0013-transport-Fix-set-volume-failure-with-invalid-device.patch` sai da
`series` (a API de volume foi refeita no 5.86), o `btmgmt.1` sai do
`debian/bluez.manpages` (o 5.86 não o gera) e seis páginas de manual novas
entram nele.

## As duas correções

### `hefesto-0001-input-keep-bond-on-virtual-cable-unplug.patch`

Em `profiles/input/device.c`, `virtual_cable_unplug()`. O Pro Controller e o
8BitDo mandam um «Virtual Cable Unplug» ao desligar, e o BlueZ apagava o
pareamento a cada queda. A correção mantém o pareamento e o aparelho.
`BLUEZ_HID_UNPLUG_REMOVES_BOND=1` no ambiente do serviço devolve o
comportamento original.

### `hefesto-0002-input-drop-report-on-eagain.patch`

Em `profiles/input/device.c`, nas funções `hidp_send_*`. Com o buffer de envio
do Bluetooth cheio por um instante, a escrita devolve EAGAIN, e o BlueZ
original respondia desconectando o controle: **um engasgo derrubava o
controle**. Com a correção:

- com EAGAIN, **aquele relatório é descartado e contado, e o controle fica**.
  Vale para a saída e para os pedidos `SET_REPORT` e `GET_REPORT`, que
  continuam respondendo EIO ao kernel;
- o diário ganha no máximo uma linha por segundo por aparelho, com o total:
  `BT socket write error: Resource temporarily unavailable (11): report dropped, 1001 so far`;
- com erro definitivo (ENOTCONN, EPIPE, ECONNRESET, escrita parcial, canal
  ausente) nada muda: o controle cai como antes.

Para ver os descartes: `journalctl -u bluetooth | grep 'report dropped'`.

## As revisões

| Versão | O que tem |
|---|---|
| `~hefesto24.04.1` | o 5.86 sobre o empacotamento do 26.04 |
| `~hefesto24.04.2` | mais o `hefesto-0001`, mantendo o pareamento |
| `~hefesto24.04.3` | o `hefesto-0001` também mantém o aparelho; reconstrói com `--revisao 3` |
| `~hefesto24.04.4` | mais o `hefesto-0002`; é a que o script constrói |

## O que o script faz

1. baixa o BlueZ e o empacotamento e confere os dois SHA-256, com tempo máximo
   para cada download;
2. monta a árvore do zero em `~/.cache/hefesto-dualsense4unix/bluez-obra/`
   (duas corridas dão a mesma árvore);
3. aplica a série com o `dpkg-source`, sem tolerância, e confere o hash do
   `device.c`;
4. prova o `hefesto-0002` no fonte baixado ([A prova sem rádio](#a-prova-sem-rádio));
5. confere as dependências de build com o `dpkg-checkbuilddeps`;
6. roda `dpkg-buildpackage -b -us -uc` e o `make check` do BlueZ;
7. entrega os três `.deb`, o `SHA256SUMS` e um `ORIGEM.txt` com os hashes de
   tudo o que entrou, e confere no `bluetoothd` construído a marca de cada
   correção.

| Opção | O que faz |
|---|---|
| (nenhuma) | constrói a última revisão; se ela já está no cache e confere, sai sem baixar nem compilar |
| `--forcar` | reconstrói mesmo pronto |
| `--sem-unit` | pula o `make check` |
| `--preparar` | só os passos 1 a 4 |
| `--mordida ARQ` | só o passo 4, sobre o `device.c` indicado |
| `--revisao N` | uma revisão antiga; exige `HEFESTO_BLUEZ_CACHE` apontando para fora do cache que o instalador lê |
| `HEFESTO_BLUEZ_JOBS=N` | compila com N processos (o padrão é um por núcleo) |

Códigos de saída: 0 certo · 2 uso · 3 falta dependência · 4 fonte não confere ·
5 a série não aplica · 6 a prova falhou · 7 build · 8 teste do BlueZ.

## Dependências de build

Se faltar alguma, o script lista o que o `dpkg-checkbuilddeps` disse e sai com
3. Instale e rode de novo:

```bash
cd ~/.cache/hefesto-dualsense4unix/bluez-obra/bluez-5.86
sudo mk-build-deps -ir debian/control
```

## A prova sem rádio

`assets/bluez-backport/prova/eagain.c` recorta do `device.c` a
`struct input_device` e as `hidp_send_*`, e as roda contra um `socketpair` não
bloqueante, cheio até o kernel devolver EAGAIN, o mesmo erro do Bluetooth:

| Cenário | BlueZ 5.86 original | com o `hefesto-0002` |
|---|---|---|
| 1001 saídas com o buffer cheio | desconectado 1001 vezes, 1001 linhas no diário | nenhuma desconexão, 1001 descartes, 2 linhas |
| `SET_REPORT` / `GET_REPORT` com o buffer cheio | desconectado | fica; o kernel recebe EIO |
| EPIPE, ENOTCONN, sem canal | desconectado | desconectado |

```bash
scripts/construir_bluez_backport.sh --mordida tests/fixtures/bluez-5.86/device.c
```

O `tests/fixtures/bluez-5.86/device.c` é o do BlueZ 5.86, byte a byte, e
`tests/unit/test_o_backport_do_bluez_e_reproduzivel.py` confere a série, os
hashes, a árvore sem rede e a prova.

Dos 38 testes do BlueZ, o `unit/test-mesh-crypto` reprova numa máquina que
desliga o `algif_aead` do kernel (a mitigação do CVE-2026-31431),
porque o AES-CCM pela AF_ALG some. O teste não toca o `profiles/input`. O
script só o perdoa depois de conferir, na hora, que o `algif_aead` está
ausente, e diz «NÃO MEDIDO»; qualquer outra falha reprova.

## Instalar

Quem instala é o `./install.sh`. Ele confere as marcas das correções no
`bluetoothd` que está rodando; se faltar alguma, ou se a versão estiver abaixo
do alvo, confere o `SHA256SUMS`, grava as versões anteriores em
`VERSOES-ANTERIORES.txt` (é por elas que o `./uninstall.sh --restore-bluez`
volta) e instala os três `.deb` juntos. A instalação reinicia o Bluetooth, e os
controles caem até reconectar.

Para relatar um travamento do `bluetoothd` ao BlueZ, mande o backtrace
(`coredumpctl info`), nunca o arquivo de core: ele carrega as chaves de todos os
aparelhos pareados. O core nunca sai da máquina.

O estudo que levou a este BlueZ está em
[docs/history](../history/2026-07-19-o-estudo-do-bluetoothd-5.72-e-o-plano-do-backport.md).
