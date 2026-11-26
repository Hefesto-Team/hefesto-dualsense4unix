"""Subcomando `hefesto-dualsense4unix doctor` — health-check no CLI."""
from __future__ import annotations

import asyncio
import getpass
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br
from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError
from hefesto_dualsense4unix.core.formas_do_endereco import mascarar
from hefesto_dualsense4unix.daemon.subsystems.diario_do_corpo import (
    CHAVE_DO_SURDO,
    FALA_DA_RECUSA,
    PREFIXO_DO_CONTROLE,
)
from hefesto_dualsense4unix.utils.repo_files import (
    bases_de_instalacao,
    encontrar_arquivo_do_repo,
)

console = Console()

_GRAVIDADE_WARN = 1
_GRAVIDADE_FAIL = 2


@dataclass
class _Saida:
    """O que o ``--quiet``, o ``--json`` e o ``--para-colar`` pedem de toda linha.

    ``falhas`` e ``avisos`` somam o que o script e os blocos disseram, para o veredito do fim.
    """

    quiet: bool = False
    como_json: bool = False
    para_colar: bool = False
    contando: bool = True
    falhas: int = 0
    avisos: int = 0
    achados: list[dict[str, str]] = field(default_factory=list)


_SAIDA = _Saida()

_CONTAS_QUE_NAO_SE_ESCONDEM = {"root"}
_MENOS_LETRAS_QUE_ISSO_E_PALAVRA = 3


def _na_mascara(texto: str) -> str:
    """O texto como sai com ``--para-colar``: nenhum endereço inteiro, o home em ``~``, sem a conta.

    Sem a opção devolve o texto igual: o comando de cura que o doctor sugere precisa do endereço
    inteiro.
    """
    if not _SAIDA.para_colar:
        return texto
    casa = str(Path.home())
    conta = getpass.getuser()
    if casa not in ("", "/"):
        texto = texto.replace(casa, "~")
    if conta not in _CONTAS_QUE_NAO_SE_ESCONDEM and len(conta) >= _MENOS_LETRAS_QUE_ISSO_E_PALAVRA:
        texto = re.sub(rf"(?<![\w.-]){re.escape(conta)}(?![\w-])", "<conta>", texto)
    return mascarar(texto)


def _executar(args: list[str], ambiente: dict[str, str] | None = None) -> int:
    """Roda o comando e devolve o código; com ``--para-colar`` cada linha sai pela máscara."""
    env = {**os.environ, **ambiente} if ambiente else None
    if not _SAIDA.para_colar:
        return subprocess.run(args, check=False, env=env).returncode
    with subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        env=env,
    ) as processo:
        assert processo.stdout is not None
        for linha in processo.stdout:
            sys.stdout.write(_na_mascara(linha))
            sys.stdout.flush()
        return processo.wait()


def _bloco(titulo: str, linhas: Iterable[tuple[str, str]], **como_imprimir: Any) -> None:
    """O impressor único dos blocos em Python: cabeçalho, linhas, e o que o quiet e o json pedem.

    ``--quiet`` descarta as linhas ``[ OK ]`` e o cabeçalho que ficou sem linha; ``--json`` junta
    ``{bloco, tag, mensagem}`` em ``_SAIDA.achados`` e não imprime nada.
    """
    linhas = [(tag, _na_mascara(mensagem)) for tag, mensagem in linhas]
    if _SAIDA.contando:
        _SAIDA.falhas += sum(_o_nome_da_tag(tag) == "FAIL" for tag, _m in linhas)
        _SAIDA.avisos += sum(_o_nome_da_tag(tag) == "WARN" for tag, _m in linhas)
    if _SAIDA.como_json:
        _SAIDA.achados.extend(
            {"bloco": titulo, "tag": _o_nome_da_tag(tag), "mensagem": mensagem}
            for tag, mensagem in linhas
        )
        return
    visiveis = [(t, m) for t, m in linhas if not (_SAIDA.quiet and _o_nome_da_tag(t) == "OK")]
    if _SAIDA.quiet and not visiveis:
        return
    console.print(f"\n== {titulo} ==")
    for tag, mensagem in visiveis:
        console.print(f"{tag} {mensagem}", **como_imprimir)


def _o_nome_da_tag(tag: str) -> str:
    return tag.strip().strip("[]").strip().upper()


def _gravidade_das_linhas(linhas: list[tuple[str, str]]) -> int:
    """A pior gravidade entre as linhas ``(tag, mensagem)`` de um bloco."""
    pior = 0
    for tag, _mensagem in linhas:
        marca = _o_nome_da_tag(tag)
        if marca == "FAIL":
            pior = max(pior, _GRAVIDADE_FAIL)
        elif marca == "WARN":
            pior = max(pior, _GRAVIDADE_WARN)
    return pior


def _find_doctor_sh() -> Path | None:
    """Localiza `scripts/doctor.sh` na instalação que está rodando.

    BG-05 (25/08/2026): a busca era uma cópia LOCAL que conhecia três layouts
    — checkout, `/usr/share` e `/usr/local/share`. O Flatpak não é nenhum dos
    três, e a cópia gêmea em `app/actions/daemon_actions.py` já havia ganhado
    `/app/share` na T-02(b) do mesmo dia: duas respostas para a mesma pergunta,
    divergindo em silêncio. A resposta agora tem dono único, em
    `utils/repo_files.py`.
    """
    return encontrar_arquivo_do_repo("scripts/doctor.sh")


