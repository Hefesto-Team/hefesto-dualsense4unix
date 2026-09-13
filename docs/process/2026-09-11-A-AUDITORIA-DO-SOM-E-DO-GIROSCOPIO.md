# A AUDITORIA DO SOM E DO GIROSCÓPIO — por controle, e dentro do jogo

**11/09/2026.** O pedido é dela:

> *"eu preciso de uma auditoria completo no sistema de audio e giroscopio pra*  <!-- noqa-acento: citação literal dela -->
> *ver se todas as features funcionam por controles e se cada uma vai ser*  <!-- noqa-acento: citação literal dela -->
> *reconhecida dentro da steam heroic e jogos diretos."*  <!-- noqa-acento: citação literal dela -->

**Este documento não muda uma linha de produto.** Ele diz onde dói, com que
prova, e qual gesto fecharia cada buraco. Toda afirmação forte traz o **degrau**
da escada; onde não há ensaio, está escrito **não medido** — que é informação, e
a boa.

---

## §0 — AS DUAS RESPOSTAS, e elas são MUITO diferentes

**PERGUNTA A — por controle.** *O endereçamento existe ponta a ponta, e a prova
para de dois.* Todo gesto de som e de movimento aceita `uniq`
(`sensor.set`, `speaker.set`, `mic.set`, `mic.canal.set` — os quatro no
`daemon/ipc_server.py`), o nó de saída nasce com o nome do aparelho
(`hefesto_som_<hex6>`, `integrations/alto_falante_bt.PREFIXO_SINK_DO_SOM`) e a
fonte de captura por rádio também. **O que não existe é a medição com quatro:**
os 60 ensaios destas três famílias foram feitos com **um ou dois** controles.

**PERGUNTA B — dentro do jogo.** *Não medida. Em nenhuma linha, em nenhum
lançador, em nenhuma máscara.* E o número é duro:

| o que se contou | número | onde se conta |
| --- | --- | --- |
| células do mapa nestas três famílias (24 chaves × 2 transportes, `dualsense`) | **48** | `docs/data/mapa-controles.csv` |
| delas, cujo **destino** é o JOGO (canal `evdev`/`uhid`) | **18** | `DIRECAO_POR_CANAL`, em `scripts/check_paridade_transporte.py` |
| delas, já num degrau de jogo (`O JOGO RECEBEU` ou `O JOGO REAGIU`) | **ZERO** | a mesma coluna |
| células do mapa INTEIRO num degrau de jogo (todas as 311 linhas × 2) | **ZERO** | idem |
| ensaios do caderno que declaram sob qual **ponte** mediram | **ZERO de 227** | `docs/data/ensaios.csv`, coluna `ponte` |

**Os quatro primeiros números saem de um programa, e ele está na §12 — junto com
o aviso de que NENHUM portão o recalcula.**

A última linha é a mais cara das cinco, e é achado desta auditoria: **nenhum
ensaio desta casa diz com que máscara foi medido.** A coluna existe desde que a
escada ganhou os dois degraus de entrada, e nunca foi preenchida — o que quer
dizer que nem os ensaios de 15/08 a 10/09 podem ser relidos como prova de
máscara nenhuma.

**A frase honesta, e é a que este documento defende:** *o som e o movimento
funcionam até o plástico e até o vpad; do vpad para dentro do jogo, a casa nunca
olhou.*

---

## §1 — A RÉGUA DESTE DOCUMENTO, e ela não é minha

Os cinco degraus e o critério de cada um têm **um dono executável**: a `ESCADA`
de `scripts/check_paridade_transporte.py`. Este documento a cita, nunca a
redigita.

    MONTOU               o byte existe na memória do produto e a suíte o lê.
                         Nada saiu do processo. Tratar MONTOU como «funciona»
                         é a mentira mais cara desta casa.
    SAIU NO FIO          a escrita no nó do transporte não errou e houve
                         resposta. Diz que o canal abriu — não que o aparelho
                         fez coisa alguma.
    O APARELHO OBEDECEU  alguém VIU. Fim da direção de saída.
    O JOGO RECEBEU       o INODE do nó do vpad aparece em /proc/<pid>/fd de um
                         processo da árvore do jogo.
    O JOGO REAGIU        ela jogou e viu.

**E o DESTINO de cada linha não é escolha de quem escreve.** Ele sai do `*_canal`
da célula, traduzido por `DIRECAO_POR_CANAL`: `hidraw`, `sysfs`, `dbus` e
`alsa-pipewire` andam para o aparelho e terminam em `O APARELHO OBEDECEU`;
`evdev` e `uhid` andam para o jogo e terminam em `O JOGO REAGIU`. `outro` não
decide destino nenhum — e a recusa é a regra, não a falta dela.

**Isto corrige a §3.3 da sprint, e é o mapa vencendo o plano** (precedência
2 > 3). A sprint pede a coluna do JOGO *"para cada linha"*. Para as doze linhas
de áudio, **onze terminam no aparelho por desenho da própria escada** — o som
não é uma coisa que o jogo *recebe* de nós. A única linha de áudio cujo destino
é o jogo é `audio.jack.deteccao`, porque o estado do plugue viaja **dentro do
report do vpad**. A §4.3 diz qual é, então, a pergunta certa do áudio.

---

## §2 — A MATRIZ DO ÁUDIO

Doze chaves, `@dualsense`. `aciona` responde *"o Hefesto mexe nisso?"*; `degrau`
responde *"até onde a prova chegou?"*. **Por controle?** é o endereçamento real
no código, não a promessa da tela.

