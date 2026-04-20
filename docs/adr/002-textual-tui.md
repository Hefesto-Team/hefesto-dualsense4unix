# ADR-002: TUI com Textual

## Contexto
Opções para interface terminal: `curses` puro, `urwid`, `textual`, `blessed`. `textual` tem API declarativa moderna, async-first, temas CSS-like, ecossistema ativo e mesma stack já adotada em outros projetos do autor.

## Decisão
Usar `textual >= 0.47` como framework da TUI. Tema Dracula por padrão.

## Consequências
Stack unificada. Animações e widgets avançados disponíveis de graça (bars, data tables, modals). Dependência robusta mas não stdlib — requer `pip install`. `mypy strict` reclama de stubs incompletos; suprimido via `[[tool.mypy.overrides]]`.
