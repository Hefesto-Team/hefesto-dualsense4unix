# CITACOES-DAS-PLANILHAS-01 — os endereços que a leva deslocou (IMPLEMENTA, opus)

Sprint: [CITACOES-DAS-PLANILHAS-01](../../sprints/2026-09-13-CITACOES-DAS-PLANILHAS-01-os-enderecos-que-a-leva-deslocou.md)
· branch `voo/CITACOES-DAS-PLANILHAS-01-opus` · base `b791d234` (= `onda/1309`).

## O que mudou

Só dígitos, em três planilhas, e os dois arquivos que se regeram delas. Nenhum
código, nenhuma tela, nenhum botão.

| arquivo | o que mudou |
| --- | --- |
| `docs/data/paridade-gtk-html.csv` | 1170 números de linha |
| `docs/data/mapa-controles.csv` | 439 números de linha |
| `docs/data/decisoes-dela.csv` | 20 números de linha |
| `html/specs.html` | regerado por `scripts/gerar-mapa.py`; `--check` confere |
| `docs/data/LEIA-PRIMEIRO.md` | três números, por `scripts/check_paridade_transporte.py --leia-primeiro --escrever` |

Conferido fora do diff: tirando os dígitos, cada planilha é byte a byte a de
`b791d234`, com o mesmo número de linhas físicas.

**O ROTEIRO** mora no rascunho, como a §I.4 manda, e não entrou no repositório
(§D). Quem coordena roda de novo depois da costura, na raiz da árvore costurada:

```
R=/tmp/claude-1000/-mnt-Apate-Desenvolvimento-hefesto-dualsense4unix/8fc26f69-7ade-42a1-9497-63eac702dfb8/scratchpad/CITACOES-DAS-PLANILHAS-01
python3 $R/reapontar.py --check      # só conta; rc=1 se há o que reapontar
python3 $R/reapontar.py --escrever   # reaponta; depois gerar-mapa.py e --leia-primeiro --escrever
```

Ao lado dele ficam `ancoras.json` (a âncora de cada uma das 1629 reapontadas,
pela posição nova) e `relatorio.tsv` (uma ocorrência por linha, com a
categoria, o motivo e a âncora).

**A REGRA É A DA §I**, sem aritmética: a âncora é a linha citada, lida no
arquivo do commit em que aquele texto de citação entrou na planilha. O «mais
antigo do `git log -S`» foi feito por token (`x.py:12` não casa dentro de
`x.py:123`) e conferido contra o `git log -S` literal em seis citações — as
seis dão o mesmo commit: `rumble_actions.py:996` → `548c0fbc`,
`connection.py:27` → `49118905`, `interface/aba02.py:2378` → `536bf9b1`,
`plano_de_radio.py:385` → `218d03fb`, `uinput_mouse.py:436-465` → `2899ef0d`,
`a06_navegacao.py:1190` → `87be790a`.

**AS TRAVAS QUE A MEDIÇÃO PEDIU**, cada uma nascida de um caso visto na
primeira corrida:

1. *A costura é por cherry-pick.* O commit de origem na branch pode ser a cópia
   de um commit escrito sobre outra base; por isso vota também o mais antigo com
   o mesmo texto em TODAS as refs, e âncoras que discordam não mexem em nada
   (três citações, na lista de baixo).
2. *Texto que entrou migrando o caminho* (mesmo número, outro caminho, na mesma
   posição da célula) só anda se a âncora do caminho velho concordar. Nenhum caso
   hoje; a trava fica para a costura.
3. *Edição não commitada* é julgada pela âncora do texto de HEAD na mesma
   posição — é o que acusa o número trocado pelo vizinho (mordidas M2 e M3).
4. *Faixa que muda de tamanho* só anda se o miolo velho couber no novo só com
   linhas somadas, ou o novo no velho só com linhas tiradas. Nasceu de
   `docs/protocol/externos-referencia-canonica.md:809-819`, que as pontas levavam
   para `159-945`. Das dez faixas que mudaram de tamanho, oito passam (o patch
   HEFESTO dentro de `hid-playstation.c`, as regras `.rules` que cresceram) e
   duas ficam (mordida M4).
5. *Faixa com ponta em branco ou ambígua* anda só se o bloco inteiro existir,
   idêntico, uma vez: 87 reapontadas assim.
6. *O símbolo prometido* (`SIMBOLO` em `x.py:N`) tem de estar na faixa nova —
   pela função `nomes_prometidos` do próprio portão.

**A CONTAGEM, antes e depois**, sobre as citações que resolvem nesta árvore:

| planilha | citações | conferiam | reapontadas | sem âncora | conferem depois |
| --- | --- | --- | --- | --- | --- |
| paridade-gtk-html | 1899 | 340 | 1170 | 389 | 1510 |
| mapa-controles | 1450 | 934 | 439 | 77 | 1373 |
| decisoes-dela | 39 | 16 | 20 | 3 | 36 |
| **total** | **3388** | **1290** | **1629** | **469** | **2919** |

Das 1629: 1404 por linha única, 138 pelas duas pontas, 87 pelo bloco inteiro.

**POR QUE 1629 E NÃO 185.** A validação da FRASES-E-DICAS-02 contou o que oito
arquivos de `src/` deslocaram numa sprint. O roteiro conta o que cada citação
andou desde o commit em que foi escrita, em todo arquivo citado — a paridade
nasceu em `548c0fbc` (03/09) e 771 das reapontadas vêm de lá. Nos três arquivos
daquela conta: `a08_conexoes.py` 63 reapontadas (6 conferiam, 14 sem âncora),
`a02_controles.py` 55 (1 e 6), `secao_controles.py` 27 (2 e 5).

**OS DOIS CASOS JÁ CONHECIDOS (§I.5):**

* `plataforma.probe.retry@dualsense`: o texto `daemon/connection.py:373` nunca
  existiu na planilha (`git log -S` vazio). A célula é
  `src/hefesto_dualsense4unix/daemon/connection.py:27, :86, :373` — o `:373` é
  continuação curta, fora do alcance de `caminho:linha` (o portão também não a
  resolve), e não foi tocado. O `:27` andou para `:53`, que é
  `RECONNECT_PROBE_INTERVAL_SEC: float = 5.0`.
* Linha 23 do mapa: `interface/aba02.py:2378` e `:2458` foram reapontadas **por
  símbolo**, as duas para `:2494` — o `title="{DICA_MIC_VIRTUAL}">Virtual</button>`
  que a validação da MIC-SEM-FONTE-01 diz que elas prometem. A âncora de origem
  levaria a primeira ao `<button` de cima e a segunda ao comentário quatro linhas
  acima. As duas estão escritas em `POR_SIMBOLO` no roteiro, com a razão.

## Qual mordida prova

Cada mordida estraga uma citação no disco, roda o roteiro e o portão, devolve os
bytes e confere o md5 das três planilhas. `git diff --stat` igual antes e depois
das quatro.

| | o que estragou | roteiro `--check` | `validar-citacoes-de-linha.py --all` |
| --- | --- | --- | --- |
| M1 | desfez uma reapontada: paridade:176, `rumble_actions.py:1048` de volta a `:996` | rc=1, acusa `:996 -> 1048` pela origem `548c0fbc` | rc=0 — cego |
| M2 | trocou por vizinho uma que já conferia: mapa:2, `app/mic_monitor.py:241` → `:242` | rc=1, acusa `:242 -> 241` pela âncora de HEAD | rc=0 — cego |
| M3 | trocou por vizinho uma reapontada: paridade:178, `rumble_actions.py:1129` → `:1130` | rc=1, acusa `:1130 -> 1129` pela âncora de HEAD (`:1078`) | rc=0 — cego |
| M4 | arrancou a trava do miolo (`miolo_preservado` devolvendo `True`) | rc=1, 2 pendentes: mapa:113 `secao_controles.py:916-934 -> 966-1013` e mapa:220 `externos-referencia-canonica.md:809-819 -> 159-945` | — |

Devolvido tudo: `--check` rc=0, «OK: nenhuma citação a reapontar».

A coluna da direita é a razão da sprint escrita em número: o portão
`citacoes-de-linha` só cobra a citação que promete símbolo, e as três primeiras
não prometem.

**DEZ REAPONTADAS CONFERIDAS À MÃO, PELO SÍMBOLO** (`grep -n` no arquivo de hoje;
e o número velho não sobrou na planilha):