| chave | cabo: aciona / degrau | rádio: aciona / degrau | por controle? | destino | quem prova |
| --- | --- | --- | --- | --- | --- |
| `audio.alto_falante` | parcial / **O APARELHO OBEDECEU** | não (`divida`) / **SAIU NO FIO** | sim — um nó por `uniq` | aparelho | `olho-dela`, 15/08 (cabo); `som-radio-l2cap-direto-abre-0910` e `som-035-no-produto-byte-a-byte-0910` (rádio) |
| `audio.alto_falante.rota` | sim / **O APARELHO OBEDECEU** | sim / **MONTOU** | sim (`speaker.set` com `uniq`) | aparelho | `olho-dela`, 16/08 (cabo). **E ver §8.2** |
| `audio.alto_falante.volume` | sim / **MONTOU** | sim / **MONTOU** | sim | aparelho | `folha-alto-falante-volume-cabo-0909`, `olho-dela` — sem degrau declarado |
| `audio.alto_falante.preamp` | sim / **MONTOU** | sim / **MONTOU** | sim | aparelho | `folha-preamp-nao-altera-cabo-0909` — **não obedece**, `olho-dela`. Ver §8.1 |
| `audio.jack.volume` | sim / **MONTOU** | sim / **MONTOU** | sim | aparelho | `folha-fone-tem-volume-proprio-cabo-0909`, `olho-dela` — sem degrau declarado |
| `audio.jack.deteccao` | sim / **MONTOU** | sim / **MONTOU** | sim (viaja no report daquele controle) | **JOGO** | não medido no jogo |
| `audio.microfone` | sim / **SAIU NO FIO** | parcial / **SAIU NO FIO** | sim — uma fonte por `uniq` | aparelho | `mic-radio-a-cura-do-driver-instalada-e-medida-0910`, `olho-dela`. Ver §7 |
| `audio.microfone.mudo` | sim / **MONTOU** | parcial / **MONTOU** | sim (`mic.set` com `uniq`) | aparelho | `mic-radio-negativo-do-mudo-0907`, `bancada` — sem degrau declarado |
| `audio.microfone.volume` | não (`decisao-tomada`) / **sem registro** | não (`decisao-tomada`) / **sem registro** | sim, se ganhar campo | aparelho | `folha-mic-volume-o-byte-age-cabo-0909` — **obedece**, `olho-dela`. Ver §8.3 |
| `luz.led_microfone` | sim / **O APARELHO OBEDECEU** | sim / **O APARELHO OBEDECEU** | sim (`daemon/subsystems/luz_do_mic.py`, por `uniq`) | aparelho | `olho-dela`, 31/08 — **é a linha de áudio mais bem provada da casa** |
| `audio.saida_dedicada` | parcial / **MONTOU** | não (`divida`) / **sem registro** | sim | aparelho | não medido |
| `audio.saida_dedicada.payload_do_degrau` | não (`nada-a-acionar`) / — | não (`so-ela-decide`) / — | não se aplica | aparelho | `sfx-radio-a-bomba-monta-os-dois-arranjos-0907`, `MONTOU` |
| `audio.leitura_de_volta` | não (`nao-medido`) / — | não (`nao-medido`) / — | — | **sem direção** (canal `outro`) | a célula **espera a palavra dela** desde 02/09 |

**O que a matriz diz de uma vez, e é contagem no mapa.** As 24 células são as
das **doze chaves `audio.`** — a linha `luz.led_microfone` está na tabela por
vizinhança de assunto e é família `luz.`: ela **não** entra nesta conta.

| degrau | células | quais |
| --- | --- | --- |
| `O APARELHO OBEDECEU` | **2** | `audio.alto_falante` e `audio.alto_falante.rota`, as duas **no cabo** |
| `SAIU NO FIO` | **3** | `audio.alto_falante` no rádio; `audio.microfone` nos dois transportes |
| `MONTOU` | **12** | `rota` no rádio, `volume`, `preamp`, `jack.volume`, `jack.deteccao`, `microfone.mudo` (dois transportes cada) e `saida_dedicada` no cabo |
| sem registro | **7** | `microfone.volume`, `payload_do_degrau` e `leitura_de_volta` (dois cada) e `saida_dedicada` no rádio |

**CORREÇÃO DE FATO — este parágrafo dizia o contrário da tabela acima dele.** Ele
afirmava *"três chegaram a `O APARELHO OBEDECEU` (as duas do LED do microfone e a
rota por cabo) e duas a `SAIU NO FIO`"*. Os dois números estavam trocados, e a
causa é uma só: as duas células do LED são de `luz.led_microfone` e **nunca
estiveram entre as 24**, enquanto `audio.alto_falante` no cabo, que está, ficou
de fora do parêntese. Recontado célula a célula no mapa: **2 · 3 · 12 · 7**. O
programa que conta está na §12, e **o número não tem guarda** — leia lá por quê.

**A assimetria de transporte do áudio é DO APARELHO, não do produto** — e está
declarada no mapa: por cabo o DualSense é placa USB Audio Class e o descritor
não tem report de saída de áudio; por rádio não há placa ALSA nenhuma, e o som
anda por HID, no report `0x35` de 334 bytes.

---

## §3 — A MATRIZ DO MOVIMENTO E DO TOQUE

Doze chaves, `@dualsense`. Mesmas colunas.

