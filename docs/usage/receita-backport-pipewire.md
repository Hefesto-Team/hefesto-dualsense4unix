# O PipeWire corrigido

Até a 1.6.8, a do Pop!_OS 24.04, o PipeWire deixa preso para sempre o cliente
que faz bind num metadata enquanto o WirePlumber sai. A Steam roda
`wpctl settings`, o `wpctl` não sai, e a Steam não fecha
([o estudo](../protocol/o-wpctl-pendurado-pelo-metadata.md)). O upstream curou
na 1.6.9. O Hefesto oferece o PipeWire 1.6.9 e o WirePlumber 0.5.18, as
estáveis mais novas, com o empacotamento do Pop. O `hefesto-dualsense4unix doctor`
manda para cá quando o PipeWire da máquina está abaixo da 1.6.9.

## Em uma linha

```bash
scripts/construir_pipewire_backport.sh
```

Constrói o `1.6.9-0~hefesto24.04.1` e o `0.5.18-0~hefesto24.04.1` e entrega os
`.deb`, com o `SHA256SUMS` e um `ORIGEM.txt`, em
`~/.cache/hefesto-dualsense4unix/pipewire-backport/`. **Não instala nada e não
usa sudo.** Quem instala é o `./install.sh`, no passo 3f-bis: ele chama este
script, confere o `SHA256SUMS`, grava o caminho de volta, fixa a prioridade do
apt, instala só os pacotes que a máquina já tem e reinicia o som. Com a Steam
aberta, ele recusa e manda fechá-la pelo menu. A instalação à mão é a de
[Instalar](#instalar).

## De onde vem cada peça

| Peça | De onde | Quem fixa |
|---|---|---|
| o PipeWire 1.6.9 e o WirePlumber 0.5.18 | o arquivo da tag no GitLab do freedesktop | SHA-256 e o commit da tag em `assets/pipewire-backport/BASELINE` |
| o `debian/` | o tarball do pacote do Pop!_OS (`1.6.8-1pop1…` e `0.5.12-2pop1…`) | SHA-256 em `assets/pipewire-backport/BASELINE` |
| as mudanças do Pop no fonte do PipeWire | `assets/pipewire-backport/patches/pop-0001` e `pop-0002` | SHA-256 de cada uma no `BASELINE` |
| o CVE-2026-14330 | o `debian/patches` do Debian 1.6.9-2, como `debian-0001` | SHA-256 no `BASELINE` |
| as entradas do changelog | `assets/pipewire-backport/debian/changelog.*.hefesto` | a revisão do `BASELINE` |

O Pop entrega os dois pacotes em formato nativo: o `debian/` vem dentro do
tarball, e as mudanças no fonte estão no próprio fonte. As do PipeWire foram
medidas pelo diff contra a tag 1.6.8:

1. `pop-0001`: o `acp.c` só troca de perfil por uma saída disponível;
2. `pop-0002`: o `ebur128` do filter-graph lê a opção pelo `get_option`;
3. o autofoco comentado no `libcamera-source.cpp` **não entra**: a 1.6.9 pede o
   libcamera 0.6.0 ou mais novo, o Ubuntu 24.04 tem o 0.2.0, e o libcamera sai
   do build.

O script faz os ajustes de empacotamento, cada um conferindo o alvo antes:

1. no PipeWire, o `-Dlibcamera=disabled` no `debian/rules` e a saída do pacote
   `libspa-0.2-libcamera` do `debian/control`;
2. no WirePlumber, os 38 símbolos que a 0.5.13 à 0.5.16 acrescentam
   (`debian/libwireplumber-0.5-0.symbols.novos`, os mesmos do Debian 0.5.18-1).
   O `dh_makeshlibs -c4` do Pop reprova símbolo novo sem linha;
3. no WirePlumber, a linha do bash-completion do `wpctl`, que o
   `dh_missing --fail-missing` do compat 13 exige;
4. no WirePlumber, o `meson-1.5` do `debian/control` do Pop vira o `meson-1.7`
   do PipeWire: os dois conflitam no noble, e a 0.5.18 constrói com o 1.7.

## A prova sem dependência de build

```bash
scripts/construir_pipewire_backport.sh --prova
```

Compila só o servidor da árvore montada (um meson mínimo, sem ALSA nem
Bluetooth), com a cura e sem ela, e roda
`assets/pipewire-backport/prova/reproduzir.sh` nos dois. Cada rodada congela o
WirePlumber, lança `wpctl settings` e mata o WirePlumber sem responder. O
servidor é privado: runtime, configuração e D-Bus num diretório temporário, sem
tocar o som da sessão. Medido em 15/10/2026, com 5 rodadas de 4 `wpctl`:

| Servidor | Pendurados |
|---|---|
| 1.6.8 do upstream | 20 de 20 |
| a árvore da casa | 0 de 20 |
| a árvore da casa sem o `remove_pending(d);` do `global_unbind` | 20 de 20 |

Precisa de meson, ninja e gcc, e do `wireplumber` e do `wpctl` no PATH.

## O que o script faz

1. baixa os quatro tarballs e confere os SHA-256;
2. monta as duas árvores do zero, aplica os patches com `patch -F0`, sem
   tolerância, faz os ajustes e escreve a entrada do changelog;
3. confere que o `metadata.c` é o do `BASELINE` e que o `global_unbind` dele
   chama o `remove_pending`;
4. confere as dependências de build com o `dpkg-checkbuilddeps`;
5. roda `dpkg-buildpackage -b -us -uc` nas duas árvores;
6. entrega os `.deb`, o `SHA256SUMS` e o `ORIGEM.txt`, e confere que o
   `libpipewire-0.3-modules` construído traz o módulo de metadata.

| Opção | O que faz |
|---|---|
| (nenhuma) | constrói os dois; se já estão no cache e conferem, sai sem baixar nem compilar |
| `--forcar` | reconstrói mesmo pronto |
| `--preparar` | só os passos 1 a 3 |
| `--prova` | os passos 1 a 3 e a prova acima |
| `--conferir-metadata ARQ` | só a pergunta do passo 3, sobre o `metadata.c` indicado |
| `HEFESTO_PIPEWIRE_CACHE=DIR` | constrói fora do cache que a receita usa |
| `HEFESTO_PIPEWIRE_JOBS=N` | compila com N processos (o padrão é um por núcleo) |

Códigos de saída: 0 certo · 2 uso · 3 falta dependência · 4 fonte não confere ·
5 patch ou ajuste não aplica · 6 sem a cura · 7 build · 8 a prova falhou.

## Dependências de build

Se faltar alguma, o script lista o que o `dpkg-checkbuilddeps` disse e sai com
3. São muitas: o PipeWire pede, entre outras, o `meson` 1.7 ou mais novo, o
`doxygen`, o `graphviz` e as bibliotecas de cada módulo (Bluetooth, JACK,
GStreamer, os codecs do rádio como sbc, lc3 e ldac, webrtc-audio-processing, ffado). O WirePlumber
pede o mesmo `meson` 1.7, o `liblua5.4-dev`, o `dh-sequence-gnome` e o sphinx.

**Com o BlueZ da casa instalado, o `libbluetooth-dev` vem primeiro.** O
`mk-build-deps` puxaria o do archive, e o apt rebaixaria o `libbluetooth3` da
casa para casar com ele. O script, ao listar o que falta, dá o comando com a
versão desta máquina; a forma é:

```bash
sudo apt install ~/.cache/hefesto-dualsense4unix/bluez-obra/libbluetooth-dev_<a versão do libbluetooth3>_amd64.deb
```

Depois, instale pelos dois `debian/control` e rode de novo:

```bash
cd ~/.cache/hefesto-dualsense4unix/pipewire-obra
sudo mk-build-deps -ir pipewire-1.6.9/debian/control
sudo mk-build-deps -ir wireplumber-0.5.18/debian/control
```

## Instalar

Trocar o PipeWire reinicia o som da sessão: os controles perdem o som e o
microfone por alguns segundos, e o jogo aberto pode perder a saída. Feche a
Steam antes.

1. Anote o antes: `pipewire --version`, `wpctl status` e o `doctor`.
2. Guarde as versões de agora, que são o caminho de volta. Entra só o que está
   instalado (`ii`) e tem versão, e sai o `pipewire-build-deps` do
   `mk-build-deps`: uma linha `pacote=` sem versão quebra o `apt install` da volta.

   ```bash
   dpkg-query -W -f='${db:Status-Abbrev}|${binary:Package}=${Version}\n' 'libpipewire*' \
       'libspa-0.2*' 'pipewire*' 'wireplumber*' 'libwireplumber*' 'gir1.2-wp*' 2>/dev/null \
       | awk -F'|' '$1 ~ /^ii/ && $2 !~ /-build-deps[:=]/ && $2 !~ /=$/ { print $2 }' \
       > ~/.cache/hefesto-dualsense4unix/pipewire-backport/VERSOES-ANTERIORES.txt
   ```

3. Fixe a prioridade do apt. O Pop fixa o repositório dele em 1001, e acima de
   1000 o apt rebaixa: o próximo `apt upgrade` trocaria a 1.6.9 da casa pela
   1.6.8. O arquivo da casa baixa só o PipeWire e o WirePlumber do Pop para 500,
   e o apt fica com a versão mais nova, a da casa ou a do Pop quando ela passar:

   ```bash
   sudo install -m 0644 assets/pipewire-backport/apt/hefesto-pipewire.pref \
       /etc/apt/preferences.d/hefesto-pipewire
   ```

4. Instale os pacotes que a máquina já tem, conferidos:

   ```bash
   cd ~/.cache/hefesto-dualsense4unix/pipewire-backport
   sha256sum -c SHA256SUMS
   debs=()
   for d in *.deb; do
       dpkg-query -W -f='${db:Status-Abbrev}' "${d%%_*}" 2>/dev/null | grep -q '^ii' && debs+=("./${d}")
   done
   sudo apt install "${debs[@]}"
   ```

   Se a máquina tem o `libspa-0.2-libcamera`, o apt o remove: ele depende da
   1.6.8 exata, e a 1.6.9 não o constrói. Só a câmera pelo PipeWire perde o
   caminho do libcamera; a pelo V4L2 continua.

5. Reinicie o som: `systemctl --user restart pipewire pipewire-pulse wireplumber`.
6. Meça o depois: `pipewire --version` diz 1.6.9, `wpctl status` responde, e o
   `doctor` não tem WARN em `pipewire`. Teste o som e o microfone de cada
   controle e feche a Steam pelo menu depois de jogar.

Para voltar: apague o `/etc/apt/preferences.d/hefesto-pipewire` e rode
`sudo apt install --allow-downgrades $(cat VERSOES-ANTERIORES.txt)`.

## O que muda para o Hefesto

Lido nos NEWS da 1.6.9 e do WirePlumber 0.5.13 ao 0.5.18. O que toca o código
do Hefesto, com o lugar dele, para conferir depois de instalar:

| Versão | Mudança | Onde o Hefesto depende |
|---|---|---|
| WirePlumber 0.5.18 | o `default-nodes` ordena os nós guardados só pela pilha, e o `priority.session` não passa por cima da última escolha do usuário (#1005) | `assets/wireplumber/51-hefesto-dualsense-no-default-source.conf:144-166`, `src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py:34`, `src/hefesto_dualsense4unix/integrations/alto_falante_bt.py:826` e `:2909` |
| WirePlumber 0.5.18 | o `prepare-link` destrói o fluxo com `node.dont-reconnect` quando o alvo some, como na 0.4, em vez de deixá-lo solto (#1026) | `src/hefesto_dualsense4unix/integrations/endpoint_de_haptica.py:807` e `src/hefesto_dualsense4unix/integrations/alto_falante_bt.py:2136`: o `pw-cat` da háptica e o ouvido saem quando o controle cai |
| WirePlumber 0.5.18 | o `find-best-profile` escolhe o perfil pela saída disponível antes da prioridade, e o nó ALSA que falha tem no máximo 3 tentativas, zeradas depois de 60 s sem erro | a placa USB do controle no cabo |
| WirePlumber 0.5.17 | o `default-nodes` desempata também pelo `object.serial` do aparelho e do nó | com quatro placas de controle no cabo, qual vira a saída padrão: `assets/wireplumber/51-hefesto-dualsense-no-default-source.conf:144-166` |
| WirePlumber 0.5.15 | o `wpctl` fala pelo socket do manager, e o acesso passa pelo `WpPermissionManager` | `scripts/fix_wireplumber_default_source.sh:325`, que lê o `wpctl status` |
| WirePlumber 0.5.14 | a fonte padrão nunca é um `Audio/Sink` sem escolha do usuário | `assets/wireplumber/51-hefesto-dualsense-no-default-source.conf:144-166` |
| WirePlumber 0.5.13 | os nós ganham as propriedades `alsa.*` do aparelho | os casamentos por `node.name` do mesmo drop-in |
| PipeWire 1.6.9 | o `pw-loopback` corrige o tratamento de canais e posições | `src/hefesto_dualsense4unix/integrations/laco_de_audio.py:79`, a háptica do cabo em 4 canais |
| PipeWire 1.6.9 | o upmix muda o volume do FC e do LFE, e o resampler preserva mais agudos | o som que o Hefesto leva ao controle |

O «Fix name of ALSA source» da 1.6.9 é do `module-alsa-source` do pulse, que o
Hefesto não carrega.

## Uma versão nova

Quando o upstream publicar outra estável:

1. baixe o arquivo da tag duas vezes e confira que os hashes batem;
2. troque no `BASELINE` a versão, o commit da tag (`git get-tar-commit-id`), a
   URL, o SHA-256 e a revisão, e confira se cada patch ainda aplica com
   `--preparar`;
3. abra a entrada nova em cada `changelog.*.hefesto`, com as linhas
   `Upstream:` e `Empacotamento:`;
4. rode a `--prova` e o teste
   `tests/unit/test_o_pipewire_da_casa_leva_a_cura_do_metadata.py`.
