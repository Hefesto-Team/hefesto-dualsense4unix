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

# ---------------------------------------------------------------------------
# A MESA, em nomes — e todos eles são a chave da casa, nunca um endereço real
# ---------------------------------------------------------------------------

#: Duas placas de DualSense no cabo, uma por aparelho. Os nomes são
#: indistinguíveis DE PROPÓSITO: o `-00`/`-00.2` é desempate posicional do
#: PipeWire e a string de serial USB do DualSense é a mesma em todos.
_P1 = "alsa_input.usb-Sony_Interactive_Entertainment_Wireless_Controller-00.mono-fallback"
_P2 = "alsa_input.usb-Sony_Interactive_Entertainment_Wireless_Controller-00.2.mono-fallback"

#: O eco da SAÍDA. Casa com a mesma marca que a placa casaria, e já custou um
#: defeito real em 16/08: o deslizante do MICROFONE mexia no ALTO-FALANTE.
_MONITOR = (
    "alsa_output.usb-Sony_Interactive_Entertainment_Wireless_Controller"
    "-00.analog-surround-40.monitor"
)

_USB_P1 = "usb-0000:0c:00.3-3"
_USB_P2 = "usb-0000:0c:00.3-4"

_UNIQ_P1 = "aabbcc010203"
_UNIQ_P2 = "aabbcc040506"
_UNIQ_RADIO = "aabbcc070809"

#: A saída LONGA não é interpretada aqui: quem a lê é o `nos_e_sysfs`, dublado.
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
    """Responde à CURTA e à LONGA com textos diferentes, como o `pactl` faz.

    `longa_ilegivel` é a cena do `pactl list sources` que não volta — e é ela
    que apaga o casamento por USB, deixando só as regras de identidade e o
    um-para-um de pé. É o caso 4 da sprint.
    """

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


# ---------------------------------------------------------------------------
# O DUBLÊ ESTRITO, e o host de IPC
# ---------------------------------------------------------------------------


class _EscritaEstrita:
    """O que chegou a `definir_volume_da_captura`, e ele RECUSA o descuido.

    `fonte` é keyword-only e SEM padrão, igual à função de verdade desde
    06/09/2026. Um dublê com `fonte=None` de padrão engoliria em silêncio a
    chamada que a cura existe para tornar impossível — e mediria a si mesmo.
    """

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
    """O backend, do jeito que `recado_do_microfone.mesa_de_agora` o lê.

    Ele exige o `connected` — é a diferença entre "tem card na tela" e "há um
    handle aberto", e é por isso que a mesa vem daquela função e não de
    `_uniqs_conectados`.
    """

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
    # A ROTA GLOBAL DEVOLVE SEMPRE A PRIMEIRA — é ela que este arquivo existe
    # para ver NÃO acontecer quando há endereço. Deixá-la respondendo é o que
    # torna a mordida visível: sem isto, arrancar a cura daria `sem_fonte` em
    # vez do nome da placa errada, e a régua reprovaria sem dizer o defeito.
    monkeypatch.setattr(audio_control, "fonte_de_captura_do_controle", lambda: _P1)
    return e


# ---------------------------------------------------------------------------
# 1. DOIS NO CABO — o caso que já estava curado, e que tem de continuar
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 2. A PORTA QUE FICOU ABERTA — o passo 1 da sprint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_deslizante_do_p2_nao_cai_na_placa_do_p1(
    monkeypatch: pytest.MonkeyPatch, escrita: _EscritaEstrita
) -> None:
    """Dois no cabo, o sysfs ILEGÍVEL: ninguém escreve em placa nenhuma.

    **MORDE:** devolva as duas linhas do `if fonte is None:
    fonte = fonte_de_captura_do_controle()` em `_handle_mic_volume_set` e este
    caso reprova nomeando `_P1` na chamada a `definir_volume_da_captura` — que
    é, palavra por palavra, o microfone da outra pessoa.
    """
    _dublar_pactl(monkeypatch, _curta(_P1, _P2, _MONITOR))
    _dublar_sysfs(monkeypatch, {}, {})  # o censo de USB não respondeu

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
    """Um no cabo, um no rádio SEM o canal do microfone de pé.

    O do rádio não tem dispositivo USB nenhum — a placa segue o transporte,
    medido em 15/08/2026 — e, sem o canal publicado, não tem nó nenhum. A única
    fonte da lista é a placa de quem está no CABO, e ela tem dono.
    """
    _dublar_pactl(monkeypatch, _curta(_P1, _MONITOR))
    _dublar_sysfs(monkeypatch, {_UNIQ_P1: _USB_P1}, {_P1: _USB_P1, _MONITOR: _USB_P1})

    res = await _host(
        _ControleQueLista(_UNIQ_P1, _UNIQ_RADIO)
    )._handle_mic_volume_set({"volume": 30, "uniq": _UNIQ_RADIO})

    assert escrita.escritas == [], (
        f"o card de quem está no rádio escreveu na placa do cabo: {escrita.escritas}")
    assert res["status"] == "sem_fonte"


