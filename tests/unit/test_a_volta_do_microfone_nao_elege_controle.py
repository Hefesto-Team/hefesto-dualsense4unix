"""A-VOLTA-DO-MICROFONE-NAO-ELEGE-CONTROLE-01 — calar não elege um controle calado.

O QUE ELA VIU NA BANCADA DE 29/09/2026 (B1.3)
---------------------------------------------
Os quatro DualSense pelo rádio, só o roxo no ar e a fonte padrão da máquina;
o vermelho, o branco e o azul calados. Ela calou o roxo pelo botão, e 166 ms
depois o diário tinha ``eleicao_mic_ok alvo=<o canal do vermelho>``. Três
calas, três vezes o vermelho: o padrão da máquina foi para um microfone que
ninguém ligou, e o rádio do vermelho acordou para entregar silêncio. Em 28/09
(G8) foi pior: a volta escreveu o canal do PRÓPRIO controle que calava.

A CAUSA
-------
A volta fazia a pergunta do INSTALL (`--melhor-fonte-elegivel`), cuja lista
deixa o canal por controle entrar de propósito (§D.2 da MIC-PADRAO-NO-CABO-01).
A resposta era o canal do controle cujo nó nasceu primeiro no PipeWire. A cura
dá uma pergunta só à eleição (`EleitorDeMicrofone.passar_o_padrao`): quem está
no ar, depois a captura da máquina que não é controle nenhum
(`outra_captura_elegivel`), e sem as duas o padrão fica.

O QUE ESTE ARQUIVO MEDE
-----------------------
Com o eleitor DO PRODUTO, o laço DO PRODUTO (`hotkey.ligar_o_microfone`) e o
subsystem DO PRODUTO (`bt_mic`). O dublê é o `pactl` e o script, e ele responde
o que o script responde: a régua 1 confere isso rodando o script e o
`doctor.sh` de verdade sobre a mesma lista, com um `pactl` de mentira num PATH
temporário. Nenhum teste daqui fala com o servidor de som dela.

Os endereços são da faixa sintética da casa, com os octetos 4 e 5 zerados, e
cada cor tem o último octeto que a sprint usa.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.subsystems import bt_mic, hotkey, recado_do_microfone
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as elm

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "fix_wireplumber_default_source.sh"

VERMELHO = "aa:bb:cc:00:00:03"
BRANCO = "aa:bb:cc:00:00:ab"
AZUL = "aa:bb:cc:00:00:d8"
ROXO = "aa:bb:cc:00:00:f0"
OS_QUATRO = (VERMELHO, BRANCO, AZUL, ROXO)

#: A entrada analógica da placa, com a porta ativa `not available` (nada no
#: jack): é o único microfone de placa da máquina dela, e ele não se sustenta.
PLACA = "alsa_input.pci-0000_0c_00.4.analog-stereo"
MONITOR_SPDIF = "alsa_output.pci-0000_0c_00.4.iec958-stereo.monitor"
MONITOR_HDMI = "alsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor"
#: Um headset de outra pessoa: porta usável, e não é controle nenhum.
HEADSET = "alsa_input.usb-Fabricante_Headset_USB-00.mono-fallback"
#: A fonte que o KERNEL publica para o DualSense no cabo.
NO_DO_KERNEL = (
    "alsa_input.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller-00.HiFi__Mic__source"
)


def _n(uniq: str) -> str:
    return norm_mac(uniq) or uniq


def _canal(uniq: str) -> str:
    """O canal por controle, com a grafia que `canal_do_microfone` publica."""
    return f"hefesto_mic_{_n(uniq)[-6:]}"


# ---------------------------------------------------------------------------
# A lista de fontes, e o que o script responde sobre ela
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Fonte:
    indice: int
    nome: str
    #: `None` = o nó não tem porta (monitor, canal virtual); `True` = porta
    #: ativa usável; `False` = porta ativa `not available`.
    porta: bool | None = None


def _mesa_de(canais: tuple[str, ...], *extra: _Fonte) -> list[_Fonte]:
    """A lista de 29/09 (mascarada), com os canais NA ORDEM dada.

    A ordem é a do índice do PipeWire, que é o que o `_melhor_source_de_captura`
    lê. A entrada da placa tem índice MENOR que o de todos os canais, como na
    bancada, e sai pelo filtro de porta.
    """
    fontes = [
        _Fonte(67, MONITOR_SPDIF),
        _Fonte(68, PLACA, porta=False),
        _Fonte(69, MONITOR_HDMI),
    ]
    for i, uniq in enumerate(canais):
        fontes.append(_Fonte(280 + 50 * i, _canal(uniq)))
    fontes.extend(extra)
    return sorted(fontes, key=lambda f: f.indice)


#: A mesa de 29/09: o vermelho nasceu primeiro (280), depois o azul, o roxo e
#: o branco (405, 412, 421 na bancada).
MESA_DE_29 = (VERMELHO, AZUL, ROXO, BRANCO)


def _curta(fontes: list[_Fonte]) -> str:
    return "".join(
        f"{f.indice}\t{f.nome}\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED\n" for f in fontes
    )


def _longa(fontes: list[_Fonte]) -> str:
    blocos = []
    for f in fontes:
        linhas = [f"Source #{f.indice}", f"\tName: {f.nome}", f"\tDescription: {f.nome}"]
        if f.porta is not None:
            disp = "" if f.porta else ", not available"
            linhas += [
                "\tPorts:",
                f"\t\tanalog-input-mic: Microphone (type: Mic, priority: 8700{disp})",
                "\tActive Port: analog-input-mic",
            ]
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos) + "\n"


def _elegiveis(fontes: list[_Fonte]) -> list[str]:
    """A `fontes_elegiveis` do script: porta usável, sem DualSense, sem monitor."""
    return [
        f.nome
        for f in fontes
        if f.porta is not False
        and "dualsense" not in f.nome.lower()
        and not f.nome.lower().endswith(".monitor")
    ]


def responde_melhor(fontes: list[_Fonte]) -> str:
    """O que `--melhor-fonte-elegivel` responde: a PERGUNTA DO INSTALL."""
    elegiveis = _elegiveis(fontes)
    return elegiveis[0] if elegiveis else ""


def responde_outra(fontes: list[_Fonte]) -> str:
    """O que `--outra-captura-elegivel` responde: sem canal de controle nenhum."""
    elegiveis = [n for n in _elegiveis(fontes) if not n.lower().startswith("hefesto_mic_")]
    return elegiveis[0] if elegiveis else ""


def responde_sustenta(fontes: list[_Fonte], nome: str) -> str:
    """O que `--fonte-se-sustenta <nome>` responde: o nome, se a porta se sustenta."""
    return nome if any(f.nome == nome and f.porta is not False for f in fontes) else ""


# ---------------------------------------------------------------------------
# O PipeWire e o WirePlumber de mentira — as bordas do eleitor, e só elas
# ---------------------------------------------------------------------------


@dataclass
class _PipeWire:
    fontes: list[_Fonte]
    #: A fonte padrão CRUA — o que `pactl get-default-source` imprime.
    ativo: str = ""
    escritas: list[str] = field(default_factory=list)
    perguntas: list[str] = field(default_factory=list)

    def rodar(self, argv: list[str]) -> tuple[int, str]:
        if argv[:2] == ["pactl", "get-default-source"]:
            return (0, self.ativo)
        if argv[:2] == ["pactl", "set-default-source"]:
            self.escritas.append(argv[2])
            self.ativo = argv[2]
            return (0, "")
        if argv[:4] == ["pactl", "list", "sources", "short"]:
            return (0, _curta(self.fontes))
        if argv[:1] == ["bash"] and len(argv) >= 3:
            flag = argv[2]
            self.perguntas.append(flag)
            if flag == "--fonte-se-sustenta":
                return (0, responde_sustenta(self.fontes, argv[3]))
            if flag == "--outra-captura-elegivel":
                return (0, responde_outra(self.fontes))
            if flag == "--melhor-fonte-elegivel":
                return (0, responde_melhor(self.fontes))
        raise AssertionError(f"pergunta que esta régua não conhece: {argv}")


class _Backend:
    """Os quatro na mesa. `cabo` diz quem está no fio; o resto, no rádio."""

    def __init__(self, cabo: str | None = None) -> None:
        self.na_mesa = list(OS_QUATRO)
        self.cabo = cabo
        self.mudo: dict[str, bool] = {_n(u): True for u in OS_QUATRO}
        self.leds: dict[str, bool] = {}

    def sair(self, uniq: str) -> None:
        self.na_mesa = [u for u in self.na_mesa if u != uniq]

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [
            {
                "uniq": u,
                "connected": True,
                "transport": "usb" if u == self.cabo else "bluetooth",
            }
            for u in self.na_mesa
        ]

    def audio_status_for(self, uniq: str | None = None) -> dict[str, Any]:
        return {"mic_mudo": self.mudo.get(_n(uniq or ""))}

    def set_microphone_mute(self, muted: bool | None, *, uniq: str | None = None) -> bool:
        if isinstance(muted, bool):
            self.mudo[_n(uniq or "")] = muted
        return True

    def set_mic_led(self, aceso: Any, *, uniq: str | None = None) -> None:
        self.leds[_n(uniq or "")] = bool(aceso)


class _Daemon:
    def __init__(self, backend: _Backend) -> None:
        self.controller = backend
        self._tasks: list[Any] = []
        self.config = SimpleNamespace(mic_button_toggles_system=True)

    def _is_stopping(self) -> bool:
        return False

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        """Sem `**kwargs` — a assinatura do daemon real."""
        return fn(*args)


@pytest.fixture()
def sem_processo(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Um `pactl` que escapasse do dublê reprova, em vez de chegar ao som dela."""

    def _recusa(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"esta régua tentou rodar processo: {args!r}")

    monkeypatch.setattr(subprocess, "run", _recusa)
    monkeypatch.setattr(subprocess, "Popen", _recusa)
    hotkey._ECO_DO_ATO.clear()
    hotkey._CANAL_POR_UNIQ.clear()
    yield
    hotkey._ECO_DO_ATO.clear()
    hotkey._CANAL_POR_UNIQ.clear()


