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
# PACKAGING-EPOCH-DOWNGRADE-01: a numeracao voltou de 4.0.0 para 0.1.0 em
# 2026-07-24. Para o rpm/dnf, 0.3.0 e DOWNGRADE de qualquer 3.x/4.0 ja
# instalado e o upgrade e RECUSADO. O Epoch vence a comparacao de Version e e
# o unico jeito de a serie 0.x suceder a 4.0. Mesmo valor do .deb e do PKGBUILD.
Epoch:          1
Version:        0.9.3
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
# TECLADO-QUE-NAO-DIGITA-01: o teclado na tela que o L3 do controle abre.
# Sem ele nenhum atalho de fabrica digita LETRA (os nove sao Super,
# PrintScreen, Alt+Tab, Alt+Shift+Tab, Enter, Delete, Backspace e os dois
# tokens de OSK) — o unico caminho para ESCREVER TEXTO com o controle.
#
# wvkbd primeiro porque digita pelo zwp_virtual_keyboard_manager_v1 (Wayland
# nativo); onboard digita por XTEST, que em sessao Wayland so alcanca janelas
# XWayland. Weak dependency de proposito: o produto inteiro funciona sem, e
# `Recommends` do RPM e IGNORADO em silencio quando o pacote nao existe nos
# repositorios habilitados — nao trava a instalacao em nenhuma spin. Quem diz
# a verdade sobre a maquina depois e o scripts/doctor.sh.
Recommends:     wvkbd
Suggests:       onboard

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
    sudo dnf install wvkbd        # on-screen keyboard opened by L3 (Wayland)
    sudo dnf install onboard      # same, for X11 sessions

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

# Icone. PACKAGING-ICON-NAME-MISMATCH-01: o nome do arquivo TEM de casar o
# `Icon=hefesto` do packaging/hefesto-dualsense4unix.desktop (compartilhado por
# todos os formatos) — instalar como %{app_id}.png deixava o lancador sem
# icone. Paridade com o build_deb.sh, que ja usava hefesto.png.
# Os DOIS nomes: o .desktop pede Icon=hefesto e o codigo pede o nome longo
# (app/main.py set_default_icon_name, app/tray.py TRAY_ICON_NAME). So um deles
# troca o lancador sem icone pela bandeja com joystick generico.
install -Dm644 assets/appimage/Hefesto-Dualsense4Unix.png \
    %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/hefesto.png
install -Dm644 assets/appimage/Hefesto-Dualsense4Unix.png \
    %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/hefesto-dualsense4unix.png

# APPLET-MONOCROMÁTICO-01 (07/08/2026): o ícone SIMBÓLICO da bandeja. O código
# pede `hefesto-dualsense4unix-symbolic` (app/tray.py), e esse nome NÃO se
# satisfaz com PNG: PNG nunca é recolorido pelo tema, e o ícone ficaria o único
# cromático do painel. Destino `symbolic/apps/`.
install -Dm644 assets/simbolico/hefesto-dualsense4unix-symbolic.svg \
    %{buildroot}%{_datadir}/icons/hicolor/symbolic/apps/hefesto-dualsense4unix-symbolic.svg

# Udev rules — conjunto canônico (paridade com scripts/install_udev.sh).
# 73/74 (hotplug-GUI) descontinuadas e removidas do repo em 2026-07-18.
# As 82/83/84 (no-sniff do Pro, snapshot de bond, variante do clone 8BitDo)
# faltavam aqui: o install-host-udev.sh exige TODAS as 14 no pre-flight.
install -Dm644 -t %{buildroot}%{_udevrulesdir} \
    assets/70-ps5-controller.rules \
    assets/71-uhid.rules \
    assets/71-uinput.rules \
    assets/72-ps5-controller-autosuspend.rules \
    assets/72-hefesto-touchpad-motion-uaccess.rules \
    assets/76-dualsense-touchpad-libinput-ignore.rules \
    assets/77-dualsense-leds.rules \
    assets/78-dualsense-motion-not-joystick.rules \
    assets/79-external-controller-leds.rules \
    assets/80-motion-joydev-hide.rules \
    assets/81-hefesto-usb-power.rules \
    assets/81-hefesto-usb-host-power.rules \
    assets/82-nintendo-pro-nosniff.rules \
    assets/83-hefesto-bond-snapshot.rules \
    assets/84-nintendo-pro-variant.rules
