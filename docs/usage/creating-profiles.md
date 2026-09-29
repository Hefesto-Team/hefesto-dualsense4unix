# Escrever um perfil à mão

A aba Perfis cria e edita perfis sem digitar nada. Esta página é para quem quer
escrever ou revisar o arquivo.

Os perfis ficam em `~/.config/hefesto-dualsense4unix/profiles/<nome>.json`.
Cada gravação guarda a versão anterior, e o `profile restore <nome>` da linha
de comando a traz de volta ([cli.md](cli.md)).

## Um exemplo

```json
{
  "name": "corrida",
  "version": 1,
  "match": {"type": "criteria", "window_class": ["steam_app_1091500"]},
  "priority": 10,
  "triggers": {
    "left":  {"mode": "Resistance", "params": [3, 5]},
    "right": {"mode": "Galloping", "params": [0, 9, 7, 7, 10]}
  },
  "leds": {"lightbar": [255, 80, 0]},
  "rumble": {"passthrough": true}
}
```

Só `name` e `match` são obrigatórios. **Campo ausente é campo sem opinião**: o
perfil não mexe naquilo quando entra.

| Campo | O que é |
|---|---|
| `name`, `version`, `match`, `priority` | o nome e quando o perfil entra ([Quando o perfil entra](#quando-o-perfil-entra)) |
| `triggers` | os gatilhos ([Os modos de gatilho](#os-modos-de-gatilho)) |
| `leds` | a barra de luz (`lightbar`, `lightbar_brightness` de 0.0 a 1.0) e a cor automática por número (`auto_player_colors`, ligada por padrão) |
| `rumble` | a vibração: `passthrough`, e a força em `policy` (`economia`, `balanceado`, `max`, `auto`, `custom`) com `custom_mult` |
| `button_actions`, `key_bindings` | o que cada botão faz fora do jogo ([hotkeys.md](hotkeys.md)) |
| `remapeamento` | trocar um botão por outro no jogo, nos quatro controles (`{"cross": "circle"}`) |
| `movimento` | a mira pelo giroscópio |
| `mouse`, `teclado_emulado`, `suppress_desktop_emulation` | o mouse e o teclado do controle |
| `mic`, `speaker` | o microfone e o alto-falante |
| `mode` | o modo que o perfil pede ([modos.md](modos.md)) |
| `controllers` | ajustes de um controle só ([Por controle](#por-controle)) |
| `ponte` | o que o Hefesto aprendeu sobre o jogo ([O que o Hefesto aprende](#o-que-o-hefesto-aprende)) |

## Quando o perfil entra

O `match` tem três formas:

- `{"type": "criteria", ...}`: entra quando a janela em foco casa;
- `{"type": "any"}`: vale sempre, fora de jogo, quando nenhum outro casa;
- `{"type": "manual"}`: nunca entra sozinho, só quando você o escolhe.

Na forma `criteria`:

- os campos preenchidos (`window_class`, `window_title_regex`, `process_name`)
  precisam casar **todos**;
- dentro de uma lista, basta um: `"window_class": ["a", "b"]` casa com qualquer
  dos dois;
- `window_title_regex` procura em qualquer parte do título;
- `process_name` casa com o nome do executável (`/proc/<pid>/exe`).

Em empate, ganha a maior `priority`. Um perfil com regra de janela ganha sempre
de um perfil `any`, qualquer que seja a prioridade, e um perfil `any` não entra
num jogo.

**Jogo da Steam: use só a `window_class`.** A janela de um jogo da Steam é
`steam_app_<número do jogo>`. Não ponha `process_name` junto: pelo Proton, o
executável é o do Wine, nunca o `.exe` do jogo, e o perfil deixa de casar. Se
um perfil de jogo não entra, este é o primeiro suspeito
([troubleshooting.md](troubleshooting.md)).

Para descobrir os valores de uma janela, com ela em foco:

```bash
xprop WM_CLASS                          # clique na janela; o segundo valor é o que vale
xdotool getactivewindow getwindowname   # o título
xdotool getactivewindow getwindowpid    # o processo; depois, readlink /proc/<pid>/exe
```

O botão **Detectar** da aba Perfis faz isso por você com o jogo aberto.

## Os modos de gatilho

O `mode` de cada gatilho tem de ser um destes 19 nomes, ou o perfil não
carrega: `Off`, `Rigid`, `SimpleRigid`, `Pulse`, `PulseA`, `PulseB`,
`Resistance`, `Bow`, `Galloping`, `SemiAutoGun`, `AutoGun`, `Machine`,
`Feedback`, `Weapon`, `Vibration`, `SlopeFeedback`, `MultiPositionFeedback`,
`MultiPositionVibration`, `Custom`.

| Modo | Parâmetros | Exemplo |
|---|---|---|
| `Off` | nenhum | `[]` |
| `Rigid` | posição, força | `[5, 200]` |
| `Resistance` | início, força (0 a 8) | `[3, 5]` |
| `Bow` | início, fim, força, estalo | `[1, 7, 8, 8]` |
| `Galloping` | início, fim, pé 1, pé 2, frequência | `[0, 9, 7, 7, 10]` |
| `Machine` | seis valores | `[0, 9, 3, 3, 50, 8]` |
| `Weapon` | início, fim, força | `[2, 5, 200]` |
| `Vibration` | posição, amplitude, frequência | `[3, 4, 40]` |

Valor fora da faixa impede o perfil de carregar. A tabela completa está em
[trigger-modes.md](../protocol/trigger-modes.md). Os nomes do DSX (`Medium`,
`Soft`, `Hard`, `GameCube` e parecidos) não são modos do Hefesto.

## O microfone e o alto-falante

```json
{
  "mic": {"button_toggles_system": true, "volume": 70, "muted": false},
  "speaker": {"volume": 180, "muted": false, "rota": 2}
}
```

- Na seção `mic`, o `button_toggles_system` é obrigatório: diz se o botão do
  microfone do controle cala também o microfone do computador. O `volume` do
  microfone vai de 0 a 100 (por cento). O `muted` só vale quando você troca de
  perfil de propósito, para abrir um jogo não desfazer um mudo que você pôs.
- Na seção `speaker`, o `volume` vai de 0 a 255 e é obrigatório. Para o mudo,
  escreva o volume que quer de volta e `"muted": true`. A `rota` vai de 0 a 3:
  `0` e `1` mandam o som ao fone, `2` o divide entre o fone e o alto-falante do
  controle, e `3` manda tudo ao alto-falante. Sem `rota`, o Hefesto não mexe no
  caminho do som.

## O mouse do controle

```json
{"mouse": {"enabled": true, "speed": 8, "scroll_speed": 1}}
```

`speed` vai de 1 a 12 e `scroll_speed` de 1 a 5. Sem a seção, entrar no perfil
não liga nem desliga o mouse. `"suppress_desktop_emulation": true` desliga o
mouse e o teclado do controle enquanto o perfil vale, para jogos que leem o
controle direto; o PS + Options continua valendo por cima dele.

## Por controle

Com mais de um controle, cada um pode ter a própria cor, gatilho, vibração e
som dentro do mesmo perfil:

```json
{"controllers": {"aabbcc000002": {"leds": {"lightbar": [0, 120, 255]}}}}
```

A chave é o endereço do controle, com ou sem os dois-pontos
(`AA:BB:CC:00:00:02` vira `aabbcc000002`). O que não estiver ali vem do perfil,
campo a campo. Aceita `leds`, `triggers`, `rumble`, `speaker`, `mic`,
`sensores`, `mascara` e `movimento`. O `rumble` daqui só aceita `policy` (sem
`auto`) e `custom_mult`.

## O que o Hefesto aprende

A seção `ponte` é a única que o Hefesto escreve sozinho. Quando você troca o
modo de um jogo com PS + R3 e ele funciona, ou quando o modo fica de pé sem
reclamação, o perfil daquele jogo guarda o que deu certo, para não perguntar de
novo:

```json
{"ponte": {"kind": "gamepad", "gamepad_flavor": "dualsense", "steam_input": false,
           "confirmada_em": "2026-08-19T21:30:00-03:00", "confirmada_por": "gesto"}}
```

Só um perfil com a regra do jogo (`steam_app_<número>`) recebe a seção: sem
perfil próprio, o jogo não aprende. Apagar a seção só faz o Hefesto aprender de
novo.

## Pela linha de comando

```bash
hefesto-dualsense4unix profile create corrida --priority 10 --match-class steam_app_1091500
hefesto-dualsense4unix profile create so-quando-eu-quiser --manual
hefesto-dualsense4unix profile list
hefesto-dualsense4unix profile show corrida
hefesto-dualsense4unix profile activate corrida
hefesto-dualsense4unix profile delete corrida --yes
```

O perfil criado pela linha de comando nasce com os gatilhos desligados; edite o
arquivo para o resto.
