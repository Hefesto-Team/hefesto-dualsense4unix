# O BlueZ corrigido

O BlueZ do Ubuntu 24.04 e do Pop!_OS 24.04 é o 5.72, que trava com vários
controles pelo Bluetooth. O Hefesto oferece um BlueZ 5.87 com duas correções
próprias e as correções de segurança que a distro publica. O instalador e o
`hefesto-dualsense4unix doctor` mandam para cá quando o BlueZ da máquina não as
tem.

## Em uma linha

```bash
scripts/construir_bluez_backport.sh
```

Constrói o `5.87-0ubuntu0.1~hefesto24.04.5` e entrega `libbluetooth3`, `bluez`
e `bluez-cups`, com o `SHA256SUMS`, em
`~/.cache/hefesto-dualsense4unix/bluez-backport/`, onde o instalador procura.
**Não instala nada e não usa sudo.** Com as dependências de build presentes,
leva uns três minutos. Depois, rode `./install.sh` de novo.

## De onde vem cada peça

| Peça | De onde | Quem fixa |
|---|---|---|
| o BlueZ 5.87 | `kernel.org/pub/linux/bluetooth/` | SHA-256 em `assets/bluez-backport/BASELINE` |
| o empacotamento `5.85-4ubuntu0.1` do Ubuntu 26.04 | Launchpad | SHA-256 em `assets/bluez-backport/BASELINE` |
| as correções da casa (`hefesto-0001` e `0002`) | `assets/bluez-backport/patches/` | o SHA-256 do `device.c` que cada revisão produz, no `BASELINE` |
| as correções do upstream (`hefesto-0003` em diante) | `git format-patch` do master do BlueZ | o commit e o SHA-256 de cada uma, na linha `UPSTREAM_` do `BASELINE` |
| o changelog das revisões | `assets/bluez-backport/debian/changelog.hefesto` | a versão alvo, conferida pelo `dpkg-parsechangelog` |

A revisão 3 e a 4 nasceram sobre o 5.86: as chaves com o sufixo `_R3` e `_R4`
do `BASELINE` guardam o que difere delas, e o script as lê antes da chave comum.

O empacotamento do 5.85 pede ajustes para servir ao 5.86 e ao 5.87, e o script
os faz:

1. o patch `0013-transport-Fix-set-volume-failure-with-invalid-device.patch`
   sai da `series` (a API de volume foi refeita no 5.86);
2. o `btmgmt.1` sai do `debian/bluez.manpages` (o 5.86 não o gera);
3. seis páginas de manual novas do 5.86 entram nele;
4. no 5.87, a linha de contexto do `ubuntu_error_restart.patch` ganha o
   `CAP_NET_RAW` que a unit do upstream passou a pedir (o que o patch muda, o
   `Restart=on-failure`, segue igual);
5. no 5.87, o `0012-src-device-Fix-stored-gatt-cache-DB-Hash-value-not-u.patch`
   sai da `series`, porque o upstream já o traz;
6. no 5.87, o pacote `bluez-hcidump` sai do `debian/control`, porque o upstream
   tirou o `hcidump` (o `btmon` segue no `bluez`);
7. no 5.87, a página `btsnoop.7` entra no `debian/bluez.manpages`.

Os três primeiros param o script se não acharem o alvo. Do quarto em diante,
cada um pergunta ao fonte se a mudança dele existe ali.

## As duas correções da casa

### `hefesto-0001-input-keep-bond-on-virtual-cable-unplug-5.87.patch`

Em `profiles/input/device.c`, `virtual_cable_unplug()`. O Pro Controller e o
8BitDo mandam um «Virtual Cable Unplug» ao desligar, e o BlueZ apagava o
pareamento a cada queda. A correção mantém o pareamento e o aparelho.
`BLUEZ_HID_UNPLUG_REMOVES_BOND=1` no ambiente do serviço devolve o
comportamento original. A versão `-5.87` é a mesma correção sobre o
`device_remove_bonding(…, BDADDR_BREDR)` do 5.87; a sem sufixo é a do 5.86,
que a revisão 3 e a 4 usam.

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

## As correções do upstream

O 5.87 é a estável mais nova, mas saiu antes de uma leva de consertos de
segurança do master. A revisão 5 leva os que tocam o que a distro já corrigiu,
cada um pelo patch do próprio commit:

| Patch | Commit | O que conserta |
|---|---|---|
| `hefesto-0003-adapter-Fix-crash-on-dev_disconnected.patch` | `5bc6aa79e` | o uso depois de liberar em `dev_disconnected` que o 5.87 trouxe |
| `hefesto-0004-a2dp-Fix-loading-of-remote-SEP-from-cache.patch` | `b7d71e506` | a regressão do cache SEP do A2DP |
| `hefesto-0005-sdp-xml-Fix-crash-caused-by-type-confusion-when-pars.patch` | `985e643d7` | CVE-2026-80185, o XML de SDP |
| `hefesto-0006-avrcp-Fix-Out-of-Bounds-Read-in-AVRCP-GetFolderItems.patch` | `bd8989620` | CVE-2026-75032, o `GetFolderItems` |
| `hefesto-0007-avrcp-Fix-media-folder-name-not-being-set.patch` | `580881498` | o nome da pasta que o 0006 deixa vazio |
| `hefesto-0008-eir-Fix-stack-buffer-overflow-when-parsing-the-remot.patch` | `381b5d0d2` | CVE-2026-80186, o nome remoto no EIR |
| `hefesto-0009-all-Fix-typo-in-AVRCP_ATTRIBUTE_ILEGAL.patch` | `73ccf6d83` | o nome que o 0011 usa (sem o `tools/parser`, que o tarball não traz) |
| `hefesto-0010-adapter-clear-discovery_found-list-before-discovery_.patch` | `7e3212fa2` | uso depois de liberar ao remover o adaptador |
| `hefesto-0011-avrcp-Fix-out-of-bounds-parsing-of-ListPlayerAttribu.patch` | `b21c216d5` | CVE-2026-85218, o `ListPlayerAttributes` |
| `hefesto-0012-avrcp-Fix-out-of-bounds-read-parsing-attribute-lists.patch` | `f0ddbc7aa` | as listas de atributos do AVRCP |
| `hefesto-0013-adapter-remove-the-devices-from-the-list-before-free.patch` | `eb82d81bf` | uso depois de liberar ao remover o adaptador (só o contexto muda no 5.87) |
| `hefesto-0014-adapter-Fix-crash-on-short-start-discovery-reply.patch` | `a734b0605` | a resposta curta do início da varredura |

