# O portal de captura do COSMIC corrigido

O `xdg-desktop-portal-cosmic` do Pop!_OS 24.04 (`1.11.0~1792525517~24.04~f448ddf`)
aborta no meio de um compartilhamento de tela com
`ext_image_copy_capture_session_v1: error 1: create_frame sent before the previous
frame was destroyed`: o `cosmic-client-toolkit` chama o `ready` (ou o `failed`) do
frame antes de destruí-lo, e quem pede o próximo frame dentro do callback esbarra
no anterior ainda vivo. O compartilhamento cai, e o portal cai com ele. A cura
é o [cosmic-protocols#92](https://github.com/pop-os/cosmic-protocols/pull/92)
(commit `3ad1781fefeaea5224ec6917f53ccad32bf5219b`), que move o
`screencopy_frame.destroy()` para antes do callback nos dois braços. O PR está
aberto, e o portal do Pop trava o `cosmic-protocols` no `c0cff4d`, o pai exato
dele. O Hefesto constrói o portal da versão que o dpkg diz, com o PR pelo
`[patch]` do Cargo, e o `hefesto-dualsense4unix doctor` manda para cá quando o
portal em execução não traz a cura.

## Em uma linha

```bash
scripts/construir_portal_cosmic_backport.sh
```

Constrói o `<versão do dpkg>+0~hefesto1` e entrega o `.deb`, com o `SHA256SUMS`
e um `ORIGEM.txt`, em `~/.cache/hefesto-dualsense4unix/portal-cosmic-backport/`.
**Não instala nada e não usa sudo.** Leva uns 6 minutos com 8 núcleos (1,5 para
buscar e montar, 5 para compilar). Quem instala é o `./install.sh`, no passo
3f-ter, e só no COSMIC com o portal instalado; fora disso o passo nem aparece.

## De onde vem cada peça

| Peça | De onde | Quem fixa |
|---|---|---|
| o fonte do portal | `apt-get source` da versão instalada, do repositório do Pop | o índice assinado do apt e o `Checksums-Sha256` do `.dsc` |
| as crates de cima | o `vendor.tar` que vem dentro do fonte | o `Cargo.lock` do Pop |
| o PR #92 | `assets/portal-cosmic-backport/patches/cosmic-protocols-92-destroy-antes-do-callback.patch` (o `gh pr diff 92`) | `PATCH_SHA256` no `BASELINE` |
| a prova no binário | o caminho do `dispatch.rs` remendado, que o rustc grava no binário | a linha `MARCA_` do `BASELINE` |

Nada do código do portal nem do `cosmic-protocols` entra no repositório.

## O que o script faz

1. Lê a versão instalada pelo dpkg (com o `+0~hefesto1` de uma construção anterior
   tirado) e busca o fonte dessa versão pelo apt, conferindo o tarball contra o `.dsc`.
2. Monta a árvore em `~/.cache/hefesto-dualsense4unix/portal-cosmic-obra/`,
   nunca dentro do checkout, e abre o `vendor.tar`.
3. Confere o `dispatch.rs` vendorizado: se o destroy já vem antes do `ready` e do
   `failed`, **a versão de cima já traz a cura**, o script grava a versão em
   `A-ORIGEM-JA-CURA.txt` e sai com o código 9 (nada a fazer). É assim que o passo
   se aposenta sozinho quando o Pop entregar o PR.
4. Copia o `vendor/cosmic-protocols` para `hefesto-cosmic-protocols-92/`, com o
   `vendor/cosmic-client-toolkit` como `client-toolkit/`, aplica o patch sem fuzz
   e confere o `dispatch.rs` de novo.
5. Acrescenta ao `Cargo.toml` o `[patch."https://github.com/pop-os/cosmic-protocols"]`
   que aponta as duas crates para a cópia, e deixa o `cargo metadata --offline`
   atualizar o `Cargo.lock`. Se o lock mudar em algo além das duas linhas
   `source` dessas crates, o script para.
6. Escreve a entrada do `debian/changelog` com o sufixo e os dois commits.
7. Constrói com `dpkg-buildpackage -b -us -uc -nc -d`, num ambiente limpo, com o
   `BINDGEN_EXTRA_CLANG_ARGS=-I$(gcc -print-file-name=include)` (o `stdbool.h` que
   o bindgen do PipeWire procura sai do gcc presente).
8. Abre o `.deb`, procura a `MARCA_` no binário e só então entrega.

Códigos de saída: 0 certo · 2 uso · 3 falta dependência · 4 fonte · 5 patch ·
6 sem a cura · 7 build · 9 a versão de cima já traz a cura.

## Dependências de build

O script confere antes e lista o que falta, com o comando de instalar:

```bash
sudo apt install dpkg-dev just libclang-dev gcc libglib2.0-dev libegl-dev \
    libgbm-dev libpipewire-0.3-dev libwayland-dev libxkbcommon-dev pkg-config
```

O Rust pode vir do apt (`sudo apt install cargo rustc`) ou do
[rustup](https://rustup.rs). O portal pede um Rust que entenda o `edition`
do `Cargo.toml` dele; o script compara com o `rustc --version`. Com o rustup, o
`cargo` e o `rustc` que contam são os do PATH; o `libclang-dev` é dispensado se
o `libclang` já estiver no `ldconfig`.

O fonte vem pelo apt, então o repositório do Pop precisa da linha `deb-src`
ligada (no Pop!_OS 24.04, já vem).

## Instalar

O `./install.sh`, no passo 3f-ter:

1. avisa de todo drop-in que troca o `ExecStart` do portal (com o caminho do
   arquivo) e **não o apaga**;
2. constrói pelo script (o registro fica em
   `~/.cache/hefesto-dualsense4unix/portal-cosmic-construir.log`); com o código 9,
   diz «nada a fazer»; com o 3, mostra o que falta e para;
3. confere o `.deb` pelo `SHA256SUMS`;
4. avisa que o reinício derruba **uma vez** um compartilhamento de tela aberto e
   pergunta;
5. grava a versão anterior em `VERSOES-ANTERIORES.txt`, fixa a prioridade do apt
   em `/etc/apt/preferences.d/hefesto-portal-cosmic` e instala o `.deb`;
6. pede ao systemd o reinício do portal com
   `systemctl --user try-restart --no-block`, sem esperar: o portal sem
   `wl_output` não responde, e o systemd só o mata aos 90 s.

À mão, o mesmo:

```bash
cd ~/.cache/hefesto-dualsense4unix/portal-cosmic-backport
sha256sum -c SHA256SUMS
sudo install -m 0644 <checkout>/assets/portal-cosmic-backport/apt/hefesto-portal-cosmic.pref \
    /etc/apt/preferences.d/hefesto-portal-cosmic
sudo apt-get install -y ./xdg-desktop-portal-cosmic_*+0~hefesto1_amd64.deb
systemctl --user try-restart --no-block org.freedesktop.impl.portal.desktop.cosmic.service
```

O `.pref` põe o repositório do Pop a 500 só para o portal (o Pop fixa o dele a
1001, o que voltaria o pacote no próximo `apt upgrade`). Com 500, o apt fica com
a versão mais nova: a da casa, até o Pop entregar uma construção nova, que tem
número maior e entra sozinha. Aí o passo 3f-ter constrói de novo sobre essa versão,
ou diz «nada a fazer» se a construção nova já trouxer o PR.

## O drop-in de outro projeto

Um drop-in em
`~/.config/systemd/user/org.freedesktop.impl.portal.desktop.cosmic.service.d/`
que zera e troca o `ExecStart` faz o systemd rodar outro programa no lugar do
`/usr/libexec/xdg-desktop-portal-cosmic`. O install e o doctor dizem o caminho do
arquivo e o programa que ele aponta, e nenhum dos dois o apaga: o arquivo é de
quem o escreveu. Para valer o portal do pacote, tire a troca à mão e rode
`systemctl --user daemon-reload`.

## Voltar

```bash
cat ~/.cache/hefesto-dualsense4unix/portal-cosmic-backport/VERSOES-ANTERIORES.txt
sudo rm /etc/apt/preferences.d/hefesto-portal-cosmic
sudo apt-get install --allow-downgrades xdg-desktop-portal-cosmic=<a versão gravada>
systemctl --user try-restart --no-block org.freedesktop.impl.portal.desktop.cosmic.service
```

## A prova

```bash
scripts/construir_portal_cosmic_backport.sh --conferir-programa /usr/libexec/xdg-desktop-portal-cosmic
```

Código 0 com a cura, 6 sem a cura. O binário de cima traz o caminho
`vendor/cosmic-client-toolkit/src/screencopy/dispatch.rs`; o da casa traz
`hefesto-cosmic-protocols-92/client-toolkit/src/screencopy/dispatch.rs`. O
`--conferir-dispatch <arquivo>` faz a mesma pergunta ao fonte.

## Uma versão nova

Nada a editar enquanto o PR #92 aplicar sem fuzz: o script segue a versão do
dpkg. Se o patch parar de aplicar (código 5), a receita precisa de revisão; se o
Pop entregar o PR, o código 9 aposenta o passo, e o doctor passa a aprovar a
versão de cima pelo `A-ORIGEM-JA-CURA.txt`.
