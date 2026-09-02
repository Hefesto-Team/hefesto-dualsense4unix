# As abas em trabalho na bancada

Toda seção aqui é uma aba cujo **desenho já andou** e cujo **produto ainda não
recebeu** — porque ela ainda não deu o OK. O
`scripts/check_o_desenho_aprovado.py` lê este arquivo; a aba que não estiver
aqui, ele reprova.

**A direção é `mockup/` → `layout/`.** A bancada é o desenho de hoje; o produto
só recebe quando ela aprova a aba **inteira**, que é a escolha dela de
31/08/2026 — nem a cada ponto, nem só no fim da lista.

**Formato** — uma seção por página, com data e o ponto que está aberto:

```
## 01-jogar.html
- **DD/MM/AAAA** — o ponto da lista que está aberto nela.
```

Quando ela aprovar a aba, `--publicar NN` leva o desenho ao produto e **apaga a
seção daqui**: a aba deixou de estar em trabalho.

---

## 09-sistema.html

- **02/09/2026** — **o bloco "O serviço" estourava 27px com os valores REAIS**,
  e o desenho nunca mostrou isso porque os textos dele são curtos. `.bloco2`
  usava `1fr` cru, que tem por piso o CONTEÚDO: quando a linha "Como ele
  enxerga a janela" deixou de dizer `Wayland · COSMIC` (literal do desenho) e
  passou a dizer `Sem ver nada agora (sem_foco_x)` (o que a máquina dela
  responde), a coluna de estado não encolheu, empurrou os quatro botões e eles
  atravessaram o risco por cima do Perfil de Bateria.

  Medido no Chrome (1920×1080), na página **publicada**, com os valores que o
  pacote emite hoje — o bloco vizinho começa em `x=973`:

  | valores | os botões ocupam | resultado |
  | --- | --- | --- |
  | os do desenho | `[748..932]` | folga de 41px |
  | os reais, com `1fr` | `[816..1000]` | **estouro de 27px** |
  | os reais, com `minmax(0,1fr)` | `[748..932]` | folga de 41px |

  Com os textos do desenho a cura **não muda um pixel** (as duas primeiras
  linhas da tabela dão a mesma caixa). O que ela muda é a aba com dado de
  verdade dentro.

