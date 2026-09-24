# O Proton desta casa — o pino, a subida para o 11-7, e o que ela não entrega

**Medido em 17/09/2026**, na máquina dela, sem escrever um byte nela. Estudo:
nada aqui foi aplicado. O passo que toca o disco dela está na §4 e tem dono
humano.

Pergunta que originou: *"dentro do proton eu gostaria que fossemos pra versão
11.7 (…) só agora na 11.6 que fomos garantir o mic e o som mesmo que por bt."*

---

## §0 A resposta, em cinco linhas

1. **A 11-7 não está no disco dela.** Existem quatro Protons em
   `compatibilitytools.d`, e o mais novo é o `GE-Proton11-6-x86_64`. A subida
   **exige download de 563.784.602 bytes**.
2. **A subida é mecanicamente segura e já foi simulada**: 24 jogos migram, 1 é
   preservado por escolha dela, o default global troca, 3 entradas ficam
   intactas. O `--lock` reconhece o 11-6 como pino NOSSO sozinho, pelo registro.
3. **A 11-7 não perde a feature pela qual o pino subiu.** A nota do release diz,
   com todas as letras, que a pilha de áudio/haptics Sony foi *rebased*
   "retaining behavior".
4. **Nenhum dos 25 jogos dela está em qualquer lista por appid do Proton** —
   nem no 11-6, nem nas que o 11-7 acrescenta. As mudanças de controle da 11-7
   não tocam a biblioteca dela.
5. **O mic e o som por Bluetooth NÃO vieram da 11-6.** São código desta casa,
   medidos em 03/09, 06/09 e 10/09 — com o pino ainda no `GE-Proton10-34`. A
   coincidência é de calendário. A §6 mede isso.

---

## §1 O mecanismo do pino, inteiro

### Quem é a fonte da verdade

`assets/proton-pin.conf` — três chaves (`name`, `url`, `sha256`) e o resto é
prosa. `proton_pin.parse_pin_conf` valida o **contrato**, não só a sintaxe:
conf sem uma das três chaves, ou com `sha256` que não seja 64 hex, **levanta**.
Seguir adiante com sha vazio extrairia binário não verificado.

O valor de `name` é o **nome INTERNO do `compatibilitytool.vdf`**, não o nome do
arquivo — é ele que vai ao `CompatToolMapping`. Desde o 11-4 esse nome carrega o
sufixo `-x86_64`; até o 11-3 não carregava.

### Quem escreve, e onde

| lugar | o quê | quem toca |
| --- | --- | --- |
| `~/.steam/steam/compatibilitytools.d/<name>/` | o Proton extraído | `ensure_pinned_proton` |
| `.../<name>/.hefesto-proton-pin.json` | manifesto (`name`, `sha256`, `installed_at`) | idem |
| `~/.cache/hefesto-dualsense4unix/proton/<name>.tar.gz` | cache offline-first | idem |
| `~/.steam/steam/config/config.vdf` → `CompatToolMapping` | a trava por jogo + o default global `"0"` | `lock_games_to_pinned_proton` |
| `.../config.vdf.bak.hefesto-proton-<carimbo>` | backup, um por escrita | `_write_vdf_with_backup` |
| `~/.local/state/hefesto-dualsense4unix/proton-pin-lock.json` | o registro do que é NOSSO | `_merge_lock_state` |

O módulo é `src/hefesto_dualsense4unix/integrations/proton_pin.py`, **100%
stdlib de propósito**: o `uninstall.sh` o roda como script avulso depois de a
`.venv` já ter sido removida.

### A ordem do `--ensure`, e por que ela é essa

`ensure_pinned_proton` tenta offline antes de online:

1. extraído **com** o nosso manifesto batendo → `already`;
2. extraído **sem** manifesto (ProtonUp ou à mão) → `already`, e o diretório é
   **MANTIDO** — é dado da dona da máquina, não se sobrescreve;
3. cache local com sha256 batendo → extrai → `installed_from_cache`;
4. baixa para um `.hefesto-download` temporário, confere o sha256, **só então**
   vira cache → `downloaded`;
