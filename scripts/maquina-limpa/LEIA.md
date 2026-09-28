# A máquina limpa sem outra máquina: a escada

O pedido dela, 27/09/2026: que qualquer pessoa com um COSMIC, um adaptador
Bluetooth, um cabo e um DualSense reproduza o que esta casa mede. A escada
prova isso sem outra máquina, **mudando uma variável por degrau**. Cada degrau
cita a linha do retrato (P0) que ele mudou, e cada resultado vira uma linha
do `docs/data/ensaios.csv`, escrita por quem mediu.

Nasceu da `O-PRODUTO-EM-QUALQUER-MAQUINA-01` (28/09/2026). Os degraus moram
aqui, versionados, porque um roteiro que só existe num estudo fora do git não
chega a quem vai reproduzir.

| degrau | muda | alcança | como |
|---|---|---|---|
| P0 | nada (o retrato) | as variáveis desta máquina | `o_basico.py retrato`, da `O-BASICO-MEDIDO-01` |
| P1 | o HOME | o plano de usuária; a prova de que o ensaio não escreve | `p1-lar-vazio.sh` |
| P2 | a interface num HOME vazio, sem aparelho | a primeira pintura das dez abas | a bancada de tela em lar de mentira, de quem coordena |
| P3 | a distro e o pip | o install como usuária, o `evdev` do pip, o `dkms build -k`, a receita do BlueZ, a sobra do uninstall | `p3-conteiner.sh` |
| P4 | o sistema inteiro, depois um aparelho por vez | cabo, rádio, pareamento do zero, Secure Boot, a Steam instalada depois | `p4-vm.sh` |
| P5 | o usuário (segunda conta) | o broker com outro uid; o `uaccess` sem o grupo `input` | só com ela: troca a tela dela |
| P6 | o chip do adaptador | o teto de pontes por chip | só com um adaptador de outro fabricante |

## P0, o retrato

É o `o_basico.py retrato` da `O-BASICO-MEDIDO-01`. Além do que ele já grava,
entram as variáveis que a bancada escondia (a C19 da contraprova e a L7):

- o pai do `cosmic-osk` (ele é de toda sessão COSMIC: a vibração nula a ~20 por
  segundo por pad, e a classe da queda da sessão, são de qualquer pessoa);
- a regra 60 do `input-remapper`, que roda `autoload` em todo nó novo;
- a GPU;
- as unidades de usuário que reagem à Steam e ao Heroic;
- o compositor contra o pacote (`dpkg -V cosmic-comp`);
- o grupo `input` da sessão;
- o Secure Boot, lido pela efivars (o último byte da `SecureBoot-*`).

## P1 — `p1-lar-vazio.sh`

O `install.sh --dry-run --yes` numa cópia da árvore (`git archive`), com o
HOME e os cinco `XDG_*` num lar novo, sem D-Bus e sem tela. **Espera-se:**
`rc=0` e o «FIM DO ENSAIO»; zero arquivos no lar; «config intacta» (a config
de quem roda só é lida por `sha256`, antes e depois).

**Limite do degrau:** os passos de root dizem o estado DESTA máquina (o DKMS
já instalado, o BlueZ curado). Isso se anota, não é defeito.

## P2 — a primeira pintura

A receita é a bancada de tela em lar de mentira de quem coordena (o piloto
`hefesto_vivo.py` com `--oculta`, Xvfb e D-Bus próprios, um daemon de
mentira). Duas variantes do daemon de mentira: zero controles, e um só pelo
rádio, sem nome. Abre as dez abas e grava o texto de cada uma. **Espera-se:**
nenhuma ocorrência de nome de pessoa, de «bancada» ou de cor de plástico de
alguém; a frase do estado vazio; zero `Traceback` no log da interface do lar.

## P3 — `p3-conteiner.sh`

O `scripts/ci/instalar_como_usuaria.sh` — o mesmo instrumento do job
`install-multi-distro` do CI — em quatro imagens: `ubuntu:24.04` com as fontes
do Pop desta máquina (o Pop sem a parte gráfica), `fedora:42`,
`archlinux:latest` e `debian:12`. Com `--dkms`, mede o `dkms build -k` e o
`make` direto do `hid-playstation` contra os headers da distro (a L6: o rc 77
é o pino, de propósito, e o `make` direto diz se o fonte compila ali). Com
`--bluez`, roda a receita do backport do BlueZ no Pop (a L2).

