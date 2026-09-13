# AUDITORIA-SOM-GIRO-01 — entrega

Árvore: `/mnt/Apate/Desenvolvimento/hefesto-voo/AUDITORIA-SOM-GIRO-01-opus`,
branch `voo/AUDITORIA-SOM-GIRO-01-opus`, nascida de `onda/0911` (`779c71f8`,
conferido contra `git rev-parse --short onda/0911`).

> **FATO SUBSTITUÍDO em 13/09/2026** —
> [SENSORES-NO-JOGO-02](../../sprints/2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md).
> A medição que esta entrega cita do cabeçalho de `core/virtual_motion.py` era
> da libSDL2 2.30.0 do sistema, e o zero em Modo Virtual era dessa biblioteca;
> nas bibliotecas dos runtimes da Steam o vpad expõe os dois sensores, e o SDL
> pareia o nó «Motion Sensors» pelo `uniq` (a tabela está na
> SENSORES-NO-JOGO-02, §1). No reparo da §5 cai o alcance dado ao nó de
> movimento: além de `evtest` e emuladores, o SDL o pareia. O degrau segue
> `MONTOU`, e o jogo segue sem medição. O corpo fica como o registro do que a
> auditoria viu.

## O que mudou

**Um documento novo, e nenhuma linha de produto:**
`docs/process/2026-09-11-A-AUDITORIA-DO-SOM-E-DO-GIROSCOPIO.md`. O
`docs/data/mapa-controles.csv` não foi tocado (está em `nao_toca`), e as
propostas de célula estão no documento, com `chave`, transporte, valor de hoje,
valor proposto e a prova.

**A resposta às duas perguntas dela, medida:**

| | |
| --- | --- |
| **A — por controle** | o endereçamento existe ponta a ponta (`sensor.set`, `speaker.set`, `mic.set`, `mic.canal.set`, os quatro com `uniq`; o nó de saída e a fonte de captura nascem com o nome do aparelho). **A prova para de dois:** os 60 ensaios destas três famílias saíram de mesas de um ou dois controles |
| **B — dentro do jogo** | **não medida, em nenhuma linha, em nenhum lançador, em nenhuma máscara** |

**Os números que sustentam o B, e cada um é contagem, não impressão:**

- 24 chaves `@dualsense` nas famílias `audio.`, `movimento.` e `toque.` — **48
  células** (cabo e rádio);
- **18** dessas 48 têm o JOGO como destino (canal `evdev`/`uhid`, pela
  `DIRECAO_POR_CANAL` de `scripts/check_paridade_transporte.py`);
- **ZERO** delas está em `O JOGO RECEBEU` ou `O JOGO REAGIU`. No mapa INTEIRO
  (311 linhas × 2 transportes) também são **zero**;
- **ZERO de 227** ensaios do caderno preenchem a coluna `ponte`. Nenhum ensaio
  desta casa diz sob que máscara foi medido.

**A correção que o mapa faz na sprint** (precedência 2 > 3): a §3.3 pede a
coluna do JOGO *"para cada linha"*, e para o áudio ela não existe por desenho da
própria escada — `hidraw` e `alsa-pipewire` andam para o aparelho, então **onze
das doze linhas de áudio terminam em `O APARELHO OBEDECEU`**. A única de áudio
cujo destino é o jogo é `audio.jack.deteccao`, porque o estado do plugue viaja
dentro do report do vpad. O documento diz, no lugar disso, qual é a pergunta
certa do som — *quem toca no nó daquele controle* — e mede que ela não tem
instrumento.

**Seis buracos com endereço**, dos quais três são achados novos:

1. `sink-input` não tem um único leitor: `grep -rF "sink-input" src/ scripts/`
   devolve **zero**. O espelho de `integrations/quem_ouve_o_microfone.py` para a
   saída — o instrumento que fecharia o degrau de entrada do alto-falante — não
   existe;
2. `integrations/sandbox_dos_lancadores.py` lê `devices=` e **não lê `sockets=`**
   (`grep -c "sockets"` = 0). O controle entra na caixa do Flatpak; ninguém sabe
   se o som entra;