def _avisar_ausente(relpath: str, consequencia: str) -> None:
    """Diz que um script não veio nesta instalação — e ONDE se procurou."""
    console.print(f"[yellow]{relpath} não veio nesta instalação — {consequencia}[/yellow]")
    console.print("[dim]       procurei o share do Hefesto em:[/dim]")
    for base in bases_de_instalacao():
        onde = _na_mascara(str(base))
        console.print(f"[dim]         {onde}[/dim]", soft_wrap=True, highlight=False)


_PREFIXO_DO_RELOGIO = "poll.tique.relogio."
_TIQUE_PARADO_S = 2.0
_PARADAS_POR_MINUTO_QUE_AVISAM = 0.5
_VIDA_MINIMA_DA_TAXA_MIN = 10.0
_ESTOURO_DO_TIQUE_QUE_AVISA = 0.02
_TIQUES_PARA_JULGAR = 600
_O_QUE_CONFERIR = "confira janelas e bandejas abertas e as extensões"
_PREFIXO_DA_VOLTA = "poll.laco.lenta."
_PREFIXO_DO_OCUPANTE = "poll.pool.ocupante."
_SEM_AMOSTRA = "sem_amostra"
_SUFIXO_DOS_BLOCOS = ".blocos"


def _linha_do_nascimento(counters: Any) -> tuple[str, str] | None:
    """Os pads que nasceram fora do tique e a média do nascimento, dos contadores do store.

    O `vpad.nascimento_ms_total` é a SOMA dos nascimentos, não a última medida.
    ``None`` enquanto nenhum pad nasceu pelo fio.
    """
    if not isinstance(counters, dict):
        return None
    nascidos = counters.get("vpad.nascimentos")
    total = counters.get("vpad.nascimento_ms_total", 0)
    if not isinstance(nascidos, int) or isinstance(nascidos, bool) or nascidos <= 0:
        return None
    if not isinstance(total, int) or isinstance(total, bool):
        return None
    return (
        "[ OK ]",
        f"nascimento do pad fora do tique: {nascidos}, média {formata_pt_br(total / nascidos)} ms",
    )


def _linhas_do_corpo(counters: Any) -> list[tuple[str, str]]:
    """O que o Som no corpo tocou em cada controle, dos contadores que o minuto sobe ao store."""
    if not isinstance(counters, dict):
        return []
    contas: dict[str, tuple[int, dict[str, int]]] = {}
    for chave, valor in counters.items():
        if not isinstance(chave, str) or not chave.startswith(PREFIXO_DO_CONTROLE):
            continue
        if not isinstance(valor, int) or isinstance(valor, bool):
            continue
        rotulo, _ponto, conta = chave[len(PREFIXO_DO_CONTROLE):].partition(".recusa.")
        if conta:
            contas.setdefault(rotulo, (0, {}))[1][conta] = valor
        elif rotulo.endswith(_SUFIXO_DOS_BLOCOS):
            rotulo = rotulo[: -len(_SUFIXO_DOS_BLOCOS)]
            contas[rotulo] = (valor, contas.get(rotulo, (0, {}))[1])
    linhas = []
    for rotulo, (blocos, recusas) in sorted(contas.items()):
        ditas = ", ".join(
            f"{FALA_DA_RECUSA.get(motivo, motivo)} {n}"
            for motivo, n in sorted(recusas.items()) if n
        )
        tag = "[WARN]" if ditas and not blocos else "[ OK ]"
        ditas = ditas or "nenhuma"
        linhas.append((tag, f"Som no corpo, {rotulo}: {blocos} blocos com sinal; recusas: {ditas}"))
    surdos = counters.get(CHAVE_DO_SURDO)
    if isinstance(surdos, int) and not isinstance(surdos, bool) and surdos > 0:
        linhas.append(("[WARN]", f"ouvido do jogo ficou surdo {surdos} vez(es) com jogo aberto"))
    return linhas


