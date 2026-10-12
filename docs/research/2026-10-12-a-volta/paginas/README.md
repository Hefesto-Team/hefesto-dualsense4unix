# As páginas da volta (12/10/2026)

As páginas que serviram à leva da volta, guardadas em versão estática. Abra o `index.html` de cada pasta direto no
navegador. A página do todo salva sozinha a cada marcação (voto, escolha ou letra de comentário) no servidor de
`127.0.0.1:8766` (`~/.local/state/hefesto-casa/leva-volta/pagina/servir.py`), que grava o `respostas.json` de lá e a
marcação embutida neste `index.html`; com o servidor fora do ar, ela guarda no navegador e manda quando ele voltar. O
botão «Só o que falta» esconde o que já tem voto ou escolha.

| página | o que mostra | fonte viva |
| --- | --- | --- |
| [todo-das-abas/](todo-das-abas/index.html) | os mockups do todo: as dez abas e as janelas com todos os ajustes de tela das sprints juntos, o publicado (depois do fecho da 1-11) ao lado do todo, e uma foto de estado de cada mudança que a foto da aba não mostra | `~/.local/state/hefesto-casa/leva-volta/todo/` e `pagina/` |
| [plano-do-fim.html](plano-do-fim.html) | o inventário das sprints (fechadas, costuradas fora do `dev`, cortadas na metade, por fazer) e as 16 ondas até a fila zerar, com filtro por setor e estado | `leva-volta/plano/PLANO-DO-FIM.md` (cópia ao lado) |

Os mockups do todo ainda esperam a escolha final: os ajustes desta página não estão no produto. A direção segue
`mockup/` → produto.