5. sha não bate → `checksum_mismatch` e **nada é extraído**.

O caso 2 tem consequência permanente e está documentada em `install.sh`
(CONSELHO-QUE-NAO-CURA-01, 02/09/2026): o doctor passa a dizer para sempre que o
manifesto não confere, e o conselho *"rode ./install.sh"* é exatamente o que
acabou de rodar sem mudar nada. A saída do `--ensure` é capturada e reimpressa
inteira por causa disso.

### A trava, e a guarda que ela tem

`lock_games_to_pinned_proton` escreve o default global `"0"` (prioridade `75`) e
uma entrada por appid instalado (prioridade `250`) — os valores nativos
observados no vdf, para ficar indistinguível de uma escolha feita na janela da
Steam.

**O gate:** `_steam_gate()` recusa com a Steam ou um jogo abertos. A Steam
regrava o `config.vdf` ao sair e a edição seria perdida. Recusa devolve `rc=3`.

**A guarda de 19/08/2026:** entrada de jogo que já aponta para outra ferramenta
vira `action="preservado"` — não se atropela escolha dela. Nasceu de um estrago
medido: em 14/08 a trava arrastou três escolhas deliberadas dela para o pino sem
perguntar.

**A memória que faz a subida alcançar os jogos:** `pinos_do_hefesto`, no
registro. É a lista dos Protons que ESTE produto já pinou. O que está nela é
nosso e **migra**; qualquer outro valor continua sendo escolha dela e é
preservado. Sem ela, a guarda de 19/08 lê como escolha dela o que o próprio
produto escreveu — que foi exatamente o defeito de 16/09/2026, curado em
`84d89a8de`.

**A ordem de escrita é registro ANTES do vdf, e é invariante:** se a persistência
do estado falhar, o vdf fica intacto e o lock volta com erro. A ordem inversa
deixaria o Proton pinado no vdf **sem registro** — e como re-lock é idempotente
(`noop`, nunca regrava estado), o unlock nunca mais conseguiria reverter.

### Como se reverte, e o que o `uninstall` desfaz

```
python3 src/hefesto_dualsense4unix/integrations/proton_pin.py --unlock
```

`unlock_games_from_pinned_proton` reverte **só o que o registro diz ser nosso**,
pelo `previous_name`. Sem registro, `noop` — nunca toca o vdf. Sucesso apaga o
arquivo de estado.

O `uninstall.sh` (linhas 1518-1536) roda o `--unlock` **antes** do strip das
Launch Options, de propósito: o strip reabre a Steam ao final, e o unlock exige
Steam fechada.

**O que o uninstall NÃO desfaz, e é decisão:** o Proton extraído em
`compatibilitytools.d` **fica**. É dado do usuário. Quem não quiser apaga a pasta
à mão.

### O passo `[11c]` do install

`install.sh:4153-4233`, **ligado por default**, opt-out `--no-proton-pin`.
Roda `--ensure`, lê o `rc`, e só então `--lock`:

| rc do `--ensure` | o que o install diz |
| --- | --- |
| 1 | checksum não bateu — passo ABORTADO, nada instalado |
| 2 | sem rede e sem cache — pin PENDENTE, trava adiada |
| 3 (do `--lock`) | Steam aberta — trava ADIADA, com a instrução |

E o doctor confere no fim (`check_proton_pin`, `install.sh:4218`), com
`proton_pin_report` — read-only.

---

## §2 O que está no disco dela HOJE

Medido em 17/09/2026.

```
~/.steam/steam/compatibilitytools.d/
  GE-Proton10-34           (03/04/2026 — instalado por FORA, sem nosso manifesto)
  GE-Proton11-1            (26/06/2026)
  GE-Proton11-3            (26/07/2026)
  GE-Proton11-6-x86_64     (16/09/2026 — o pino de hoje, 1,5 GB)
```

**A 11-7 NÃO está lá.** Nem extraída, nem no cache: o
`~/.cache/hefesto-dualsense4unix/proton/` tem só o tarball do 11-6 (509 MB) e o
`.sha512sum` dele.

