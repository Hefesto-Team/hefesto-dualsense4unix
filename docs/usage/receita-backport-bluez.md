# A receita do backport do BlueZ

O `install.sh` (passo 3f) e o `doctor.sh` mandam para cá quando o BlueZ da
máquina está abaixo do alvo. Até 23/09/2026 esta página era só o estudo de
19/07 (lá embaixo): o `5.86-0ubuntu0.1~hefesto24.04.3` que roda na máquina
dela não tinha fonte, patch nem receita em lugar nenhum, e o install só
consumia `.deb` prontos de um cache que já não existia.

## Em uma linha

```bash
scripts/construir_bluez_backport.sh
```

Constrói o `5.86-0ubuntu0.1~hefesto24.04.4` e entrega `libbluetooth3`,
`bluez` e `bluez-cups` com `SHA256SUMS` em
`~/.cache/hefesto-dualsense4unix/bluez-backport/`, onde o install procura.
**Não instala nada e não usa sudo.** Numa máquina com as dependências de
build, leva uns três minutos.

## De onde vem cada peça

| peça | de onde | quem fixa |
| --- | --- | --- |
| o BlueZ 5.86 | `kernel.org/pub/linux/bluetooth/` | SHA-256 em `assets/bluez-backport/BASELINE` |
| o empacotamento `5.85-4ubuntu0.1` do resolute | Launchpad (saiu do pool do archive, que hoje tem o 0.2) | SHA-256 em `assets/bluez-backport/BASELINE` |
| os patches `hefesto-NNNN` | `assets/bluez-backport/patches/` | o SHA-256 do `device.c` que cada revisão produz, no `BASELINE` |
| o changelog das revisões `.1` a `.4` | `assets/bluez-backport/debian/changelog.hefesto` | a versão alvo, conferida no `dpkg-parsechangelog` |

O empacotamento do 5.85 pede três ajustes para servir ao 5.86, medidos no
build de 22/07 e feitos pelo script — cada um para se não achar o alvo:

1. o `0013-transport-Fix-set-volume-failure-with-invalid-device.patch` sai da
   `series`: a API de volume foi refeita no 5.86;
2. o `btmgmt.1` sai do `debian/bluez.manpages`: o 5.86 não o gera mais;
3. seis man pages novas do 5.86 entram no `debian/bluez.manpages`, sem as
   quais o `dh_missing` aborta.

## Os patches

### `hefesto-0001-input-keep-bond-on-virtual-cable-unplug.patch`

Em `profiles/input/device.c`, `virtual_cable_unplug()`. Desde o 5.85 o HID
por rádio vai pelo uhid, e o Virtual Cable Unplug que o Pro Controller e o
8BitDo mandam ao desligar chegava ao `device_remove_bonding()`: o bond
evaporava a cada queda. O patch mantém o bond (BOND-KEEP-01, revisão `.2`) e,
se o aparelho é BONDED, o desmarca como temporário (BOND-KEEP-02, revisão
`.3`) — sem isso o `TemporaryTimeout` apagava o aparelho E o bond ~30 s depois.
`BLUEZ_HID_UNPLUG_REMOVES_BOND=1` no ambiente do serviço devolve o
comportamento de origem. Marca no binário: `HEFESTO BOND-KEEP-01`.

### `hefesto-0002-input-drop-report-on-eagain.patch`

Em `profiles/input/device.c`, nas funções `hidp_send_*`. Os dois canais
L2CAP do HID são não bloqueantes (`btio` abre com `G_IO_FLAG_NONBLOCK`).
Com o buffer de envio cheio por um instante, o `writev` devolve EAGAIN, e o
BlueZ de origem respondia com `uhid_disconnect(idev, true)`: **um engasgo
destruía o controle**. Em 22/09, nos quatro episódios de queda, o EAGAIN no
bluetoothd e o ENODEV no escritor do hidraw vieram no mesmo segundo, em três
controles, com zero «Output queue is full» do uhid do kernel.

O que o patch faz:

- guarda o errno da escrita que falhou;
- com EAGAIN ou EWOULDBLOCK, **descarta aquele relatório, conta, e o aparelho
  fica**. Vale para os três chamadores: a saída (`UHID_OUTPUT`) e os pedidos
  `SET_REPORT` e `GET_REPORT`, que continuam respondendo EIO ao kernel;
- registra no máximo uma linha por segundo por aparelho, com o total, e mantém
  o prefixo de sempre para quem já lê o journal:
  `BT socket write error: Resource temporarily unavailable (11): report dropped, 1001 so far`;
- com erro terminal (ENOTCONN, EPIPE, EBADFD, ECONNRESET, escrita parcial, canal
  ausente) nada muda: o aparelho cai como antes.

O `BT_IO_OPT_FLUSHABLE` no canal de interrupção ficou de fora de propósito:
só entra se a bancada medir. Para ver os descartes numa máquina com o `.4`:

```bash
journalctl -u bluetooth | grep 'report dropped'
```

## As revisões

| versão | data | o que mudou | reconstrói? |
| --- | --- | --- | --- |
| `~hefesto24.04.1` | 22/07 | o 5.86 sobre o empacotamento do resolute (o retry-limit + backoff do upstream 17a227b7) | não |
| `~hefesto24.04.2` | 22/07 | `hefesto-0001` com o BOND-KEEP-01 | não |
| `~hefesto24.04.3` | 23/07 | `hefesto-0001` com o BOND-KEEP-02 — a que roda na máquina dela | sim, `--revisao 3` |
| `~hefesto24.04.4` | 23/09 | `hefesto-0002` | sim, o padrão |

## O que o script faz

1. baixa o upstream e o empacotamento e confere os dois SHA-256 — nada é
   usado sem conferir, e cada tentativa de download tem teto de tempo;
2. monta a árvore em `~/.cache/hefesto-dualsense4unix/bluez-obra/`, refeita
   do zero a cada corrida (é isso que faz duas corridas darem a mesma árvore),
   com os três ajustes, os patches da revisão e o changelog;
3. aplica a série com o `dpkg-source` (fuzz zero) e confere o hash do
   `device.c` resultante;
4. **morde** o `hefesto-0002` no fonte baixado (a prova abaixo);
5. confere as dependências de build com o `dpkg-checkbuilddeps`;
6. `dpkg-buildpackage -b -us -uc` e, em seguida, o `make check` do próprio
   BlueZ;
7. entrega os três `.deb`, o `SHA256SUMS` e um `ORIGEM.txt` com os hashes de
   tudo o que entrou, e confere no `bluetoothd` construído a marca de cada
   patch.

| opção | o que faz |
| --- | --- |
| (nenhuma) | constrói a última revisão; com os `.deb` dela no cache e o `SHA256SUMS` batendo, sai 0 sem baixar nem compilar |
| `--forcar` | reconstrói mesmo já pronto |
| `--sem-unit` | pula o `make check` |
| `--preparar` | só os passos 1 a 4 |
| `--mordida ARQ` | só o passo 4, sobre o `device.c` informado |
| `--revisao N` | uma revisão antiga; exige `HEFESTO_BLUEZ_CACHE` apontando para FORA do cache que o install lê |
| `HEFESTO_BLUEZ_JOBS=N` | compila com N processos (o padrão é um por núcleo) |

Códigos de saída: 0 ok · 2 uso · 3 falta dependência · 4 fonte não confere ·
5 série não aplica · 6 a mordida não morde · 7 build · 8 unit do BlueZ.

## Dependências de build

O script não usa sudo. Se faltar alguma, ele lista o que o
`dpkg-checkbuilddeps` disse e sai com 3. Quem tem sudo instala e roda de novo:

```bash
cd ~/.cache/hefesto-dualsense4unix/bluez-obra/bluez-5.86
sudo mk-build-deps -ir debian/control
```

## A prova sem rádio

