# Hotkeys do DualSense

O Hefesto reconhece atalhos nativos do DualSense detectados pelo daemon via
`HotkeyManager`. Todos os atalhos respeitam o buffer de 150 ms (V3-2) para
distinguir combos de toques isolados.

## Combos sagrados (troca de perfil)

| Combo            | Ação                                  |
|------------------|---------------------------------------|
| PS + D-pad cima  | Avança para o próximo perfil ativo    |
| PS + D-pad baixo | Volta para o perfil anterior          |

Política:

- Pressionar `PS` isolado atrasa qualquer repasse ao gamepad virtual (quando
  emulação uinput está ligada) por até **150 ms** para aguardar o segundo botão.
- Se o combo completo for detectado nesse buffer, o perfil troca e o PS **não**
  propaga ao jogo.
- Se o buffer expirar ou o D-pad nunca chegar, trata-se como **PS solo**
  (ver abaixo).

## Botão PS isolado (FEAT-HOTKEY-STEAM-01)

Quando `PS` é pressionado e solto sem que nenhum combo tenha disparado, o
daemon executa a ação configurada em `[hotkey.ps_button]` do `daemon.toml`.

### Modos suportados

```toml
[hotkey.ps_button]
# Valores: "steam" (padrão), "none", "custom"
action = "steam"

# Usado apenas quando action = "custom". Lista argv — nunca string shell.
custom_command = []
```

- **`steam`** (padrão): abre a Steam se ela não estiver rodando;
  se estiver, foca a janela principal (`WM_CLASS = steam.Steam`).
  Requer `steam` no PATH. Usa `pgrep -x steam` para detectar processo e
  `wmctrl -lx` / `wmctrl -ia <wid>` para focar. Nunca bloqueia o daemon —
  execução em thread worker dedicada.
- **`none`**: PS solo é ignorado (útil para quem quer preservar o botão
  home para outros usos via mapeamento externo).
- **`custom`**: executa `ps_button_command` via `subprocess.Popen` com
  `start_new_session=True` e stdio em `/dev/null`. Exemplo:
  `["xdg-open", "steam://open/bigpicture"]` abre o Big Picture Mode.

### Falhas silenciosas

- Se `steam` não existe no PATH, o daemon loga `steam_binary_not_found`
  uma vez e passa a ignorar futuras tentativas até reinício. Evita poluir
  logs com repetições.
- Se `wmctrl` não existe, loga `wmctrl_binary_not_found` e faz fallback
  para spawn (pode resultar em tentativas duplicadas do usuário, mas a
  Steam já trata múltiplas instâncias).
- Qualquer erro inesperado é capturado e logado como `warning` — o daemon
  nunca morre por causa do hotkey.

### Segurança

- `shell=True` **nunca** é usado. Toda chamada passa uma lista argv.
- Processo filho é desprendido via `start_new_session=True` — fechar o
  daemon não mata a Steam.
- stdin/stdout/stderr vão para `/dev/null` — nada vaza nos logs do daemon.

## Observações

- O combo sagrado tem **prioridade** sobre o PS solo: pressionar PS + D-pad
  em menos de 150 ms sempre troca perfil, nunca abre a Steam.
- O release do PS após um combo não dispara PS solo (suprimido internamente
  pelo `HotkeyManager`).
- Para desativar temporariamente, use `action = "none"` e recarregue o
  daemon com `hefesto daemon reload` (V1.2+).