def _montar(
    monkeypatch: pytest.MonkeyPatch, fontes: list[_Fonte], *, cabo: str | None = None
) -> SimpleNamespace:
    """A mesa: o PipeWire de mentira por baixo, o produto inteiro por cima."""
    pw = _PipeWire(fontes=fontes)
    monkeypatch.setattr(elm, "_rodar", pw.rodar)
    # O script é o DE VERDADE para o `_script_conhece`: é o arquivo do disco
    # que diz se conhece a pergunta. Quem responde é o dublê, acima.
    monkeypatch.setattr(elm, "_script_do_wireplumber", lambda: SCRIPT)
    monkeypatch.setattr(elm, "casamento_usb_agora", lambda _uniqs: None)
    monkeypatch.setattr(elm, "SETTLE_PASSOS", 2)
    monkeypatch.setattr(elm, "SETTLE_PASSO_S", 0.0)
    monkeypatch.setattr(elm, "ESPERA_DO_CANAL_PASSOS", 1)
    monkeypatch.setattr(elm, "ESPERA_DO_CANAL_PASSO_S", 0.0)
    registro = bt_mic.RegistroDePedidosDeCanal()
    sub = bt_mic.BtMicSubsystem(registro=registro)
    anteriores = elm.registrar_dizedor_do_no_ar(
        sub.no_ar, sub.esquecer_a_palavra, sub.palavra_no_ar
    )
    pedidor = elm.registrar_pedidor_de_canal(sub.pedir_canal)
    backend = _Backend(cabo=cabo)
    return SimpleNamespace(
        pw=pw,
        registro=registro,
        sub=sub,
        backend=backend,
        daemon=_Daemon(backend),
        restaurar=lambda: (
            elm.registrar_dizedor_do_no_ar(*anteriores),
            elm.registrar_pedidor_de_canal(pedidor),
        ),
    )