`assets/bluez-backport/prova/eagain.c` recorta do `device.c` a
`struct input_device` e as `hidp_send_*`, e as roda contra um `socketpair`
não bloqueante cheio até o kernel devolver EAGAIN — o mesmo errno do L2CAP.
Medido em 23/09/2026:

| cenário | vanilla 5.86 | com o `hefesto-0002` |
| --- | --- | --- |
| 1001 saídas com o socket cheio | destruído 1001 vezes, 1001 linhas de log | destruído 0 vezes, 1001 descartes, 2 linhas |
| `SET_REPORT` / `GET_REPORT` com o socket cheio | destruído | fica; o kernel recebe EIO |
| EPIPE, ENOTCONN, sem canal | destruído | destruído |

```bash
scripts/construir_bluez_backport.sh --mordida tests/fixtures/bluez-5.86/device.c
```

O `tests/fixtures/bluez-5.86/device.c` é o do tarball, byte a byte. A régua
do repositório é `tests/unit/test_o_backport_do_bluez_e_reproduzivel.py`: os
patches aplicam com fuzz zero e dão os hashes do `BASELINE`, o preparo monta
a árvore da versão alvo sem rede, duas corridas dão a mesma árvore, e a
mordida acima.

**O `unit/` do BlueZ**, no build de 23/09: 38 testes, 37 passam. O
`unit/test-mesh-crypto` reprova em «Crypto packet encrypt» porque a máquina
dela desliga o `algif_aead` (`/etc/modprobe.d/disable-algif_aead.conf`,
CVE-2026-31431), e o AES-CCM do kernel pela AF_ALG some. O teste liga só o
próprio objeto e a `-lell`, nada de `profiles/input`. O script só o perdoa
depois de medir o AEAD ausente na hora, e diz «NÃO MEDIDO»; qualquer outra
falha reprova.

A mordida de verdade — três pontes de som no mesmo adaptador, e a queda que
não vem — é da bancada dela.

## Instalar não é deste script

O postinst do pacote `bluez` reinicia o bluetoothd ao trocar de versão
(`dh_installinit --restart-after-upgrade`), e todo controle por rádio cai
até reconectar. Quem instala é o `install.sh`, passo 3f, com o aviso na tela:
ele confere o `SHA256SUMS`, grava as versões anteriores em
`VERSOES-ANTERIORES.txt` (o `uninstall.sh` volta por elas) e instala os três
`.deb` juntos.

**NOTA DATADA — 23/09/2026.** O passo 3f ainda mira o `.3` e pula quando o
bluetoothd em execução é ≥ 5.79 — então ele pularia o `.4` sobre o `.3`. O
alvo e o portão são da onda 4 da leva do rádio: o install passa a comparar a
versão INSTALADA do pacote `bluez` com a versão alvo completa.

---

## O estudo de 19/07 — bluetoothd 5.72 crasha crônico: diagnóstico upstream e plano de backport

> **NOTA DATADA — 11/08/2026, ao recuperar este estudo para a árvore.**
>
> Este documento é de **19/07**, e em dois pontos (o fim da §1 e a Síntese) ele sugere
> **anexar o core dump** do `bluetoothd` a um relatório upstream. **Não faça
> isso.** Uma medição de **04/08/2026** — quinze dias depois deste estudo —
> mostrou que um core do `bluetoothd` carrega **todas as LinkKeys, LTKs e
> IRKs** pareadas na máquina.
> Para upstream vai o **backtrace** (`coredumpctl info`), nunca o core.
>
> A regra é uma linha: **o core nunca sai da máquina.** Há teste que reprova
> quem instruir o contrário
> (`tests/unit/test_radio_aberto_e7_e9.py`) — foi ele que pegou esta recuperação,
> antes do commit.
>
> O resto do estudo fica como o PORQUÊ do backport. A receita de hoje é a do
> topo desta página: o caminho 1 da §3 virou `scripts/construir_bluez_backport.sh`
> (23/09/2026), e parte do 5.86 do upstream sobre o empacotamento do resolute,
> não do fonte do resolute como está. O texto de 19/07 fica como estava, porque
> **não se apaga decisão medida** — só ganha a nota que diz o que caducou.


