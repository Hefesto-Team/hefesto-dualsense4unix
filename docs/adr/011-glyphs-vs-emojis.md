# ADR-011: Glyphs Unicode de estado são preservados; emojis gráficos são proibidos

## Contexto

A regra universal do projeto proíbe emojis em código, commits e docs. A regra existe para manter tom técnico e evitar assinatura cultural. Em 2026-04-21 um diff interpretou "zero emojis" como "zero caracteres não-ASCII" e strippou BLACK CIRCLE (U+25CF), WHITE CIRCLE (U+25CB), BLACK VERTICAL RECTANGLE (U+25AE) e WHITE VERTICAL RECTANGLE (U+25AF) de markups Pango e do `BatteryMeter` da TUI, quebrando indicadores de status visuais da GUI e zerando a barra de bateria textual. O teste correspondente foi adaptado para a regressão (`assert == ""`), escondendo o bug.

## Decisão

Distinção canônica baseada no bloco Unicode:

- **Proibidos**: caracteres do bloco Emoji_Presentation (U+1F000+ pictográficos, U+2700+ coloridos como HEAVY CHECK MARK U+2705, CROSS MARK U+274C, PARTY POPPER U+1F389). São decoração cultural, violam o tom do projeto e são bloqueados pelo hook `guardian.py`.
- **Permitidos**: Geometric Shapes (U+25A0–U+25FF), Block Elements (U+2580–U+259F), Box Drawing (U+2500–U+257F), Arrows (U+2190–U+21FF). São UI textual funcional. Exemplos canônicos usados no projeto: BLACK/WHITE CIRCLE nos headers Pango, BLACK/WHITE VERTICAL RECTANGLE no `BatteryMeter`, CIRCLE WITH LEFT HALF BLACK (U+25D0) no estado "reconectando".

Para docs: quando semântica OK/ERRO for necessária, usar texto literal `OK:` / `ERRADO:` — jamais reintroduzir HEAVY CHECK MARK ou CROSS MARK.

`scripts/check_anonymity.sh` e o hook `guardian.py` cobrem os proibidos. Validação de preservação dos permitidos é responsabilidade do validador-sprint: em qualquer diff tocando `*_actions.py`, `tui/widgets/`, ou `main.glade`, scanear deleções de U+25CF, U+25CB, U+25AE, U+25AF, U+25D0 antes de aprovar.

## Consequências

(+) Regra sai do campo subjetivo ("é emoji?") para o objetivo ("está em Emoji_Presentation?").
(+) UI textual funcional (barras de progresso, indicadores de estado, frames de TUI) permanece expressiva sem violar a regra.
(+) Teste `test_tui_widgets.test_icon_bateria_varia_com_nivel` serve de regressão permanente para o `BatteryMeter`.
(−) Novos contribuidores precisam internalizar a distinção. `VALIDATOR_BRIEF.md` A-04 registra o precedente como ancoragem.
