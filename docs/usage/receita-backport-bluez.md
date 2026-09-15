# Estudo Onda R — bluetoothd 5.72 crasha crônico: diagnóstico upstream e plano de backport

> **NOTA DATADA — 11/08/2026, ao recuperar este estudo para a árvore.**
>
> Este documento é de **19/07**, e em dois pontos (linhas 49 e 94) ele sugere
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
> O resto do estudo continua válido: é dele que sai a receita de backport que o
> `install.sh` e o `doctor.sh` apontam quando o BlueZ está abaixo de 5.79. O
> texto de 19/07 fica como estava, porque **não se apaga decisão medida** — só
> ganha a nota que diz o que caducou.


> Pesquisa de 19/07 (agente com clone parcial do git upstream do BlueZ + Launchpad + madison).
> Contexto medido na máquina: bluez 5.72-0ubuntu5.5 (noble-updates via espelho Pop), 5 crashes do
> bluetoothd em 5 dias (14→19/07), sempre em sessão com controles BT: 2× SEGV, 3× heap corruption
> (malloc tcache/fastbin/consolidate), com `hidp_add_connection`/`ioctl_is_connected`/
> `control_connect_cb` ao redor nos logs. Artefatos da pesquisa (clone bluez-git, diffs device.c
> 5.72master, control files) ficaram no scratchpad da sessão 089ae384.

## Fato estrutural que muda a leitura

`/etc/bluetooth/input.conf` local tem `#UserspaceHID=true` COMENTADO e o default só virou `true`
no 5.73 (commit 9698870). Ou seja: o 5.72 do noble roda o input profile na via **kernel HIDP** —
consistente com as funções nos logs (só existem nessa via). Qualquer backport ≥5.73 muda o input
para a via **uhid** (bluetoothd vira dono do uhid do controle BT) — mudança comportamental
relevante para o projeto, com knob de contingência `UserspaceHID=false`.

## 1. Bugs upstream correspondentes

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

## 2. Distros

- Changelog noble: 5.1=reconnect-fix; 5.2/5.3=HSP/HFP pós-suspend; 5.4=Pair auto_connect;
  5.5=só áudio/AVDTP. **Nenhum SRU do noble toca crash de input/HIDP.**
- Versões: noble 5.72 | questing 5.83 | **resolute (26.04 LTS) 5.85-4ubuntu0.1** | Debian trixie
  5.82, sid 5.85-4. Pop não tem bluez próprio (apt.pop-os.org = espelho do archive Ubuntu).

## 3. Caminhos de cura (ranqueados)

1. **Rebuild do source package do resolute (5.85-4ubuntu0.1) para noble** — cura duradoura; 26.04 é
   LTS (re-backportar cada SRU deles com o mesmo script). Build-deps TODOS presentes no noble
   (glib 2.80, libell 0.64, json-c 0.17, debhelper 13.14 com dh-sequence-installsysusers —
   verificado). Fluxo: dget do .dsc → dch --local → mk-build-deps -ir → dpkg-buildpackage -us -uc
   -b → instalar só bluez+bluez-cups+libbluetooth3 → pin apt Priority 1001. ABI libbluetooth3
   estável (soname 3 há décadas; pipewire/blueman/COSMIC falam D-Bus). Risco real =
   comportamental (input vira uhid; kernel local 7.0.11 ok — a regressão #988 era do 6.11.4);
   contingência `UserspaceHID=false` (e o 5.80 tem fallback automático, 8f853903b). Uninstall
   simétrico: remover pin + `apt install bluez=5.72-0ubuntu5.5 ...` (archive segue servindo).
2. **PPA ppa:giner/bluez** — 5.84-1~bpo24.04.1~ppa2 PARA noble, mantida (nov/2025), "backported
   from 26.04 due to older Bluez being very buggy". Boa para VALIDAR rápido antes do rebuild
   próprio. Risco: terceiro; sem e3a16c28e (5.85). Uninstall: ppa-purge.
3. **Quilt pontual sobre 5.72** — só os cherry-picks HIDP (c3b6f4e4b, 6d55c7d7f, 2645d3f66,
   756da3fa1); NÃO cura o heap corruption; rebase a cada SRU. Paliativo apenas.
4. **Esperar o Pop** — plano de update de bluez no 24.04: não encontrado.

## 4. Bônus — sintomas satélites explicados

- **"Failed to set privacy: Rejected (0x0b)"** no start: `set_privacy()` do kernel retorna
  REJECTED se o adaptador está LIGADO — cenário exato do respawn pós-crash com hci0 up. Benigno
  para controles (HIDP classic não usa privacy LE).
- **"No agent available for request type 2" / device_confirm_passkey**: nenhum agente de
  pareamento registrado no D-Bus no momento → pareamento sem autenticação completa → nasce o bond
  meio-salvo (Paired yes/Bonded no) — EXATAMENTE o estado do roxo. Mitigação scriptável: agente
  persistente `bt-agent --capability=NoInputNoOutput` (pacote bluez-tools, no noble) como serviço
  systemd, OU registrar agente default no próprio daemon hefesto (já fala D-Bus).
  Complemento: `JustWorksRepairing = always` no main.conf facilita re-pareamento.

## Síntese

O 5.72 do noble está 13 releases atrás num subsistema com ~10 fixes de crash de input/uhid entre
5.74 e 5.87. Plano da Onda R: (1) backport 5.85 do resolute como .deb próprio com pin + uninstall
simétrico (validação rápida opcional via ppa:giner); (2) agente de pareamento persistente (cura o
vetor do bond quebrado); (3) `UserspaceHID=false` documentado como contingência; (4) anexar core
dump ao LP #2137758; (5) doctor: check "Connected sem hidraw" e "Paired sem Bonded".
