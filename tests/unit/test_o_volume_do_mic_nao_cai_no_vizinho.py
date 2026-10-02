"""ONDA5-02-01: o deslizante do microfone parou de cair na placa do vizinho.

**A palavra dela, 02-Q8, 05/09/2026**, depois de eu oferecer três redações de
bilhete para a tela CONFESSAR a queda:

    *"Esse erro não deveria acontecer. Deveria ser só pro controle em questao.
    Parece um bug"*

As três opções guardavam o defeito e discutiam o bilhete. O que esta régua
mede é a resposta certa: **o Hefesto não explica a própria falha — ele a
conserta.**

O QUE ESTAVA ABERTO, e onde
---------------------------
`_handle_mic_volume_set` resolvia a fonte pelo `uniq` e, quando não resolvia,
caía para `fonte_de_captura_do_controle()` — a PRIMEIRA source de DualSense da
lista. Com dois controles ligados, "a primeira" é quem calhou de aparecer
primeiro no `pactl`, e é isso, e nada mais, que fazia o deslizante do card dela
mexer no microfone de outra pessoa.

A regra que ela pede **já estava escrita um arquivo ao lado**: a aplicação de
perfil (`daemon/lifecycle.py`) recusa a queda desde 03/09. Duas réguas sobre a
mesma pergunta com dois vereditos é como esta casa fabrica divergência
silenciosa — e a porta que ficara aberta era justamente a que ela CLICA.

POR QUE ESTA RÉGUA CHAMA O HANDLER, e não a função
--------------------------------------------------
`tests/unit/test_mic_da_mesa_cheia_01.py` já mede
`fonte_de_captura_do_uniq` — e ela estava CERTA o tempo todo. **Quem caiu foi o
handler**, no `if fonte is None` logo depois dela. Medir de novo a função seria
medir o degrau que nunca quebrou; então aqui se chama
`_handle_mic_volume_set` e se olha **o que chegou a
`definir_volume_da_captura` — a source, pelo nome.**

E O DUBLÊ É ESTRITO, pela cicatriz de 04/09/2026: duas vezes num dia um gesto
passou verde sem gravar um byte porque o dublê do teste era mais frouxo que a
peça real. `_EscritaEstrita` recusa a chamada sem `fonte=`, exatamente como a
função de verdade passou a recusar.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import audio_control


#: Duas placas de DualSense no cabo, uma por aparelho. Os nomes são
#: PipeWire e a string de serial USB do DualSense é a mesma em todos.
_P1 = "alsa_input.usb-Sony_Interactive_Entertainment_Wireless_Controller-00.mono-fallback"
_P2 = "alsa_input.usb-Sony_Interactive_Entertainment_Wireless_Controller-00.2.mono-fallback"

_MONITOR = (
    "alsa_output.usb-Sony_Interactive_Entertainment_Wireless_Controller"
    "-00.analog-surround-40.monitor"
)

_USB_P1 = "usb-0000:0c:00.3-3"
_USB_P2 = "usb-0000:0c:00.3-4"

_UNIQ_P1 = "aabbcc010203"
_UNIQ_P2 = "aabbcc040506"
_UNIQ_RADIO = "aabbcc070809"

_LONGA = "(a saída longa; quem a lê é o `nos_e_sysfs`, que está dublado)"


def _curta(*nomes: str) -> str:
    """`pactl list sources short`: `índice\\tnome\\tdriver\\tformato\\testado`."""
    return "\n".join(
        f"{600 + i}\t{nome}\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED"
        for i, nome in enumerate(nomes)
    )


def _dublar_pactl(
    monkeypatch: pytest.MonkeyPatch, curta: str, *, longa_ilegivel: bool = False
) -> None:
    """Responde à CURTA e à LONGA com textos diferentes, como o `pactl` faz."""

    class _Saida:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def run(argv: Any, *_a: Any, **_k: Any) -> Any:
        if "short" in list(argv):
            return _Saida(curta)
        if longa_ilegivel:
            raise OSError("o `pactl list sources` não respondeu")
        return _Saida(_LONGA)

    monkeypatch.setattr(audio_control.subprocess, "run", run)


def _dublar_sysfs(
    monkeypatch: pytest.MonkeyPatch,
    por_uniq: dict[str, str],
    por_no: dict[str, str],
) -> None:
    """O censo de USB, dublado. `{}` dos dois lados é o sysfs ILEGÍVEL."""
    from hefesto_dualsense4unix.integrations import usb_pai

    monkeypatch.setattr(
        usb_pai, "usb_pai_por_uniq",
        lambda uniqs, **_kw: {u: por_uniq.get(u, "") for u in uniqs if u})
    monkeypatch.setattr(usb_pai, "usb_pai_por_no", lambda _nos: dict(por_no))
    monkeypatch.setattr(usb_pai, "nos_e_sysfs", lambda _s: {})


class _EscritaEstrita:
    """O que chegou a `definir_volume_da_captura`, e ele RECUSA o descuido."""

    def __init__(self) -> None:
        self.escritas: list[tuple[int, str | None]] = []
        self.leituras: list[str | None] = []

    def definir(self, volume: int, *, fonte: str | None) -> bool:
        self.escritas.append((volume, fonte))
        return True

    def ler(self, *, fonte: str | None) -> int | None:
        self.leituras.append(fonte)
        return 42


class _ControleQueLista:
    """O backend, do jeito que `recado_do_microfone.mesa_de_agora` o lê."""

    def __init__(self, *uniqs: str, sabe_listar: bool = True) -> None:
        self._uniqs = uniqs
        self._sabe = sabe_listar

    def describe_controllers(self) -> list[dict[str, Any]]:
        if not self._sabe:
            raise RuntimeError("backend legado: não sei listar")
        return [{"uniq": u, "connected": True} for u in self._uniqs]


def _host(controle: Any) -> Any:
    """Um `IpcHandlersMixin` com o `daemon` que o handler agora consulta."""
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
    from hefesto_dualsense4unix.daemon.state_store import StateStore

    class _Daemon:
        def __init__(self) -> None:
            self.controller = controle

    class _Host(IpcHandlersMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self.controller = controle
            self.daemon = _Daemon()
            self.store = StateStore()

    return _Host()


@pytest.fixture
def escrita(monkeypatch: pytest.MonkeyPatch) -> _EscritaEstrita:
    e = _EscritaEstrita()
    monkeypatch.setattr(audio_control, "definir_volume_da_captura", e.definir)
    monkeypatch.setattr(audio_control, "volume_da_captura", e.ler)
    monkeypatch.setattr(audio_control, "fonte_de_captura_do_controle", lambda: _P1)
    return e


@pytest.mark.asyncio
async def test_o_gesto_do_p2_escreve_na_placa_do_p2(
    monkeypatch: pytest.MonkeyPatch, escrita: _EscritaEstrita
) -> None:
    """Curado em 20/08 pelo casamento por USB. Aqui só se guarda o chão."""
    _dublar_pactl(monkeypatch, _curta(_P1, _P2, _MONITOR))
    _dublar_sysfs(monkeypatch, {_UNIQ_P1: _USB_P1, _UNIQ_P2: _USB_P2},
                  {_P1: _USB_P1, _P2: _USB_P2, _MONITOR: _USB_P1})

    res = await _host(_ControleQueLista(_UNIQ_P1, _UNIQ_P2))._handle_mic_volume_set(
        {"volume": 70, "uniq": _UNIQ_P2})

    assert res["status"] == "ok"
    assert res["por_uniq"] is True
    assert escrita.escritas == [(70, _P2)], (
        f"o gesto do card do Jogador 2 não chegou à placa dele: {escrita.escritas}")


@pytest.mark.asyncio
async def test_o_deslizante_do_p2_nao_cai_na_placa_do_p1(
    monkeypatch: pytest.MonkeyPatch, escrita: _EscritaEstrita
) -> None:
    """Dois no cabo, o sysfs ILEGÍVEL: ninguém escreve em placa nenhuma."""
    _dublar_pactl(monkeypatch, _curta(_P1, _P2, _MONITOR))
    _dublar_sysfs(monkeypatch, {}, {})

    res = await _host(_ControleQueLista(_UNIQ_P1, _UNIQ_P2))._handle_mic_volume_set(
        {"volume": 70, "uniq": _UNIQ_P2})

    assert escrita.escritas == [], (
        "com o endereço em mãos e a fonte irresolvida, o daemon escreveu assim "
        f"mesmo — e foi na placa do vizinho: {escrita.escritas}")
    assert res["status"] == "sem_fonte"
    assert res["volume"] is None
    assert res["por_uniq"] is True, (
        "`por_uniq: False` aqui faria a tela confessar `mexi no microfone de "
        "outra pessoa` sobre um gesto que não mexeu em microfone nenhum")


@pytest.mark.asyncio
async def test_o_radio_sem_canal_nao_cai_na_placa_de_quem_esta_no_cabo(
    monkeypatch: pytest.MonkeyPatch, escrita: _EscritaEstrita
) -> None:
    """Um no cabo, um no rádio SEM o canal do microfone de pé."""
    _dublar_pactl(monkeypatch, _curta(_P1, _MONITOR))
    _dublar_sysfs(monkeypatch, {_UNIQ_P1: _USB_P1}, {_P1: _USB_P1, _MONITOR: _USB_P1})

    res = await _host(
        _ControleQueLista(_UNIQ_P1, _UNIQ_RADIO)
    )._handle_mic_volume_set({"volume": 30, "uniq": _UNIQ_RADIO})

    assert escrita.escritas == [], (
        f"o card de quem está no rádio escreveu na placa do cabo: {escrita.escritas}")
    assert res["status"] == "sem_fonte"


@pytest.mark.asyncio
async def test_um_controle_e_uma_source_resolvem_sem_rota_global(
    monkeypatch: pytest.MonkeyPatch, escrita: _EscritaEstrita
) -> None:
    """Um controle só, uma source, o `pactl list sources` ILEGÍVEL."""
    _dublar_pactl(monkeypatch, _curta(_P1, _MONITOR), longa_ilegivel=True)
    _dublar_sysfs(monkeypatch, {_UNIQ_P1: _USB_P1}, {_P1: _USB_P1})

    res = await _host(_ControleQueLista(_UNIQ_P1))._handle_mic_volume_set(
        {"volume": 55, "uniq": _UNIQ_P1})

    assert res["status"] == "ok", (
        "a mesa de UM controle perdeu a resposta que a rota global dava por "
        "acaso — o passo 1 sem o passo 2 é regressão, e é este o caso")
    assert escrita.escritas == [(55, _P1)]


@pytest.mark.asyncio
async def test_backend_que_nao_sabe_listar_nao_inventa_dono(
    monkeypatch: pytest.MonkeyPatch, escrita: _EscritaEstrita
) -> None:
    """`None` da mesa é "não perguntei", e mantém o comportamento de antes."""
    _dublar_pactl(monkeypatch, _curta(_P1, _MONITOR), longa_ilegivel=True)
    _dublar_sysfs(monkeypatch, {}, {})

    res = await _host(
        _ControleQueLista(_UNIQ_P1, sabe_listar=False)
    )._handle_mic_volume_set({"volume": 55, "uniq": _UNIQ_P1})

    assert res["status"] == "sem_fonte"
    assert escrita.escritas == []


@pytest.mark.asyncio
async def test_sem_endereco_a_rota_global_continua(
    monkeypatch: pytest.MonkeyPatch, escrita: _EscritaEstrita
) -> None:
    """Quem não manda `uniq` continua com a conveniência de sempre."""
    _dublar_pactl(monkeypatch, _curta(_P1, _MONITOR))
    _dublar_sysfs(monkeypatch, {_UNIQ_P1: _USB_P1}, {_P1: _USB_P1})

    res = await _host(_ControleQueLista(_UNIQ_P1))._handle_mic_volume_set(
        {"volume": 12})

    assert res["status"] == "ok"
    assert escrita.escritas == [(12, _P1)]


def test_ninguem_escreve_volume_sem_dizer_em_qual_fonte() -> None:
    """`fonte=` deixou de ter padrão nas duas funções que falam com o `pactl`."""
    import inspect

    for funcao in (audio_control.definir_volume_da_captura,
                   audio_control.volume_da_captura):
        parametro = inspect.signature(funcao).parameters["fonte"]
        assert parametro.kind is inspect.Parameter.KEYWORD_ONLY, funcao.__name__
        assert parametro.default is inspect.Parameter.empty, (
            f"`{funcao.__name__}` voltou a resolver a fonte sozinha quando "
            "ninguém a declara — e o que ela resolve é a PRIMEIRA da lista")

    with pytest.raises(TypeError, match="definir_volume_da_captura"):
        audio_control.definir_volume_da_captura(50)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="volume_da_captura"):
        audio_control.volume_da_captura()  # type: ignore[call-arg]


def test_nenhum_chamador_de_src_omite_a_fonte() -> None:
    """A outra metade do passo 3: a porta fechou e ninguém ficou do lado de fora."""
    import ast
    import pathlib

    alvos = {"definir_volume_da_captura", "volume_da_captura"}
    raiz = pathlib.Path(__file__).resolve().parents[2] / "src"
    fora: list[str] = []
    for arquivo in raiz.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), str(arquivo))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func
            nome = (alvo.id if isinstance(alvo, ast.Name)
                    else alvo.attr if isinstance(alvo, ast.Attribute) else "")
            if nome not in alvos:
                continue
            if not any(k.arg == "fonte" for k in no.keywords):
                fora.append(f"{arquivo.relative_to(raiz)}:{no.lineno} {nome}")
    assert not fora, f"chamadores sem `fonte=`: {fora}"


class _PonteEstrita:
    """O dublê da ponte da tela, tão estrito quanto a ponte de verdade."""

    def __init__(self, **respostas: Any) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self._respostas = respostas

    def __getattr__(self, nome: str) -> Any:
        import hefesto_dualsense4unix.interface.pacotes.ponte as ponte_real

        if not hasattr(ponte_real, nome):
            raise AttributeError(
                f"a ponte real não tem `{nome}` — um dublê que responde a "
                f"nomes que a ponte não expõe mede a si mesmo")

        def chamar(*a: Any, **kw: Any) -> Any:
            self.chamadas.append((nome, a, kw))
            return self._respostas.get(nome, True)

        return chamar


def test_sem_fonte_nao_diz_que_o_hefesto_esta_parado() -> None:
    """A frase do `sem_fonte` deixou de mandar procurar nos lugares errados."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto
    from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

    uniq = "aa:bb:cc:00:00:01"
    ctx = Contexto(
        state={}, mesa=[], estados={},
        conectados=[{"uniq": uniq, "player": 1, "connected": True,
                     "transport": "bt", "battery_pct": 50, "is_primary": True,
                     "inputs": {"buttons": []}}])
    p = _PonteEstrita(mic_volume_set_detalhado={
        "status": "sem_fonte", "fonte": None, "volume": None, "por_uniq": True})

    with pytest.raises(RuntimeError) as erro:
        a02.volume(ctx, {"uniq": uniq, "volume": "microfone", "valor": "42"}, p)

    frase = str(erro.value)
    assert frase == a02.TEXTO_MIC_SEM_FONTE
    assert "está parado" not in frase, (
        "a frase manda procurar num serviço que RESPONDEU")
    assert "saiu da mesa" not in frase, (
        "a frase manda procurar um controle que está aqui")