def _linha_do_tique(counters: Any) -> tuple[str, str] | None:
    """O tique do daemon em uma linha, dos contadores do ``state_full``.

    O `_poll_loop` mede cada tique: quantos passaram do orçamento de 16,7 ms, o
    p99 e o pior da última janela, e o relógio lento que estava no pior tique.
    ``None`` quando o daemon ainda não mediu (ou não conhece a medida). Antes de a
    primeira janela fechar, o p99 e o pior ainda não existem, e a linha fica só
    com a contagem: medida que não há não sai como zero. O último tique mais velho
    que ``_TIQUE_PARADO_S`` é falha: o serviço responde, mas o controle não é lido.
    """
    if not isinstance(counters, dict):
        return None
    medidos = counters.get("poll.tique.medidos")
    if not isinstance(medidos, int) or isinstance(medidos, bool) or medidos <= 0:
        return None

    def ms(chave: str) -> str:
        valor = counters.get(chave)
        quanto = valor if isinstance(valor, int) and not isinstance(valor, bool) else 0
        return formata_pt_br(quanto / 1000)

    estouros = counters.get("poll.tique.estouros", 0)
    if not isinstance(estouros, int) or isinstance(estouros, bool):
        estouros = 0
    contagem = f"tique do laço: {estouros} de {medidos} acima de 16,7 ms"
    parte = estouros / medidos
    pesado = medidos >= _TIQUES_PARA_JULGAR and parte >= _ESTOURO_DO_TIQUE_QUE_AVISA
    marca = "[WARN]" if pesado else "[ OK ]"
    cobranca = (
        f"; {formata_pt_br(parte * 100)} % dos tiques acima do orçamento: {_O_QUE_CONFERIR}"
        if pesado
        else ""
    )
    ultimo = counters.get("poll.tique.ultimo_ms")
    if isinstance(ultimo, int) and not isinstance(ultimo, bool):
        ha_s = max(time.time() - ultimo / 1000, 0.0)
        if ha_s > _TIQUE_PARADO_S:
            parado = formata_pt_br(ha_s)
            return ("[FAIL]", f"tique do laço parado há {parado} s: o controle não é lido")
        contagem = f"{contagem}, o último há {formata_pt_br(ha_s)} s"
    if "poll.tique.p99_us" not in counters:
        return (marca, f"{contagem}{cobranca}")
    relogio = _o_pior_nome(counters, _PREFIXO_DO_RELOGIO)
    onde = f", o pior com «{relogio[0].replace('_', ' ')}»" if relogio is not None else ""
    atraso = ""
    if "poll.tique.atraso_p99_us" in counters:
        atraso = (
            f"; atraso p99 {ms('poll.tique.atraso_p99_us')} ms, "
            f"pior {ms('poll.tique.atraso_pior_us')} ms"
        )
    return (
        marca,
        f"{contagem}; p99 {ms('poll.tique.p99_us')} ms, pior {ms('poll.tique.pior_us')} ms{onde}"
        f"{atraso}{cobranca}",
    )


def _o_pior_nome(counters: dict[str, Any], prefixo: str) -> tuple[str, int] | None:
    """O nome de maior medida entre os contadores de ``prefixo``, e a medida em µs."""
    nomes = {
        chave[len(prefixo):]: valor
        for chave, valor in counters.items()
        if chave.startswith(prefixo)
        and isinstance(valor, int)
        and not isinstance(valor, bool)
        and valor > 0
    }
    if not nomes:
        return None
    pior = max(nomes, key=lambda nome: nomes[nome])
    return pior, nomes[pior]


def _linha_do_atraso(counters: Any, vida_s: float | None = None) -> tuple[str, str] | None:
    """O laço e o pool presos desde que o serviço subiu, com o nome de quem prendeu.

    ``None`` quando o daemon não conhece a medida. A janela do tique esquece em segundos:
    estes contadores são os que ainda valem depois de jogar. Com a ``vida_s`` do serviço, as
    paradas por minuto acima de ``_PARADAS_POR_MINUTO_QUE_AVISAM`` viram ``[WARN]`` (a vida conta
    ao menos ``_VIDA_MINIMA_DA_TAXA_MIN`` minutos, para as paradas da subida não acusarem).
    Sem a vida não há taxa, e a linha com parada é ``[INFO]``: o «não sei» nunca sai ``[ OK ]``.
    """
    if not isinstance(counters, dict) or "poll.laco.lentas" not in counters:
        return None
    lentas = counters.get("poll.laco.lentas", 0)
    filas = counters.get("poll.pool.lentas", 0)
    if not lentas and not filas:
        return ("[ OK ]", "atraso do serviço: nenhuma parada acima de 100 ms")
    partes = []
    if lentas:
        pior = _o_pior_nome(counters, _PREFIXO_DA_VOLTA)
        detalhe = "" if pior is None else f", a pior {formata_pt_br(pior[1] / 1000)} ms"
        if pior is not None and pior[0] != _SEM_AMOSTRA:
            detalhe += f" em «{pior[0]}»"
        palavra = "parada" if lentas == 1 else "paradas"
        partes.append(f"{lentas} {palavra} acima de 100 ms{detalhe}")
    if filas:
        pior = _o_pior_nome(counters, _PREFIXO_DO_OCUPANTE)
        detalhe = "" if pior is None else (
            f", a pior {formata_pt_br(pior[1] / 1000)} ms atrás de «{pior[0]}»"
        )
        palavra = "espera" if filas == 1 else "esperas"
        partes.append(f"{filas} {palavra} na fila do controle{detalhe}")
    texto = "atraso do serviço: " + "; ".join(partes)
    if vida_s is None:
        return ("[INFO]", f"{texto}; sem a vida do serviço, sem taxa")
    taxa = (int(lentas) + int(filas)) / max(vida_s / 60, _VIDA_MINIMA_DA_TAXA_MIN)
    if taxa < _PARADAS_POR_MINUTO_QUE_AVISAM:
        return ("[ OK ]", texto)
    em = f"{formata_pt_br(taxa)} por minuto em {formata_pt_br(vida_s / 60)} min de serviço"
    return ("[WARN]", f"{texto}; {em}: {_O_QUE_CONFERIR}")


