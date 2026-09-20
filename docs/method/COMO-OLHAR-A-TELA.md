# Como olhar a tela deste projeto

**Leia isto antes de tentar fotografar, medir ou entender a interface.**

Pedido dela, literal, em 01/08/2026:

> *"se tiver outro conhecimento desatualizado no repositório, ou que você usou
> e não funcionou e você descobriu a forma certa, isso deve ser materializado
> como conhecimento perpétuo pra evitar perdermos tempo reaprendendo sempre sem
> necessidade."*

Este arquivo é isso. Cada linha aqui custou tempo de alguém.

---

## ANTES DE TUDO: ELA TEM UMA TELA SÓ, E A JANELA NÃO NASCE NELA

**Regra dela, 04/09/2026, e ela é sobre o serviço dela, não sobre estética.**
A sessão do COSMIC tem **três áreas de trabalho alfinetadas, nesta ordem**: a
PRIMEIRA é DELA e ela está nela **agora**, trabalhando; a SEGUNDA é de quem
estiver trabalhando aqui. Uma janela que nasce na dela rouba o foco, e o mouse
dela passa a brigar com o clique de quem mede — os dois se quebram.

**A ORDEM DE PREFERÊNCIA, e ela é dura:**

1. **Não abrir janela nenhuma.** É quase sempre possível, e é o que as levas de
   03/09 e 04/09 fizeram: `Gtk.OffscreenWindow`, `--oculta`, Playwright em
   `headless`, `interface/olhar.py`. **Se você conseguir medir sem janela, essa
   é a resposta certa** — não há área de trabalho a errar.
2. **Se a janela for inevitável** (o app de validação, um Playwright que precisa
   de compositor, um jogo para o ensaio do sensor), ela nasce na SEGUNDA área.
   O auxiliar que a estaciona é da MÁQUINA DELA, não deste repositório: ele vive
   em `~/.config/zsh/scripts/` e os quatro gestos dele — estacionar a janela que
   nascer, abrir um navegador dedicado, mover uma janela já aberta e
   diagnosticar — estão escritos nas instruções da máquina, que são o dono
   dessa página.

   **POR QUE O NOME DELE NÃO ESTÁ AQUI, e isto é regra e não descuido:** este
   arquivo é versionado desde 20/09/2026, e o que é versionado é publicado. O
   nome do auxiliar carrega o de um fornecedor, e o `check_anonymity.sh`
   reprova fornecedor em arquivo rastreado. Duplicar aqui a página da máquina
   dela também quebraria a regra da casa de não ter dois donos do mesmo texto.

3. **Se o auxiliar RECUSAR** estacionar, a resposta é **aceitar a recusa e
   dizer na entrega**. Não force a variável de ambiente que ele oferece: ela
   pode jogar a janela em cima dela, que é exatamente o que a regra existe para
   impedir.

**O que NUNCA se faz, por conta própria:** os gestos que TROCAM a área de
trabalho visível. Os dois trocam o que ela está vendo. Só quando ela pedir para
ver.

**E a irmã desta regra, que já custou uma sessão inteira:** para matar um
processo, **PID conferido com `ps -o pid,ppid,cmd`, nunca padrão de nome.** Em
04/09/2026 um `pkill -f 'cosmic-comp'` casou com o compositor **dela**, a tela
caiu e a conversa morreu — ela teve de restaurá-la.

---

## A regra, em uma linha

```bash
src/hefesto_dualsense4unix/interface/olhar.py --todas --publicado --doc
```

Uma execução. Nenhum clique, nenhuma janela aberta, nenhuma tela em foco. Sai um
PNG por aba em `docs/usage/assets/aba-NN-*.png`, recortado na moldura da janela
(1180x777) — que são as imagens do `README.md` e do
[`AS-DEZ-ABAS`](../usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md).

**ESTA SEÇÃO MUDOU DE COMANDO EM 06/09/2026 (`GTK-3`).** Aqui estava
`scripts/gui-captura/retratar_abas.py`, que montava o `gui/main.glade` numa
`Gtk.OffscreenWindow` e fotografava as ONZE abas da JANELA. A janela foi
aposentada por decisão dela (`D-0609-GTK-LEVA-INTEIRA`) e o estúdio inteiro —
os cinco arquivos de `scripts/gui-captura/` — saiu com ela. **O que ela abre
hoje tem DEZ páginas HTML**, e o retratista delas mora dentro do pacote porque
depende só do Chrome; o antigo importava GTK na primeira linha.