**As travas:** a árvore nunca é montada (o roteiro do CI faz `chown -R` da
raiz), entra por tarball só de leitura; nada de `--privileged` nem `--device`.

**Espera-se:** `rc_install=0` nas quatro; os avisos que uma pessoa nova lê
(entre eles o «Reinicie» do fecho e o do microfone pelo rádio); as versões do
`constraints.txt` no `pip list`; a lista de `[FAIL]`/`[WARN]` de uma máquina
sem controle; e a sobra do uninstall, que se confere contra o que o produto
declara deixar.

O job `install-multi-distro` do CI ganha as mesmas imagens e o passo do
`dkms build -k` na onda em que o `ci.yml` volta a esta sprint.

## P4 — `p4-vm.sh`

A VM KVM **sem janela** (`-display none`), dirigida pelo QMP; cada tela vem
por `foto` para um PNG. Precisa de `qemu-system-x86`, `qemu-utils` e `ovmf`
— o pedido 1 dela. Sem eles, o script diz isso e sai.

- **P4a — cabo.** Pop!_OS COSMIC novo, o install com a árvore servida do
  host, e um DualSense passado pelo cabo (`passar <hostbus> <hostaddr> <id>
  --sei-que-tira`). Antes e depois do reinício: o `doctor`, o `state_full`, o
  `pip list` e o `modinfo -n hid_playstation`. «A sessão não cai» com o
  compositor do pacote: cinco reinícios do daemon com o `cosmic-osk` de pé, e
  o PID do compositor igual no fim. E o C20: o pad `uhid` nasce com o
  `cosmic-osk` de pé, sem queda?
- **P4b — rádio.** Um dos adaptadores e o controle que ele hospeda. O
  pareamento do zero pelo «Conectar» da aba Conexões, com as Configurações do
  COSMIC fechadas e depois abertas. O A/B do microfone com a única variável
  sendo o driver: antes do reinício, o de fábrica (o daemon não põe o
  microfone no ar, e o `bt_mic.motivo` diz `driver_sem_a_guarda_do_audio`);
  depois, o desta casa, com a marca `mic_frames_ignored`. Os instrumentos: o
  `scripts/ensaios/a_permanencia_do_bit_do_mic.py` e o `libinput
  debug-events` (o cursor não anda sozinho). **Para devolver:** `devolver
  <id>`, e no host o controle volta pelo «Mover» da aba Conexões.
- **P4c — Secure Boot.** `ligar --secboot`. O install não instala o DKMS sem
  a chave, diz o passo da MOK, e o DualSense segue com o driver de fábrica.
- **P4d — a Steam instalada depois.** A nativa e a do Flathub, cada uma
  instalada depois do Hefesto, na ordem dela: reiniciar o daemon, fechar o
  Hefesto, sair da Steam, e então abrir, validar e anotar. O C21: o ambiente
  que a bancada abre é o do `systemd --user`, e não o da sessão COSMIC; a volta
  declara qual usou, e compara só os NOMES com os da Steam aberta pelo ícone.

**O que sai da VM com endereço de aparelho** passa pelo mascarador antes do
disco: `guardar <origem> <destino>`, com `HEFESTO_MASCARA_SED` apontando para o
mascarador da casa (octetos 4 e 5 zerados, a forma com `_` e com `-`, o serial
e o `hefesto-<palavra>-<6 hex>`). Sem ele, o `guardar` recusa.

## O que não se faz

- o daemon real num lar de mentira, com o dela parado: não vale o risco (o
  broker aceita o uid dela, a central do rádio e os nomes do BlueZ são estado
  do sistema). P2 e P4 cobrem o que ele cobriria;
- contêiner com `--privileged`, `--device` ou a árvore de trabalho montada;
- VM com janela na tela dela;
- a Steam aberta do shell de um agente (o ambiente dele contamina todo jogo).