| chave | cabo: aciona / degrau | rádio: aciona / degrau | por controle? | destino | quem prova |
| --- | --- | --- | --- | --- | --- |
| `movimento.giroscopio` | sim / **MONTOU** | sim / **MONTOU** | sim (`sensor.set` com `uniq`) | **JOGO** | `aparelho`, 15/08 — até a interface, não até o jogo |
| `movimento.giroscopio.jogo` | sim / **MONTOU** | sim / **MONTOU** | sim | **JOGO** | não medido no jogo |
| `movimento.giroscopio.taxa` | parcial / **sem registro** | parcial / **sem registro** | sim | **JOGO** | `aparelho`, 15/08 — mede o TETO, não «declarada contra entregue» |
| `movimento.acelerometro` | sim / **MONTOU** | sim / **MONTOU** | sim | **JOGO** | `aparelho`, 29/08 |
| `movimento.acelerometro.jogo` | sim / **MONTOU** | sim / **MONTOU** | sim | **JOGO** | `fonte-do-driver`, 31/08 — inferido, não medido |
| `movimento.imu.calibracao` | sim / **MONTOU** | sim / **MONTOU** | sim (feature `0x05` por unidade) | aparelho | `fonte-do-driver`, 11/08 |
| `movimento.imu.ligar` | não (`nada-a-acionar`) / — | não (`nada-a-acionar`) / — | — | aparelho | `aparelho`, 15/08 — **busca fechada: o comando não existe** |
| `movimento.imu.perda` | não (`divida`) / — | parcial / — | não (o contador é global do leitor) | aparelho | `aparelho`, 15/08 |
| `toque.touchpad` | sim / **MONTOU** | sim / **MONTOU** | sim | **JOGO** | medido até o vpad. **Dentro do jogo, no rádio, ela mediu que NÃO responde** — sem causa desde 16/08 |
| `toque.touchpad.clique` | sim / **MONTOU** | sim / **MONTOU** | sim | **JOGO** | `fonte-do-driver`, 31/08 |
| `toque.touchpad.cursor` | sim / **MONTOU** | sim / **MONTOU** | sim | **JOGO** | `fonte-do-driver`, 31/08 |
| `toque.touchpad.escrita` | não (`nada-a-acionar`) / — | não (`nada-a-acionar`) / — | — | **sem direção** | nada a acionar |

**As OITO chaves desta tabela cujo destino é o jogo estão TODAS em `MONTOU` ou
sem registro** — e com a nona, que é `audio.jack.deteccao` da §2 (a única linha
de áudio que chega ao jogo), fecham as **nove** de que o resto deste documento
fala. Nove chaves, **18 células**, **zero** num degrau de jogo. É o mesmo desenho
do defeito do touchpad, e ele é o precedente que manda desconfiar: *o repasse
está íntegro e o jogo não reage.*

**O `movimento.imu.ligar` fecha uma pergunta que volta sempre:** não existe, no
DualSense, comando de ligar ou desligar a IMU. Logo, em **Nativo** não há byte a
zerar — o jogo lê o `hidraw` do físico e o daemon não está no caminho. Quem
chama `sensor.set` em Nativo recebe esse limite **escrito na resposta**
(`core/virtual_motion.py`), em vez de um «aplicado» sobre um giro que continua
chegando.

---

## §4 — A COLUNA DO JOGO — a que falta em toda outra página desta casa

### 4.1 O que já existe de instrumento, e o que ele fecha

| instrumento | pergunta | degrau que sustenta |
| --- | --- | --- |
| `scripts/ensaios/o_jogo_segura_o_nosso_no.py` | algum processo da árvore do jogo está com o **inode** do nosso vpad aberto? | `O JOGO RECEBEU` |
| `scripts/ensaios/o_jogo_no_log_do_proton.py` | a mesma pergunta, por régua independente | `O JOGO RECEBEU` (segunda régua) |
| `scripts/ensaios/quem_o_jogo_abre.py` | o par: o que o jogo que funciona abre, contra o que não funciona | diagnóstico |
| `scripts/ensaios/o_jogo_para_de_ver_o_giro.py` | quantas amostras **distintas** de giro e de acelerômetro um consumidor **SDL** recebe | o movimento, nos dois modos |
| `scripts/ensaios/o_vpad_quando_o_jogo_abre.py` | o que acontece com o vpad no instante em que o jogo abre | apoio |

**Os cinco existem e nenhum rodou com áudio na frente.**

### 4.2 Como se mede `O JOGO RECEBEU` — e as duas armadilhas já pagas

O critério é literal, e está na `ESCADA`:

> o INODE do nó do vpad (`stat -c %i`) aparece em `/proc/<pid>/fd` de um
> processo da **árvore** do jogo.

- **NUNCA case por caminho.** O minor é reciclado: `event22` foi vpad DualSense
  às 01:40 e vpad Xbox às 01:50.
- **NUNCA case pelo carimbo de tempo do fd.** Ele marca quando alguém OLHOU e
  fica cacheado — medido: dois fds do MESMO nó com carimbos separados por 1m36s.
- **Olhe a ÁRVORE, não o `.exe`.** Sob Proton quem segura o dispositivo é o
  `winedevice`, e olhar só o processo do jogo dá falso zero.

O produto já publica os dois inodes sem abrir nada:
`integrations/no_do_vpad.py` traduz o carimbo que ele mesmo pôs no
`UHID_CREATE2` em `(/dev/input/eventN, /dev/hidrawM)` e nos inodes dos dois.
`os.stat` não dispara `UHID_OPEN` e não entra na conta de quem fecha por último.

### 4.3 A PERGUNTA CERTA DO ÁUDIO — e o instrumento que NÃO existe

Som não chega ao jogo: **o jogo toca**, e nós decidimos para onde. A pergunta
equivalente a `O JOGO RECEBEU`, do lado do som, é outra:

> **algum processo da árvore do jogo tem um fluxo aberto no nó daquele
> controle?**

Para o MICROFONE a casa já sabe responder, e não sabe que sabe:
`integrations/quem_ouve_o_microfone.py` lê os `source-output` do PipeWire, tira
o `application.process.id` de cada um e **descarta os nossos** com
`descende_do_hefesto`. É exatamente o instrumento do degrau de entrada do
microfone — e nunca foi usado para isso: ele existe para acender a luz do botão.

Para o ALTO-FALANTE **não existe nada**, e é medição, não impressão:

    grep -rF "sink-input"   src/ scripts/   ->  ZERO ocorrências
    grep -rlF "source-output" src/          ->  quatro módulos

**A casa aprendeu a perguntar quem ESCUTA um controle e nunca perguntou quem
TOCA nele.** É o primeiro buraco desta auditoria, e é o mais barato de fechar:
o espelho do módulo que já existe.