def _vida_do_servico_s() -> float | None:
    """Segundos desde que a unit do serviço ficou ativa; ``None`` sem o número.

    Levanta ``OSError`` ou ``SubprocessError`` quando o ``systemctl`` não responde.
    """
    from hefesto_dualsense4unix.utils.identidade import HEFESTO

    feito = subprocess.run(
        ["systemctl", "--user", "show", HEFESTO.unit_daemon,
         "--property=ActiveEnterTimestampMonotonic", "--value"],
        capture_output=True, text=True, check=False, timeout=_PRAZO_DO_SYSTEMCTL_S,
    )
    valor = feito.stdout.strip()
    if not valor.isdigit() or int(valor) <= 0:
        return None
    return max(time.monotonic() - int(valor) / 1e6, 0.0)


def _ha_parada(counters: Any) -> bool:
    return isinstance(counters, dict) and bool(
        counters.get("poll.laco.lentas") or counters.get("poll.pool.lentas")
    )


def _linha_da_mascara_pro(estado: Any) -> tuple[str, str] | None:
    """O que a máscara Pro Controller entrega, quando algum controle a mostra ao jogo agora."""
    from hefesto_dualsense4unix.integrations.virtual_pad import (
        LINHA_DA_PRO_NO_UINPUT,
        o_jogo_ve_a_pro,
    )

    emulacao = estado.get("gamepad_emulation") if isinstance(estado, dict) else None
    if not isinstance(emulacao, dict) or not emulacao.get("enabled"):
        return None
    por_aparelho = emulacao.get("por_aparelho")
    if isinstance(por_aparelho, dict) and por_aparelho:
        mascaras = list(por_aparelho.values())
    else:
        mascaras = [emulacao.get("flavor")]
    if not o_jogo_ve_a_pro(emulacao.get("caminho"), mascaras):
        return None
    return ("[INFO]", LINHA_DA_PRO_NO_UINPUT)


_ROTULO_DO_TRANSPORTE = {"usb": "cabo", "bt": "rádio"}


def _linhas_do_firmware(controles: Any) -> list[tuple[str, str]]:
    """A versão do firmware de cada controle, do ``controller.list`` do daemon.

    A-VERSAO-DO-FIRMWARE-APARECE-NO-DOCTOR-E-NUNCA-SE-ATUALIZA-DAQUI-01. O daemon lê o
    ``update_version`` (feature 0x20) quando o controle conecta, e a versão chega aqui em
    ``firmware``; o doctor só LÊ o que ele disse, nunca escreve nada no controle. Abaixo do
    ``LIMITE_DA_VIBRACAO_V2`` o SDL e o jogo tratam o controle de outro jeito, e o defeito de um
    firmware velho parece defeito do Hefesto: o aviso diz onde se atualiza. O Edge é sempre v2 e
    tem outra numeração: ele mostra a versão e nunca avisa. Versão não lida é ``[INFO]``.
    """
    if not isinstance(controles, list):
        return []
    from hefesto_dualsense4unix.core.backend_pydualsense import (
        LIMITE_DA_VIBRACAO_V2,
        fala_a_vibracao_v2,
    )

    linhas: list[tuple[str, str]] = []
    for posicao, controle in enumerate(controles):
        if not isinstance(controle, dict) or not controle.get("connected"):
            continue
        numero = controle.get("numero")
        if not isinstance(numero, int) or isinstance(numero, bool):
            numero = posicao + 1
        via = _ROTULO_DO_TRANSPORTE.get(str(controle.get("transport")))
        nome = f"controle {numero}" + (f" ({via})" if via else "")
        versao = controle.get("firmware")
        if not isinstance(versao, int) or isinstance(versao, bool):
            linhas.append(("[INFO]", f"{nome}: a versão do firmware ainda não foi lida"))
        elif not fala_a_vibracao_v2(versao, edge=bool(controle.get("edge"))):
            linhas.append((
                "[WARN]",
                f"{nome}: firmware 0x{versao:04x}, anterior ao 0x{LIMITE_DA_VIBRACAO_V2:04x}: o "
                "controle vibra no modo antigo e o SDL o trata de outro jeito. Atualize pelo PS5 "
                "ou pelo aplicativo da Sony no Windows; o Hefesto nunca atualiza firmware",
            ))
        else:
            linhas.append(("[ OK ]", f"{nome}: firmware 0x{versao:04x}"))
    return linhas


