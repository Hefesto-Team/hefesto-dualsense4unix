# Contribuindo com o Hefesto - Dualsense4Unix

Obrigado pelo interesse em contribuir. Este é um projeto pessoal com ciclo de desenvolvimento próprio, mas contribuições externas são bem-vindas desde que sigam os protocolos descritos aqui.

---

## Natureza do projeto

Hefesto - Dualsense4Unix é um **projeto pessoal** mantido em regime de anonimato pelo autor. O fluxo interno de desenvolvimento usa um pipeline de sprints automatizadas com auto-merge em `main` sem PR formal — esse é o modo normal de operação.

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

O projeto organiza trabalho em **sprints**. Cada sprint tem:

- ID canônico (`FEAT-*`, `BUG-*`, `REFACTOR-*`, `CHORE-*`, `DOCS-*`, `INFRA-*`, `AUDIT-*`).
- Spec própria com contexto, decisão, critérios de aceite e proof-of-work.
- Status: `PLANNED`, `READY`, `IN_PROGRESS`, `MERGED`, `PROTOCOL_READY`, `SUPERSEDED`.

As specs e o índice de status vivem no arquivo de processo, fora da `main` (ver
"Arquivo de processo" no fim deste documento).

Para contribuir:

1. Identifique ou proponha uma sprint com ID claro.
2. Use `gh issue develop N --checkout` se houver issue correspondente.
3. Implemente seguindo o spec; não expanda escopo sem registrar achado colateral.
4. Se tocar runtime (HID, daemon, IPC), prove via smoke real: `./run.sh --smoke`.
5. Se tocar UI/TUI/GUI, anexe screenshot + sha256 + descrição multimodal.
6. Se descobrir algo não-óbvio, registre: ADR em `docs/adr/` quando muda arquitetura, nota em `docs/research/` quando é medição.

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

## A língua do produto

**Decisão de 07/08/2026: o português do Brasil é a língua do Hefesto.** Ele não
é a língua de partida de um produto multilíngue à espera de tradutores; é a
língua em que o produto está escrito, e é assim que ele é entregue.

Até esta data, esta página trazia uma receita completa de como um voluntário
acrescentaria o francês ou o espanhol. **O convite era falso**, e o motivo é
medido: dos **18** módulos de
`src/hefesto_dualsense4unix/app/actions/` — que são os que escrevem o texto vivo
das abas, o que a janela diz enquanto roda —, **15** não importam a função de
tradução e carregam, juntos, **561** literais com acentuação portuguesa. Quem
traduzisse os catálogos inteiros veria o esqueleto fixo mudar de idioma e o
recado da janela continuar em português.

**Grau: MEDIDO** em 07/08/2026, por leitura de AST dos 18 arquivos (**19**
desde 08/08, com o `relancar.py` da `RELANCAR-01`): conta-se
quem importa `_` de `hefesto_dualsense4unix.utils.i18n` (ou `gettext`) e quem
tem literal com caractere acentuado. Só `footer_actions.py`,
`lightbar_actions.py` e `status_actions.py` importam. O portão que guarda esta
decisão refaz essa mesma contagem a cada rodada — ver abaixo.

### O encanamento de i18n continua vivo, e de propósito

Nada de i18n foi removido: `po/en.po`, `po/pt_BR.po`, `scripts/i18n_extract.sh`,
`scripts/i18n_compile.sh`, `src/hefesto_dualsense4unix/utils/i18n.py` e os 308
`translatable="yes"` de `gui/main.glade` continuam onde estavam, funcionando. O
encanamento está **correto**; o que não existe é o texto passando por ele.

Removê-lo para "ficar coerente" seria destruir trabalho bom para provar um
ponto — e é exatamente o que esta casa não faz. Quem for mexer em i18n mexe
para **ligar** o encanamento às telas, não para arrancá-lo.

### Quando o convite pode voltar

Quando a contagem acima chegar a zero, ou seja: quando nenhum módulo de
`app/actions/` escrever prosa em português fora da função de tradução. Aí o
convite passa a ser verdadeiro, e o portão para de reprová-lo sozinho — sem que
ninguém precise editar o teste.

Enquanto isso, **nenhuma página que ensina** (`README.md`, `docs/usage/`,
`docs/adr/`, `docs/protocol/` e esta) pode trazer a receita de volta. Há
portão: `tests/unit/test_lingua_do_produto_01_o_convite_a_traduzir.py`.

### O vocabulário que fica em inglês dentro do português

Isto é decisão de produto, não convenção de tradutor, e continua valendo:

| termo | por quê |
|---|---|
| `lightbar` | nome Sony do componente; não tem tradução consagrada |
| `rumble` | nome Sony da vibração; idem |
| `daemon` | termo técnico Unix, e é como o próprio serviço se chama |

Fora esses, a regra é a da casa: **português do Brasil, com acentuação
correta**, em código, comentário, documentação e mensagem de commit. Há portão
(`scripts/validar-acentuacao.py`).

Registro completo desta decisão, com o que foi medido e o que ficou aberto:
`docs/process/sprints/2026-08-07-LINGUA-DO-PRODUTO-01-o-convite-a-traduzir-era-falso.md`.

---

## Dúvidas

Abra uma issue com o template `question` ou consulte:

- `docs/adr/` — Architecture Decision Records.
- `docs/usage/quickstart.md` — uso da ferramenta.
- `docs/research/` — pesquisas e medições.

---

## Arquivo de processo

Sprints, estudos, diário de descobertas, decisões V1/V2/V3 e roadmap interno
**não ficam na `main`** — são material de processo, preservado inteiro na tag
`arquivo/processo-pre-1.0`. Todo caminho `docs/process/...` citado em
comentários, docstrings ou docs deste repositório se resolve por ali:

```bash
git show arquivo/processo-pre-1.0:docs/process/SPRINT_ORDER.md
git checkout arquivo/processo-pre-1.0 -- docs/process
```

---

*"A forja não revela o ferreiro. Só a espada."*