> Pesquisa de 19/07 (agente com clone parcial do git upstream do BlueZ + Launchpad + madison).
> Contexto medido na máquina: bluez 5.72-0ubuntu5.5 (noble-updates via espelho Pop), 5 crashes do
> bluetoothd em 5 dias (14→19/07), sempre em sessão com controles BT: 2× SEGV, 3× heap corruption
> (malloc tcache/fastbin/consolidate), com `hidp_add_connection`/`ioctl_is_connected`/
> `control_connect_cb` ao redor nos logs. Artefatos da pesquisa (clone bluez-git, diffs device.c
> 5.72master, control files) ficaram no scratchpad da sessão 089ae384.

### Fato estrutural que muda a leitura

`/etc/bluetooth/input.conf` local tem `#UserspaceHID=true` COMENTADO e o default só virou `true`
no 5.73 (commit 9698870). Ou seja: o 5.72 do noble roda o input profile na via **kernel HIDP** —
consistente com as funções nos logs (só existem nessa via). Qualquer backport ≥5.73 muda o input
para a via **uhid** (bluetoothd vira dono do uhid do controle BT) — mudança comportamental
relevante para o projeto, com knob de contingência `UserspaceHID=false`.

### 1. Bugs upstream correspondentes

**Família issue #815 ("Random crash on device reconnect" — SEGV + corrupted double-linked list em
reconexão HID), curada na via uhid entre 5.74 e 5.79:**

| Commit | Título | Release |
|---|---|---|
| ee39d01fb | shared/uhid: Fix registering UHID_START multiple times | 5.78 |
| a13638e6a | shared/uhid: Fix not cleanup input queue on destroy | 5.78 |
| 2daddeada | shared/uhid: Fix unregistering UHID_START on bt_uhid_unregister_all | 5.78 |
| 9a6a84a8a | shared/uhid: Fix crash after bt_uhid_unregister_all | 5.79 |
| b94f1be65 | shared/uhid: Fix crash if bt_uhid_destroy free replay structure | 5.76 |
| b8ad3490a | input/device: Force UHID_DESTROY on error | 5.74 |
| ea96d7d18 | input/device: Fix not handling IdleTimeout when uhid is in use | 5.74 |

Ressalva: a família é da via uhid, que o 5.72 do noble NÃO usa por default — ela importa porque o
backport ativa essa via, e aí é obrigatório ≥5.79 (série completa).

**Fixes que afetam a via HIDP/core diretamente:**