O `--report` de hoje, na máquina dela:

```
pinned_name         = GE-Proton11-6-x86_64
pinned_present      = True
pinned_manifest_ok  = True          <- o sha256 do manifesto bate com o conf
global_tool         = GE-Proton11-6-x86_64
global_is_pinned    = True
games_off_pin       = ['2497900']   <- DON'T SCREAM, escolha dela
games_leaky_proton  = []            <- nenhum jogo em Proton <= 9
mapping             = 29 entradas
```

**O `CompatToolMapping` vivo tem 29 entradas**, e a conta exata é esta:

| ferramenta | entradas | quais |
| --- | --- | --- |
| `GE-Proton11-6-x86_64` | **25** | o default global `"0"` + **24 jogos** |
| `proton_11` | 3 | `2497900` (preservado), `1245620`, `4046520` |
| `GE-Proton10-34` | 1 | `2369580` |

Os 24 jogos que carregam o pino: Grim Fandango Remastered, Touhou Luna Nights,
FAITH, Stray, Big Walk, Scarlet Deer Inn, Sackboy, Mr. Sleepy Man, Bail or Jail,
Mina the Hollower, Mortal Kombat 1, Mullet Mad Jack, REANIMAL, Black Myth:
Wukong, Avatar Legends, Duskfade, DON'T SCREAM TOGETHER, Dark Scrolls, PRAGMATA,
Wendigo Blue, PEAK, Pro Jank Footy, ORPHEUS e Future Knight.

**As três entradas que o pino não alcança, e a razão de cada uma:**

| appid | onde está | por quê |
| --- | --- | --- |
| `2497900` DON'T SCREAM | `proton_11` | **escolha dela**, respeitada desde 19/08 |
| `1245620` | `proton_11` | **não está instalado** — fora de `list_installed_appids` |
| `2369580` | `GE-Proton10-34` | **não está instalado**; ficou no pino de abril |

O `2369580` é o único que merece nota: ele está num pino NOSSO antigo e ficou
para trás porque o jogo não está instalado. **Se ela reinstalar esse jogo, ele
abre no Proton de abril** até que um `--lock` rode de novo. Não é defeito da
subida; é como o alvo é montado.

---

## §3 O que a 11-7 muda em relação à 11-6

**Com rede**, lida da API de releases em 17/09/2026.

| | publicado | tarball x86_64 |
| --- | --- | --- |
| `GE-Proton11-6` | 2026-08-28T21:37:07Z | 533.700.853 B |
| `GE-Proton11-7` | 2026-09-16T02:28:16Z | 563.784.602 B |

Os dois saíram do mesmo dia em que o pino subiu: o 11-7 foi publicado às
**02:28Z de 16/09** e o registro do lock desta casa foi gravado às **02:10 de
16/09, hora local**. O pino escolheu o 11-6 com o 11-7 a minutos de distância, e
isso está declarado no conf.

### O que importa para ESTE projeto

A seção 3 do release do 11-7 chama-se **"DS5 / DualSense and Other Controller
Fixes"**. Cinco itens, e só o último é infraestrutura:

> *"Rebased the existing Sony audio/haptics/hotplug stack against current Wine,
> **retaining behavior** and removing an overlapping hotplug patch already
> supplied upstream."* — commit `2bad9078`

**É a linha que decide a migração.** A feature pela qual o pino subiu para o
11-6 não é removida nem reescrita no 11-7: é rebaseada com comportamento
preservado. Não há, na nota, promessa de melhora do áudio do controle — e
também não há regressão anunciada.

Os outros quatro itens são **por appid** e nenhum toca a biblioteca dela (§5):

- novos defaults Sony→XInput: Capcom Fighting Collection 1 e 2, MARVEL vs.
  CAPCOM Arcade Classics, Street Fighter 30th Anniversary, Tetris Effect:
  Connected;