# Onda PLATAFORMA 2026-07-18: modprobe.d (cura do storm + btusb sem autosuspend).
install -Dm644 assets/modprobe/hefesto-dualsense-storm.conf \
    %{buildroot}/usr/lib/modprobe.d/hefesto-dualsense-storm.conf
install -Dm644 assets/modprobe.d/hefesto-btusb-no-autosuspend.conf \
    %{buildroot}/usr/lib/modprobe.d/hefesto-btusb-no-autosuspend.conf
# Onda T (2026-07-20): opções do hid-nintendo patchado (bt_probe_retries=3).
# Sem o módulo DKMS o in-tree ignora o parâmetro e sobe normal (fail-safe).
install -Dm644 assets/modprobe.d/hefesto-hid-nintendo.conf \
    %{buildroot}/usr/lib/modprobe.d/hefesto-hid-nintendo.conf
# Contencao BT (2026-07-25): opcoes do hid-playstation patchado
# (feature_retries=2). Mesmo fail-safe: sem o modulo DKMS o in-tree ignora.
install -Dm644 assets/modprobe.d/hefesto-hid-playstation.conf \
    %{buildroot}/usr/lib/modprobe.d/hefesto-hid-playstation.conf
# Onda T (corretor, achado #9): a conf acima e INERTE sem o MODULO DKMS.
# Empacota as fontes + a lib generica; o install-host-udev.sh (abaixo) roda
# o dkms add/build/install no pos-instalacao (mesma instrucao do broker).
install -Dm644 scripts/dkms_lib.sh \
    %{buildroot}%{_datadir}/%{app_id}/scripts/dkms_lib.sh
mkdir -p %{buildroot}%{_datadir}/%{app_id}/dkms/hid-nintendo
cp -a assets/dkms/hid-nintendo/. \
    %{buildroot}%{_datadir}/%{app_id}/dkms/hid-nintendo/
# Contencao BT (2026-07-25): fontes do hid-playstation patchado (retry de
# feature report na probe) — mesma paridade da Onda T/W.
mkdir -p %{buildroot}%{_datadir}/%{app_id}/dkms/hid-playstation
cp -a assets/dkms/hid-playstation/. \
    %{buildroot}%{_datadir}/%{app_id}/dkms/hid-playstation/
# Onda W (2026-07-20): fontes DKMS do rtw88_usb patchado (device-gone +
# port reset — cura de raiz do fantasma USB do dongle WiFi). Mesma rota da
# Onda T: o install-host-udev.sh roda o dkms add/build/install no host.
mkdir -p %{buildroot}%{_datadir}/%{app_id}/dkms/rtw88-usb
cp -a assets/dkms/rtw88-usb/. \
    %{buildroot}%{_datadir}/%{app_id}/dkms/rtw88-usb/
