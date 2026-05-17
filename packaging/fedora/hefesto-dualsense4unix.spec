## RPM spec para o Hefesto - Dualsense4Unix.
## v3.4.0 (FEAT-PACKAGING-FEDORA-01).
##
## Estrategia: empacotamento Python 3 padrao (pyproject.toml + hatchling
## PEP 517). pydualsense vem do PyPI durante build (sem RPM no Fedora 40
## ainda). Outras deps Python ficam em RPMs python3-* nativos onde
## disponiveis.

%global pypi_name hefesto-dualsense4unix
%global app_id    hefesto-dualsense4unix

Name:           %{pypi_name}
Version:        3.4.0
Release:        1%{?dist}
Summary:        Linux adaptive trigger daemon for the PS5 DualSense controller

License:        MIT
URL:            https://github.com/AndreBFarias/%{pypi_name}
Source0:        %{url}/archive/v%{version}/%{pypi_name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel >= 3.10
BuildRequires:  python3-build
BuildRequires:  python3-wheel
BuildRequires:  python3-installer
BuildRequires:  python3-hatchling
BuildRequires:  python3-pip
BuildRequires:  gettext

# Runtime deps — packages no Fedora 40+.
Requires:       python3 >= 3.10
Requires:       python3-gobject
Requires:       gtk3
Requires:       libayatana-appindicator-gtk3
Requires:       hidapi
Requires:       libnotify
Requires:       python3-pydantic >= 2.0
Requires:       python3-typer
Requires:       python3-textual
Requires:       python3-rich
Requires:       python3-evdev
Requires:       python3-xlib
Requires:       python3-structlog
Requires:       python3-platformdirs
Requires:       python3-filelock
Requires:       python3-jeepney
# pydualsense puxado via pip no %install (sem RPM Fedora ainda).

Recommends:     wlrctl

%description
Hefesto - Dualsense4Unix is a user-level Linux daemon that enables the
DualSense (PS5) adaptive triggers, with automatic per-window profile
switching, RGB lightbar, rumble, Xbox 360 controller emulation via
uinput, and a 10-tab GTK3 GUI (Status, Triggers, Lightbar, Rumble,
Profiles, Daemon, Emulation, Mouse, Keyboard, Firmware).

It runs without root: udev rules and uinput module enable raw access
to /dev/hidraw* and /dev/uinput for the active user session.

After installation, start the daemon as user service:

    systemctl --user enable --now hefesto-dualsense4unix.service

Recommended optional packages:

    sudo dnf install wlrctl       # auto-switch in Wayland
    # dualsensectl                # for the Firmware tab (build from source)

%prep
%autosetup -n %{pypi_name}-%{version}

%build
# Compila catalogos i18n (.mo) antes do wheel — o include do
# pyproject.toml.[tool.hatch.build.targets.wheel] pega os arquivos
# em src/hefesto_dualsense4unix/locale/.
bash scripts/i18n_compile.sh

# PEP 517 wheel build (sem isolacao para reusar deps BuildRequires).
python3 -m build --wheel --no-isolation

%install
# Instala o wheel via python-installer (canonico no Fedora).
python3 -m installer --destdir=%{buildroot} \
    --prefix=%{_prefix} \
    dist/*.whl

# pydualsense via pip (sem RPM Fedora). --no-deps porque deps Python
# core ja vieram via RPM Requires.
pip3 install --root=%{buildroot} \
    --prefix=%{_prefix} \
    --no-deps \
    --no-build-isolation \
    --no-compile \
    "pydualsense>=0.7.5"

# Desktop entry.
install -Dm644 packaging/hefesto-dualsense4unix.desktop \
    %{buildroot}%{_datadir}/applications/%{app_id}.desktop

# Icone.
install -Dm644 assets/appimage/Hefesto-Dualsense4Unix.png \
    %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/%{app_id}.png

# Udev rules.
install -Dm644 -t %{buildroot}%{_udevrulesdir} \
    assets/70-ps5-controller.rules \
    assets/71-uinput.rules \
    assets/72-ps5-controller-autosuspend.rules \
    assets/73-ps5-controller-hotplug.rules \
    assets/74-ps5-controller-hotplug-bt.rules
install -Dm644 assets/hefesto-dualsense4unix.conf \
    %{buildroot}%{_modulesloaddir}/hefesto-dualsense4unix.conf

# Systemd user units.
mkdir -p %{buildroot}%{_userunitdir}
for unit in assets/*.service; do
    [ -f "$unit" ] || continue
    install -Dm644 "$unit" "%{buildroot}%{_userunitdir}/$(basename "$unit")"
done

# Catalogos i18n compilados.
if [ -d locale ]; then
    for lang_dir in locale/*/; do
        [ -d "$lang_dir" ] || continue
        lang="$(basename "$lang_dir")"
        mo="${lang_dir}LC_MESSAGES/hefesto-dualsense4unix.mo"
        [ -f "$mo" ] && install -Dm644 "$mo" \
            "%{buildroot}%{_datadir}/locale/${lang}/LC_MESSAGES/hefesto-dualsense4unix.mo"
    done
fi

# Helper de re-aplicacao de regras udev (para usuario rodar manualmente).
install -Dm755 scripts/install-host-udev.sh \
    %{buildroot}%{_datadir}/%{app_id}/scripts/install-host-udev.sh

%post
# Recarrega udev rules + carrega uinput. Idempotente.
/usr/sbin/udevadm control --reload-rules || :
/usr/sbin/udevadm trigger || :
/usr/sbin/modprobe uinput 2>/dev/null || :

%postun
if [ $1 -eq 0 ]; then
    # Remocao final — recarrega udev sem nossas regras.
    /usr/sbin/udevadm control --reload-rules || :
    /usr/sbin/udevadm trigger || :
fi

%files
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/hefesto-dualsense4unix
%{_bindir}/hefesto-dualsense4unix-gui
%{python3_sitelib}/hefesto_dualsense4unix/
%{python3_sitelib}/hefesto_dualsense4unix-*.dist-info/
%{python3_sitelib}/pydualsense/
%{python3_sitelib}/pydualsense-*.dist-info/
%{_datadir}/applications/%{app_id}.desktop
%{_datadir}/icons/hicolor/256x256/apps/%{app_id}.png
%{_udevrulesdir}/70-ps5-controller.rules
%{_udevrulesdir}/71-uinput.rules
%{_udevrulesdir}/72-ps5-controller-autosuspend.rules
%{_udevrulesdir}/73-ps5-controller-hotplug.rules
%{_udevrulesdir}/74-ps5-controller-hotplug-bt.rules
%{_modulesloaddir}/hefesto-dualsense4unix.conf
%{_userunitdir}/*.service
%{_datadir}/locale/*/LC_MESSAGES/hefesto-dualsense4unix.mo
%{_datadir}/%{app_id}/scripts/install-host-udev.sh

%changelog
* Sat May 16 2026 Vitoria Maria <[REDACTED]> - 3.4.0-1
- v3.4.0: i18n EN baseline + a11y ATK + packaging multi-distro + CI matrix.
- Initial RPM spec (FEAT-PACKAGING-FEDORA-01).