- eFootball e Dragon Age: Inquisition ganham o caminho HIDRAW XInput de DS4/DS5;
- Grandia, Grandia II e Lunar trocam o spoof de identidade DS4 por Sony XInput;
- VitaPad com fio passa a aparecer como DS4 por default.

### O resto da 11-7, e o que dele vale um olho

O grosso do release é **Wine-Wayland com renderização de processo filho** (85
patches na série), janelamento/fullscreen/cursor, vídeo e overlay da Steam. Ela
roda COSMIC sob Wayland, então esse é o pedaço que de fato muda o chão embaixo
dos jogos dela. Dois itens são os que eu olharia primeiro se algo estranhar:

- **overlay da Steam, "Focus restoration and Steam Input identity"**
  (`fb769bc5`): passa a usar uma janela X11 `InputOnly` separada e o **foco de
  teclado** governa o foco da ponte, em vez do hover do mouse. Esta casa tem
  história com foco — `FOCO-ERRANTE-01` — e detecção de janela por xlib.
- **escala fracionária do overlay** (`8ba3d8e9`) e **VRR/flicker** (`cf707135`).

O próprio autor marca dois itens como **não reconfirmados em tempo de execução**
(o flicker do launcher do Marvel Rivals e o HDR do DOOM Eternal), e pede
cautela com "direct scanout" — nenhum deles alcança a biblioteca dela.

### O upstream do Proton

A nota diz que o 11-7 atualizou o Wine bleeding-edge e rebaseou EM-11, child
rendering, vídeo, **controller**, staging, game, Steam client, WineOpenXR e
OptiScaler, mais cherry-picks da Valve (`steam2ea://`, `appcache` no prefixo,
limite de espaço de endereço para um jogo). **A nota não nomeia uma versão de
Proton upstream**, e eu não a derivei: dizer "Proton 11.x" sem medir seria
inventar.

### Os números que a migração precisa, medidos

```
name   = GE-Proton11-7-x86_64      <- MEDIDO: raiz do tarball E nome interno
                                      do compatibilitytool.vdf, lidos em fluxo
url    = https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton11-7/GE-Proton11-7-x86_64.tar.gz
sha256 = c5448b76a230384e2d7bc6beb5ccb97bafb7e2c3b6c527cb03a1a546bbcb00a0
```

**Como o sha256 foi obtido, e por que ele é confiável:** o tarball foi baixado
em FLUXO e descartado — nada foi gravado no cache dela —, calculando sha256 e
sha512 na mesma passada. O sha512 resultante bate, byte a byte, com o
`GE-Proton11-7-x86_64.sha512sum` publicado no release. Logo o sha256 acima é do
tarball autêntico.

O mesmo cruzamento foi feito no 11-6 como controle: o `.sha512sum` em cache na
máquina dela é idêntico ao publicado hoje, e o `pinned_manifest_ok` é `True`.

---

## §4 O caminho seguro de migração — NÃO EXECUTADO

Nada desta seção foi rodado. O passo 3 em diante toca a máquina dela.

### Antes de tudo: as duas perguntas que são dela

1. **A 11-6 entrega hoje o que o pino prometeu?** O som do jogo no alto-falante
   do controle **nunca foi confirmado** nesta casa (§6.3). Se ela ainda não
   ouviu isso funcionar, subir para a 11-7 não arrisca nada medido — e testar a
   promessa uma vez, na 11-6, antes de trocar, vale mais do que qualquer plano.
2. **Ela quer o 11-7 pelo controle, ou pelo resto?** Pelo controle, o ganho é
   nulo para a biblioteca dela (§5). Pelo Wayland/overlay, pode ser real.

### Passo 0 — a foto de antes (read-only, sem risco)

```bash
python3 src/hefesto_dualsense4unix/integrations/proton_pin.py --report > /tmp/proton-antes.json
cp ~/.local/state/hefesto-dualsense4unix/proton-pin-lock.json /tmp/lock-antes.json
cp ~/.steam/steam/config/config.vdf /tmp/config-antes.vdf
```

É o que permite comparar depois e é o backup que NÃO depende do produto.

### Passo 1 — a Steam fechada

