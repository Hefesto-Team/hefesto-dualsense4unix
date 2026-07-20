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
Version:        3.14.0
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
# Onda T: modulo hid-nintendo patchado via DKMS (cura de raiz do probe BT
# dos controles Nintendo/8BitDo) — o install-host-udev.sh roda o build.
Recommends:     dkms

%description
Hefesto - Dualsense4Unix is a user-level Linux daemon that enables the
DualSense (PS5) adaptive triggers, with automatic per-window profile
switching, RGB lightbar, rumble, Xbox 360 controller emulation via
uinput, and a 9-tab GTK3 GUI (Status, Triggers, Lightbar, Rumble,
Profiles, Daemon, Emulation, Mouse, Keyboard).

It runs without root: udev rules and uinput module enable raw access
to /dev/hidraw* and /dev/uinput for the active user session.

After installation, start the daemon as user service:

    systemctl --user enable --now hefesto-dualsense4unix.service

Recommended optional packages:

    sudo dnf install wlrctl       # auto-switch in Wayland

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

# Udev rules — conjunto canônico (paridade com scripts/install_udev.sh).
# 73/74 (hotplug-GUI) descontinuadas e removidas do repo em 2026-07-18.
install -Dm644 -t %{buildroot}%{_udevrulesdir} \
    assets/70-ps5-controller.rules \
    assets/71-uhid.rules \
    assets/71-uinput.rules \
    assets/72-ps5-controller-autosuspend.rules \
    assets/76-dualsense-touchpad-libinput-ignore.rules \
    assets/77-dualsense-leds.rules \
    assets/78-dualsense-motion-not-joystick.rules \
    assets/79-external-controller-leds.rules \
    assets/80-motion-joydev-hide.rules \
    assets/81-hefesto-usb-power.rules \
    assets/81-hefesto-usb-host-power.rules
# Onda PLATAFORMA 2026-07-18: modprobe.d (cura do storm + btusb sem autosuspend).
install -Dm644 assets/modprobe/hefesto-dualsense-storm.conf \
    %{buildroot}/usr/lib/modprobe.d/hefesto-dualsense-storm.conf
install -Dm644 assets/modprobe.d/hefesto-btusb-no-autosuspend.conf \
    %{buildroot}/usr/lib/modprobe.d/hefesto-btusb-no-autosuspend.conf
# Onda T (2026-07-20): opções do hid-nintendo patchado (bt_probe_retries=3).
# Sem o módulo DKMS o in-tree ignora o parâmetro e sobe normal (fail-safe).
install -Dm644 assets/modprobe.d/hefesto-hid-nintendo.conf \
    %{buildroot}/usr/lib/modprobe.d/hefesto-hid-nintendo.conf
# Onda T (corretor, achado #9): a conf acima e INERTE sem o MODULO DKMS.
# Empacota as fontes + a lib generica; o install-host-udev.sh (abaixo) roda
# o dkms add/build/install no pos-instalacao (mesma instrucao do broker).
install -Dm644 scripts/dkms_lib.sh \
    %{buildroot}%{_datadir}/%{app_id}/scripts/dkms_lib.sh
mkdir -p %{buildroot}%{_datadir}/%{app_id}/dkms/hid-nintendo
cp -a assets/dkms/hid-nintendo/. \
    %{buildroot}%{_datadir}/%{app_id}/dkms/hid-nintendo/
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

# BROKER-01 (Onda S — fd-injection): binario standalone + units-template do
# broker root hide-hidraw. NAO ativa sozinho aqui — %post roda sem sessao de
# usuario (renderizaria uid 0, PROIBIDO — licao 6). O install-host-udev.sh
# acima (ja empacotado) e o caminho de ATIVACAO pos-instalacao.
install -Dm644 src/hefesto_dualsense4unix/broker/hidraw_broker.py \
    %{buildroot}%{_datadir}/%{app_id}/broker/hidraw_broker.py
install -Dm644 -t %{buildroot}%{_datadir}/%{app_id}/systemd/ \
    assets/systemd/hefesto-hidraw-broker.service \
    assets/systemd/hefesto-hidraw-broker.socket

%post
# Recarrega udev rules + carrega uinput. Idempotente.
/usr/sbin/udevadm control --reload-rules || :
/usr/sbin/udevadm trigger || :
/usr/sbin/modprobe uinput 2>/dev/null || :