# ---------------------------------------------------------------------------
# 3. A MESA ENTRA NA CONTA — o passo 2, e sem ele o passo 1 é regressão
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_um_controle_e_uma_source_resolvem_sem_rota_global(
    monkeypatch: pytest.MonkeyPatch, escrita: _EscritaEstrita
) -> None:
    """Um controle só, uma source, o `pactl list sources` ILEGÍVEL.

    Antes desta sprint este caso resolvia pela rota global — **certo por
    acaso**, porque a primeira da lista calhava de ser a única. Fechar a queda
    sem a mesa o teria quebrado; com a mesa, a regra 4 do `escolher_fonte`
    (um-para-um) o resolve — **certo por REGRA**.

    **MORDE:** devolva o `[]` no lugar de `candidatos` em
    `audio_control.fonte_de_captura_do_uniq` e este caso reprova com
    `sem_fonte` onde a mesa de um tem resposta certa.
    """
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
    """`None` da mesa é "não perguntei", e mantém o comportamento de antes.

    A diferença entre `[]` e `None` é a diferença entre *"não há ninguém"* e
    *"não perguntei a ninguém"* — confundi-las é como esta casa já publicou
    ausência de dado como negação. Com o backend mudo, a regra 4 fica desligada
    e o um-para-um não é inventado: ninguém escreve.
    """
    _dublar_pactl(monkeypatch, _curta(_P1, _MONITOR), longa_ilegivel=True)
    _dublar_sysfs(monkeypatch, {}, {})

    res = await _host(
        _ControleQueLista(_UNIQ_P1, sabe_listar=False)
    )._handle_mic_volume_set({"volume": 55, "uniq": _UNIQ_P1})

    assert res["status"] == "sem_fonte"
    assert escrita.escritas == []


# ---------------------------------------------------------------------------
# 4. A ROTA GLOBAL CONTINUA EXISTINDO — ela nunca foi o defeito
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sem_endereco_a_rota_global_continua(
    monkeypatch: pytest.MonkeyPatch, escrita: _EscritaEstrita
) -> None:
    """Quem não manda `uniq` continua com a conveniência de sempre.

    A rota global nunca foi o defeito; o defeito era ela ser o CONSOLO de um
    endereço que não resolveu. Matá-la junto teria fechado o caminho de quem
    tem um controle só e não manda endereço.
    """
    _dublar_pactl(monkeypatch, _curta(_P1, _MONITOR))
    _dublar_sysfs(monkeypatch, {_UNIQ_P1: _USB_P1}, {_P1: _USB_P1})

    res = await _host(_ControleQueLista(_UNIQ_P1))._handle_mic_volume_set(
        {"volume": 12})

    assert res["status"] == "ok"
    assert escrita.escritas == [(12, _P1)]


# ---------------------------------------------------------------------------
# 5. AS DUAS PORTAS DORMENTES — o passo 3
# ---------------------------------------------------------------------------


def test_ninguem_escreve_volume_sem_dizer_em_qual_fonte() -> None:
    """`fonte=` deixou de ter padrão nas duas funções que falam com o `pactl`.

    Elas eram portas fechadas com a chave na fechadura: nenhum chamador de
    `src/` as empurrava, e quem as empurrasse amanhã cairia na primeira placa
    da lista sem uma linha de aviso. É a disciplina do `muted` do `mic.set`,
    que também não tem padrão — quem escreve declara em qual aparelho escreve.

    **MORDE:** devolva o `= None` a qualquer uma das duas e este caso reprova.
    """
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
    """A outra metade do passo 3: a porta fechou e ninguém ficou do lado de fora.

    Uma assinatura que aperta sem esta conta deixa um `TypeError` esperando o
    primeiro clique dela em vez de esperar o CI.
    """
    import ast
    import pathlib

    # POR AST, E NÃO POR EXPRESSÃO REGULAR. A primeira tentativa desta régua
    # recortava o argumento até o primeiro `)` e acusou
    # `lifecycle.py:3411`, que passa `fonte=` — o `)` era o do `int(volume)`
    # aninhado. Uma régua que lê estrutura com busca de texto é a ferramenta
    # errada, e esta casa já pagou por isso.
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


# ---------------------------------------------------------------------------
# 6. A FRASE DA RECUSA — o passo 4
# ---------------------------------------------------------------------------