Sem `--doc` ele grava em `/tmp` e não toca no repositório:

```bash
src/hefesto_dualsense4unix/interface/olhar.py --todas --publicado
src/hefesto_dualsense4unix/interface/olhar.py 05-vibracao.html --publicado
```

`--publicado` fotografa `interface/paginas/`, **o que o produto renderiza**. Sem
ele, o alvo é a bancada, que é onde o desenho é concluído — e a diferença entre
os dois é o assunto do `mockup/LEIA-PRIMEIRO.md`.

---

## Os quatro instrumentos de tela desta casa, e qual usar

| instrumento | o que faz | quando |
|---|---|---|
| **`src/hefesto_dualsense4unix/interface/olhar.py`** | fotografa as dez páginas num Chrome headless e mede a moldura | **rotina, sempre** |
| **`src/hefesto_dualsense4unix/interface/hefesto_vivo.py`** | o PILOTO: a janela GTK com o `WebView` e o daemon vivo dentro. `--oculta` desvia para um Xvfb; `--foto`, `--segundos` e `--prova-clique` dirigem por dentro | quando a pergunta é *"o produto FAZ?"* — é o único que roda o motor |
| `src/hefesto_dualsense4unix/interface/ver.py` | o desenho aprovado dentro da janela GTK, sem dado nenhum | quando a pergunta é sobre o DESENHO, e ligar dado atrapalharia |
| `src/hefesto_dualsense4unix/gui/ponte_da_tela.py` | a ponte JS: clica, lê o DOM e mede geometria por `run_javascript` | dentro do piloto, para validar sem tocar no mouse dela |

Esta tabela tem portão: `tests/unit/test_a_tabela_dos_scripts_de_tela.py` confere
que todo caminho citado aqui EXISTE, que o retratista está nomeado e que o
número do título bate com o das linhas. Ela já envelheceu calada uma vez —
dizia "os três scripts" com cinco no disco.

### O Playwright não alcança o WebKitGTK

O `olhar.py` dirige as páginas num Chrome headless e serve para medir layout,
`:hover` e fotografar o DESENHO. **Ele não alcança o `WebKit2.WebView`** — o
motor que ela usa de verdade. Quem prova o produto é o piloto, com a ponte JS e
o daemon vivo. São dois instrumentos com alvos diferentes, e o segundo é o que
fecha uma entrega.

### E a régua tem de viver no TEMPO

Uma régua que roda o tique uma vez mede um INSTANTE, não um comportamento: em
29/08/2026 uma leva introduziu uma regressão que só aparecia aos **181
segundos**, com 67 testes verdes. O `--segundos` do piloto existe para isso.

### O que se perdeu com o estúdio antigo, e está escrito porque se perdeu

O `capturar_verificado.sh` fotografava a tela **de verdade**, percorrendo as abas
por teclado e conferindo onde parou — a prova final para *"ficou bonito?"*. Ele
precisava da janela **aberta, maximizada e em foco**, e o COSMIC recusou
maximizar por atalho, por duplo clique e por F11 nesta máquina; por isso nunca
foi rotina. **A interface nova não tem equivalente hoje**, e quem quiser essa
prova abre o piloto e pede o olho dela (PROVA-DE-TELA-01).

O `retratar_dialogos.py` fotografava os **diálogos** de confirmação, que nascem
por cima e vivem um segundo. A interface nova não tem diálogo GTK modal: o que
ela usa é o canal de recado das dez páginas, que a foto normal alcança.

---

## O que a foto offscreen NÃO prova

Seja honesto sobre isto ao usá-la:

- **não passa pelo compositor** — não há sombra, canto arredondado nem o tema de
  janela do COSMIC;
- **a foto recorta na moldura `.janela`** e não mostra o cromo da janela GTK que
  a envolve: a barra de título, os botões de fechar/maximizar e o ícone da dock
  ficam **fora do recorte**. Quem for medir aquilo abre o piloto;
- **não prova que a janela abre** — prova o que tem dentro dela;
- **não vê o que o `<script>` escreve depois de um clique.** A foto é do estado
  INICIAL da página; o que nasce do gesto só aparece com o piloto ou com uma
  régua que clica (`tests/unit/test_a_palavra_de_tela_da_interface_nova.py` é o
  molde);