### 4.4 A tabela do JOGO, linha a linha

`RECEBEU?` é o estado de hoje; `como se mediria` é o gesto que fecha.

| linha | Steam | Heroic | jogo direto | como se mediria |
| --- | --- | --- | --- | --- |
| `movimento.giroscopio.jogo` · `movimento.acelerometro.jogo` | não medido | não medido | não medido | `o_jogo_para_de_ver_o_giro.py` com o jogo aberto, nas três máscaras; e `o_jogo_segura_o_nosso_no.py` para o inode |
| `movimento.giroscopio.taxa` | não medido | não medido | não medido | contar SYN por segundo no consumidor SDL, não no físico |
| `toque.touchpad` · `.clique` · `.cursor` | **NÃO responde no rádio** — medição dela, 16/08, sem causa | não medido | não medido | o mesmo par de instrumentos; o toque tem precedente e merece o primeiro lugar |
| `audio.jack.deteccao` | não medido | não medido | não medido | o byte 53 do report do vpad, lido de dentro do jogo — só pelo inode |
| `audio.alto_falante` e filhas | não medido | não medido | não medido | **o instrumento não existe** (§4.3): `sink-input` com PID da árvore do jogo apontando para `hefesto_som_<hex6>` |
| `audio.microfone` e filhas | não medido | não medido | não medido | `quem_ouve_o_microfone.ouvintes_por_fonte`, filtrando a árvore do jogo |

---

## §5 — AS TRÊS MÁSCARAS, e elas decidem metade da resposta ANTES da bancada

Uma afirmação sobre «o jogo recebe giroscópio» sem dizer a máscara não é
afirmação. O tipo fechado é `MascaraDeGamepad` (`profiles/schema.py`), e são
três.

**E a coluna do movimento virou DUAS**, porque os caminhos são dois e só um
deles é da máscara.

| máscara | o vpad | movimento **pelo vpad** | movimento **pelo nó do FÍSICO** | áudio |
| --- | --- | --- | --- | --- |
| **DualSense** (`054c:0df2`) | `uhid`, report `0x01` com a janela de motion de 25 bytes | **o único vpad que carrega giroscópio** | livre e publicando | indiferente |
| **Xbox 360** (`045e:028e`) | `uinput` | o pacote do Xbox 360 é fixo desde 2005, sete eixos — **não há onde pôr** | livre e publicando | indiferente |
| **Nintendo Pro** (`057e:2009`) | `uinput` (o `uhid` só nasce para `dualsense`) | idem — **não há onde pôr** | livre e publicando | indiferente |
| **Nativo** (sem vpad) | não há | não há vpad | livre e publicando — e o jogo lê o `hidraw` do físico, que é quem lhe entrega o giro | indiferente |

**CORREÇÃO DE FATO — esta tabela dizia que a máscara DualSense «é o único caminho
com giroscópio em Virtual», e a árvore mede o contrário.** O nó de movimento do
FÍSICO **não depende de máscara nenhuma**: `movimento.giroscopio@dualsense` tem
`canal = evdev` nos dois transportes e `cabo_detalhe = «Existe mesmo com a
emulação desligada»`, e `core/virtual_motion.py` mediu em 04/09 (SDL 2.30.0
headless, um DualSense no cabo) que *"em Virtual o nó de movimento do FÍSICO
continua livre e publicando, ao lado do espelho"*. O `EVIOCGRAB` de
`daemon/sensor_hub.py` existe exatamente por isso — ele *"alcança o consumidor
evdev direto, nos DOIS modos"*. **O que a máscara decide é o caminho do vpad, e
só ele.**

**E esse nó tem alcance medido, para a afirmação não crescer mais do que deve.**
**FATO SUBSTITUÍDO em 13/09/2026**
([SENSORES-NO-JOGO-02](sprints/2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md)):
esta página dizia que o SDL deixava o nó de movimento de fora. Ele não o abre
como controle, mas o casa como sensor do gamepad da MESMA peça pelo `uniq`:
quem abre o físico por evdev lê o nó do físico, e o jogo que abre o vpad lê o do
vpad. Fora do SDL, quem lê o nó é o **consumidor evdev direto** (`evtest`,
emuladores). **Degrau das duas chaves de movimento que andam
por `evdev` — `movimento.giroscopio` e `movimento.acelerometro`: `MONTOU` nos
dois transportes; dentro do jogo, em qualquer máscara, não medido.**

**A assimetria que esta auditoria quer deixar escrita:** *o som não depende da
máscara; o movimento **pelo vpad** depende inteiramente dela.* O som do controle
é um nó do PipeWire mais uma escrita por `hidraw`, e nenhum dos dois passa pelo
vpad.

**Daí a previsão do microfone — e ela é previsão, não medição.** O esperado é que
o microfone do DualSense continue servindo sob a máscara Xbox, que é o princípio
que ela nomeou em 05/09: *a máscara não custa feature*. **Não medido sob máscara
nenhuma**, e a falta não é de atenção: a coluna `ponte` está vazia nos 227
ensaios (§0), então nenhum ensaio desta casa pode ser relido como prova de
máscara. O degrau de hoje de `audio.microfone` é **`SAIU NO FIO`** nos dois
transportes, medido sem máscara declarada. **O gesto que fecha é o J4**, com o
jogo aberto e a máscara dita em voz alta.

**O movimento não tem essa sorte, e o número é POR CHAVE.** Das nove chaves de
destino JOGO destas famílias, **seis** andam por `uhid` — e essas seis só existem
na máscara DualSense; as **três** de `evdev` não dependem de máscara. Nas
famílias de movimento e toque, as de `uhid` são **cinco**
(`movimento.giroscopio.jogo`, `movimento.acelerometro.jogo`,
`movimento.giroscopio.taxa`, `toque.touchpad` e `toque.touchpad.clique`), que
valem **dez células**. Esta frase dizia *"as dez linhas que chegam ao jogo por
`uhid`"*: no vocabulário deste documento «linha» é **chave**, e dez era a conta
de **células**.

