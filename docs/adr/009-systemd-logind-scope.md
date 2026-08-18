# ADR-009: Escopo Linux — `systemd-logind` requerido

**Status:** aceito

## Contexto
As udev rules do projeto usam `TAG+="uaccess"` para dar ACL seletiva ao usuário da sessão ativa. Essa tag é processada pelo `systemd-logind`, que só existe em distros com systemd. Alternativas em distros sem systemd (Alpine OpenRC, Void runit, Gentoo/Artix com OpenRC) exigem ACL manual via `setfacl` ou `MODE="0666"` (inseguro: qualquer processo lê o controle).

## Decisão
v0.x e v1.x suportam oficialmente apenas distros com `systemd-logind`. README declara o requisito. PRs adicionando suporte a OpenRC/runit são bem-vindos mas o mainline não testa nem garante — seriam labels `P3-low`.

## Consequências
Cobre 99%+ dos usuários de DualSense em Linux (Pop!\_OS, Ubuntu, Fedora, Arch, Debian, Mint, etc.). Usuários de distros alternativas recebem mensagem clara em `install_udev.sh` ao invés de falha obscura no runtime. Reduz superfície de teste a uma única estratégia de permissão.
