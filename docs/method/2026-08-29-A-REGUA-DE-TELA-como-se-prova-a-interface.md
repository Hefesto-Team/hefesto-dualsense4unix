---
cria: nenhum módulo — este documento ensina a usar dois instrumentos que já existem
---

# A RÉGUA DE TELA — como se prova a interface

**29/08/2026.** Pedido dela, com todas as letras:

> *"materializa isso, e temos que ter no nosso hook do novo dev algo que induza
> a construção de validações via interface pra ver se tal problema foi resolvido
> ou se tal coisa traz regressão. E os testes automáticos funcionam."*

**Este arquivo é para quem for escrever a PRÓXIMA validação de interface** —
pessoa ou agente. Ele não narra o dia: ele ensina o vocabulário, diz qual dos
dois instrumentos usar, e lista os defeitos de tela que esta casa **já pagou**,
cada um virando um caso de régua. É contra defeito conhecido que se prova
instrumento.

Quem só quer começar: pule para [§3, o exemplo de dez linhas](#3-o-vocabulário).

---

## 1. O que mudou, e por que agora dá para provar

A interface nova é o mockup HTML rodando num `WebKit2.WebView` dentro da janela
GTK3. Isso a torna **dirigível por dentro**:

* `evaluate_javascript` executa JS arbitrário na página: `el.click()` percorre o
  **mesmo caminho de eventos** de um clique de rato, e o DOM responde geometria e
  texto;
* `register_script_message_handler` traz a resposta de volta ao Python, pelo
  `postMessage`.

Os dois sentidos fechados é o que separa "o clique saiu" de "o clique foi
ouvido" — e essa diferença é o defeito inteiro do §4.3.

**A régua é `scripts/regua_de_tela.py`.** Ela embrulha isso num vocabulário
síncrono: cada pergunta bombeia o laço GLib até a resposta chegar, então quem
escreve o teste não lida com *callback* nem *thread*, e não perde o tempo real —
que é onde a interface vive.

---

## 2. Playwright × ponte JS — os dois instrumentos, e não são substitutos

Esta é a primeira decisão de toda régua nova, e escolher errado dá verde falso.

| | **`olhar.py` e as réguas de `src/hefesto_dualsense4unix/interface/`** | **`scripts/regua_de_tela.py`** |
|---|---|---|
| motor | Playwright dirigindo **Chromium** | **WebKitGTK** dentro de uma janela GTK |
| alvo | o **mockup**, arquivo `file://` | o **motor que ela vai usar**, com o piloto e o daemon vivo |
| alcança `:hover`, arrastar, roda do rato, foco por teclado | **sim** | não |
| alcança a ponte tela → Python → eco | não | **sim** |
| alcança `postMessage`, estado do produto, IPC | não | **sim** |
| custa | um Chrome por corrida | ~1,5 s por `WebView`, sem rede |
| entra na suíte do `pytest` | não hoje (`playwright` está fora do `pyproject.toml`) | **sim**, com guarda de ambiente |

**O Playwright não alcança o WebKitGTK.** Ele controla Chromium, Firefox e o
WebKit *dele próprio* — nunca um `WebView` embutido num aplicativo GTK. Não é
limitação de configuração; é o que ele é.

**E o inverso também vale**: a ponte JS não move o ponteiro, logo `:hover`,
arrastar e foco por teclado só existem do lado do Playwright.

> **A regra prática.** *Isto é uma promessa do DESENHO (medida, alinhamento,
> `:hover`, a caixa que não pode vazar)?* → Playwright sobre o mockup.
> *Isto é uma promessa do PRODUTO (o botão responde, o valor chega, o eco volta,
> o estado muda)?* → `scripts/regua_de_tela.py`.

Uma régua de layout escrita na ponte JS mede certo e custa caro; uma régua de
comportamento escrita no Playwright **não pode falhar**, porque no mockup não há
ninguém do outro lado do clique.

---

## 3. O vocabulário

`Tela` é a aba aberta. Tudo é síncrono e tudo reprova em vez de devolver
silêncio.

| verbo | o que faz |
|---|---|
| `Tela.abrir("02")` · `Tela(pagina)` | abre a aba num `WebView` oculto e **espera a PÁGINA confirmar** |
| `clicar(sel)` | `el.click()`, e devolve o retrato do alvo (travado, visível, caixa, texto) |
| `clicar_e_ouvir(sel, esperados=1)` | clica e **exige** que a página responda. `esperados=0` prova o silêncio |
| `ler(sel)` · `atributo(sel, nome)` · `estilo(sel, prop)` · `classes(sel)` · `tem_classe(sel, c)` | o que a tela diz |
| `medir(sel)` → `Caixa(x, y, largura, altura)`, com `.centro` | geometria do DOM |
| `contar(sel)` · `existe(sel)` · `travado(sel)` | quantos, se há, se está insensível |
| `esperar_ate(pergunta, prazo=…)` | bombeia até virar verdade; **reprova no estouro** e devolve *quando* |
| `avancar(seg)` · `aos(seg, funcao)` · `relogio` | o tempo, que é metade das provas |
| `recados(gesto=None)` · `limpar_recados()` | o que a página mandou pelo `postMessage`, na ordem |
| `executar(js)` | JS cru, para o que o vocabulário não cobre |
| `foto(caminho)` | um PNG da janela oculta, para o olho dela |

**Nada devolve `None` calado.** Todo `_exigir` conta quantos elementos o seletor
casou, e `0` levanta `SemElemento` nomeando o seletor. Zero não é *"nada
mudou"* — é a régua olhando para um endereço que não existe.

### O exemplo de dez linhas

Este trecho **foi rodado hoje** e a saída abaixo é a dele. Copie e troque o
seletor.

```python
import sys
sys.path.insert(0, "scripts")
from regua_de_tela import Tela, achar_a_aba

pagina = achar_a_aba("02")
sys.path.insert(0, str(pagina.parent / "_ferramentas"))
import controles_vivos                                  # o piloto, como biblioteca

with Tela(pagina, titulo_esperado="Hefesto") as tela:
    tela.executar(controles_vivos.BOOTSTRAP)            # instala os ouvintes da página
    recados = tela.clicar_e_ouvir('.ctl [data-mudo="microfone"]')
    print("recados:", [r.bruto for r in recados])
    tela.clicar_e_ouvir('.ctl [data-mudo="mic-liberar"]', esperados=0)
    print('o "Liberar" nasce travado e não responde — provado o silêncio')
```

```
recados: ['{"gesto":"mudo","bloco":"microfone","controle":"p1","estava":"off"}']
o "Liberar" nasce travado e não responde — provado o silêncio
```

**Três coisas a notar, e as três são a lição:**

1. `Tela(pagina, titulo_esperado="Hefesto")` — o título é conferido. Escrever
   `titulo_esperado="Controles"` **reprova**, porque a página se chama
   *"Hefesto — aba CONTROLES (mockup 26/08/2026)"*. Medido hoje: o instrumento
   levanta `CargaFalhou` dizendo o `readyState`, o URI e o título que achou.
2. `tela.executar(controles_vivos.BOOTSTRAP)` — **o mockup sozinho não tem
   ouvinte**. Sem esta linha, todo `clicar_e_ouvir` reprova por silêncio, e
   estaria certo: sem o piloto não há produto do outro lado.
3. `esperados=0` cumpre o **prazo inteiro** antes de concluir. Não se prova
   ausência olhando por um instante.

Régua de verdade mora em `tests/unit/test_*.py`, e o modelo pronto é
`tests/unit/test_regua_de_tela_a_aba_controles.py`: 17 casos, uma `bancada` de
módulo (abrir um `WebView` por teste custaria 1,5 s cada) e uma `CabecaDeMentira`
que **herda o piloto** em vez de copiá-lo — `_remontar`, `_pintar`,
`_pacote_do_card` e `_da_tela` rodam verbatim, então quem quebrar qualquer um
dos quatro é pego ali e não na tela dela.

---

## 4. Os sete defeitos que esta casa já pagou

Cada um vira um caso de régua. A coluna da direita é a asserção que o teria
pegado — e, onde já existe, onde ela está.

### 4.1 O `or 128` — o extremo do analógico virava o centro

`_eixo_do_analogico` era `int(inputs.get(nome) or 128)`, e `0 or 128` é `128`.
O zero, que num analógico é o **extremo** (o talo à esquerda ou para cima),
chegava à tela como o **centro**: erro de 128 unidades, o máximo possível, e
exatamente no fim do curso. Só o zero mentia, e mentia sozinho — `1`, `64`,
`128` e `255` passavam.

**A régua:** pintar a mesa com `lx=0` e exigir que a tela **escreva o zero**, e
que o ponto do círculo esteja no extremo — não no meio.
*Onde está:* `test_o_extremo_do_analogico_nao_e_o_centro`.
**Mordida remedida hoje:** devolvido o `or 128`, **3 dos 17 vermelhos**, e a
mensagem foi `a tela não escreveu o zero: 'X: 128Y: 128'`.

> A lição que passa desta linha: **`or` com valor numérico é armadilha sempre que
> o zero for legítimo.** O produto que ela usa há meses estava certo —
> `int(inputs.get("lx", 128))`, a forma com *default*, imune ao *falsy*.

### 4.2 A geometria assimétrica dos sticks

O ponto do analógico é posicionado em percentagem e centrado por
`transform:translate(-50%,-50%)`. Sem esse `transform` ele é posicionado **pelo
canto**, e as duas pontas do curso deixam de ser espelhos.

**A régua:** medir o desvio do ponto em relação ao **centro do próprio círculo**
(não à página: a posição absoluta muda com o layout, a relativa é a promessa do
desenho) nos dois extremos, e exigir simetria.
*Onde está:* `test_os_dois_extremos_sao_simetricos`.
**Mordida remedida hoje:** arrancado o `transform` do `.stick .p`, a régua
devolveu **-43,50 px e +52,50 px** — os números históricos, medidos de volta
pela tela. Na árvore sã: −48 e +48.

> **E aqui mora um limite do instrumento, medido hoje e não conhecido antes:**
> arrancar o mesmo `transform` do **gerador** (`aba02.py`) deixou os 17 testes
> **verdes**. A régua mede a página **gerada**, e o CSS do gerador só chega lá
> depois do `regerar.py` — a remontagem do piloto devolve a *marcação*, não a
> folha de estilo. **Quem mexe em `aba*.py` regera antes de medir, ou mede o
> arquivo de ontem.** Está escrito no `--limites` do instrumento.

### 4.3 O `--prova-gesto` que dava verde sobre dois botões mortos

O `chr(0x1F399)` (o microfone) e o `chr(0x266A)` (a nota) da aba Controles tinham `cursor:pointer`, eram pintados, e **não
tinham ouvinte**. A prova de gesto do piloto clicava a faixa, um interruptor de
sensor e um botão de rota — **e nunca os dois de som**. Verde sobre dois botões
mortos, e não foi *rodar* a régua que achou: foi **ampliá-la**.

**É o defeito de origem deste documento**, e o que o `clicar_e_ouvir` existe para
matar: um clique que só "sai" não distingue botão vivo de botão morto.

**A régua:** todo botão novo entra no roteiro, e **a ordem é a mordida**. Hoje o
roteiro tem sete cliques, e o `[data-mudo="mic-liberar"]` é clicado **antes** do
`chr(0x1F399)` (o microfone), com a posse ainda do kernel: travado, tem de produzir **zero** gestos.
Depois o `chr(0x1F399)` (o microfone) assume a posse, e só então o Liberar responde e volta a travar. Uma
régua que clicasse os três em qualquer ordem não distinguiria *"travado"* de
*"sem ouvinte"* — que é exatamente o defeito de origem.
*Onde está:* o roteiro de `_marcar_gestos_de_mentira`, e
`test_o_liberar_nasce_travado_e_nao_responde`.
**Mordida remedida hoje:** tirado do `BOOTSTRAP` o laço que instala os ouvintes
de `[data-mudo]`, **4 dos 17 vermelhos**, com o retrato do alvo na mensagem:
`<button class='mudo-i'> texto='`chr(0x1F399)` (o microfone)' · travado=False · visível=True`.

### 4.4 O hexadecimal da barra de luz no título do Touchpad

`q(".de-quem")` pegava o **primeiro** elemento da classe. Quando o touchpad
ganhou o seu `.de-quem`, a classe deixou de ser única no cartão e o código da
cor do jogador foi escrito no título do Touchpad. **Foi visto NA FOTO, não
deduzido** — nenhuma asserção existente o pegava, porque nenhuma perguntava
*"quem é o dono deste texto"*.

**A régua:** endereçar por `data-campo`, nunca por classe de estilo, e ter uma
asserção por campo — `ler('[data-campo="luz-hex"]')` e
`ler('[data-campo="touch-estado"]')` são perguntas diferentes, e uma não pode
responder pela outra.

> **A regra geral:** classe é para pintar, `data-*` é para endereçar. Um seletor
> de estilo usado como endereço quebra no dia em que o desenho reusar a classe —
> em silêncio, e num lugar que ninguém está olhando.

E por isso a mordida do endereço existe: `--arranca-enderecos` apaga os `data-*`
e vê a pintura **desabar**. Se a conta não cair, os endereços não estavam sendo
usados. `campo` e `mudo` entraram nessa lista em 29/08 — e a falta deles era o
mesmo buraco do §4.3: *uma régua que não toca um endereço não pode reprovar quem
o quebrar.*

### 4.5 A guarda de carga que matava a janela quando ela clicava numa aba

Na primeira vez que ela abriu o piloto, **a janela fechou sozinha depois de ~12
segundos** — o tempo de ela clicar em "Conexões". A tira do mockup é um `<a
href="08-conexoes.html">`, ou seja ela **navega de verdade**; o `load-changed`
dispara outra vez, e a guarda de carga — que existe para pegar carga **falha** —
leu navegação legítima como erro fatal.

**A régua:** distinguir *"a primeira carga não confirmou"* de *"a página mudou
porque alguém clicou"*. A guarda continua valendo para a primeira carga, que é
onde ela protege; sair da aba só **pausa a pintura**.

> **A lição, e ela vale para toda cura de robustez:** uma guarda que trata o
> caminho normal como falha é pior que guarda nenhuma — matou a tela DELA para
> relatar um sucesso. O mesmo padrão apareceu no `DONOS_DOS_GESTOS`, onde um
> `KeyError` cru derrubava a janela inteira para relatar um dono desconhecido.

### 4.6 Os 84 filtros SVG mortos que o Chrome ignorava e o WebKit revelou

O `monta.py` prefixa os ids do SVG e **não reescreve o `url()`**, porque o
desenho usa `&quot;` escapado. Resultado: 84 filtros apontando para ids que já
não existem, em cinco abas. **O contorno do touchpad nunca apareceu, em motor
nenhum** — o Chrome falhava calado, e foi a troca para o WebKit que revelou.

**A régua:** contar os filtros que apontam para id inexistente e **deixar a
conta escrita**, em voz alta, mesmo enquanto a cura não é aplicada (ela muda
1,09% dos pixels do desenho que ela aprovou, logo é decisão dela).

> **A lição:** *referência morta que o motor ignora em silêncio é a classe de
> defeito que só um SEGUNDO motor revela.* Vale para `url(#id)`, para
> `querySelector` e para `data-*` arrancado. Quando existir uma conta possível,
> a régua conta — e uma conta que não muda é mais barata que um olho que
> compara.

### 4.7 A régua de pop-up que comparava o rodapé com a viewport do navegador

As três pop-ups da Navegação **nunca tinham sido medidas**, e as duas réguas
existentes eram cegas a elas por motivos **diferentes** — o que é pior que uma
cegueira só, porque cada uma parecia cobrir o que a outra não cobria: a `regua.py`
carrega a página **sem fragmento**, e a pop-up só aparece em `:target`; a
`regua_estados.py` varre `.miolo, .miolo *`, e a pop-up nasce **irmã** da
`.janela`, fora do miolo.

E quando alguém finalmente as mediu, mediu **contra o errado**: a pop-up é
`position:fixed`, logo ela se centra nos 1920×1080 do navegador — e não nos
1180×757 da `.janela` desenhada, que é a janela do produto. **Medir contra a
viewport daria verde numa caixa de 1000 px que no produto ficaria com 243 px
para fora.**

**A régua:** medir contra a `.janela` da própria página e projetar a caixa
centrada nela. *Onde está:* `regua_popup.py`, que já traz `--morde`.

> **A lição, e é a mais cara das sete:** *duas réguas verdes não são cobertura —
> podem ser dois pontos cegos que se acham cobertos.* Antes de acreditar num
> verde, pergunte **o que aquela régua nunca viu**. E declare o **referencial**:
> o número certo medido contra o quadro errado é indistinguível de um acerto.

---

## 5. A regra que vale para toda régua nova

### 5.1 Ela tem de MORDER

**Um teste que passa com a cura arrancada não testa nada.** Arranque, veja
reprovar, devolva — e escreva o resultado, porque o número da mordida é o que
prova o instrumento.

A forma que funciona é uma **matriz**: uma cópia da árvore por mordida, cada
mordida quebrando **uma** coisa, e a contagem de vermelhos anotada. Foi assim
que a régua da aba Controles se provou:

| mordida | vermelhos |
|---|---|
| árvore sã | **0** — 17 passam |
| o `or 128` de volta | 3 |
| o `.stick .p` perde o `translate(-50%,-50%)` | 3 |
| sai do `BOOTSTRAP` o laço que ouve `[data-mudo]` | 4 |
| a remontagem desiste calada | 13 |
| a pintura conta cego em vez de ler a tela | 1 |

**E a matriz achou três defeitos na própria régua**, que rodá-la nunca acharia:

1. **A variável de ambiente não fixava o alvo** — só acrescentava uma raiz, e
   como a escolha é por *mtime*, três mordidas foram medidas contra a árvore
   **viva** e passaram todas. Sem a matriz, teria sido entregue um instrumento
   que mede alvo diferente do que lhe mandam.
2. **Um teto de mordida frouxo** deixava a conta cega passar por 1,3 ponto.
3. **Um teste reprovava a CURA, não o defeito** — exigia sobra zero, e a sobra de
   2,5 px é o desenho (ponto de 9 px, borda de 2 px). O defeito era a sobra ser
   *diferente* nas pontas. Reescrito como simetria.

> **O padrão desta casa, e ele já pegou instrumento falso vezes demais:** *a
> régua confunde a PALAVRA com o ATO.* Ela desliga exatamente quando alguém
> escreve bem — procura o nome no arquivo inteiro e acha no comentário. Uma
> régua que lê fonte tem de olhar **linha de código**, não o texto todo.

### 5.2 Ela tem de VIVER NO TEMPO

Uma ação acontece aos 3 s e a consequência aos 5. **Uma régua que roda o tique
UMA VEZ mede um instante, não um comportamento** — foi assim que uma leva
introduziu uma regressão visível só aos 181 segundos, com 67 testes verdes.

Daí `esperar_ate`, `avancar` e `aos`. E daí `esperar_ate` **reprovar** no
estouro em vez de devolver `False`: quem escreveu o teste esqueceria de conferir,
e o silêncio viraria verde.

### 5.3 Ela tem de exigir um PISO

`contar(sel)` devolvendo `0` é resposta **legítima**. Medido em 29/08: uma
leitura caiu no instante em que outra leva regerava o `02-controles.html`, e a
tela veio vazia com `readyState == 'complete'` e o título certo — porque um
arquivo truncado carrega inteiro. A defesa não é do instrumento, é da régua:
**afirme quantos** (`assert tela.contar(".ctl") == 4`) antes de afirmar qualquer
coisa sobre o conteúdo.

### 5.4 Um pulo não é um verde

A régua da aba Controles pula, nomeando o motivo, sem servidor gráfico, sem
WebKit ou sem o mockup. **Pulo lido como verde é o mesmo verde falso de sempre**,
e hoje ele quase aconteceu: apontada para a cópia de `novo-layout/` da própria
árvore `interface/nova`, ela **pulou** com
`ModuleNotFoundError: No module named 'mesa_viva'` — porque aquela cópia é de
28/08 03:09 e não tem o piloto. Ela só passa porque o instrumento varre as
árvores que o `git` declara e escolhe **a mais nova**, que hoje é a dela.
Quem contar pulos como aprovação vai declarar cobertura sobre uma árvore que não
tem o que medir.

---

## 6. Onde a régua mora — e por que não em `novo-layout/`

**`novo-layout/` é `.gitignore:108`.** Medido: o `git` conhece **0 arquivo** lá
dentro e **0 commit de toda a história** tocou a pasta. É a mesma cicatriz
estrutural do arquivo de contrato desta casa, e ela tem três consequências que
decidem o endereço de todo instrumento novo:

1. **Não viaja em worktree.** `git worktree add` não copia arquivo ignorado.
   Régua ali é invisível a toda árvore de agente.
2. **Não entra em índice**, logo **nenhum `pre-commit` pode cobrá-la**, e o
   portão do §7 diz isso em vez de fingir cobertura.
3. **Não entra no CI.**

Por isso `scripts/regua_de_tela.py` nasceu em `scripts/` e a régua dela em
`tests/unit/`. **Instrumento permanente é versionado; ferramenta de mockup pode
ficar onde o mockup está.**

E a divergência que isso já criou, medida hoje: **as duas árvores têm cópias
diferentes do mockup**, e quatro ferramentas do piloto faltam na cópia da
`interface/nova`. O instrumento avisa no `stderr` quando acha mais de uma cópia,
e usa a mais nova:

```
régua_de_tela: 2 cópias de '02'; uso a mais nova.
  …/hefesto-dualsense4unix/layout/02-controles.html      (29/08 20:48, 149820 B)
  …/hefesto-dualsense4unix-dev/layout/02-controles.html  (29/08 03:09, 129354 B)
```

Para fixar o alvo — e **toda mordida tem de fixar** —, use a variável de
ambiente `HEFESTO_NOVO_LAYOUT`: quando ela está posta, é a **única** raiz.

---

## 7. O gancho que pergunta pela régua

`scripts/check_regua_de_tela.py` faz **uma** pergunta ao índice, em ~40 ms, sem
montar GTK e sem abrir Chrome: *este commit mexe na tela e não traz régua
nenhuma?* Se sim, ele nomeia as abas tocadas, aponta este documento, separa **a
biblioteca** (que se importa de um teste) **das réguas do mockup** (que se rodam
à mão), e lembra que a régua precisa morder.

Ele **induz, não bloqueia** — e o degrau é uma constante, com gatilho medido:

| grau | faz | gatilho para subir |
|---|---|---|
| **1 (hoje)** | avisa, nomeia as abas, lista as réguas do disco | — |
| 2 | imprime o comando pronto de cada régua da aba | toda aba ter ao menos uma régua que a nomeia |
| 3 | reprova | o censo mostrar a maioria dos commits de tela já com régua |

A razão de começar avisando está escrita nesta casa: *um portão que reprova
tudo de uma vez é um portão que alguém desliga na segunda-feira*, e a primeira
reação seria `--no-verify`.

**Duas coisas que a medição derrubou, e a segunda é maior que o portão:**

* **O gancho deste repositório nunca rodou em worktree nenhuma.** O gancho global
  encadeia o do repositório por um caminho dentro de `$REPO_ROOT/.git`; numa
  worktree ligada o `.git` é um **arquivo** (`gitdir: …`), esse caminho não pode
  existir, o teste `[ -x ]` é falso e a delegação não acontece — **em silêncio**.
  Cai fora o gancho inteiro, não só este portão. O conserto é de uma linha e é
  **dela**, porque o arquivo é global e vale para todo repositório dela;
  `check_regua_de_tela.py --diagnostico` imprime o estado da árvore e o patch.

  **E o patch sozinho não fecha a história — medido ao integrar.** O
  `.git/hooks/pre-commit` da árvore principal é um **link simbólico** para
  `../../scripts/hooks/pre-commit`, e o link é relativo ao `.git`, não à árvore
  que está commitando. Então, com o patch, uma worktree passa a rodar o texto do
  gancho **da árvore principal** contra o **próprio índice**. Hoje isso quer
  dizer que a `interface/nova` rodaria o gancho do `dev`, que ainda não tem o
  bloco da régua — o desalinhamento só some quando o ramo mergeia. Quem for
  medir gancho em worktree confira primeiro *qual texto* está sendo executado.
* **Nenhum gancho pode cobrir o mockup**, pelo §6.2. O portão declara isso no
  `--diagnostico`; a saída, se ela quiser cobertura ali, é de **versionamento**,
  não de gancho.

---

## 8. O estado do resto — para não confundir "tem régua" com "o CI mede"

Tudo abaixo é de 29/08/2026, na árvore dela. Onde diz **remedido**, a conta foi
refeita ao escrever este documento; onde diz **medido no HEAD `da75f4cc`**, é a
medição da leva e não foi repetida — a árvore estava sob escrita de seis levas,
e número de árvore em movimento não repete.

* **A suíte roda e fecha** (medido no HEAD `da75f4cc`): oito lotes, 13.839 verdes
  em 11 min 16 s, nenhum lote morreu no meio. O contrato desta casa publica dois
  números mais velhos, 13.133 e 13.381.
* **A tela quase não é medida por máquina** (medido no HEAD `da75f4cc`): **2,4%
  dos testes simulam ação do usuário**, e **todos por emissão direta de sinal**.
  **Remedido:** `Gdk.Event` aparece em **0** arquivos de teste e `send_event` em
  **0** — ninguém injeta evento real. E `.clicked()` **não passa por sensível nem
  por visível**: botão dessensibilizado ou invisível passa verde. **É o defeito
  do §4.3 na forma geral, espalhado pela suíte.**
* **`WebView` na suíte: zero** antes desta leva — remedido, `WebView(` casa **0**
  arquivos em `tests/`. E **nenhum job de CI instala o binding do WebKit**:
  remedido, a palavra `webkit` não aparece em workflow nenhum. Hoje nenhum job
  rodaria um teste de `WebView` nem que ele existisse.
* **O CI não roda desde 26/08 e a última corrida foi vermelha** — remedido pelo
  `gh`: a última em `dev` é de 26/08 com conclusão `failure`, e há **13 commits
  locais não empurrados**. O job `anonymity` só faz `checkout` (sem
  `setup-python`, sem `pip install`) e ganhou **depois daquela corrida** dois
  passos que importam `playwright` e `structlog`. Remedido com o `python3` do
  sistema: `ModuleNotFoundError` nos dois. Ele reprova na primeira vez que rodar.
  E `playwright` não está no `pyproject.toml`, em extra nenhum.

**A leitura honesta:** a metade que é texto e dado funciona; a metade que é tela
está sendo construída agora, e este documento é o começo dela, não o fim.

---

## 9. A lista de conferência, para a próxima régua

1. Escolhi o instrumento certo? (§2 — promessa do desenho × promessa do produto)
2. A régua mora em `tests/unit/` ou `scripts/`, e não em `novo-layout/`? (§6)
3. Ela exige um **piso** antes de afirmar qualquer coisa? (§5.3)
4. Ela **vive no tempo** — espera a consequência, não fotografa o instante? (§5.2)
5. Se é comportamento: usei `clicar_e_ouvir`, e não só `clicar`? (§4.3)
6. Endereço por `data-*`, nunca por classe de estilo? (§4.4)
7. Declarei o **referencial** de toda medida? (§4.7)
8. **Arranquei a cura e vi reprovar?** Quantos vermelhos? Está escrito? (§5.1)
9. A mordida foi medida contra a árvore que eu **fixei**? (§6)
10. O que esta régua **nunca vai ver**? Está escrito junto? (§4.7)
