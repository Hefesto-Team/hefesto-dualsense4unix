# Configuração do repositório no GitHub — execução humana

Este documento contém os comandos `gh` que requerem autenticação interativa do dono do repositório. Foram extraídos da sprint **FEAT-GITHUB-PROJECT-VISIBILITY-01** e marcados como **PROTOCOL_READY**: os arquivos de governança (`.github/*.md`, social preview) já estão MERGED; a configuração do GitHub em si precisa ser aplicada manualmente.

---

## Pré-requisitos

- `gh` autenticado no GitHub com escopo `repo` e `admin:org` (se aplicável).
- Usuário autenticado é dono ou admin de `AndreBFarias/hefesto`.

```bash
gh auth status
```

Deve mostrar `Logged in to github.com as AndreBFarias`.

---

## 1. Descrição do repositório (About)

Define a descrição de 1 linha (≤ 140 caracteres) exibida no topo da página do repositório e em resultados de busca do GitHub:

```bash
gh repo edit AndreBFarias/hefesto \
  --description "Daemon Linux para DualSense: gatilhos adaptativos, rumble, LEDs, perfis e emulação. Zero-dep, anônimo, PT-BR."
```

Valide:

```bash
gh repo view AndreBFarias/hefesto --json description --jq '.description'
```

---

## 2. Topics (até 20 keywords para descoberta)

Topics são a maior alavanca de descoberta orgânica no GitHub. A sprint definiu 20 topics cobrindo o domínio (DualSense, adaptive triggers, PS5), a stack (Python, GTK3, Textual), o packaging (Flatpak, AppImage, Debian) e a audiência (Linux, acessibilidade, PT-BR).

```bash
gh repo edit AndreBFarias/hefesto \
  --add-topic dualsense \
  --add-topic playstation-5 \
  --add-topic ps5-controller \
  --add-topic adaptive-triggers \
  --add-topic linux-gamepad \
  --add-topic gamepad-driver \
  --add-topic hidapi \
  --add-topic python-daemon \
  --add-topic gtk3 \
  --add-topic textual-tui \
  --add-topic udev-rules \
  --add-topic flatpak \
  --add-topic appimage \
  --add-topic debian-package \
  --add-topic cosmic-desktop \
  --add-topic gnome \
  --add-topic open-source \
  --add-topic portuguese-brazilian \
  --add-topic accessibility \
  --add-topic input-device
```

Valide:

```bash
gh repo view AndreBFarias/hefesto --json repositoryTopics \
  --jq '.repositoryTopics[].name'
```

Deve listar as 20 topics.

---

## 3. Homepage URL (opcional)

Se no futuro houver GitHub Pages ou site dedicado:

```bash
gh repo edit AndreBFarias/hefesto \
  --homepage "https://github.com/AndreBFarias/hefesto"
```

Ou, quando houver Pages:

```bash
gh repo edit AndreBFarias/hefesto \
  --homepage "https://andrebfarias.github.io/hefesto"
```

---

## 4. Social preview (og-image)

A imagem `docs/usage/assets/social-preview.png` (1280×640, gradiente Drácula + logo Hefesto + epígrafe) foi gerada pela sprint e commitada ao repositório.

**A API REST do GitHub não expõe upload de social preview.** A operação precisa ser feita pela interface web:

1. Abra `https://github.com/AndreBFarias/hefesto/settings`.
2. Role até a seção **Social preview**.
3. Clique em **Edit** → **Upload an image**.
4. Selecione o arquivo `docs/usage/assets/social-preview.png`.
5. Confirme. O card de preview será atualizado em alguns minutos (cache do GitHub e do Twitter/Discord/Slack pode levar mais tempo).

Valide compartilhando o link `https://github.com/AndreBFarias/hefesto` em um chat com preview automático (Discord, Slack, Telegram) — o card deve mostrar a imagem customizada.

---

## 5. Features opcionais do repositório

Habilitar/desabilitar features conforme decisão do dono. Default atual provavelmente já está adequado; ajuste se necessário:

```bash
# Habilitar Discussions (fórum de perguntas — complementa o template question)
gh repo edit AndreBFarias/hefesto --enable-discussions

# Habilitar Issues (deve já estar ativo)
gh repo edit AndreBFarias/hefesto --enable-issues

# Wiki — projeto pessoal raramente usa; manter desabilitado
gh repo edit AndreBFarias/hefesto --enable-wiki=false

# Projects — opcional para gerenciamento de sprints
gh repo edit AndreBFarias/hefesto --enable-projects
```

---

## 6. Branch protection (opcional, projeto pessoal)

Como `main` recebe auto-merge via pipeline local, branch protection rígida atrapalha mais que ajuda. Se quiser proteger apenas contra force-push acidental:

```bash
gh api -X PUT repos/AndreBFarias/hefesto/branches/main/protection \
  -f required_status_checks=null \
  -f enforce_admins=false \
  -f required_pull_request_reviews=null \
  -f restrictions=null \
  -F allow_force_pushes=false \
  -F allow_deletions=false
```

---

## Checklist de execução

Marcar conforme for aplicando:

- [ ] `gh auth status` confirmado.
- [ ] Descrição aplicada (`gh repo edit --description`).
- [ ] 20 topics aplicadas (`gh repo edit --add-topic`).
- [ ] Homepage URL definida (opcional).
- [ ] Social preview uploaded via web UI.
- [ ] Features ajustadas (Discussions opcional).
- [ ] Branch protection leve aplicada (opcional).

Após executar, atualize o status da sprint em `docs/process/SPRINT_ORDER.md` de `PROTOCOL_READY` para `MERGED`.

---

*"A forja não revela o ferreiro. Só a espada."*
