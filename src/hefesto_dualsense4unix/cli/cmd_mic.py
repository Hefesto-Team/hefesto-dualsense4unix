"""Subcomando `hefesto-dualsense4unix mic on|off|status|bt|bt-status`.

Dois microfones diferentes moram aqui, e a diferença é de TRANSPORTE:

**No cabo** o mic do DualSense é um dispositivo de áudio USB comum — o
PipeWire o publica sozinho e o trabalho é só de POLÍTICA (deixar ou não que
ele vire a entrada padrão do sistema). É o que `on`/`off`/`status` fazem,
reusando `scripts/fix_wireplumber_default_source.sh` (mesma lógica do
install/doctor):

- on     -> --enable-mic     (remove os drop-ins de supressão 51/52/53; mic livre)
- off    -> --disable-source (instala 52/53; mic do controle some, sem spam)
- status -> --status

A supressão por default é OFF do ponto de vista do mic (o install instala 52/53),
então "ligar quando precisar" é `mic on`. Pensado para a GUI e o applet COSMIC
acionarem o mesmo caminho do CLI. FEAT-DUALSENSE-MIC-TOGGLE-01.

**Em Bluetooth não existe fonte de áudio nenhuma para o PipeWire publicar**: o
DualSense não fala A2DP/HFP/HSP e manda o áudio como Opus dentro dos reports
HID. Aí não há política a ajustar — é preciso IMPLEMENTAR o transporte. É o que
`bt` faz, subindo a ponte de `integrations/dualsense_bt_audio.py` (BT-MIC-01);
`bt-status` mostra as pré-condições sem mexer em nada.

MIC-USB-01 (25/07) — AS TRÊS CAMADAS DE MUDO. Medido ao vivo com o controle no
cabo: o microfone estava mudo por três motivos empilhados, em três donos
diferentes, e cada cura revelava o de baixo. Este módulo agora alcança os três:

1. **rota do WirePlumber** — `mute:true` persistido por ROTA de placa em
   `~/.local/state/wireplumber/default-routes`, restaurado a cada conexão sem
   nada no log. Cura: `scripts/doctor.sh --fix` (ou `--enable-mic` aqui);
2. **perfil da placa** — preso em `input:iec958-stereo`, que é S/PDIF e não
   carrega sinal, porque o WirePlumber marca a entrada analógica indisponível
   sem fone plugado. Mas o mic EMBUTIDO usa esse caminho (no mixer ALSA o
   controle de captura se chama `Headset`). Cura: `scripts/doctor.sh --fix`;
3. **firmware do controle** — o mesmo estado que o botão físico de mic alterna
   e que acende o LED. Cura: `mute`/`unmute`/`release` daqui, pelo `mic.set` do
   IPC. Até esta sprint só o botão físico o alcançava.

`promote`/`demote` são de uma quarta pergunta, que não é de mudo e sim de
POLÍTICA: quem é o microfone PADRÃO do sistema.
"""
from __future__ import annotations

import contextlib
import signal
import subprocess
import threading
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

console = Console()

_SCRIPT_NAME = "fix_wireplumber_default_source.sh"
_ACTION_FLAG = {
    "on": "--enable-mic",
    "off": "--disable-source",
    "status": "--status",
    # MIC-USB-01 (entrega 3): promoção EXPLÍCITA do mic do controle a entrada
    # padrão do sistema, e a volta. O drop-in 51 rebaixa a prioridade da fonte
    # para o DualSense não ser eleito sozinho — o que é correto e nunca foi o
    # culpado do mute —, mas rebaixar também tirava dela o direito de ESCOLHER:
    # o `set-default-source` era sobrescrito de volta para o monitor da saída.
    "promote": "--promote-source",
    "demote": "--install",
}

#: Ações que mexem no mudo do FIRMWARE do controle (camada 3), pelo `mic.set`
#: do IPC. Os três estados são pedidos DIFERENTES e explícitos: `unmute` não é
#: `release`. Ver `_mic_firmware`.
_ACOES_FIRMWARE: dict[str, bool | None] = {
    "mute": True,
    "unmute": False,
    "release": None,
}

#: Ações que NÃO passam pelo script do WirePlumber (são a ponte por BT).
_ACOES_BT = ("bt", "bt-status")