# CR-05 (07/08/2026): a GPL-2.0, secao 1, exige que a copia do texto da licenca
# viaje JUNTO com o fonte. Os tres diretorios acima sao GPL (o rtw88-usb e
# GPL-2.0 OR BSD-3-Clause, licenca dupla), e ate 07/08 nenhum texto os
# acompanhava. Procedencia em LICENSES/README.md.
mkdir -p %{buildroot}%{_datadir}/%{app_id}/dkms/LICENSES
cp -a LICENSES/. \
    %{buildroot}%{_datadir}/%{app_id}/dkms/LICENSES/
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
modulos DKMS patchados hid-nintendo (Onda T — cura de raiz do probe BT dos
controles Nintendo/8BitDo) e rtw88_usb (Onda W — cura de raiz do fantasma
USB do dongle WiFi; requer dkms + kernel-devel):
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
    rm -f /etc/modprobe.d/hefesto-hid-playstation.conf
    # Onda W: o modulo DKMS hefesto-rtw88-usb tambem nasce FORA do manifesto
    # do rpm (install-host-udev.sh) — mesma simetria: sem este bloco, dnf
    # remove deixava o patchado registrado vencendo o in-tree para sempre.
    # NUNCA descarrega modulo em uso (o WiFi cairia); o in-tree volta
    # sozinho no proximo boot.
    if command -v dkms >/dev/null 2>&1 \
            && dkms status hefesto-rtw88-usb 2>/dev/null | grep -q .; then
        dkms status hefesto-rtw88-usb 2>/dev/null \
            | sed -n 's|^hefesto-rtw88-usb/\([^,: ]*\).*|\1|p' | sort -u \
            | while read -r _v; do
                [ -n "${_v}" ] || continue
                dkms remove "hefesto-rtw88-usb/${_v}" --all >/dev/null 2>&1 || :
                rm -rf "/usr/src/hefesto-rtw88-usb-${_v}"
            done
        depmod -a >/dev/null 2>&1 || :
        # belt (simetrico ao uninstall.sh nativo): desarma o reset agressivo a
        # quente se o patchado ainda estiver carregado (o modulo em uso nunca
        # e descarregado — o WiFi cairia).
        if [ -e /sys/module/rtw88_usb/parameters/hang_reset ]; then
            printf '0' > /sys/module/rtw88_usb/parameters/hang_reset 2>/dev/null || :
        fi
    fi
    # Contencao BT: o modulo DKMS hefesto-hid-playstation tambem nasce FORA do
    # manifesto do rpm (install-host-udev.sh) — mesma simetria. NUNCA
    # descarrega o modulo em uso: derrubaria TODOS os DualSense, inclusive os
    # por Bluetooth; o in-tree volta sozinho no proximo boot.
    if command -v dkms >/dev/null 2>&1 \
            && dkms status hefesto-hid-playstation 2>/dev/null | grep -q .; then
        dkms status hefesto-hid-playstation 2>/dev/null \
            | sed -n 's|^hefesto-hid-playstation/\([^,: ]*\).*|\1|p' | sort -u \
            | while read -r _v; do
                [ -n "${_v}" ] || continue
                dkms remove "hefesto-hid-playstation/${_v}" --all >/dev/null 2>&1 || :
                rm -rf "/usr/src/hefesto-hid-playstation-${_v}"
            done
        depmod -a >/dev/null 2>&1 || :
        # belt (simetrico ao uninstall.sh nativo): devolve o feature_retries a
        # 0 se o patchado ainda estiver carregado. E lido a cada probe, entao
        # a proxima conexao ja e vanilla — sem recarregar nada.
        if [ -e /sys/module/hid_playstation/parameters/feature_retries ]; then
            printf '0' > /sys/module/hid_playstation/parameters/feature_retries 2>/dev/null || :
        fi
    fi
    # INITRAMFS-01: os `dkms remove` acima limpam /lib/modules, mas o initramfs
    # guarda uma COPIA dos .ko e seguiria entregando os modulos do hefesto no
    # boot. Regenera uma vez, best-effort (nunca falha a transacao do rpm).
    if command -v dracut >/dev/null 2>&1; then
        dracut --force >/dev/null 2>&1 || :
    elif command -v update-initramfs >/dev/null 2>&1; then
        update-initramfs -u >/dev/null 2>&1 || :
    fi
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
%{_datadir}/icons/hicolor/256x256/apps/hefesto.png
%{_datadir}/icons/hicolor/256x256/apps/hefesto-dualsense4unix.png
%{_datadir}/icons/hicolor/symbolic/apps/hefesto-dualsense4unix-symbolic.svg
%{_udevrulesdir}/70-ps5-controller.rules
%{_udevrulesdir}/71-uhid.rules
%{_udevrulesdir}/71-uinput.rules
%{_udevrulesdir}/72-ps5-controller-autosuspend.rules
%{_udevrulesdir}/72-hefesto-touchpad-motion-uaccess.rules
%{_udevrulesdir}/76-dualsense-touchpad-libinput-ignore.rules
%{_udevrulesdir}/77-dualsense-leds.rules
%{_udevrulesdir}/78-dualsense-motion-not-joystick.rules
%{_udevrulesdir}/79-external-controller-leds.rules
%{_udevrulesdir}/80-motion-joydev-hide.rules
%{_udevrulesdir}/81-hefesto-usb-power.rules
%{_udevrulesdir}/81-hefesto-usb-host-power.rules
%{_udevrulesdir}/82-nintendo-pro-nosniff.rules
%{_udevrulesdir}/83-hefesto-bond-snapshot.rules
%{_udevrulesdir}/84-nintendo-pro-variant.rules
/usr/lib/modprobe.d/hefesto-dualsense-storm.conf
/usr/lib/modprobe.d/hefesto-btusb-no-autosuspend.conf
/usr/lib/modprobe.d/hefesto-hid-nintendo.conf
/usr/lib/modprobe.d/hefesto-hid-playstation.conf
%{_modulesloaddir}/hefesto-dualsense4unix.conf
%{_userunitdir}/*.service
%{_datadir}/locale/*/LC_MESSAGES/hefesto-dualsense4unix.mo
%{_datadir}/%{app_id}/scripts/install-host-udev.sh
%{_datadir}/%{app_id}/scripts/dkms_lib.sh
%{_datadir}/%{app_id}/dkms/hid-nintendo/
# Contencao BT (2026-07-25): as fontes do hid-playstation eram INSTALADAS no
# %install e nao apareciam aqui — com %_unpackaged_files_terminate_build no
# default o rpmbuild ABORTAVA com "Installed (but unpackaged) file(s) found",
# ou seja o spec inteiro nao compilava.
%{_datadir}/%{app_id}/dkms/hid-playstation/
%{_datadir}/%{app_id}/dkms/rtw88-usb/
%{_datadir}/%{app_id}/broker/hidraw_broker.py
%{_datadir}/%{app_id}/systemd/hefesto-hidraw-broker.service
%{_datadir}/%{app_id}/systemd/hefesto-hidraw-broker.socket

