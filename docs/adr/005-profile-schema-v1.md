# ADR-005: Schema de perfil v1

## Contexto
Perfis precisam: identificar-se (nome), declarar contra qual janela casam (match), e configurar triggers + LEDs + rumble. Opções de matcher: AND total, OR total, híbrido. DSX Windows não serve de referência (UI-driven, não serializado).

## Decisão
Schema JSON versionado (`version: 1`) validado com pydantic v2. Semântica do matcher:
- AND entre campos preenchidos.
- OR dentro de cada lista (`window_class: ["a", "b"]` casa qualquer).
- Fallback via sentinel `MatchAny` explícito (V2-8), não via campos vazios — evita wildcard silencioso por engano.
- `window_title_regex` usa `re.search` (V2-10), permite `.*Cyberpunk.*` e `Cyberpunk` indistintamente.
- `process_name` casa com `basename` de `/proc/PID/exe` (V2-9), não `/proc/PID/comm` (trunca em 15 chars).

Prioridade numérica quebra empates; `fallback.json` tem `priority: 0` e `match: {"type": "any"}`.

## Consequências
Criador de perfil precisa decidir explicitamente entre matcher e fallback. Matcher truncado silenciosamente sempre casa → forçamos declaração. Basename do exe casa com o que o usuário vê no `ps` sem truncamento. Regex simples não exige `.*` nas pontas.
