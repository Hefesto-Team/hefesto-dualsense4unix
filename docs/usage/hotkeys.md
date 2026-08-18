# Hotkeys do DualSense

O Hefesto - Dualsense4Unix reconhece atalhos nativos do DualSense detectados pelo daemon via
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

## Onde a configuração dos hotkeys mora (leia antes)

**O daemon não lê `daemon.toml`.** O arquivo que a aba Emulação abre no botão
"Ver daemon.toml (referência)" é só isso — referência. Ele nasce com um
cabeçalho dizendo exatamente o mesmo, e nada nele chega ao daemon.

A configuração efetiva vem de duas fontes, e só delas:

1. **Variáveis de ambiente lidas na subida do daemon** — hoje são três:
   `HEFESTO_DUALSENSE4UNIX_POLL_HZ`, `HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS`
   e `HEFESTO_DUALSENSE4UNIX_NICE`.
2. **O método IPC `daemon.reload`**, que aceita `config_overrides` com qualquer
   subconjunto dos campos de `DaemonConfig` e aplica em tempo de execução:

   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"daemon.reload",
          "params":{"config_overrides":{"ps_button_action":"none"}}}' \
     | nc -U "$XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock"
   ```

   Overrides feitos assim são **transitórios**: valem até o daemon reiniciar.
   Não há hoje persistência em disco para eles.

Os nomes dos campos são os do `DaemonConfig` (`ps_button_action`,
`ps_button_command`, `ps_long_press_ms`, …) — não os nomes de seção TOML que
apareciam nas versões anteriores desta página.

## Botão PS isolado (FEAT-HOTKEY-STEAM-01)

Quando `PS` é pressionado e solto sem que nenhum combo tenha disparado, o
daemon executa a ação de `ps_button_action`.

### Modos suportados

`ps_button_action` aceita `"steam"` (padrão), `"none"` ou `"custom"`; com
`"custom"`, `ps_button_command` é a lista argv a executar — nunca uma string de
shell.

- **`steam`** (padrão): abre a Steam se ela não estiver rodando;
  se estiver, foca a janela principal (`WM_CLASS = steam.Steam`).
  Requer `steam` no PATH. Usa `pgrep -x steam` para detectar processo e
  `wmctrl -lx` / `wmctrl -ia <wid>` para focar. Nunca bloqueia o daemon —
  execução em thread worker dedicada.
- **`none`**: PS solo é ignorado (útil para quem quer preservar o botão
  home para outros usos via mapeamento externo).
- **`custom`**: executa a lista `ps_button_command` via `subprocess.Popen` com
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

## Modo jogo — combo PS + Options

O "modo jogo" alterna a supressão da emulação de mouse/teclado do daemon,
mantendo os **combos de troca de perfil ativos** — para o gesto continuar
funcionando e conseguir reativar a emulação depois.

| Gesto | Ação |
|-------|------|
| PS (toque curto) | Ação `[hotkey.ps_button]` — default `steam` |
| **PS + Options** | Modo jogo on/off — suprime/restaura emulação de mouse/teclado |
| PS + D-pad ↑/↓ | Troca de perfil (combo sagrado) |

**Por que não é mais o long-press.** O gesto original era segurar o PS por ~1 s
(FEAT-EMULATION-GAMEMODE-LONGPRESS-01, v3.8.1). Ele provocava modo jogo
**acidental**: o toque de abrir a Steam que passasse de um segundo alternava o
modo sem ninguém pedir. Hoje o padrão é `ps_long_press_ms = 0` — o gesto vem
**desligado** — e o modo jogo é o combo deliberado PS + Options
(FEAT-EMULATION-GAMEMODE-COMBO-01).

**Diferenças entre os gestos do PS:**

- O combo (PS + outro botão) dispara primeiro — long-press e PS solo ficam suprimidos.
- O PS solo só dispara no release, e só se nenhum combo já tiver disparado.

**Configuração:** o limiar do long-press é `ps_long_press_ms` (ms). Padrão `0` =
gesto desligado; valor maior que zero traz o gesto de volta, com o risco de
acionamento acidental. É o único campo de hotkey com variável de ambiente
própria:

```bash
HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS=1000 \
  systemctl --user restart hefesto-dualsense4unix.service
```

**Estado do modo jogo via IPC** (útil para GUI/applet/CLI custom):

```bash
# Consulta — o campo `emulation_suppressed` vem do método IPC `daemon.status`.
# Atenção: `hefesto-dualsense4unix daemon status` NÃO serve aqui — esse
# subcomando imprime a saída do `systemctl --user`, não o JSON do daemon.
echo '{"jsonrpc":"2.0","id":1,"method":"daemon.status","params":{}}' \
  | nc -U "$XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock"

# Alternar (espelha o gesto)
echo '{"jsonrpc":"2.0","id":1,"method":"daemon.emulation.suppress","params":{}}' \
  | nc -U "$XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock"

# Definir explicitamente
# params: {"suppressed": true}  ou  {"suppressed": false}
```

Notifica via D-Bus (`org.freedesktop.Notifications`) em ambas as transições — feedback necessário
porque a ação é deliberada (sem visual, o usuário não saberia se o gesto pegou). O estado é
**transitório**: não persiste entre boots — a emulação volta ao estado da config no próximo
restart do daemon.

## Observações

- O combo sagrado tem **prioridade** sobre o PS solo: pressionar PS + D-pad
  em menos de 150 ms sempre troca perfil, nunca abre a Steam.
- O release do PS após um combo não dispara PS solo (suprimido internamente
  pelo `HotkeyManager`).
- Para desativar temporariamente o PS solo, mande
  `{"ps_button_action":"none"}` em `config_overrides` do `daemon.reload` (ver a
  primeira seção). **Não existe** `hefesto-dualsense4unix daemon reload` na
  linha de comando — só o método IPC.
- O combo PS + Options é independente da ação configurada para o PS solo — ele
  funciona mesmo com `ps_button_action = "none"`.
