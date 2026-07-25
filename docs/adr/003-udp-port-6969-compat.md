# ADR-003: UDP na porta 6969 para compatibilidade com DSX

**Status:** aceito

## Contexto
Mods existentes para Cyberpunk, Forza, Assetto Corsa escrevem em `127.0.0.1:6969` usando o schema JSON do DSX Windows. Rodando esses jogos via Proton, o mod envia pacotes do lado host-shared. Abandonar a porta quebra compatibilidade; reaproveitá-la mantém os mods funcionando sem modificação.

## Decisão
Escutar UDP em `127.0.0.1:6969` com o mesmo schema posicional do DSX v1. Porta configurável via `~/.config/hefesto/daemon.toml` para usuários que já tenham conflito. Validação com `pydantic` + discriminator. `version != 1` dropa com `log.warn` (V2 5.10).

## Consequências
Integração zero-config com mods. Mantém rate limit duplo (global 2000 pkt/s + per-IP 1000 pkt/s; V3-1). Schema v2 nomeado fica para v1.x+, sem pressa.

## Nota de verificação — 2026-07-25

A decisão continua válida na porta e no schema. **Uma frase dela nunca foi
verdade no código:** a porta UDP **não** é configurável por
`~/.config/hefesto/daemon.toml`. O daemon não lê arquivo de configuração nenhum
(ver `docs/usage/hotkeys.md`, seção "Onde a configuração dos hotkeys mora"); a
porta vive em `DaemonConfig` e só se altera por `daemon.reload` via IPC ou no
código. Aquele caminho `~/.config/hefesto/` também é o layout curto legado,
migrado para `~/.config/hefesto-dualsense4unix/`.

O rate limit citado (global 2000 pkt/s, per-IP 1000 pkt/s) foi conferido e
confere com `daemon/udp_server.py`.