- **não substitui o olho dela.** A regra da casa
  ([PROVA-DE-TELA-01](../process/sprints/arquivados/2026-07-27-PROVA-DE-TELA-01-dez-minutos-de-olho-antes-de-qualquer-leva.md))
  continua valendo: interface só fecha com ela olhando.

Para *"o que tem nesta aba, e onde?"*, a foto é fiel. É para isso que serve.

---

## Armadilhas de GTK que este projeto já pagou

Estas não são sobre foto — são sobre **medir** a interface, e cada uma custou
horas.

### A foto pega a animação no meio, e o `git status` mente

Registrado em **14/08/2026**. **GRAU: MEDIDO.**

`readme_inicio.png` saía **diferente a cada execução** do script oficial —
~3 mil pixels de 2,07 M, delta 1 a 2 por canal, sempre nas bordas dos dois
botões segmentados **selecionados**. Quem rodasse o script antes de commitar,
como o `CLAUDE.md` manda, via o `git status` sujar sem nada ter mudado na tela.

A causa não é "ruído de gradiente": é **transição de CSS**. Um `GtkRadioButton`
recém-marcado anima a mudança para `:checked` (o tema do sistema traz
`transition` em `button:checked`), e a foto sai no meio da animação — o ponto
dela depende do **relógio**, não do desenho. A aba Início era a única afetada
porque é a **primeira** fotografada: as outras nove tinham tempo de assentar
enquanto o laço percorria a tira.

**A cura, e ela vale para qualquer instrumento de captura desta casa:**

```python
Gtk.Settings.get_default().set_property("gtk-enable-animations", False)
```

Com isso o GTK pinta o estado **final** na hora. Medido: as outras nove fotos
saem byte a byte idênticas com ou sem a chave, e duas execuções seguidas
passaram a sair idênticas nas dez.

**A armadilha irmã, que a mesma medição encontrou:** `_assentar()` drena
eventos **pendentes** e não deixa o relógio andar. Isso basta para layout, mas
**não** para um redimensionamento de janela offscreen — a superfície só é
recriada no tique do frame clock, que é temporizador. Pedindo 2055 px de altura
e fotografando logo depois, o pixbuf saía com os 1080 **antigos**, sem erro
nenhum. Quem precisa de resize espera tempo de parede
(`_esperar_o_redimensionamento`) e **confere a altura do pixbuf** antes de
acreditar na foto.

### Sob Xvfb não há gerenciador de janelas

Uma `Gtk.Window` de verdade **nunca é mapeada**, e o filho fica **1x1 para
sempre**, por mais que o laço de eventos rode. O `get_surface()` que destrava
uma `OffscreenWindow` não existe ali.

**Consequência:** todo teste de layout deve usar `Gtk.OffscreenWindow`, ou dar
o tamanho à janela por conta própria. Isso reprovou o CI de uma tag inteira.

### Widget sem alocação mede 1x1 — e o teste passa com qualquer desenho

Medir antes de o laço assentar dá 1x1, e uma asserção sobre 1x1 passa com
qualquer coisa. **Drene o laço mais de uma vez** antes de medir.

### `set_size_request` é MÍNIMO, nunca máximo

No GTK3 não existe "largura máxima" por pedido. Um `width-request` sozinho não
segura nada — ele precisa de `halign=start` para virar teto de fato. E com
`halign=center` ele **trava** o widget no número exato.

### `max-width-chars` sozinho não encolhe label nenhum

Ele limita a largura **natural** (o que o widget *pede*); o pai continua livre
para alocar mais, e um label esticado quebra na largura que **recebeu**. Precisa
de `halign=start` junto. Medido em 01/08: sem isso, um parágrafo de 1869px ficou
intacto.

### Uma célula de `GtkGrid` nunca é mais larga que suas colunas

Pedir largura inteira de dentro de uma grade faz **todas** as colunas
expandirem junto. Quem precisa da largura toda sai da grade, para uma caixa
própria.

### `GtkProgressBar` desenha o próprio texto CENTRADO

Numa barra larga, o número fica a centenas de pixels de cada borda. Se a barra
precisa ser larga, o texto sai dela e vira um rótulo ao lado.

### `column_homogeneous` dá metades IGUAIS

