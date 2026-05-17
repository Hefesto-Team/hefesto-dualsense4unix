# Pacote Fedora RPM — hefesto-dualsense4unix

RPM spec oficial para usuarios Fedora / CentOS Stream / RHEL / Rocky /
Alma / Nobara (comunitario, mantido junto ao source do projeto).

## Build local

```bash
# Setup do rpmdev tree (uma vez):
sudo dnf install rpm-build rpmdevtools
rpmdev-setuptree

# Copia o spec + builda:
cp packaging/fedora/hefesto-dualsense4unix.spec ~/rpmbuild/SPECS/

# Opcao A: build a partir do source local (modo dev).
rpmbuild --build-in-place -bb packaging/fedora/hefesto-dualsense4unix.spec

# Opcao B: build a partir do tarball do GitHub.
spectool -g -R packaging/fedora/hefesto-dualsense4unix.spec
rpmbuild -ba packaging/fedora/hefesto-dualsense4unix.spec
```

Resultado em `~/rpmbuild/RPMS/noarch/hefesto-dualsense4unix-3.4.0-1.fc40.noarch.rpm`.

Instalar com:

```bash
sudo dnf install ~/rpmbuild/RPMS/noarch/hefesto-dualsense4unix-3.4.0-*.rpm
```

## Submissao ao Copr (build farm comunitario)

Copr permite distribuir RPMs para Fedora sem passar pelo processo oficial
Fedora package review.

Passos:

1. Criar conta em <https://copr.fedorainfracloud.org/>.
2. Criar projeto novo, ex.: `hefesto-dualsense4unix`.
3. Habilitar chroots: `fedora-40-x86_64`, `fedora-41-x86_64`, etc.
4. Adicionar source: aponta para o `.spec` no repositorio GitHub via
   webhook ou Copr CLI:

   ```bash
   pip install copr-cli
   copr-cli create hefesto-dualsense4unix \
     --chroot fedora-40-x86_64 --chroot fedora-41-x86_64
   copr-cli build-package hefesto-dualsense4unix --name hefesto-dualsense4unix
   ```

5. Usuarios finais habilitam o repo com:

   ```bash
   sudo dnf copr enable [REDACTED]/hefesto-dualsense4unix
   sudo dnf install hefesto-dualsense4unix
   ```

## Submissao ao Fedora oficial

Apos o projeto sair de Alpha (v4.0+), considerar package review oficial:

1. Build local + test em mock (`mock -r fedora-40-x86_64 --rebuild
   hefesto-dualsense4unix-3.4.0-1.src.rpm`).
2. Submeter para pkgs.fedoraproject.org seguindo
   <https://docs.fedoraproject.org/en-US/package-maintainers/>.

## Dependencias DNF

| RPM package | Para que serve |
|---|---|
| `python3 >= 3.10` | Runtime |
| `python3-gobject` | Bindings PyGObject (GUI) |
| `gtk3` | Toolkit GUI |
| `libayatana-appindicator-gtk3` | Tray icon |
| `hidapi` | I/O hidraw |
| `libnotify` | D-Bus notifications |
| `python3-pydantic >= 2.0` | Schema validation |
| `python3-typer` | CLI framework |
| `python3-textual` | TUI |
| `python3-rich` | Rich output |
| `python3-evdev` | Input events |
| `python3-xlib` | X11 backend |
| `python3-structlog` | Logging |
| `python3-platformdirs` | XDG paths |
| `python3-filelock` | File locking |
| `python3-jeepney` | D-Bus async (cosmic backend) |

## Limitacoes conhecidas

- `pydualsense` puxado via pip durante build — sem RPM no Fedora ainda.
- `python-uinput` (extras emulation): Fedora tem `python3-python-uinput`
  em alguns chroots; spec atual NAO requer (apenas via pip se preciso).
- `dualsensectl` (aba Firmware): nao distribuido como RPM oficial; usuario
  precisa buildar do source (<https://github.com/nowrep/dualsensectl>).

Reportar bugs em <https://github.com/AndreBFarias/hefesto-dualsense4unix/issues>.