| Commit | Título | Release | Relação |
|---|---|---|---|
| 366a8c522 | adapter: Fix up address type when loading keys (#875) | 5.78 | JÁ no noble (5.72-0ubuntu5.1, git-reconnect-fix.patch) |
| 6d55c7d7f | device: Fix Device.Pair using wrong address type | 5.79 | re-pair de já-bonded trava até timeout — casa com o bond meio-salvo (Paired yes/Bonded no) |
| c3b6f4e4b | device: Check presence of ServiceRecords when loading from store | 5.83 | HID pareado sem cache SDP nunca conecta → loops de control_connect_cb fúteis |
| 2645d3f66 | input/device: Fix off by one report descriptor size error | 5.86 | cita literalmente `playstation 0005:054C:0CE6`; 0x00 espúrio no descriptor via SDP |
| 756da3fa1 | input: Fix checking LE bonding on HIDP (#2034) | 5.87 | dual-mode: bond checado no endereço LE → "Rejected connection from !bonded device" |
| 941dbc5f3 | device: Fix memory leak | 5.84 | leak em src/device.c |

**NÃO encontrado**: fix upstream para heap corruption na via kernel-HIDP do 5.72. O SEGV em
`control_connect_cb → btd_service_connecting_complete` segue reportado ATÉ no 5.83-5.85
(LP #2137758, Confirmed, sem SRU) — o upgrade não é bala de prata; vale anexar o core dump desta
máquina ao LP #2137758 (mesmo call chain do crash de 19/07 14:38).

### 2. Distros

- Changelog noble: 5.1=reconnect-fix; 5.2/5.3=HSP/HFP pós-suspend; 5.4=Pair auto_connect;
  5.5=só áudio/AVDTP. **Nenhum SRU do noble toca crash de input/HIDP.**
- Versões: noble 5.72 | questing 5.83 | **resolute (26.04 LTS) 5.85-4ubuntu0.1** | Debian trixie
  5.82, sid 5.85-4. Pop não tem bluez próprio (apt.pop-os.org = espelho do archive Ubuntu).

### 3. Caminhos de cura (ranqueados)

1. **Rebuild do source package do resolute (5.85-4ubuntu0.1) para noble** — cura duradoura; 26.04 é
   LTS (re-backportar cada SRU deles com o mesmo script). Build-deps TODOS presentes no noble
   (glib 2.80, libell 0.64, json-c 0.17, debhelper 13.14 com dh-sequence-installsysusers —
   verificado). Fluxo: dget do .dsc → dch --local → mk-build-deps -ir → dpkg-buildpackage -us -uc
   -b → instalar só bluez+bluez-cups+libbluetooth3 → pin apt Priority 1001. ABI libbluetooth3
   estável (soname 3 há décadas; pipewire/blueman/COSMIC falam D-Bus). Risco real =
   comportamental (input vira uhid; kernel local 7.0.11 ok — a regressão #988 era do 6.11.4);
   contingência `UserspaceHID=false` (e o 5.80 tem fallback automático, 8f853903b). Uninstall
   simétrico: remover pin + `apt install bluez=5.72-0ubuntu5.5 ...` (archive segue servindo).
   **23/09/2026:** este caminho é hoje o `scripts/construir_bluez_backport.sh` — ver o topo.
2. **PPA ppa:giner/bluez** — 5.84-1~bpo24.04.1~ppa2 PARA noble, mantida (nov/2025), "backported
   from 26.04 due to older Bluez being very buggy". Boa para VALIDAR rápido antes do rebuild
   próprio. Risco: terceiro; sem e3a16c28e (5.85). Uninstall: ppa-purge.
3. **Quilt pontual sobre 5.72** — só os cherry-picks HIDP (c3b6f4e4b, 6d55c7d7f, 2645d3f66,
   756da3fa1); NÃO cura o heap corruption; rebase a cada SRU. Paliativo apenas.
4. **Esperar o Pop** — plano de update de bluez no 24.04: não encontrado.

### 4. Bônus — sintomas satélites explicados

- **"Failed to set privacy: Rejected (0x0b)"** no start: `set_privacy()` do kernel retorna
  REJECTED se o adaptador está LIGADO — cenário exato do respawn pós-crash com hci0 up. Benigno
  para controles (HIDP classic não usa privacy LE).
- **"No agent available for request type 2" / device_confirm_passkey**: nenhum agente de
  pareamento registrado no D-Bus no momento → pareamento sem autenticação completa → nasce o bond
  meio-salvo (Paired yes/Bonded no) — EXATAMENTE o estado do roxo. Mitigação scriptável: agente
  persistente `bt-agent --capability=NoInputNoOutput` (pacote bluez-tools, no noble) como serviço
  systemd, OU registrar agente default no próprio daemon hefesto (já fala D-Bus).
  Complemento: `JustWorksRepairing = always` no main.conf facilita re-pareamento.

### Síntese

O 5.72 do noble está 13 releases atrás num subsistema com ~10 fixes de crash de input/uhid entre
5.74 e 5.87. Plano da Onda R: (1) backport 5.85 do resolute como .deb próprio com pin + uninstall
simétrico (validação rápida opcional via ppa:giner); (2) agente de pareamento persistente (cura o
vetor do bond quebrado); (3) `UserspaceHID=false` documentado como contingência; (4) anexar core
dump ao LP #2137758; (5) doctor: check "Connected sem hidraw" e "Paired sem Bonded".
