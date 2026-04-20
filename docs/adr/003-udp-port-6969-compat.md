# ADR-003: UDP na porta 6969 para compatibilidade com DSX

## Contexto
Mods existentes para Cyberpunk, Forza, Assetto Corsa escrevem em `127.0.0.1:6969` usando o schema JSON do DSX Windows. Rodando esses jogos via Proton, o mod envia pacotes do lado host-shared. Abandonar a porta quebra compatibilidade; reaproveitá-la mantém os mods funcionando sem modificação.

## Decisão
Escutar UDP em `127.0.0.1:6969` com o mesmo schema posicional do DSX v1. Porta configurável via `~/.config/hefesto/daemon.toml` para usuários que já tenham conflito. Validação com `pydantic` + discriminator. `version != 1` dropa com `log.warn` (V2 5.10).

## Consequências
Integração zero-config com mods. Mantém rate limit duplo (global 2000 pkt/s + per-IP 1000 pkt/s; V3-1). Schema v2 nomeado fica para v1.x+, sem pressa.