**E a escada de pontes conhece DUAS das três.** `integrations/ponte_escada.py`
tem quatro degraus — `gamepad/dualsense`, `gamepad/xbox`, `native`,
`gamepad/dualsense+steam_input` — e **`nintendo` não é degrau de nenhum**. Quem
escolher a máscara Nintendo na mão sai da escada: `proximo_degrau` devolve
`None` porque a ponte de pé não é um degrau conhecido. Isso é desenho
defensável (*a escolha dela manda; a escada não a corrige*), mas **não está
escrito em lugar nenhum que a máscara Nintendo desliga a escada**, e esta
auditoria o escreve aqui.

---

## §6 — O QUE CADA LANÇADOR MUDA NO CAMINHO

### 6.1 A conta é uma só; o que muda é a ESTRADA por onde ela chega

O daemon materializa o ambiente em
`~/.local/state/hefesto-dualsense4unix/launch_env/` (`daemon/launch_env.py`):
`default.env` mais um `steam_app_<appid>.env` por perfil que opine. As variáveis
que decidem entrada são `SDL_GAMECONTROLLER_IGNORE_DEVICES`,
`SDL_JOYSTICK_HIDAPI` e `PROTON_DISABLE_HIDRAW`.

**Metade de cada ponte congela no `exec`.** A env é lida UMA vez, quando o jogo
abre. É o que parte a escada em dois tramos: trocar entre as duas máscaras
alcança um processo vivo (ao preço de recriar o vpad); subir para Nativo ou para
Steam Input, não.

### 6.2 Steam

- **Chega pelo atalho de inicialização**, uma string constante
  (`hefesto-launch %command%`) gravada no `localconfig.vdf`.
- O wrapper **lê o `SteamAppId`** e exporta o `.env` daquele jogo.
- **A Steam guarda UMA linha de `LaunchOptions` por jogo.** Qualquer coisa
  escrita nela substitui a chamada do wrapper, em silêncio — e aí vence a lista
  de IGNORE da própria Steam, que contém `0x054c/0x0df2`, o PID do NOSSO vpad.
  O sintoma, nas palavras dela: *"parou de ser reconhecido no jogo, mas o perfil
  segue ativo no controle com tudo funcionando só não sendo reconhecido"*.
  A cura anda de carona no gesto de salvar ou aplicar perfil
  (`app/actions/carona_do_wrapper.py`).
- **O Steam Input entra no meio**, e inverte a disputa a favor dela: com o jogo
  na allowlist, os ajustes dela vencem o jogo. É a única ponte da classe *"só
  aceita Steam Input"*, e a mais cara de tentar — exige fechar a Steam, reabrir
  a Steam e reabrir o jogo, porque `UseSteamControllerConfig` só sobrevive com a
  Steam fechada.
- **Para o SOM, a Steam não muda nada:** o jogo escolhe um sink do PipeWire, e
  quem decide qual é o host.

### 6.3 Heroic

- **O wrapper não o alcança.** `assets/hefesto-launch.sh` é ambiente e só
  ambiente: sem `SteamAppId` ele não faz nada, e **nenhum jogo do Heroic tem
  um**.
- A estrada é o `config.json` do Heroic, em `defaultSettings.enviromentOptions`
  — a lista que ele passa a TODO jogo que lança. Quem escreve é
  `integrations/cura_por_estrada.py`, e **só depois de um gesto dela**: o
  primeiro clique arma, o segundo escreve.
- Medido no disco dela em 09/09: a chave existe e **está vazia**. Enquanto ela
  não clicar, um jogo do Heroic abre **sem** o `IGNORE` — ou seja, vendo o
  controle físico ao lado do vpad. O invariante que o produto defende (*um
  controle físico produz exatamente UM dispositivo de jogo*) **não vale no
  Heroic hoje**.
- A biblioteca dela no Heroic, medida no mesmo dia: 35 jogos da Epic e 2 da GOG,
  **0 instalados**.

### 6.4 Jogo direto (binário ou AppImage, sem lançador)

**Não há estrada.** Medido nesta árvore, com busca literal:

    grep -rF "environment.d"   src/ scripts/ assets/ install.sh  ->  ZERO
    grep -rF "/etc/profile.d"  src/ scripts/ assets/ install.sh  ->  ZERO
    grep -rF "set-environment" src/ scripts/ assets/ install.sh  ->  ZERO

O produto tem exatamente três caminhos para o ambiente: o atalho da Steam, o
`config.json` do Heroic e o override de Flatpak dos demais lançadores. **Um
binário nativo aberto do terminal não recebe nenhum deles** — ele abre com o
físico visível ao lado do vpad. É o pior caso conhecido (duplicado), nunca zero
controles, mas é um caso que ninguém nomeou até aqui.

### 6.5 A caixa do Flatpak — e o buraco do som dentro dela

`integrations/sandbox_dos_lancadores.py` responde *"o controle virtual entra na
caixa em que o jogo roda?"* lendo `[Context] devices=` do `metadata` e dos
overrides, somando o `!` que TIRA. Medido na máquina dela em 09/09, os cinco
lançadores trazem `devices=all`.

**Ele não lê `sockets=`**, e a medição é literal:

    grep -c "sockets" src/hefesto_dualsense4unix/integrations/sandbox_dos_lancadores.py  ->  0

`sockets=` é onde mora a permissão de áudio. **Um jogo em flatpak com
`devices=all` e sem a permissão de som veria o controle e não o nó de som dele**
— e a régua da caixa daria verde, porque ela só sabe a metade da pergunta que
lhe interessava quando nasceu.

---

## §7 — AS CINCO CÉLULAS QUE O CADERNO JÁ ULTRAPASSOU

