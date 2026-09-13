---
sprint: MIC-SEM-FONTE-01
estado: feita
posse:
  MIC-SEM-FONTE-01:
    - src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py
    # 13/09/2026 (tarde): `hefesto_vivo.py` e a régua da recusa saíram da
    # posse — o recado não existe mais depois da FRASES-E-DICAS-01; a moldura
    # do microfone ganha endereço próprio no gerador.
    - src/hefesto_dualsense4unix/interface/aba02.py
    - tests/unit/test_o_cartao_diz_se_o_som_tem_para_onde_ir.py
bancada: false
depois_de:
  # SERIALIZADA PARA DEPOIS DA SEGUNDA LISTA DELA — 11/09/2026, e é o
  # mesmo precedente da lista anterior: a queixa VIVA vem primeiro. As
  # frentes abaixo reescrevem o TEXTO dos arquivos que esta sprint
  # também toca; medir ou desenhar sobre a prosa de ontem seria medir o
  # mundo de ontem — e a costura viraria «a última a gravar vence».
  - LINGUA-A3
  - TOOLTIP-C1
  # 13/09/2026: a TELA-CALADA-01 muda o canal de recado no mesmo
  # `hefesto_vivo.py` (o sucesso para de depositar, a recusa fica só na
  # página em que nasceu) — e a tarja do título desta sprint saiu em
  # `71c69c57`. Medir a recusa antes daquela costura é medir o canal velho.
  - TELA-CALADA-01
  # 13/09/2026: a OS-QUATRO-NO-AR-01 muda o que o botão do microfone faz
  # no mesmo `a02_controles.py` (os quatro no ar juntos, decisão dela).
  - OS-QUATRO-NO-AR-01
  # 13/09/2026: a TELA-CALADA-04 muda a recusa de gesto sem coluna no mesmo
  # `hefesto_vivo.py` — medir a recusa antes dela é medir o canal velho.
  - TELA-CALADA-04
  # 13/09/2026 (tarde): a FRASES-E-DICAS-01 tira o canal de recado inteiro (a
  # tarja do título desta sprint deixa de existir), e a FRASES-E-DICAS-02
  # escreve o mesmo `a02_controles.py`.
  - FRASES-E-DICAS-01
  - FRASES-E-DICAS-02
nao_toca:
  - src/hefesto_dualsense4unix/daemon/ipc_handlers.py
  - src/hefesto_dualsense4unix/daemon/subsystems/bt_mic.py
  - src/hefesto_dualsense4unix/integrations/fontes_de_captura.py
  - src/hefesto_dualsense4unix/integrations/audio_control.py
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
---

> **ESTADO 2026-09-13: feita** — [entrega](../agentes/2026-09-13/MIC-SEM-FONTE-01-opus.md):
> a moldura do microfone ganha o endereço próprio `mic-apagado`, e o deslizante
> de um controle com `canal_fonte` nulo apaga antes do arrasto, sem frase; o
> alto-falante, o botão do microfone e os modos ficam acesos.

> **ROTA CORRIGIDA — 13/09/2026, e ela vence o corpo abaixo** (triagem das
> abertas). **A metade da TARJA morreu:** a
> [FRASES-E-DICAS-01](2026-09-13-FRASES-E-DICAS-01-toda-frase-de-aviso-que-ainda-chega-a-tela.md)
> tira o canal de recado da tela, e com ele a pergunta [A]/[B] do cartão fechado
> — não há recado para pousar em lugar nenhum. **Sobra a metade do cinza:** o
> botão do microfone de um controle sem fonte publicada fica cinza ANTES do
> arrasto, lendo `canal_fonte`. Dois fatos de 13/09 mudam o como:
>
> 1. o campo `som-sem-endereco` está declarado nas DUAS molduras do cartão
>    (microfone e alto-falante), e pôr `canal_fonte` nele apagaria também o
>    alto-falante dos controles no rádio, que toca pelo 0x35 desde 10/09 — **a
>    moldura do microfone ganha endereço próprio**, que é atributo e não botão; por
>    isso `aba02.py` entra na posse;
> 2. **nenhuma frase nova:** o cinza é o estado, e a regra das duas FRASES vale
>    aqui — `TEXTO_MIC_SEM_FONTE` não vai à dica nem ao `title`.
>
> **Mordida:** estado dublado com `canal_fonte` nulo num controle → o microfone
> dele cinza, o alto-falante dele não; arrancar o endereço próprio → os dois
> cinzas, e reprova.

