# Nix flake — Hefesto - Dualsense4Unix.
# v3.4.0 (FEAT-PACKAGING-NIX-01).
#
# Uso (NixOS, nix-shell, qualquer plataforma com nix):
#   nix build .#default                  # build do pacote
#   nix run .#default -- version         # smoke test
#   nix shell .#default                  # entra em shell com binario no PATH
#   nix profile install .#default        # instala no perfil do usuario
#
# Ou de qualquer maquina com nix instalado, direto do GitHub:
#   nix run github:AndreBFarias/hefesto-dualsense4unix -- version
{
  description = "Hefesto - Dualsense4Unix: Linux adaptive trigger daemon for the PS5 DualSense controller";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        package = pkgs.callPackage ./packaging/nix/package.nix { };
      in {
        packages = {
          default = package;
          hefesto-dualsense4unix = package;
        };

        apps = {
          default = {
            type = "app";
            program = "${package}/bin/hefesto-dualsense4unix";
          };
          gui = {
            type = "app";
            program = "${package}/bin/hefesto-dualsense4unix-gui";
          };
        };

        devShells.default = pkgs.mkShell {
          inputsFrom = [ package ];
          packages = with pkgs; [
            python3
            python3Packages.pip
            python3Packages.build
            python3Packages.hatchling
            gettext
            ruff
            mypy
          ];
          shellHook = ''
            echo "Hefesto - Dualsense4Unix dev shell"
            echo "Python: $(python3 --version)"
            echo "Compile catalogos i18n: bash scripts/i18n_compile.sh"
            echo "Run baseline: pytest tests/unit -q"
          '';
        };
      });
}
