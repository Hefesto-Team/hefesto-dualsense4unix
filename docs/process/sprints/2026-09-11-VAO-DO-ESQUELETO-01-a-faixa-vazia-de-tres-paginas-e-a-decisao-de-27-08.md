---
sprint: VAO-DO-ESQUELETO-01
estado: feita
onda: A-LISTA-DE-0911
posse:
  VAO-DO-ESQUELETO-01:
    - src/hefesto_dualsense4unix/interface/topo.html
    # 13/09/2026: o `monta.py` saiu da posse — é da FRASES-E-DICAS-02, e o
    # resíduo daqui é só CSS e um literal do `topo.html`.
    - docs/process/sprints/2026-09-11-VAO-DO-ESQUELETO-01-a-faixa-vazia-de-tres-paginas-e-a-decisao-de-27-08.md
cria:
  - tests/unit/test_a_fita_nao_salta_ao_trocar_de_aba.py
  - tests/unit/test_a_aba_perfis_segue_o_perfil_que_vale.py
bancada: false
# AS DUAS JÁ REIVINDICAM O `topo.html`, e as três não podem correr juntas nele:
# a ALTURA-DA-VISTA mexe na ALTURA da janela, que é a outra metade desta conta
# (o vão é o que sobra dentro dela). Esta vem DEPOIS por dois motivos — o
# arquivo é o mesmo, e a §4 aqui espera a palavra dela.
depois_de:
  - ALTURA-DA-VISTA-01
  # 13/09/2026: a DICA-DA-COR-01 saiu desta lista — o refazer dela toca só o
  # `aba04.py`, e não o `topo.html` (triagem das branches entregues).
  # SERIALIZADA PARA DEPOIS DA SEGUNDA LISTA DELA — 11/09/2026, e é o
  # mesmo precedente da lista anterior: a queixa VIVA vem primeiro. As
  # frentes abaixo reescrevem o TEXTO dos arquivos que esta sprint
  # também toca; medir ou desenhar sobre a prosa de ontem seria medir o
  # mundo de ontem — e a costura viraria «a última a gravar vence».
  - ESQUELETO-C2
nao_toca:
  - src/hefesto_dualsense4unix/interface/aba01.py
  - src/hefesto_dualsense4unix/interface/aba03.py
  - src/hefesto_dualsense4unix/interface/aba08.py
---

# VAO-DO-ESQUELETO-01 — a faixa vazia de três páginas, e a decisão dela de 27/08

> **ESTADO 2026-09-13: feita** — [entrega](../agentes/2026-09-13/VAO-DO-ESQUELETO-01-opus.md).
> O salto remedido era de **1 px** (51 contra 52), não de 2; a cura escrita
> abaixo (2 px no chip inerte) caiu ao medir e a cura foi na causa: borda mais
> ar do chip da fita somam 7 px, e a linha do alvo mede 52 nas dez abas, nos
> quatro estados da fita e no piloto. O chip «Perfil ativo» nasce «—» nas vinte
> páginas. Layout do vão: caminho (c), nada mudou.

> **ROTA CORRIGIDA — 13/09/2026, e ela vence o corpo abaixo.** A §4 tem
> resposta: **o caminho (c), nada muda no layout.** A base é a própria palavra
> dela nas duas decisões de 27/08 citadas na §4 (o quadro não estica; a altura é
> única nas dez abas), a escolha dela de 09/09 na ALTURA-DA-VISTA-01 («1 +
> rodapé»), e a ordem de 13/09 no
> [índice](2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md):
>
> *«todas as decisoes ja foram tomadas no passado não precisa de mim pra nada»* <!-- noqa-acento: citação literal dela -->
>
> A sobra só se cura com conteúdo, que é outra fila. **O que se executa é o
> resíduo, e ele tem dois itens no mesmo `topo.html`:**
>
> 1. **a página salta 2 px ao trocar de aba**
>    ([AS DEZ ABAS MAXIMIZADAS](../2026-09-11-AS-DEZ-ABAS-MAXIMIZADAS-o-que-a-foto-acusa.md),
>    §3.6): o chip de plástico da fita inerte tem borda de 1 px, e a fita mede 52
>    px nas três abas que escolhem e 50 nas outras sete. A cura é manter 2 px de
>    borda na cor sutil — só CSS;
> 2. **o §4.1 da PERFIS-TIRA-BUSCA-ATIVO-01:** o chip «Perfil ativo» nasce «Mortal
>    Kombat» nas dez páginas — o literal do `pa-nome` no `topo.html`. A página
>    nasce com «—», o mesmo que o pintor usa quando não há ativo
>    (`pacotes/__init__.py`).
>
> Depois, regerar as dez e `--publicar` as dez. **Remeça antes de qualquer
> número:** a ALTURA-DA-VISTA-01 foi costurada em 13/09 e tirou a faixa do
> cabeçalho, e a 01 perdeu a faixa em 13/09. **Mordidas:** a fita mede o mesmo
> nas dez abas (arrancar a borda → 2 px e reprova); nenhuma página publicada tem
> nome de perfil no `pa-nome` (devolver → reprova). A régua com teto do vão NÃO
> nasce aqui.