> *"mic tá igual e o de som também (esse eu esperava que não fosse funcionar agora)"* <!-- noqa-acento: citação literal dela -->
>
> — 09/09/2026, na aba Controles, com os quatro DualSense na mesa

# MIC-SEM-FONTE-01 — a razão chega DEPOIS do arrasto, e a tarja pousa em cima da linha de cima

## §1 — O que ela viu, e o que está MEDIDO

Na foto dela, uma tarja vermelha cobre a linha de cima de um cartão:

> *"O sistema não publica um microfone para este controle: no rádio, é o canal
> do microfone que ainda não está de pé; no cabo, é a placa de som que não
> apareceu. Nada foi mudado."*

É o `TEXTO_MIC_SEM_FONTE` (`interface/pacotes/a02_controles.py:3574`), e ele tem
**um único emissor**: a linha 3766, quando o daemon responde `status:
"sem_fonte"` ao `mic.volume.set`. Nenhum outro caminho o escreve — medido com
`grep -rn "TEXTO_MIC_SEM_FONTE"`: duas ocorrências em `src/`, a definição e o
`raise`.

**A resposta VIVA do daemon dela, medida às 22h23 pelo mesmo caminho que a tela
usa** (`app/ipc_bridge.mic_volume_set_detalhado`, com o volume que os três nós
já tinham — 100%, conferido antes com `pactl get-source-volume`, portanto uma
escrita que não moveu um byte):

| cartão | endereço | transporte | resposta | fonte |
| --- | --- | --- | --- | --- |
| P1 | `14:3a:9a:00:00:ab` | cabo | **ok** | `hefesto_mic_0000ab` (mascarado) |
| P2 | `44:46:48:00:00:03` | rádio | **sem_fonte** | — |
| P3 | `d4:2f:4b:00:00:d8` | cabo | **ok** | `alsa_input.usb-…DualSense…-00.iec958-stereo` |
| P4 | `a0:fa:9c:00:00:f0` | rádio | **sem_fonte** | — |

A ordem dos cartões é a `mesa_viva.mesa_do_estado` do mesmo instante: `p1` é o
controle BRANCO no cabo, `p2` e `p4` são os dois do rádio.

**A tarja não mente. Ela chega tarde e pousa em cima do que ela veio explicar.**

## §2 — A causa, com o número

### A hipótese que eu recebi CAIU, e caiu por três medições

O enunciado desta frente supunha que a MIC-OS-QUATRO-01 (fechada hoje) trocou o
nome do nó e que o `mic.volume.set` procurava pelo nome antigo. **Não é isso**:

1. **a MIC-OS-QUATRO-01 trocou o RÓTULO, não o NOME.** O nome do nó já era
   `hefesto_mic_<hex6>` desde 06/09; o que ela trocou foi o `Description`, que
   passou de *"Microfone DualSense BT (endereço)"* para *"Microfone do Controle
   N"*. A busca não olha rótulo nenhum;
2. **a regra 0 de `fontes_de_captura.escolher_fonte` casa por IDENTIDADE** — o
   rabo hex do MAC dentro do nome do nó —, não por texto. Chamada nesta árvore
   com a lista viva do `pactl`, ela devolve o nó do controle branco;
