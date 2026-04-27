# Contribuindo com o Hefesto - Dualsense4Unix

Obrigado pelo interesse em contribuir. Este é um projeto pessoal com ciclo de desenvolvimento próprio, mas contribuições externas são bem-vindas desde que sigam os protocolos descritos aqui.

---

## Natureza do projeto

Hefesto - Dualsense4Unix é um **projeto pessoal** mantido em regime de anonimato pelo autor. O fluxo interno de desenvolvimento usa um pipeline de sprints automatizadas (ver `docs/process/SPRINT_ORDER.md`) com auto-merge em `main` sem PR formal — esse é o modo normal de operação.

**Contribuições externas de pessoas desconhecidas passam por revisão manual antes do merge.** Não há prazo garantido de resposta, mas toda PR bem documentada será lida.

Se sua intenção é uma mudança grande, abra uma issue primeiro descrevendo o problema/proposta antes de investir tempo em código. Isso evita retrabalho.

---

## Preparação de ambiente

Script idempotente que garante `.venv/` viva e dependências corretas:

```bash
bash scripts/dev-setup.sh
```

Na primeira clonagem, use o bootstrap completo:

```bash
bash scripts/dev_bootstrap.sh              # base
bash scripts/dev_bootstrap.sh --with-tray  # inclui PyGObject + GTK3 (para GUI)
```

Ative o pre-commit antes do primeiro commit:

```bash
pip install pre-commit
pre-commit install
```

O pre-commit bloqueia:

- Acentuação PT-BR faltando (`acao`, `funcao`, `descricao`, `configuracao`, etc.).
- Menção a IA, modelo, assistente ou similares (anonimato).
- Falha de `ruff check`.
- Emojis gráficos em commits, docs e código.

Glyphs Unicode de estado (`U+25CF BLACK CIRCLE`, `U+25CB WHITE CIRCLE`, box drawing, block elements) são permitidos — fazem parte da UI textual.

---

## Rodando os gates locais

Antes de qualquer commit:

```bash
# Testes unitários
.venv/bin/pytest tests/unit -q

# Lint
.venv/bin/ruff check src/ tests/

# Tipagem (gate rígido)
.venv/bin/mypy src/hefesto_dualsense4unix

# Acentuação periférica
python3 scripts/validar-acentuacao.py --all

# Anonimato
bash scripts/check_anonymity.sh
```

Se algum falhar, corrija antes de seguir. Não use `--no-verify` para bypassar hooks.

---

## Fluxo de sprint

O projeto organiza trabalho em **sprints** rastreadas em `docs/process/SPRINT_ORDER.md`. Cada sprint tem:

- ID canônico (`FEAT-*`, `BUG-*`, `REFACTOR-*`, `CHORE-*`, `DOCS-*`, `INFRA-*`, `AUDIT-*`).
- Spec em `docs/process/sprints/<ID>.md` com contexto, decisão, critérios de aceite e proof-of-work.
- Status: `PLANNED`, `READY`, `IN_PROGRESS`, `MERGED`, `PROTOCOL_READY`, `SUPERSEDED`.

Para contribuir:

1. Identifique ou proponha uma sprint com ID claro.
2. Use `gh issue develop N --checkout` se houver issue correspondente.
3. Implemente seguindo o spec; não expanda escopo sem registrar achado colateral.
4. Se tocar runtime (HID, daemon, IPC), prove via smoke real: `./run.sh --smoke`.
5. Se tocar UI/TUI/GUI, anexe screenshot + sha256 + descrição multimodal.
6. Se descobrir algo não-óbvio, registre em `docs/process/discoveries/`.

---

## Convenção de commit

PT-BR acentuado, sem emojis, sem menção a IA.

Formato:

```
<tipo>: <ID-SPRINT> — <descrição curta imperativa>

<corpo opcional explicando o porquê>
```

Tipos: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `polish`, `release`.

Exemplo:

```
feat: FEAT-LED-BRIGHTNESS-03 — handler GUI persiste brightness no state

Slider de luminosidade agora sincroniza com state_full via guard anti-loop;
valor é incluído no JSON salvo pelo editor.
```

Squash merge ao fechar PR externa; mensagem final segue o mesmo padrão.

---

## Protocolo anti-débito

Achado colateral durante implementação **não é corrigido silenciosamente**. Opções válidas:

1. **Edit-pronto:** patch separado com ID novo (`BUG-<NN>`), commit isolado.
2. **Sprint-nova:** abra issue ou arquivo de spec descrevendo o achado; deixe o fix para o próximo ciclo.

Nunca use `# TODO` ou `# FIXME` como substituto de spec. Débitos silenciosos quebram a rastreabilidade do projeto.

---

## Anonimato

O autor mantém anonimato absoluto. Contribuições devem respeitar:

- Nenhum arquivo (código, doc, commit message) menciona o autor por nome próprio completo.
- E-mail de contato público é `andre.dsbf@gmail.com` (já presente nos commits históricos).
- Nenhum crédito é devido a assistentes de IA; menções são bloqueadas pelo pre-commit.

Se sua PR expõe dados pessoais de terceiros por engano, avise imediatamente para reescrita do histórico.

---

## Dúvidas

Abra uma issue com o template `question` ou consulte:

- `AGENTS.md` — protocolo do repo.
- `docs/process/HEFESTO_DECISIONS_V2.md` e `HEFESTO_DECISIONS_V3.md` — decisões consolidadas.
- `docs/adr/` — Architecture Decision Records.
- `docs/usage/quickstart.md` — uso da ferramenta.

---

*"A forja não revela o ferreiro. Só a espada."*
