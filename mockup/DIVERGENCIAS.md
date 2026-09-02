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
