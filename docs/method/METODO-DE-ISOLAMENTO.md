# O método de isolamento — a lista que nos impede de errar

- **Escrito em:** 10/08/2026, depois do primeiro ensaio de bancada dela e minha
  (rumble do DualSense por Bluetooth).
- **Revisto em:** 13/08/2026, depois das bancadas de 12 e 13/08. O que a revisão
  trouxe tem um nome só: **o instrumento mentia, não o produto** — quatro formas
  do mesmo defeito, todas medidas, todas com hora e linha de código.
- **Nasceu de:** *"a ideia é terminarmos aqui com uma to do list de método boa o
  suficiente pra nunca errarmos"*.
- **Para que serve:** um ciclo repetível para isolar qualquer feature de qualquer
  controle em qualquer canal — e, no fim, **encolher o produto**.

O molde é o estudo `LIGHTBAR-BT-CULPADO-01`. Ele levou dezesseis dias, e a lição
que este documento existe para não deixar esquecer: **o que fechou aquela conta
não foram os seis ensaios com o suspeito presente — foi o único em que ele estava
ausente.** Correlação vira causa no ensaio que discrimina, nunca no acúmulo.

---

## Antes de qualquer ensaio — as perguntas de sanidade (0 a 5)

Ordem importa. A primeira que falhar interrompe: um ensaio feito sobre premissa
errada não é ensaio, é folclore com data.

Os números são **endereços**, não contagem: são citados de fora deste arquivo, e
por isso não se renumeram. Pergunta nova entra pelas pontas — foi assim que a
`0` entrou.

### 0. Em QUEM o instrumento está mirando?

- **Acrescentada em:** 13/08/2026, por `VPAD-NO-ESPELHO-01`.
- **Por que ela é ZERO e não SEIS:** as outras cinco são citadas por número de
  fora deste arquivo — `scripts/ensaio_rumble_um_bit_por_vez.py:391` diz
  *"Pergunta 2 do método"*. Renumerar invalidaria a citação em silêncio, que é o
  defeito da armadilha `A-12`. A pergunta nova entra **antes** sem empurrar as
  outras.

O `scripts/ensaio_rumble_em_par.py` prometia por escrito recusar gamepads
virtuais **e não recusava**: a régua era VID + PID + barramento, e o vpad do
próprio Hefesto forja os três de propósito — ele existe para se passar por um
DualSense Edge (`integrations/uhid_gamepad.py:575` carimba
`02:fe:00:00:00:0N`; a linha `:1478` carimba `hefesto-vpad`). Com quatro
controles na mesa, o `--listar` marcava `mirar? SIM` nos QUATRO vpads.

```bash
.venv/bin/python scripts/ensaio_rumble_em_par.py --listar
```

