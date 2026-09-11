# TOUCHPAD-NO-3DS-01 — o preço do `ignore`, medido na tela de baixo

**Árvore:** `hefesto-voo/TOUCHPAD-NO-3DS-01-opus` · branch `voo/TOUCHPAD-NO-3DS-01-opus`
· nasceu de `dev` em `315d912b`, o mesmo `git rev-parse --short dev` da hora.

**Bancada:** LIVRE. Reservada e liberada em cada leva de medição
(`scripts/bancada.sh exigir` com rc=0 antes de cada reserva). **Não esperei por
aparelho** — mas a mesa tinha UM DualSense **no cabo**, não no rádio, e é isso
que limita o alcance do que está escrito aqui.

---

## O que mudou

**Um arquivo, o que a sprint declara em `cria:`:**
`scripts/ensaios/o_touchpad_chega_na_tela_de_baixo.py`.

Ele mede em **quatro degraus** e fecha três. O quarto é dela.

### Degrau 0 — o recurso está LIGADO? (o degrau que a sprint não tinha)

A sprint pergunta se o `IGNORE_DEVICES` apaga o recurso *"Map touchpads on
controllers like the DualSense directly to touch"*. **Medido: o recurso está
DESLIGADO na configuração, e nunca foi tocado.**

```
profiles\1  use_touchpad=false                <-- DESLIGADO
            controller_touch_device=(vazio — nenhum controle atado)
            touch_device=engine:emu_window
```

As três linhas vêm do `qt-config.ini` que o próprio emulador escreve, e todas
carregam a linha-irmã `\default=true`: **é o padrão de fábrica, ninguém mexeu.**

Isto muda a acusação inteira. Com o recurso desligado, o dedo no touchpad não
faria nada **mesmo que o descritor estivesse aberto** — e medir o degrau 3 sem
dizer isso produziria a conclusão *"o `IGNORE_DEVICES` matou o touchpad"* sobre
um recurso que ninguém ligou. É a família de defeito desta casa: *o instrumento
respondendo sobre outra coisa que não o produto*. Por isso o degrau 0 nasceu, e
por isso ele vem **antes** dos outros na saída.

Confirmado no binário do emulador (`strings` do executável extraído do
AppImage, sem executá-lo): a frase da interface existe, o rótulo do campo é
«Use controller touchpad», a classe que o alimenta é
`InputCommon::SDL::Polling::SDLTouchpadPoller`, e os eventos são
`SDL_CONTROLLERTOUCHPADDOWN/UP/MOTION`. **O que NÃO confirmei está no terceiro
cabeçalho.**

### Degrau 1 — o nó existe (MEDIDO, e existe)

Dois nós de touchpad na mesa, resolvidos por identidade:

```
nó        papel      de quem          transporte             ponteiro
event27   touchpad   vpad do Hefesto  vpad (sem transporte)  mouse3
event256  touchpad   aparelho físico  cabo                   mouse4
```

**Os números não são endereço.** Entre a primeira e a última execução desta
sessão os nós andaram (`event23` virou `event27`, um segundo vpad apareceu e
sumiu) — por isso o instrumento resolve tudo do sysfs a cada chamada e usa a
régua única `scripts/identidade_do_vpad.py`, nunca o número.

### Degrau 2 — o emulador ABRE o nó? (MEDIDO, e NÃO abre)

**Com a cura** (o atalho dela, que lê o `default.env` vivo):

```
janelas na tela ........... 3  ·  janela de verdade? SIM   (933x855)
nós de entrada abertos:
    event25  principal  vpad do Hefesto   DualSense … (Hefesto P1)
    event26  movimento  vpad do Hefesto   DualSense … (Hefesto P1) Motion Sensors
hidraw abertos ............ NENHUM
```

O touchpad **não** está lá. E `hidraw` **zero** — que é por onde a API de
touchpad do SDL seria alimentada. O degrau 2 está VERMELHO, como a sprint
previu, e agora com número.

**Sem a cura** (a mordida — o executável cru, sem `SDL_GAMECONTROLLER_IGNORE_DEVICES`):

```
janelas na tela ........... 1  ·  janela de verdade? NÃO   (só a de 3x3 do Qt)
>> TRAVOU — a janela do emulador NUNCA NASCEU dentro do teto.
   tid=…  AppRun.wrapped  futex_do_wait  <-- a PRINCIPAL, esperando por outra
nós de entrada abertos:
    event25  principal  vpad do Hefesto
    event26  movimento  vpad do Hefesto
    event30  principal  aparelho físico  cabo   <-- a diferença
hidraw abertos ............ NENHUM
```

**A única diferença entre as duas rodadas é o nó do DualSense FÍSICO.** Com a
cura o emulador não o toca e abre; sem a cura ele o abre e trava. Medido três
vezes, sempre igual.