O `--lock` recusa (`rc=3`) com a Steam ou um jogo abertos, e está certo. Fechar
antes evita um passo pela metade.

### Passo 2 — editar o conf, e só ele

Em `assets/proton-pin.conf`, trocar as **três chaves** pelos valores medidos na
§3. O bloco de prosa acima delas ganha a data e a razão da subida — é o contrato
da casa.

Nada mais precisa mudar no código: `proton_major("GE-Proton11-7-x86_64")`
devolve `11` pelo `_GE_NAME_RE`, então o jogo não entra em `games_leaky_proton`;
e o `--lock` descobre sozinho que o 11-6 é pino nosso, pelo registro.

### Passo 3 — baixar e verificar, sem travar nada ainda

```bash
python3 src/hefesto_dualsense4unix/integrations/proton_pin.py --ensure
```

Baixa 563.784.602 B, confere o sha256 e extrai. **Se o sha não bater, nada é
extraído** e o rc é 1 — é o passo que se pode rodar sem medo, porque ele não
toca o `config.vdf`.

Espaço: `/home` tem 228 GB livres; o extraído do 11-6 ocupa 1,5 GB e o tarball
509 MB. A subida acrescenta cerca de 2 GB e **não apaga o 11-6** — o que é bom,
porque é dele que se volta.

### Passo 4 — travar

```bash
python3 src/hefesto_dualsense4unix/integrations/proton_pin.py --lock
```

**O que isso fará, simulado em 17/09/2026 contra uma CÓPIA do `config.vdf` e do
registro dela** (`dry_run=True`, nada escrito):

```
status: locked
24 migrado  ·  1 replaced (o default global "0")  ·  1 preservado (DON'T SCREAM)
25 jogos mirados + o default global
entradas intactas: 1245620, 2369580, 4046520
```

Todos os 24 saem de `GE-Proton11-6-x86_64` com `veio_de` gravado. O
`previous_name` preservado no registro continua sendo o **pré-hefesto**
(`GE-Proton10-34` para os que vieram de lá), que é o que desfaz TUDO.

### Passo 5 — conferir

```bash
python3 src/hefesto_dualsense4unix/integrations/proton_pin.py --report
```

`pinned_manifest_ok` tem de ser `True` e `games_off_pin` tem de continuar
`['2497900']` — só o DON'T SCREAM. Qualquer outro appid ali é achado, não
esperado.

### Como se volta, se um jogo quebrar

**Três caminhos, do mais fino ao mais grosso.** Os três existem porque o
`GE-Proton11-6-x86_64` continua no disco: nenhum deles precisa de rede.

1. **Um jogo só** — trocar o Proton daquele jogo pela janela da Steam
   (Propriedades → Compatibilidade). Isso o transforma em escolha dela, e o
   `--lock` seguinte passa a **preservá-lo**. É o caminho mais barato e o que o
   produto foi desenhado para respeitar.
2. **Tudo, pelo produto** — voltar as três chaves do conf para o 11-6 e rodar
   `--ensure` (que devolve `already`, sem rede) e `--lock`. Os 24 migram de
   volta, porque o 11-7 já estará em `pinos_do_hefesto`.
3. **Tudo, pelo arquivo** — restaurar o `config.vdf.bak.hefesto-proton-<carimbo>`
   que o passo 4 acabou de criar, com a Steam fechada.

**O que o backup do `config.vdf` cobre, e o que não cobre:** ele é uma cópia
integral do arquivo, feita imediatamente antes da escrita, então cobre o
`CompatToolMapping` inteiro **e tudo o mais que o vdf guarda**. O que ele não
cobre é o registro do lock: restaurar o vdf à mão deixa o
`proton-pin-lock.json` descrevendo uma corrida que não aconteceu mais. Depois de
um retorno pelo caminho 3, o registro tem de ser restaurado junto (`/tmp/lock-antes.json`
do passo 0) — senão o `--unlock` do uninstall tentará reverter para um estado
que o vdf já não tem.

### O que NÃO se deve fazer

