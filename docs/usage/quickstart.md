# Quickstart

```bash
git clone <repo> hefesto && cd hefesto
./scripts/dev_bootstrap.sh
./scripts/install_udev.sh
```

Reconectar o DualSense. Verificar acesso:

```bash
ls -l /dev/hidraw*   # deve mostrar acesso pelo usuário atual
```

Rodar:

```bash
hefesto daemon start --foreground
```

Em outro terminal:

```bash
hefesto status
hefesto test trigger --side right --mode Rigid --params 5,200
```

Instalar como serviço do usuário:

```bash
hefesto daemon install-service
systemctl --user enable --now hefesto.service
```

Ver logs:

```bash
journalctl --user -u hefesto -f
```