Se as duas metades reais do desenho não forem iguais, as divisórias não batem.
Para amarrar larguras entre linhas diferentes, o instrumento é `Gtk.SizeGroup`.

### O quadrado vermelho ao lado dos interruptores

Todo `GtkSwitch` do GTK3 tem dois nós `image` internos que pedem ícones que
**nenhum tema desta máquina resolve** — e o GTK pinta o "imagem faltando" do
tema ativo. `color: transparent`, `-gtk-icon-source: none` e `opacity: 0`
**não** funcionam (o fallback é ícone colorido, não simbólico). O que cura:
`-gtk-icon-transform: scale(0)`.

---

## Armadilhas de medição fora do GTK

### Medir contra a biblioteca errada produz alarme convincente e falso

Em 01/08 mediu-se o gamepad virtual contra a `libSDL2` **do Ubuntu** e
concluiu-se que ele não entregava quase nada ao jogo. A **SDL3 que a Steam
distribui** o enumera por completo. Nenhum jogo da Steam carrega a do sistema.

**Regra:** todo instrumento tem de declarar **qual biblioteca** está usando —
caminho absoluto e versão — no cabeçalho da saída.

### Struct incompleta em `ctypes` corrompe o resultado SEM erro

Faltavam três campos numa `SDL_hid_device_info`; o ponteiro de lista deslocou e
a enumeração saiu errada **em silêncio**, com aparência legítima. Confira campo
a campo contra o header da versão certa.

### O instrumento pode estar brigando com o produto

`hefesto-dualsense4unix test trigger --raw` abre um **segundo** controlador e
disputa o hidraw com o daemon, que sobrescreve em ≤ 0,5 s — **e imprime
"trigger aplicado" mesmo assim**. Testes de gatilho vão pela GUI/IPC, ou com o
daemon parado.

### Nome de recurso do kernel é POSIÇÃO, nunca semântica de produto

Registrado em **07/08/2026**, do commit `cf176d6`. **GRAU: MEDIDO.**

Em 06/08 às 22h40 a medição dos player-LEDs foi lida assim: cada nó aceso em
`/sys/class/leds/*:player-N` foi tomado como *"este aparelho é o jogador N"*.
É falso para o DualSense. O número do jogador é o **padrão das cinco lâmpadas**
(`core/led_control.py`, a tabela `_PLAYER_LED_PATTERNS`): jogador 1 é **só a do
meio**, que o kernel chama de `player-3`; jogador 3 são as duas pontas mais o
meio.

O que a leitura errada produziu foi um achado inteiro que **nunca existiu**
(*"DOIS aparelhos no MESMO jogador 3"*), commitado em dois lugares e citado em
duas mensagens de commit. Não houve colisão naquela mesa: o vpad acendia o
padrão do 1 e o DualSense físico o do 3.

**Quem leu certo foi ela, de olho, sem instrumento** — *"o dualsense branco
dessa vez conectado como player 3"*. A pessoa que USA o produto leu o plástico
melhor do que quem o escreve leu o `sysfs`.

**A regra, e ela é da mesma família do "medir contra a biblioteca errada":**
nome de recurso do kernel descreve **onde a lâmpada fica**, não o que ela
significa no produto. Antes de usar um nome de `sysfs` como valor de domínio,
confira contra a tabela do produto que traduz um no outro — aqui,
`core/led_control.py`. Se não existir essa tabela, o nome não é dado: é
coincidência.

**O que salvou a casa foi um teste que já sabia disso:**
`tests/unit/test_lugar_a_mesa_numero_de_jogador_nao_se_repete.py` compara o
**padrão**, nunca o nome do nó — era o único artefato da leva com a distinção
escrita, e por isso não herdou o erro.

### Instrumento que consulta o `journal` declara o locale, ou mente calado

Registrado em **07/08/2026**, do commit `6e04c57`. **GRAU: MEDIDO.**

Um medidor formatava a janela de tempo com a data **em português** e a passava
para o `journalctl --since`. O `journalctl` não entende `ago`, `set`, `dez` — e
não reclama: ele devolve **zero linha**, que é indistinguível de "não houve
nenhum evento". Foi daí que saiu a afirmação falsa dita **a ela, ao vivo**, de
que *"três controles custam 40 perdas por minuto e dois custam zero"*.

