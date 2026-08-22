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

1. **Variáveis de ambiente lidas na subida do daemon** — hoje são seis, todas
   em `daemon/main.py`:
   `HEFESTO_DUALSENSE4UNIX_POLL_HZ`, `HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS`,
   `HEFESTO_DUALSENSE4UNIX_KEYBOARD_EMULATION`, `HEFESTO_DUALSENSE4UNIX_NICE`,
   `HEFESTO_DUALSENSE4UNIX_FAKE` e `HEFESTO_DUALSENSE4UNIX_FAKE_TRANSPORT`.

   As duas últimas são o backend falso (teste e desenvolvimento, sem hardware),
   não configuração de uso. A terceira,
   `HEFESTO_DUALSENSE4UNIX_KEYBOARD_EMULATION`, nasceu em 29/07 com a
   EMULACAO-NO-JOGO-01 e é o desligador do teclado emulado — `=0` desliga,
   qualquer outro valor mantém ligado. Esta página a omitia até 01/08 e
   afirmava "hoje são três" (DOC-VERDADE-02, E7). A precedência dela, do mais
   fraco ao mais forte: default do `DaemonConfig` < esta variável <
   `keyboard_emulation.flag`, que é a escolha registrada na janela e vence
   sempre.
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
| **PS + R3** | **Próxima ponte** — DualSense → Xbox 360 → mouse+teclado (ver a seção abaixo) |
| **L3 / R3** | Abre / fecha o **teclado na tela** (ver a seção abaixo) |

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

> **NOTA DATADA — 09/08/2026: "transitório" continua verdade para o GESTO, e
> deixou de ser toda a história.** O combo PS + Options segue sem persistir. O
> que mudou é que a **janela** passou a guardar o modo jogo: o interruptor da
> aba Emulação escreve no rascunho e o **Salvar Perfil** do rodapé o persiste em
> `suppress_desktop_emulation`, **inclusive** em perfil "Vale sempre" — a recusa
> que existia nesse caso caiu por decisão dela, *"a vontade na GUI prevalece
> sempre"*. Num perfil "Vale sempre" o valor fica guardado no arquivo mas o
> daemon **não o liga sozinho** na ativação seguinte, e é isso que impede o
> desktop de acordar sem ponteiro depois de um boot. O campo e o preço estão em
> [`creating-profiles.md`](creating-profiles.md#seção-opcional-mouse-e-suppress_desktop_emulation).

## Próxima ponte — combo PS + R3

**Ponte** é a forma como o jogo enxerga o controle. O gesto **PS + R3** troca de
ponte sem fechar o jogo, em ciclo: **DualSense → Xbox 360 → mouse+teclado →
DualSense**. Ele vem **ligado de fábrica** (FEAT-HOTKEY-PONTE-CYCLE-01).

**O R3 sozinho continua fechando o teclado na tela** — é o PS *junto* com o R3
que troca a ponte. Os dois não brigam: o latch de combo
(FEAT-HOTKEY-COMBO-NO-LEAK-02) segura o R3 até todos os botões serem soltos, e o
combo só dispara com PS e R3 pressionados **juntos** por mais de 150 ms
(`buffer_ms`). Acionar por acidente é difícil; acionar **sem saber o que se
fez** é fácil, e é por isso que esta seção existe.

**O produto avisa pela lightbar** — o único canal visível sem sair do jogo. As
cores saem da paleta da janela, não são inventadas aqui:

| Cor da barra | O que ficou de pé |
|---|---|
| **rosa** `#ff79c6` | ponte **DualSense** (o Hefesto na frente) |
| **verde claro** `#50fa7b` | ponte **Xbox 360** |
| **laranja** `#ffb86c` | ponte **mouse+teclado** |
| **azul claro** `#8be9fd` | **Steam Input** (não entra no ciclo do gesto) |
| **branco** `#f8f8f2` | **Modo Nativo** (não entra no ciclo do gesto) |
| **dois pulsos vermelhos**, antes de aplicar | "isto pode derrubar o controle dentro do jogo" |
| dois pulsos vermelhos **+ um vermelho longo** | "pedi a ponte e não consegui" — o vpad não subiu |

**O preço, que foi medido (R-04):** trocar de ponte **destrói e recria o vpad**,
e isso invalida o handle que o jogo já tinha aberto. Um jogo aberto pode precisar
de replug lógico — daí o aviso vermelho *antes* de aplicar.

**Ressalva de 19/08/2026:** o gesto e as cinco cores da piscada ainda **não
foram vistos em hardware**. O roteiro de prova está em
[PROVA-NO-PLASTICO-01](../process/sprints/2026-08-19-PROVA-NO-PLASTICO-01-o-roteiro-de-quarenta-minutos-com-o-controle-na-mao.md).

## Teclado na tela — L3 abre, R3 fecha

Os defaults de `l3` e `r3` no mapa de fábrica não são teclas: são os tokens
virtuais `__OPEN_OSK__` e `__CLOSE_OSK__`, interceptados pelo device de teclado
virtual e delegados ao subsistema de teclado, que sobe (ou mata) o processo do
teclado na tela do sistema. Nada de evento de tecla real é emitido.

**Isto é o único caminho de fábrica para escrever texto pelo controle.** Nenhum
atalho de fábrica digita uma letra: o mapa de fábrica tem nove entradas, e as
que emitem tecla de verdade são Super (Options), PrintScreen (Create),
Alt+Shift+Tab (L1) e Alt+Tab (R1) — mais Backspace, Enter e Delete, que eram
das três regiões do touchpad e [saíram em 09/08/2026](modos.md#o-touchpad-é-touchpad-do-sistema).
As outras duas entradas são justamente o `l3` e o `r3` desta seção.

O programa é do sistema, e a escolha sai da **sessão viva**, não de preferência:

| Sessão | Pacote | Binário | Como digita |
|---|---|---|---|
| Wayland | `wvkbd` | `wvkbd-mobintl` | `zwp_virtual_keyboard_manager_v1` — cliente Wayland puro |
| X11 | `onboard` | `onboard` | XTEST |

Desde 10/08/2026 o `install.sh` instala o certo sozinho, sem flag (passo 4f). Em
máquina provisionada antes disso, `sudo apt install wvkbd` (ou `onboard` em X11)
resolve, **sem reiniciar o daemon** — ele reconsulta o sistema a cada 10 s. Sem
nenhum dos dois instalados, o L3 **avisa na tela** em vez de não fazer nada.

A ordem importa e já foi um defeito: até 10/08 a lista de candidatos era fixa,
com o `onboard` primeiro. Com os dois instalados numa sessão Wayland, o daemon
escolheria justamente o que **abre e não digita**. Hoje quem decide é
`WAYLAND_DISPLAY` primeiro, `DISPLAY` só depois — numa sessão Wayland com
XWayland os dois estão setados, então olhar `DISPLAY` antes classificaria toda
sessão Wayland moderna como X11.

Desligar **"Emular teclado"** na aba Navegação tira também o teclado na tela: é
o mesmo device virtual que carrega os dois. Diagnóstico e as quatro histórias de
um `command -v` vazio em
[`troubleshooting.md`](troubleshooting.md#17-o-l3-não-abre-o-teclado-na-tela).

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