O CVE-2026-19774 (a2dp, `912f5efb0`) já vem no 5.87.

O changelog da revisão escreve duas linhas que o doctor lê:

- `Leva do upstream: <commits>`: com o `5bc6aa79e` nela, o 5.87 da casa passa
  pelo teto que barra o 5.87 de fora;
- `Cobre a segurança da distro até: <versão>`: a versão do bluez da distro cujas
  correções a revisão já leva.

## Uma revisão nova

O doctor avisa quando a distro publica um bluez maior que o da linha «Cobre…»:
a correção da distro não chega, porque o apt não a aplica por cima do backport.
Para levar a correção:

1. leia o changelog da versão nova da distro (`apt changelog bluez`) e ache, no
   master do BlueZ, o commit de cada CVE;
2. confira que o 5.87 não o tem (`git merge-base --is-ancestor <commit> 5.87`)
   e exporte com `git format-patch --no-signature -1 <commit>` como o próximo
   `hefesto-NNNN`, sem as linhas de coautoria da mensagem (o projeto não
   versiona trailer; o diff fica o do upstream);
3. acrescente no `BASELINE` a linha `UPSTREAM_hefesto-NNNN=<commit> <sha256>`, a
   lista `PATCHES_R<n>` e `REVISAO_ULTIMA=<n>`;
4. abra no `changelog.hefesto` a entrada `~hefesto24.04.<n>` com os CVE, a linha
   «Leva do upstream» e a «Cobre a segurança da distro até» com a versão nova;
5. rode o script e o teste
   `tests/unit/test_o_bluez_da_casa_leva_as_correcoes_de_seguranca.py`.

## As revisões

| Versão | O que tem |
|---|---|
| `~hefesto24.04.1` | o 5.86 sobre o empacotamento do 26.04 |
| `~hefesto24.04.2` | mais o `hefesto-0001`, mantendo o pareamento |
| `~hefesto24.04.3` | o `hefesto-0001` também mantém o aparelho; reconstrói com `--revisao 3` |
| `~hefesto24.04.4` | mais o `hefesto-0002`; reconstrói com `--revisao 4` |
| `~hefesto24.04.5` | o 5.87 com as correções do upstream, cobrindo a distro até o `5.72-0ubuntu5.8`; é a que o script constrói |

## O que o script faz

1. baixa o BlueZ e o empacotamento e confere os dois SHA-256, com tempo máximo
   para cada download;
2. monta a árvore do zero em `~/.cache/hefesto-dualsense4unix/bluez-obra/`
   (duas corridas dão a mesma árvore), conferindo o commit e o hash de cada
   patch do upstream;
3. aplica a série com o `dpkg-source`, sem tolerância, e confere o hash do
   `device.c`;
4. prova o `hefesto-0002` no fonte baixado ([A prova sem rádio](#a-prova-sem-rádio));
5. confere as dependências de build com o `dpkg-checkbuilddeps`;
6. roda `dpkg-buildpackage -b -us -uc` e o `make check` do BlueZ;
7. entrega os três `.deb`, o `SHA256SUMS` e um `ORIGEM.txt` com os hashes de
   tudo o que entrou, e confere no `bluetoothd` construído a marca de cada
   correção da casa.

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
cd ~/.cache/hefesto-dualsense4unix/bluez-obra/bluez-5.87
sudo mk-build-deps -ir debian/control
```

## A prova sem rádio

`assets/bluez-backport/prova/eagain.c` recorta do `device.c` a
`struct input_device` e as `hidp_send_*`, e as roda contra um `socketpair` não
bloqueante, cheio até o kernel devolver EAGAIN, o mesmo erro do Bluetooth:

| Cenário | BlueZ original (5.86 e 5.87) | com o `hefesto-0002` |
|---|---|---|
| 1001 saídas com o buffer cheio | desconectado 1001 vezes, 1001 linhas no diário | nenhuma desconexão, 1001 descartes, 2 linhas |
| `SET_REPORT` / `GET_REPORT` com o buffer cheio | desconectado | fica; o kernel recebe EIO |
| EPIPE, ENOTCONN, sem canal | desconectado | desconectado |

```bash
scripts/construir_bluez_backport.sh --mordida tests/fixtures/bluez-5.87/device.c
```

O `tests/fixtures/bluez-5.87/device.c` e o `tests/fixtures/bluez-5.86/device.c`
são os do BlueZ, byte a byte. O `tests/fixtures/bluez-5.87/recorte/` guarda, dos
outros arquivos que a série toca, só os trechos em volta de cada pedaço (o fonte
inteiro passaria de 600 kB). O
`tests/unit/test_o_backport_do_bluez_e_reproduzivel.py` confere a série, os
hashes, a árvore sem rede e a prova.

Dos testes do BlueZ, o `unit/test-mesh-crypto` reprova numa máquina que
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