def _linhas_de_quem_segura_o_pad(
    estado: Any, *, raiz_proc: str | None = None
) -> list[tuple[str, str]]:
    """Por controle, quem segura o pad virtual e por que conta ou não como jogo."""
    from hefesto_dualsense4unix.integrations.quem_segura_o_pad import quem_segura

    rumble = estado.get("rumble_ff") if isinstance(estado, dict) else None
    pads = rumble.get("per_vpad") if isinstance(rumble, dict) else None
    if not isinstance(pads, list):
        return []
    linhas: list[tuple[str, str]] = []
    for pad in pads:
        if not isinstance(pad, dict):
            continue
        nome = f"controle {pad.get('player')}"
        nos: dict[str, int | None] = {}
        for chave_no, chave_ino in (("evdev", "ino"), ("hidraw", "hidraw_ino")):
            caminho, ino = pad.get(chave_no), pad.get(chave_ino)
            if isinstance(caminho, str) and caminho:
                nos[caminho] = ino if isinstance(ino, int) else None
        if not nos:
            linhas.append(("[INFO]", f"{nome}: o nó do pad virtual não se achou"))
            continue
        vereditos = quem_segura(nos, raiz_proc=raiz_proc)
        if not vereditos:
            linhas.append(("[INFO]", f"{nome}: ninguém segura o pad virtual"))
        for segurador, jogo, motivo in vereditos:
            conta = "conta como jogo" if jogo else "não conta como jogo"
            linhas.append((
                "[INFO]",
                f"{nome}: {segurador.nome} (pid {segurador.pid}) segura o pad; {conta}: {motivo}",
            ))
    return linhas


async def _daemon_checks() -> list[tuple[str, str]]:
    """Checks que só o daemon conhece (via IPC). Retorna [(tag, mensagem)]."""
    rows: list[tuple[str, str]] = []
    try:
        async with IpcClient.connect() as client:
            status = await client.call("daemon.status")
            rows.append(("[ OK ]", "IPC responde (daemon.status atendido)"))
            if isinstance(status, dict) and status.get("paused"):
                rows.append(
                    ("[WARN]", "daemon PAUSADO — input suspenso ('daemon resume' p/ retomar)")
                )
            profiles = await client.call("profile.list")
            lista = profiles.get("profiles") if isinstance(profiles, dict) else None
            if isinstance(lista, list):
                rows.append(("[ OK ]", f"perfis listáveis via IPC ({len(lista)})"))
            else:
                rows.append(("[WARN]", "o daemon não respondeu a lista de perfis"))
            try:
                estado = await client.call("daemon.state_full")
            except IpcError:
                estado = None
            linha_do_tique = _linha_do_tique(
                estado.get("counters") if isinstance(estado, dict) else None
            )
            if linha_do_tique is not None:
                rows.append(linha_do_tique)
            contadores = estado.get("counters") if isinstance(estado, dict) else None
            vida_s = None
            if _ha_parada(contadores):
                try:
                    vida_s = _vida_do_servico_s()
                except (OSError, subprocess.SubprocessError) as exc:
                    rows.append(("[INFO]", f"vida do serviço ilegível ({type(exc).__name__})"))
            linha_do_atraso = _linha_do_atraso(contadores, vida_s)
            if linha_do_atraso is not None:
                rows.append(linha_do_atraso)
            linha_do_nascimento = _linha_do_nascimento(
                estado.get("counters") if isinstance(estado, dict) else None
            )
            if linha_do_nascimento is not None:
                rows.append(linha_do_nascimento)
            rows.extend(
                _linhas_do_corpo(estado.get("counters") if isinstance(estado, dict) else None)
            )
            linha_da_pro = _linha_da_mascara_pro(estado)
            if linha_da_pro is not None:
                rows.append(linha_da_pro)
            rows.extend(_linhas_de_quem_segura_o_pad(estado))
            try:
                controles = await client.call("controller.list")
            except IpcError:
                controles = None
            rows.extend(
                _linhas_do_firmware(
                    controles.get("controllers") if isinstance(controles, dict) else None
                )
            )
    except IpcError as exc:
        from hefesto_dualsense4unix.app.ipc_bridge import prazo_vencido

        if prazo_vencido(exc):
            rows.append(("[FAIL]", f"{exc.message} — o serviço está parado ou travado"))
        else:
            rows.append(("[WARN]", "daemon offline — checks de runtime pulados"))
    except (FileNotFoundError, ConnectionError):
        rows.append(("[WARN]", "daemon offline — checks de runtime pulados"))
    return rows


def _run_script(relpath: str, *args: str, confirm: str | None = None) -> int:
    """Roda um script do repo. `confirm` != None pede confirmação antes."""
    script = encontrar_arquivo_do_repo(relpath)
    if script is None:
        _avisar_ausente(relpath, "pulado")
        return 0
    if confirm is not None and not typer.confirm(confirm):
        console.print("[dim]cancelado.[/dim]")
        return 0
    return _executar(["bash", str(script), *args])


async def _state_full_ou_none() -> dict[str, Any] | None:
    """`daemon.state_full` via IPC; ``None`` com o daemon offline (best-effort)."""
    try:
        async with IpcClient.connect() as client:
            estado = await client.call("daemon.state_full")
            return estado if isinstance(estado, dict) else None
    except (FileNotFoundError, ConnectionError, IpcError, OSError):
        return None


def _print_storm_block() -> int:
    """Diagnóstico storm (FEAT-DSX-UNIFY-01) — read-only, sem sudo. Devolve a gravidade."""
    from hefesto_dualsense4unix.integrations import storm_doctor

    no_cabo = storm_doctor.controles_no_cabo(asyncio.run(_state_full_ou_none()))
    linhas = storm_doctor.storm_report(controles_no_cabo=no_cabo)
    _bloco("anti-storm / sistema", linhas)
    return _gravidade_das_linhas(linhas)


