## packaging/nix/module.nix — o módulo NixOS do Hefesto - DualSense4Unix.
##
## O-NIX-LEVA-AS-REGRAS-DO-HOST-01 (06/10/2026). Uma derivation só escreve em
## `$out`, e as regras udev 82 e 83 chamam alvos que, nos outros formatos, moram
## no host (`/usr/local/lib/hefesto-dualsense4unix`, `/etc/systemd/system`). O
## `TEST==` das duas regras deixava isso calado: quem instalava pelo Nix tinha as
## regras e nenhum alvo, e nada falhava.
##
## O jeito do Nix é levar os alvos DENTRO do pacote e apontar a regra para eles:
## o `package.nix` instala os dois scripts em `$out/libexec/hefesto-dualsense4unix`,
## a unidade do snapshot dos bonds em `$out/lib/systemd/system`, e reescreve os
## caminhos das regras (e o `systemctl`) para o store. Este módulo só liga o que o
## NixOS precisa para o pacote valer na máquina:
##
##   * `services.udev.packages`: as regras (e o `TEST==` delas acha o alvo);
##   * `systemd.packages`: a unidade do snapshot dos bonds e o timer dela;
##   * `boot.kernelModules`: `uinput` e `uhid`, o que o `modules-load.d` do
##     pacote pede nos outros formatos;
##   * o diretório de estado do snapshot, que a unidade declara em
##     `ReadWritePaths=` e sem o qual ela não sobe.
##
## Uso:
##
##   imports = [ hefesto.nixosModules.default ];   # ou ./packaging/nix/module.nix
##   services.hefesto-dualsense4unix.enable = true;
##
## O daemon de usuário e a interface continuam sendo do perfil de quem usa: o
## módulo não escreve em `$HOME` de ninguém.

{ config, lib, pkgs, ... }:

let
  cfg = config.services.hefesto-dualsense4unix;
in
{
  options.services.hefesto-dualsense4unix = {
    enable = lib.mkEnableOption ''
      as regras udev do Hefesto - DualSense4Unix, os alvos delas no host e o
      snapshot dos bonds do Bluetooth
    '';

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ./package.nix { };
      defaultText = lib.literalExpression "pkgs.callPackage ./package.nix { }";
      description = ''
        O pacote que leva as regras udev, os alvos delas e a unidade do snapshot.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ cfg.package ];

    # As regras 82 e 83 já saem do pacote apontando para o store.
    services.udev.packages = [ cfg.package ];

    # A unidade e o timer do snapshot dos bonds: a regra 83 inicia a unidade pelo
    # nome a cada conexão HID, e o timer a repete de quinze em quinze minutos.
    systemd.packages = [ cfg.package ];
    systemd.timers.hefesto-bt-bonds-snapshot.wantedBy = [ "timers.target" ];

    # `ReadWritePaths=/var/lib/hefesto-dualsense4unix` na unidade: o systemd recusa
    # montar o espaço de nomes se o caminho não existe.
    systemd.tmpfiles.rules = [
      "d /var/lib/hefesto-dualsense4unix 0755 root root -"
    ];

    # O que o `hefesto-dualsense4unix.conf` do pacote carrega nos outros formatos.
    boot.kernelModules = [ "uinput" "uhid" ];
  };
}