- **Não rodar `install.sh` só para subir o pino.** O passo 11c é um passo entre
  dezenas; o install reinicia o daemon e reescreve lançadores. As duas linhas do
  `proton_pin.py` fazem exatamente o passo 11c e nada mais.
- **Não apagar o `GE-Proton11-6-x86_64`.** Ele é o caminho de volta sem rede.
- **Não tocar em `2497900`, `1245620` nem `4046520`.** São escolhas dela.

---

## §5 O risco por jogo

**Procurei decisão datada que amarre algum jogo à 11-6 especificamente. Não
existe.** O que existe é uma decisão datada de sinal contrário, e ela vale:

| decisão | data | o que diz |
| --- | --- | --- |
| a guarda `preservado` | 19/08/2026 | jogo que já aponta para outra ferramenta **não** é atropelado. Nasceu do estrago de 14/08, em que três escolhas dela foram apagadas sem pergunta |
| o pino sobe para 11-6 | 16/09/2026 | a razão é a **feature** (áudio/haptics no jogo), e o conf declara que o 11-7 saiu no mesmo dia e não foi pinado porque *"o pino é a versão que este projeto validou"* |

A segunda é a que a subida para o 11-7 muda, e ela é explicitamente reversível
por decisão — o próprio conf diz que *"upgrade é SEMPRE deliberado"*. Não há
jogo com razão escrita para ficar na 11-6.

### A medição que fecha o risco de controle

O script `proton` do GE-Proton liga variáveis de ambiente de controle **por
appid**. Se um jogo dela caísse numa dessas listas, o Proton mudaria a
identidade do DualSense dentro do jogo — e isso conversaria com o que este
produto faz por fora. Medido contra o `proton` do 11-6 instalado, cruzando com
`list_installed_appids()`:

| variável | appids na lista | jogos DELA |
| --- | --- | --- |
| `PROTON_SONY_HIDRAW_XINPUT` | 144 | **nenhum** |
| `PROTON_SONY_DUALSENSE_AS_DUALSHOCK4` | 21 | **nenhum** |
| `PROTON_SONY_DUALSHOCK4_V2_AS_V1` | 6 | **nenhum** |
| `PROTON_STEAMINPUT_FALLBACK` | 3 | **nenhum** |
| `PROTON_DEATH_STRANDING_CONTROLLER_EFFECTS` | 2 | **nenhum** |
| `PROTON_ENABLE_MHWILDS_USB_AUDIO` | 1 | **nenhum** |
| `WINE_DISABLE_EXE_ASLR` | 1 | **nenhum** |

E os appids que o 11-7 **acrescenta** a essas listas (eFootball, Dragon Age:
Inquisition, as três coletâneas Capcom, Street Fighter 30th, Tetris Effect:
Connected, Grandia, Grandia II, Lunar) também não estão na biblioteca dela.

**Conclusão medida: pelo lado do controle, a 11-7 é neutra para os 25 jogos
dela.** O risco real da subida não é de controle — é o chão de Wayland e
overlay da §3.

### O que continua de pé, e é a razão original do pino

A semântica do `winebus` mudou entre Proton 9 e 10: `PROTON_ENABLE_HIDRAW`
morreu e a env moderna é `PROTON_DISABLE_HIDRAW`, que o wrapper emite. Em Proton
menor ou igual a 9 o controle físico volta a vazar duplicado. O 11-7 é major 11,
então `proton_major` o classifica igual ao 11-6 e `games_leaky_proton` continua
vazio. **A subida não mexe nessa proteção.**

---

## §6 O fato que ela citou — e ele precisa de correção

> *"só agora na 11.6 que fomos garantir o mic e o som mesmo que por bt"*

**O mic e o som por Bluetooth não vieram da 11-6. São código desta casa, e os
três marcos são anteriores à subida do pino.**

### 6.1 A linha do tempo, medida

