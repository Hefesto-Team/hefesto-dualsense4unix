# Pacote Arch Linux — hefesto-dualsense4unix

PKGBUILD oficial para usuarios Arch / Manjaro / EndeavourOS / SteamOS
(comunitario, mantido junto ao source do projeto).

## Build local

```bash
cd packaging/arch
makepkg -si
```

Vai:

1. Baixar o tarball do release v3.4.0 do GitHub.
2. Verificar deps (`python-gobject`, `gtk3`, `libayatana-appindicator`, etc).
3. Compilar catalogos i18n (`scripts/i18n_compile.sh`).
4. Buildar wheel via `python -m build`.
5. Instalar com `python -m installer` em `/usr/`.
6. Puxar `pydualsense` do PyPI (sem pacote pacman ainda).
7. Empacotar udev rules, systemd units, `.desktop`, locale.
8. Disparar `hefesto-dualsense4unix.install` (post_install): recarrega
   udev + carrega modulo `uinput`.

Resultado em `~/.cache/yay/hefesto-dualsense4unix/*.pkg.tar.zst` (ou
similar dependendo do helper AUR).

## Submissao ao AUR

Quando o projeto sair de Alpha (v4.0+), considerar submeter ao AUR
oficialmente.

Passos:

1. Clonar o repo do AUR vazio:
   ```bash
   git clone ssh://aur@aur.archlinux.org/hefesto-dualsense4unix.git
   ```
2. Copiar `PKGBUILD` + `hefesto-dualsense4unix.install` + gerar
   `.SRCINFO`:
   ```bash
   cp ../path/to/packaging/arch/{PKGBUILD,hefesto-dualsense4unix.install} .
   makepkg --printsrcinfo > .SRCINFO
   ```
3. Commit + push:
   ```bash
   git add PKGBUILD hefesto-dualsense4unix.install .SRCINFO
   git commit -m "v3.4.0 — initial release"
   git push origin master
   ```

## Atualizacao de versao

A cada release nova:

1. Bump `pkgver=` no PKGBUILD.
2. `makepkg --printsrcinfo > .SRCINFO`.
3. Commit + push.

Optional: substituir `sha256sums=('SKIP')` por checksum real via
`makepkg -g >> PKGBUILD` apos baixar o tarball.

## Dependencias do pacman

| Pacman package | Para que serve |
|---|---|
| `python>=3.10` | Runtime Python |
| `python-gobject` | Bindings PyGObject (GUI GTK3) |
| `python-cairo` | Cairo bindings (renderizacao) |
| `gtk3` | Toolkit GUI |
| `libayatana-appindicator` | Tray icon (KDE / COSMIC compativel) |
| `hidapi` | I/O hidraw (DualSense USB e BT) |
| `libnotify` | D-Bus desktop notifications |
| `python-pydantic`, `python-typer`, etc | Stack do daemon |

## Limitacoes conhecidas

- `pydualsense` puxado do PyPI durante `package()` — sem mirror em
  Arch ainda. Build precisa de internet.
- `python-uinput` (extras emulation) e `python-jeepney` (extras cosmic)
  vem do pacman. Sem optional installs separados ainda.

Reportar bugs em <https://github.com/AndreBFarias/hefesto-dualsense4unix/issues>.