3. o **jogo direto não tem estrada**: `grep -rF` por `environment.d`,
   `/etc/profile.d` e `set-environment` em `src/ scripts/ assets/ install.sh`
   devolve zero nas três. Um binário nativo aberto do terminal não recebe o
   ambiente por caminho nenhum;
4. o interruptor do **acelerômetro** é cobrado pela linha do giroscópio: o
   `DO_APARELHO` de `scripts/check_cabo_bt_perfil_controle.py` mapeia o gesto
   `sensor` só para `movimento.giroscopio`, e a tela oferece dois interruptores;
5. a máscara **Nintendo Pro** não é degrau de `integrations/ponte_escada.py` —
   escolhê-la desliga a escada, e isso não estava escrito em lugar nenhum;
6. nenhuma medição desta casa foi feita com quatro controles.

**Três contradições entre o aparelho e o mapa** (e o aparelho ganha), todas da
folha de 09/09 com a orelha dela: o pré-amplificador diz `aciona = sim` e não
altera nada audível; três das quatro rotas do `OUTPUT_PATH_SEL` saem mono no
fone; e o volume do microfone, que a célula diz `não` por decisão, **obedece** —
o que decide a MIC-VOLUME-02 em vez de contradizê-la.

**Cinco células que o caderno já ultrapassou**, propostas no documento com a
prova ao lado (três do rádio subindo a `O APARELHO OBEDECEU`, uma a `MONTOU`, e
o `aciona` de `audio.alto_falante` no rádio, que **não se muda sozinho**: ele
espera o negativo de rota e o teste cego, por disciplina).

**Sete gestos para a bancada dela**, ordenados pelo que desbloqueia mais, com
tempo e número de controles. Eles não repetem os sete de
`docs/process/sprints/2026-09-10-OS-GESTOS-QUE-SO-ELA-PODE-FAZER.md`, que são da
direção de saída — estes são a coluna do JOGO, que nenhum deles cobre. **Se o
tempo der para só um, é o J1**, o touchpad dentro do jogo no rádio: é o único
que pode DERRUBAR a leitura mais confortável desta casa, a de que o repasse ao
vpad basta.

## Qual mordida prova

Duas, e as duas com a cura arrancada e devolvida.

**1. O número central é medição, não um zero digitado.** Um contador
independente (`scratchpad/contar.py`, fora da árvore) lê o mapa e conta as
células cujo destino é o jogo e as que já estão num degrau de jogo.

    COM A CURA (o mapa de verdade):
      celulas=48 destino_jogo=18 ja_no_degrau_do_jogo=0 | mapa_inteiro=0

    MORDIDA — uma CÓPIA do mapa, no scratchpad, com `movimento.giroscopio.jogo`
    levado a `O JOGO RECEBEU` no cabo:
      celulas=48 destino_jogo=18 ja_no_degrau_do_jogo=1 | mapa_inteiro=1

    git status --short docs/data/mapa-controles.csv  ->  (vazio: intocado)

O zero vira um quando UMA célula sobe. Se o contador fosse cego, os dois lados
dariam o mesmo número.

**2. A régua que guarda esta entrega reprova o documento.** O portão
`referencias-docs` é quem impede um documento de citar arquivo que não existe.

    COM A CURA:
      OK: 924 documento(s) sem referência morta.   rc=0

    CURA ARRANCADA (acrescentei ao documento uma citação a
    `integrations/quem_toca_no_alto_falante.py`, que não existe):
      docs/process/2026-09-11-A-AUDITORIA-DO-SOM-E-DO-GIROSCOPIO.md:518:
        integrations/quem_toca_no_alto_falante.py  [arquivo]
      rc=1

    CURA DEVOLVIDA:
      OK: 924 documento(s) sem referência morta.   rc=0

Ela acusou o MEU arquivo, na MINHA linha, com o nome que eu inventei.

## O que NÃO verifiquei

