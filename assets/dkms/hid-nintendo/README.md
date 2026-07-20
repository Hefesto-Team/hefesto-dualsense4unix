# hefesto-hid-nintendo (DKMS) — Onda T

Módulo `hid-nintendo` patchado para curar a morte por probe BT dos controles
Nintendo/8BitDo sob interferência 2.4GHz (medida 3× nesta máquina: `-110` no
`joycon_read_info`, HID não re-proba, controle some até power-cycle).

## Proveniência

- `hid-nintendo.c` = **vanilla v7.0.11** (idêntico byte a byte ao source do
  kernel `7.0.11-76070011-generic` do Pop!_OS, commit pop-os/linux em
  `patch/BASELINE`) **+ `patch/0001-*.patch` aplicado**. Nada além do patch —
  invariante verificável: `patch -R -p3 hid-nintendo.c < patch/0001-*.patch`
  reproduz exatamente o `SHA256_VANILLA_C` do `patch/BASELINE`.
- `hid-ids.h` = header local intocado do mesmo commit (único include local).
- Código C em inglês (convenção do subsistema HID, visando o upstream).

## O que o patch muda (3 alvos, detalhe no próprio patch)

- **[B] Não transmitir após esgotar o rate-limit**: hoje o driver esgota as 25
  tentativas ("exceeded max attempts") e transmite mesmo assim, sem ritmo —
  exatamente o que o comentário do próprio driver diz que derruba o link BT.
  Com o patch, o TX é suprimido (o chamador vê o mesmo `-ETIMEDOUT` de sempre).
- **[A] Retry de probe BT** (opt-in): laço com backoff exponencial em volta do
  `joycon_init()` no probe, só bluetooth. Default `bt_probe_retries=0` ==
  comportamento vanilla; a cura entra via
  `assets/modprobe.d/hefesto-hid-nintendo.conf` (`bt_probe_retries=3`).
- **[C] Module params** com defaults idênticos aos valores hardcoded
  (250/25/2/2000/0) — tuning de campo ao vivo em
  `/sys/module/hid_nintendo/parameters/` (presença do diretório = marcador
  "patch carregado" para o doctor; o in-tree tem zero params).

## Build / instalação

- Instala via `install.sh` (DEFAULT; opt-out `--no-dkms`) usando
  `scripts/dkms_lib.sh`; vai para `updates/dkms`, que vence o in-tree
  automaticamente (`/etc/depmod.d/ubuntu.conf`). Uninstall simétrico.
- Prova de build manual (sem instalar nada):
  `make -C /usr/src/linux-headers-$(uname -r) M=$PWD modules`
- `Makefile` replica `CONFIG_NINTENDO_FF=y` do in-tree via
  `-DCONFIG_NINTENDO_FF=1` (sem isso o rumble sumiria).
- Fail-safe: build DKMS falhou num kernel novo → o in-tree continua (nunca
  ficar sem controle); se o in-tree carregar com a conf presente, o kernel só
  loga `unknown parameter 'bt_probe_retries' ignored` e sobe normal.
- Ativação NUNCA por reload com controles em uso — vale no próximo boot
  (se o módulo estiver descarregado, entra sozinho no próximo plug).

## Rebase (kernel novo)

`patch/BASELINE` guarda kernel base, commit e os sha256. Rota: baixar o
vanilla novo, `patch -p3 < patch/0001-*.patch`, resolver fuzz, atualizar
BASELINE + `PACKAGE_VERSION` no `dkms.conf`, re-provar o build. O `patch/`
não entra no build (o helper DKMS o exclui do source copiado).

## Upstream

`patch/0001-*.patch` está em formato `git format-patch` (caminho
`a/drivers/hid/hid-nintendo.c`, `git am` direto) para submissão a
`linux-input@vger.kernel.org` (cc Daniel J. Ogorchock). O Signed-off-by é o
placeholder anônimo do projeto; a submissão real exige trocar o SoB por nome
real de pessoa (DCO) — decisão da mantenedora, fora do repo. Recomendação:
quebrar em série de 3 ([B] correção, [A] retry opt-in, [C] params).