- **02/09/2026** — **o mesmo defeito, de novo, em `.saude-cols`, e 253px.** As
  frases do `storm_report` são longas (*"regra áudio-off inativa — o mic e o
  fone do controle estão liberados. O que fazer: nada."*) e as do desenho são
  curtas. Com `1fr` cru a coluna não encolhe, as reticências de
  `.saude .txt span:last-child` nunca chegam a agir, e a segunda coluna do
  exame passa por cima de "Preparar os jogos". Medido na bancada, `x=1263` é
  onde aquela faixa começa:

  | achados | a 2ª coluna termina em | resultado |
  | --- | --- | --- |
  | os do desenho | `1222` | folga de 41px |
  | os reais, com `1fr` | `1516` | **estouro de 253px** |
  | os reais, com `minmax(0,1fr)` | `1222` | folga de 41px |

  **A régua desta aba passou a cobrir `.bloco2` e `.saude-cols`** (`aba09.py`,
  régua 5): ela cobria as três faixas EXTERNAS e deixava as internas de fora —
  e o `1fr` cru ficou invisível ali por não estourar com texto de bancada.

- **02/09/2026** — **o exame ganhou endereço** (`data-campo` + `data-hef-alvo`
  em `exame-contagem` e `exame-lista`). São atributos invisíveis, não mudam um
  pixel, e estão nesta seção só porque as mudanças de CSS acima já a abriram.
  Enquanto o exame não tinha endereço, a janela mostrava os OITO achados de
  bancada deste gerador — *"Steam Input estava ligado em 2 jogos — desliguei"*,
  *"Proton fixado em 9.0-4 para 3 jogos"*, *"8 linhas · nenhum aviso"*. Nenhum
  aconteceu: o `storm_report` desta máquina devolve **seis**, e outros seis.

**Publicar as duas:** `scripts/check_o_desenho_aprovado.py --publicar 09`.
## 05-vibracao.html
- **02/09/2026** — **nada muda na tela; muda o ENDEREÇO.** São 14 linhas, todas
  de atributo — nenhuma cor, nenhum texto, nenhuma medida. Duas coisas:
  - cada coluna ganhou `data-controle="pN"` (as quatro, viva e vazia). Sem ele o
    pintor não achava onde pôr os valores daquele controle **e** "Testar" e
    "Parar" chegavam sem dizer de quem foi o clique — medido no DOM: os quatro
    botões recusavam sempre, com o rato de verdade;
  - o par de endereços da linha "Personalizado" passou de `forca`/`forca-pct`
    para `mult`/`mult-pct`. O nome `forca` era o `data-papel` dos quatro degraus
    **e** o `data-campo` do número: o pintor escrevia `"balanceado"` dentro dos
    botões e apagava a linha inteira. Está fotografado em `/tmp/antes-05.png`.

  **O que o produto ganha quando você publicar:** a coluna passa a dizer o
  controle que está ali (hoje diz `P1 • Cosmic Red • USB` com o P1 no rádio), o
  "Personalizado" passa a mostrar o multiplicador de verdade (70%, não 150% do
  desenho), os dois motores passam a dizer `—` quando ninguém pediu vibração em
  vez de `0` e `60`, e os quatro "Testar"/"Parar" passam a ter dono.

  O comando é `scripts/check_o_desenho_aprovado.py --publicar 05`, e é seu.
## 07-lancadores.html

- **02/09/2026** — ONDA F (`docs/process/sprints/2026-09-02-ROTA-F-a-aba-lancadores.md`).
  A aba era desenho inteiro: **0 gestos, 0 campos escritos**. Ela ganhou os
  endereços e o pacote (`interface/pacotes/a07_lancadores.py`).

  **Nenhuma caixa andou.** A grade, o CSS, os textos de ajuda e o lugar de cada
  botão continuam os que você aprovou (*"lançadores perfeito parabéns"*). O que
  mudou é **de onde vem o que está escrito dentro deles** — e três coisas
  aparecem na tela:

  1. **Os números da Steam saíram do teclado.** Medido na sua máquina, em 02/09,
     com `censo_do_wrapper` e `prontuario_dos_jogos` (leitura pura, nada
     escrito):

     | o cartão dizia | o produto responde |
     | --- | --- |
     | `412 jogos` | **23 jogos instalados** |
     | `◆ 3 jogos já sabem por onde entrar` | **0 pontes confirmadas** |
     | `5 encontrados · 1 com impedimento` | **1 lançador medível** |
     | `Heroic · 28 jogos · NÃO CHEGAM` | o produto **nunca olhou** o Heroic |

  2. **Nasceu um quarto selo: `NÃO SEI`** (mesmo cinza do `NÃO ACHEI`). Heroic,
     Lutris, Flatpak, RetroArch e Dolphin·mGBA passam a dizer que o produto
     ainda não sabe olhá-los. `CHEGAM` e `NÃO CHEGAM` eram as duas afirmações
     que ele não pode fazer sobre eles — `grep` nos cinco nomes em `src/`
     devolve **cinco linhas, todas comentário**. Zero função.

  3. **O cartão da Steam ganhou uma lista de jogos**, abaixo dos botões, com o
     nome de cada jogo que perdeu o atalho de inicialização e um botão
     `Não usar neste jogo` / `Voltar a usar`. Ela **nasce vazia e não ocupa um
     pixel** quando não há o que dizer — a mesma regra do carimbo. Ela existe
     porque o `jogos_sem_wrapper.txt` já era respeitado pelo produto inteiro e
     **nenhuma tela o escrevia**: a única forma de tirar um jogo era editar o
     arquivo à mão.

  **E ela já achou um defeito vivo na sua máquina, às 04h55 de 02/09:** o
  **PRAGMATA** perdeu as Opções de Inicialização do Hefesto — a linha dele está
  `VKD3D_CONFIG=no_upload_hvv %command%`, sem o atalho. É exatamente a
  regressão que a sentinela existe para nomear, e sem esta aba ela não aparecia
  em tela nenhuma. **O botão `Consertar` repõe preservando o `VKD3D_CONFIG`**
  (o `migrate_value` prepende), com a Steam fechada. **Não cliquei por você** —
  ele escreve no `localconfig.vdf`.

  **O que continua sem endereço, e é decisão:** `Abrir o lançador` (é
  `xdg-open`, não IPC) e `Criar perfil para um jogo` (é da aba Perfis — dois
  caminhos para o mesmo disco é como duas telas passam a discordar).