| quando | o quê | o pino naquele dia |
| --- | --- | --- |
| 03/09/2026 | o canal de captura por controle — CANAL-POR-CONTROLE-01 | `GE-Proton10-34` |
| 06/09/2026 | a ponte do mic segue o estado da source — ONDA5-MIC-VIRTUAL-02 | `GE-Proton10-34` |
| **10/09/2026** | **o alto-falante toca por rádio: o report `0x35`** | `GE-Proton10-34` |
| 16/09/2026 | o pino sobe para `GE-Proton11-6-x86_64` | — |

O pino só saiu do `GE-Proton10-34` em **16/09/2026** (`dcada2d59`, e o registro
do lock foi gravado às 02:10 daquele dia). Os três marcos são de **seis a treze
dias antes**.

### 6.2 Por que Proton não podia ser a causa

O som por rádio é `write()` no `/dev/hidraw`, pelo BlueZ, com o daemon vivo —
`docs/protocol/dualsense-referencia-canonica.md`, seção *"O som que saiu pelo
rádio — o `0x35`, medido em 10/09/2026"*:

```
report 0x35 · 334 B · UM quadro Opus · tag 0x13 · a cada 10,667 ms
write() no /dev/hidraw, com o daemon vivo e o hid-playstation ligado
sem primer · sem socket L2CAP · sem root · sem unbind
```

Grau: **MEDIDO NO APARELHO**, com a orelha dela — 70 segundos contínuos sem
corte, e a mordida do CRC calando o som. Nada nesse caminho passa por Proton: o
Proton só existe dentro de um jogo Windows, e a ponte toca com jogo nenhum
aberto.

O mesmo vale para o microfone: `integrations/dualsense_bt_audio.py` decodifica
Opus e publica uma source PipeWire (`module-pipe-source`) a partir do report
`0x32`. Também fora do Proton.

**E há medição direta de que o Proton não escreve nesse fio**, feita em
16/09/2026 (`ce10c7f3b`): o `winebus.so` só expõe
`hidraw_device_set_output_report` e `hid_device_set_feature_report` — é um cano,
repassa o report do processo Windows e não compõe nenhum. Quem escreve são o SDL
do jogo e a Steam Input, e os dois já têm cobertura própria.

### 6.3 O que a 11-6 entrega de verdade, e o que ainda não foi confirmado

O que a 11-6 traz é o **outro** caminho: o áudio e as haptics que **o jogo
Windows pede**, chegando ao controle. Pelo cabo, onde o DualSense é uma placa de
som de quatro canais. É uma feature real e distinta — e **ainda não foi
confirmada nesta máquina**.

O ensaio que a confirmaria está escrito e **aberto**: *J3 · Quem toca no
alto-falante do controle*, em
`docs/process/2026-09-11-A-AUDITORIA-DO-SOM-E-DO-GIROSCOPIO.md` — 10 minutos, 1
controle, 1 jogo. Nada em `docs/data/ensaios.csv` mede um jogo Windows abrindo o
alto-falante do controle: as linhas de `audio.alto_falante@dualsense` são todas
do caminho **nosso** (IPC `speaker.set` e `pw-play`), medidas em 15/08.

**A consequência prática para a decisão dela:** a 11-6 está pinada por uma
promessa não colhida. Subir para a 11-7 não arrisca uma feature medida, porque
não há feature medida a arriscar — e, segundo a nota do release, a pilha
continua lá.

### 6.4 O que a frase dela acerta

Ela associou 11-6 ao som e ao mic porque as duas coisas aconteceram na mesma
semana e a subida do pino foi pedida por ela com o Sackboy aberto, pedindo
*"sons do jogo sfx, microfone também"*. O pedido é o mesmo; os dois caminhos que
o atendem é que são dois. **A casa deve os dois — um já entrega por rádio
(nosso), o outro ainda não foi conferido no jogo (Proton).**

---

## §7 As correções de fato desta leva

### 7.1 O mecanismo `dsound`/`ContainerId`/`MMDevice` não tinha endereço

Três lugares afirmavam que *"o GE-Proton 11-4 fechou o casamento do `ContainerId`
do HID com o MMDevice que o jogo abre, e o 11-6 refez esse caminho pelo
`dsound`"*: `assets/proton-pin.conf`, `install.sh:4170-4171` e
`tests/unit/test_proton_pin.py:64`.