def test_a_frase_do_sem_fonte_fala_a_lingua_da_tela() -> None:
    """Nenhum comando, nenhum nome de nó, e nem a palavra que ela baniu."""
    from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

    frase = a02.TEXTO_MIC_SEM_FONTE.lower()
    for banida in ("mesa", "pactl", "pipewire", "hidraw", "uniq", "mic bt",
                   "source", "daemon", "terminal", "comando"):
        assert banida not in frase, f"a frase de tela diz `{banida}`"
    assert "nada foi mudado" in frase, (
        "a frase deixou de dizer que nada foi mudado — quem lesse ficaria sem "
        "saber se o ajuste entrou pela metade")


def test_a_confissao_da_tela_continua_de_pe_para_o_daemon_velho() -> None:
    """`por_uniq: False` ainda faz a tela confessar."""
    from hefesto_dualsense4unix.app.ipc_bridge import alvo_honrado
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        TEXTO_MIC_ALVO_NAO_HONRADO,
        frase_do_alvo_do_mic,
    )

    velho = {"status": "ok", "fonte": "webcam", "volume": 42, "por_uniq": False}
    assert frase_do_alvo_do_mic(alvo_honrado(velho)) == TEXTO_MIC_ALVO_NAO_HONRADO
    assert frase_do_alvo_do_mic(alvo_honrado({"status": "ok"})) == ""


