## O que muda

<!-- O que esta mudança faz e por quê. Se houver issue: Closes #N. -->

## Tipo de mudança

- [ ] `feat`: funcionalidade nova
- [ ] `fix`: correção de defeito
- [ ] `refactor`: reorganização sem mudança de comportamento
- [ ] `chore`: manutenção, ferramentas, infraestrutura
- [ ] `docs`: documentação
- [ ] `test`: só testes

## Onde mexe

- [ ] Serviço (daemon, IPC, HID, UDP)
- [ ] Janela
- [ ] Interface de terminal
- [ ] Linha de comando
- [ ] Perfis e troca automática
- [ ] Instalador e pacotes (.deb, Flatpak, AppImage, Arch, Fedora, Nix)
- [ ] CI e GitHub
- [ ] Documentação

## Antes de pedir a revisão

- [ ] O autor dos commits está no `.mailmap` e os commits estão assinados (veja o [CONTRIBUTING](CONTRIBUTING.md)).
- [ ] `.venv/bin/ruff check src/ tests/` sem apontamentos.
- [ ] `.venv/bin/mypy src/hefesto_dualsense4unix` sem erros.
- [ ] `bash scripts/rodar-a-suite.sh` sem falhas.
- [ ] A mudança vale para o cabo e para o Bluetooth, e para um a quatro controles.
- [ ] O pre-commit rodou, sem `--no-verify`.

## Como testei

<!-- O que você rodou e o que viu. Se tocou o serviço, cole o fim da saída de `./run.sh --smoke`. Se tocou a janela, anexe um print de antes e de depois. -->
