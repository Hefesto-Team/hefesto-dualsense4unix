## packaging/nix/package.nix — derivation Nix do Hefesto - DualSense4Unix.
## v3.4.0 (FEAT-PACKAGING-NIX-01).
##
## Carregada pelo flake.nix via callPackage. Mantida em arquivo separado
## para clareza e para permitir override de nixpkgs sem reescrever o
## flake (`nix build .#default --override-input nixpkgs ...`).

{ lib
, python3Packages
, fetchFromGitHub
, fetchurl
, gtk3
, libayatana-appindicator
, hidapi
, libnotify
# LOADER SVG DO GDK-PIXBUF (19/08/2026). CONFERIDO ANTES DE ACRESCENTAR: o
# runtime do Nix NAO o traz de graca. Em nixpkgs quem monta o
# `GDK_PIXBUF_MODULE_FILE` do wrapper e o setup-hook do gdk-pixbuf, e ele so
# junta os loaders dos pacotes que estao nos `buildInputs` DESTA derivacao —
# o `gtk3` nao propaga o `librsvg`. Sem ele o wrapper aponta para um
# loaders.cache sem svg, o pixbuf sai None em silencio, o icone da bandeja
# some da barra (app/tray.py) — BUG-TRAY-ICONE-INVISIVEL-01, descrito em
# app/arranque.py. Nao remova por parecer superfluo: o sintoma nao aponta para a
# causa. Paridade com librsvg2-common (.deb), librsvg2 (RPM) e librsvg (Arch);
# no Flatpak quem cobre e o proprio runtime (org.gnome.Platform//47 ja traz
# libpixbufloader_svg.so e librsvg-2.so.2 — medido em 19/08/2026).
, librsvg
, gettext
, gobject-introspection
, wrapGAppsHook3
, glib
, makeWrapper
# O-NIX-LEVA-AS-REGRAS-DO-HOST-01 (06/10/2026): o que os alvos das regras 82 e 83
# precisam no PATH quando o udev (ou o systemd) os roda, e o `systemctl` que a
# regra 83 chama. O `bluez` (o `hcitool` do no-sniff) é opcional: sem ele o
# `bt_nosniff_now.sh` registra que não aplicou, e não quebra.
, coreutils
, findutils
, gawk
, util-linux
, systemd
, bluez ? null
# TECLADO-QUE-NAO-DIGITA-01: o teclado na tela que o L3 do controle abre. Vem
# como argumento com default `null` de proposito — `callPackage` passa
# `pkgs.wvkbd` quando o atributo existe (nixpkgs by-name/wv/wvkbd) e cai no
# default quando nao existe, entao um nixpkgs mais velho nao QUEBRA a
# derivacao por causa de um acessorio. O `null` e tratado abaixo.
, wvkbd ? null
}:

python3Packages.buildPythonApplication rec {
  pname = "hefesto-dualsense4unix";
  version = "0.9.5";
  pyproject = true;

  # Source local (clonado pelo flake). Em release tag, trocar por
  # fetchFromGitHub com tag estavel.
  src = ../..;

  build-system = with python3Packages; [
    hatchling
  ];

  nativeBuildInputs = [
    wrapGAppsHook3
    gobject-introspection
    gettext
    makeWrapper
  ];

  buildInputs = [
    gtk3
    libayatana-appindicator
    hidapi
    libnotify
    # Aqui, e nao em nativeBuildInputs: o que o setup-hook do gdk-pixbuf varre
    # para montar o GDK_PIXBUF_MODULE_FILE do wrapper sao os buildInputs. Ver o
    # comentario do argumento `librsvg` no topo.
    librsvg
    glib
  ];

  # Compila catalogos i18n antes do build do wheel.
  # Roda como preBuild para garantir que src/hefesto_dualsense4unix/locale/
  # esteja populado quando hatchling embarcar via pyproject include.
  preBuild = ''
    bash scripts/i18n_compile.sh
  '';

  # O `hidapiUsb` mora AQUI e não num `let` no topo: o `check_version_consistency.py` lê a
  # primeira `version = "...";` do arquivo, e ela tem de ser a do próprio pacote.
  dependencies =
    let
    # O módulo `hidapi` do PyPI `hidapi-usb` 0.3.2 (CFFI sobre a libhidapi), que o
    # nixpkgs não empacota. O sdist é imutável pelo endereço por conteúdo do
    # próprio PyPI; o sha256 em hexa (a31a7eda…c8164d) é o que o PyPI publica para
    # o arquivo, e foi conferido contra o download em 07/10/2026.
    hidapiUsb = python3Packages.buildPythonPackage {
      pname = "hidapi-usb";
      version = "0.3.2";
      pyproject = true;
      src = fetchurl {
        url = "https://files.pythonhosted.org/packages/55/80/960ae94b615e26a7d1aeebe8e9fefda2f25608bf1016f9aec268b328c35e/hidapi_usb-0.3.2.tar.gz";
        hash = "sha256-oxp+2i+qqYd1uwiS2Dh8/PzO62iYQQXpR936MnDIFk0=";
      };
      build-system = with python3Packages; [ setuptools wheel ];
      dependencies = with python3Packages; [ cffi ];
      # O módulo faz `ffi.dlopen` de nomes SEM caminho (libhidapi-hidraw.so, ...)
      # e levanta OSError no import se nenhum abre. No Nix a libhidapi não está em
      # nenhum caminho de busca da construção: o caminho absoluto do nixpkgs vai na
      # frente da lista (hidraw, que é o backend dos caminhos /dev/hidraw*), e os
      # nomes soltos seguem como estavam.
      postPatch = ''
        substituteInPlace hidapi.py \
          --replace-fail "library_paths = (" \
          "library_paths = ('${lib.getLib hidapi}/lib/libhidapi-hidraw.so.0',"
      '';
      pythonImportsCheck = [ "hidapi" ];
      doCheck = false;
    };
    in
    with python3Packages; [
    pygobject3
    pydantic
    typer
    textual
    rich
    evdev
    python-xlib
    structlog
    platformdirs
    filelock
    jeepney
    pyyaml
    # pydualsense nao esta em nixpkgs ainda — buildPythonPackage extra
    # abaixo dentro do propagatedBuildInputs como deriv inline.
    (python3Packages.buildPythonPackage rec {
      pname = "pydualsense";
      version = "0.7.5";
      pyproject = true;
      src = python3Packages.fetchPypi {
        inherit pname version;
        # O sdist de 0.7.5 no PyPI, 101042 bytes. O sha256 em hexa
        # (6205fc00…702a0b) é o que o próprio PyPI publica para o arquivo, e foi
        # conferido contra o download em 06/10/2026.
        hash = "sha256-YgX8AJE4f8p7geKT3xlCD0Mlh1GcyHpBz4rEIqdwKgs=";
      };
      build-system = with python3Packages; [ poetry-core ];
      # O `pydualsense` 0.7.5 declara `hidapi-usb (>=0.3.2,<0.4.0)` e faz
      # `import hidapi` (pydualsense/pydualsense.py:17). O `python3Packages.hidapi`
      # do nixpkgs é OUTRO pacote (o `import hid`, em Cython): dava o nome certo
      # da biblioteca e não o módulo, e a checagem de dependências da construção
      # reprovava com `hidapi-usb not installed` (CI do dev, 07/10/2026).
      dependencies = [ hidapiUsb ];
      # Sem a lista de testes: a suíte é do repo, não do sdist. O import PROVA o
      # par inteiro (módulo `hidapi` + a libhidapi achada) ainda na construção.
      pythonImportsCheck = [ "pydualsense" ];
      doCheck = false;
    })
  ];

  # Glade + assets + .mo ja vem via hatchling include do pyproject.toml.
  # Aqui copiamos udev rules, systemd units, .desktop, icone, locale para
  # /share/ canonico do Nix.
  postInstall = ''
    # Udev rules.
    #
    # O-NO-NASCE-FECHADO-01 (auditoria de 20/09/2026, bloqueante 3): a regra do
    # no (a 73-hefesto, que era a 70 ate 25/09/2026) vai
    # para o diretorio VIVO na variante ABERTA, e nao e opiniao — e a unica
    # metade da cura que este pacote consegue entregar. O asset versionado
    # fecha o no do DualSense (TAG-="uaccess", 0600 root) contando que o broker
    # o abra sob pedido; e o broker e um servico de SISTEMA instalado fora
    # desta derivacao. Gravar o asset fechado aqui deixaria o DualSense
    # inutilizavel — e o produto e para qualquer usuario (ordem dela,
    # 11/09/2026).
    bash scripts/regra_do_no_aberta.sh assets/73-hefesto-ps5-controller.rules \
        $out/lib/udev/rules.d/73-hefesto-ps5-controller.rules
    install -Dm644 assets/71-uinput.rules \
        $out/lib/udev/rules.d/71-uinput.rules
    # 71-uhid: /dev/uhid — o gamepad virtual vira um DualSense de verdade (hidraw +
    # lightbar + LEDs), o que faz a vibração funcionar também com a máscara DualSense.
    # O número precisa ser < 73 (a 73-seat-late.rules é quem vira a TAG uaccess em ACL).
    install -Dm644 assets/71-uhid.rules \
        $out/lib/udev/rules.d/71-uhid.rules
    install -Dm644 assets/72-ps5-controller-autosuspend.rules \
        $out/lib/udev/rules.d/72-ps5-controller-autosuspend.rules
    # 72-hefesto-touchpad-motion-uaccess: touchpad e sensores de movimento com
    # ACL da sessão. A 70-uaccess.rules do sistema só cobre ID_INPUT_JOYSTICK, e
    # o kernel classifica esses dois nós como touchpad/acelerômetro — sem esta
    # regra ficam root:input e só funcionam para quem está no grupo `input` por
    # fora do produto. OQ-6. O número precisa ser < 73.
    install -Dm644 assets/72-hefesto-touchpad-motion-uaccess.rules \
        $out/lib/udev/rules.d/72-hefesto-touchpad-motion-uaccess.rules
    # As 73/74 (GUI auto-spawn no hotplug) foram DESCONTINUADAS e REMOVIDAS do
    # repositorio em 2026-07-18 — este postInstall continuava instalando as
    # duas e o build quebrava aqui, antes mesmo do fakeSha256 do pydualsense.
    # A lista abaixo e a canonica (mesma de install_udev.sh/build_deb.sh);
    # a 75 (disable-usb-audio) fica de fora porque e opt-in.
    install -Dm644 assets/76-dualsense-touchpad-libinput-ignore.rules \
        $out/lib/udev/rules.d/76-dualsense-touchpad-libinput-ignore.rules
    install -Dm644 assets/77-dualsense-leds.rules \
        $out/lib/udev/rules.d/77-dualsense-leds.rules
    install -Dm644 assets/78-dualsense-motion-not-joystick.rules \
        $out/lib/udev/rules.d/78-dualsense-motion-not-joystick.rules
    install -Dm644 assets/79-external-controller-leds.rules \
        $out/lib/udev/rules.d/79-external-controller-leds.rules
    install -Dm644 assets/80-motion-joydev-hide.rules \
        $out/lib/udev/rules.d/80-motion-joydev-hide.rules
    install -Dm644 assets/81-hefesto-usb-power.rules \
        $out/lib/udev/rules.d/81-hefesto-usb-power.rules
    install -Dm644 assets/81-hefesto-usb-host-power.rules \
        $out/lib/udev/rules.d/81-hefesto-usb-host-power.rules
    install -Dm644 assets/82-nintendo-pro-nosniff.rules \
        $out/lib/udev/rules.d/82-nintendo-pro-nosniff.rules
    install -Dm644 assets/83-hefesto-bond-snapshot.rules \
        $out/lib/udev/rules.d/83-hefesto-bond-snapshot.rules
    install -Dm644 assets/84-nintendo-pro-variant.rules \
        $out/lib/udev/rules.d/84-nintendo-pro-variant.rules
    install -Dm644 assets/85-hefesto-o-cabo-assume.rules \
        $out/lib/udev/rules.d/85-hefesto-o-cabo-assume.rules
    install -Dm644 assets/hefesto-dualsense4unix.conf \
        $out/lib/modules-load.d/hefesto-dualsense4unix.conf

    # OS ALVOS DAS REGRAS 82 E 83 (O-NIX-LEVA-AS-REGRAS-DO-HOST-01, 06/10/2026).
    # As duas regras chamam, com `TEST==`, `/usr/local/lib/hefesto-dualsense4unix/…`
    # e `/usr/bin/systemctl`, caminhos de HOST que o Nix não tem: sem os alvos a
    # regra vira inércia silenciosa (o `TEST==` a deixa calada). O jeito do Nix é
    # levar os alvos DENTRO do $out e reescrever o caminho da regra para ele, que
    # é o que o `services.udev.packages` do módulo NixOS (packaging/nix/module.nix)
    # carrega. `--replace-fail` de propósito: se a regra mudar de caminho, o build
    # reprova em vez de entregar a regra apontando para o nada.
    install -Dm755 scripts/bt_nosniff_now.sh \
        $out/libexec/hefesto-dualsense4unix/bt_nosniff_now.sh
    install -Dm755 scripts/bt_bonds_snapshot.sh \
        $out/libexec/hefesto-dualsense4unix/bt_bonds_snapshot.sh
    install -Dm644 assets/systemd/hefesto-bt-bonds-snapshot.service \
        $out/lib/systemd/system/hefesto-bt-bonds-snapshot.service
    install -Dm644 assets/systemd/hefesto-bt-bonds-snapshot.timer \
        $out/lib/systemd/system/hefesto-bt-bonds-snapshot.timer
    substituteInPlace $out/lib/udev/rules.d/82-nintendo-pro-nosniff.rules \
        --replace-fail /usr/local/lib/hefesto-dualsense4unix \
                       $out/libexec/hefesto-dualsense4unix
    substituteInPlace $out/lib/udev/rules.d/83-hefesto-bond-snapshot.rules \
        --replace-fail /usr/local/lib/hefesto-dualsense4unix \
                       $out/libexec/hefesto-dualsense4unix \
        --replace-fail /usr/bin/systemctl ${systemd}/bin/systemctl
    substituteInPlace $out/lib/systemd/system/hefesto-bt-bonds-snapshot.service \
        --replace-fail /usr/local/lib/hefesto-dualsense4unix \
                       $out/libexec/hefesto-dualsense4unix
    # O udev e o systemd rodam o alvo com o PATH deles, que não tem `find`,
    # `flock` nem `logger`: o wrapper entrega o que o script chama.
    wrapProgram $out/libexec/hefesto-dualsense4unix/bt_nosniff_now.sh \
        --prefix PATH : ${lib.makeBinPath ([ coreutils util-linux ] ++ lib.optional (bluez != null) bluez)}
    wrapProgram $out/libexec/hefesto-dualsense4unix/bt_bonds_snapshot.sh \
        --prefix PATH : ${lib.makeBinPath [ coreutils findutils gawk util-linux ]}

    # Systemd user units (NixOS users carregam manualmente; non-NixOS
    # users wireiam via home-manager).
    for unit in assets/*.service; do
        [ -f "$unit" ] || continue
        install -Dm644 "$unit" $out/lib/systemd/user/$(basename "$unit")
    done

    # Desktop entry + icone.
    install -Dm644 packaging/hefesto-dualsense4unix.desktop \
        $out/share/applications/hefesto-dualsense4unix.desktop
    # PACKAGING-ICON-NAME-MISMATCH-01: o nome do arquivo TEM de casar o
    # `Icon=hefesto` do .desktop instalado logo acima (compartilhado por todos
    # os formatos) — como hefesto-dualsense4unix.png o lancador ficava sem
    # icone. Paridade com o build_deb.sh, que ja usava hefesto.png.
    # Os DOIS nomes: o .desktop pede Icon=hefesto e o codigo pede o nome longo
    # (scripts/abrir_interface.py set_default_icon_name, app/tray.py TRAY_ICON_NAME).
    install -Dm644 assets/appimage/Hefesto-Dualsense4Unix.png \
        $out/share/icons/hicolor/256x256/apps/hefesto.png
    install -Dm644 assets/appimage/Hefesto-Dualsense4Unix.png \
        $out/share/icons/hicolor/256x256/apps/hefesto-dualsense4unix.png
    # APPLET-MONOCROMÁTICO-01 (07/08/2026): o ícone SIMBÓLICO da bandeja. O
    # código pede `hefesto-dualsense4unix-symbolic` (app/tray.py), e esse nome
    # NÃO se satisfaz com PNG: PNG nunca é recolorido pelo tema, e o ícone
    # ficaria o único cromático do painel. Destino `symbolic/apps/`.
    install -Dm644 assets/simbolico/hefesto-dualsense4unix-symbolic.svg \
        $out/share/icons/hicolor/symbolic/apps/hefesto-dualsense4unix-symbolic.svg

    # OS CINCO SCRIPTS QUE O PRODUTO EXECUTA (25/08/2026, BG-04). Ate aqui so o
    # .deb os levava (build_deb.sh:234): quem instalava por aqui apertava
    # "Deixar tudo pronto" ou o botao do microfone e recebia "Script do
    # WirePlumber nao encontrado", com um unico conselho — rodar um
    # ./install.sh que nao existe na maquina de quem nao clonou o repositorio.
    # Quem consome cada um esta escrito no manifesto do Flatpak, dono unico
    # dessa lista.
    #
    # A METADE QUE ESTA AQUI E A METADE QUE FALTA, dito de frente: o Nix nao
    # tem /usr/share, e $out/share/hefesto-dualsense4unix/scripts NAO e uma das
    # bases que BASES_DE_INSTALACAO (app/actions/daemon_actions.py) procura
    # hoje — ela conhece a raiz do checkout, /app/share (Flatpak), /usr/share e
    # /usr/local/share. Levar os arquivos e condicao NECESSARIA e nao
    # suficiente: enquanto o consumidor nao olhar para `sys.prefix/share/
    # hefesto-dualsense4unix`, o botao continua sem achar. A lacuna esta
    # DECLARADA em _PRODSCRIPT_LACUNAS_HOJE, em
    # scripts/check_packaging_parity.sh, e o portao reprova quando ela caducar.
    #
    # Sem patchShebangs: o fixup do nixpkgs so o roda em bin/sbin/libexec, e
    # $out/share fica de fora. Os cinco comecam com `#!/usr/bin/env bash`, que
    # resolve pelo PATH de quem os chama — e quem os chama e o proprio produto,
    # ja embrulhado pelo wrapGAppsHook.
    # Um `install` por linha, e nao um laco, pela mesma razao que o resto deste
    # postInstall: nome literal e o que qualquer leitor — pessoa ou portao —
    # enxerga sem interpretar shell. A primeira versao daqui usava um `for`
    # com a lista quebrada em duas linhas, e o check_packaging_parity.sh
    # reprovou dizendo que o doctor.sh chamava um irmao que este arquivo NAO
    # levava (25/08/2026). Aquele ponto cego do portao foi curado no mesmo dia
    # (as continuacoes agora sao dobradas antes do grep); o nome literal fica
    # porque e mais claro, nao porque o portao ainda precise dele.
    install -Dm755 scripts/doctor.sh \
        $out/share/hefesto-dualsense4unix/scripts/doctor.sh
    install -Dm755 scripts/bluez_config.sh \
        $out/share/hefesto-dualsense4unix/scripts/bluez_config.sh
    install -Dm755 scripts/disable_steam_input.sh \
        $out/share/hefesto-dualsense4unix/scripts/disable_steam_input.sh
    install -Dm755 scripts/fix_wireplumber_default_source.sh \
        $out/share/hefesto-dualsense4unix/scripts/fix_wireplumber_default_source.sh
    install -Dm755 scripts/install_snd_quirk.sh \
        $out/share/hefesto-dualsense4unix/scripts/install_snd_quirk.sh

    # Catalogos i18n compilados.
    if [ -d locale ]; then
      for lang_dir in locale/*/; do
        [ -d "$lang_dir" ] || continue
        lang="$(basename "$lang_dir")"
        mo="''${lang_dir}LC_MESSAGES/hefesto-dualsense4unix.mo"
        [ -f "$mo" ] && install -Dm644 "$mo" \
          "$out/share/locale/''${lang}/LC_MESSAGES/hefesto-dualsense4unix.mo"
      done
    fi
  '';

  # Wrappa o binario com GI_TYPELIB_PATH e LD_LIBRARY_PATH para o
  # libayatana-appindicator ser descoberto em runtime.
  #
  # E com o TECLADO NA TELA no PATH (TECLADO-QUE-NAO-DIGITA-01): o daemon
  # resolve `wvkbd-mobintl` por `shutil.which` quando o L3 pede o teclado na
  # tela, e sem ele o unico caminho do produto para ESCREVER TEXTO com o
  # controle nao existe (nenhum dos nove atalhos de fabrica digita LETRA).
  # `--suffix` e nao `--prefix` de proposito: um wvkbd que a usuaria ja tenha
  # no ambiente vence o nosso.
  #
  # So o wvkbd, e nao o onboard: em NixOS a sessao e Wayland na esmagadora
  # maioria, o wvkbd digita pelo zwp_virtual_keyboard_manager_v1 (nativo) e o
  # onboard digita por XTEST — em Wayland ele abriria e nao digitaria fora do
  # XWayland. Quem estiver em X11 instala o onboard no proprio perfil, e o
  # scripts/doctor.sh diz isso com todas as letras.
  preFixup = ''
    gappsWrapperArgs+=(
      --prefix LD_LIBRARY_PATH : "${lib.makeLibraryPath [ libayatana-appindicator hidapi ]}"
      ${lib.optionalString (wvkbd != null)
        ''--suffix PATH : "${lib.makeBinPath [ wvkbd ]}"''}
    )
  '';

  # Skipa testes — suite de 1415+ assume hardware DualSense ou mocks
  # heavy; manter no CI principal, nao na deriv Nix.
  doCheck = false;

  meta = with lib; {
    description = "Linux adaptive trigger daemon for the PS5 DualSense controller (GTK3 GUI + CLI + TUI)";
    homepage = "https://github.com/Hefesto-Team/hefesto-dualsense4unix";
    license = licenses.mit;
    platforms = platforms.linux;
    maintainers = [];
  };
}
