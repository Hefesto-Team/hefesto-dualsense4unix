# As versões em que isto funciona

O que o produto confere sozinho, o que rodou na máquina de teste e o que ainda
não foi testado. A página e o código são conferidos juntos por
`tests/unit/test_versoes_validadas_batem_com_o_codigo.py`.

## O que o produto confere sozinho

| Peça | Faixa aceita | Quem confere | Fora da faixa |
|---|---|---|---|
| Python | `>= 3.10` | `pyproject.toml` | a instalação não começa |
| BlueZ | `>= 5.79` e `< 5.87` | `hefesto-dualsense4unix doctor` | abaixo de 5.79, reprova (o `bluetoothd` trava com vários controles); de 5.87 em diante, avisa (há um defeito conhecido na desconexão) |
| Kernel, para o `hid-playstation` e o `uhid` | só `7.1.5-76070105` | o `dkms.conf` de cada módulo | o módulo não é compilado e o driver de fábrica fica. Sem o `hid-playstation` do Hefesto, o microfone pelo Bluetooth não liga |
| Kernel, para o `rtw88-usb` | `7.0.11-76070011` e `7.1.5-76070105` | `assets/dkms/rtw88-usb/dkms.conf` | o módulo não é compilado e o driver de fábrica fica |
| Kernel, para o `hid-nintendo` | sem trava | `hefesto-dualsense4unix doctor` | avisa quando o kernel difere do testado (`7.0.11-76070011-generic`): o módulo pode compilar e esconder um driver de fábrica mais novo |

As versões das bibliotecas Python que rodaram com os controles estão em
`constraints.txt`, e o instalador as usa.

## O que rodou na máquina de teste

| Peça | Versão |
|---|---|
| Sistema | Pop!_OS 24.04, sessão COSMIC (Wayland) |
| Kernel | `7.0.11-76070011-generic` e `7.1.5-76070105-generic` |
| Python | 3.12 |
| BlueZ | 5.86, pelo BlueZ corrigido que o instalador oferece (o apt do 24.04 tem o 5.72) |
| Instalação | `./install.sh`, formato nativo |

## O que não foi testado

- **Outros kernels.** O `hid-nintendo` não tem trava de kernel: em outra série
  ele pode não compilar, ou compilar e esconder um driver mais novo. É o ponto
  com mais chance de decidir uma instalação em outra máquina.
- **Secure Boot ligado.** Sem a chave do DKMS inscrita, o instalador não
  instala os módulos e diz como inscrevê-la; o resultado depois da inscrição
  não foi medido.
- **Distribuições fora da família Debian.** O instalador conhece apt, dnf e
  pacman, e há pacotes para Fedora, Arch e Nix; nenhum foi testado com um
  controle ligado.
- **Sessões que não sejam o COSMIC.** Mudam a bandeja, o teclado na tela e a
  forma de descobrir o jogo em foco, que é o que troca o perfil.
- **BlueZ 5.87 ou mais novo.** A correção do defeito da desconexão veio depois
  da tag 5.87, e nenhuma versão lançada a traz ainda.

## Conferir a sua máquina

O instalador confere antes de mudar qualquer coisa. Para ver por conta própria:

```bash
grep PRETTY_NAME /etc/os-release; echo "$XDG_CURRENT_DESKTOP / $XDG_SESSION_TYPE"
uname -r
bluetoothctl --version
hefesto-dualsense4unix doctor
```

Para o BlueZ abaixo de 5.79, a receita do BlueZ corrigido está em
[receita-backport-bluez.md](receita-backport-bluez.md).
