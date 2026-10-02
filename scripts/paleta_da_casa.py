"""paleta_da_casa.py — os tokens visuais que os artefatos HTML desta casa dividem."""
from __future__ import annotations

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