Refeita a medição com instrumento validado, o número **inverte a conclusão**:
quatro controles estáveis custam **14,6** perdas de IMU por minuto, e **três**
controles com o 8BitDo tentando voltar custam **48,4**. Não é a quantidade de
controles; é o que não consegue entrar. A retratação está na
[CONECTA-E-DESLIGA-01](../process/sprints/arquivados/2026-08-07-CONECTA-E-DESLIGA-01-a-regressao-que-ela-relatou-e-a-suspeita-que-recai-sobre-nos.md).

**A regra tem duas metades, e a segunda é a que faltava:**

1. **declare o locale.** `LC_ALL=C` no instrumento, ou monte a data com
   `strftime("%Y-%m-%d %H:%M:%S")` — nunca com nome de mês;
2. **prove a janela contra contagem direta antes de acreditar nela.** Foi assim
   que o medidor das 20h13 se validou: a contagem do instrumento bateu com a
   contagem à mão do mesmo intervalo, **53 = 53**. Sem essa conferência, um
   instrumento quebrado e uma janela limpa dão a mesma saída.

Vale a mesma advertência de data completa da armadilha seguinte: `--since
"21:34:39"` **sem data** também devolve zero em qualquer janela.

Esta foi a **segunda** vez no mesmo dia em que o instrumento enganou quem media. <!-- noqa-acento: verbo medir, imperfeito -->
A primeira é a armadilha logo acima, do nome de `sysfs`.

### O medidor pode estar INERTE — e inerte é indistinguível de "não houve nada"

Esta é a irmã da anterior, e é pior, porque a anterior mente e esta **cala**.

**O install deste projeto é *editable*** (o `.pth` da venv aponta para o `src/`
do repositório). Consequência que vale para **todo** código de daemon, sem
exceção: **o que você escreveu hoje só entra em vigor no PRÓXIMO start do
processo**. Um daemon vivo mais velho que a sua cura não a executa, não falha e
não avisa — ele simplesmente não a tem dentro dele.

Quando a cura é um **medidor**, o resultado é o pior que existe: a medição
devolve **zero**, e zero é exatamente o que uma medição bem-sucedida devolveria
se o defeito não tivesse acontecido. **Silêncio de instrumento morto é
indistinguível de ausência de defeito.**

A casa já pagou por isso **duas vezes**, com custo medido:

- **05-06/08/2026** — o daemon vivo era o PID 1670, de 04/08 23:39:46; as curas
  de perfil eram de 05/08 00:38:41. Ela trocava de perfil e a cor/gatilho/rumble
  não entravam. **Era o defeito já curado no disco**, e ela estava olhando para o
  produto de anteontem
  ([PERFIL-REESCRITO-NA-PARTIDA-01](../process/sprints/arquivados/2026-08-05-PERFIL-REESCRITO-NA-PARTIDA-01-o-perfil-dela-era-reescrito-sozinho-no-meio-da-partida.md),
  linhas 43-47);
- **07/08/2026** — o diário da bateria (474 linhas, 49 testes verdes) ficou
  **5h49m** no disco sem escrever **uma linha** no journal, com o controle dela
  conectado o tempo todo. Uma noite de medição teria produzido nada, em silêncio.
  Reiniciado o serviço às 21:34:39 (autorização dela), a primeira amostra saiu
  35 segundos depois.

**A regra: antes de acreditar em qualquer medição feita pelo daemon, confira o
relógio do processo.** Os dois comandos, e o zero que condena:

```bash
systemctl --user show hefesto-dualsense4unix.service \
  -p ExecMainStartTimestamp --value            # desde quando o processo existe

journalctl --user -u hefesto-dualsense4unix.service \
  --since "AAAA-MM-DD HH:MM:SS" --no-pager \
  | grep -c <evento_que_a_sua_cura_emite>      # 0 = instrumento morto
```

A janela do `journalctl` tem de **começar depois** do start, e **sempre com data
completa** — `--since "21:34:39"` sem data devolve zero em qualquer janela, e
aqui o comando quebrado imita exatamente o defeito que ele deveria detectar.

E **reiniciar é decisão dela**, nunca sua: o restart derruba os handles de uma
partida em curso.

O caso inteiro, com a mordida (0 antes, 2 depois, mesmo código no disco) e o
desenho de um aviso no `doctor` que mediria isso sozinho, está em
[PROTOCOLO — o controle que cai sozinho](../process/estudos/2026-08-07-PROTOCOLO-o-controle-que-cai-sozinho.md),
seções 8.1 e 9.