`docs/data/mapa-controles.csv` está em `nao_toca` desta sprint, de propósito:
sumir com a diferença entre *o que a casa dizia* e *o que a auditoria achou*
apagaria o que vale. **Quem grava é a bancada dela.** Aqui está a proposta, com
a prova ao lado.

| chave | transporte | hoje | proposto | a prova |
| --- | --- | --- | --- | --- |
| `audio.alto_falante` | rádio | `SAIU NO FIO` | **`O APARELHO OBEDECEU`** | `som-radio-l2cap-direto-abre-0910`, `olho-dela` — o canal L2CAP direto abre sem root e sem derrubar o perfil de input |
| `audio.alto_falante.rota` | rádio | `MONTOU` | **`O APARELHO OBEDECEU`** | `som-radio-035-toca-0910` e `som-radio-035-setenta-segundos-0910`, `orelha-dela` — 70 segundos sem um corte |
| `audio.microfone` | rádio | `SAIU NO FIO` | **`O APARELHO OBEDECEU`** | `mic-radio-a-cura-do-driver-instalada-e-medida-0910`, `olho-dela` — 1231 permanências do bit viraram UMA |
| `audio.saida_dedicada.payload_do_degrau` | rádio | sem registro | **`MONTOU`** | `sfx-radio-a-bomba-monta-os-dois-arranjos-0907`, `bancada` |
| `audio.alto_falante` | rádio | `radio_aciona = não` | **decisão dela** | as três acima. A célula fica como está até o **negativo de rota** e o **teste cego** rodarem — é disciplina, não dúvida, e está escrito no handoff de 10/09 |

**A última linha é a que NÃO se muda sozinha.** Subir o `aciona` sem o negativo
é exatamente a falácia do canal que responde, com outra roupa.

---

## §8 — TRÊS VEZES EM QUE O APARELHO CONTRADIZ O MAPA — e o aparelho ganha

A precedência é dela: *o aparelho vence o mapa*. As três saíram da folha de
ensaios de 09/09, com a orelha dela.

### 8.1 O pré-amplificador não faz nada — e a célula diz `aciona = sim`

`audio.alto_falante.preamp@dualsense`, cabo e rádio, diz `aciona = sim` com
`de_onde_sei = inferido-do-codigo`. O ensaio
`folha-preamp-nao-altera-cabo-0909` mediu, com ela ouvindo: *"só funciona se
colocar o fone (onde o som sai apenas), mas o slicer em si não altera nada"*.
Os oito degraus do pré-amp não mudaram nada audível.

**Consequência pela régua desta casa** (*byte que o aparelho não obedece não
ganha campo*): o pré-amplificador **não vira controle de tela**, e as duas
células deveriam sair de `sim` para uma leitura que diga o que se mediu. **Não
proponho o valor** — `parcial` e `não` dizem coisas diferentes sobre de quem é o
próximo passo, e essa é a decisão da bancada.

### 8.2 Três das quatro rotas fazem a mesma coisa

`audio.alto_falante.rota@dualsense` está em `O APARELHO OBEDECEU` no cabo desde
16/08. Em 09/09, o ensaio `folha-rota-todas-mono-no-fone-cabo-0909` mediu
`resultado = parcial` e `resultado_da_feature = não obedece`, com as palavras
dela: *"esteREO NO FONE TÁ OK, NA REAL TODOS SÃO MONO NO FONE, O DO ALTO
FALANTE NÃO FUNCIONA AQUI MAS FUNCIONOU NO SOM DO CONTROLE 01"*.

São duas faltas, e a segunda é de TELA: as quatro rotas do `OUTPUT_PATH_SEL`
saem mono no fone, e a rota «só no alto-falante» não sai por aquele caminho.
**A tela não pode oferecer quatro rotas nomeadas pela consequência enquanto três
delas fizerem a mesma coisa** — e a aba 02 hoje oferece três botões, dos quais
dois escrevem esse mesmo `OUTPUT_PATH_SEL`. É trabalho da **SOM-BOTOES-01**,
que corre nesta mesma leva; esta auditoria só junta a medição ao endereço.

### 8.3 O volume do microfone OBEDECE, e a célula diz `aciona = não`

`audio.microfone.volume@dualsense` diz `não` nos dois lados, com causa
`decisao-tomada`: o dono do microfone no Linux é o kernel, e o produto deixa o
`microphone=` fora da chamada de propósito.

**Isso não é contradição — é a decisão esperando o dado que agora existe.** O
ensaio `folha-mic-volume-o-byte-age-cabo-0909` mediu, com ela: *"Deu certo.
funciona"*. O byte do `common[6]` age. A decisão de criar o campo tem dona
escrita — a sprint **MIC-VOLUME-02** — e o que faltava era a medição, que
chegou. Medido **só no cabo**: o rádio não tem nó de áudio para gravar.

---

## §9 — OS BURACOS QUE ESTA AUDITORIA ACHOU, com endereço

1. **`sink-input` não tem leitor nenhum** (§4.3). O espelho de
   `quem_ouve_o_microfone` para a saída não existe, e é ele que fecharia o
   degrau de entrada do alto-falante. **Zero ocorrências em `src/` e em
   `scripts/`.**
2. **A caixa do Flatpak responde metade da pergunta** (§6.5):
   `sandbox_dos_lancadores` lê `devices=` e não lê `sockets=`. O controle entra
   na caixa; ninguém sabe se o som entra.
3. **O interruptor do ACELERÔMETRO não tem linha que responda por ele.** A
   régua das quatro perguntas mapeia o gesto `sensor` da tela para
   `movimento.giroscopio` e só (`DO_APARELHO`, em
   `scripts/check_cabo_bt_perfil_controle.py`). A tela oferece **dois**
   interruptores — `data-sensor="giroscopio"` e `data-sensor="acelerometro"` —
   e `movimento.acelerometro@dualsense` existe no mapa. Hoje o acelerômetro é
   cobrado pela linha do vizinho.
