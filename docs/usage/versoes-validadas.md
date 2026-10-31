# As versões em que isto funciona

O que o produto confere sozinho, o que rodou na máquina de teste e o que ainda
não foi testado. A página e o código são conferidos juntos por
`tests/unit/test_versoes_validadas_batem_com_o_codigo.py`.

## O que o produto confere sozinho

| Peça | Faixa aceita | Quem confere | Fora da faixa |
|---|---|---|---|
| Python | `>= 3.10` | `pyproject.toml` | a instalação não começa |
| BlueZ | `>= 5.79` e `< 5.87` | `hefesto-dualsense4unix doctor` | abaixo de 5.79, reprova (o `bluetoothd` trava com vários controles); de 5.87 em diante, avisa (há um defeito conhecido na desconexão) |
| Kernel, para os módulos do Hefesto (`hid-playstation`, `hid-nintendo`, `uhid`, `usb-f-hid`, `rtw88-usb`) | o que roda, quando o fonte de fábrica dele se acha e a série de `patch/` aplica sem fuzz | o `preparar-o-fonte.py` de cada módulo, no `dkms build`, e o `hefesto-dualsense4unix doctor` | o módulo não é compilado, o driver de fábrica fica, e o doctor diz o que falta (a fonte do kernel da distro, a rede até o git.kernel.org ou o rebase da série). Sem o `hid-playstation` do Hefesto, o microfone pelo Bluetooth não liga |

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

- **Outros kernels.** Medido em contêiner, sem controle: no Arch com o 7.2.11, os cinco
  módulos compilam do stable v7.2.11 conferido pelo `srcversion` do de fábrica, com a série
  rebaseada para o 7.2.6 nos módulos que a guardam; no Ubuntu 24.04 com o 7.0.0-42, só o `usb-f-hid`
  acha o fonte (o kernel da distro traz mudanças que o stable não tem), e os outros ficam no
  de fábrica com o motivo no doctor.
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