3. **o daemon vivo responde `ok`** para os dois controles no cabo — a tabela da
   §1. Simulei também o estado de ANTES de ela apertar o botão do microfone
   (a lista de fontes sem o `hefesto_mic_*`): a regra 3, o casamento por
   dispositivo USB, resolve os dois do cabo do mesmo jeito.

**Fica registrado porque é a regra da casa:** a hipótese era boa e a medição a
derrubou. O que sobra não é um defeito de busca.

### A causa medida: o fato JÁ ESTÁ na tela, e a tela não o lê

O daemon publica, **por controle, a cada tique**, em `state_full`:

```
controllers[i].audio.canal_fonte
```

Medido no `state_full` dela, no mesmo instante da tabela da §1:

| endereço | transporte | `canal_fonte` | `volume_captura` |
| --- | --- | --- | --- |
| `d4:2f:4b:00:00:d8` | cabo | `alsa_input.usb-…-00.iec958-stereo` | 100 |
| `14:3a:9a:00:00:ab` | cabo | `hefesto_mic_0000ab` | 100 |
| `44:46:48:00:00:03` | rádio | **`null`** | **`null`** |
| `a0:fa:9c:00:00:f0` | rádio | **`null`** | **`null`** |

`canal_fonte: null` **é** `sem_fonte`. A resposta pela qual ela paga um arrasto
já viajou no payload do tique anterior.

**E o cinza que a diz ANTES do clique já existe, inteiro, nesta aba.** A folha
da `02-controles.html` tem:

```css
.moldura[data-bloco="microfone"][title] .vol,
.moldura[data-bloco="microfone"][title] .rota{opacity:.45}
.moldura[data-bloco="microfone"][title] .puxa-vol{cursor:not-allowed}
```

e o comentário ao lado, no próprio arquivo, diz por que ele nasceu:

> *"a GTK impede ANTES do clique enquanto esta tela só recusava DEPOIS."*

**O mecanismo está pronto e ligado a UMA condição só.** Quem escreve o `title`
da moldura é o campo `som-sem-endereco`, e a condição dele é uma linha
(`a02_controles.py:2599`):

```python
"som-sem-endereco": ("" if uniq_do_entry(c) is not None else TEXTO_AUDIO_SEM_ENDERECO)
```

*Não tem endereço* → cinza. *Tem endereço e não tem microfone* → **aceso, e o
deslizante arrasta**. `porques_do_som` (`:1623`) tem a mesma cegueira: ela
pergunta a `acao_mic` (o MUDO do firmware) e a `acao_speaker_mudo` (a posse do
volume), e nenhuma das duas sabe da fonte de captura. `canal_fonte` aparece
UMA vez em toda a interface — em `no_do_microfone` (`:1305`), que alimenta as
catorze barrinhas da onda sonora. **A mesma leitura, dois metros ao lado, nunca
foi perguntada pelo deslizante.**

É a assinatura que esta casa já nomeou em 04/09: *o instrumento apontava para
outra coisa*. Aqui é pior de um jeito específico — **o instrumento certo está
no mesmo arquivo e responde de graça.**

### A segunda porta: quando a tarja MENTE

`_texto_do_pactl` (`integrations/audio_control.py:295`) devolve `None` em
`OSError` e em `SubprocessError`. `TimeoutExpired` é `SubprocessError`, e o teto
é `SUBPROCESS_TIMEOUT_SEC = 2.0`. Um `pactl` que demora vira, sem escala,
*"o sistema não publica um microfone para este controle"*.

Não é hipótese — está no journal dela de hoje:

```
21:56:11.936  [warning] audio_fonte_do_uniq_falhou  err="…'pactl','list','sources','short' timed out after 2.0 seconds"
21:56:13.947  [warning] audio_fonte_do_uniq_falhou  …
21:56:15.958  [warning] audio_fonte_do_uniq_falhou  …
21:56:16.708  [info]    luz_do_mic_sem_resposta     uniq=…
```

