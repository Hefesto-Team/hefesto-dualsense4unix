# As versões em que isto funciona

- **Escrito em:** 11/08/2026, a pedido dela: *"talvez seja importante setar as
  versões que tudo funciona pro user, não?"*
- **Grau:** a coluna **validado** é o que rodou nesta bancada e foi medido. A
  coluna **faixa aceita** é o que o produto confere sozinho. O que não foi
  testado está dito com todas as letras — e é a maior parte

Antes deste documento, os números viviam em quatro arquivos diferentes e
nenhum sabia do outro. Quem fosse instalar em outra máquina não tinha onde
olhar. Agora tem, e um teste
(`tests/unit/test_versoes_validadas_batem_com_o_codigo.py`) reprova se este
documento e o código discordarem.

---

## O que o produto confere sozinho

| peça | faixa aceita | quem confere | o que acontece fora da faixa |
|---|---|---|---|
| **Python** | `>= 3.10` | `pyproject.toml` | a instalação não começa |
| **BlueZ** | `>= 5.79` e `< 5.87` | `scripts/doctor.sh` | abaixo: **reprova** (crashes crônicos de input/HIDP, 6 em 5 dias medidos). Acima: avisa, por causa do uso-depois-de-liberado em `dev_disconnected` |
| **Kernel, para o `rtw88-usb`** | só `7.0.11-76070011-*` | `assets/dkms/rtw88-usb/dkms.conf` | o módulo **não constrói, de propósito**, e o driver in-tree fica. Comportamento certo |
| **Kernel, para os outros dois DKMS** | sem trava | `scripts/doctor.sh` | avisa que o kernel difere do testado. O módulo pode construir e **mascarar um in-tree mais novo** |

## O que rodou de verdade

| peça | validado nesta bancada |
|---|---|
| Sistema | Pop!_OS 24.04, sessão COSMIC (Wayland) |
| Kernel | `7.0.11-76070011-generic` |
| Python | 3.12 |
| BlueZ | 5.86, e é um **backport desta casa** — o `apt` do 24.04 só oferece 5.72 |
| GTK | 3, por `python3-gi` do sistema |
| Formato de instalação | `native` (venv editável) |

## O que NÃO foi testado, e é honesto dizer

- **Nenhum kernel fora do `7.0.11-76070011-generic`.** Os forks de
  `hid-nintendo` e `hid-playstation` são o fonte daquela versão mais os patches
  da casa, e **não têm trava de kernel**. Em outra série, ou não constroem, ou
  constroem e mascaram um driver mais novo. É o furo com maior chance de decidir
  uma instalação em máquina nova.
- **Secure Boot ligado.** Com a chave MOK não enrolada, o kernel recusa o `.ko`
  e **não volta ao in-tree sozinho** — a máquina fica pior do que sem a cura. O
  `install.sh` avisa logo no passo 1, mas ninguém mediu o resultado.
- **Qualquer distro fora da família Debian.** O caminho nativo só sabe
  `apt-get`. Há pacote para Fedora, Arch e Nix, e **nenhum foi validado em
  hardware**.
- **Sessão que não seja COSMIC.** Muda quatro coisas de uma vez: a bandeja, o
  applet, o teclado na tela e a detecção de janela — que é quem troca o perfil
  quando o jogo abre.
- **BlueZ 5.87 ou mais novo.** O teto existe porque o 5.87 é a menor versão
  rejeitada conhecida; a correção está um commit depois da tag, e nenhum
  lançamento a carrega ainda.

## O que o `install.sh` instala por você

Desde 11/08/2026 ele garante, perguntando antes: `dkms`, `build-essential` e
`linux-headers` da sua versão de kernel. Sem eles os três módulos desta casa não
compilam — e antes disso o instalador seguia em silêncio, deixando a conferência
final sair verde com as curas ausentes.

Se você recusar, ou se os headers do seu kernel não existirem no repositório da
distro, o produto **continua funcionando** com os drivers in-tree: só sem as
curas. A conferência final diz quais faltaram.

## Se a sua máquina está fora da faixa

O `install.sh` faz um voo de reconhecimento no passo 1 e diz o que vai
atrapalhar, **antes** de mexer em qualquer coisa. Os mesmos três comandos, se
quiser conferir por conta própria:

```bash
cat /etc/os-release | head -3 ; echo "$XDG_CURRENT_DESKTOP / $XDG_SESSION_TYPE"
bluetoothctl --version
mokutil --sb-state 2>/dev/null || echo "sem Secure Boot"
```

Para o BlueZ abaixo de 5.79, a receita do backport está em
[estudo da Onda R](../process/estudos/2026-07-19-estudo-bluez-backport-onda-r.md).