%changelog
* Sun Aug 02 2026 Vitoria Maria <[REDACTED]> - 1:0.9.3-1
- Sete presets de gatilho nao faziam nada: tres mandavam o modo que vale OFF
  no firmware e quatro mandavam modo oficial sem o bitmask de zonas ativas
- Aba Status passou a dizer o que CHEGA ao jogo, e nao so o que existe
- Cura do rumble preso: o report de parada do SDL vem com os flags zerados e
  era descartado pelo filtro de vibracao
- Alto-falante ganhou o pre-amplificador e a rota de saida (os 60% de curso
  que estavam inertes)
- Botao do microfone parou de mutar o microfone de outro aparelho no Bluetooth
- A mascara escolhida no perfil parou de virar Xbox sozinha ao salvar

* Sat Aug 01 2026 Vitoria Maria <[REDACTED]> - 1:0.7.0-1
- Aba Status alinhada: as duas linhas do card passam a dividir o mesmo
  desenho, o frame Estado cai para tres linhas e a bateria ocupa a largura
  inteira sem o numero boiando no meio da barra
- Botao da rota de som mudou para o bloco Alto-falante do card; "sem dado"
  saiu dos botoes de microfone e alto-falante
- Mascara Xbox passa a dizer o que custa: sem giroscopio e sem touchpad no
  jogo (a API do controle de Xbox nao tem os dois)
- Metricas ganham chave de usuario (HEFESTO_DUALSENSE4UNIX_METRICS_ENABLED
  e _METRICS_PORT), cumprindo a decisao registrada na ADR-016