| planilha · feature/chave | antes → depois | a linha de hoje |
| --- | --- | --- |
| paridade · 05 «Aplicar» | `rumble_actions.py:996` → `:1048` | `def on_rumble_apply` |
| paridade · 05 «Parar» | `rumble_actions.py:1078` → `:1129` | `def on_rumble_stop` |
| paridade · 06 «Motivo da recusa do daemon traduzido» | `a06_navegacao.py:1190` → `:2205` | `return frase_da_recusa_do_mouse(resposta)` |
| paridade · 07 «Steam Input: conferir se está ligado e desligar» | `emulation_actions.py:1909` → `:1959` | `def on_emulation_steam_input_disable` |
| paridade · 01 «A frase que conta os jogadores» | `home_actions.py:2753` → `:2971` | `self._home_players_hint.set_text(` |
| paridade · 09 «Exame do sistema — as seis verificações do storm_report» | `daemon_actions.py:1128` → `:1167` | `rows = storm_doctor.storm_report(controles_no_cabo=no_cabo)` |
| mapa · `combinacao.rumble_simultaneo@dualsense` (OUT_REPORT_KEEPALIVE_SEC) | `core/backend_pydualsense.py:253` → `:262` | `OUT_REPORT_KEEPALIVE_SEC: float = 0.5` |
| mapa · `entrada.emulacao_mouse.analogico@dualsense` (`_emit_move`) | `uinput_mouse.py:436-465` → `:458-487` | `def _emit_move(…)` até o `syn()` que o fecha |
| mapa · `toque.touchpad.clique@dualsense` (`_BT_STRUCT_BASE = 2`) | `core/physical_report_reader.py:145` → `:146` | `_BT_STRUCT_BASE = 2` |
| decisões · `D-QUAL-REGUA-MANDA-NO-ARRANJO` | `plano_de_radio.py:385` → `:407` | `def ordem_de_redistribuicao(` |

**E A PROSA, EM DUAS AMOSTRAS SORTEADAS (30 reapontadas):** 22 caem no que a
célula descreve; 4 duvidosas; e **4 já estavam fora do lugar no commit de
origem** — lidas lá, não aqui: `interface/aba06.py:962` em `548c0fbc` era a
docstring do cartão de identidade (a linha fala do atalho novo);
`a03_gatilhos.py:1218` em `548c0fbc` era o comentário do lugar vazio (a linha
fala do «Desligar»); `a03_gatilhos.py:1132` em `548c0fbc` era o `trig =` do
`pacote` (a linha fala da recusa traduzida); `a04_iluminacao.py:1412` em
`cf048461` era o comentário da cor escolhida (a linha fala da frase do
desfecho, que morava em `:1688-1799`). A regra da §I leva essas junto com o que
apontavam; não as cura.

**Réguas pontuais, com as planilhas novas:** 18 arquivos de teste que leem
as três planilhas, o `specs.html` e o LEIA-PRIMEIRO, `test_portao_o_par_com_metade_ligada.py`
(o portão `citacoes-no-codigo`) entre eles — 336 passed. E
`scripts/check_paridade_gtk_html.py`, `scripts/check_paridade_transporte.py`,
`scripts/gerar-mapa.py --check`, `--leia-primeiro` e
`validar-citacoes-de-linha.py --all` (3288 conferidas): rc=0.

**PORTÕES:** a corrida final roda com esta entrega no índice, e o resultado vai
na mensagem do commit.

## O que NÃO verifiquei

* **As 1629 uma a uma.** Dez pelo símbolo e trinta pela prosa. A proporção de
  «fora do lugar já na origem» (4 de 30) é de amostra, não de contagem.
* **As 205 citações de página `.html` da paridade depois da costura.** As
  páginas publicadas são regeradas por quem coordena; toda citação a elas tem de
  ser recontada DEPOIS da regeração, não antes.
* **O alinhamento das âncoras gravadas depois da costura.** A chave é a posição
  (linha, coluna, ordem na célula); se outra sprint mexer na mesma célula, a
  gravada não casa e a citação volta a ser julgada pela história — onde a trava 1
  pode deixá-la sem âncora em vez de reapontar.
* **Tela, aparelho, cabo e rádio:** nada tocado. A sprint não muda tela, então
  não há foto nem clique. Piloto, bancada e daemon não foram usados.
* **A suíte inteira:** não rodada.

## O que sobrou para o próximo

* **QUEM COORDENA RODA O ROTEIRO DE NOVO depois da costura** e depois de regerar
  as dez páginas, porque a RESTOS-DA-ONDA-DOIS-01 e a SENSORES-NO-JOGO-03
  deslocam linhas na mesma onda: `--check`, `--escrever`,
  `scripts/gerar-mapa.py`, `scripts/check_paridade_transporte.py --leia-primeiro --escrever`.
  Conflito nas planilhas no cherry-pick: fique com o lado da outra sprint e rode o
  roteiro, que ele refaz o que esta branch fez.
* **As citações que já nasceram fora do lugar** pedem remedição pelo símbolo, não
  pela âncora. A leva de `548c0fbc` é a candidata: é de onde vieram as quatro da
  amostra.
* **391 continuações curtas** (`x.py:27, :86, :373`) ficam fora do alcance —
  386 no mapa, 4 nas decisões, 1 na paridade. Entre elas o `:373` de
  `plataforma.probe.retry@dualsense`, que a F1-REMAPEAR-02 diz nunca ter sido o
  laço de reconexão.
* **As 469 sem âncora**, abaixo. A §R declarou o preço: âncora repetida não se
  chuta. Legenda: `sumiu` (a linha não existe mais no arquivo) · `repete N×` ·
  `branco` (linha em branco ou só pontuação) · `início`/`fim` (a ponta da faixa)
  · `bloco` (o bloco inteiro também não serve) · `miolo` (a faixa mudou de
  tamanho e o miolo não é o mesmo) · `divergem` (as âncoras de origem da branch e
  de todas as refs discordam). A âncora vai cortada em 70 caracteres.