- **Nada foi medido no aparelho.** A bancada estava LIVRE e não foi reservada: a
  sprint declara `bancada: false`, e o documento não fecha degrau nenhum. As
  duas matrizes e as propostas de célula são leitura do mapa, do caderno e do
  fonte desta árvore.
- **Nenhum jogo foi aberto.** As três colunas de Steam · Heroic · jogo direto
  dizem «não medido» porque ninguém mediu — e não por falta de instrumento em
  quatro das seis linhas.
- **A Steam, o Heroic e o jogo direto foram lidos no CÓDIGO**, não exercitados.
  O que afirmo do caminho de cada lançador é o que os módulos que o fazem dizem,
  mais as medições de disco de 09/09 que eles citam.
- **Não confirmei se falta a permissão de som do Flatpak** em algum dos cinco
  lançadores dela. O que está medido é que o **produto não olha** para ela.
- **Não rodei a suíte inteira**, e não abri janela nenhuma: esta sprint não toca
  tela. Rodei `bash scripts/portoes.sh` completo.
- **O Pro Controller e o 8BitDo ficaram fora das matrizes** de propósito (a tela
  é dos quatro DualSense, decisão dela de 06/09). Onde eles importam — o
  giroscópio nativo do Pro passando direto ao jogo — está na §5 do documento.

## O que sobrou para o próximo

1. **O instrumento que falta é um só, e o molde já existe.** O espelho de
   `integrations/quem_ouve_o_microfone.py` para a SAÍDA: ler os fluxos de saída
   do PipeWire, tirar o PID de cada um, descartar os nossos com
   `descende_do_hefesto` e perguntar se algum é da árvore do jogo. **Mas o J3 da
   lista vem ANTES** — ele diz se vale escrever o instrumento ou se o problema é
   de rota.
2. **Um fato caducou dentro do `src/`, e não é da minha posse.** Um comentário
   de `src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py` afirma que
   *"não há método de sensor nos 39"*, medido em 01/09. O `sensor.set` existe,
   está registrado em `src/hefesto_dualsense4unix/daemon/ipc_server.py` e aceita
   `{uniq?, giroscopio?, acelerometro?}` — ele nasceu em 04/09 com a
   SENSOR-DE-VERDADE-01. Quem tocar naquele arquivo substitui.
3. **A coluna `ponte` do caderno é uma decisão de processo, não de código.**
   Enquanto os ensaios não disserem sob que máscara foram feitos, nenhum deles
   pode ser relido como prova sobre máscara — e as duas perguntas que a máscara
   decide não têm como ser respondidas por arquivo nenhum. Quem despachar a
   próxima bancada pode fechar isso pedindo a coluna.
4. **O acelerômetro merece linha própria na régua das quatro perguntas**
   (`DO_APARELHO`, em `scripts/check_cabo_bt_perfil_controle.py`). É uma entrada
   de dicionário, e o mapa já tem a chave.
5. **A SOM-BOTOES-01, que corre nesta mesma leva, tem a medição que precisa** —
   três das quatro rotas fazem a mesma coisa no fone, com as palavras dela no
   ensaio `folha-rota-todas-mono-no-fone-cabo-0909`. Está na §8.2 do documento.

---

## O reparo de 11/09

A entrega voltou do conferente adversarial. Ele **reproduziu e confirmou** o que
sustenta a auditoria — `celulas=48 destino_jogo=18 ja_no_degrau_do_jogo=0`, o
`0 de 227` da coluna `ponte`, os cinco greps, os cinco instrumentos, os doze
ensaios citados, os 56 portões e a mordida do `referencias-docs` — e devolveu por
**quatro afirmações que a medição derruba**, mais duas de contagem e uma de
guarda. **As sete fecharam, e nenhuma linha de produto foi tocada.**

**O padrão das quatro primeiras é um só, e é o da casa:** *a afirmação respondia
sobre outra coisa que não o que a frase prometia* — a máscara respondendo pelo nó
do físico, o LED respondendo pelas células de áudio, o inode do vpad respondendo
por chaves de `evdev`.