### `paplay --device=inexistente` sai ZERO e toca no padrão

Nunca aceite código de saída como prova de que o som saiu no dispositivo certo.

### Régua que pergunta pelo campo errado — ou no lugar errado — produz NÃO-ACHADO convincente

**Esta é a família, e ela é mais cara que qualquer medição individual desta
página.** As outras armadilhas fazem o instrumento dizer um número errado, e
número errado tem chance de parecer estranho. Esta faz o instrumento dizer
**"não há nada"** — e "não há nada" nunca parece estranho. Ele parece
tranquilizador, encerra a investigação, e às vezes vira relatório.

O molde é sempre o mesmo: a pergunta é boa, a régua é plausível, a saída é
vazia, e **vazio é lido como ausência quando na verdade é erro de endereço.**

Casos reais, todos de 22 e 23/08/2026, e vários são de quem escreveu isto:

| a régua | o que ela devolveu | o que era |
|---|---|---|
| `grep` por `trigger` no perfil | *"34 perfis sem gatilho"* — levado à dona da casa | o campo é `triggers`, **no plural** |
| `find /tmp /home -maxdepth 4` pelos logs de frametime | *"o log por quadro não está no disco; os números não são sustentáveis"* | estavam em `$CLAUDE_JOB_DIR/tmp/mangohud/`, fora das raízes e abaixo do `maxdepth` |
| `grep -rn "Disconnect(" src/` | *"zero chamadores; o chamador sumiu"* | a chamada é a **string** `"Disconnect"` dentro de um argv, sem parêntese |
| `cat /sys/class/bluetooth/hci*/address` | campo vazio para todo adaptador | esse atributo não existe nesse caminho nesta máquina |
| contar controles por `HID_PHYS` truncado no OUI | `3/1` adaptadores | são `2/1/1` — dois adaptadores do mesmo fabricante fundidos |
| censo de sprints por apelido com prefixo de data opcional | uma lista de "órfãs abertas" | o apelido capturado era `2026-08`, que casa com quase toda linha |
| a régua seguinte, procurando `\*\*Estado:\*\*` no cabeçalho | *"66 sprints sem marcador de estado nenhum"* | a forma mais comum da casa é `- **Status:**`, com **90** ocorrências, e existe a de negrito aninhado. São **quatro**, não 66 |

**O antídoto, e ele é barato:** *antes* de acreditar num vazio, prove que a
régua sabe achar. Rode-a contra um caso que você **sabe** que existe e veja-a
acusar. Se `grep trigger` devolve 34, rode `grep triggers` também; se um `find`
não acha, imprima onde ele procurou e até que profundidade. Uma régua que nunca
foi vista acertando não mediu nada — só ficou quieta.

**E a variante social, que é a pior:** *afirmar o resultado de uma régua que
nunca foi rodada.* Aconteceu nesta sessão — uma passagem disse a dois
subagentes que um censo tinha sido "consertado e revalidado" quando ele não
tinha sido rodado nenhuma vez, e os dois trabalharam vinte minutos sobre a
premissa inventada. A regra que fecha isto é a de sempre nesta casa: **o
comando ao lado do número.** Se não dá para colar o comando, o número não
existe.

### O MangoHud escreve ZERO na metade GPU inteira nesta máquina

**MEDIDO em 23/08/2026**, na RTX 4060 dela, num log real de sessão do Sackboy
(`/tmp/hefesto-mh/*.csv`, 923 linhas de dado):

| coluna | zeros |
|---|---|
| `gpu_load`, `gpu_temp`, `gpu_core_clock`, `gpu_mem_clock`, `gpu_vram_used`, `gpu_power` | **100 %** — todas as 923 linhas |
| `fps`, `frametime`, `cpu_load`, `cpu_temp`, `ram_used` | zero zeros, valores plausíveis |

Não é uma coluna morta: é **a metade GPU do instrumento inteira**, enquanto o
`nvidia-smi` na mesma sessão mostrava 51 % de uso. O cabeçalho de metadados sai
com o campo `driver` **vazio**, que é o sintoma antecedente. O `_summary.csv`
sai com `Average FPS,-nan` e `GPU Load,-nan`.