```
# decisoes-dela.csv
  41  src/hefesto_dualsense4unix/integrations/arranjo_da_mesa.py:1047 — sumiu · «CUSTO_SEM_MIC = 260»
  90  app/actions/config/secao_mesa.py:1810 — sumiu · «_BOTAO_DESENHAR = "Desenhar a minha mesa"»
  98  docs/process/sprints/2026-08-27-ONDA-CONEXOES-03-o-exame-em-tres-colunas.md:43 — sumiu · «| **o que só você sabe** | as duas perguntas de rádio, com o "?" que …»

# mapa-controles.csv
  23  daemon/ipc_handlers.py:5145-5148 — início: sumiu · bloco sumiu · «fonte = fonte_de_captura_do_uniq(uniq) if uniq else None … fonte = fo…»
  23  daemon/subsystems/hotkey.py:885-913 — fim: sumiu · bloco sumiu · «(a) **`audio.toggle_default_source_mute`.** Ele opera em … "estou no …»
  23  integrations/audio_control.py:1-60 — fim: branco · bloco sumiu · «"""Controle de mute do microfone padrão do sistema via wpctl ou pactl…»
  23  integrations/eleicao_de_microfone.py:1-42 — fim: branco · bloco sumiu · «"""Elege o microfone do sistema POR CONTROLE — e sabe voltar atrás. ……»
  23  profiles/schema.py:902 — sumiu · «"`fonte_de_captura_do_controle()`, que devolve a PRIMEIRA "»
  32  app/mic_monitor.py:227-246 — início: sumiu · fim: sumiu · bloco sumiu · «sinks: list[str], uniq: str, uniqs_com_audio: list[str] … return esco…»
  48  assets/dkms/hid-playstation/hid-playstation.c:1579-1596 ×2 — fim: branco · bloco sumiu · «if (hdev->bus == BUS_USB && report->id == DS_INPUT_REPORT_USB && … }»
  54  core/backend_pydualsense.py:534-540 — pontas invertidas · bloco sumiu · «if ( … self._last_write_at = now»
  62  assets/modprobe.d/hefesto-hid-nintendo.conf:63-88 — já passava do fim na origem ef61c628 (81 linhas)
  69  core/physical_report_reader.py:879 — sumiu · «def _observe_battery(self, report: bytes) -> None:»
  80  docs/usage/troubleshooting-8bitdo.md:31 — sumiu · «| Switch por Bluetooth | `057e:2009` (bus `0005`) | `hid-nintendo` | …»
  81  core/physical_report_reader.py:288-311 — fim: branco · bloco sumiu · «Extraído para que motion e clique do touchpad apliquem EXATAMENTE a m…»
  87  assets/dkms/hid-playstation/hid-playstation.c:1579-1596 ×2 — fim: branco · bloco sumiu · «if (hdev->bus == BUS_USB && report->id == DS_INPUT_REPORT_USB && … }»
  88  assets/dkms/hid-playstation/hid-playstation.c:1579-1596 ×2 — fim: branco · bloco sumiu · «if (hdev->bus == BUS_USB && report->id == DS_INPUT_REPORT_USB && … }»
  89  core/evdev_reader.py:57 ×2 — repete 5× · «@dataclass(frozen=True)»
  92  src/hefesto_dualsense4unix/core/backend_pydualsense.py:1758-1782 — início: sumiu · bloco sumiu · «# purgado por `end_game_session_for` no fim da MESMA sessão que o … #…»
 113  app/actions/config/secao_controles.py:930 ×2 — sumiu · «if not uniq or uniq in self._cores or transporte != "usb":»
 113  src/hefesto_dualsense4unix/app/actions/config/secao_controles.py:916-934 — fim: miolo · bloco sumiu · «def _perguntar_as_cores(self, adotados: list[dict[str, Any]]) -> None…»
 113  src/hefesto_dualsense4unix/app/actions/config/secao_controles.py:930 — sumiu · «if not uniq or uniq in self._cores or transporte != "usb":»
 138  core/backend_pydualsense.py:5569 — repete 2× · «if campos:»
 154  assets/79-external-controller-leds.rules:1-6 ×2 — início: sumiu · bloco sumiu · «# Hefesto - DualSense4Unix — acesso de escrita aos LEDs de player dos…»
 165  core/backend_pydualsense.py:5569 — repete 2× · «if campos:»
 180  core/evdev_reader.py:1781-1783 ×3 — início: sumiu · fim: sumiu · bloco sumiu · «O eixo é mapeado por `ABS_RX/RY/RZ` (gyro) — `ABS_X/Y/Z` no mesmo nod…»
 180  src/hefesto_dualsense4unix/core/evdev_reader.py:2092-2094 ×2 — início: sumiu · fim: sumiu · bloco sumiu · «O eixo é mapeado por `ABS_RX/RY/RZ` (gyro) — `ABS_X/Y/Z` no mesmo nod…»
 183  assets/dkms/hid-playstation/hid-playstation.c:304-305 — início: repete 2× · fim: repete 2× · bloco repete 2× · «__le16 gyro[3]; /* x, y, z */ … __le16 accel[3]; /* x, y, z */»
 187  src/hefesto_dualsense4unix/daemon/subsystems/external_identity.py:196-212 — início: sumiu · fim: branco · bloco sumiu · «#: GYRO-02: OUI (6 hex, sem ``:``) do Nintendo Pro Controller GENUÍNO…»
 189  core/physical_report_reader.py:285-311 — fim: branco · bloco sumiu · «def _struct_base(report: bytes) -> int | None: … »
 191  docs/usage/troubleshooting-8bitdo.md:241-253 ×2 — fim: sumiu · bloco sumiu · «## Gyro × Steam Input × o guard do hefesto (o conflito, com todas as …»
 193  interface/aba02.py:1199-1206 — início: sumiu · fim: sumiu · bloco sumiu · «TAXA_DO_GIRO = { … "para Bluetooth não aparecem em janela nenhuma.",»
 197  docs/usage/troubleshooting-8bitdo.md:35-37 — início: sumiu · fim: sumiu · bloco sumiu · «¹ O gyro existe e é real (**PROVADO**: `using factory cal for IMU` + …»
 198  src/hefesto_dualsense4unix/core/physical_report_reader.py:191 — sumiu · «#: DualSense vivo emite SEMPRE (250-765 Hz)" só vale NO CABO. Em Blue…»
 198  src/hefesto_dualsense4unix/core/physical_report_reader.py:8 — sumiu · «ao vivo (2026-07-19): o físico emite gyro a 250 Hz (USB) / ~765 Hz (B…»
 200  src/hefesto_dualsense4unix/daemon/subsystems/external_identity.py:196-212 — início: sumiu · fim: branco · bloco sumiu · «#: GYRO-02: OUI (6 hex, sem ``:``) do Nintendo Pro Controller GENUÍNO…»
 204  src/hefesto_dualsense4unix/core/evdev_reader.py:1181 ×2 — repete 2× · «dev.grab()»
 219  scripts/bt_active_mode.sh:104-108 ×2 — início: sumiu · fim: sumiu · bloco sumiu · «#: OUI (maiúsculas, com ':') do Nintendo Pro Controller GENUÍNO — o Ú…»
 219  src/hefesto_dualsense4unix/daemon/subsystems/external_identity.py:200 — sumiu · «NINTENDO_REAL_OUI = "e0f6b5"»
 220  docs/protocol/externos-referencia-canonica.md:809-819 — fim: miolo · bloco sumiu · «| afirmação | GRAU | … driver que pega. **Nenhuma chave sozinha basta…»
 220  scripts/bt_active_mode.sh:104-108 — início: sumiu · fim: sumiu · bloco sumiu · «#: OUI (maiúsculas, com ':') do Nintendo Pro Controller GENUÍNO — o Ú…»
 220  src/hefesto_dualsense4unix/daemon/subsystems/external_identity.py:200 — sumiu · «NINTENDO_REAL_OUI = "e0f6b5"»
 223  src/hefesto_dualsense4unix/core/external_leds.py:21-26 — fim: sumiu · bloco sumiu · «GYRO-02 (2026-07-19): `enable_imu` é a ÚNICA exceção que sai do sysfs…»
 228  assets/dkms/hid-nintendo/README.md:47-95 — início: branco · bloco sumiu · « … **Por que o padding é a aposta forte.** O descritor do próprio con…»
 229  src/hefesto_dualsense4unix/core/backend_pydualsense.py:3609 ×2 — repete 33× · «return»
 247  src/hefesto_dualsense4unix/core/backend_pydualsense.py:2221 ×2 — repete 40× · «return None»
 249  assets/dkms/hid-nintendo/README.md:47-70 — início: branco · bloco sumiu · « … Timeout foi testado e REFUTADO: esta máquina já roda `sync_send_tr…»
 250  src/hefesto_dualsense4unix/core/backend_pydualsense.py:1583 — branco
 256  src/hefesto_dualsense4unix/daemon/subsystems/identity.py:543 ×2 — sumiu · «def slot_for(self, uniq: str | None, *, assign: bool = True) -> int |…»
 259  assets/82-nintendo-pro-nosniff.rules:23 ×2 — sumiu · «ACTION=="add", SUBSYSTEM=="hid", ENV{HID_UNIQ}=="e0:f6:b5:*", RUN+="/…»
 260  assets/82-nintendo-pro-nosniff.rules:1-24 — fim: sumiu · bloco sumiu · «# BT-SNIFF-BORDA-01 (2026-07-24) … ACTION=="add", SUBSYSTEM=="hid", E…»
 260  scripts/bt_active_mode.sh:70-130 — início: branco · bloco sumiu · « … && log "link policy de ${MAC} -> RSWITCH (sem SNIFF; Pro genuíno)"…»
 261  assets/82-nintendo-pro-nosniff.rules:8-19 — fim: sumiu · bloco sumiu · «# aposta caiu ao vivo: o Pro voltou a desconectar, e a janela entre o…»
 261  scripts/bt_active_mode.sh:75-134 — início: branco · bloco sumiu · «# … exit 0»
 262  src/hefesto_dualsense4unix/integrations/uhid_gamepad.py:949 — sumiu · «#: poll loop — o físico entrega 250 Hz USB / ~765 Hz BT).»
 265  app/widgets/controller_card.py:973 ×2 — repete 2× · «if isinstance(hz, (int, float)) and not isinstance(hz, bool) and hz >…»
 274  src/hefesto_dualsense4unix/core/backend_pydualsense.py:2082 ×2 — repete 43× · «try:»
 276  scripts/bt_health_watchdog.sh:165 ×2 — repete 18× · «fi»
 286  assets/dkms/hid-playstation/hid-playstation.c:1579-1596 — fim: branco · bloco sumiu · «if (hdev->bus == BUS_USB && report->id == DS_INPUT_REPORT_USB && … }»
 292  app/mic_monitor.py:235 — sumiu · «``alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_C…»
 301  src/hefesto_dualsense4unix/integrations/uinput_gamepad.py:261 — sumiu · «caps[ecodes.EV_FF] = [»

# paridade-gtk-html.csv
   2  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:1170 — sumiu · «<b>Desligado</b> — o Hefesto sai do meio e o jogo fala direto com o c…»
   4  src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py:420 — sumiu · «#: também a resposta (`ipc_bridge._run_call`).»
   4  src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py:535 — branco
   6  src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py:427 — branco · «#:»
   8  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:1121 — branco
   9  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:1167 — sumiu · «title="Modo Nativo: o Hefesto sai do meio e o jogo fala direto com o …»
  10  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:1165 — sumiu · «title="O Hefesto fica no meio: ele acende as luzes, faz o controle vi…»
  10  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:1167 — sumiu · «title="Modo Nativo: o Hefesto sai do meio e o jogo fala direto com o …»
  10  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:1171 — sumiu · «Isto não encerra o serviço. Para isso, a aba <b>Sistema</b>.»
  13  mockup/01-jogar.html:2545 — repete 3× · «<span class="chip" data-gesto="mascara" data-mascara="DualSense" data…»
  14  src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py:286 — branco
  14  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:1168 — repete 3× · «<span class="ajuda">?<span class="dica">»
  18  mockup/01-jogar.html:2219 — sumiu · «<span class="rotulo">Sony <span class="pt">•</span> <b data-campo="jo…»
  18  src/hefesto_dualsense4unix/interface/aba01.py:1087 — sumiu · «<span class="rotulo">Sony <span class="pt">•</span> <b data-campo="jo…»
  20  src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py:55 — branco · «#»
  20  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:1592 — repete 4× · «<g transform="translate(16 16) scale(0.99425) translate(-16.0925 -16.…»
  21  src/hefesto_dualsense4unix/interface/mesa_viva.py:327 — sumiu · «"via": "USB" if transporte == "usb" else "BT",»
  21  src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py:46 — sumiu · «via = casa.get("via") or (c.get("transport") or "").upper()»
  22  src/hefesto_dualsense4unix/interface/aba01.py:639 — sumiu · «o "vai pra direita" — o botão passa a terminar no `right` do quadro, …»
  22  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:1585 — repete 4× · «<title>Glifo — Options</title>»
  23  src/hefesto_dualsense4unix/interface/pacotes/__init__.py:281 — sumiu · «def apagar_os_lugares_sem_dono(carga: dict[str, Any]) -> dict[str, An…»
  24  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:2807 — repete 4× · «<rect x="3" y="10" width="22" height="12" rx="2" fill="none" stroke="…»
  25  src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py:2414 — sumiu · «return {"recado": _painel().recibo_do_reconectar(jogadores, renumerou…»
  29  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:1973 — repete 4× · «<title>Glifo — Share</title>»
  31  src/hefesto_dualsense4unix/app/actions/home_actions.py:2543 — repete 2× · «_lock_hint = getattr(self, "_home_autoswitch_lock_hint", None)»
  32  src/hefesto_dualsense4unix/interface/aba01.py:1087 — sumiu · «<span class="rotulo">Sony <span class="pt">•</span> <b data-campo="jo…»
  33  app/actions/jogar/painel.py:649 — sumiu · «Aviso("JOGO", home_actions.wrapper_banner_text, "home_actions.wrapper…»
  33  src/hefesto_dualsense4unix/app/actions/home_actions.py:2688 — sumiu · «aviso_wrapper = wrapper_banner_text(state)»
  34  src/hefesto_dualsense4unix/interface/controles_vivos.py:877 — repete 2× · «lembra = painel.modo_lembrado()»
  34  src/hefesto_dualsense4unix/interface/controles_vivos.py:909 — repete 2× · «lembra = painel.modo_lembrado()»
  36  src/hefesto_dualsense4unix/app/actions/home_actions.py:2543 — repete 2× · «_lock_hint = getattr(self, "_home_autoswitch_lock_hint", None)»
  36  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:2795 — repete 19× · «</path>»
  36  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:963 — sumiu · «esperando em branco. */»
  37  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1073 — sumiu · «<button class="btn vermelho" title="O Hefesto deixa de rodar e os 2 v…»
  39  src/hefesto_dualsense4unix/interface/hefesto_vivo.py:1259 — sumiu · «`cartao` é ONDE ELE POUSA AGORA. Somar os dois num campo só faria dois»
  39  src/hefesto_dualsense4unix/interface/hefesto_vivo.py:80 — sumiu · «TIQUE_MS = 500»
  42  src/hefesto_dualsense4unix/interface/paginas/01-jogar.html:947 — sumiu · «o "vai pra direita" — o botão passa a terminar no `right` do quadro, …»
  43  src/hefesto_dualsense4unix/interface/hefesto_vivo.py:1267 — sumiu · «del self._recados[chave]»
  43  src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py:41 — sumiu · «# A IDENTIDADE É `nome · via`, como o desenho a escreve ("Cosmic Red»
  44  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1861 — sumiu · «<span class="card-nome"><span class="so-fechado">P1 <span class="pt">…»
  48  src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py:484 — repete 2× · «for c in ctx.conectados:»
  48  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1465 — repete 9× · «</span>»
  49  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1447 — sumiu · «A <b>borda</b> tem a cor do plástico, aberto ou fechado — é como você…»
  50  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1448 — sumiu · «qual com a mesa cheia; o <b>fundo lilás</b> diz qual está escolhido.<…»
  50  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1614 — repete 64× · «</svg></span>»
  52  profiles/schema.py:902 — sumiu · «"`fonte_de_captura_do_controle()`, que devolve a PRIMEIRA "»
  52  src/hefesto_dualsense4unix/interface/hefesto_vivo.py:1019 — repete 2× · «self._voltas_da_aba = 0»
  52  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1450 — sumiu · «interruptor de cada um está na <b>linha dele</b>. O botão acima é o ú…»
  52  src/hefesto_dualsense4unix/profiles/schema.py:902 — sumiu · «"`fonte_de_captura_do_controle()`, que devolve a PRIMEIRA "»
  54  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1896 — sumiu · «<span class="leia" title="O que o jogo vê deste controle. A escolha é…»
  58  src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py:3200 — repete 2× · «confissao = frase_do_alvo_do_mic(alvo_honrado(corpo))»
  60  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1475 — repete 4× · «31/08/2026, em duas frases: *"remover o vê como de todos os»
  61  src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py:214 — sumiu · «def toque_do_controle(inputs: Any) -> tuple[str, str]:»
  61  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1571 — sumiu · «<span class="ponto on" data-campo="touch-ponto" data-hef-alvo="classe"»
  62  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1481 — repete 4× · «que o jogo vê, com o `data-campo="mascara"` intacto, que é o»
  63  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1577 — repete 4× · «<div class="barra-luz" data-campo="luz-cor" data-hef-alvo="cor"»
  66  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1484 — branco
  68  src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py:239 — sumiu · «# nao_faz` reprovando nomeando as três. Quem responde do lado do prod…»
  68  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1496 — repete 4× · «PINTURA DO MOCKUP para sempre: o pacote da aba emite `bateria`»
  68  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1503 — repete 4× · «LARGURA, pelo `data-hef-alvo="largura"` que o `escrever` do»
  70  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1855 — repete 4× · «<span class="trilho"><span class="cheio" data-campo="l2-barra"»
  72  src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py:379 — branco
  73  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1644 — repete 28× · «<div>»
  74  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1648 — repete 4× · «sentido o liberar ali"*.»
  76  src/hefesto_dualsense4unix/interface/aba02.py:2520 — sumiu · «<li class="foi"><b>O <code>Liberar</code> do microfone saiu desta tel…»
  76  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:2118 — repete 4× · «<span class="ajuda porque">?<span class="dica" data-campo="mic-porque…»
  77  src/hefesto_dualsense4unix/interface/aba02.py:2054 — sumiu · «<span class="trilho"><span class="cheio" style="width:{mic_vol}%"></s…»
  77  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:2115 — sumiu · «<span class="trilho"><span class="cheio" style="width:80%"></span><in…»
  78  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1670 — repete 4× · «308 que `PARA_O_CARD` reserva. O quadro passava a rolar por»
  80  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1678 — repete 4× · «avaliada e os 12 botões (4 controles x 3 modos) nasciam todos com»
  80  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:2009 — repete 4× · «<!-- AS CHAVES SÃO SIMPLES, E A DUPLA ERA UM BOTÃO MORTO.»
  81  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:2156 — repete 4× · «<span class="trilho"><span class="cheio" data-campo="alto-barra"»
  82  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:2157 — sumiu · «data-hef-alvo="largura" style="width:100%"></span><input class="puxa-…»
  83  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1688 — sumiu · «<span class="onda"><i style="height:22%"></i><i style="height:48%"></…»
  83  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1979 — sumiu · «<div class="moldura" data-bloco="microfone">»
  84  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:2155 — repete 4× · «<div class="vol" data-campo="alto-porque" data-hef-alvo="atributo" da…»
  85  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1691 — sumiu · «<span class="n">80</span>»
  87  src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py:1218 — sumiu · «"alto-rota": rota_na_tela(c),»
  88  app/audio_saida.py:1622-1634 — início: sumiu · fim: sumiu · bloco sumiu · «**No cabo** ele entrega nos canais 1-2 do sink USB DAQUELE controle, …»
  90  src/hefesto_dualsense4unix/interface/paginas/02-controles.html:1678 — repete 4× · «avaliada e os 12 botões (4 controles x 3 modos) nasciam todos com»
  94  src/hefesto_dualsense4unix/interface/paginas/03-gatilhos.html:1244 — repete 4× · «<select class="modo" data-gesto="modo" data-campo="modo-chave-e"»
  95  src/hefesto_dualsense4unix/interface/aba03.py:525 — sumiu · «DICA_DO_MODO = {»
  96  src/hefesto_dualsense4unix/interface/paginas/03-gatilhos.html:1249 — repete 7× · «<option value="Rigid" title="Trava dura do começo ao fim do curso. Se…»
  98  src/hefesto_dualsense4unix/interface/pacotes/a03_gatilhos.py:2518 — sumiu · «def ajuste(ctx: Contexto, o: dict[str, Any], p: Any) -> None:»
 100  src/hefesto_dualsense4unix/interface/pacotes/a03_gatilhos.py:1004 — sumiu · «elif nome:»
 102  src/hefesto_dualsense4unix/interface/paginas/03-gatilhos.html:1270 — repete 4× · «<select class="pronto" data-gesto="pronto" data-campo="pronto-e"»
 107  src/hefesto_dualsense4unix/interface/hefesto_vivo.py:1036 — sumiu · «subtitulo="as dez abas, vivas",»
 108  src/hefesto_dualsense4unix/interface/pacotes/a03_gatilhos.py:1569 — repete 10× · «raise ValueError(»
 112  src/hefesto_dualsense4unix/interface/pacotes/a03_gatilhos.py:1347 — branco · «"""»
 115  src/hefesto_dualsense4unix/interface/paginas/03-gatilhos.html:1374 — sumiu · «<button class="btn roxo" data-gesto="guardar" data-hef-forma="@contro…»
 117  src/hefesto_dualsense4unix/interface/pacotes/a03_gatilhos.py:910 — sumiu · «#: Repintar o mesmo HTML a cada tique não muda um pixel, mas **infla …»
 118  src/hefesto_dualsense4unix/interface/hefesto_vivo.py:1006 — sumiu · «#: SÓ O LAÇO DO GTK ESCREVE AQUI. O gesto corre em thread, e deposita…»
 119  src/hefesto_dualsense4unix/interface/paginas/03-gatilhos.html:1371 — repete 4× · «<input class="nome-efeito" type="text" data-linha="nome-do-efeito"»
 120  src/hefesto_dualsense4unix/interface/pacotes/a03_gatilhos.py:1004 — sumiu · «elif nome:»
 120  src/hefesto_dualsense4unix/interface/pacotes/a03_gatilhos.py:902 — sumiu · «#: medição de 03/09/2026 desfazer a escolha: `escrever()` carimba»
 121  src/hefesto_dualsense4unix/interface/pacotes/a03_gatilhos.py:944 — sumiu · «#: que não se paga.»
 124  src/hefesto_dualsense4unix/interface/paginas/03-gatilhos.html:1244 — repete 4× · «<select class="modo" data-gesto="modo" data-campo="modo-chave-e"»
 126  src/hefesto_dualsense4unix/interface/paginas/04-iluminacao.html:1634 — repete 4× · «<line x1="24" y1="11" x2="19.5" y2="21" stroke="currentColor" stroke-…»
 128  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:635 — sumiu · «f' data-hef="troca.item"{anel}>'»
 128  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:693 — branco · «"",»
 130  src/hefesto_dualsense4unix/interface/aba04.py:1111 — sumiu · «<span class="hex reenvia" data-campo="hex" data-gesto="reenviar"»
 131  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:693 — branco · «"",»
 133  src/hefesto_dualsense4unix/interface/paginas/04-iluminacao.html:1664 — repete 4× · «<title>Lightbar — tira direita</title>»
 134  src/hefesto_dualsense4unix/interface/aba04.py:975 — sumiu · «<span class="trilho"><span class="cheio" data-campo="brilho-pct" data…»
 134  src/hefesto_dualsense4unix/interface/hefesto_vivo.py:1078 — sumiu · «("03-gatilhos.html", "guardar"),»
 134  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:2169 — sumiu · «def brilho(ctx: Contexto, o: dict[str, Any], p: Any) -> None:»
 137  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:143 — branco
 138  src/hefesto_dualsense4unix/interface/paginas/04-iluminacao.html:1657 — repete 4× · «<title>LUZES</title>»
 139  src/hefesto_dualsense4unix/interface/paginas/04-iluminacao.html:1645 — repete 4× · «<path fill="currentColor" d="M 2.265 23.706 C 1.447 24.279 1.598 25.2…»
 146  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:2846 — sumiu · «@gesto("04-iluminacao.html", "auto-cores")»
 147  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:743 — branco · «#»
 149  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:743 — branco · «#»
 149  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:793 — branco · «#:»
 151  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:2846 — sumiu · «@gesto("04-iluminacao.html", "auto-cores")»
 152  src/hefesto_dualsense4unix/interface/paginas/04-iluminacao.html:1631 — repete 4× · «<title>Glifo — Share</title>»
 152  src/hefesto_dualsense4unix/interface/paginas/04-iluminacao.html:2063 — repete 4× · «<title>Glifo — Share</title>»
 154  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:2332 — sumiu · «def _acender_o_numero(ctx: Contexto, p: Any, uniq: str, n: int) -> No…»
 154  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:2484 — sumiu · «def player(ctx: Contexto, o: dict[str, Any], p: Any) -> None:»
 154  src/hefesto_dualsense4unix/interface/paginas/04-iluminacao.html:2144 — sumiu · «<button class="on" data-gesto="player" data-player="1" title="O Cosmi…»
 155  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:323 — branco
 155  src/hefesto_dualsense4unix/interface/paginas/04-iluminacao.html:1652 — repete 4× · «<line x1="21.67" y1="26.588" x2="21.67" y2="29.367" stroke="currentCo…»
 159  src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py:743 — branco · «#»
 160  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:729 — sumiu · «policy: str | None, custom: float | None = None) -> None:»
 160  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:1897 — sumiu · «<div class="seg"><button class="" data-campo="degrau" data-hef-alvo="…»
 161  src/hefesto_dualsense4unix/app/telas/vibracao.py:268 — repete 2× · «"forca": politica,»
 161  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:311 — sumiu · «"degrau": str(col.get("forca") or ""),»
 161  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:1897 — sumiu · «<div class="seg"><button class="" data-campo="degrau" data-hef-alvo="…»
 162  src/hefesto_dualsense4unix/interface/aba05.py:806 — sumiu · «f' data-papel="intensidade" data-campo="{campo}"'»
 163  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:722 — repete 2× · «slider: Gtk.Scale = self._get("rumble_policy_slider")»
 163  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:788 — repete 5× · «self._rumble_guard_refresh = False»
 163  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:119 — sumiu · «def _pct_do_pedido(state: dict[str, Any]) -> dict[str, str]:»
 163  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:1898 — sumiu · «<div class="motor" data-papel="forca"><span></span><span class="trilh…»
 165  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:788 — repete 5× · «self._rumble_guard_refresh = False»
 166  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:1259 — branco
 166  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:175 — branco
 166  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:2785 — repete 4× · «<line x1="7" y1="16" x2="25" y2="16" stroke="currentColor" stroke-wid…»
 167  src/hefesto_dualsense4unix/app/telas/vibracao.py:446 — branco · «)»
 168  src/hefesto_dualsense4unix/app/telas/vibracao.py:451 — branco · «)»
 171  src/hefesto_dualsense4unix/interface/aba05.py:1107 — sumiu · «def _barra_de_motor(valor, sigla, m, ligado, botao):»
 172  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:370 — branco
 172  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:1588 — repete 211× · «</g>»
 172  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:1994 — repete 211× · «</g>»
 173  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:1025 — repete 2× · «weak, strong = self._read_scales()»
 173  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:245 — sumiu · «# elementos destruídos por tique e não pintava um valor sequer.»
 174  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:412 — sumiu · «recusa é o que separa as duas coisas: `rumble.policy_custom` pede um …»
 174  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:464 — sumiu · «no laço do GTK.»
 175  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:1024 — repete 4× · «self._cancel_rumble_test_timer()»
 175  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:997 — repete 4× · «self._cancel_rumble_test_timer()»
 175  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:609 — sumiu · «vez = _minha_vez()»
 175  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:625 — sumiu · «if vez != _VEZ[0]:»
 175  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:657 — repete 2× · «_minha_vez()»
 176  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:1588 — repete 211× · «</g>»
 176  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:2822 — sumiu · «<div class="seg"><span class="nada">—</span></div>»
 178  src/hefesto_dualsense4unix/interface/aba05.py:797 — sumiu · «<div class="ctrl" data-controle="{c["pref"]}" data-uniq="{c.get("uniq…»
 178  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:416 — sumiu · «da coluna.** `app/actions/rumble_actions.py:911` escreve *"não há IPC…»
 179  src/hefesto_dualsense4unix/daemon/ipc_handlers.py:4133 — branco
 181  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:1159 — sumiu · «return {"recado": (»
 182  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:1124 — repete 2× · «self._zerar_rumble_no_rascunho(passthrough=True)»
 182  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:1231 — repete 2× · «self._zerar_rumble_no_rascunho(passthrough=True)»
 183  src/hefesto_dualsense4unix/interface/aba05.py:1699 — sumiu · «<div class="vib-mesa">»
 184  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:1012 — repete 2× · «self._toast_rumble(motivo)»
 184  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:1014 — repete 5× · «self._toast_rumble(»
 184  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:1035 — repete 2× · «self._toast_rumble(motivo)»
 184  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:1098 — repete 5× · «self._toast_rumble(»
 184  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:1126 — repete 5× · «self._toast_rumble(»
 184  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:676 — repete 5× · «self._toast_rumble(»
 184  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:885 — repete 5× · «self._toast_rumble(»
 185  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:1010 — repete 2× · «ok, motivo = rumble_set_checked(weak, strong)»
 185  src/hefesto_dualsense4unix/app/actions/rumble_actions.py:109 — sumiu · «_BTN_GIVE_BACK_TO_GAME = BTN_GIVE_BACK_TO_GAME»
 186  src/hefesto_dualsense4unix/interface/aba05.py:1718 — sumiu · «<div class="vib-nota">{DICA_DOS_VALORES_QUE_PASSAM}</div>»
 187  src/hefesto_dualsense4unix/interface/aba05.py:680 — sumiu · «title="Nenhum controle neste lugar.">»
 187  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:1568 — repete 211× · «</g>»
 187  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:1974 — repete 4× · «<text style="dominant-baseline: central; fill: rgb(200, 204, 218); fo…»
 187  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:1981 — repete 4× · «<line x1="24" y1="11" x2="19.5" y2="21" stroke="currentColor" stroke-…»
 188  src/hefesto_dualsense4unix/app/telas/vibracao.py:216 — branco · «"""»
 189  src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:332 — branco
 189  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:1785 — sumiu · «<g id="vb-p1-feat-rumble-esquerdo" data-campo="treme-e" data-hef-alvo…»
 190  src/hefesto_dualsense4unix/interface/aba05.py:1200 — sumiu · «{DICA_DO_TETO_DA_MESA}»
 190  src/hefesto_dualsense4unix/interface/aba05.py:176 — sumiu · «DICA_DO_TETO_DA_MESA = _do_glade(»
 190  src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html:1566 — repete 4× · «<line x1="8" y1="11" x2="12.5" y2="21" stroke="currentColor" stroke-w…»
 191  src/hefesto_dualsense4unix/interface/aba06.py:1050 — sumiu · «"Liga o que o controle <b>digita</b>: os atalhos da tabela à direita,…»
 192  src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html:2911 — repete 58× · «</div>»
 193  src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html:3014 — sumiu · «<div class="at-linha"><span class="at-rot">Status do Modo<span class=…»
 194  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:583 — repete 2× · «nome = SEM_LEITURA»
 200  src/hefesto_dualsense4unix/app/actions/emulation_actions.py:529 — repete 2× · «"vpad_suspenso_pelo_steam_input": (»
 201  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:548 — branco · «"""»
 201  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:869 — branco
 201  src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html:2915 — repete 58× · «</div>»
 202  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:549 — repete 2× · «if nome == NOME_SEM_LEITURA:»
 202  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:898 — sumiu · «nome = str(o.get("gesto") or "")»
 203  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:895 — sumiu · «o portão do desenho NÃO ignora (`check_o_desenho_aprovado.INVISIVEIS`…»
 203  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:913 — sumiu · «entrega o corpo. Está no relato como achado; enquanto isso, o que dá …»
 205  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:893 — sumiu · «`<nome>-menos` e `<nome>-mais`. Assim a direção não precisa de um atr…»
 207  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:1013 — branco
 208  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:1305 — repete 2× · «dehumanize_binding,»
 210  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:1079 — sumiu · «ELE ENTENDE AS CINCO PALAVRAS, E NÃO AS TRÊS — 02/09/2026, corretivo.…»
 211  src/hefesto_dualsense4unix/interface/aba06.py:1276 — sumiu · «(gl("touchpad", rot="deslizar"), "Movimento do cursor"),»
 214  interface/aba06.py:1395-1397 — fim: sumiu · bloco sumiu · «<span class="tn-tit">Estilo Point-and-click</span> … "Um <b>Estilo de…»
 215  src/hefesto_dualsense4unix/interface/aba06.py:983 — sumiu · «f'<span data-campo="identidade">{c["nome"]}</span></div>\n'»
 216  src/hefesto_dualsense4unix/interface/aba06.py:972 — branco · «"""»
 216  src/hefesto_dualsense4unix/interface/aba06.py:974 — sumiu · «navega = n == NAVEGA»
 217  src/hefesto_dualsense4unix/interface/aba06.py:1404 — repete 39× · «</div>»
 217  src/hefesto_dualsense4unix/interface/aba06.py:997 — branco
 218  src/hefesto_dualsense4unix/interface/aba06.py:1572 — sumiu · «<div class="estado" data-campo="teclado-osk" data-hef-alvo="html"></d…»
 218  src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html:3029 — sumiu · «<div class="estado" data-campo="teclado-osk" data-hef-alvo="html"></d…»
 221  src/hefesto_dualsense4unix/app/actions/emulation_actions.py:1722 — repete 19× · «else:»
 222  src/hefesto_dualsense4unix/interface/aba06.py:1276 — sumiu · «(gl("touchpad", rot="deslizar"), "Movimento do cursor"),»
 222  src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html:3166 — repete 2× · «</svg></span></td><td><select class="campo-linha" data-gesto="linha-d…»
 223  src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html:1690 — repete 4× · «<rect x="16.67" y="5.588" width="10" height="15" rx="5" ry="5" fill="…»
 223  src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html:2070 — repete 4× · «<rect x="16.67" y="5.588" width="10" height="15" rx="5" ry="5" fill="…»
 224  src/hefesto_dualsense4unix/interface/aba06.py:937 — sumiu · «O CARD CONTINUA NA FILEIRA, e é o ponto: quem olha precisa saber que …»
 224  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:1311 — repete 2× · «nome = str((ctx.state or {}).get("active_profile") or "").strip()»
 227  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:1317 — branco
 229  src/hefesto_dualsense4unix/interface/aba06.py:1323 — repete 3× · «<div class="tn-cx">»
 230  src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py:916 — sumiu · «if not p.chamar("mouse.emulation.set", **params):»
 230  src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html:3166 — repete 2× · «</svg></span></td><td><select class="campo-linha" data-gesto="linha-d…»
 231  src/hefesto_dualsense4unix/interface/pacotes/rodape.py:356 — sumiu · «return _recado(perfil.com_a_carona())»
 231  src/hefesto_dualsense4unix/interface/pacotes/rodape.py:384 — sumiu · «return _recado(perfil.com_a_carona())»
 232  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:1405 — sumiu · «if str(o.get("v") or "").strip() != CONFIRMO:»
 232  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:732 — repete 2× · «def _corpo(self) -> None:»
 233  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:1371 — repete 3× · «dialog.show_all()»
 233  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:1415 — repete 25× · «return»
 234  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:1497 — repete 12× · «_get_executor().submit(_worker)»
 234  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:1529 — branco
 234  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:571 — repete 2× · «return "", ""»
 235  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:504 — branco
 236  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:2160 — sumiu · «@gesto("07-lancadores.html", desenho.JOGO_NAO_FUNCIONA)»
 238  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:571 — repete 2× · «return "", ""»
 238  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:805 — branco
 240  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:1009 — sumiu · «que o Hefesto cumpriu. A janela velha diz isso num toast do rodapé»
 240  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:1013 — sumiu · «A FRASE É A DO DONO, montada por `carona_do_wrapper.passada` — a mesma»
 241  src/hefesto_dualsense4unix/interface/desenho_dos_lancadores.py:577 — branco
 242  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:592 — branco
 243  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:512 — branco
 244  src/hefesto_dualsense4unix/interface/desenho_dos_lancadores.py:560 — sumiu · «"processo e pela janela."»
 245  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:354 — branco
 246  src/hefesto_dualsense4unix/daemon/lifecycle.py:4169 — branco
 246  src/hefesto_dualsense4unix/interface/desenho_dos_lancadores.py:470 — sumiu · «#: A PROVA DE QUE NENHUM É LIDO POR DENTRO, medida em 02/09/2026:»
 246  src/hefesto_dualsense4unix/interface/desenho_dos_lancadores.py:509 — branco · «#:»
 246  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:232 — branco
 247  src/hefesto_dualsense4unix/interface/desenho_dos_lancadores.py:470 — sumiu · «#: A PROVA DE QUE NENHUM É LIDO POR DENTRO, medida em 02/09/2026:»
 249  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:198 — repete 2× · «return»
 249  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:474 — branco · «"""»
 249  src/hefesto_dualsense4unix/interface/paginas/07-lancadores.html:895 — branco
 250  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:1618 — branco · «"""»
 250  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:1057 — branco
 250  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:2202 — sumiu · «@gesto("07-lancadores.html", desenho.TUDO_PRONTO)»
 251  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:2160 — sumiu · «@gesto("07-lancadores.html", desenho.JOGO_NAO_FUNCIONA)»
 252  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1207 — sumiu · «<button class="btn" title="Trava de novo o Proton que você validou no…»
 253  src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py:1800 — divergem (origem 8ac42e98 ≠ todas-as-refs cee0ab05)
 253  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1304 — divergem (origem 8ac42e98 ≠ todas-as-refs cee0ab05)
 254  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:2099 — sumiu · «@gesto("07-lancadores.html", desenho.DESLIGAR_STEAM_INPUT)»
 255  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1206 — sumiu · «<button class="btn" title="Sem senha e sem fechar nada: arruma o áudi…»
 256  src/hefesto_dualsense4unix/interface/desenho_dos_lancadores.py:743 — repete 5× · «return Lancador(»
 257  src/hefesto_dualsense4unix/app/actions/carona_do_wrapper.py:319 — sumiu · «return ResultadoDaCarona(status, sw.frase_do_aviso(censo), faltantes,…»
 257  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:377 — branco
 258  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:178 — repete 2× · «def __init__(self) -> None:»
 259  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:504 — branco
 265  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:544 — branco
 270  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:1503 — sumiu · «<div class="sub">Gerenciador DualSense para Linux</div>»
 270  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:1509 — sumiu · «O PERFIL ATIVO fica à direita, e é IGUAL nas dez abas: em cada tela e…»
 270  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:1515 — sumiu · «<span class="chip plastico on" data-campo="fita-chip" style="--plasti…»
 270  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:1521 — sumiu · «<span class="ajuda">?<span class="dica" style="left:auto;right:22px">»
 270  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:1527 — repete 91× · «</div>»
 274  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:3826 — sumiu · «@gesto("08-conexoes.html", GESTO_DO_APELIDO)»
 276  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:3289 — branco
 278  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:2506 — repete 4× · «<path fill="currentColor" d="M 2.265 23.706 C 1.447 24.279 1.598 25.2…»
 279  mockup/08-conexoes.html:2788 — sumiu · «<div class="viz"><span class="qual" data-campo="vizinho-nome" title="…»
 280  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:2506 — repete 4× · «<path fill="currentColor" d="M 2.265 23.706 C 1.447 24.279 1.598 25.2…»
 281  mockup/08-conexoes.html:2936 — sumiu · «<div class="viz"><span class="qual" data-campo="vizinho-nome" title="…»
 281  src/hefesto_dualsense4unix/app/actions/config/secao_mesa.py:1119 — repete 2× · «largura_max=_LARGURA_DA_FRASE,»
 282  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:2667 — sumiu · «<span class="trilho" title="Folgada — 276,7 das 1.600 turnos (17%). A…»
 283  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:926 — branco · «"""»
 283  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:2667 — sumiu · «<span class="trilho" title="Folgada — 276,7 das 1.600 turnos (17%). A…»
 285  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:1896 — sumiu · «`cfg.rumble is None` (`profiles/manager.py:1862`) e `"policy" not in»
 286  mockup/08-conexoes.html:2987 — sumiu · «<div class="mm-conf-linha" data-campo="confissao-nada" data-hef-alvo=…»
 287  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:2654 — repete 5× · «</span></span>»
 288  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:2686 — sumiu · «<span><i class="vaga"></i>Cada controle do cabo, se viesse — +276,7</…»
 289  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:1246 — repete 2× · «declaracao = _declaracao()»
 289  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:1610 — repete 91× · «</div>»
 289  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:1623 — sumiu · «<button class="ignora" data-gesto="ignorar" data-v="2" title="Ignora …»
 290  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:3103 — repete 20× · «return ""»
 291  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:1380 — branco · «#»
 291  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:917 — branco
 291  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:2012 — repete 211× · «</g>»
 292  mockup/08-conexoes.html:2072 — sumiu · «<span title="O microfone deste controle chega <b>pelo cabo</b>, pela …»
 293  mockup/08-conexoes.html:2204 — sumiu · «<span data-campo="mic-dica" data-hef-alvo="atributo" data-hef-atribut…»
 294  mockup/08-conexoes.html:2514 — sumiu · «<span class="leitura" data-campo="mic-escopo" title="O que o botão fí…»
 295  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:1919 — branco
 295  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:1959 — branco
 295  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:2447 — repete 4× · «<rect x="7" y="7" width="18" height="18" fill="none" stroke="currentC…»
 298  mockup/08-conexoes.html:2395 — sumiu · «<button class="btn apagado" data-gesto="luz-nao-acende" data-campo="l…»
 298  src/hefesto_dualsense4unix/app/actions/config/secao_controles.py:285 — sumiu · «def dica_do_botao(dados: Any, mesa_suja: bool = False) -> str:»
 299  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:2273 — sumiu · «dica = dica_do_botao(dados)»
 300  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:776 — repete 9× · «continue»
 300  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:2024 — repete 4× · «<title>Glifo — Quadrado</title>»
 303  src/hefesto_dualsense4unix/interface/mesa_viva.py:335 — branco
 303  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:1400 — sumiu · «Agora o `monta.py` LÊ o `.svg` — ela redesenha, e as dez abas mudam»
 304  mockup/08-conexoes.html:2055 — sumiu · «<span class="conta" data-campo="conta-gestao" data-hef-alvo="html">2 …»
 307  src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:3169 — repete 47× · «perfil._com_o_src()»
 309  src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html:2605 — sumiu · «<tr><td class="mudo"><span class="renomeia" contenteditable="true" ti…»
 310  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:1943 — branco
 310  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:2536 — repete 2× · «self._daemon_autostart_guard = True»
 310  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1061 — sumiu · «<div class="est ok" data-id="hefesto-estado"><span class="g">[OK]</span>…»
 312  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1073 — sumiu · «<button class="btn vermelho" title="O Hefesto deixa de rodar e os 2 v…»
 313  src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py:1531 — sumiu · «@gesto("09-sistema.html", "reiniciar")»
 313  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1071 — sumiu · «<button class="btn" title="Para e liga de novo. Resolve a maioria dos…»
 314  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1072 — sumiu · «<button class="btn" title="Relê tudo o que esta aba mostra. Não muda …»
 316  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:1955 — repete 2× · «self._daemon_autostart_guard = True»
 316  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:2532 — repete 2× · «status = self._daemon_status()»
 316  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1065 — sumiu · «<div class="est ok" data-id="hefesto-autostart"><span class="g">[OK]</sp…»
 316  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1066 — sumiu · «<span class="chave on" data-gesto="autostart"></span></div>»
 317  src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py:1497 — sumiu · «@gesto("09-sistema.html", "autostart")»
 317  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1066 — sumiu · «<span class="chave on" data-gesto="autostart"></span></div>»
 318  src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py:1236 — sumiu · «def _trava(ctx: Contexto, nome: str) -> str | None:»
 319  src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py:440 — repete 8× · «return ""»
 319  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1070 — sumiu · «<button class="btn verde" title="Tira o serviço da pausa agora. Só ac…»
 320  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1062 — sumiu · «<div class="est warn" title="A pausa fica gravada em disco e sobreviv…»
 321  src/hefesto_dualsense4unix/gui/aba_sistema.py:330 — branco
 321  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1064 — sumiu · «<div class="est info" data-id="hefesto-ambiente"><span class="g">◆</s…»
 322  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1063 — sumiu · «<div class="est ok" data-id="hefesto-troca-de-perfil"><span class="g"…»
 323  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:2084 — branco · «)»
 324  src/hefesto_dualsense4unix/interface/hefesto_vivo.py:80 — sumiu · «TIQUE_MS = 500»
 324  src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py:1351 — repete 4× · «_LENTO.clear()»
 325  src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py:495 — sumiu · «registro = bruto.get("registro")»
 325  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1098 — sumiu · «<div class="seg bat-perfis" data-id="bateria-perfil"><button class="o…»
 326  src/hefesto_dualsense4unix/app/actions/config/secao_orcamento.py:452 — branco · «)»
 326  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1098 — sumiu · «<div class="seg bat-perfis" data-id="bateria-perfil"><button class="o…»
 327  src/hefesto_dualsense4unix/gui/aba_sistema.py:400 — branco
 327  src/hefesto_dualsense4unix/gui/aba_sistema.py:418 — branco
 327  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1099 — sumiu · «<div class="est info" title="O que este perfil limita hoje, na mesa i…»
 328  src/hefesto_dualsense4unix/gui/aba_sistema.py:369 — branco
 328  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1100 — sumiu · «<div class="est info" title="É o teto da MESA. Cada controle pode sob…»
 329  mockup/09-sistema.html:1275 — sumiu · «<div class="est info" title="Onde o teto do perfil age de verdade hoj…»
 331  src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py:382 — branco
 333  src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py:444 — sumiu · «achado = _daemon.medir_prontuario_dos_jogos()»
 335  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:1122 — repete 19× · «with contextlib.suppress(Exception):»
 336  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:1602 — repete 4× · «dialog.destroy()»
 336  src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py:1147 — sumiu · «@gesto("07-lancadores.html", FECHAR)»
 338  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1206 — sumiu · «<button class="btn" title="Sem senha e sem fechar nada: arruma o áudi…»
 340  interface/aba09.py:1256 — sumiu · «{item("Aplicar aos jogos da Steam", "Põe a linha de inicialização do …»
 341  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1207 — sumiu · «<button class="btn" title="Trava de novo o Proton que você validou no…»
 342  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1304 — divergem (origem 8ac42e98 ≠ todas-as-refs cee0ab05)
 345  src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py:133 — branco · «#:»
 345  src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py:596 — branco
 345  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1221 — sumiu · «<button class="btn" title="Joga as últimas 80 linhas do registro técn…»
 346  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:1970 — repete 2× · «return False  # não repetir via GLib»
 346  src/hefesto_dualsense4unix/app/actions/daemon_actions.py:2549 — repete 2× · «text = self._systemctl_status_text(SERVICE_NORMAL)»
 346  src/hefesto_dualsense4unix/interface/paginas/09-sistema.html:1225 — sumiu · «<div class="log" data-id="registro-texto" data-campo="registro-texto"…»
 355  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:271 — branco · «#:»
 357  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1360 — sumiu · «o campo travado com a frase do que fazer (`perfis_web.py:172`). Aceit…»
 361  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1327 — repete 2× · «return»
 362  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:2069 — repete 2× · «_ESCOLHIDO = nome»
 365  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:140 — branco
 365  src/hefesto_dualsense4unix/interface/paginas/10-perfis.html:1111 — sumiu · «<div class="sec-rot">Perfis Salvos</div>»
 367  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:2266 — repete 3× · «_anotar(frase)»
 367  src/hefesto_dualsense4unix/interface/paginas/10-perfis.html:1421 — repete 4× · «<span class="pl" data-hef="guarda.plastico" data-hef-alvo="cor"»
 368  src/hefesto_dualsense4unix/interface/pacotes/rodape.py:121 — sumiu · «@gesto("*", "salvar")»
 368  src/hefesto_dualsense4unix/interface/paginas/10-perfis.html:1464 — repete 4× · «<path d="M6,12 h5 l7,-6 v20 l-7,-6 H6 Z" fill="none" stroke="currentC…»
 369  src/hefesto_dualsense4unix/app/actions/profiles_actions.py:3376 — repete 2× · «and selecionado is not None»
 369  src/hefesto_dualsense4unix/app/actions/profiles_actions.py:3452 — branco · «):»
 369  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1775 — sumiu · «raise RuntimeError(str(editor.get("ambiente_recado") or ""))»
 370  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1204 — branco
 370  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1315 — sumiu · «load_profile,»
 372  src/hefesto_dualsense4unix/app/actions/profiles_actions.py:3374 — repete 2× · «and not duplicando»
 375  src/hefesto_dualsense4unix/app/actions/perfis_web.py:217 — sumiu · «#: (ver :func:`_ambiente_do_perfil`).»
 375  src/hefesto_dualsense4unix/app/actions/profiles_actions.py:82 — sumiu · «_RADIO_IDS = ("any", "steam", "browser", "terminal", "editor", "game"…»
 376  src/hefesto_dualsense4unix/app/actions/perfis_web.py:232 — sumiu · «"""``"3 de 4 controles com ajuste próprio neste perfil"``.»
 376  src/hefesto_dualsense4unix/app/actions/perfis_web.py:303 — sumiu · «return f"{com_ajuste} de {total} {peca} com ajuste próprio neste perf…»
 376  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1259 — branco
 378  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1120 — sumiu · «def _html_dos_jogos() -> str:»
 380  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1218 — branco
 380  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1272 — sumiu · «régua (um dicionário montado à mão, sem `evento`) tem de continuar va…»
 380  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1324 — sumiu · «raise ValueError("o perfil precisa de um nome — o campo ficou vazio.")»
 383  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:585 — sumiu · «"editor.jogo.exigencia": "a frase do ponto de alerta, no hover",»
 385  src/hefesto_dualsense4unix/interface/aba10.py:1964 — sumiu · «for proibida in ("rádio", "Xbox 360 não", "giroscópio"):»
 386  src/hefesto_dualsense4unix/interface/aba10.py:1964 — sumiu · «for proibida in ("rádio", "Xbox 360 não", "giroscópio"):»
 388  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1274 — sumiu · «return str(o.get("evento") or "") != "click"»
 389  src/hefesto_dualsense4unix/interface/paginas/10-perfis.html:1420 — repete 4× · «<td class="gd-nome">»
 390  src/hefesto_dualsense4unix/app/actions/perfis_web.py:436 — branco · «}»
 390  src/hefesto_dualsense4unix/interface/paginas/10-perfis.html:1212 — repete 2× · «</span>»
 391  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:744 — repete 3× · «from hefesto_dualsense4unix.profiles.loader import load_all_profiles»
 392  src/hefesto_dualsense4unix/interface/paginas/10-perfis.html:1212 — repete 2× · «</span>»
 395  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1432 — repete 2× · «p.chamar("launch_env.refresh")»
 395  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:1939 — repete 4× · «_gravar(prof, ctx, p)»
 395  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:2000 — repete 4× · «_gravar(prof, ctx, p)»
 395  src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py:285 — sumiu · «def _dizer(frase: str) -> dict[str, Any]:»
 396  src/hefesto_dualsense4unix/interface/paginas/10-perfis.html:1466 — repete 4× · «<path d="M26,7 Q32,16 26,25" fill="none" stroke="currentColor" stroke…»
 397  src/hefesto_dualsense4unix/interface/paginas/10-perfis.html:1465 — repete 4× · «<path d="M22,11 Q26,16 22,21" fill="none" stroke="currentColor" strok…»
```