### [ALTA] §5 — «é o único caminho com giroscópio em Virtual» era falso

**O que a árvore mede.** `core/virtual_motion.py` (a medição de 04/09, SDL 2.30.0
headless, um DualSense no cabo): *"em Virtual o nó de movimento do FÍSICO
continua livre e publicando, ao lado do espelho"*, e o `EVIOCGRAB` de
`daemon/sensor_hub.py` existe porque *"alcança o consumidor evdev direto, nos
DOIS modos"*. No mapa, `movimento.giroscopio@dualsense` tem `canal = evdev` nos
dois transportes e `cabo_detalhe = «Existe mesmo com a emulação desligada»`. **O
nó de movimento do físico não depende de máscara nenhuma.**

**O que fiz.** A tabela das máscaras passou a ter **duas** colunas de movimento —
*pelo vpad* e *pelo nó do FÍSICO* — e as três máscaras dizem «livre e publicando»
na segunda. Acima dela, uma **CORREÇÃO DE FATO** nomeando a frase derrubada e
citando as duas medições. **O que a máscara decide é o caminho do vpad, e só
ele.**

**E o alcance não cresceu para o outro lado:** a mesma página mede que o **SDL
não enumera** o nó de movimento (`SDL_NumJoysticks` devolve só os controles; o nó
carrega `ID_INPUT_ACCELEROMETER`). Quem lê por ali é o consumidor evdev direto —
`evtest`, emuladores. Ficou escrito, com o degrau: `MONTOU` nos dois transportes,
e dentro do jogo, em qualquer máscara, **não medido**.

Com isso some a contradição que o conferente apontou: a §3 lista
`movimento.giroscopio` (evdev) com destino JOGO, e a §9.4 diz que nenhum ensaio
pode ser relido como prova sobre máscara. As três frases agora dizem a mesma
coisa.

### [ALTA] §2 — o resumo contradizia a própria tabela, nos dois números

**Recontado no mapa**, as 24 células das doze chaves `audio.@dualsense`:

    O APARELHO OBEDECEU = 2    SAIU NO FIO = 3    MONTOU = 12    sem registro = 7

O parágrafo dizia «três … e duas», e **a causa era uma só**: as duas células que
eu contei do LED são de `luz.led_microfone`, família `luz.`, que **nunca esteve
entre as 24** — enquanto `audio.alto_falante` no cabo, que está, ficou de fora do
parêntese. O resumo virou **tabela com os nomes de cada célula**, mais uma
CORREÇÃO DE FATO dizendo o que estava errado e por quê.

### [MEDIA] §J1 — o gesto prometia o que o instrumento não alcança

Das nove chaves de destino JOGO destas famílias, **seis são `uhid`** e **três são
`evdev`** — medido com `DIRECAO_POR_CANAL` sobre o mapa. O inode do vpad responde
pelas seis (`toque.touchpad`, `.clique`, `movimento.giroscopio.jogo`,
`.acelerometro.jogo`, `movimento.giroscopio.taxa`, `audio.jack.deteccao`), que
viajam no mesmo nó. **Não responde pelas três de `evdev`**
(`movimento.giroscopio`, `movimento.acelerometro`, `toque.touchpad.cursor`): elas
viajam pelo nó que o kernel publica para o controle FÍSICO — está no
`cabo_codigo_ref` das três células (`core/evdev_reader.py`,
`discover_dualsense_motion_evdevs` e `_discover_dualsense_por_nome` com o
marcador «Touchpad»).

O J1 passou a dizer as seis pelo nome e a dizer, em parágrafo próprio, **o que
ele não alcança**. E o repasse ao J2 ficou honesto em vez de confortável: o J2
mede o que um consumidor **SDL** recebe, e o consumidor **evdev direto** daquele
nó **não tem gesto nesta lista** — fica como buraco declarado, não como gesto
prometido. O fecho do J1 («as nove linhas mudam de dono») virou «as seis chaves
de `uhid`».

