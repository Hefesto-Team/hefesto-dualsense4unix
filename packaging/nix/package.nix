## packaging/nix/package.nix — derivation Nix do Hefesto - Dualsense4Unix.
## v3.4.0 (FEAT-PACKAGING-NIX-01).
##
## Carregada pelo flake.nix via callPackage. Mantida em arquivo separado
## para clareza e para permitir override de nixpkgs sem reescrever o
## flake (`nix build .#default --override-input nixpkgs ...`).

{ lib
, python3Packages
, fetchFromGitHub
, gtk3
, libayatana-appindicator
, hidapi
, libnotify
, gettext
, gobject-introspection
, wrapGAppsHook
, glib
, makeWrapper
}:

python3Packages.buildPythonApplication rec {
  pname = "hefesto-dualsense4unix";
  version = "3.4.0";
  pyproject = true;

  # Source local (clonado pelo flake). Em release tag, trocar por
  # fetchFromGitHub com tag estavel.
  src = ../..;

  build-system = with python3Packages; [
    hatchling
  ];

  nativeBuildInputs = [
    wrapGAppsHook
    gobject-introspection
    gettext
    makeWrapper
  ];

  buildInputs = [
    gtk3
    libayatana-appindicator
    hidapi
    libnotify
    glib
  ];

  # Compila catalogos i18n antes do build do wheel.
  # Roda como preBuild para garantir que src/hefesto_dualsense4unix/locale/
  # esteja populado quando hatchling embarcar via pyproject include.
  preBuild = ''
    bash scripts/i18n_compile.sh
  '';

  dependencies = with python3Packages; [
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
    # pydualsense nao esta em nixpkgs ainda — buildPythonPackage extra
    # abaixo dentro do propagatedBuildInputs como deriv inline.
    (python3Packages.buildPythonPackage rec {
      pname = "pydualsense";
      version = "0.7.5";
      pyproject = true;
      src = python3Packages.fetchPypi {
        inherit pname version;
        # Hash placeholder — substituir por sha256 real (gerar com
        # `nix-prefetch-url ...` ou deixar Nix calcular no primeiro build).
        sha256 = lib.fakeSha256;
      };
      build-system = with python3Packages; [ setuptools ];
      dependencies = with python3Packages; [ hidapi ];
      doCheck = false;
    })
  ];

  # Glade + assets + .mo ja vem via hatchling include do pyproject.toml.
  # Aqui copiamos udev rules, systemd units, .desktop, icone, locale para
  # /share/ canonico do Nix.
  postInstall = ''
    # Udev rules.
    install -Dm644 assets/70-ps5-controller.rules \
        $out/lib/udev/rules.d/70-ps5-controller.rules
    install -Dm644 assets/71-uinput.rules \
        $out/lib/udev/rules.d/71-uinput.rules
    install -Dm644 assets/72-ps5-controller-autosuspend.rules \
        $out/lib/udev/rules.d/72-ps5-controller-autosuspend.rules
    install -Dm644 assets/73-ps5-controller-hotplug.rules \
        $out/lib/udev/rules.d/73-ps5-controller-hotplug.rules
    install -Dm644 assets/74-ps5-controller-hotplug-bt.rules \
        $out/lib/udev/rules.d/74-ps5-controller-hotplug-bt.rules
    install -Dm644 assets/hefesto-dualsense4unix.conf \
        $out/lib/modules-load.d/hefesto-dualsense4unix.conf

    # Systemd user units (NixOS users carregam manualmente; non-NixOS
    # users wireiam via home-manager).
    for unit in assets/*.service; do
        [ -f "$unit" ] || continue
        install -Dm644 "$unit" $out/lib/systemd/user/$(basename "$unit")
    done

    # Desktop entry + icone.
    install -Dm644 packaging/hefesto-dualsense4unix.desktop \
        $out/share/applications/hefesto-dualsense4unix.desktop
    install -Dm644 assets/appimage/Hefesto-Dualsense4Unix.png \
        $out/share/icons/hicolor/256x256/apps/hefesto-dualsense4unix.png

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
  preFixup = ''
    gappsWrapperArgs+=(
      --prefix LD_LIBRARY_PATH : "${lib.makeLibraryPath [ libayatana-appindicator hidapi ]}"
    )
  '';

  # Skipa testes — suite de 1415+ assume hardware DualSense ou mocks
  # heavy; manter no CI principal, nao na deriv Nix.
  doCheck = false;

  meta = with lib; {
    description = "Linux adaptive trigger daemon for the PS5 DualSense controller (GTK3 GUI + CLI + TUI)";
    homepage = "https://github.com/AndreBFarias/hefesto-dualsense4unix";
    license = licenses.mit;
    platforms = platforms.linux;
    maintainers = [];
  };
}