4. **A coluna `ponte` do caderno está vazia nos 227 ensaios** (§0). Enquanto
   ficar, nenhum ensaio pode ser relido como prova sobre uma máscara — e as
   duas perguntas que a máscara decide (§5) não têm como ser respondidas por
   arquivo nenhum.
5. **Um comentário de `interface/pacotes/a02_controles.py` afirma que não há
   método de sensor no daemon** — *"não há método de sensor nos 39"*, medido em
   01/09. `sensor.set` existe e está registrado em
   `daemon/ipc_server.py`, com `{uniq?, giroscopio?, acelerometro?}`. O fato
   caducou em 04/09 com a SENSOR-DE-VERDADE-01 e o comentário ficou. Não é da
   posse desta sprint; fica relatado.
6. **Nenhuma medição desta casa foi feita com quatro controles** (§0). Os 60
   ensaios destas três famílias saíram de mesas de um ou dois.

---

## §10 — A LISTA DE GESTOS PARA A BANCADA DELA

Ordenados pelo que **desbloqueia mais**. Cada um diz o tempo, quantos controles
precisa, e o que destrava. **Eles não repetem** os sete gestos de
`docs/process/sprints/2026-09-10-OS-GESTOS-QUE-SO-ELA-PODE-FAZER.md`, que são da
direção de SAÍDA — estes são a coluna do JOGO, que nenhum deles cobre.

### J1 · O touchpad dentro do jogo, no rádio — 15 min, 1 controle, 1 jogo
**Destrava:** a causa mais antiga em aberto desta família (16/08) e, com ela, as
**seis** chaves que chegam ao jogo por `uhid` — `toque.touchpad`,
`toque.touchpad.clique`, `movimento.giroscopio.jogo`,
`movimento.acelerometro.jogo`, `movimento.giroscopio.taxa` e
`audio.jack.deteccao`. As seis viajam no MESMO nó, e é por isso que **uma**
medição de inode responde por todas.

**E o que ele NÃO alcança — escrito aqui para ela não gastar o gesto esperando
demais.** As outras três chaves de destino JOGO — `movimento.giroscopio`,
`movimento.acelerometro` e `toque.touchpad.cursor` — têm canal **`evdev`** e
viajam pelo nó que o kernel publica para o controle **FÍSICO**
(`core/evdev_reader.py`: `discover_dualsense_motion_evdevs` para as duas de
movimento, `_discover_dualsense_por_nome` com o marcador «Touchpad» para o
cursor — é o `cabo_codigo_ref` das três células). **O inode do vpad não toca
nesse nó**, e nenhum resultado do J1 diz coisa alguma sobre as três.

**E quem responde por elas responde só em parte, o que também tem de ficar
escrito.** O **J2** mede o que um consumidor **SDL** recebe — e SDL é o que quase
todo jogo é. O consumidor **evdev direto** daquele nó (`evtest`, emuladores)
**não tem gesto nesta lista**, e a §5 diz o alcance: o SDL casa o nó ao gamepad
da mesma peça, e quem o lê fora do SDL não tem instrumento aqui. Fica como
buraco declarado, não como gesto prometido.

**O gesto:** com o jogo aberto e a máscara DualSense, rode
`scripts/ensaios/o_jogo_segura_o_nosso_no.py`. Se o inode do nosso vpad
**estiver** em `/proc/<pid>/fd` da árvore do jogo e o dedo continuar sem
resposta, a falha é DEPOIS do vpad e o alvo encolheu de «tudo» para «o que o
jogo faz com o report». Se **não estiver**, o defeito é de ponte, não de
touchpad — e as **seis** chaves de `uhid` mudam de dono no mesmo gesto.

### J2 · O giroscópio dentro do jogo, nas três máscaras — 30 min, 1 controle
**Destrava:** `movimento.giroscopio.jogo` e `.acelerometro.jogo`, os dois
transportes, e a dúvida dela de 08/09.
`scripts/ensaios/o_jogo_para_de_ver_o_giro.py` com o jogo aberto, em
**Virtual/DualSense**, **Virtual/Xbox** e **Nativo**. O Xbox é o controle
NEGATIVO: se chegar giro ali, o instrumento está lendo o físico e a medição toda
cai. **Mexa no controle durante a medição** — controle parado dá zero amostras
distintas, e zero por imobilidade se lê como zero por defeito.

### J3 · Quem toca no alto-falante do controle — 10 min, 1 controle, 1 jogo
**Destrava:** o degrau de entrada do som, que hoje não tem instrumento (§4.3).
Com o jogo aberto e a rota no controle, liste os fluxos de saída e veja se algum
PID da árvore do jogo aponta para `hefesto_som_<hex6>`. **É o gesto que diz se
vale a pena escrever o instrumento** — se o fluxo estiver lá, o espelho de
`quem_ouve_o_microfone` fecha a linha; se não estiver, o problema é de rota e o
instrumento não resolveria nada.

### J4 · O microfone do controle dentro do jogo — 10 min, 1 controle, 1 jogo
**Destrava:** `audio.microfone` no degrau de entrada, com instrumento que **já
existe**.
Com o jogo aberto e o microfone eleito, `quem_ouve_o_microfone` responde quem
está com a fonte daquele controle aberta. Se o PID for da árvore do jogo, o
degrau fecha sem uma linha de código nova.

### J5 · O Heroic sem a cura, e com ela — 20 min, 1 controle, 1 jogo do Heroic
**Destrava:** a metade do §6.3 que ninguém mediu.
Abra um jogo do Heroic **antes** de clicar em «Consertar» e conte quantos
controles o jogo vê; clique, reabra e conte de novo. Se o número não mudar, a
estrada do `config.json` não está sendo lida — e isso muda a sprint dos
lançadores, não esta.

