"""paleta_da_casa.py — os tokens visuais que os artefatos HTML desta casa dividem.

Este módulo nasceu em 23/08/2026 para responder a um pedido dela: *"e sincronizar
ele com o specs.html também?"*, sobre o painel do plano. Sincronizar dois HTML
gerados por scripts diferentes só é verdade se a paleta tiver **um dono**; duas
cópias do mesmo hexadecimal divergem no dia em que alguém corrige uma delas.

Quem lê daqui (todos escrevem em ``html/``, desde 25/08/2026):
  - ``scripts/gerar-mapa.py``           → ``html/specs.html``  (o mapa de canais)
  - ``scripts/gerar-painel.py``         → ``html/painel.html`` (o estado do projeto)
  - ``scripts/gerar-frases-de-tela.py`` → ``html/frases-de-tela.html``
  - ``scripts/gerar-indice-html.py``    → ``html/index.html`` (a porta dos quatro)

A procedência que os quatro dividem — commit e hora — tem outro dono, o irmão
``scripts/carimbo_da_casa.py``, e pelo mesmo motivo escrito aqui.

**A REGRA QUE NÃO SE NEGOCIA: nada de fonte web.** O texto abaixo é o do
``gerar-mapa.py`` que a originou, e vale igual aqui: *"uma fonte que não carrega
transforma um instrumento numa página quebrada, e um instrumento que só funciona
com rede não serve para depurar rádio."* Os dois arquivos abrem com duplo
clique, sem servidor, sem venv e sem internet.

As cores são a paleta Drácula, a mesma que o produto usa no ``theme.css`` — o
artefato tem de parecer parte do Hefesto, não um site sobre ele.
"""
from __future__ import annotations

#: Os tokens, como bloco CSS pronto para entrar num ``<style>``.
#:
#: **Este texto é byte a byte o que estava em ``gerar-mapa.py`` até 23/08/2026.**
#: O ``--check`` daquele script compara CONTEÚDO da página gerada, então mudar
#: um único caractere aqui o deixa vermelho — que é exatamente o que se quer:
#: a paleta não muda por acidente.
TOKENS = """
:root {
  /* Paleta Drácula — a mesma que o produto usa em 82 lugares no código.
     O mapa tem de parecer parte do Hefesto, não um site sobre ele. */
  --color-paper:      #282a36;
  --color-paper-2:    #21222c;
  --color-paper-3:    #343746;
  --color-rule:       #44475a;
  --color-ink:        #f8f8f2;
  --color-ink-quiet:  #a8b0c8;
  --color-ink-faint:  #6272a4;
  --color-accent:     #bd93f9;   /* o literal que set_accent() já substitui */
  --color-ok:         #50fa7b;
  --color-lacuna:     #ffb86c;   /* a casa sabe e o produto não faz */
  --color-nulo:       #6272a4;
  --color-alerta:     #ff5555;
  --color-frio:       #8be9fd;

  /* Pilha do sistema: nada de fonte web, para o arquivo abrir sem rede. */
  --font-corpo: ui-sans-serif, system-ui, "Cantarell", "Segoe UI", Roboto, sans-serif;
  --font-dado:  ui-monospace, "JetBrains Mono", "Fira Mono", "DejaVu Sans Mono", monospace;

  --space-3xs: .25rem; --space-2xs: .5rem;  --space-xs: .75rem;
  --space-sm:  1rem;   --space-md:  1.5rem; --space-lg: 2.5rem;
  --space-xl:  4rem;   --space-2xl: 6rem;

  --text-xs: .75rem;  --text-sm: .8125rem; --text-base: .9375rem;
  --text-lg: 1.125rem; --text-xl: 1.5rem;  --text-2xl: 2rem;
  --text-display: clamp(2rem, 5vw, 3.25rem);

  --rule-hair: 1px;
  --radius-sm: 3px; --radius-md: 6px;
  --ease-out: cubic-bezier(.22,.61,.36,1);
  --dur-fast: 120ms; --dur-base: 200ms;
}
"""

__all__ = ["TOKENS"]