def _linhas_perfis() -> tuple[list[tuple[str, str]], bool]:
    """Verificação SEMÂNTICA dos perfis. Devolve (linhas, houve_erro)."""
    from hefesto_dualsense4unix.profiles import sanidade
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles, perfis_ilegiveis

    try:
        perfis = load_all_profiles()
    except OSError as exc:
        return ([("[WARN]", f"não deu para ler os perfis: {exc}")], False)
    ilegiveis = [
        ("[FAIL]", f"{i.arquivo}: ilegível: {i.motivo}. Restaure uma versão guardada "
                   f"(profile restore {Path(i.arquivo).stem}) ou apague o arquivo "
                   f"(profile delete {Path(i.arquivo).stem})")
        for i in perfis_ilegiveis()
    ]
    achados = sanidade.verificar_perfis(perfis)
    linhas = ilegiveis + sanidade.linhas_de_relatorio(achados, total_perfis=len(perfis))
    houve_erro = bool(ilegiveis) or any(a.gravidade == "erro" for a in achados)
    return (linhas, houve_erro)


def _print_bloco_perfis() -> bool:
    """Imprime o bloco de perfis. True quando há achado GRAVE (exit != 0)."""
    linhas, houve_erro = _linhas_perfis()
    _bloco("perfis (coerência entre eles)", linhas)
    return houve_erro


def _print_bloco_contratos() -> int:
    """Os contratos de fora (BlueZ, PipeWire, systemd, kernel, Steam, Proton, COSMIC).

    Devolve a gravidade do bloco.
    """
    from hefesto_dualsense4unix.integrations import contratos_de_fora

    linhas = contratos_de_fora.linhas_do_doctor()
    _bloco(
        "contratos de fora (o que o Hefesto assume dos outros)", linhas,
        soft_wrap=True, highlight=False,
    )
    return _gravidade_das_linhas(linhas)


def _print_bloco_proton_fixado() -> int:
    """O Proton fixado e o que o recibo diz de cada versão. Devolve a gravidade do bloco."""
    from hefesto_dualsense4unix.integrations import qualificar_proton

    linhas = qualificar_proton.linhas_do_doctor_desta_maquina()
    _bloco("Proton fixado (o recibo de cada versão)", linhas, soft_wrap=True, highlight=False)
    return _gravidade_das_linhas(linhas)


def _print_bloco_receitas() -> int:
    """As receitas de ambiente dos jogos e o pino da peça GDK. Devolve a gravidade do bloco."""
    from hefesto_dualsense4unix.integrations import receitas_de_ambiente

    linhas = receitas_de_ambiente.linhas_do_doctor()
    _bloco("receitas de ambiente dos jogos", linhas, soft_wrap=True, highlight=False)
    return _gravidade_das_linhas(linhas)


def _print_bloco_entrada() -> int:
    """A permissão de ler o teclado e o pedal do «Usar como botões de». Devolve a gravidade."""
    from hefesto_dualsense4unix.core.system_check import permissao_de_ler_a_entrada

    linhas = [permissao_de_ler_a_entrada()]
    _bloco(
        "teclado e pedal (o acionador da aba Conexões)", linhas, soft_wrap=True, highlight=False
    )
    return _gravidade_das_linhas(linhas)


_AVISOS_DO_REGISTRO = 5
_PRAZO_DO_SYSTEMCTL_S = 5
_LARGURA_DA_LINHA_DO_REGISTRO = 200
_LINHA_DE_AVISO = re.compile(
    r"\[(?:warning|error|critical)\s*\]|\"level\": \"(?:warning|error|critical)\""
)


def _linhas_do_registro(atual: Path) -> list[tuple[str, str]]:
    """Até onde o registro do serviço alcança, e os últimos avisos dele, do mais velho ao novo."""
    from hefesto_dualsense4unix.utils.logging_config import geracoes_do_registro

    try:
        geracoes = [c for c in geracoes_do_registro(atual) if c.is_file()]
        if not geracoes:
            return [("[INFO]", "registro do serviço: o arquivo nasce quando o serviço sobe")]
        tamanho = sum(c.stat().st_size for c in geracoes)
        with geracoes[-1].open(encoding="utf-8", errors="replace") as mais_velho:
            comeco = mais_velho.readline()[:16].replace("T", " ")
        avisos: list[str] = []
        for caminho in geracoes:
            texto = caminho.read_text(encoding="utf-8", errors="replace")
            achadas = [linha for linha in texto.splitlines() if _LINHA_DE_AVISO.search(linha)]
            avisos = [*achadas[-(_AVISOS_DO_REGISTRO - len(avisos)):], *avisos]
            if len(avisos) >= _AVISOS_DO_REGISTRO:
                break
    except OSError as exc:
        return [("[WARN]", f"registro do serviço: não deu para ler {atual} ({exc.strerror})")]
    desde = f"desde {comeco}, " if comeco else ""
    linhas = [("[ OK ]", f"registro do serviço: {formata_pt_br(tamanho / (1 << 20))} MB "
                         f"{desde}em {atual}")]
    linhas.extend(("[INFO]", aviso[:_LARGURA_DA_LINHA_DO_REGISTRO]) for aviso in avisos)
    return linhas