**Medido em 17/09/2026:** as palavras `dsound`, `ContainerId` e `MMDevice` não
aparecem em nenhuma das notas de release do GE-Proton **11-4, 11-5, 11-6 ou
11-7**. O que elas dizem é:

- 11-4: *"Finalized DualShock 4, DualSense, and DualSense Edge haptics,
  controller-speaker audio, and hotplug handling."*
- 11-6: *"Reworked DualShock 4, DualSense and DualSense Edge audio/haptic
  routing, **endpoint identity**, profile switching and hotplug lifecycle."*

**E a mordida da minha própria hipótese:** vendo que o `dsound.dll` do 11-6
carrega 12 símbolos `ContainerId`, quase publiquei isso como a prova que
faltava. Conferido contra as outras versões instaladas:

```
GE-Proton10-34          ContainerId=12  bytes=867548
GE-Proton11-1           ContainerId=12  bytes=868499
GE-Proton11-3           ContainerId=12  bytes=868499
GE-Proton11-6-x86_64    ContainerId=12  bytes=868499
```

O pino **velho**, de abril, tem os mesmos 12. São chaves de propriedade de
dispositivo genéricas do Wine e **não distinguem versão nenhuma** — a presença
delas não prova nada sobre o que a 11-6 mudou.

A substância (a feature existe, e é por ela que o pino subiu) fica; o mecanismo
inventado sai e dá lugar às palavras do próprio autor. A sequência certa,
sourceada, é **11-4 fechou · 11-6 refez a rota e a identidade de endpoint ·
11-7 rebaseou preservando comportamento**.

### 7.2 O `-x86_64` do 11-7 deixou de ser inferência

O conf avisava que o sufixo faz parte do nome a partir do 11-4. Para o 11-7 isso
agora está **medido**, não deduzido do padrão: a raiz do tarball é
`GE-Proton11-7-x86_64/` e o nome interno do `compatibilitytool.vdf`, lido em
fluxo no membro 8363, é `GE-Proton11-7-x86_64`.

### 7.3 A precisão de "25 jogos travados"

Circula a leitura de que o pino *"trava 25 jogos mais o default global"*. O
número exato, medido no vdf vivo e batendo com o commit `84d89a8de`:

> **25 jogos são MIRADOS; 24 carregam o pino; 1 é preservado; mais o default
> global.** São 25 entradas no `CompatToolMapping` apontando para o
> `GE-Proton11-6-x86_64` (24 jogos + o `"0"`).

A distinção não é preciosismo: *"locked — 25 jogos + default global"* é
literalmente a linha falsa que o `_cmd_lock` imprimia antes de 16/09, quando os
25 ficavam onde estavam. O código guarda essa frase como registro do defeito
(`proton_pin.py:1349-1353`). Repeti-la como se fosse o resultado desfaz a cura.

---

## §8 O que NÃO foi medido

- **Nada foi aplicado.** A 11-7 não foi baixada para o cache dela, o conf não
  mudou de versão, o `config.vdf` não foi tocado. O tarball foi lido em fluxo e
  descartado.
- **A 11-7 não foi executada.** Nenhum jogo foi aberto, nenhuma sessão de Steam
  foi iniciada. Tudo o que se afirma sobre o comportamento dela vem da nota do
  release e do conteúdo do tarball.
- **A versão de Proton upstream da 11-7 não foi derivada** — a nota não a nomeia
  e eu não a inferi.
- **A feature da 11-6 continua não confirmada** (§6.3). O ensaio J3 está aberto.
- **As listas por appid do 11-7 não foram lidas do script `proton` dele** — a §5
  cruza os 25 appids dela contra o script do **11-6** instalado, e contra os
  appids que a nota do 11-7 declara acrescentar. Ler o `proton` do 11-7 exigiria
  extraí-lo.
- **O efeito das mudanças de Wayland/overlay da 11-7 sobre o COSMIC dela** é o
  risco que sobra, e ele só se mede jogando.