@pytest.fixture()
def mesa(monkeypatch: pytest.MonkeyPatch, sem_processo: Any) -> Any:
    feitas: list[SimpleNamespace] = []

    def _fazer(fontes: list[_Fonte], *, cabo: str | None = None) -> SimpleNamespace:
        m = _montar(monkeypatch, fontes, cabo=cabo)
        feitas.append(m)
        return m

    yield _fazer
    for m in feitas:
        m.restaurar()


async def _apertar(m: SimpleNamespace, uniq: str, *, ligado: bool) -> Any:
    """O botão do plástico: o kernel já alternou o bit quando a borda chega."""
    m.backend.mudo[_n(uniq)] = not ligado
    return await hotkey.ligar_o_microfone(m.daemon, uniq, ligado=ligado)


def _eleitor(m: SimpleNamespace) -> Any:
    return hotkey._eleitor(m.daemon)


def _no_ar(m: SimpleNamespace) -> list[str]:
    return hotkey._no_ar_da_sessao(m.daemon).todos()


# ---------------------------------------------------------------------------
# 1. A pergunta, no script de verdade
# ---------------------------------------------------------------------------


def _script_de_verdade(tmp_path: Path, fontes: list[_Fonte], flag: str) -> str:
    """O `fix_wireplumber_default_source.sh` e o `doctor.sh` DE VERDADE.

    O `pactl` é de mentira, num PATH temporário (o molde de `_dubla_pactl`,
    `test_o_instalador_que_aprovou_o_monitor.py`), e o `HOME` também: as duas
    perguntas são consulta, e mesmo assim nada aqui toca o `~` dela.
    """
    binario = tmp_path / "bin"
    binario.mkdir(exist_ok=True)
    (binario / "pactl.curto").write_text(_curta(fontes), encoding="utf-8")
    (binario / "pactl.longo").write_text(_longa(fontes), encoding="utf-8")
    pactl = binario / "pactl"
    pactl.write_text(
        "#!/bin/bash\n"
        'case "$*" in\n'
        '  "list sources short") cat "$0.curto" ;;\n'
        '  "list sources") cat "$0.longo" ;;\n'
        "  *) : ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    pactl.chmod(0o755)
    casa = tmp_path / "casa"
    casa.mkdir(exist_ok=True)
    env = {
        "PATH": f"{binario}:/usr/bin:/bin",
        "HOME": str(casa),
        "XDG_STATE_HOME": str(casa / ".local" / "state"),
        "XDG_CONFIG_HOME": str(casa / ".config"),
        "LC_ALL": "C",
    }
    assert env["HOME"] != os.path.expanduser("~")
    r = subprocess.run(
        ["bash", str(SCRIPT), flag],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    assert r.returncode == 0, r.stderr
    assert not (casa / ".config").exists(), "a consulta escreveu no HOME"
    return r.stdout.strip()


#: As listas em que o dublê e o script têm de concordar.
LISTAS = {
    "a-mesa-de-29-09": _mesa_de(MESA_DE_29),
    "a-mesa-de-28-09": _mesa_de((BRANCO, VERMELHO, AZUL, ROXO)),
    "com-um-headset-plugado-depois": _mesa_de(
        MESA_DE_29, _Fonte(500, HEADSET, porta=True)
    ),
    "com-um-controle-no-cabo": _mesa_de(
        MESA_DE_29, _Fonte(90, NO_DO_KERNEL, porta=True)
    ),
}


def test_na_mesa_dela_so_a_pergunta_do_install_responde_um_canal(tmp_path: Path) -> None:
    """O script e o doctor de verdade, sobre a lista de 29/09.

    A entrada da placa tem índice menor que o de todos os canais, e o filtro de
    porta a tira. Sobra a ordem dos canais: a pergunta do install responde o
    primeiro (o vermelho), e a da volta responde vazio.
    """
    fontes = LISTAS["a-mesa-de-29-09"]
    assert _script_de_verdade(tmp_path, fontes, "--melhor-fonte-elegivel") == _canal(VERMELHO)
    assert _script_de_verdade(tmp_path, fontes, "--outra-captura-elegivel") == ""


@pytest.mark.parametrize("rotulo", sorted(LISTAS))
def test_o_duble_responde_o_que_o_script_responde(tmp_path: Path, rotulo: str) -> None:
    """O dublê das réguas 2 a 4 não pode ser mais frouxo que o script.

    Foi assim que o defeito atravessou: `test_os_quatro_microfones_ficam_no_ar`
    dublava a volta com um microfone de placa que a máquina dela não tem, e
    nenhum dublê respondia o que o script responde na mesa dela.
    """
    fontes = LISTAS[rotulo]
    for flag, duble in (
        ("--melhor-fonte-elegivel", responde_melhor),
        ("--outra-captura-elegivel", responde_outra),
    ):
        assert duble(fontes) == _script_de_verdade(tmp_path, fontes, flag), (rotulo, flag)


def test_a_volta_do_eleitor_nao_escreve_canal_nenhum(
    mesa: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O eleitor, com o roxo eleito e ninguém no ar: nenhum `set-default-source`.

    MORDIDA: devolva a pergunta do install à volta (`--melhor-fonte-elegivel`
    em `EleitorDeMicrofone.devolver_o_microfone`), e sai
    `set-default-source hefesto_mic_000003` — o vermelho, que ninguém ligou.
    """
    m = mesa(_mesa_de(MESA_DE_29))
    eleitor = elm.EleitorDeMicrofone()
    m.pw.ativo = _canal(ROXO)
    assert eleitor.eleger_o_controle(ROXO, list(OS_QUATRO)).ok
    m.pw.escritas.clear()

    resultado = eleitor.passar_o_padrao([], list(OS_QUATRO), ROXO)

    assert m.pw.escritas == [], f"a volta escreveu um canal de controle: {m.pw.escritas}"
    assert "--outra-captura-elegivel" in m.pw.perguntas
    assert "--melhor-fonte-elegivel" not in m.pw.perguntas
    assert resultado.ok is True and resultado.motivo == ""
    assert resultado.ativo == _canal(ROXO)
    assert eleitor.eleito is None


# ---------------------------------------------------------------------------
# 2. A mesa dela, cada um dos quatro
# ---------------------------------------------------------------------------


def _ordem(quem: str, o_primeiro: str) -> tuple[str, ...]:
    """Os quatro canais, com o de `quem` primeiro ou com o de outro primeiro."""
    outros = tuple(u for u in OS_QUATRO if u != quem)
    return (quem, *outros) if o_primeiro == "o-dele" else (*outros, quem)


@pytest.mark.parametrize("cabo", ["todos-no-radio", "quem-cala-no-cabo", "outro-no-cabo"])
@pytest.mark.parametrize("o_primeiro", ["o-dele", "o-de-outro"])
@pytest.mark.parametrize("quem", OS_QUATRO, ids=["vermelho", "branco", "azul", "roxo"])
@pytest.mark.asyncio
async def test_calar_o_unico_no_ar_nao_escreve_padrao_nenhum(
    mesa: Any, quem: str, o_primeiro: str, cabo: str
) -> None:
    """Cada um dos quatro como o único no ar, e os outros três calados.

    (o-dele) o canal de quem cala é o primeiro no índice: é 28/09, em que a
    volta escreveu o próprio canal dele e a posse caiu por 3,7 s com o padrão
    nele. (o-de-outro) o de outro é o primeiro: é 29/09, em que a volta elegeu
    o vermelho calado.

    No cabo, o controle também publica a fonte do kernel, que as duas
    perguntas já tiravam pelo «dualsense».

    MORDIDAS:
    - com a pergunta velha, o (o-dele) escreve o próprio canal e o
      (o-de-outro) escreve o canal de um calado;
    - com o «fica» lido como a falha de hoje (o `ok=False` com o motivo em
      `passar_o_padrao`), o cartão de quem calou ganha a frase e a luz dele
      acende pelo escritor da eleição.
    """
    no_cabo = {"todos-no-radio": None, "quem-cala-no-cabo": quem}.get(
        cabo, next(u for u in OS_QUATRO if u != quem)
    )
    extra = (_Fonte(90, NO_DO_KERNEL, porta=True),) if no_cabo else ()
    m = mesa(_mesa_de(_ordem(quem, o_primeiro), *extra), cabo=no_cabo)
    assert (await _apertar(m, quem, ligado=True)).feito
    assert _eleitor(m).eleito == quem and _no_ar(m) == [quem]
    assert m.pw.ativo == _canal(quem)
    m.pw.escritas.clear()

    ato = await _apertar(m, quem, ligado=False)

    assert ato.feito, ato.motivo
    assert m.pw.escritas == [], f"calar escreveu a fonte padrão: {m.pw.escritas}"
    assert m.pw.ativo == _canal(quem), "o padrão fica no canal que ela calou"
    assert _eleitor(m).eleito is None, "o ato de calar sem destino solta a posse"
    assert m.backend.leds[_n(quem)] is False, "mudo é luz apagada (decisão de 19/09)"
    assert _no_ar(m) == []
    recado = recado_do_microfone.publicar(m.daemon)["recados"][quem]
    assert (recado["gesto"], recado["ok"], recado["motivo"]) == ("devolver", True, ""), recado
    assert recado_do_microfone.publicar(m.daemon)["eleito"] is None


# ---------------------------------------------------------------------------
# 3. Qualquer usuário
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_headset_plugado_depois_herda_o_padrao(mesa: Any) -> None:
    """Um headset de índice maior que os canais, como quem pluga depois do daemon.

    MORDIDA: com a pergunta velha, o padrão vai ao primeiro canal de controle
    (o vermelho), e não ao headset.
    """
    m = mesa(_mesa_de(MESA_DE_29, _Fonte(500, HEADSET, porta=True)))
    assert (await _apertar(m, ROXO, ligado=True)).feito
    m.pw.escritas.clear()

    ato = await _apertar(m, ROXO, ligado=False)

    assert ato.feito, ato.motivo
    assert m.pw.escritas == [HEADSET]
    assert m.pw.ativo == HEADSET
    assert _eleitor(m).eleito is None
    assert m.backend.leds[_n(ROXO)] is False


@pytest.mark.parametrize("como", ["sem-o-script", "script-mais-velho"])
@pytest.mark.asyncio
async def test_sem_poder_perguntar_nada_se_escreve_e_o_ato_de_calar_se_completa(
    mesa: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, como: str
) -> None:
    """O «não sei» nunca escreve, e o silêncio que ela pediu não depende dele.

    MORDIDA: deixe a `ConsultaIndisponivelError` subir de
    `devolver_o_microfone` e o ato morre no meio (no laço do botão, em
    `mic_hotkey_falhou`), sem a metade do firmware e sem o disco.
    """
    m = mesa(_mesa_de(MESA_DE_29))
    assert (await _apertar(m, ROXO, ligado=True)).feito
    m.pw.escritas.clear()
    if como == "sem-o-script":
        monkeypatch.setattr(elm, "_script_do_wireplumber", lambda: None)
    else:
        velho = tmp_path / "fix_wireplumber_default_source.sh"
        velho.write_text("#!/usr/bin/env bash\n--fonte-se-sustenta) :;;\n")
        monkeypatch.setattr(elm, "_script_do_wireplumber", lambda: velho)
    gravados: list[tuple[str, bool]] = []
    from hefesto_dualsense4unix.utils import maquina

    monkeypatch.setattr(
        maquina,
        "gravar_o_mudo_do_microfone",
        lambda chave, mudo: gravados.append((chave, mudo)) or True,
    )

    ato = await _apertar(m, ROXO, ligado=False)

    assert m.pw.escritas == []
    assert "--outra-captura-elegivel" not in m.pw.perguntas
    assert ato.feito, ato.motivo
    assert ato.firmware.feita and ato.canal_no_sistema.feita
    assert gravados == [(_n(ROXO), True)], gravados
    assert m.backend.leds[_n(ROXO)] is False


# ---------------------------------------------------------------------------
# 4. O nó que morre
# ---------------------------------------------------------------------------


async def _uma_volta_da_porta_do_no(m: SimpleNamespace) -> Any:
    """`_devolver_a_fonte_padrao` NO FIO, como no daemon, e a entrega ao laço."""
    veredicto = await asyncio.to_thread(m.sub._devolver_a_fonte_padrao)
    for _ in range(50):
        await asyncio.sleep(0)
        em_voo = [t for t in getattr(m.sub, "_herancas_em_voo", ()) if not t.done()]
        if em_voo:
            await asyncio.gather(*em_voo)
    return veredicto


@dataclass
class _CenaDoNo:
    m: SimpleNamespace
    de_pe: set[str]
    avisos: list[tuple[str, dict[str, Any]]]


async def _cena_do_no(
    mesa: Any, monkeypatch: pytest.MonkeyPatch, *, no_ar: tuple[str, ...]
) -> _CenaDoNo:
    """Os quatro no rádio; `no_ar` ligados nesta ordem; o último é o padrão."""
    m = mesa(_mesa_de(MESA_DE_29))
    for uniq in no_ar:
        assert (await _apertar(m, uniq, ligado=True)).feito, uniq
    de_pe = {_canal(u) for u in OS_QUATRO}
    m.sub._daemon = m.daemon
    m.sub._laco = asyncio.get_running_loop()
    monkeypatch.setattr(m.sub, "_nomes_de_pe", lambda: frozenset(de_pe))
    monkeypatch.setattr(bt_mic, "fonte_padrao_crua", lambda ler=None: m.pw.ativo)
    avisos: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        bt_mic.logger, "warning", lambda ev, **c: avisos.append((ev, c))
    )
    assert await _uma_volta_da_porta_do_no(m) is None, "a primeira volta não acusa"
    return _CenaDoNo(m=m, de_pe=de_pe, avisos=avisos)


def _o_roxo_morre(cena: _CenaDoNo, herdeiro: str) -> None:
    """O PS do roxo segurado até apagar: o nó cai e o WirePlumber escolhe."""
    cena.de_pe.discard(_canal(ROXO))
    cena.m.pw.fontes = [f for f in cena.m.pw.fontes if f.nome != _canal(ROXO)]
    cena.m.backend.sair(ROXO)
    cena.m.pw.ativo = herdeiro
    cena.m.pw.escritas.clear()


@pytest.mark.parametrize(
    "herdeiro",
    ["o-vermelho-calado", "um-monitor", "o-fantasma"],
)
@pytest.mark.asyncio
async def test_o_no_que_morre_passa_o_padrao_a_quem_esta_no_ar(
    mesa: Any, monkeypatch: pytest.MonkeyPatch, herdeiro: str
) -> None:
    """O roxo é o padrão e está no ar; o azul está no ar; o vermelho, calado.

    O DUBLÊ RESPONDE O QUE O WIREPLUMBER FAZ: depois da morte, o padrão vai
    ao canal do vermelho, calado e de prioridade igual à dos outros (o
    desempate do WirePlumber não foi medido), e não a um monitor. Um dublê que
    devolvesse só monitor abriria a porta que o aparelho não abre.

    MORDIDAS:
    - a porta do nó chamando a volta direto (`devolver_o_microfone` no lugar de
      `passar_o_padrao` em `hotkey.passar_o_padrao_do_no_morto`): o azul não
      herda;
    - sem o desfecho novo (`_e_canal_de_controle` em `a_heranca_do_no_morto`):
      o veredicto sai «nenhum», e o vermelho calado fica com o padrão.
    """
    cena = await _cena_do_no(mesa, monkeypatch, no_ar=(AZUL, ROXO))
    assert _eleitor(cena.m).eleito == ROXO
    _o_roxo_morre(
        cena,
        {
            "o-vermelho-calado": _canal(VERMELHO),
            "um-monitor": MONITOR_SPDIF,
            "o-fantasma": _canal(ROXO),
        }[herdeiro],
    )

    veredicto = await _uma_volta_da_porta_do_no(cena.m)

    assert veredicto is not None and veredicto.aberto, veredicto
    assert cena.m.pw.escritas == [_canal(AZUL)], cena.m.pw.escritas
    assert cena.m.pw.ativo == _canal(AZUL)
    assert _eleitor(cena.m).eleito == AZUL
    denuncias = [c for ev, c in cena.avisos if ev == "bt_mic_heranca_do_no_morto"]
    assert len(denuncias) == 1 and denuncias[0]["curado"] is True, cena.avisos


@pytest.mark.asyncio
async def test_so_com_o_roxo_no_ar_nenhum_canal_de_controle_e_escrito(
    mesa: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O roxo era o único no ar: o buraco continua, e o diário nomeia o nó.

    MORDIDA: com a pergunta velha, o vermelho calado herda.
    """
    cena = await _cena_do_no(mesa, monkeypatch, no_ar=(ROXO,))
    _o_roxo_morre(cena, _canal(VERMELHO))

    await _uma_volta_da_porta_do_no(cena.m)

    assert cena.m.pw.escritas == [], cena.m.pw.escritas
    denuncias = [c for ev, c in cena.avisos if ev == "bt_mic_heranca_do_no_morto"]
    assert len(denuncias) == 1, cena.avisos
    assert denuncias[0]["curado"] is False
    assert denuncias[0]["eleito"] == _canal(VERMELHO)
    assert denuncias[0]["buraco"] == "canal_de_controle"


@pytest.mark.asyncio
async def test_o_herdeiro_que_esta_no_ar_fica_como_esta(
    mesa: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O WirePlumber deu o padrão ao azul, que está no ar: foi ela quem o ligou.

    MORDIDA: tire a conferência do herdeiro de
    `hotkey.passar_o_padrao_do_no_morto` e o padrão sai do azul para o
    vermelho, que ela ligou por último.
    """
    cena = await _cena_do_no(mesa, monkeypatch, no_ar=(AZUL, VERMELHO, ROXO))
    _o_roxo_morre(cena, _canal(AZUL))

    await _uma_volta_da_porta_do_no(cena.m)

    assert cena.m.pw.escritas == [], cena.m.pw.escritas
    assert cena.m.pw.ativo == _canal(AZUL)
    assert [c for ev, c in cena.avisos if ev == "bt_mic_heranca_do_no_morto"] == []


def test_o_fio_nunca_le_o_no_ar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem laço (o subsystem que não passou pelo `start`), a porta não pergunta.

    O `MicrofonesNoAr` é do laço e não tem lock: o fio do `bt_mic` classifica a
    herança e entrega o resto. Sem a quem entregar, nada se elege.

    MORDIDA: chame `hotkey.passar_o_padrao_do_no_morto` direto do fio, e o
    eleitor é chamado sem o laço.
    """
    chamadas: list[Any] = []

    class _Eleitor:
        def passar_o_padrao(self, *a: Any) -> Any:
            chamadas.append(a)
            return elm.ResultadoDaEleicao(ok=True)

    sub = bt_mic.BtMicSubsystem(registro=bt_mic.RegistroDePedidosDeCanal())
    sub._daemon = SimpleNamespace(_eleitor_de_microfone=_Eleitor())
    de_pe = {_canal(ROXO)}
    monkeypatch.setattr(sub, "_nomes_de_pe", lambda: frozenset(de_pe))
    monkeypatch.setattr(bt_mic, "fonte_padrao_crua", lambda ler=None: MONITOR_SPDIF)
    sub._devolver_a_fonte_padrao()
    de_pe.clear()

    veredicto = sub._devolver_a_fonte_padrao()

    assert veredicto is not None and veredicto.aberto
    assert chamadas == []


def test_o_uniq_da_fixture_e_da_faixa_sintetica() -> None:
    """A faixa de fixture da casa: endereço de teste nunca vem do real."""
    assert all(u.startswith("aa:bb:cc:00:00:") for u in OS_QUATRO)