Três, na abertura do daemon. Medido agora com a máquina ociosa, o mesmo `pactl`
volta em **0,00 s nas doze corridas**, curto e longo — ou seja: o teto de 2 s é
folgado no repouso e estoura numa rajada. Nessa janela a frase **afirma um fato
sobre o sistema dela que ninguém mediu**, e a tela não tem como distinguir *"o
teu controle não tem microfone"* de *"eu não consegui perguntar"*.

### A terceira metade: onde a tarja POUSA

Medido no DOM, com Chrome headless (`/usr/bin/google-chrome`, nenhuma janela na
tela dela), reproduzindo exatamente o que `hefesto_vivo.pintar_recados` faz —
os dois literais de estilo copiados do piloto, o cartão `p1` da página
publicada:

```
const ESTILO_NA_GRADE = 'position:absolute;top:4px;left:4px;right:4px;z-index:5;margin:0;';
```

`.ctl` é `display:flex; flex-direction:column; position:relative` — então
`foraDoFluxo` é verdadeiro, e o recado nasce **colado no topo do cartão**,
enquanto a `.faixa` (a linha de cima) começa 6 px abaixo. O recado mais curto
possível tem 30 px.

| janela | largura do cartão | altura da tarja | a linha de cima se moveu? | o que a tarja cobre |
| --- | --- | --- | --- | --- |
| 1280 px | 1180 px | 30 px (1 linha) | **0 px** | `Cosmic Red` `•` `cabo` `·` `DualSense` `100%` |
| 1024 px | 924 px | 46 px (2 linhas) | **0 px** | os mesmos seis |
| 900 px | 800 px | 46 px | **0 px** | os mesmos seis |
| 760 px | 660 px | 46 px | **0 px** | os mesmos seis |

**A cura de 04/09 funcionou e cobrou o preço no outro lado.** Ela nasceu na aba
05, contra um recado que EMPURRAVA as linhas do cartão (medido lá: o topo do
desenho descia 65 px). O comentário que a acompanha já escrevia o preço, e
ninguém o mediu:

> *"`block` fica de fora de propósito: (…) tirar do fluxo criaria sobreposição
> onde não havia problema."*

Aqui há problema. `faixa_moveu: 0` nas quatro larguras é a prova de que a cura
faz o que promete — **e a lista de cobertos é a prova de que ela troca um
defeito por outro.** É a mesma forma de 04/09, palavra por palavra: *o aviso
que veio explicar quebra a tela que estava explicando.*

E **não há canto livre neste cartão**. Medi as outras duas pousadas absolutas:

| pousada | cobre |
| --- | --- |
| `top:4px` (hoje) | `Cosmic Red` `•` `cabo` `·` `DualSense` `100%` |
| logo abaixo da faixa | `1 toque` `ATIVO` `X` `+143.2` |
| `bottom:4px` | `Sons do jogo` `Todo o som do PC` `R2` `40 / 255` |

## §3 — A cura, e as opções

### (a) A razão chega ANTES do arrasto — e não custa endereço novo

Uma condição a mais no campo que já existe: sem endereço **ou** sem
`canal_fonte`, o `title` da moldura do microfone se escreve, e a folha apaga o
bloco e põe `cursor:not-allowed` no deslizante. Zero HTML novo, zero campo
novo, zero IPC novo.

**A frase do cinza é curta, e é a que o cartão pode dizer**, porque o cartão
sabe o transporte — o que o `TEXTO_MIC_SEM_FONTE` não sabia e por isso recitava
os dois:

* no rádio: *"O canal do microfone deste controle ainda não está de pé."*
* no cabo: *"Este controle não publicou placa de som."*

**O `TEXTO_MIC_SEM_FONTE` FICA** no gesto, e não vira código morto: ele é a
resposta para a corrida entre o tique e o clique (o cartão pintou com fonte, ela
arrastou, a fonte caiu no meio). O que muda é ele deixar de ser o caminho
NORMAL de descobrir.

