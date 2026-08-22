# Nix flake — hefesto-dualsense4unix

Pacote Nix oficial para usuários NixOS / nix-darwin / nix em qualquer
distro Linux (comunitario, mantido junto ao source do projeto).

## Antes de rodar qualquer comando desta página

O `sha256` do `pydualsense` ainda é o placeholder `lib.fakeSha256` em
`packaging/nix/package.nix`, então **todo comando abaixo falha com
hash-mismatch** até alguém gravar o hash real: rode
`nix-prefetch-url https://pypi.org/packages/source/p/pydualsense/pydualsense-0.7.5.tar.gz`
numa máquina com nix e substitua o `lib.fakeSha256` pelo hash impresso (o
próprio erro do primeiro build também diz qual é). Sem isso não há caminho que
funcione — nem `nix run`, que não tem árvore local para corrigir.

## Uso rapido

```bash
# Direto do GitHub, sem clonar:
nix run github:Hefesto-Team/hefesto-dualsense4unix -- version

# Ou GUI:
nix run github:Hefesto-Team/hefesto-dualsense4unix#gui

# Instalar no perfil do usuario:
nix profile install github:Hefesto-Team/hefesto-dualsense4unix
```

## Build local

```bash
git clone https://github.com/Hefesto-Team/hefesto-dualsense4unix
cd hefesto-dualsense4unix

# Build do pacote:
nix build .#default

# Smoke test:
./result/bin/hefesto-dualsense4unix version
./result/bin/hefesto-dualsense4unix-gui
```

## Dev shell (com Python + pytest + ruff + mypy)

```bash
nix develop
# Dentro do shell:
python3 -m venv .venv
.venv/bin/pip install -e .[dev]
.venv/bin/pytest tests/unit -q
```

## NixOS — configuração do sistema

Adicionar ao `configuration.nix` ou `flake.nix` da maquina:

```nix
{
  inputs.hefesto.url = "github:Hefesto-Team/hefesto-dualsense4unix";

  outputs = { self, nixpkgs, hefesto, ... }: {
    nixosConfigurations.minha-maquina = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ({ pkgs, ... }: {
          environment.systemPackages = [
            hefesto.packages.${pkgs.system}.default
          ];

          # Habilita udev rules + carrega uinput.
          services.udev.packages = [
            hefesto.packages.${pkgs.system}.default
          ];
          boot.kernelModules = [ "uinput" ];

          # Habilita o servico systemd user.
          systemd.user.services.hefesto-dualsense4unix = {
            description = "Hefesto - Dualsense4Unix daemon";
            wantedBy = [ "default.target" ];
            serviceConfig = {
              ExecStart = "${hefesto.packages.${pkgs.system}.default}/bin/hefesto-dualsense4unix daemon start --foreground";
              Restart = "on-failure";
            };
          };
        })
      ];
    };
  };
}
```

## home-manager — configuração do usuário

```nix
{ pkgs, ... }: {
  home.packages = [
    inputs.hefesto.packages.${pkgs.system}.default
  ];

  systemd.user.services.hefesto-dualsense4unix = {
    Unit.Description = "Hefesto - Dualsense4Unix daemon";
    Install.WantedBy = [ "default.target" ];
    Service = {
      ExecStart = "${inputs.hefesto.packages.${pkgs.system}.default}/bin/hefesto-dualsense4unix daemon start --foreground";
      Restart = "on-failure";
    };
  };
}
```

## Dependências nixpkgs

Resolvidas automaticamente pela deriv (`packaging/nix/package.nix`):

| nixpkgs attr | Para que serve |
|---|---|
| `python3` | Runtime Python |
| `python3Packages.pygobject3` | GUI bindings |
| `gtk3` | Toolkit GUI |
| `libayatana-appindicator` | Tray icon |
| `hidapi` | I/O hidraw |
| `libnotify` | D-Bus notifications |
| `gettext` | Compila .mo no preBuild |
| `wrapGAppsHook` + `gobject-introspection` | wrap binário com GI_TYPELIB_PATH |

`pydualsense` (sem pacote em nixpkgs) eh declarado inline na deriv
via `python3Packages.buildPythonPackage` + `fetchPypi`.

## Atualização de versão

1. Bump `version = "3.4.0"` em `packaging/nix/package.nix`.
2. Se mudou hash do `pydualsense` no PyPI, atualizar `sha256`:
   ```bash
   nix-prefetch-url https://pypi.org/packages/source/p/pydualsense/pydualsense-0.x.y.tar.gz
   ```
3. Commit + push.

## Limitações conhecidas

- O `sha256` placeholder do `pydualsense` está na seção do topo — é a que
  impede qualquer comando desta página de funcionar.
- Sem submissao a nixpkgs oficial ainda; aguarda saida de Alpha (v4.0).
- Wayland backend `wlrctl` não bundlado; usuário instala via
  `environment.systemPackages = [ pkgs.wlrctl ];`.

Reportar bugs em <https://github.com/Hefesto-Team/hefesto-dualsense4unix/issues>.
