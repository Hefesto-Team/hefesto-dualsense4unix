# hefesto-rtw88-usb (DKMS) — Onda W

Módulo `rtw88_usb` patchado para curar o **fantasma USB** do dongle WiFi
(Archer T3U / RTL8822BU): device removido cujo `USB disconnect` nunca é
processado vive 13h em lsusb/sysfs segurando o nome `wlx...` (medido
20/07: colisão "Arquivo existe" no replug), teardown flooda `-71` contra
hardware morto e vaza ack frames (WARN do mac80211).

## Proveniência

- `usb.c`/`usb.h` = **vanilla v7.0.11** (== byte a byte o rtw88 do kernel
  `7.0.11-76070011-generic` do Pop!_OS, diff Pop×vanilla = 0, commit em
  `patch/BASELINE`) **+ `patch/0001` + `patch/0002` aplicados**. Invariante
  verificável: reverter os dois patches reproduz os `SHA256_VANILLA_*` do
  `patch/BASELINE`.
- `main.h debug.h mac.h reg.h tx.h rx.h fw.h ps.h util.h hci.h` = headers
  locais do rtw88, vanilla **intocados** (fecho transitivo de includes do
  usb.c: usb.c inclui main/debug/mac/reg/tx/rx/fw/ps/usb.h; main.h inclui
  util.h e hci.h). Existem aqui só porque o pacote linux-headers não traz
  headers de drivers.
- Código C em inglês (convenção do subsistema wireless, visando upstream).

## O que os patches mudam

- **0001 (backport verbatim)**: upstream `6b964941bbfe` "fix memory leaks
  on USB write failures" (CVE-2026-63821, `Cc: stable`) — backportado p/
  6.6.144+/6.12.95+/6.18.38+/7.1.3+; a série 7.0.y (EOL) ficou de fora.
  Pré-requisito do 0002: o early-return `-ENODEV` no TX depende de os
  chamadores liberarem skb/txcb na falha de submit.
- **0002 (nosso, modelo rtw89 `2135c28be6a8`)**: `struct rtw_usb` ganha
  `flags` (bit `RTW_USB_FLAG_DEVICE_GONE`), `continual_io_error` (atomic)
  e `intf`; -ENODEV/-ESHUTDOWN armam device_gone imediato; -EPROTO e
  família só via >4 erros consecutivos sem nenhum sucesso no meio;
  early-return em todos os helpers de registro + TX; leitura falha devolve
  0 determinístico (não lixo do ring buffer); na 1ª armada,
  `usb_queue_reset_device()` (gateado pelo param `hang_reset`, default Y)
  força o core a revalidar a porta — a cura automática do fantasma
  (replica o `usb_reset_device` que o unbind manual executou).

## Build / instalação

- Instala via `install.sh` (DEFAULT; opt-out `--no-dkms`) usando
  `scripts/dkms_lib.sh` (2ª instância; a 1ª é o hid-nintendo da Onda T);
  vai para `updates/dkms`, que vence o in-tree automaticamente
  (`/etc/depmod.d/ubuntu.conf`). Uninstall simétrico (dkms remove →
  in-tree volta no próximo boot).
- Símbolos do `rtw88_core`/`mac80211`: resolvidos pelo `Module.symvers`
  que o linux-headers JÁ traz (todos os módulos in-tree). CRCs dos nossos
  exports (`rtw_usb_probe`/`rtw_usb_disconnect`) == in-tree (provado no
  build: 0x391a4de4/0x1124d2ff) → o `rtw88_8822bu` in-tree continua
  carregando contra o nosso módulo.
- `CONFIG_RTW88_DEBUG/DEBUGFS/LEDS` vêm do autoconf.h do kernel alvo —
  nenhum ccflag manual necessário.
- Prova de build manual (sem instalar nada):
  `make -C /usr/src/linux-headers-$(uname -r) M=$PWD modules`
- Fail-safe: build DKMS falho num kernel novo → in-tree volta (nunca ficar
  sem WiFi). Ativação NUNCA por reload com WiFi em uso — vale no próximo
  boot/replug do dongle.

## Params novos (0644, viram marcador p/ o doctor)

- `hang_reset` (bool, default Y): desarma só a parte agressiva
  (`usb_queue_reset_device`); a detecção/silenciamento continua. Com N o
  comportamento volta ao do rtw89 vanilla (muta e não recupera sozinho).

## Rebase (kernel novo)

`patch/BASELINE` guarda kernel base, commit e sha256. Rota: baixar o
vanilla novo, aplicar 0001 (se ainda ausente na série) + 0002, resolver
fuzz, atualizar BASELINE + `PACKAGE_VERSION`, re-provar o build. Num
kernel ≥7.1.3 o 0001 já vem aplicado — remover do pacote e registrar no
BASELINE. `patch/` não entra no build (o helper DKMS o exclui).

## Upstream

`patch/0002` em formato `git format-patch` contra a série estável (para
wireless-next, rebase trivial: mover flag p/ `rtwdev->flags` como o rtw89
faz). Citar: journal do incidente (fantasma 13h + WARN "Have pending ack
frames!"), precedente rtw89 (mesmo mantenedor, Ping-Ke Shih) e análogos
mt76 (`MT76_REMOVED`)/rt2x00 (`DEVICE_STATE_PRESENT`). O SoB é o
placeholder anônimo do projeto; submissão real exige DCO com nome real —
decisão da mantenedora, fora do repo.