### (b) A tarja deixa de cobrir a linha de cima

Medi a alternativa no mesmo DOM: o recado **de volta ao fluxo**, mas como
primeiro filho de `.corpo-cx` (o corpo do cartão), e não de `.ctl`:

| onde | o cartão cresce | a linha de cima desce | cobre |
| --- | --- | --- | --- |
| `top:4px` (hoje) | 0 | 0 | os seis da linha de cima |
| fluxo, 1º filho de `.ctl` | 37–58 px | **58 px** | nada (mas empurra — é o defeito de 04/09) |
| fluxo, 1º filho de `.corpo-cx` | 37–58 px | **0 px** | **nada** |

O cartão ABERTO desta aba é `height:auto; flex:1 0 auto` — ele **pode** crescer,
ao contrário do cartão de linhas fixas da 05 que produziu a cura. Por isso a
mesma solução que lá era impossível aqui é a barata.

**A ARMADILHA, e ela está medida:** com o cartão FECHADO, `.corpo-cx` é
`visibility:hidden; overflow:hidden; height:0`. Um recado ali some inteiro —
medido, `recado_visivel: false`. Trocar a tarja por um recado invisível é
exatamente o silêncio que este canal nasceu para curar, e **é a única coisa que
esta cura pode quebrar**. O recado do cartão fechado continua onde está hoje
(sobre a faixa, que é o cartão inteiro), ou vai para a faixa da página
(`data-hef-recados`) — ver a decisão abaixo.

### O que é DELA nesta sprint

**A pousada do recado no cartão FECHADO.** São dois caminhos e nenhum é
tecnicamente melhor:

* **[A]** fica como hoje — sobre a linha, porque no cartão fechado a linha é o
  cartão inteiro e não há para onde ir;
* **[B]** vai para a faixa de recados da página, e o cartão fechado ganha só a
  borda laranja dizendo *"tem recado aqui, abre"*.

Nada mais precisa dela. As frases do cinza são as duas curtas acima, na língua
que ela já aprovou; se ela quiser outras, são duas linhas.

### O que NÃO é desta sprint, e por quê

* **O «Microfone do Controle 2» sobre o cartão que se chama P1.** Medido hoje
  no `pactl` dela: o nó do controle branco tem `Description: Microfone do
  Controle 2` e a mesa da tela dá `pref: p1`, `jogador: 1` **para o mesmo
  endereço**. É a `TRES-CONTAS-PARA-UM-NUMERO-01`, que tem dona e já recebeu
  esta prova. O que esta medição acrescenta é o alcance: **a divergência deixou
  de ser teórica e está publicada na lista de som do sistema dela.**
* **O alto-falante.** Ela já sabe: *"esse eu esperava que não fosse funcionar
  agora"*. O que falta são as três linhas de registro do daemon declaradas na
  `SOM-POR-CONTROLE-01`.
* **Só 1 dos 4 microfones existe — e não é defeito.** Medido: o supervisor do
  cabo (`bt_mic._reconciliar_o_cabo`) só ergue canal para `uniq` que **PEDIU**,
  e o pedido é o gesto dela. O journal do dia tem **dois** `bt_mic_canal_pedido`,
  os dois do controle branco; `d4:2f:4b:00:00:d8` nunca foi pedido. A trava de
  privacidade está funcionando como desenhada. Os dois do rádio dependem da
  ponte, que é conhecida.
* **Mas há um fato que sai daí e é da MESA-DE-QUATRO-01, não daqui:** para o
  mesmo cartão no cabo, o `mic.volume.set` tem **dois alvos possíveis** — o nó
  ALSA antes do gesto, o `hefesto_mic_<hex6>` depois —, e a troca acontece num
  gesto que não é o do volume. Medido: `integrations/canal_do_microfone.py` não
  tem **uma** menção a volume, e nada reaplica o número quando o canal do cabo
  sobe. O número que ela escolheu antes do botão do microfone não viaja para o
  nó novo.