class _PonteEstrita:
    """O dublê da ponte da tela, tão estrito quanto a ponte de verdade.

    Um nome que `interface/pacotes/ponte.py` não expõe levanta `AttributeError`
    em vez de responder `True` — é a diferença entre medir o gesto e medir o
    próprio dublê, e a cicatriz é de 04/09/2026.
    """

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
    """A frase do `sem_fonte` deixou de mandar procurar nos lugares errados.

    Com a queda fechada, `sem_fonte` passa a ser a resposta NORMAL do controle
    no rádio sem o canal do microfone de pé. Nesse caso o serviço não está
    parado e o controle não saiu — e a frase antiga afirmava as duas coisas.

    **MORDE:** devolva o ramo único (`if corpo is None or status != "ok"`) e
    este caso reprova comparando a frase depositada no cartão com as duas
    causas falsas.
    """
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
    """Nenhum comando, nenhum nome de nó, e nem a palavra que ela baniu.

    `docs/A-LINGUA-DESTA-CASA`: são proibidos em texto de tela `hidraw`, `MAC`,
    `uniq`, "linha de comando", "mesa" e qualquer frase que mande a pessoa
    procurar um botão que não existe. Uma recusa nova é exatamente onde jargão
    entra sem ninguém ver.
    """
    from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

    frase = a02.TEXTO_MIC_SEM_FONTE.lower()
    for banida in ("mesa", "pactl", "pipewire", "hidraw", "uniq", "mic bt",
                   "source", "daemon", "terminal", "comando"):
        assert banida not in frase, f"a frase de tela diz `{banida}`"
    # O DIAGNÓSTICO POR TRANSPORTE SAIU — 11/09/2026, A3-054, aprovada por ela:
    # *no rádio é o canal que não está de pé, no cabo é a placa de som* é o
    # NOSSO mecanismo, e ela não pode agir sobre nenhum dos dois. Esta linha
    # cobrava `cabo` e `rádio` DIGITADOS e teria reprovado a melhora.
    #
    # O QUE SOBRA DE MEDÍVEL É A PROMESSA: o clique não mexeu em nada. Sem ela,
    # quem lê fica sem saber se o ajuste entrou pela metade.
    assert "nada foi mudado" in frase, (
        "a frase deixou de dizer que nada foi mudado — quem lesse ficaria sem "
        "saber se o ajuste entrou pela metade")


# ---------------------------------------------------------------------------
# 7. NADA SE PERDEU — a confissão continua podendo acontecer
# ---------------------------------------------------------------------------


def test_a_confissao_da_tela_continua_de_pe_para_o_daemon_velho() -> None:
    """`por_uniq: False` ainda faz a tela confessar.

    Ele deixa de poder disparar contra ESTE daemon e continua sendo a última
    trava contra um daemon INSTALADO mais velho que a janela — o caso que
    aconteceu de verdade em 04/09 com o `mic.canal.set`, na máquina dela.
    """
    from hefesto_dualsense4unix.app.ipc_bridge import alvo_honrado
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        TEXTO_MIC_ALVO_NAO_HONRADO,
        frase_do_alvo_do_mic,
    )

    velho = {"status": "ok", "fonte": "webcam", "volume": 42, "por_uniq": False}
    assert frase_do_alvo_do_mic(alvo_honrado(velho)) == TEXTO_MIC_ALVO_NAO_HONRADO
    assert frase_do_alvo_do_mic(alvo_honrado({"status": "ok"})) == ""


# ---------------------------------------------------------------------------
# 8. O ALVO `marcado` QUE A RÉGUA DO MOCKUP NÃO ENXERGAVA
# ---------------------------------------------------------------------------
#
# **POR QUE ISTO MORA AQUI, e a razão é de endereço.** O buraco foi medido no
# alvo `p1·card-aberto` — o rádio que abre o cartão do Jogador 1 na aba 02, a
# aba desta sprint —, e ele REPROVAVA a `--prova-de-mockup` inteira com a
# cegueira *"o parser e o leitor de tela discordam neste alvo"*. Não é assunto
# de microfone; é assunto DESTA ABA, e ficar sem régua era deixar a próxima
# pessoa remedindo o mesmo defeito.


def test_o_arquivo_e_a_tela_falam_a_mesma_lingua_no_alvo_marcado() -> None:
    """`checked` no arquivo é `sim`, igual ao que o navegador devolve.

    O leitor de tela (`hefesto_vivo.LER_CAMPOS`) responde `el.checked ? 'sim'
    : ''` para o alvo `marcado`, e o parser do arquivo NÃO tinha esse ramo:
    caía no do TEXTO, que num `<input>` é sempre vazio. As duas leituras têm de
    casar endereço a endereço — é o que a guarda do DOM virgem cobra a cada
    aba, e era ela que estava reprovando.

    **MORDE:** tire o ramo `elif alvo == "marcado"` de
    `regua_do_mockup._Leitor._campo` e este caso reprova com `''` onde a página
    virgem mostra `'sim'`.
    """
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
    """O caso real, no arquivo que o produto renderiza.

    Medido em 06/09/2026, ANTES da cura: `p1·card-aberto` lia `''` no arquivo e
    `'sim'` na página virgem. Este caso é o mesmo endereço, no mesmo arquivo.
    """
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