### J6 · O jogo direto — 15 min, 1 controle, 1 binário ou AppImage
**Destrava:** o caso que o produto não cobre (§6.4), e a decisão que vem dele.
Abra um jogo nativo pelo terminal e conte os controles que ele vê. Se ele vir
dois (físico mais vpad), está confirmado o que a busca literal já diz — e a
pergunta passa a ser sua: **vale uma quarta estrada, ou o caso fica declarado e
sem cura?**

### J7 · A mesa de quatro, com o jogo aberto — 40 min, 4 controles + hub
**Destrava:** a pergunta A no único regime em que ela nunca foi feita.
Quatro controles, um jogo aberto, e ao mesmo tempo: giroscópio, touchpad, som
por controle e microfone por controle. **O que anotar é o que degrada primeiro,
e em que ordem.** O mapa já avisa que o orçamento é do ADAPTADOR, não do
controle.

**Se o tempo der para só um, é o J1.** Ele é o único que pode DERRUBAR a leitura
mais confortável desta casa — a de que o repasse ao vpad basta.

---

## §11 — O QUE ESTA AUDITORIA NÃO VERIFICOU

- **Nada foi medido no aparelho.** A bancada estava livre e não foi usada: a
  sprint declara `bancada: false` e o documento não fecha degrau nenhum. Toda a
  §2, a §3 e a §7 são leitura do mapa, do caderno e do fonte desta árvore.
- **Nenhum jogo foi aberto.** As três colunas do §4.4 dizem «não medido» porque
  ninguém mediu, e não porque falte instrumento em quatro das seis linhas.
- **A Steam, o Heroic e o jogo direto foram lidos no CÓDIGO**, não exercitados.
  O que está afirmado do §6 é o que o produto faz segundo os módulos que o
  fazem, mais as medições de disco de 09/09 que eles citam.
- **O Pro Controller e o 8BitDo ficaram de fora das matrizes**, de propósito: a
  tela é dos quatro DualSense por decisão dela de 06/09, e as linhas daqueles
  dois dizem `nao-tem` em quase tudo do áudio. Onde eles importam — o giroscópio
  nativo do Pro passando direto ao jogo — está na §5.
- **Não confirmei se a permissão de som do Flatpak está de fato ausente** em
  algum dos cinco lançadores dela. O que está medido é que o **produto não olha**
  para ela (§6.5).

---

## §12 — O CONTADOR, e o aviso de que ele NÃO TEM GUARDA

**O `48 / 18 / 0` da §0 é medição, não impressão — mas nada nesta árvore o
recalcula amanhã.** O programa abaixo rodou fora da árvore (num rascunho de
sessão) e por isso está escrito aqui, inteiro: enquanto ele não virar arquivo em
`scripts/`, **o número envelhece em silêncio**. É o mesmo defeito que esta casa
já pagou três vezes — *a régua mede o mundo de ontem* —, e fica declarado em vez
de escondido.

Ele não digita degrau nem direção: pergunta os dois ao dono executável,
`DIRECAO_POR_CANAL` de `scripts/check_paridade_transporte.py`, e lê as células de
`docs/data/mapa-controles.csv`.

```python
import csv, pathlib, importlib.util, sys

spec = importlib.util.spec_from_file_location("cpt", "scripts/check_paridade_transporte.py")
cpt = importlib.util.module_from_spec(spec)
sys.modules["cpt"] = cpt
spec.loader.exec_module(cpt)

JOGO = {"O JOGO RECEBEU", "O JOGO REAGIU"}
rows = list(csv.DictReader(pathlib.Path("docs/data/mapa-controles.csv").open(encoding="utf-8")))
alvo = [r for r in rows
        if r["controle"] == "dualsense"
        and r["chave"].startswith(("audio.", "movimento.", "toque."))]

celulas = destino_jogo = no_degrau = 0
for r in alvo:
    for t in ("cabo", "radio"):
        celulas += 1
        if cpt.DIRECAO_POR_CANAL.get(r[f"{t}_canal"]) == cpt.DIRECAO_ENTRADA:
            destino_jogo += 1
            if r[f"{t}_ate_onde_foi"].strip() in JOGO:
                no_degrau += 1

mapa_inteiro = sum(1 for r in rows for t in ("cabo", "radio")
                   if r[f"{t}_ate_onde_foi"].strip() in JOGO)
print(f"celulas={celulas} destino_jogo={destino_jogo} "
      f"ja_no_degrau_do_jogo={no_degrau} | mapa_inteiro={mapa_inteiro}")
```

**A saída de hoje, 11/09/2026, nesta árvore:**

    celulas=48 destino_jogo=18 ja_no_degrau_do_jogo=0 | mapa_inteiro=0

**E ele MORDE.** Numa CÓPIA do mapa, fora da árvore, com
`movimento.giroscopio.jogo` levado a `O JOGO RECEBEU` no cabo:

    celulas=48 destino_jogo=18 ja_no_degrau_do_jogo=1 | mapa_inteiro=1

O zero vira um quando UMA célula sobe. Se o contador fosse cego, os dois lados
dariam o mesmo número. **`docs/data/mapa-controles.csv` não foi tocado** — ele
está em `nao_toca` desta sprint.

**A quinta linha da §0 se confere com duas linhas, e também não tem guarda:**

```python
import csv, pathlib
e = list(csv.DictReader(pathlib.Path("docs/data/ensaios.csv").open(encoding="utf-8")))
print(len(e), sum(1 for r in e if (r.get("ponte") or "").strip()))   # 227 0
```

**O que falta para o número ter dono, e é uma frase:** a `posse` desta sprint tem
um arquivo só — este documento. Criar o contador em `scripts/` e pendurá-lo no
`scripts/portoes.sh` é trabalho de UMA hora, e **precisa do alargamento da posse**
para não colidir com os outros agentes desta leva. **A pergunta é dela.**
