# Releases não publicados no GitHub — v1.0.0 até v2.1.0

**Data de registro:** 2026-04-23 durante a sprint `CHORE-CI-REPUBLISH-TAGS-01`.

## O que aconteceu

Entre 2026-04-21 (v1.0.0) e 2026-04-23 (v2.1.0) o workflow `.github/workflows/release.yml` abortava no gate `mypy src/hefesto` dentro do step "Instalar e testar". A falha ocorria antes dos jobs `appimage`, `deb`, `deb-install-smoke` e `github-release` rodarem — todos ficavam em `skipped`.

Consequência: cada tag publicada (`v1.0.0`, `v1.1.0`, `v1.2.0`, `v2.0.0`, `v2.1.0`) **não** produziu release real no GitHub. Nenhum `.whl`, `.tar.gz`, `.AppImage`, `.deb` ou `.flatpak` foi anexado. O único release publicado no período é `v0.1.0` (2026-04-21), anterior ao primeiro workflow quebrado.

O `.deb v2.1.0` foi buildado localmente (`dist/hefesto_2.1.0_amd64.deb`, SHA256 `db56770a2ead1afdc8836c3d5bba9b298792cebf8c3cd1d81184ac45bc321b60`) mas também não publicado.

## Fix raiz

Sprint `BUG-CI-RELEASE-MYPY-GATE-01` (2026-04-23) moveu `mypy` para um job `typecheck` com `continue-on-error: true` em `ci.yml`. `release.yml` ficou só com `ruff check` + `pytest tests/unit`. Débito típico marcado pra fechar em 30 dias via `CHORE-MYPY-CLEANUP-V22-01`.

Sprint `FEAT-CI-RELEASE-FLATPAK-ATTACH-01` (2026-04-23) adicionou job `flatpak` no `release.yml` para anexar o bundle `.flatpak` junto com os outros 4 formatos.

## Decisão sobre re-publicação das tags antigas

- **v2.0.0 e v2.1.0**: elegíveis a re-publicar via `gh workflow run release.yml -f tag=v2.1.0` (e idem v2.0.0). O workflow ganhou trigger `workflow_dispatch` nesta sprint com input `tag`, e os checkouts dos jobs usam `ref: ${{ github.event.inputs.tag || github.ref }}` para buildar a versão certa.
- **v1.0.0, v1.1.0, v1.2.0**: **não re-publicar** automaticamente. Risco de ressuscitar assets históricos que podem conter regressões fechadas em versões posteriores. Ficam como "histórico não empacotado" no GitHub — usuários devem baixar v2.x em diante.

## Execução

A re-publicação requer ação humana (decisão do dono do repo + autenticação `gh`). Comandos canônicos:

```bash
# Re-publica v2.0.0
gh workflow run release.yml -f tag=v2.0.0
gh run watch

# Re-publica v2.1.0
gh workflow run release.yml -f tag=v2.1.0
gh run watch

# Verifica assets após cada run verde
gh release view v2.1.0 --json assets --jq '.assets[].name'
# Esperado: hefesto-2.1.0-py3-none-any.whl, hefesto-2.1.0.tar.gz,
#           Hefesto-2.1.0-x86_64.AppImage, hefesto_2.1.0_amd64.deb,
#           br.andrefarias.Hefesto.flatpak
```

## Status

- [ ] v2.0.0 re-publicada (execução humana pendente).
- [ ] v2.1.0 re-publicada (execução humana pendente).
- [x] Infra pronta: `workflow_dispatch` com input `tag` + checkouts com `ref:` condicional.
- [x] Decisão sobre v1.x registrada (não re-publicar).

Sprint permanece em `PROTOCOL_READY` até as 2 execuções humanas serem registradas (operacionaliza L-21-6).