- Quadrado vermelho ao lado dos interruptores curado (icone quebrado do GTK)

* Sat Aug 01 2026 Vitoria Maria <[REDACTED]> - 1:0.6.0-1
- A leva do alto-falante: o bloco da aba Status ganhou controle deslizante,
  botao de mudo e devolucao da posse, com o preco escrito na propria interface.
- O controle deslizante percorre a faixa que o registrador de fato usa: medido
  no hardware, os primeiros 15 por cento do curso emudecem e os ultimos 60 nao
  mudam nada, entao a escala passou a ser remapeada para a faixa util.
- O botao de mudo nasce insensivel enquanto nao ha volume conhecido: um mudo
  como primeira escrita trancaria o alto-falante em zero sem o proprio botao
  poder solta-lo.
- Um selo avisa quando quem esta mudo e o sistema, e nao o registrador do
  controle: sao duas verdades diferentes, e a que decide se sai som e a do
  PipeWire.
- O perfil ganhou secao propria de alto-falante, que fica de fora do arquivo
  quando nao ha opiniao.
- O clique do touchpad passou a chegar ao jogo: o leitor tinha o byte na mao e
  o descartava.
- O emblema de testes deixou de declarar contagem exata, que envelhecia a cada
  leva, e o portao de anonimato deixou de aprovar quando nao conseguia auditar.

* Fri Jul 31 2026 Vitoria Maria <[REDACTED]> - 1:0.5.0-1
- A leva da auditoria: treze agentes mediram o projeto e um verificador
  independente reenquadrou tres dos oito achados graves.
- O instalador voltou a rearmar as curas de modulo: quatro portoes testavam
  permissao de escrita num arquivo de root, davam sempre falso, e o ciclo de
  desinstalar e instalar desligava seis curas em silencio ate o proximo boot.
- A aba Status passou a ocupar o vao lateral (desenhos de 180 para 360px) e o
  teto elastico chegou as seis abas que faltavam.
- A janela parou de perder a reconciliacao, o Restaurar Padrao deixou de morrer
  em instalacao empacotada, e salvar perfil passou a comparar por slug.
- O NOTICE declarou os tres drivers de kernel GPL-2.0 embarcados.
* Thu Jul 30 2026 Vitoria Maria <[REDACTED]> - 1:0.4.0-1
- Os tres automatismos: o R1 parou de virar Alt+Tab dentro do jogo, o perfil
  passou a guardar as outras abas, e a fonte de captura padrao voltou a ser um
  microfone de verdade em vez do monitor do alto-falante do proprio controle.
- O caminho de ativacao do .deb estava morto (espelho de regras udev parava na
  81 e o helper abortava exigindo as 14); hefesto-hid-playstation passou a ser
  desregistrado na remocao; e o %files deixou de omitir o que o %install grava.

* Wed Jul 29 2026 Vitoria Maria <[REDACTED]> - 1:0.3.0-1
- Epoch 1: a numeracao voltou de 4.0.0 para 0.1.0 em 2026-07-24 e, sem epoch,
  o dnf tratava 0.3.0 como downgrade de 3.4.0 e RECUSAVA o upgrade. O topo
  deste changelog tambem estava em 3.4.0-1, acima do proprio Version do spec.
- Regras udev 82/83/84 (no-sniff do Pro, snapshot de bond, variante do clone
  8BitDo) empacotadas: o install-host-udev.sh exige todas as 14 no pre-flight.
- dkms/hid-playstation listado na secao files — ele era instalado e nao
  empacotado, e o rpmbuild abortava com "Installed (but unpackaged) file(s)".
- Icone instalado como hefesto.png, casando o Icon= do .desktop compartilhado.

* Sat May 16 2026 Vitoria Maria <[REDACTED]> - 3.4.0-1
- v3.4.0: i18n EN baseline + a11y ATK + packaging multi-distro + CI matrix.
- Initial RPM spec (FEAT-PACKAGING-FEDORA-01).