**Por que `.venv/bin/python` na frente, e não o caminho nu** (medido em
13/08/2026, e vale para **todo** script de `scripts/` citado neste guia): os
arquivos estão em modo `664`, então o shell recusa com `permissão negada` antes
de qualquer coisa; e o `--listar` importa `evdev`, que só existe no venv do
projeto — `python3 -c "import evdev"` devolve `ModuleNotFoundError` nesta
máquina e `.venv/bin/python -c "import evdev"` funciona. O próprio cabeçalho do
script já declarava a fonte (`scripts/ensaio_rumble_em_par.py:26`: *"a do venv
do projeto"*); quem copiava a linha nua parava no primeiro comando.

**O que OLHAR:** a coluna `mirar?` de cada linha. Confira à mão o nó que você vai
usar — e o `N` do `hidraw` você não precisa adivinhar, o laço varre todos:

```bash
for d in /sys/class/hidraw/hidraw*; do
  echo "== $d"
  grep -E 'HID_PHYS|HID_UNIQ|HID_ID' "$d/device/uevent"
done
```

| você lê | é |
|---|---|
| `HID_PHYS=hefesto-vpad` | **vpad NOSSO** — não é alvo de ensaio nenhum |
| `HID_UNIQ=02:fe:…` | **vpad NOSSO** — o **bit 1** do primeiro octeto (`0x02`) é o de *localmente administrado*, que por definição não colide com endereço de fábrica (`integrations/uhid_gamepad.py:572-573`) |
| `HID_PHYS=<MAC do adaptador>` | DualSense de verdade, no rádio |
| `HID_PHYS=<caminho USB>` | DualSense de verdade, no cabo |

**O que isto decide:** se o que você está prestes a medir é o aparelho ou o
espelho do próprio produto. O vpad **tem força-feedback e aceita o efeito
calado**, sem motor nenhum girar — a medição sai falsa sem avisar.

**O que NÃO serve de régua**, e é o ponto: barramento, VID e PID (o vpad forja os
três) e *"mora sob `/devices/virtual/`"* — com BlueZ ≥ 5.73 o `bluetoothd` cria o
HID dos controles **físicos** de rádio por `/dev/uhid`, no mesmo lugar.

**Se der errado:** anote no ensaio *qual* nó você mirou, com o `HID_PHYS` colado.
A régua única é `scripts/identidade_do_vpad.py`, importada pelos três ensaios;
qualquer instrumento novo importa dela em vez de reimplementar.

### 1. O instrumento briga com o produto?

A armadilha mais cara desta casa. `test trigger --raw` disputa o hidraw com o
daemon e **imprime "aplicado" sem ter aplicado**.

```bash
# o comando que vamos usar passa pelo daemon, ou escreve no hidraw direto?
grep -n 'ipc\|hidraw\|_safe_call' src/hefesto_dualsense4unix/cli/cmd_test.py
```

Passa pelo IPC → segue. Escreve direto no hidraw com o daemon de pé → **pare** e
use o IPC, senão o ensaio mede a briga, não a feature.

**E o instrumento tem de RECUSAR sozinho.** Não é conselho: dois já fazem, e a
forma é para copiar.

```bash
systemctl --user is-active --quiet hefesto-dualsense4unix.service && echo VIVO
```

- `scripts/ensaio_o_keepalive_mata_o_rumble.py:281-287` — imprime
  `RECUSO rodar com o daemon vivo` e sai, a menos que se passe
  `--confirmo-parar-o-daemon` (ele mesmo para e religa) ou `--com-o-daemon-vivo`
  (só a fase `gatilho`, cujo objeto **é** a disputa);
- `scripts/ensaio_rumble_um_bit_por_vez.py:783-792` — mesma guarda, e com uma
  segunda trava: em **783-792** o `modo_ensaio` recusa e manda *"Rode de novo
  com --confirmo-parar-o-daemon"*, e em **799-801** ele aborta se o daemon
  **não parou de verdade** (*"escrever agora seria medir a briga"*). O detector
  que as duas usam é o `daemon_ativo()` da linha **356** — ele só responde
  sim/não; quem **recusa** são as linhas acima. O script ainda imprime a idade
  do daemon contra o último commit em `src/` (`idade_do_daemon()`, linha 390),
  que é a **pergunta 2** respondida sem ninguém precisar lembrar.

Quem **não** tem a guarda é o `scripts/ensaio_rumble_em_par.py`, e por desenho:
ele mede a cura **com o daemon vivo**. A regra não é *"todo instrumento recusa"*,
é **todo instrumento DIZ na tela em que estado do daemon está medindo**.

### 2. O daemon vivo é mais velho que o código?

Instalação editável: o código no disco pode estar curado e o processo em memória
não. O sintoma é traiçoeiro — a **ausência** de um dado, não um erro.

```bash
systemctl --user show hefesto-dualsense4unix.service -p ActiveEnterTimestamp
git log -1 --format=%cd -- src/    # o código é mais novo que o processo?
```

### 3. O transporte é mesmo o que eu penso?

Não confie no rótulo da janela nem na memória.

```bash
for d in /sys/class/hidraw/hidraw*; do echo -n "$d "; grep HID_ID "$d/device/uevent"; done
#   0005:... = Bluetooth      0003:... = USB
```

### 4. O que este ensaio pode derrubar?

Escreva a hipótese **antes**, e o que ela prevê para cada lado. Ensaio cuja
resposta não muda nada é passatempo.

### 5. A hipótese explica o que JÁ funcionava?

Regra da casa. Se a explicação só cobre o defeito e não explica por que aquilo
funcionava ontem, ou no outro transporte, ela está incompleta — e o que vier
depois é contorno, não cura.

---

## O ciclo — os oito passos

### Passo 1 · Levantar os suspeitos LENDO O CÓDIGO

Nunca por palpite. Abra o caminho e liste tudo que é escrito para aquela feature.

O rumble do DualSense, medido em 10/08, é o exemplo do porquê:

```python
if not rumble_asserted:
    flag0 &= ~(COMPATIBLE_VIBRATION | HAPTICS_SELECT)   # dois bits
    flag1 &= ~MOTOR_POWER                               # um
    flag2 &= ~COMPATIBLE_VIBRATION2                     # um
```

**Quatro bits de autorização em três flags, mais dois bytes de intensidade.**
Seis coisas escritas para uma feature — e ninguém nunca mediu de quantas o
aparelho precisa. Foi assim na lightbar: cinco canais, um importava.

### Passo 2 · A LINHA DE BASE, antes de mexer em nada

Aciona no estado normal. Funciona?

- **Funciona** → há o que eliminar. Siga.
- **Não funciona** → não há o que eliminar ainda; o defeito é anterior aos
  suspeitos. Ache-o primeiro.

### Passo 3 · Um suspeito por vez, e os DOIS lados

A regra que o `scripts/eliminacao.py` implementa e que não se negocia:

> Um suspeito só é julgado quando existem ensaios **com** ele e **sem** ele.

Enquanto houver só um lado, o veredicto é `inconclusivo` — e o instrumento diz
**qual ensaio falta**. Essa frase é a que ninguém tinha durante os dezesseis dias
da lightbar.

### Passo 4 · O ensaio que DISCRIMINA

Melhor que repetir o mesmo ensaio é achar um que separe duas hipóteses de uma
vez. Em 10/08, `--weak 0 --strong 200` respondeu três perguntas num disparo:
o rumble funciona no rádio, os motores são endereçáveis em separado, e `strong`
é o esquerdo — porque **só um lado vibrou**.

### Passo 5 · O controle negativo

O que **não** deveria mudar o resultado, e não muda. Na lightbar foi o `0x08`
disparado fora da janela: o mesmo report, sem travar — foi ele que provou que a
variável era a **janela**, não o report.

### Passo 6 · Registrar na hora

```bash
.venv/bin/streamlit run bancada.py     # o formulário de ensaio
```

Cada ensaio grava: suspeito, presente sim/não, resultado, quem observou, e a
nota do que mais estava valendo. **Uma prova sem data é folclore**, e um ensaio
não registrado no mesmo dia vira lembrança.

### Passo 7 · A PODA — a metade que dá lucro

Todo suspeito que ficar `não é a causa` é candidato a **parar de ser acionado**.

Foi o que ela descreveu: *"de 5 canais, um deles é o que realmente impactava;
após isso passamos a usar somente ele, e deixamos o projeto menos complexo"*.

A causa isolada responde **por onde acionar**. Os inocentados respondem **o que
dá para parar de fazer** — e é essa a pergunta que encolhe o código.

Cuidado único: `não sei se faz efeito` **não é** `provei que não faz efeito`.
Podar por inconclusivo é arrancar a cura de alguém achando que era enfeite.

### Passo 8 · O teste que MORDE

Sem ele, tudo isto volta na próxima mexida.

```bash
# 1. escreva o teste     2. rode: passa
# 3. ARRANQUE a cura DO ARQUIVO DE PRODUÇÃO
# 4. rode: TEM de reprovar        5. devolva a cura
```

**Arrancar de verdade, não simular.** Em 10/08 escrevi um teste que "provava" a
mordida com um `move_to()` no lugar de remover a linha: passava com a cura
arrancada. Teste que passa sem a cura não protege nada — e é pior que teste
nenhum, porque dá sossego falso.

---

## O CHECKLIST — o padrão universal de validação de um elemento

- **Acrescentado em:** 11/08/2026, a pedido dela: *"pra que esse padrão de agora
  seja o padrão universal de validação de cada elemento, pra que tenhamos um
  padrão de checklist nesse sentido"*.
- **Nasceu de:** a sessão da mesa cheia — quatro DualSense, dois no cabo e dois
  no rádio — em que rumble, lightbar e gatilho foram validados pela mesma
  sequência, e a sequência se mostrou melhor que a soma das partes.

Os oito passos acima continuam sendo o ciclo. Este checklist é **a ordem em que
se percorre o ciclo para UM elemento**, do zero até poder escrever `O APARELHO
OBEDECEU` no mapa sem mentir.

Marque cada linha. Item pulado é dado — anote que pulou. Item respondido no
chute contamina tudo o que vier depois.

### A — Antes de tocar no aparelho

- [ ] **A1.** As perguntas de sanidade desta página, da `0` à `5`, na ordem. A
      primeira que falhar interrompe.
- [ ] **A2.** Os suspeitos levantados **lendo o código**, não por palpite
      (Passo 1). Liste tudo que é escrito para aquele elemento: bits de
      autorização, bytes de valor, e quem mais escreve no mesmo lugar.
- [ ] **A3.** **Que grau esta feature tem hoje?** Se está em `MONTOU`, ninguém
      provou que o aparelho obedece — e essa é a pergunta, não um detalhe. E se
      a feature é da direção de ENTRADA (o jogo lendo o nosso vpad), o grau mais
      alto da ida não diz nada sobre ela: pergunte pelos degraus da volta.

### B — Provar que a peça responde

- [ ] **B1. A linha de base** (Passo 2). No estado normal, aciona? Se não, o
      defeito é anterior aos suspeitos.
- [ ] **B2. O teste de controle: tudo apagado contra tudo aceso.** Antes de
      perguntar *de que lado* falha, prove que **responde**. Em 11/08 três
      rodadas foram perdidas medindo uma peça que talvez nem obedecesse.

### C — Medir NO PAR, que é o que a mesa cheia compra

- [ ] **C1.** Acione o elemento em **um controle no cabo e um no rádio, na mesma
      janela**. Registre o espalhamento do disparo — se não for de milissegundos,
      são dois ensaios em fila, não um ensaio de coexistência.
- [ ] **C2.** Leia o resultado por esta regra, que não se negocia:
      - **`sim` em par** → vale, e é evidência **mais forte** que sozinho: a
        feature sobreviveu à companhia.
      - **`não` ou `parcial` em par** → **ambíguo**. Não se sabe se é o
        transporte ou a coexistência. Re-meça aquele controle **sozinho** antes
        de escrever qualquer coisa.
- [ ] **C3.** O **controle negativo simultâneo**: o que não deveria mudar, na
      mesma mão e no mesmo instante. Em 11/08 foi o R2 continuar solto enquanto
      o L2 endurecia — provou de uma vez que o comando agiu e que não vazou de
      lado. É a **melhoria mais barata e mais forte** que esta casa achou: ele
      transforma *"achei que estava diferente"* em medição, e custa zero
      rodada extra. Ver a seção **O que FUNCIONOU** abaixo.
- [ ] **C4. Mire UM controle e deixe os outros de testemunha** (ideia dela,
      12/08). Com quatro na mesa, o alvo por MAC é o controle negativo mais
      forte que existe: se o `uniq` fosse ignorado o comando viraria broadcast,
      e o isolamento seria ilusão. Comando literal na seção
      **O que FUNCIONOU**.

### D — Isolar o mecanismo, não só o sintoma

- [ ] **D1. Um suspeito por vez, os DOIS lados** (Passo 3), com **ida e volta**:
      tire o suspeito e veja curar, devolva e veja o defeito voltar. Só a volta
      distingue causa de coincidência.
- [ ] **D2. DOSE-RESPOSTA, sempre que o suspeito tiver um número.** Se o
      suspeito é um intervalo, um limite ou uma constante, **mude o número e
      veja a resposta seguir**. Isso é prova causal; sim/não é indício.
      Em 11/08 o keepalive foi fechado assim: `0,5 s` produzia um pulso,
      `8,0 s` produziu **oito segundos exatos** de vibração.
- [ ] **D3. O aparelho honra os BITS de autorização, ou os BYTES de valor?**
      Pergunte sempre, para todo elemento. Em 11/08 ficou medido que o firmware
      do DualSense **obedece aos bytes de motor com os bits de vibração
      desligados** — o que derrubou a premissa de uma cura inteira que estava
      escrita, correta na própria lógica, e mirando o alvo errado.
      **Isto não foi medido para gatilho, LED nem áudio**, e os blocos deles
      também saem escritos em todo report.
- [ ] **D4. A hipótese explica o que JÁ funcionava?** (pergunta 5). Se o
      elemento funcionava em outro transporte, em outro dia, ou no relato dela,
      a explicação tem de cobrir isso também.

### E — O desenho do ensaio, para não desperdiçar a mão dela

- [ ] **E1. Nunca peça cronômetro a um humano.** Se a resposta depende de
      *quando* algo mudou, o instrumento está errado — redesenhe para que a
      resposta seja **sentida**, não medida. Em 11/08 duas rodadas se perderam
      pedindo "em que instante parou", e a terceira fechou a questão trocando o
      tremor **de lado**: ou muda de mão, ou não muda.
- [ ] **E2. Ela não vê a janela do comando.** A mensagem "aperte agora" só chega
      **depois** que o comando termina. Ou o ensaio roda em segundo plano e ela
      age quando quiser, ou dura o bastante para ela pegar o controle depois de
      ler.
- [ ] **E3. Amplitude máxima na primeira tentativa** (`METODO-01`, 01/08). 15%
      contra 100% quase reprovou uma entrega correta; 0 contra 255 a reabilitou
      em trinta segundos.
- [ ] **E4. O desenho não pode ser AMBÍGUO** — regra dela, 12/08:
      *"nosso resultado não deve ser ambíguo"*. Eu propus *"deixe os quatro na
      mesa e veja qual para antes"*; ela recusou. O desenho que ficou:
      **dois controles, um em cada mão**, e os outros dois recebendo a mesma
      carga como lastro. Comparar duas mãos é resposta que o corpo dá sem
      dúvida; olhar quatro na mesa não é. A carga fica igual, o que muda é
      **como se lê**. Foi assim que `rumble-quatro-duracao-igual-r1/r2`
      fecharam em duas rodadas o que uma noite antes tinha saído
      *"por duração diferente"*.
- [ ] **E5. CARIMBE O RELÓGIO do disparo — T0 e T1, hora de parede.** Sem isso
      não há como cruzar com o `journalctl` depois, e foi exatamente o que
      faltou quando um controle caiu às 22:00:33 de 12/08: eu não sabia quando o
      rumble tinha rodado. **Cuidado:** o `ensaio_rumble_em_par.py` imprime o
      **espalhamento** do disparo (linha 349, `time.monotonic`), que é outra
      coisa — ele **não** imprime hora de parede. Enquanto não imprimir, carimbe
      por fora:
      ```bash
      date +%T.%3N; .venv/bin/python scripts/ensaio_rumble_em_par.py <args>; date +%T.%3N
      ```
      e cole os dois na nota do ensaio, como fazem os de 12/08
      (`22:10:22.942 -> 22:10:31.206`).

### F — Fechar

- [ ] **F1. Registrar na hora** (Passo 6) — **inclusive o ensaio que você
      descartou, e por quê**. Um ensaio mal desenhado que foi trocado é
      informação: sem o registro, o próximo o repete.
- [ ] **F2. O teste que MORDE** (Passo 8), arrancado **de verdade** do arquivo
      de produção, visto reprovar, devolvido.
- [ ] **F3. O grau, e ele é honesto por construção:** `MONTOU` → `SAIU NO FIO` →
      `O APARELHO OBEDECEU` → `O JOGO RECEBEU` → `O JOGO REAGIU`. Só o olho dela
      sustenta o terceiro e o quinto; o quarto um instrumento vê, se declarar
      qual régua usou. A escada inteira, com o critério de cada degrau, está na
      seção *A escada de `ate_onde_foi`*.
- [ ] **F4. A PODA** (Passo 7): o que foi inocentado pode parar de ser acionado.
- [ ] **F5. A pergunta que ela faz e que fecha o assunto:** *"o elemento
      específico que faz ele funcionar de fato está isolado?"* Funcionar **não
      é** saber por quê. Se o elemento passou em tudo acima e você ainda não sabe
      de qual bit, byte ou condição ele depende, escreva isso na ressalva — em
      vez de deixar a linha parecer fechada.
- [ ] **F6. Antes de escrever `não obedece`, pergunte se aquilo é DECISÃO
      DELA.** Em 12/08 registrei `não obedece` para o BlueZ não reconectar
      sozinho — e a reconexão automática está desligada **a pedido dela**, por
      decisão anterior, tomada por causa dos problemas que ela trazia. O ensaio
      `ps-nao-reconecta-daemon-parado-2242` foi corrigido por ela no mesmo dia.
      O que fica no caderno é o **fato** (`Connectable=false`, `Paired=true`,
      `Bonded=true`, `ReconnectMode=device`, bond intacto), nunca o julgamento.
      Procure em `docs/process/` e na memória de decisões antes de chamar de
      defeito.
- [ ] **F7. A linha do caderno** — como escrever para o julgador não ser
      enganado: seção própria abaixo, e ela vale tanto quanto o ensaio.

---

## O INSTRUMENTO MENTE MAIS QUE O PRODUTO — as quatro formas

- **Acrescentado em:** 13/08/2026, depois das bancadas de 12 e 13/08.

Foi o padrão que dominou a sessão inteira: **em quatro investigações seguidas o
defeito estava na régua, não no aparelho.** Elas parecem diferentes e são a mesma
coisa — algo entre você e o fato responde por ele.

Rode isto **antes** de acreditar em qualquer leitura de bancada — é o único
comando que vem antes de tudo, porque as outras três formas só se diagnosticam
**depois** que um verde e um vermelho discordam:

```bash
.venv/bin/python scripts/ensaio_rumble_em_par.py --listar
```

Só lê: nem toca no aparelho, nem fala com o daemon. Se a coluna `mirar?` disser
`SIM` para um nó cujo `HID_PHYS` é `hefesto-vpad`, **pare** — você ia medir o
espelho do produto. As formas 2 a 4 têm cada uma o seu comando na própria
seção; a triagem entre elas é uma pergunta só:

| o sintoma | a forma |
|---|---|
| verde na máquina dela, vermelho no runner | **2** (o teste mede a máquina) ou **3** (o dublê é incompleto) — leia a exceção: `AttributeError` é 3, decisão que mudou é 2 |
| a **mesma SHA** deu verde e vermelho | **4** — é corrida do instrumento, não defeito |
| o instrumento diz "aplicado" e nada aconteceu | **1**, ou a `A-1` (o instrumento disputa o hidraw) |

### Forma 1 — o instrumento aceita mirar no lugar errado

Já está na **pergunta 0**. Resumo com o comando:
`.venv/bin/python scripts/ensaio_rumble_em_par.py --listar`, e olhe o
`HID_PHYS`.

### Forma 2 — o teste mede a MÁQUINA, não a lógica

O teste passava na máquina dela e reprovava no runner, nas três versões de
Python, e o motivo é que ele perguntava ao **sistema** sem querer.

```bash
grep -n 'uhid_available' src/hefesto_dualsense4unix/daemon/launch_env.py
```

**O que OLHAR:** a linha **1414**:

```python
prognostico_uhid = uhid_available() and permite_uhid
```

Passar `permite_uhid=True` é **metade** da condição. `uhid_available()` pergunta
se `/dev/uhid` existe — na máquina dela existe, no runner não. O teste
`test_o_prognostico_de_outra_mascara_segue_intacto`
(`tests/unit/test_ignore_no_fim_da_sequencia_cobertura.py:169`) achava que
bastava a metade dele.

**O que isto decide:** se o verde do teste fala da sua lógica ou do hardware de
quem o roda.

**A cura, e ela tem forma fixa:** a condição de ambiente entra **declarada**, com
`monkeypatch`, e some junto com o teste — nunca vira `skipif`, que esconde a
pergunta em vez de respondê-la.

**Como pegar sozinho:** todo teste que exercita lógica de decisão, leia o `and`
inteiro. Se alguma parcela pergunta ao sistema, ou você a declara ou está
medindo a máquina.

### Forma 3 — o dublê não imita o que o produto usa

```bash
grep -rn 'markup_escape_text' src/ tests/
```

**O que OLHAR:** o stub de `gi` que os testes de interface plantam quando não há
PyGObject tem `timeout_add`, `idle_add` e `source_remove` — e **não** tinha
`markup_escape_text`. Resultado: `AttributeError` nas três versões de Python do
`ci.yml` e verde na máquina dela, onde o PyGObject é real.

**O que isto decide:** se o dublê cobre a superfície que o produto de fato usa.

**A cura:** `src/hefesto_dualsense4unix/utils/markup.py` — o escape passa a ter
piso próprio, e o GLib continua fazendo o trabalho quando está inteiro. Note o
que **não** foi feito: proteger a chamada com `hasattr` teria trocado a exceção
por markup quebrado, que é pior — o teste afirma que o escape **acontece**.

**Como pegar sozinho:** quando o CI reprova e a máquina dela passa, o suspeito
número um é o dublê, não o produto.

### Forma 4 — a foto mede um INSTANTE em vez de esperar a condição

```bash
grep -n 'FOTO-QUE-ESPERA-01' tests/unit/test_dialogo_nao_mata_a_janela.py
```

**O que OLHAR:** a foto era tirada **uma vez**, 120 ms depois de o diálogo
nascer. Sob Xvfb **não há gerenciador de janelas** e o foco de teclado chega
quando chega — a **MESMA SHA** (`973c92c`) deu `success` e `failure` no CI
(runs do GitHub Actions `31668837810` e `31669474030`; conferíveis por
`gh run view <id>`, não pela árvore).

**O que isto decide:** se o vermelho é defeito ou corrida do instrumento. Um
teste que dá os dois resultados no mesmo commit não está medindo o produto.

**A cura, e ela não afrouxa nada:** a foto **espera a condição** em vez de medir
num instante arbitrário — até 3 s, olhando a cada 60 ms; se o foco não vier no
teto, `tem_foco` sai `False` e o teste reprova como antes.

**Como pegar sozinho:** todo prazo fixo em teste de interface é uma corrida
esperando uma máquina mais lenta. Prazo é **teto de espera**, nunca *momento de
medir*.

### O irmão destas quatro: o portão que erra de véspera

Duas armadilhas de **portão** têm a mesma forma e custaram dois dias cada:

**A corrida do `pipefail`** (`A-13`) — `produtor | grep -q` com
`set -o pipefail`: o `grep -q` sai no primeiro casamento, o produtor morre com
SIGPIPE (141) e o **pipe inteiro** devolve 141, mesmo tendo achado.

```bash
sed -n '31,50p' scripts/check_packaging_parity.sh   # CORRIDA-DO-PIPEFAIL-01
```

**O que OLHAR:** a assinatura no log é `printf: write error: Broken pipe`. Na
máquina dela o produtor ganhou 200 de 200; o runner, mais lento, perdeu — e o
`ci.yml` acusou o `doctor.sh` de não chamar uma função **viva na linha 4493**.
A cura é **não construir o pipe**: o produtor vai para uma variável e o `grep` lê
dela por here-string. As outras nove ocorrências de `| grep -q` naquele arquivo
seguem vulneráveis por construção — estão anotadas lá.

**O relógio no lugar do conteúdo** (`A-14`) — o `gerar-mapa.py --check`
comparava **mtime**, e mtime deu verde falso das duas maneiras possíveis
(`scripts/gerar-mapa.py:28-46`): por **omissão** (o `ensaios.csv` não estava na
lista de fontes, então editar o caderno nunca reclamava, e o `specs.html`
publicado mostrava a lightbar como *"os ensaios se contradizem"* com o culpado
já isolado no mesmo commit) e por **relógio** (qualquer ferramenta que toque o
HTML depois da geração o deixa mais novo — o `--fix` do
`scripts/validar-acentuacao.py` reescreve arquivos; e no CI o `actions/checkout`
escreve em ordem de caminho, então `specs.html` na raiz nasce depois de `docs/`).
Hoje ele compara **conteúdo**.

```bash
python3 scripts/gerar-mapa.py --check   # a página publicada é a que as fontes produzem?
```

**E o `--fix` da acentuação reescreve o ARQUIVO INTEIRO** (`A-15`).
`scripts/validar-acentuacao.py:869` faz `path.write_text(...)` com o conteúdo
todo; e como a leitura é `read_text` (linha 745), que traduz `\r\n` em `\n` por
newline universal, **um arquivo CRLF volta LF depois de uma única substituição**,
sem uma palavra. Importa para o `ensaios.csv`: o `csv.writer` do Python termina
linha em `\r\n` por padrão, então o caderno recém-escrito pela bancada é CRLF, e
o `--fix` o converte calado. Se você usa `--fix`, **olhe o `git diff` inteiro**,
não só as linhas que pediu:

```bash
git diff --stat                      # uma "correção de acento" que muda o arquivo todo é isto
grep -c $'\r' docs/data/ensaios.csv  # quantas linhas ainda terminam em CRLF? 0 = já foi convertido
```

**E aqui o instrumento óbvio mente — medido em 13/08/2026.** O reflexo é rodar
`file docs/data/ensaios.csv` e procurar *"with CRLF line terminators"*. **Não
funciona para CSV:** escrevi dois arquivos de duas linhas, um com `\r\n` e outro
com `\n`, e o `file` respondeu `CSV ASCII text` para **os dois** — a frase sobre
CRLF não aparece quando ele classifica o arquivo como CSV. O `grep -c $'\r'`
separa os dois casos na hora (`2` contra `0`), e o `od -c arquivo | head` mostra
os bytes se você quiser ver com os próprios olhos. Se insistir no `file`, tem de
ser `file -k`, que deixa de parar na primeira classificação e aí sim diz
`CSV ASCII text\012- , ASCII text, with CRLF line terminators`.

Detalhe de shell que também engana: `grep -c` sai com **rc=1** quando a contagem
é `0`. Num script com `set -e` isso derruba a linha justamente no caso bom —
use `grep -c $'\r' arquivo || true` ali dentro.

---

## O que FUNCIONOU — copie isto

Um guia que só lista erro ensina medo. Estas cinco coisas fecharam medições que
não fechavam, e todas custam pouco.

### 1. O controle negativo DENTRO do mesmo ensaio

**É a melhoria mais barata e mais forte da bancada.** Não é uma rodada a mais: é
a mesma rodada, lida melhor.

```bash
hefesto-dualsense4unix test trigger --side left --mode Rigid --params 0,8
```

**O que OLHAR:** aperte **L2 e R2** de **cada** controle. O L2 endurece; o R2
tem de continuar solto.

**O que isto decide:** três coisas de uma vez — o comando agiu, não vazou para o
outro lado, e o lado não está invertido. Foi assim que
`gatilho-esq-radio-1216` (12/08) sustentou o grau no rádio, e assim que
`gatilho-lado-nao-esta-invertido` (11/08) **eliminou uma suspeita na mesma
rodada em que ela nasceu**.

**Cuidado que já custou** (armadilha `A-10`): o R2 ficar solto prova a
não-contaminação; **não** prova que o R2 obedece. São dois ensaios.

### 2. Isolar por MAC — mirar um, deixar os outros de testemunha

Ideia dela, 12/08. O daemon sabe fazer: `_apply_por_uniq`
(`src/hefesto_dualsense4unix/daemon/ipc_handlers.py:821`) aplica **só** no
controle do MAC pedido, e a GUI usa isso. **O CLI não expõe** — o
`cmd_trigger` (`src/hefesto_dualsense4unix/cli/cmd_test.py:76-83`) só aceita
`--side`, `--mode`, `--params` e `--raw`, e despacha em broadcast. Enquanto não
expuser, fale com o socket.

**Primeiro, o MAC do alvo — é o `HID_UNIQ` da pergunta 0**, e é o mesmo laço:

```bash
for d in /sys/class/hidraw/hidraw*; do
  echo -n "$d "; grep -E 'HID_UNIQ|HID_PHYS' "$d/device/uevent" | tr '\n' ' '; echo
done
```

Ler essa saída tem uma ordem, e ela foi medida nesta máquina em 13/08 (seis nós):

1. **Jogue fora o que nem é controle.** Quatro dos seis eram teclado e mouse
   (`HID_ID=0003:00003554:0000FA09` e `0003:000025A7:0000FA07`) — e são
   exatamente os de `HID_UNIQ` **vazio**.
2. **Dos que sobram, o vpad é o do `HID_PHYS=hefesto-vpad`**, com `HID_UNIQ` em
   `02:fe:`. Continua valendo a pergunta 0: a régua é o `HID_PHYS`, **não** o
   VID/PID, que o vpad forja (aqui ele se anunciava `054C:0DF2`, o Edge, contra
   o `054C:0CE6` do físico — parecido demais para servir de régua).
3. **O que resta é o DualSense de verdade, e o `HID_UNIQ` dele é o MAC que você
   quer.** Ele vem preenchido **inclusive no CABO** — o nó físico medido tinha
   `HID_PHYS=usb-0000:…/input3` e `HID_UNIQ` cheio ao mesmo tempo. Não espere
   que "cabo" signifique "sem MAC aqui".

Copie o do alvo:

```bash
python3 - <<'PY'
import json, os, socket
S = f"{os.environ['XDG_RUNTIME_DIR']}/hefesto-dualsense4unix/hefesto-dualsense4unix.sock"
p = {"jsonrpc": "2.0", "id": 1, "method": "trigger.set",
     "params": {"side": "right", "mode": "Rigid", "params": [0, 8],
                "uniq": "AA:BB:CC:00:00:FF"}}   # o MAC do alvo, do HID_UNIQ acima
s = socket.socket(socket.AF_UNIX); s.connect(S)
s.sendall(json.dumps(p).encode() + b"\n")
print(s.makefile().readline().strip())
PY
```

(O MAC aí é de exemplo, na máscara da casa `OUI:00:00:NN` — octetos 4 e 5
zerados, que é o que `tests/unit/test_docs_mac_anonimato.py:145` impõe. Nunca
cole um MAC real num arquivo versionado.)

**O que OLHAR:** confira os **quatro** controles, não só o alvo. Os três
intocados são o controle negativo — e cobrem o risco real: **se o `uniq` fosse
ignorado, viraria broadcast e o isolamento seria ilusão.**

**Cuidado medido — o modo de falha mais provável é MAC errado, e ele é MUDO.**
`_apply_por_uniq` (`daemon/ipc_handlers.py:821-840`) devolve `True` assim que
chama `apply_output_for`, **sem conferir se aquele MAC está na mesa**. E do
outro lado, `apply_output_for`
(`core/backend_pydualsense.py:3452-3494`) trata controle desconectado por
desenho: registra o override no mapa em memória e, quando não há handle
(linha **3417**), loga `apply_output_for_desconectado_registrado` e **retorna
sem escrever no hardware** (linha **3423**). MAC que nem parece MAC cai antes,
em `apply_output_for_sem_mac_ignorado` (linha **3406**). Nos dois casos o daemon
responde `{"status": "ok"}` do mesmo jeito.

Ou seja: **se nada acontecer em NENHUM dos quatro, desconfie do MAC, não do
produto.** Um dígito trocado produz exatamente a tela de "o produto não
obedeceu".

E a resposta **não** é a confirmação que parece ser. O `trigger.set` devolve só
`{"status": "ok"}` (`ipc_handlers.py:958`). O `led.set` devolve
`aplicado_em` (`ipc_handlers.py:1061`) — mas, no caminho por-MAC, `aplicado_em`
é `[str(params["uniq"])]` (linha **1027**): **o eco do que você pediu**, não uma
leitura do que ficou. Ele prova que a rota por-uniq foi tomada, não que o
aparelho obedeceu. Quem confirma o alvo é a mão dela nos outros três.

### 3. Carimbar o relógio

Ver **E5**. Sem T0/T1 não se cruza com o `journal`, e sem cruzar com o `journal`
não se sabe se o que aconteceu na janela foi seu.

```bash
journalctl --user -u hefesto-dualsense4unix.service --since "2026-08-12 22:10:20" --until "2026-08-12 22:10:35"
journalctl -k --since "2026-08-12 22:10:20" --until "2026-08-12 22:10:35"   # o kernel também
```

**Ponha a DATA, mesmo cruzando na mesma noite.** `--since "22:10:20"` sem data
significa **hoje**: rodando o par acima na manhã seguinte, os dois devolvem
`-- No entries --` com **rc=0** — janela errada, e a tela é idêntica à de
"não aconteceu nada". Medido em 13/08/2026, e é a `A-1` em outro traje: o
instrumento respondeu, mas não à pergunta que você fez.

**O que OLHAR:** silêncio do kernel e do daemon na janela é **dado** — desde que
a janela seja a certa. Os ensaios de 12/08 o registram assim: *"Kernel e daemon
em silêncio nas duas janelas — ninguém caiu, ninguém foi removido"*.

### 4. O instrumento que se recusa a mentir

O padrão está na **pergunta 1**. O exemplo mais limpo é um script de bancada
**não versionado** (`pintar_por_rota.py`, da noite de 12/08) <!-- ref-externa: arquivo de scratchpad, não versionado — a ausência dele é o assunto da frase -->, que abre com a
regra e a faz valer: *"não se mede cor com o daemon vivo — ele desfaz em ≤30 s e
você mede a defesa, não o firmware"*, e **recusa rodar** se achar o socket.
**Todo instrumento novo desta casa deveria nascer assim**, e dois dos versionados
já nascem (ver pergunta 1). Que ele tenha ficado no scratchpad é, em si, uma
perda: o instrumento que acertou o desenho é o que menos sobrevive.

### 5. O portão pegou a PRÓPRIA CASA no mesmo dia

A régua `grau-sem-ensaio` (em `scripts/check_paridade_transporte.py`) foi
escrita em 12/08 e **reprovou três afirmações nossas na mesma sessão**: as três
linhas de gatilho declaravam `O APARELHO OBEDECEU` **por rádio** sem um único
ensaio de rádio no caderno. As três foram medidas na bancada daquela noite,
entre **22:16 e 22:21 de 12/08** (`gatilho-esq-radio-1216`,
`gatilho-resumo-radio-1216`, `gatilho-dir-radio-isolado-2221`) — o próprio
`gatilho-esq-radio-1216` registra que *"foi o portao grau-sem-ensaio (12/08) que
flagrou"*. O commit que trouxe a régua para a árvore é o `0b010bd`, carimbado
**13/08 00:41**: a mesma sessão, depois da meia-noite.

```bash
.venv/bin/python scripts/check_paridade_transporte.py
```

**O que isto decide:** se o mapa está afirmando mais do que a bancada sustenta.
**É a prova de que a régua vale a pena** — ela cobra de quem a escreveu primeiro.

---

## A LINHA DO CADERNO — escrever para o julgador não ser enganado

O `scripts/eliminacao.py` julga sozinho, e **julga o que está escrito**. Quatro
maneiras de enganá-lo sem mentir uma vírgula:

### O `linha_id` sem `@controle` não casa — e o ensaio SOME

```bash
python3 -c "import csv;print({r['linha_id'] for r in csv.DictReader(open('docs/data/ensaios.csv'))} - {r['id'] for r in csv.DictReader(open('docs/data/mapa-controles.csv'))})"
```

**O que OLHAR:** o conjunto tem de sair **vazio**. O casamento é por
`(linha_id, transporte)` contra a coluna `id` do mapa
(`eliminacao.py:147`; `check_paridade_transporte.py:602`), e o `id` do mapa é
`chave@controle` — `gatilho.esquerdo.adaptativo@dualsense`, não
`gatilho.esquerdo.adaptativo`. **Não há portão que acuse o órfão**: ele
simplesmente não aparece para o julgador, e você fica com um ensaio caro que não
conta para nada.

### O `resultado` tem de CARREGAR a ressalva

Um ensaio de 11/08 dizia `obedece` e a ressalva — *"por duração diferente"* —
vivia só na nota. **O julgador lê o campo, não a nota**: com `obedece` limpo ele
dizia NÃO-É-A-CAUSA e absolvia o culpado. O caderno foi corrigido em 12/08 para
`parcial`, que já está no vocabulário
(`check_paridade_transporte.py:273`) — a **observação** não mudou, mudou o campo
que a codifica. Regra: *se você precisou de um "porém" para descrever o que
sentiu, o campo não é `obedece`.*

### O NOME do suspeito decide o veredicto

*"O daemon escrevendo output"* (amplo) e *"o keepalive perpétuo"* (estreito) dão
vereditos **diferentes** para os MESMOS ensaios. Os seis ensaios de rumble de
11/08 foram reformulados em 12/08, com o aceite dela, porque a dose-resposta
(`0,5 s` → pulso; `8,0 s` → oito segundos exatos) tinha estreitado o mecanismo.
O nome amplo **não estava errado, estava impreciso** — e manter os dois obrigaria
a próxima pessoa a escolher entre eles.

**Como escolher o nome:** o mais estreito que os seus ensaios sustentam. Se a
dose-resposta apontou uma constante, o nome é a constante.

### Não julgue DECISÃO DELA como defeito

Ver **F6**. O caderno registra fato; o julgamento é o que envelhece mal.

---

## As armadilhas, todas medidas

**Sem contagem no título, de propósito**, e a história deste próprio cabeçalho é
a prova. Em `94d72aa` (12/08 00:38) ele dizia *"As **sete** armadilhas"* sobre
uma tabela de **doze** linhas; em `0b010bd` (13/08 00:41) foi corrigido para
*"As **doze**"* — e teria caducado de novo na mesma semana, porque a lista
cresce toda bancada.

Então o número não mora mais aqui: **quantas são hoje se lê no último ID da
tabela abaixo**, que é a contagem por construção. Um número no cabeçalho é uma
afirmação que caduca sozinha e que ninguém lembra de conferir — a armadilha
`A-12` em miniatura, dentro do documento que a nomeia. Cada armadilha tem **ID
estável** (`A-1`…), para poder ser citada de fora sem depender de posição.

Cada uma custou tempo real. Nenhuma é hipotética.

| ID | Armadilha | Como ela aparece |
|---|---|---|
| A-1 | **O instrumento disputa o hidraw** | Diz "aplicado" e não aplicou |
| A-2 | **O daemon vivo é mais velho que o código** | Falta um dado que deveria estar lá |
| A-3 | **Medir contra a régua errada** | Número absurdo (uma posição relativa deu `1,207`, impossível) |
| A-4 | **Teste que não morde** | Verde com a cura arrancada |
| A-5 | **Relatório de agente não é prova** | Reportou `aplicado=true` sem ter escrito no arquivo |
| A-6 | **Colisão de nomes silenciosa** | `getElementById('corpo')` devolveu o `<g>` do SVG, não a tabela; nenhum erro |
| A-7 | **Só um lado do ensaio** | Seis ensaios "com" e nenhum "sem": zero poder de prova |
| A-8 | **Pedir cronômetro à mão humana** | Duas rodadas com respostas incompatíveis entre si — e nenhuma delas era erro dela |
| A-9 | **A janela que ela não vê** | O "aperte agora" só chega depois que o comando terminou |
| A-10 | **Confundir controle negativo com prova** | O R2 ficar solto prova que o comando não vazou; **não** prova que o R2 obedece |
| A-11 | **Supor que o firmware honra os bits** | A cura desliga os bits de autorização e o aparelho obedece aos bytes assim mesmo |
| A-12 | **O caderno envelhecer sem que ninguém note** | Uma medição que só existe em docstring deixa o `eliminacao.py` acusando um culpado removido há sete dias |
| A-13 | **A corrida do `pipefail`** | `produtor \| grep -q` devolve 141 **tendo achado**; enganou dois dias, porque a máquina dela ganhava a corrida e o runner perdia |
| A-14 | **Comparar relógio em vez de conteúdo** | `--check` verde com a página publicada divergindo das fontes |
| A-15 | **O `--fix` reescreve o arquivo inteiro** | Uma "correção de acento" converte o CSV de CRLF para LF sem avisar |
| A-16 | **O instrumento aceita mirar no vpad do próprio produto** | O vpad tem força-feedback e aceita o efeito **calado**; a medição sai falsa sem erro nenhum |
| A-17 | **O teste mede a máquina** | Verde na máquina dela, vermelho no runner — a condição perguntava ao sistema (`/dev/uhid`) |
| A-18 | **O dublê não tem o que o produto usa** | O stub de `gi` sem `markup_escape_text`: `AttributeError` só no CI |
| A-19 | **A foto mede um instante** | A MESMA SHA deu success e failure sob Xvfb, onde não há gerenciador de janelas |
| A-20 | **Presumir a causa e escrever como se fosse medição** | Um controle caiu às 22:00:33 de 12/08 e eu escrevi uma causa de firmware sem uma medição que a sustentasse. O caderno só tem o **efeito** (`comb-slot-jogador-2200`) e um **suspeito em aberto** (`rumble-quatro-duracao-igual-r1`) |
| A-21 | **O desenho ambíguo** | "Veja qual dos quatro para antes" não tem resposta; dois controles, um em cada mão, tem |
| A-22 | **`linha_id` sem `@controle`** | O ensaio não casa com o mapa e **some do julgador**, sem portão que acuse |
| A-23 | **`resultado` limpo com a ressalva só na nota** | `obedece` + *"porém por duração diferente"* fez o julgador absolver o culpado |
| A-24 | **O nome amplo demais do suspeito** | *"O daemon escrevendo output"* e *"o keepalive perpétuo"* dão vereditos opostos para os mesmos ensaios |
| A-25 | **Julgar decisão dela como defeito** | `não obedece` para o BlueZ não reconectar sozinho — que é pedido dela, decisão anterior |

A `A-5` merece nota: em 10/08 um agente relatou a cura aplicada e com mordida
provada, e o arquivo estava intacto. **Conferir o arquivo é parte do método**, não
desconfiança.

As `A-8` a `A-12` são de 11/08, e três delas são erro meu, registrado de
propósito:

- **A `A-8` e a `A-9` são de desenho, não de execução.** Quando o ensaio exige da
  mão dela uma precisão que a mão não dá, quem falhou foi o instrumento. A saída
  não é repetir com mais cuidado — é **redesenhar para que a resposta seja
  sentida**.
- **A `A-10` aconteceu comigo em pleno registro:** marquei `gatilho.direito` como
  `O APARELHO OBEDECEU` porque o R2 ficou solto enquanto o L2 endurecia. Aquilo
  provava a não-contaminação, não a obediência do lado direito. Ela pegou.
- **A `A-12` é a mais silenciosa de todas.** O caderno não erra sozinho: ele fica
  certo sobre o dia em que foi escrito. Toda medição que muda um veredito
  **precisa virar linha em `ensaios.csv` no mesmo dia**, ou o instrumento passa a
  mentir com autoridade.

As `A-13` a `A-25` são de 12 e 13/08, e a maioria também é erro meu:

- **A `A-20` é a que fez este guia ser reescrito.** Sobre a queda de um controle
  às 22:00:33 de 12/08 eu escrevi uma causa de firmware — *"foi power off do
  firmware por proteção"* — sem uma única medição que a sustentasse, num
  documento cuja pergunta de abertura é qual instrumento está mentindo. Ela
  corrigiu na hora, e a regra que ela deu vale mais que o episódio: *"presumir
  nunca pode ser feito, trabalhamos com evidências"*.

  **As duas falas acima são relato da sessão de 12→13/08, não citação de
  documento.** Não as procure na árvore — não estão lá, e conferir quer dizer ir
  ao transcrito daquela sessão. O que **está** na árvore, e é o que sustenta esta
  armadilha, são duas linhas do caderno:

  - o **efeito medido**, em `comb-slot-jogador-2200`: quando o controle do cabo
    caiu, o daemon removeu o jogador (`coop_player_removed`, `players=3`) e
    **renumerou** os que ficaram — o `event29` era P4 e virou P3; quando o
    controle voltou, o `event29` voltou a P4. A renumeração é **reversível e
    simétrica**, e nada ali fala de firmware;
  - o **suspeito em aberto**, dito em voz alta em
    `rumble-quatro-duracao-igual-r1`: *"PS apertado sem querer"* — e foi por
    causa dele que segurar os quatro na mesa foi descartado como desenho de
    ensaio.

  Causa nenhuma foi escrita, e é assim que fica até alguém medir.
- **`A-16` a `A-19` são as quatro formas do instrumento que mente**, e têm seção
  própria acima, com comando e linha.
- **`A-22` a `A-25` são do caderno**, e também têm seção própria: são as maneiras
  de enganar o `eliminacao.py` sem mentir uma vírgula.

---

## O que registrar em cada linha do mapa

| coluna | o que é |
|---|---|
| `ate_onde_foi` | **a escada**, definida na seção seguinte. Cinco degraus, duas direções |
| `por_que_nao_aciona` | **por que o produto não faz**, quando ele não faz. Seção logo abaixo |
| `provado_por` | `ci` / `bancada` / `olho-dela` — só `olho-dela` sustenta *O APARELHO OBEDECEU* e *O JOGO REAGIU* |
| `provado_em` | a data. Sem ela a prova não vence nunca, e prova que não vence vira mito |
| `teste_que_morde` | o nó do pytest que reprova se aquilo quebrar |
| `mordida_provada_em` | quando alguém **de fato** arrancou a cura e viu reprovar |

Tratar **MONTOU** como **funciona** é a mentira mais cara desta casa.

> A coluna se chamava `grau` até 15/08/2026 (D-13, decisão dela). O nome velho
> não é aceito em lugar nenhum: quem o escrever leva `integridade` do portão.

---

## `por_que_nao_aciona` — a coluna que separa dívida de decisão (22/08/2026)

**O problema que ela resolve.** Contado no CSV em 22/08/2026: **41 células**
diziam `de_onde_sei = medido` e `aciona = não` — 20 no cabo, 21 no rádio, e 13
linhas com as duas assim. **São 43 em 07/09/2026** (22 no cabo, 21 no rádio), e
a recontagem, com o que entrou e o que saiu de cada lado, está no cabeçalho de
`tests/unit/test_o_mapa_separa_divida_de_decisao.py` — que é quem tem o
contador. O retrato de 22/08 fica porque a frase abaixo o cita. O `gerar-mapa.py` já as pintava de laranja
(`--color-lacuna`, *"a casa sabe e o produto não faz"*) e já as somava no cartão
de cada controle. **Contar não bastava, e é por isso que nunca houve portão
aqui:** as 41 não são a mesma coisa.

- `identidade.revisao_de_placa@dualsense` não é acionada porque o mapa diz, em
  letras grandes, *"NÃO É A COR"*. Ler aquele nó para nomear jogador daria dois
  "controles iguais" no dia em que ela comprar um par. **Não acionar é o certo.**
- `movimento.imu.perda@dualsense` não é acionada porque a cura está medida e
  nunca foi ligada: o `__le32` de `corpo[11..14]` é contador de reports nos
  **dois** transportes e o produto não o lê em transporte nenhum. **Não acionar
  é falta.**

Um portão que reprovasse as 41 juntas reprovaria a decisão junto com a dívida —
e seria desligado na primeira semana.

**É um par por transporte** (`cabo_por_que_nao_aciona`,
`radio_por_que_nao_aciona`) porque a resposta muda de lado:
`identidade.cor_do_aparelho@dualsense` é decisão nenhuma no cabo (lá o produto
lê a cor do plástico, e a aba Configurações a mostra desde 22/08) e é dívida no
rádio, onde não chega.

| valor | *não aciona — e daí?* |
|---|---|
| *(vazio)* | ninguém respondeu. É o que o portão cobra |
| `divida` | falta fazer, e há quem queira. **É o que o portão limita** |
| `decisao-tomada` | não acionar é a escolha, e ela está certa hoje |
| `nada-a-acionar` | não há feature a acionar: ou o aparelho não oferece, ou a linha é de MEDIÇÃO e `aciona = não` quer dizer *"o fenômeno não aconteceu"*, nunca *"o produto não faz"* |
| `so-ela-decide` | a pergunta existe, ninguém a respondeu, e a resposta é dela |

Retrato de 22/08/2026: **4 dívidas**, 15 decisões, 20 `nada-a-acionar`,
2 `so-ela-decide`.

**A régua** é `tests/unit/test_o_mapa_separa_divida_de_decisao.py`, e ela tem
teto: as dívidas não podem passar de quatro. **Subir o teto é confissão, não
conserto** — pagar uma dívida é baixá-lo no mesmo commit, senão o teto vira
folga e o portão para de morder.

> **Dívida deste desenho, dita na cara.** O domínio desta coluna tem dono
> executável no arquivo de teste, e não no `DOMINIO_POR_SUFIXO` de
> `scripts/check_paridade_transporte.py`, que é o lugar dele — a leva que
> escreveu a coluna não tinha `scripts/` no território. Duas consequências,
> ambas abertas: o portão do mapa **não** confere o domínio desta coluna, e a
> `bancada.py` não a oferece no formulário, de modo que a resposta só entra
> editando o CSV à mão.

---

## A escada de `ate_onde_foi` — cinco degraus, duas direções

**Esta seção é a definição.** O vocabulário executável mora num lugar só —
`scripts/check_paridade_transporte.py`, a tupla `ESCADA` — e é de lá que o
domínio do portão e a legenda do `specs.html` saem. Ninguém redigita a lista:
até 19/08/2026 o portão tinha os degraus num `frozenset` e o gerador os tinha
escritos à mão na legenda, duas listas do mesmo vocabulário.

### Os três degraus da IDA — produto → aparelho

```
MONTOU  →  SAIU NO FIO  →  O APARELHO OBEDECEU
```

| degrau | o critério, e é isto que se tem de OBSERVAR | quem fecha |
|---|---|---|
| `MONTOU` | o byte existe na memória do produto e a suíte o lê. **Nada saiu do processo.** | a suíte, sem aparelho |
| `SAIU NO FIO` | a escrita no nó do transporte não errou e houve resposta do outro lado. Diz que o canal está aberto — **não** diz que o aparelho fez coisa alguma com o que recebeu | a bancada, com o aparelho na mão |
| `O APARELHO OBEDECEU` | alguém **viu** o aparelho fazer o que foi pedido, e gravou o ensaio no caderno com `observado_por = olho-dela` | a mão dela |

### Os dois degraus da VOLTA — aparelho → vpad → JOGO (19/08/2026)

```
…  →  O JOGO RECEBEU  →  O JOGO REAGIU
```

**Por que eles faltavam, e o que isso custou.** Os três degraus de cima são
**todos** da direção de saída, e dá para conferir no dado: `O APARELHO OBEDECEU`
só aparece em linha de saída — alto-falante, rumble, gatilho adaptativo,
lightbar. A volta não tinha uma palavra, e o mapa **admitia o buraco por
escrito**, em duas linhas suas:

- `toque.touchpad`: *"quem ler `radio_aciona = sim` aqui está lendo 'o vpad
  ENTREGA', não 'o jogo REAGE'"*;
- `movimento.giroscopio.jogo`: *"o repasse está íntegro e o jogo não reage: a
  falha, se existir, é DEPOIS do vpad, e ninguém a localizou"*.

Enquanto isso, o mapa inteiro podia ficar verde **enquanto ela não conseguia
jogar** — porque nenhuma célula falava do jogo. O desenho dos dois degraus é o
da `../process/sprints/arquivados/2026-08-19-TRES-PORTOES-01-nao-anda-nem-o-microfone.md`, §7.

| degrau | o critério | quem fecha |
|---|---|---|
| `O JOGO RECEBEU` | o **inode** do nó do nosso vpad aparece em `/proc/<pid>/fd` de um processo da árvore do jogo | um instrumento, de fora |
| `O JOGO REAGIU` | o personagem andou, o gatilho endureceu **dentro** do jogo, o grito entrou | **a mão dela, e mais ninguém** |

#### O critério de `O JOGO RECEBEU`, com as quatro armadilhas já medidas

Este degrau é observável **sem a pessoa**, e é isso que o separa do de cima.
Quatro coisas já foram medidas nesta casa, e todas as quatro derrubam a leitura
ingênua:

1. **A árvore de processos do contêiner do jogo é visível do hospedeiro.** Não é
   preciso entrar em lugar nenhum para enxergar quem abriu o quê.
2. **Quem segura o vpad é o `winedevice`, não o `.exe`.** Procurar pelo nome do
   jogo devolve "ninguém abriu" com o jogo lendo o controle na sua frente.
3. **Identidade de nó é o INODE** (`stat -c %i`), **nunca o caminho.** O minor é
   reciclado: `event22` foi vpad DualSense às 01:40 e vpad Xbox às 01:50. Casar
   por caminho é casar com o número de um nó que já morreu.
4. **Nunca o carimbo de tempo do fd.** Ele marca quando alguém **olhou**, não
   quando abriu, e fica cacheado — medido: dois fds do **mesmo** nó com carimbos
   separados por 1m36s.

E os dois instrumentos que a casa já tem **mentem exatamente no cenário que
interessa**, o que quer dizer que nenhum dos dois fecha este degrau como está:

- `scripts/ensaios/quem_o_jogo_abre.py` conta **handle morto** como fd vivo;
- a sonda de "quem segura o nó" do produto varre **só os PIDs da Steam** — e o
  `winedevice` não está lá.

Quem for fechar `O JOGO RECEBEU` tem de dizer, no ensaio, **qual régua usou** e
como ela escapa dessas quatro. Um instrumento que não declara isso é o defeito
mais caro deste projeto repetido: *o instrumento mente mais que o produto*.

#### O critério de `O JOGO REAGIU`, e por que só a mão dela o fecha

**Não existe instrumento.** Nenhuma régua desta casa lê o estado interno de um
jogo Unreal sob Proton, e nenhuma vai ler. O único sensor deste degrau é ela.

É por isso que o gesto **`PS + R3`** não é conveniência de interface: ele é **o
instrumento de medida** deste degrau. Ele mede sem tirar a mão do controle (um
instrumento que exige Alt+Tab destrói o que mede), custa uma vez por jogo, e o
que fica gravado no perfil não é o que o produto **pediu** e sim o que
**funcionou** — que é a mesma diferença entre `MONTOU` e `O APARELHO OBEDECEU`,
aplicada ao jogo.

O portão cobra isso, e cobra **duro**: `reagiu-sem-olho-dela` é FALHA desde o
primeiro dia, ao contrário da regra irmã `grau-sem-olho-dela`, que avisa. A
diferença é **legado, não princípio** — a regra da lightbar nasceu com células
já escritas por outra régua, e esta nasceu com zero.

### O que NÃO foi feito nesta leva, de propósito

**Nenhuma célula do CSV foi preenchida com os dois degraus novos.** `◌ ninguém
respondeu` é verdade; preencher por analogia destrói o valor do arquivo. Nada
do que a onda de 19/08 construiu — o aviso na lightbar por modo, o gesto
`PS + R3`, a ponte confirmada por jogo — foi visto em **hardware**: foi tudo
dublê. O grau tem de refletir isso, e reflete: o censo do portão imprime
`desses, na direção de ENTRADA (o jogo)` e o número de hoje é **zero**.

---

## Como isto replica entre os três controles

É para isto que a chave canônica existe. `vibracao.rumble.esquerdo` é a mesma
chave nos três; o que muda é a peça e o código evdev:

| | DualSense | Nintendo Pro | 8BitDo SN30 |
|---|---|---|---|
| convergência | `common[2]/[3]` | report `0x10` | report `0x10` |
| envelope cabo | `0x02` | direto | direto |
| envelope rádio | `0x31` + CRC32 | igual ao cabo | igual + rate limiter 60 ms |

Isolado num controle, o outro é **trocar o nome da variável** — que foi a frase
dela. E o que **não** replica precisa estar escrito: a lightbar do DualSense é
`impossível` no 8BitDo, que não tem LED RGB.

---

## O primeiro ensaio completo — 10/08/2026

Registro do que serve de gabarito para os próximos.

**DualSense, Bluetooth confirmado por `HID_ID=0005`, daemon ativo.**

| ensaio | comando | resultado |
|---|---|---|
| linha de base | `--weak 220 --strong 220` | vibrou |
| discrimina | `--weak 0 --strong 200` | **só o esquerdo** |
| discrimina | `--weak 200 --strong 0` | **só o direito** |
| parada | `--weak 0 --strong 0` | parou de fato |

Veredicto do caderno, calculado sozinho: `common[3]` (strong) **é a causa** do
motor esquerdo; `common[2]` (weak), do direito. Grau **O APARELHO OBEDECEU**,
observado por ela.

Achado de brinde: o *"trava sem fim"* da `ONDA-U` **não se reproduziu** — o zero
parou o motor na hora.

E o instrumento se validou: `test rumble` chama o mesmo `rumble_set` do
`ipc_bridge` que a aba Rumble da GUI chama. **O ensaio percorreu o caminho real
do produto**, não um atalho de teste.

### O que ficou aberto nesta feature

Os quatro bits de autorização continuam sem ensaio. Sabemos que o conjunto
inteiro funciona; **não sabemos de quantos o aparelho precisa**. É a poda que
sobra — e o `HAPTICS_SELECT` tem urgência própria: a pesquisa de 10/08 registra
que ele **mata os haptics de áudio do jogo**, e ninguém mediu se ele é preciso
para vibrar.

---

## O segundo gabarito — 11/08/2026, a mesa cheia

Quatro DualSense: **P2 e P3 no cabo, P1 e P4 no rádio**, identificados pelo
padrão de LED de jogador lido no fonte do driver
(`hid-playstation.c:1836-1842`) e conferidos contra a leitura dela — bateram
quatro de quatro, inclusive o transporte. É o gabarito de como o checklist acima
se percorre de verdade, e do que cada passo comprou.

| passo | o que se fez | o que comprou |
|---|---|---|
| B2 | branco nos quatro lightbars, daemon parado | separou dois defeitos que pareciam um |
| C1 | rumble disparado nos quatro na mesma janela (0,0 ms) | os quatro vibram juntos: `combinacao.rumble_simultaneo` deixou de estar muda |
| C2 | falha em par → re-medido sozinho | evitou registrar *"o cabo mata o rádio"*, que era falso |
| D1 | daemon parado → contínuo; religado → morre | a causa é o daemon, com ida e volta |
| D2 | `OUT_REPORT_KEEPALIVE_SEC` de `0,5` para `8,0` | **oito segundos exatos**: é o keepalive, com número |
| D3 | report com bits desligados e bytes trocados | o firmware obedece aos **bytes** — a premissa de uma cura inteira caiu |
| E1 | o tremor troca de lado, em vez de *"quando parou?"* | fechou numa rodada o que duas não fecharam |
| C3 | R2 solto enquanto o L2 endurece | provou que o comando agiu **e** que não vazou de lado |

**Três features fecharam, e cada uma com dono diferente** — a lição de que o
mesmo sintoma pode ter causas distintas, e de que tratá-las como uma só teria
custado o dia:

| feature | parar o daemon | dono do defeito |
|---|---|---|
| rumble por evdev no nó físico | **cura** | o keepalive do produto |
| lightbar no rádio | não muda nada | fora do nosso código — **nomeado em 12/08**: ver o terceiro gabarito |
| gatilho adaptativo | não foi preciso | nenhum: obedeceu de primeira |

### O que ficou aberto nesta sessão — e o que 12/08 fechou

- **O gatilho funciona e ninguém sabe de qual bit ou byte ele depende.**
  Continua aberto.
- A previsão herdada de **D3** (os blocos de gatilho — `common[10..20]` e
  `common[21..31]` — saem em todo report, então o keepalive apagaria o efeito de
  gatilho de um jogo como apagava o rumble) **foi medida em 11/08 e NÃO se
  confirmou**: `gatilho-quem-apaga-nao-e-o-keepalive`, três rodadas, mesmo
  comando, só o tempo mudando — aos 8 s e aos 30 s o L2 seguia duro; aos 120 s
  ele soltou. **O keepalive de 0,5 s está inocentado**: se fosse ele, o efeito
  morreria antes dos 8 s, como o rumble morria. O que reaplica entre 30 s e
  120 s **não foi medido** — candidatos no código são o tick do daemon (30 s,
  fatiado em 2 s) e o `reassert_resolved_outputs`.
- **O lado direito do gatilho tem ensaio próprio desde 12/08**
  (`gatilho-dir-radio-isolado-2221`, isolado por MAC, três R2 soltos de
  testemunha). Os **oito modos do firmware** seguem sem ensaio: só `Rigid` foi
  exercitado, com um único jogo de parâmetros.
- **A lightbar no rádio ganhou nome em 12/08.** Nota datada, porque isto
  substitui duas afirmações erradas que estavam aqui:
  - *"a barra continuou morta por cinco dias e vinte adoções"* era **falso**, e o
    erro foi meu: eu registrei como medição uma frase que só existia em docstring
    (`cli/cmd_lightbar_reset.py:18-20`). A escavação do journal e dos transcritos
    achou a barra **acesa** no rádio dentro daqueles cinco dias, quatro vezes,
    três delas com fala literal dela (ensaios `lightbar-bt-aceso-*`). **O
    docstring seguiu com a frase falsa até 13/08**, quando foi substituído no
    próprio arquivo — porque enquanto ela ficasse lá, quem lesse o código
    reencontraria a afirmação que o caderno já tinha derrubado;
  - *"a suspeita viva é tempo desde a conexão"* era **proxy**. O que a instância
    de conexão carregava era **quem estava com o hidraw aberto no instante da
    probe** — e era o **Steam**, com `/dev/hidraw4..7` em leitura+escrita, medido
    por `readlink` em `/proc/*/fd` e confirmado no `fdinfo`.

---

## O terceiro gabarito — 12/08/2026, a noite em que o réu foi o instrumento

Quatro DualSense de novo, e três frentes fechadas. É o gabarito de **como se
mede quando a suspeita é da própria régua**.

### A lightbar: o suspeito que ninguém tinha olhado em dezesseis dias

| passo | o que se fez | o que comprou |
|---|---|---|
| B2 | mesa **comprovadamente vazia ANTES** da conexão: Steam com 0 processos, daemon parado, **0 descritores de hidraw abertos por qualquer processo** | os três nasceram acesos e os três obedeceram ao verde. Primeiro ensaio em dezesseis dias feito com a mesa limpa **antes** da probe, e não depois |
| D1 | o contraste, 6 minutos antes, com os MESMOS três: Steam fechada **depois** de eles subirem | só **um** dos três obedeceu. Mesmo controle, mesma revisão, resultados opostos — a variável é quem tinha o hidraw na probe |
| — | as três revisões de hardware (`0x0710`, `0x1111`, `0x0711`) estavam representadas | a suspeita de revisão de hardware cai **com prova**, não por argumento |
| D2 | `btmon`, duas capturas de 45 s, uma por braço | **98** pacotes de saída na probe suja contra **6** na limpa (dois por controle, que é o que o driver manda sozinho) — dezesseis vezes mais escrita, e o resultado inverso |
| D2 | os **timestamps** desses pacotes | a Steam não disputa sempre: ela escreve em **duas rajadas** (t+0→3 s e t+15→18 s) e depois **cala**. A pergunta foi dela: *"se medimos quando a steam pinta o lightbar então sabemos quando sobrescrever, não?"* |

**Limite dito em voz alta, porque não foi medido:** eu contei os pacotes,
**não decodifiquei** o conteúdo deles. Não sei que report a Steam manda nem se
algum pede a barra apagada.

**A cura que saiu disso** tem forma de ensaio, não de palpite: o gatilho **arma**
a cada conexão mas só **dispara quando o rádio sossega**, e então escreve em
**todos** — a primeira versão escrevia 1,5 s depois de *cada* conexão e só o
último controle sobrevivia, porque a rajada da Steam é **por evento**, não por
controle.

### O padrão que apareceu três vezes no mesmo dia

**O produto decide durante a sequência, em vez de esperar ela sossegar.**
Lightbar (a cor é pintada no priming, dentro da rajada), co-op (o `IGNORE` foi
avaliado três vezes durante a subida dos vpads e **nunca** depois que a cobertura
ficou completa — o quarto vpad ficou pronto **onze segundos** depois do
primeiro), e o gatilho da cor v1. Três defeitos de tempo, **mesma forma de
cura**.

Quando você achar o quarto, ele provavelmente é este.

### E o que o journal do SISTEMA respondeu que o da unit não respondia

Eu atribuí ao `systemd-logind` a retirada da permissão do nó, com o argumento de
que device virtual não tem seat. **Errado.** Quem esconde o nó é o **broker de
hidraw do próprio produto**, de propósito, para impedir que jogos e a Steam mexam
direto no controle — e ele o faz 14.105 vezes em sete dias na máquina dela:

```bash
journalctl --user -b | grep hidraw       # o journal da unit
journalctl -b | grep hidraw              # o do SISTEMA — foi ESTE que respondeu
#   hefesto-dualsense4unix[...]: hidraw_broker_hidden node=/dev/hidraw4
```

**O que isto decide, e vale como regra:** **antes de culpar o sistema, procure o
produto no journal do SISTEMA.** Duas horas teriam sido poupadas por um
`journalctl | grep hidraw`.

**Consequência de método:** a permissão nunca foi defeito — era o produto
trabalhando. **Quem escreve por hidraw tem de ser o DAEMON, pelo handle que o
broker abriu.** Um processo de fora abrindo `/dev/hidrawN` direto pode nunca
ganhar a disputa, porque **o broker age depois do udev** — e foi por isso que uma
regra udev escrita para "vencer" a disputa não venceu, e foi removida em vez de
ficar como peça sem defeito que a justifique.