### Degrau 3 — não medido, e o instrumento se recusa a concluir

`--o-gesto` imprime o que ela tem de fazer. O instrumento diz, em toda
execução, que descritor fechado é **evidência forte, não prova**.

---

## Qual mordida prova

**Quatro mordidas, e a quarta é contra o próprio instrumento.**

**1. A régua REPROVA o degrau 2 hoje** — é o que a §5 da sprint exige.

```
$ … --abrir --exigir-touchpad
RESUMO: o touchpad NÃO chegou ao emulador: nem nó de touchpad, nem `hidraw` nenhum
`--exigir-touchpad`: o degrau 2 está VERMELHO. rc=1.
rc=1
```

**2. E ela sabe dizer SIM** — sem isto, «reprovou» não vale nada: uma régua que
só sabe reprovar estaria medindo *"o processo existe"*, que é exatamente o que a
§5 proíbe. Com um processo qualquer segurando o nó de touchpad do vpad:

```
$ … --padrao "dev/input/event27" --exigir-touchpad
    event27  touchpad  vpad do Hefesto  DualSense … (Hefesto P1) Touchpad
RESUMO: o nó de TOUCHPAD chegou ao emulador
rc=0
```

**3. A cura arrancada, e o ensaio ACUSA em vez de travar junto.** É a segunda
exigência da §5, e é a que mais engana: o alvo desta medição é um processo cujo
modo de falha É TRAVAR. Sem teto de tempo, o ensaio esperaria para sempre e
nunca reprovaria. Com teto: `TRAVOU`, a assinatura das threads, e `rc=1` em 45 s.

**4. A régua da PILHA mentiu, e foi arrancada.** A primeira versão chamava
`eu-stack` e imprimia *"pilha lida, e NENHUM quadro cita HID, SDL ou udev"*.
Ela nunca leu pilha nenhuma: com `kernel.yama.ptrace_scope=1` o `eu-stack` sai
com `rc=2` e **ainda imprime duas linhas de cabeçalho**, e o guarda-chuva era
`rc != 0 and not stdout` — a saída não vazia fazia a recusa passar por leitura.
*Uma afirmação sobre o emulador construída sobre uma recusa do kernel.*

A cura foi validada **contra uma resposta que eu já conhecia** (um `sleep` meu,
onde o `eu-stack` recusa do mesmo jeito):

```
motivo : NÃO LIDA — eu-stack: dwfl_thread_getframes tid …: Operação não permitida
         · kernel.yama.ptrace_scope=1: só o processo PAI pode anexar, e este
         instrumento não eleva privilégio nenhum
OK — a régua distingue RECUSA de leitura vazia
```

**Portões:** `bash scripts/portoes.sh` — o estado está no fim deste arquivo, e
**dois vermelhos vieram de `dev`**, não daqui.

---

## O que NÃO verifiquei

- **O degrau 3.** É dela: a ROM é dela e o olho é dela. Nada aqui afirma que o
  toque chega ou não chega à tela de baixo — só que o descritor não está aberto.
- **O RÁDIO.** A mesa tinha UM DualSense, **no cabo**, o tempo todo. A sprint
  nasceu de um travamento medido com o controle **por rádio**, e esse arranjo eu
  não tive. Tudo o que está escrito aqui sobre o travamento vale para o CABO.
- **Se `use_touchpad` é exatamente aquele campo da tela.** O nome da chave sai
  do arquivo que o emulador escreve e o rótulo «Use controller touchpad» sai do
  binário dele, mas eu **não** cliquei o campo para ver a chave mudar — a
  configuração é dela e este instrumento não escreve nela. É INFERÊNCIA
  DECLARADA, não medição.
- **Se o SDL entregaria o touchpad caso abrisse o `hidraw` do vpad.** O vpad se
  apresenta como `054c:0df2` (DualSense Edge), que o driver HIDAPI do SDL
  conhece, e o `hidraw` dele é acessível à usuária. Em nenhuma das rodadas o
  emulador o abriu — mas **por que** ele não abre eu não medi.
- **Se o emulador LÊ dado dos nós que abriu.** Ele abre o principal e o de
  movimento do vpad; ter o descritor não é receber evento, e eu não medi
  evento.
- **A mesa de quatro.** Um controle só, um transporte só.
- **O `HIDAPI Rumble`.** O censo por nome não responde: 21 das 41 threads
  herdam o nome do processo, e a pilha que decidiria está bloqueada pelo
  `ptrace_scope`. O instrumento diz isso na cara em vez de concluir.

---

## O que sobrou para o próximo

**1. As células do mapa, para a SPECS-A-PROCEDENCIA-01 escrever** (não toquei
no `mapa-controles.csv`, que a sprint põe em `nao_toca:`):