def _linha_das_voltas_sozinho() -> tuple[str, str] | None:
    """Quantas vezes o systemd reergueu o serviço (``NRestarts``); ``None`` sem o número."""
    from hefesto_dualsense4unix.utils.identidade import HEFESTO

    try:
        feito = subprocess.run(
            ["systemctl", "--user", "show", HEFESTO.unit_daemon, "--property=NRestarts",
             "--value"],
            capture_output=True, text=True, check=False, timeout=_PRAZO_DO_SYSTEMCTL_S,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ("[INFO]", f"as voltas sozinho do serviço não se leem ({type(exc).__name__})")
    valor = feito.stdout.strip()
    if not valor.isdigit():
        return None
    voltas = int(valor)
    if voltas == 0:
        return ("[ OK ]", "o serviço não reiniciou sozinho")
    return ("[INFO]", f"o serviço reiniciou sozinho {voltas} {'vez' if voltas == 1 else 'vezes'}")


def _print_bloco_registro() -> int:
    """O registro próprio do serviço e as voltas sozinho dele. Devolve a gravidade do bloco."""
    from hefesto_dualsense4unix.utils.logging_config import caminho_do_registro

    linhas = _linhas_do_registro(caminho_do_registro())
    voltas = _linha_das_voltas_sozinho()
    if voltas is not None:
        linhas.append(voltas)
    _bloco("registro do serviço", linhas, soft_wrap=True, highlight=False, markup=False)
    return _gravidade_das_linhas(linhas)


JANELA_DOS_FIOS_S = 1.0
FIOS_QUE_SE_MOSTRAM = 8


def _pid_do_servico() -> int | None:
    """O pid vivo do serviço pelo arquivo da instância única; ``None`` sem serviço de pé."""
    from hefesto_dualsense4unix.daemon.main import single_instance_name
    from hefesto_dualsense4unix.utils import single_instance

    pid = single_instance._read_existing_pid(single_instance._pid_file(single_instance_name()))
    if pid is None or not single_instance.is_alive(pid):
        return None
    if not single_instance._is_hefesto_dualsense4unix_process(pid):
        return None
    return pid


def _linhas_dos_fios(pid: int | None, janela_s: float = JANELA_DOS_FIOS_S) -> list[tuple[str, str]]:
    """O custo de cada fio do serviço numa janela: o total e os que mais gastam, pelo nome."""
    from hefesto_dualsense4unix.utils.nome_do_fio import custo_dos_fios

    if pid is None:
        return [("[INFO]", "fios do serviço: o serviço não está de pé")]
    try:
        custos = custo_dos_fios(pid, janela_s)
    except OSError as exc:
        return [("[INFO]", f"fios do serviço: não deu para ler /proc/{pid}/task ({exc.strerror})")]
    nucleo = sum(c.nucleo for c in custos)
    acordadas = sum(c.acordadas_s for c in custos)
    linhas = [("[INFO]", (
        f"{len(custos)} fios em {formata_pt_br(janela_s)} s: "
        f"{formata_pt_br(round(nucleo * 100, 1))}% de um núcleo, "
        f"{round(acordadas)} acordadas/s"
    ))]
    linhas.extend(
        ("[INFO]", (
            f"fio {c.nome}: {formata_pt_br(round(c.nucleo * 100, 1))}% de um núcleo, "
            f"{round(c.acordadas_s)} acordadas/s"
        ))
        for c in custos[:FIOS_QUE_SE_MOSTRAM]
        if c.nucleo or c.acordadas_s
    )
    return linhas


def _print_bloco_fios() -> int:
    """O custo de cada fio do serviço, pelo nome que ele leva no kernel. Só informa."""
    linhas = _linhas_dos_fios(_pid_do_servico())
    _bloco("fios do serviço (custo em 1 s)", linhas, soft_wrap=True, highlight=False, markup=False)
    return _gravidade_das_linhas(linhas)


def _print_bloco_install() -> int:
    """O install que o fecho da janela soltou e parou com um motivo. Devolve a gravidade."""
    from hefesto_dualsense4unix.app.actions.versao_ao_abrir import pendencia_do_install

    linha = pendencia_do_install()
    if linha is None:
        return 0
    _bloco("versão nova (o install do fecho da janela)", [linha], soft_wrap=True, highlight=False)
    return _gravidade_das_linhas([linha])


def _entregar_o_json() -> None:
    if _SAIDA.como_json:
        console.print_json(data=_SAIDA.achados)


def _rodar_o_doctor_sh(fix: bool, quiet: bool) -> int:
    sh = _find_doctor_sh()
    if sh is None:
        _avisar_ausente("scripts/doctor.sh", "só os checks do daemon")
        return 0
    args = ["bash", str(sh)]
    if fix:
        args.append("--fix")
    if quiet:
        args.append("--quiet")
    with tempfile.TemporaryDirectory() as pasta:
        contagem = Path(pasta) / "contagem"
        rc = _executar(args, {"HEFESTO_DOCTOR_CONTAGEM": str(contagem)})
        falhas, avisos = _a_contagem_do_script(contagem)
    falhas = max(falhas, 1 if rc else 0)
    _SAIDA.falhas += falhas
    _SAIDA.avisos += avisos
    return _GRAVIDADE_FAIL if rc else 0


def _a_contagem_do_script(arquivo: Path) -> tuple[int, int]:
    """As falhas e os avisos que o ``doctor.sh`` anotou ao fechar; ``(0, 0)`` sem a anotação."""
    try:
        falhas, avisos = arquivo.read_text(encoding="utf-8").split()
        return int(falhas), int(avisos)
    except (OSError, ValueError):
        return 0, 0


def _o_veredito(codigo: int) -> str:
    """A linha única que fecha o doctor: o total do script e dos blocos, e o código de saída.

    Os avisos do ``doctor.sh`` e os do bloco de perfis entram na conta e não mudam o código
    (D-0810-A-OPCAO-QUE-A-STEAM-DESFAZ-E-AVISO-DO-DOCTOR, D-1310-O-RC-DO-DOCTOR-E-O-PIOR-VEREDITO).
    """
    avisos = _SAIDA.avisos
    falhas = max(_SAIDA.falhas, 1 if codigo == _GRAVIDADE_FAIL else 0)
    ha = f"{avisos} {'aviso' if avisos == 1 else 'avisos'}"
    if codigo == _GRAVIDADE_FAIL:
        quebra = f"{falhas} {'falha' if falhas == 1 else 'falhas'}"
        return f"Diagnóstico: {quebra} e {ha}. Código de saída 2: há falha."
    if codigo == _GRAVIDADE_WARN:
        return f"Diagnóstico: {ha}, nenhuma falha. Código de saída 1: só avisos."
    if avisos:
        return (
            f"Diagnóstico: {ha}, nenhuma falha. "
            "Código de saída 0: esses avisos não mudam o código."
        )
    return "Diagnóstico: nenhum aviso e nenhuma falha. Código de saída 0."


def _rodar_o_doctor(
    fix: bool,
    quiet: bool,
    fix_safe: bool,
    perfis: bool,
    como_json: bool,
) -> None:
    if perfis:
        rc_perfis = 1 if _print_bloco_perfis() else 0
        _entregar_o_json()
        raise typer.Exit(code=rc_perfis)

    rc = 0 if como_json else _rodar_o_doctor_sh(fix, quiet)

    rc = max(rc, _print_storm_block())

    if _print_bloco_perfis():
        rc = _GRAVIDADE_FAIL

    rc = max(rc, _print_bloco_contratos())

    rc = max(rc, _print_bloco_proton_fixado())

    rc = max(rc, _print_bloco_receitas())

    rc = max(rc, _print_bloco_entrada())

    rc = max(rc, _print_bloco_registro())
    rc = max(rc, _print_bloco_install())

    linhas_do_daemon = asyncio.run(_daemon_checks())
    _bloco("daemon (via IPC)", linhas_do_daemon)
    rc = max(rc, _gravidade_das_linhas(linhas_do_daemon))
    rc = max(rc, _print_bloco_fios())
    _entregar_o_json()

    if fix_safe and not como_json:
        console.print("\n== fix-safe (sem sudo) ==")
        _run_script("scripts/disable_steam_input.sh", "--apply-quiet")
        _run_script("scripts/fix_wireplumber_default_source.sh", "--install")
        _run_script("scripts/install_snd_quirk.sh", "--runtime")
        _SAIDA.contando = False
        rc = max(rc, _print_storm_block())

    if _SAIDA.falhas:
        rc = _GRAVIDADE_FAIL
    if not como_json:
        console.print(f"\n{_o_veredito(rc)}", markup=False, highlight=False, soft_wrap=True)
    raise typer.Exit(code=rc)


def doctor_cmd(
    fix: bool = False,
    quiet: bool = False,
    fix_safe: bool = False,
    perfis: bool = False,
    como_json: bool = False,
    para_colar: bool = False,
) -> None:
    """Roda `scripts/doctor.sh` (infra) + diagnóstico storm + checks do daemon.

    ``como_json`` imprime só os blocos em Python como lista de ``{bloco, tag, mensagem}``: o
    `doctor.sh` e o ``--fix-safe`` falam em texto e ficam de fora. ``para_colar`` passa toda linha
    pela máscara da casa (nenhum endereço inteiro, o home em ``~``, sem o nome da conta): é a saída
    que um relato público pede.
    """
    _SAIDA.quiet, _SAIDA.como_json, _SAIDA.achados = quiet, como_json, []
    _SAIDA.para_colar = para_colar
    _SAIDA.contando, _SAIDA.falhas, _SAIDA.avisos = True, 0, 0
    try:
        _rodar_o_doctor(fix, quiet, fix_safe, perfis, como_json)
    finally:
        _SAIDA.quiet, _SAIDA.como_json, _SAIDA.achados = False, False, []
        _SAIDA.para_colar = False
        _SAIDA.contando, _SAIDA.falhas, _SAIDA.avisos = True, 0, 0


__all__ = ["doctor_cmd"]