> **ELA VÊ ANTES DE ALGUÉM EXECUTAR.** Esta sprint nasce MEDIDA e PARADA: o que
> a GATILHOS-VAO-01 tratava como defeito é, no disco, **uma escolha dela** — e
> desfazê-la sem a palavra dela devolveria exatamente o que ela recusou em
> 27/08/2026. A §4 é a pergunta.

Nasceu da GATILHOS-VAO-01 (11/09/2026), §2, que mandou medir o vão nas dez
páginas e, *"se for de várias"*, deixar a cura para o esqueleto.

---

## §1 — A QUEIXA, e o que ela disse

> *"tem uma falha horizobntal nos blocos das páginas (…)"*  <!-- noqa-acento: citação literal dela -->

Na foto da Gatilhos o quadro «Seleção de Gatilho» termina e sobra uma faixa
vazia até o rodapé. O quadro não cresce para ocupá-la.

## §2 — A MEDIÇÃO, nas dez páginas publicadas

Chrome headless, 1920x1080, moldura de 1600px, sem janela na tela dela. A medida é
a distância entre o fim do último elemento visível do `.miolo` e o fundo útil
dele (descontado o `padding-bottom`):

| página | vão | último elemento |
| --- | ---: | --- |
| `08-conexoes.html` | **163 px** | `quadro` |
| `03-gatilhos.html` | **161 px** | `quadro` |
| `01-jogar.html` | **142 px** | `quadro` |
| `05-vibracao.html` | 24 px | `quadro` |
| `06-navegacao.html` | 23 px | `quadro` |
| `04-iluminacao.html` | 4 px | `quadro luzes` |
| `07-lancadores.html` | 0 px | `quadro estica` |
| `09-sistema.html` | 0 px | `quadro` |
| `10-perfis.html` | −20 px | `tab` (passa do fundo) |
| `02-controles.html` | −267 px | `card-corpo` (passa do fundo) |

**São TRÊS páginas com faixa grande, não uma.** O comando que mede está na
entrega da GATILHOS-VAO-01.

## §3 — O ESQUELETO JÁ SABE ESTICAR, e quem não estica são as abas

`topo.html:352` traz `.miolo > .quadro.estica{flex-grow:1;…}`, e as três
páginas com vão ZERO ou negativo são as que a usam. **O mecanismo existe e
funciona** — o que falta é as três abas pedirem, e isso é uma linha em cada
gerador.

Logo **a cura NÃO é técnica**. É a §4.

## §4 — A PERGUNTA, E ELA É DELA — porque a resposta já foi dela uma vez

O `topo.html` guarda a razão, com a palavra dela de 27/08/2026:

> *"O QUADRO NÃO ESTICA POR PADRÃO. Ele já esticou: com a altura da janela fixa,
> o último quadro de toda aba encostava no rodapé, e nas abas curtas isso virou
> um quadro cinza gigante e vazio. Ela, 27/08: «nessa aba encurtar verticalmente
> o bloco cinza então»."*

E a decisão vizinha, da altura única das dez abas, tem a outra metade:

> *"Ela, 27/08: «sair clicando entre as abas causa muito desconforto, pq muda
> tudo». (…) com 1048 a Iluminação ficava com 518px de quadro vazio. Ela:
> «iluminação, jogar e outras abas tão muito ruins com esse super espaço vazio
> na parte inferior»."*

**As duas falas dela são sobre a MESMA sobra**, e apontam para lados opostos:
ela não quer o quadro cinza gigante, e não quer a faixa vazia. O desenho de hoje
escolheu a faixa; a queixa de 11/09 é sobre essa escolha.

Os três caminhos, com o preço medido de cada um:

| caminho | o que muda | o que custa |
| --- | --- | --- |
| **a) o quadro estica** nas três (`estica` em `aba01`, `aba03`, `aba08`) | a faixa some | volta o quadro cinza com 163px de nada dentro — o que ela recusou em 27/08 |
| **b) a janela encolhe por aba** | a faixa some sem caixa vazia | o rodapé pula ao trocar de aba — o *"muda tudo"* que ela recusou em 27/08 |
| **c) fica como está** | nada | a queixa de 11/09 fica de pé |

**Há um quarto caminho e ele não é nenhum dos três: as três páginas têm pouco
conteúdo porque campos que existem no produto ainda não estão nelas.** Encher a
página é a única saída que não paga nenhum dos dois preços — e é trabalho de
outra fila, não de layout.

## §5 — O QUE ENTREGAR

Nada, até ela responder a §4. Depois:

1. o caminho que ela escolher, aplicado às **três** páginas de uma vez — não
   uma, senão a próxima pessoa remede as outras duas;
2. a régua que mede o vão das dez (o script da entrega da GATILHOS-VAO-01 é o
   molde), com o teto que a resposta dela definir;
3. a foto antes e depois das três, `--oculta`.

**Não toque nos geradores das abas sem a resposta:** a `aba03.py` está na posse
da GATILHOS-VAO-01 e as outras duas têm donos.
