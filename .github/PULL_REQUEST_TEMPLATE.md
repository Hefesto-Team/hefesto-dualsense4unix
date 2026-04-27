## Descrição

<!-- Resumo em PT-BR do que esta PR faz e por quê. Link para issue ou sprint: Closes #N ou refs SPRINT-ID. -->

## Tipo de mudança

- [ ] `feat` — funcionalidade nova
- [ ] `fix` — correção de bug
- [ ] `refactor` — refatoração sem mudança de comportamento
- [ ] `chore` — manutenção, tooling, infraestrutura
- [ ] `docs` — documentação
- [ ] `test` — apenas testes
- [ ] `polish` — ajustes de UI/UX sem lógica nova
- [ ] `release` — corte de release

## Escopo tocado

- [ ] Runtime (daemon, IPC, HID, UDP)
- [ ] GUI (GTK3)
- [ ] TUI (Textual)
- [ ] CLI (typer)
- [ ] Perfis e autoswitch
- [ ] Build / packaging (.deb, Flatpak, AppImage)
- [ ] CI / workflows
- [ ] Documentação

## Checklist de gates locais

- [ ] `.venv/bin/pytest tests/unit -q` passa (sem regressões).
- [ ] `.venv/bin/ruff check src/ tests/` sem violações.
- [ ] `.venv/bin/mypy src/hefesto_dualsense4unix` fecha com zero erros.
- [ ] `python3 scripts/validar-acentuacao.py --all` sem violações.
- [ ] `bash scripts/check_anonymity.sh` limpo (zero menção a IA, modelo, assistente, autor).
- [ ] Pre-commit rodou localmente sem bypass (`--no-verify` não usado).

## Proof-of-work runtime (se tocou runtime)

<!-- Cole output relevante: -->

```
# smoke USB
HEFESTO_DUALSENSE4UNIX_FAKE=1 HEFESTO_DUALSENSE4UNIX_FAKE_TRANSPORT=usb HEFESTO_DUALSENSE4UNIX_SMOKE_DURATION=2.0 ./run.sh --smoke

# (cole últimas linhas aqui)
```

## Evidência visual (se tocou UI/TUI/GUI)

- [ ] Screenshot anexada (PNG).
- [ ] `sha256sum` incluído.
- [ ] Descrição multimodal (3-5 linhas: elementos visíveis, acentuação PT-BR, contraste, comparação antes/depois).

## Impactos e riscos

<!-- Breve análise do que pode quebrar. Armadilhas conhecidas tocadas? Ver VALIDATOR_BRIEF.md seção Armadilhas. -->

## Notas para o revisor

<!-- Pontos de atenção, decisões questionáveis, alternativas consideradas. -->