cat <<MSG
Broker root hide-hidraw (BROKER-01 — esconde o controle FISICO do jogo,
cura de raiz do duplicado; requer sessao de usuario, NUNCA root puro) e
modulo DKMS hid-nintendo patchado (Onda T — cura de raiz do probe BT dos
controles Nintendo/8BitDo; requer dkms + kernel-devel):
  sudo %{_datadir}/%{app_id}/scripts/install-host-udev.sh
MSG

%preun
# BROKER-01 (achado #21): purge nao pode deixar a unit ROOT do broker orfa
# habilitada. disable+stop dispara o ExecStopPost --restore-all-and-exit da
# propria unit (nenhum hidraw fisico fica 0600 orfao); o belt explicito roda
# o MESMO restore ANTES do rpm apagar o binario (arquivos saem DEPOIS do
# %preun). So na remocao final ($1 -eq 0), nunca em upgrade.
if [ $1 -eq 0 ]; then
    /usr/bin/systemctl disable --now hefesto-hidraw-broker.socket \
        hefesto-hidraw-broker.service >/dev/null 2>&1 || :
    if [ -x /usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker ]; then
        /usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker \
            --restore-all-and-exit >/dev/null 2>&1 || :
    fi
    rm -f /etc/systemd/system/hefesto-hidraw-broker.service \
          /etc/systemd/system/hefesto-hidraw-broker.socket
    /usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
    # Onda T (corretor, achado #9): o modulo DKMS hefesto-hid-nintendo e
    # construido FORA do manifesto do rpm (install-host-udev.sh) — sem este
    # bloco, dnf remove deixava o modulo patchado registrado vencendo o
    # in-tree para sempre. NUNCA descarrega modulo em uso; o in-tree volta
    # sozinho no proximo boot.
    if command -v dkms >/dev/null 2>&1 \
            && dkms status hefesto-hid-nintendo 2>/dev/null | grep -q .; then
        dkms status hefesto-hid-nintendo 2>/dev/null \
            | sed -n 's|^hefesto-hid-nintendo/\([^,: ]*\).*|\1|p' | sort -u \
            | while read -r _v; do
                [ -n "${_v}" ] || continue
                dkms remove "hefesto-hid-nintendo/${_v}" --all >/dev/null 2>&1 || :
                rm -rf "/usr/src/hefesto-hid-nintendo-${_v}"
            done
        depmod -a >/dev/null 2>&1 || :
    fi
    rm -f /etc/modprobe.d/hefesto-hid-nintendo.conf
fi

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
%{_udevrulesdir}/71-uhid.rules
%{_udevrulesdir}/71-uinput.rules
%{_udevrulesdir}/72-ps5-controller-autosuspend.rules
%{_udevrulesdir}/76-dualsense-touchpad-libinput-ignore.rules
%{_udevrulesdir}/77-dualsense-leds.rules
%{_udevrulesdir}/78-dualsense-motion-not-joystick.rules
%{_udevrulesdir}/79-external-controller-leds.rules
%{_udevrulesdir}/80-motion-joydev-hide.rules
%{_udevrulesdir}/81-hefesto-usb-power.rules
%{_udevrulesdir}/81-hefesto-usb-host-power.rules
/usr/lib/modprobe.d/hefesto-dualsense-storm.conf
/usr/lib/modprobe.d/hefesto-btusb-no-autosuspend.conf
/usr/lib/modprobe.d/hefesto-hid-nintendo.conf
%{_modulesloaddir}/hefesto-dualsense4unix.conf
%{_userunitdir}/*.service
%{_datadir}/locale/*/LC_MESSAGES/hefesto-dualsense4unix.mo
%{_datadir}/%{app_id}/scripts/install-host-udev.sh
%{_datadir}/%{app_id}/scripts/dkms_lib.sh
%{_datadir}/%{app_id}/dkms/hid-nintendo/
%{_datadir}/%{app_id}/broker/hidraw_broker.py
%{_datadir}/%{app_id}/systemd/hefesto-hidraw-broker.service
%{_datadir}/%{app_id}/systemd/hefesto-hidraw-broker.socket

%changelog
* Sat May 16 2026 Vitoria Maria <[REDACTED]> - 3.4.0-1
- v3.4.0: i18n EN baseline + a11y ATK + packaging multi-distro + CI matrix.
- Initial RPM spec (FEAT-PACKAGING-FEDORA-01).