def test_o_arquivo_e_a_tela_falam_a_mesma_lingua_no_alvo_marcado() -> None:
    """`checked` no arquivo é `sim`, igual ao que o navegador devolve."""
    from hefesto_dualsense4unix.interface import regua_do_mockup

    campos = regua_do_mockup._campos_cravados(
        '<div data-controle="p1">'
        '<input data-campo="card-aberto" data-hef-alvo="marcado" checked>'
        "</div>"
        '<div data-controle="p2">'
        '<input data-campo="card-aberto" data-hef-alvo="marcado">'
        "</div>"
    )
    lido = {c.endereco: c.valor for c in campos}
    assert lido == {"p1·card-aberto": "sim", "p2·card-aberto": ""}, (
        "o parser do arquivo não fala a língua do leitor de tela neste alvo — "
        f"a `--prova-de-mockup` reprova por cegueira própria: {lido}")


def test_a_pagina_publicada_da_aba_02_nao_cega_a_regua() -> None:
    """O caso real, no arquivo que o produto renderiza."""
    import pathlib

    from hefesto_dualsense4unix.interface import regua_do_mockup

    pagina = (pathlib.Path(__file__).resolve().parents[2] /
              "src/hefesto_dualsense4unix/interface/paginas/02-controles.html")
    marcados = {c.endereco: c.valor
                for c in regua_do_mockup._campos_cravados(
                    pagina.read_text(encoding="utf-8"))
                if c.alvo == "marcado"}
    assert marcados.get("p1·card-aberto") == "sim", (
        "o cartão do P1 nasce ABERTO no arquivo (`checked`) e a régua lê vazio")
    assert marcados.get("p2·card-aberto") == ""
