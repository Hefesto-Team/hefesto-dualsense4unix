# Quando estas imagens foram conferidas pela última vez

Este arquivo existe porque o portão `test_as_fotos_nao_ficam_atras_do_codigo_da_tela`
compara **commits**, não bytes: ele pergunta se o último commit que tocou
`docs/usage/assets` é mais novo que o último que tocou o código da tela.

Isso deixa um estado sem saída: quando o código da tela muda mas **o desenho
não**, `retratar_abas.py` produz imagens idênticas às que já estão versionadas,
o git não tem o que commitar, e o portão fica vermelho para sempre — mesmo com
a conferência feita e o resultado correto.

Não é falso positivo: o portão está certo em exigir a conferência. O que faltava
era um lugar para **registrar que ela aconteceu**. É este arquivo.

## Como usar

Rode `scripts/gui-captura/retratar_abas.py`. Se as imagens mudarem, commite-as —
e a mudança de desenho é palavra dela, não de quem tirou a foto
([PROVA-DE-TELA-01](../../process/sprints/2026-07-27-PROVA-DE-TELA-01-dez-minutos-de-olho-antes-de-qualquer-leva.md)).
Se **não** mudarem, acrescente uma linha aqui embaixo e commite este arquivo: o
portão volta ao verde e fica escrito quem conferiu, quando, e contra qual commit.

## O registro

| data | commit do código conferido | resultado |
|---|---|---|
| 15/08/2026 | `9441678` — a numeração dos jogadores | **10 abas, todas idênticas.** O commit mexeu na fonte do número do jogador (`coop.py`, `ipc_handlers.py`), que é dado e não desenho: nenhum pixel mudou. Conferido rodando `retratar_abas.py` e comparando com `git status docs/usage/assets/` — zero arquivos diferentes. |
| 18/08/2026 | `afe9ba7` — o rodapé que saía pela borda, mais a leva do microfone no perfil e a guarda do foco errante | **10 abas, todas idênticas.** O commit de ontem mexeu no orçamento de altura do rodapé (`controller_card.py`, `main.glade`) e a leva de hoje acrescentou o escritor do microfone no rascunho (`controller_card.py`, `draft_config.py`) — dado e fiação, não desenho. Conferido rodando `retratar_abas.py`: `git status docs/usage/assets/` voltou vazio, zero arquivos diferentes. |