#: Cadência da reconciliação de hotplug do `mic bt`. Não é polling de dados —
#: o áudio flui numa thread bloqueada no hidraw; isto só pergunta ao sysfs se
#: apareceu/sumiu controle, e o laço DORME num Event entre uma e outra.
_RECONCILIA_S = 5.0


def _find_script() -> Path | None:
    """Localiza o script do WirePlumber em layouts conhecidos (editable e .deb)."""
    candidates = [
        Path(__file__).resolve().parents[3] / "scripts" / _SCRIPT_NAME,
        Path("/usr/share/hefesto-dualsense4unix/scripts") / _SCRIPT_NAME,
        Path("/usr/local/share/hefesto-dualsense4unix/scripts") / _SCRIPT_NAME,
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def mic_cmd(action: str = "status", uniq: str | None = None) -> None:
    """Liga (on) / desliga (off) / consulta (status) o mic do DualSense.

    `bt` sobe a ponte do microfone por Bluetooth; `bt-status` diagnostica.
    `mute`/`unmute`/`release` mexem no mudo do FIRMWARE do controle
    (MIC-USB-01, camada 3); `promote`/`demote` na política de microfone padrão.
    `uniq` (MAC normalizado) escolhe o controle nas ações de firmware.
    """
    action = action.lower()
    if action in _ACOES_BT:
        raise typer.Exit(code=_mic_bt(status_apenas=action == "bt-status"))
    if action in _ACOES_FIRMWARE:
        raise typer.Exit(code=_mic_firmware(_ACOES_FIRMWARE[action], uniq=uniq))

    flag = _ACTION_FLAG.get(action)
    if flag is None:
        console.print(
            f"[red]ação inválida: {action}[/red] — use: on | off | status | "
            "promote | demote | mute | unmute | release | bt | bt-status"
        )
        raise typer.Exit(code=2)

    script = _find_script()
    if script is None:
        console.print(
            f"[red]{_SCRIPT_NAME} não encontrado[/red] — reinstale ou rode o script "
            "manualmente."
        )
        raise typer.Exit(code=1)

    rc = subprocess.run(["bash", str(script), flag], check=False).returncode
    # disable-source devolve 2 quando o DualSense é a única fonte (aviso, não falha).
    if action == "off" and rc == 2:
        rc = 0
    raise typer.Exit(code=rc)


# ---------------------------------------------------------------------------
# Mudo no FIRMWARE do controle (MIC-USB-01, camada 3)
# ---------------------------------------------------------------------------


def _mic_firmware(muted: bool | None, *, uniq: str | None = None) -> int:
    """Manda `mic.set` ao daemon e imprime o que o controle passou a declarar.

    MIC-USB-01. Este é o PRIMEIRO chamador do `mic.set` — o método nasceu nesta
    sprint porque o backend tinha `set_microphone_mute` desde o AUDIO-OWNER-01 e
    ele não estava exposto em superfície nenhuma: para desmutar o microfone só
    existia o botão físico do controle.

    Os três pedidos são diferentes e nenhum é "não mexer":

    - ``True``  — muta, e a partir daí NÓS somos os donos do registrador;
    - ``False`` — desmuta, e o botão físico deixa de valer enquanto durar;
    - ``None``  — devolve a posse ao `hid-playstation`, que volta a alternar o
      mudo na borda do botão físico. É o único que "solta" o controle.

    O que sai impresso é a LEITURA do byte de estado do report de INPUT, que
    pode vir um report atrás da escrita — por isso a linha diz o que o firmware
    DECLARA agora, e não o eco do que acabamos de mandar.
    """
    import asyncio

    from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

    payload: dict[str, object] = {"muted": muted}
    if uniq:
        payload["uniq"] = uniq

    async def _chamar() -> dict[str, object] | None:
        try:
            async with IpcClient.connect() as client:
                resposta = await client.call("mic.set", payload)
        except (FileNotFoundError, ConnectionError, IpcError, OSError):
            return None
        return resposta if isinstance(resposta, dict) else {}

    resultado = asyncio.run(_chamar())
    if resultado is None:
        console.print(
            "[red]daemon offline[/red] — o mudo do firmware só se altera pelo "
            "daemon (inicie com 'hefesto-dualsense4unix daemon start'), ou "
            "aperte o botão de microfone do controle."
        )
        return 1
    if resultado.get("status") != "ok":
        console.print(
            "[yellow]nenhum controle recebeu o pedido[/yellow] — conecte o "
            "DualSense (ou confira o MAC passado em uniq)."
        )
        return 1

    pedido = {True: "MUDO", False: "ATIVO", None: "posse devolvida ao kernel"}[muted]
    console.print(f"  microfone do firmware .... {pedido}")
    audio = resultado.get("audio")
    if isinstance(audio, dict):
        declarado = audio.get("mic_mudo")
        selo = "MUDO" if declarado else "ativo"
        console.print(f"  o controle declara ....... {selo}")
        if declarado:
            console.print(
                "  [dim]ainda mudo? o firmware pode levar um report para "
                "convergir. Se o medidor seguir parado, o resto é WirePlumber: "
                "rode `scripts/doctor.sh --fix`.[/dim]"
            )
    else:
        console.print(
            "  [dim]o controle ainda não entregou um report de estado — o selo "
            "aparece no próximo tick.[/dim]"
        )
    return 0


# ---------------------------------------------------------------------------
# Microfone por Bluetooth (BT-MIC-01)
# ---------------------------------------------------------------------------
#
# A ARBITRAGEM DA PORTA — QUATRO-MICROFONES-01/E3, 25/08/2026
# ------------------------------------------------------------
# O estudo `docs/process/estudos/2026-08-16-O-PS-PRESO-*.md` mediu um DualSense
# travado com a ponte de pé e nomeou a causa provável: **dois donos do report
# `0x32`**. Dali saiu a regra 5.c, que é desta casa e vale para este arquivo:
#
#   *Instrumento que ESCREVE ou que toma posse de um recurso não é instrumento
#   — é mudança de estado.*
#
# `mic bt` é exatamente esse instrumento: ele abre o hidraw em RDWR e escreve
# `0x32`. E até 25/08 ele o fazia **sem perguntar se alguém já estava lá** — o
# subsystem `bt_mic` do daemon sobe a MESMA ponte, no MESMO nó, com um contador
# de sequência PRÓPRIO, porque é outro processo. Dois donos do `0x32` feitos
# pelo próprio produto, sem kernel nenhum no meio.
#
# A cura é a arbitragem NA PORTA, e ela usa um fato que o produto já publica
# desde 23/08: `daemon.state_full` → `bt_mic.uniqs`, os `uniq` cuja ponte SUBIU.
# `mic bt` lê essa lista e **não sobe ponte em cima de quem já tem uma**.
#
# O LIMITE, DECLARADO: isto fecha o sentido CLI → daemon, e só ele. O daemon
# não sabe que este processo existe, então uma ponte que ELE suba depois ainda
# passa por cima da nossa. Fechar os dois sentidos é a arbitragem do nó no
# broker — o portão 5.a de `2026-08-16-O-QUE-FICOU-ABERTO-01`, que **não
# existe** (`broker/hidraw_broker.py::_cmd_open`: *"`open` NÃO altera
# lease/refcount"*). O portão que vigia essa dívida é
# `tests/unit/test_portao_a_ponte_do_mic_espera_a_arbitragem.py`.


#: Situações que a régua abaixo sabe distinguir. `"velho"` é a que importa:
#: o daemon diz que há ponte de pé e NÃO diz de quem.
_SEM_DAEMON = "sem-daemon"
_DAEMON_VELHO = "velho"
_DAEMON_RESPONDE = "ok"


def _pontes_ja_de_pe() -> tuple[frozenset[str], str]:
    """Quem JÁ tem ponte de microfone de pé, pela régua do daemon.

    Devolve `(uniqs normalizados, situação)`.

    **Ausência de notícia não é notícia boa** — é a lição do
    `O-PRODUTO-RESPONDE-PELO-TRANSPORTE`. Um daemon que não publica `bt_mic`,
    ou que publica `running: true` sem a chave `uniqs` (o daemon vivo é mais
    velho que o código — a chave nasceu em 23/08), cai em `_DAEMON_VELHO`, e
    quem chama RECUSA em vez de assumir que o caminho está livre.

    Daemon offline é diferente e é sabível: sem daemon não há subsystem, logo
    não há ponte do produto de pé, e o caminho à mão é legítimo.
    """
    import asyncio

    from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError

    async def _chamar() -> dict[str, object] | None:
        try:
            async with IpcClient.connect() as client:
                resposta = await client.call("daemon.state_full")
        except (FileNotFoundError, ConnectionError, IpcError, OSError):
            return None
        return resposta if isinstance(resposta, dict) else {}

    estado = asyncio.run(_chamar())
    if estado is None:
        return frozenset(), _SEM_DAEMON
    return _ler_bloco_bt_mic(estado)


def _ler_bloco_bt_mic(estado: dict[str, object]) -> tuple[frozenset[str], str]:
    """A leitura pura do bloco `bt_mic` do `state_full` — sem IPC, testável."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    bloco = estado.get("bt_mic")
    if not isinstance(bloco, dict):
        return frozenset(), _DAEMON_VELHO
    uniqs = bloco.get("uniqs")
    if isinstance(uniqs, list):
        return frozenset(
            n for n in (norm_mac(str(u)) or "" for u in uniqs) if n
        ), _DAEMON_RESPONDE
    # Sem a chave `uniqs`: só é seguro concluir "ninguém" quando o daemon diz,
    # ele mesmo, que o subsystem NÃO está de pé.
    if not bloco.get("running"):
        return frozenset(), _DAEMON_RESPONDE
    return frozenset(), _DAEMON_VELHO


def _livres(nos: list[Any], ja_de_pe: frozenset[str]) -> tuple[list[Any], list[Any]]:
    """Reparte os nós em `(livres, tomados)` pelo conjunto do daemon."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    livres: list[Any] = []
    tomados: list[Any] = []
    for no in nos:
        uniq = norm_mac(str(getattr(no, "uniq", ""))) or ""
        (tomados if uniq and uniq in ja_de_pe else livres).append(no)
    return livres, tomados


def _mic_bt(*, status_apenas: bool) -> int:
    """Diagnostica (e opcionalmente sobe) a ponte do mic por BT. Devolve o rc.

    Import tardio de propósito: `mic on/off/status` não pode passar a depender
    de nada que a ponte carrega (ctypes/libopus), e o CLI inteiro não pode
    ficar mais lento por causa de um subcomando.
    """
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
        GerenciadorMicBluetooth,
        diagnosticar,
        nos_dualsense_bluetooth,
    )

    diag = diagnosticar()
    console.print("[bold]Microfone do DualSense por Bluetooth[/bold]")
    console.print(
        f"  libopus ............ {diag.libopus or '[red]ausente[/red]'}\n"
        f"  pactl .............. {'ok' if diag.pactl else '[red]ausente[/red]'}\n"
        f"  module-pipe-source . {'ok' if diag.pipe_source else '[red]ausente[/red]'}\n"
        f"  broker de hidraw ... {'ok' if diag.broker else 'ausente (usa os.open)'}"
    )
    if diag.controles:
        for no in diag.controles:
            console.print(f"  controle BT ........ {no.caminho}  {no.uniq}")
    else:
        console.print("  controle BT ........ [yellow]nenhum[/yellow]")

    ja_de_pe, situacao = _pontes_ja_de_pe()
    if situacao == _DAEMON_VELHO:
        console.print(
            "  pontes do daemon ... [yellow]não sei[/yellow] (o daemon vivo não "
            "publica `bt_mic.uniqs`)"
        )
    elif ja_de_pe:
        console.print(f"  pontes do daemon ... {', '.join(sorted(ja_de_pe))}")
    else:
        console.print("  pontes do daemon ... nenhuma")

    if not diag.pronto:
        for falta in diag.impedimentos:
            console.print(f"  [yellow]![/yellow] {falta}")
        # Falta de controle em BT não é erro do programa: é o estado normal de
        # quem está no cabo. Só o que a usuária pode CONSERTAR vira rc != 0.
        return 0 if not diag.controles and diag.libopus and diag.pactl else 1
    if status_apenas:
        console.print("\n  pronto — `hefesto-dualsense4unix mic bt` sobe a ponte.")
        return 0

    # A ARBITRAGEM DA PORTA (ver o cabeçalho da seção). Duas recusas, e cada
    # frase diz O QUÊ, POR QUÊ e O QUE FAZER — é a regra desta casa para
    # diagnóstico.
    if situacao == _DAEMON_VELHO:
        console.print(
            "\n[red]não subo a ponte[/red] — o daemon está de pé e não diz de "
            "quem são as pontes que ele segura.\n"
            "  Por quê: subir a segunda ponte no mesmo controle põe DOIS donos "
            "no report 0x32, que foi o que travou um DualSense em 16/08/2026.\n"
            "  O que fazer: reinicie o daemon sobre esta versão "
            "(`hefesto-dualsense4unix daemon restart`) e rode de novo — daí ele "
            "publica `bt_mic.uniqs` e esta régua enxerga."
        )
        return 1

    livres, tomados = _livres(diag.controles, ja_de_pe)
    for no in tomados:
        console.print(
            f"  [dim]pulo {no.uniq}: o daemon já segura a ponte dele[/dim]"
        )
    if not livres:
        console.print(
            "\n[yellow]nada a fazer[/yellow] — todo controle em BT já tem ponte "
            "de microfone de pé, e quem a segura é o daemon.\n"
            "  Por quê: uma segunda ponte no mesmo controle seria um segundo "
            "dono do report 0x32.\n"
            "  O que fazer: para desligar, use o interruptor do card na aba "
            "Configurações — quem subiu é quem derruba."
        )
        return 0

    gerenciador = GerenciadorMicBluetooth()
    parar = threading.Event()

    def _sinal(_sig: int, _frm: object) -> None:
        parar.set()
        gerenciador.parar()

    # SIGINT/SIGTERM param a ponte pelo MESMO caminho do Ctrl-C: o `parar()`
    # manda o 0x32 de desligar em cada controle. Sair sem isso deixaria o
    # microfone de alguém ligado — o pior fim possível para este comando.
    for sig in (signal.SIGINT, signal.SIGTERM):
        # `signal.signal` levanta ValueError fora da thread principal.
        with contextlib.suppress(ValueError):
            signal.signal(sig, _sinal)

    console.print("\n  subindo a ponte… (Ctrl-C encerra e desliga o mic)\n")
    # Legenda do "sem-ouvinte": enquanto NENHUM app estiver gravando, o
    # PipeWire deixa a source suspensa e não drena o fifo — a ponte descarta os
    # quadros em vez de bloquear (é a invariante do módulo). Ver ~100% de
    # descarte com o medidor parado é o comportamento CERTO, não uma falha; o
    # número cai para perto de zero assim que alguém abre o microfone.
    console.print(
        "  [dim]sem-ouvinte = quadros descartados porque nenhum app está "
        "gravando (esperado)[/dim]\n"
    )
    try:
        while not parar.is_set():
            # A LISTA vai explícita a cada volta, e é a arbitragem da porta
            # acontecendo ao VIVO: se o daemon subir a ponte de um controle no
            # meio da sessão, ele sai da lista e a NOSSA ponte cai na mesma
            # volta — em vez de dois donos do 0x32 convivendo. Sem daemon, o
            # conjunto é vazio e nada é filtrado.
            de_pe, agora = _pontes_ja_de_pe()
            if agora == _DAEMON_VELHO:
                console.print(
                    "  [yellow]o daemon parou de dizer de quem são as pontes — "
                    "encerro para não virar o segundo dono do 0x32[/yellow]"
                )
                break
            alvos, _ = _livres(nos_dualsense_bluetooth(), de_pe)
            gerenciador.reconciliar(alvos)
            pontes = gerenciador.pontes
            if not pontes:
                console.print("  [yellow]nenhuma ponte de pé[/yellow]")
            for ponte in pontes.values():
                st = ponte.estatistica()
                selo = "MUDO" if st.mudo else "ativo"
                entregues = max(0, st.quadros_audio - st.quadros_descartados)
                console.print(
                    f"  [green]{st.source}[/green]  {selo}  "
                    f"quadros={st.quadros_audio} entregues={entregues} "
                    f"sem-ouvinte={st.quadros_descartados} "
                    f"invalidos={st.quadros_invalidos} rearmes={st.rearmes} "
                    f"mudo={st.mudo_pct:.0f}%"
                )
            if gerenciador.dormir(_RECONCILIA_S):
                break
    finally:
        gerenciador.parar()
        console.print("\n  ponte encerrada; microfone devolvido ao estado anterior.")
    return 0


__all__ = ["mic_cmd"]