### [MEDIA] §5 — o microfone sob a máscara Xbox, no presente do indicativo

A frase virou **previsão declarada**: o esperado é que o microfone continue
servindo sob a máscara Xbox (o caminho é PipeWire mais `hidraw`, e nenhum dos
dois passa pelo vpad), **não medido sob máscara nenhuma** — e a falta tem causa
escrita: a coluna `ponte` está vazia nos 227 ensaios, logo nenhum ensaio pode ser
relido como prova de máscara. O degrau de hoje de `audio.microfone` é `SAIU NO
FIO` nos dois transportes, medido sem máscara declarada, e **o gesto que fecha é
o J4**.

### [BAIXA] §3 — «as nove chaves» sob uma tabela que marca oito

Virou: **as OITO desta tabela**, mais a nona, que é `audio.jack.deteccao` da §2 —
a única linha de áudio que chega ao jogo. Nove chaves, 18 células, zero num
degrau de jogo.

### [BAIXA] §5 — «as DEZ linhas que chegam ao jogo por `uhid`»

Medido: as chaves de movimento e toque com canal `uhid` são **cinco**, e valem
**dez células**. O documento diz agora as duas contas e nomeia as cinco, com a
frase que explica o erro: neste vocabulário «linha» é **chave**, e dez era a
conta de **células**.

### [BAIXA] o contador rodou fora da árvore — e a resposta é declarar, não criar

A `posse:` desta sprint tem **um arquivo**: o documento. Criar um script em
`scripts/` sem o alargamento colidiria com os outros agentes desta leva, então
**não criei**. O que fiz foi a outra metade que o conferente ofereceu: o programa
inteiro está agora na **§12 do documento**, com a saída de hoje, com a mordida
(uma cópia do mapa no scratchpad, uma célula levada a `O JOGO RECEBEU`: o zero
vira um) e com o aviso em negrito de que **nenhum portão o recalcula** — o número
envelhece em silêncio enquanto não tiver dono. **A pergunta do alargamento é
dela.**

## As mordidas do reparo

**1. O contador continua mordendo, e agora está escrito no documento.**

    COM A CURA (o mapa de verdade):
      celulas=48 destino_jogo=18 ja_no_degrau_do_jogo=0 | mapa_inteiro=0

    MORDIDA (cópia do mapa no scratchpad, `movimento.giroscopio.jogo`
    levado a `O JOGO RECEBEU` no cabo):
      celulas=48 destino_jogo=18 ja_no_degrau_do_jogo=1 | mapa_inteiro=1

    git status --short docs/data/mapa-controles.csv  ->  (vazio: intocado)

**2. O `referencias-docs` reprova o documento REPARADO.** A §12 e o J1 novo
acrescentaram citações de arquivo (`core/evdev_reader.py`,
`daemon/sensor_hub.py`, `docs/data/ensaios.csv`), e a régua passou a ter mais o
que conferir:

    CURA ARRANCADA (uma linha citando `core/evdev_reader_que_nao_existe.py`):
      1 referência(s) morta(s) em 924 documento(s):
        docs/process/2026-09-11-A-AUDITORIA-DO-SOM-E-DO-GIROSCOPIO.md:665:
          core/evdev_reader_que_nao_existe.py  [arquivo]
      rc=1

    CURA DEVOLVIDA:
      OK: 924 documento(s) sem referência morta.   rc=0

## Os portões do reparo

    git add -A && bash scripts/portoes.sh  ->  TODOS VERDES — 56 portões

## O que o reparo NÃO fez

- **Não reabri o escopo.** Só os sete achados. Nenhuma seção nova além da §12,
  que é a guarda do número, e nenhuma linha de produto.
- **Não criei script fora da posse** (§12 explica), e **não toquei o mapa**: ele
  segue em `nao_toca`, e o `git status` do arquivo segue vazio.
- **Nada foi medido no aparelho neste reparo.** Ele é de leitura: o mapa, o
  caderno e o fonte desta árvore. Os sete gestos da §10 continuam sendo dela.