## §4 — O que MORDE

Cada uma foi escrita para reprovar com a cura arrancada.

1. **`canal_fonte: None` acende o cinza.** Entrada dublada com endereço e
   `audio.canal_fonte = None` → `som-sem-endereco` volta preenchido. Arranque a
   condição nova: a régua reprova com o campo vazio. **E a metade contrária, no
   mesmo arquivo:** com `canal_fonte` preenchido o campo volta `""` — uma cura
   que apaga o bloco dos dois do cabo seria pior que o defeito.
2. **A frase do cinza segue o TRANSPORTE.** `transport: "bt"` diz do canal;
   `transport: "usb"` diz da placa. Uma frase só para os dois é o defeito que o
   próprio `TEXTO_MIC_SEM_FONTE` documenta ter herdado.
3. **A tarja não cobre a linha de cima.** No DOM, com o cartão ABERTO: insira o
   recado pelo caminho do produto e meça `getBoundingClientRect()` da `.faixa`
   antes e depois — **ela não pode se mover** (é a cura de 04/09, que continua
   valendo) **e não pode ser interceptada** pelo retângulo do recado. Hoje a
   segunda metade reprova nas quatro larguras medidas na §2; sem a cura ela
   volta a reprovar.
4. **O recado do cartão FECHADO continua VISÍVEL.** `.corpo-cx` fechado é
   `height:0; visibility:hidden` — a régua mede `height > 0` e
   `visibility !== 'hidden'`. É a única regressão que esta cura pode causar, e
   ela reprova sozinha.
5. **A corrida continua coberta.** Com `canal_fonte` preenchido no tique e o
   daemon respondendo `sem_fonte` no clique, o gesto ainda levanta o
   `TEXTO_MIC_SEM_FONTE`. Apagar aquele `raise` junto com o cinza deixaria a
   janela entre os dois muda.
6. **A prova de tela, `--oculta`**, com o daemon vivo e pelo menos um controle
   cujo `canal_fonte` seja `null` na mesa: foto antes e depois, o bloco do
   microfone do rádio cinza, o do cabo aceso, e o arrasto no cinza sem recado
   nenhum. **Não pede gesto dela** — só que a mesa tenha um controle no rádio,
   que é o estado da bancada hoje.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** | com placa USB, `canal_fonte` vem preenchido e o bloco fica **aceso**; o arrasto escreve. Sem placa (ou antes de o PipeWire publicá-la), `canal_fonte` é `null` e o bloco fica cinza dizendo *"este controle não publicou placa de som"*. Medido hoje: os dois do cabo dela acesos, um no nó ALSA e outro no `hefesto_mic_<hex6>`. |
| **por BT** | `canal_fonte` é `null` enquanto a ponte de áudio não estiver de pé — medido nos dois do rádio dela — e o bloco nasce **cinza**, dizendo *"o canal do microfone deste controle ainda não está de pé"*. Quando a ponte subir, o mesmo campo o acende sozinho, sem uma linha a mais: a fonte da verdade é o tique, não um estado guardado na tela. |
| **no perfil** | **não se aplica, e é decisão de 06/09 já tomada.** O cinza é LEITURA de estado vivo; ele não é preferência e não vai para o perfil. O que o perfil guarda é o número do volume (`ProfileMicConfig.volume`), que esta sprint não toca. |
| **por controle** | é a metade que dá nome à sprint. O fato é `controllers[i].audio.canal_fonte` — **um por aparelho**, não um por máquina — e a régua tem de morder a mesa MISTA: dois no cabo acesos e dois no rádio cinzas, na mesma foto. Uma régua que testa um controle só passaria com a leitura global, que é o defeito que o `uniq` do `mic.volume.set` fechou em 20/08. |