É a armadilha nº 1 desta página noutro traje: quem ler esse CSV e concluir *"a
GPU está ociosa, fria e sem VRAM"* está lendo sensor desconectado, não medição.
**Antes de usar um log do MangoHud como prova, conte os zeros por coluna.** E
não confunda com o outro defeito do mesmo arquivo: aquele log é **amostrado a
2,47 amostras/s**, não por quadro — `frametime` ali não sustenta análise de
cauda (p99), por mais que a coluna exista.

### Endereço de rádio truncado FUNDE dois adaptadores num só

**MEDIDO em 23/08/2026** na mesa dela, que tem dois adaptadores 5.4 do **mesmo
fabricante** — logo o mesmo OUI, os três primeiros octetos.

Contando controles por adaptador na mesma leitura de `HID_PHYS`:

| régua | resultado |
|---|---|
| endereço **inteiro** (o que o produto usa) | `ac:a7:f1:00:00:41` → 2 · `ac:a7:f1:00:00:ce` → 1 · `d8:44:89:00:00:c4` → 1 |
| **OUI** (três octetos) | `ac:a7:f1` → **3** · `d8:44:89` → 1 |

Os dois adaptadores viram um, e um deles desaparece com os controles dele
junto. Um `grep` de conveniência sobre o prefixo produz uma distribuição
**convincente e errada** — e a casa já pagou por isso noutro lugar (*"uma faixa
de MAC não é um fabricante"*, `e5376a0`).

**A régua é sempre o endereço inteiro.** E na hora de ESCREVER o número em
arquivo versionado, a máscara da casa é zerar os octetos 4 e 5
(`ac:a7:f1:00:00:41`); em fixture, a faixa sintética `aa:bb:cc`. Há portão
(`scripts/check_anonymity.sh`), e ele não perdoa. **A máscara preserva o último
octeto de propósito** — é ela que continua separando `…:41` de `…:ce` depois de
anonimizado.

### O `environ` do PRIMEIRO processo da árvore da Steam não é o do jogo

**MEDIDO em 16/08/2026**, e a armadilha voltou em 23/08 num traje novo, o que é
o motivo de estar nesta página e não só no estudo que a mediu
([O RÁDIO MEIO MUDO](../process/estudos/2026-08-16-O-RADIO-MEIO-MUDO-o-que-atravessa-e-o-que-nao.md),
§"Os erros de instrumento do dia").

O `quem_o_jogo_abre.py` dizia *"o WRAPPER rodou? NÃO"* para dois jogos. Ele lia
o `environ` do primeiro processo da árvore — o **`reaper` da Steam**, que roda
*antes* do wrapper. O `/proc` do processo do JOGO tinha a variável.

**A régua certa é estrutural:** o processo **mais fundo** da cadeia que casa com
o padrão, nunca o primeiro, e nunca por conteúdo. Já é código:
`scripts/ensaios/quem_o_jogo_abre.py::processo_do_jogo`. Use-o — não escreva um
`grep` novo em `/proc`.

*Um instrumento que acusa a própria cura de não existir manda a investigação
para o lugar mais caro possível.* Em 23/08 esse mesmo formato de leitura
produziu a conclusão *"cura por variável de ambiente no wrapper não serve"* —
generalização que a
[ESCONDE-SÓ-O-HIDRAW-01](../process/sprints/arquivados/2026-08-23-ESCONDE-SO-O-HIDRAW-01-o-jogo-continua-vendo-o-fisico-pelo-evdev.md)
teve de desfazer com nota datada.

### Régua que casa um token em QUALQUER lugar do texto, em vez do campo que o significa

**MEDIDO em 23/08/2026**, num censo das sprints. Três resultados convincentes e
falsos, os três da mesma família: a régua achou a palavra certa no lugar errado.

| o que a régua fez | o que ela concluiu | o que era |
|---|---|---|
| extraiu a **data** do nome do arquivo como se fosse o apelido da sprint | tudo casava com tudo (`2026-08` está em toda linha) | régua correta: `^\d{4}-\d{2}-\d{2}-([A-ZÀ-Ú][A-Z0-9À-Ú-]*-\d{2})\b`, **e conferir que nenhuma chave extraída parece uma data** |
| casou a chave por **substring** contra a linha do `SPRINT_ORDER.md` | a linha de `TRES-MODOS-DO-SOM-01` (ABERTA) foi lida contra o arquivo de `SOM-01` (ENTREGUE) → alarme de *"a fila diz aberta e a sprint diz feita"* | `SOM-01` é sufixo de `TRES-MODOS-DO-SOM-01`. Casamento tem de ser da chave INTEIRA, com fronteira |
| procurou a palavra `FECHADA` em **qualquer lugar** do arquivo | `PROVA-NO-PLASTICO-01` foi dada como concluída | a linha 37 diz *"exige a Steam FECHADA"*. É sobre a Steam, não sobre a sprint |

E a régua mais óbvia de todas também mente: **o campo `Status:` de uma sprint
não é fonte.** Esta casa preserva o rótulo antigo de propósito (*"não se apaga
decisão medida"*), então um arquivo cujo cabeçalho diz **CONCLUÍDA** carrega
logo abaixo, e para sempre, o `Status: ABERTA` que valeu antes. Já foi medido
duas vezes: **40 de 48 diziam ABERTA** em 30/07 e **41 de 50** em 31/07, com
entregas provadas no meio. Ler `Status:` produz uma lista de "sprints abertas"
que é quase toda tumba.

**A régua que sobrevive:** cruzar cada pedido com a árvore de HOJE — *a entrega
que ela pede existe em `src/`?* — e nunca com o cabeçalho.

---

## Ferramentas de sistema, e o que não fazer com elas

- **`ydotool` exige `ydotoold` vivo** e só faz `mousemove` **relativo**. Clique
  por coordenada absoluta não existe — e clique cego já desfez configuração
  dela;
- **`wtype` cria e destrói um teclado virtual a cada chamada**; em rajada o
  compositor perde eventos;
- **o helper global de captura de tela dela** (fora deste repositório, em
  `/usr/local/bin`) fotografa a tela inteira e imprime o caminho do PNG. Serve
  para ver o que está na frente dela agora — não para percorrer abas.

---

## Quando desenhar ANTES de codar — o mockup desta casa

Escrito em 25/08/2026, depois de duas rodadas de mockup jogadas fora por não
haver regra escrita.

**Quando vale.** Quando a tela vai mudar de forma, não de detalhe — e quando a
pergunta é *"isso resolve o que eu preciso?"*, que ela responde **vendo**, nunca
lendo. Um mockup em HTML custa horas; uma aba refeita custa dias.

**As cinco regras, e cada uma nasceu de um defeito da mesma noite:**

1. **HTML standalone, aberto por duplo clique.** Sem rede, sem servidor, sem
   fonte web. Ela recusou o artefato publicado com uma frase: *"html standalone
   por favor"*. É o mesmo motivo do `specs.html` e do `painel.html` — instrumento
   que só funciona com rede não serve para depurar rádio.
2. **A paleta tem dono único: `scripts/paleta_da_casa.py`**, copiada byte a byte.
   *"O artefato tem de parecer parte do Hefesto, não um site sobre ele."*
3. **Ponha o dado REAL da máquina dela dentro**, medido no dia — não um exemplo.
   Foi o que fez o mapa de entradas virar conversa: ela reconheceu a própria mesa
   e apontou o erro em segundos.
4. **A tela mostra o AGORA.** O mockup abria numa leitura antiga do barramento e
   ela viu o Wi-Fi numa entrada de onde já o tinha tirado. **Estado velho como
   padrão é o F7 desta casa** — a tela afirmando com confiança o que deixou de
   ser verdade. O "antes" é relatório; nunca estado.
5. **Se ele vira especificação de sprint, ele é VERSIONADO** — em
   `docs/process/sprints/<SPRINT>/mockup/`, nunca em `novo-layout/`, que é
   `.gitignore:108`. O precedente é de 21/08
   (`2026-08-21-ABA-CONFIGURACOES/mockup/`). Um `git clean -xdf` não pode apagar
   a única descrição de um motor de 1058 linhas.

**E a régua do mockup: `node --check` NÃO é teste.** Ele valida sintaxe e é cego
a referência inexistente. Um `ReferenceError` na última linha da função de
desenho deixou uma seção inteira — que carregava três decisões dela — sem
aparecer em **todas** as versões entregues, e nenhuma conferência acusou. A régua
que serve monta um DOM falso e **roda**, em todo estado alcançável:

```bash
node docs/process/sprints/2026-08-24-ABA-CONEXOES/mockup/fumaca.js
# 29/29 estados pintaram — nenhum erro de execução
```