| chave | transporte | até onde foi | o que vi |
| --- | --- | --- | --- |
| `toque.touchpad@dualsense` | vpad (sem transporte); o físico na mesa estava no **cabo** | **MONTOU** | o nó `… Touchpad` do vpad existe e abre (`event27`, com `mouse3`); um app de terceiro real — o emulador de 3DS — **NÃO** o abre, nem por evdev nem por `hidraw`, com a cura ou sem ela |
| `movimento.giroscopio.jogo@dualsense` | vpad; físico no **cabo** | **MONTOU** | o emulador ABRE o nó `… Motion Sensors` do vpad (`event26`) já na subida, sem ROM carregada. Que ele LEIA evento dali não foi medido |

**2. A linha da sprint que CAIU, e ela é do §0.** A sprint diz:

> `fd 53 -> /dev/hidraw7 ← o DualSense FÍSICO, por rádio`

Hoje `hidraw7` **não existe**, e o número que a frase carrega não é endereço de
nada: nas duas leituras desta sessão o `hidraw` de índice mais alto era um
**vpad** (`HID_PHYS=hefesto-vpad`), não um físico. Mais forte que isso: **com o
daemon vivo, o `hidraw` do DualSense físico é `0600 root:root`** — o broker o
esconde — e nenhum processo da usuária consegue abri-lo. Nas três rodadas sem a
cura o emulador travou com **ZERO `hidraw` aberto**.

Isso não derruba a cura (ela funciona: com a variável o emulador abre, sem ela
não), mas derruba a **explicação**: no cabo, hoje, o que separa abrir de travar
é o emulador tocar o **evdev** do físico — não o `hidraw` dele. Quem for
escrever a causa mede de novo, com o controle **no rádio**, que é o arranjo do
achado original.

**3. A decisão dela, e é a §4 da sprint** — qual das três saídas vale. Nada
disso é meu: o degrau 3 ainda não foi medido, e a §4 diz com todas as letras
que a escolha é dela, depois da medição. O que a medição de hoje acrescenta à
pergunta é que **existe um quarto caminho barato**: o nó de touchpad do vpad
publica um `mouseN` (`event27` → `mouse3`), isto é, o kernel já o oferece como
ponteiro — e o emulador tem `touch_device=engine:emu_window`, que é toque pelo
ponteiro na janela. Ninguém mediu se um encosta no outro; é sprint nova, e
nasce daqui.

**4. Nada a integrar em `src/`.** Esta sprint não toca produto: ela troca uma
ressalva escrita por uma medição.

---

**5. ESTA ÁRVORE NASCEU VERMELHA EM DOIS PORTÕES, e a culpa não é desta
sprint.** Os dois portões de MAC reprovam um arquivo que veio pronto no commit
base:

```
mac-por-oui     VERMELHO  tests/unit/test_o_no_do_radio_conta_como_placa.py:26 e :28
mac-de-fixture  VERMELHO  os mesmos dois tokens
```

A prova de que é herdado, e ela é do git, não minha:

```
$ git cat-file -e 315d912b:tests/unit/test_o_no_do_radio_conta_como_placa.py  → existe
$ git log --oneline 315d912b..HEAD                                            → vazio
$ git diff --stat 315d912b HEAD -- tests/                                     → vazio
```

**O que os dois tokens são, medido:** cada um é um **OUI real** da bancada dela
colado a um **sufixo sintético da casa** (`…02fe00` e `…aabbcc`). Identidade de
unidade não vaza — o que vaza é a FORMA: a convenção desta casa zera os octetos
**4 e 5**, e ali eles valem `02:fe` e `aa:bb`. É violação de forma, não de
segredo, e é exatamente o ponto cego que o `CLAUDE.md` descreve: máscara
aplicada nos octetos errados.

**Não editei**, e é a regra: o arquivo não está na minha `posse:`, e ele é a
prova da cura de som que entrou em `dev` hoje (`315d912b`). Editar aqui viraria
conflito de merge com quem o escreveu.

**`dev` ESTÁ VERMELHO AGORA**, não só esta árvore: o mesmo arquivo, com os
mesmos dois tokens, está no tip `21a1853e`. Quem for costurar precisa saber
disso antes de rodar os portões e achar que quebrou alguma coisa.

## A saída dos portões

```
portões — árvore /mnt/Apate/Desenvolvimento/hefesto-voo/TOUCHPAD-NO-3DS-01-opus
         python  …/.venv/bin/python
         camadas rapido completo
REPROVOU: 2 vermelho(s) de 56 -> mac-por-oui mac-de-fixture
```

Os 54 restantes, verdes — inclusive os que olham este trabalho:
`acentuacao`, `ruff`, `mypy`, `anonimato`, `saida-de-agente`,
`citacoes-no-codigo`, `referencias-docs`, `a-tela-dela`,
`o-instrumento-e-a-tela`, `casa-sabe`.

**A camada rápida sozinha:** `TODOS VERDES — 38 portões`.
