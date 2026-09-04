"""O microfone é UM ATO, e as duas metades são do mesmo gesto.

MICROFONE-UM-ATO-01 (04/09/2026). O conceito é DELA, e derrubou a pergunta que
eu tinha feito: eu levei o microfone como *"duas camadas se contradizem"* e
ofereci três arranjos que GUARDAVAM a contradição. Ela recusou os três:

    *"tá errado o conceito da coisa. o botão é pra ligar o microfone e ele ser
    ouvido no canal específico dele."*

E ao meio-dia acrescentou as duas regras que faltavam, com todas as letras:

    *"o botão fisico do mic se ligado no  # noqa-acento: citação dela
    microfone ele fica ligado tambem.  # noqa-acento: citação dela
    indepente se nativo ou virtual"*  # noqa-acento: citação dela

A CONTRADIÇÃO ERA MEDÍVEL, E FOI MEDIDA NA BANCADA
---------------------------------------------------
Com um DualSense no cabo, em 04/09/2026, pelo daemon vivo:

    mic.set {muted: true}   -> default-source: …HD_Pro_Webcam_C920…
    mic.set {muted: false}  -> default-source: …DualSense_Wireless_Controller…

O `mic.set` da TELA mudava o microfone padrão do SISTEMA — por efeito
colateral. O bit do firmware mudava, o laço das bordas via a mudança e elegia o
canal, e a resposta do `mic.set` não trazia uma palavra a respeito. O
acoplamento existia; o que não existia era o ato DECLARADO.

AS QUATRO MORDIDAS QUE ESTE ARQUIVO EXERCE
-------------------------------------------
1. **fazer `mic_button_loop` chamar `_eleger_ou_devolver` direto** (o chamador
   do ato arrancado) — reprova `test_o_botao_do_plastico_e_o_da_tela_chamam_a_mesma_funcao`;
2. **pôr um `if native_mode` em `ligar_o_microfone`** — reprova
   `test_o_ato_nao_muda_de_caminho_com_o_modo_nativo`;
3. **tirar o `_borda_e_eco_do_ato` do laço** — reprova
   `test_o_eco_da_nossa_escrita_nao_executa_o_ato_de_novo`;
4. **tirar a guarda de idempotência da metade do firmware** — reprova
   `test_o_botao_do_plastico_nao_toma_a_posse_do_byte`, que é a régua da
   decisão dela de 30/08: *"o botão do Controle sempre controla a interface"*.

E O DUBLÊ É TÃO ESTRITO QUANTO A PONTE REAL, que é a cicatriz de 04/09: a
máscara **nunca gravou um byte** e a régua passou verde porque o dublê aceitava
uma chamada que a ponte real recusa. Aqui
`test_o_duble_confere_a_assinatura_que_o_produto_chama` compara a assinatura
que o produto usa com a do backend de produção, por `inspect`.
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations.eleicao_de_microfone import ResultadoDaEleicao


# ---------------------------------------------------------------------------
# Os dublês — e cada um sabe RECUSAR, que é o que separa régua de carimbo
# ---------------------------------------------------------------------------


class BackendDeMentira:
    """O backend, com a MESMA assinatura da ponte real.

    `set_microphone_mute(muted, *, uniq=None) -> bool` e
    `audio_status_for(uniq) -> dict` são copiadas de
    `core/backend_pydualsense.py`; o teste
    `test_o_duble_confere_a_assinatura_que_o_produto_chama` prova a cópia.
    """

    def __init__(self, mic_mudo: bool = True) -> None:
        self.mic_mudo = mic_mudo
        self.escritas: list[tuple[bool | None, str | None]] = []
        self.leds: list[tuple[Any, str | None]] = []
        self.aceita_escrita = True

    def audio_status_for(self, uniq: str | None = None) -> dict[str, Any]:
        return {"fone_plugado": False, "mic_externo": False, "mic_mudo": self.mic_mudo}

    def set_microphone_mute(self, muted: bool | None, *, uniq: str | None = None) -> bool:
        self.escritas.append((muted, uniq))
        if not self.aceita_escrita:
            return False
        if isinstance(muted, bool):
            # O aparelho real leva ~550 ms; o dublê responde na hora, e é por
            # isso que o teste do represamento usa `aceita_escrita=False`.
            self.mic_mudo = muted
        return True

    def set_mic_led(self, aceso: Any, uniq: str | None = None) -> bool:
        self.leds.append((aceso, uniq))
        return True

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": "aa:bb:cc:00:00:01", "connected": True, "transport": "usb"}]


class EleitorDeMentira:
    def __init__(self, *, elege: bool = True) -> None:
        self.eleito: str | None = None
        self.elege = elege
        self.chamadas: list[tuple[str, str | None]] = []

    def eleger_o_controle(self, uniq: str, conectados: list[str]) -> ResultadoDaEleicao:
        self.chamadas.append(("eleger", uniq))
        if not self.elege:
            return ResultadoDaEleicao(
                ok=False, alvo=uniq, motivo="não há canal de captura para este controle"
            )
        self.eleito = uniq
        return ResultadoDaEleicao(ok=True, alvo=uniq, ativo=f"fonte-de-{uniq}")

    def devolver_o_microfone(self) -> ResultadoDaEleicao:
        self.chamadas.append(("devolver", self.eleito))
        self.eleito = None
        return ResultadoDaEleicao(ok=True, ativo="fonte-de-antes")


class DaemonDeMentira:
    """O daemon, com o mínimo que o ato pede — e nada além."""

    def __init__(self, *, backend: BackendDeMentira, native_mode: bool = False) -> None:
        self.controller = backend
        self._eleitor_de_microfone = EleitorDeMentira()
        self._tasks: list[Any] = []
        self._parando = False
        self.config = type("Cfg", (), {"mic_button_toggles_system": True})()
        # O MODO ENTRA NO DUBLÊ DE PROPÓSITO. Se algum dia o ato passar a
        # consultá-lo, a mordida 2 tem onde acontecer — um dublê que não
        # oferece a informação não consegue provar que ninguém a usou.
        self.store = type("Store", (), {"native_mode_active": native_mode})()
        self.native_mode = native_mode

    def is_native_mode(self) -> bool:
        return bool(self.native_mode)

    def _is_stopping(self) -> bool:
        return self._parando

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        """**SEM `**kwargs`, e é a assinatura do daemon REAL.**

        `daemon/lifecycle.py:_run_blocking(self, fn, *args)` e o protocolo em
        `daemon/protocols.py` são os dois posicionais-só — por baixo é um
        `loop.run_in_executor(executor, fn, *args)`, que não passa keywords.

        **O DUBLÊ AQUI TINHA `**kw`, E ISSO DEIXOU UM DEFEITO PASSAR VERDE.**
        Em 04/09/2026 o ato chamava
        `_run_blocking(setter, mudo_desejado, uniq=uniq)`; com o dublê frouxo
        os 17 testes passavam, e contra o daemon real aquilo levantava
        `TypeError` dentro de um `suppress` — a metade do firmware nunca
        escrevia um byte e o produto respondia uma frase educada. Quem revelou
        foi o APARELHO, na bancada, com a cura intacta.

        É a mesma família da máscara de 04/09 (`p.chamar("gamepad.mask.set",
        {…})`, o dicionário virando o `timeout` posicional): **o dublê era
        mais frouxo que a ponte real**. Endurecê-lo é a régua.
        """
        return fn(*args)


@pytest.fixture(autouse=True)
def _sem_eco_entre_testes() -> Any:
    """O registro do eco é de módulo; um teste não pode herdar o do outro."""
    hotkey._ECO_DO_ATO.clear()
    hotkey._CANAL_POR_UNIQ.clear()
    yield
    hotkey._ECO_DO_ATO.clear()
    hotkey._CANAL_POR_UNIQ.clear()


def _daemon(**kw: Any) -> DaemonDeMentira:
    return DaemonDeMentira(backend=BackendDeMentira(**kw.pop("backend", {})), **kw)


# ---------------------------------------------------------------------------
# 1. Uma função, dois chamadores — POR NOME
# ---------------------------------------------------------------------------


def test_o_botao_do_plastico_e_o_da_tela_chamam_a_mesma_funcao() -> None:
    """MORDIDA 1: os dois caminhos apontam para `ligar_o_microfone`, por NOME.

    Arranque o `ligar_o_microfone` de dentro de `mic_button_loop` (troque-o de
    volta por `_eleger_ou_devolver`) e este teste reprova dizendo que o botão
    do plástico deixou de fazer o ato.
    """
    fonte_do_laco = inspect.getsource(hotkey.mic_button_loop)
    assert "ligar_o_microfone(" in fonte_do_laco, (
        "o laço do botão do plástico não chama `ligar_o_microfone` — o botão "
        "físico e o da tela deixaram de ser o mesmo ato"
    )

    from hefesto_dualsense4unix.daemon import ipc_handlers

    fonte_do_handler = inspect.getsource(ipc_handlers.IpcHandlersMixin._handle_mic_canal_set)
    assert "ligar_o_microfone(" in fonte_do_handler, (
        "o handler do IPC não chama `ligar_o_microfone` — o botão da tela "
        "deixou de ser o mesmo ato"
    )


def test_o_metodo_do_ato_esta_registrado_no_ipc() -> None:
    """Uma função com dois chamadores só serve se o IPC souber chamá-la."""
    import pathlib

    fonte = pathlib.Path(
        inspect.getsourcefile(  # type: ignore[arg-type]
            __import__(
                "hefesto_dualsense4unix.daemon.ipc_server", fromlist=["x"]
            )
        )
    ).read_text(encoding="utf-8")
    assert '"mic.canal.set": self._handle_mic_canal_set' in fonte


# ---------------------------------------------------------------------------
# 2. O ato não muda de caminho com o modo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nativo", [False, True])
def test_o_ato_nao_muda_de_caminho_com_o_modo_nativo(nativo: bool) -> None:
    """MORDIDA 2: injete `native_mode=True` e o ato tem de fazer o MESMO.

    Regra dela: *"indepente se nativo ou virtual"*.  # noqa-acento: dela

    Ponha um `if daemon.is_native_mode(): return` em `ligar_o_microfone` e a
    versão `nativo=True` deste teste reprova. O que o Modo Nativo muda é o que
    o APARELHO aceita — e isso o ato RELATA, no teste do represamento abaixo.
    """
    d = _daemon(native_mode=nativo)
    ato = asyncio.run(hotkey.ligar_o_microfone(d, "aa:bb:cc:00:00:01", ligado=True))

    assert ato.canal_no_sistema.feita, "a metade do canal não aconteceu"
    assert ato.firmware.feita, "a metade do firmware não foi nem pedida"
    assert ato.feito
    assert d._eleitor_de_microfone.chamadas == [("eleger", "aa:bb:cc:00:00:01")]
    assert d.controller.escritas == [(False, "aa:bb:cc:00:00:01")], (
        "o ato escreveu (ou deixou de escrever) o mudo por causa do modo"
    )


def test_o_ato_e_identico_nos_dois_modos() -> None:
    """A prova direta da regra dela: os dois caminhos são o mesmo caminho."""
    passos = []
    for nativo in (False, True):
        d = _daemon(native_mode=nativo)
        ato = asyncio.run(hotkey.ligar_o_microfone(d, "aa:bb:cc:00:00:01", ligado=True))
        passos.append(
            (d._eleitor_de_microfone.chamadas, d.controller.escritas, ato.feito)
        )
    assert passos[0] == passos[1], (
        "o ato fez coisas diferentes em Virtual e em Nativo — a regra dela é "
        "que ele não muda de caminho com o modo"
    )


# ---------------------------------------------------------------------------
# 3. A idempotência é a decisão dela sobre o botão do plástico
# ---------------------------------------------------------------------------


def test_o_botao_do_plastico_nao_toma_a_posse_do_byte() -> None:
    """MORDIDA 4: vindo do plástico, o byte JÁ está certo — não se escreve.

    Escrever tomaria a posse do `hid-playstation`, e enquanto a posse for nossa
    *"o botão físico não manda mais"* (`_handle_mic_set`). Ou seja: o próximo
    toque dela no plástico não faria nada. É o oposto da decisão de 30/08 —
    *"o botão do Controle sempre controla a interface"*.

    Tire a guarda `if mudo_agora == mudo_desejado` de `_metade_do_firmware` e
    este teste reprova.
    """
    d = _daemon(backend={"mic_mudo": False})  # o kernel já desmutou no aperto
    ato = asyncio.run(hotkey.ligar_o_microfone(d, "aa:bb:cc:00:00:01", ligado=True))

    assert ato.firmware.feita, "a metade do firmware devia contar como feita"
    assert d.controller.escritas == [], (
        "o ato escreveu o byte que o kernel já tinha posto no valor certo — "
        "isso toma a posse e mata o botão do plástico dela"
    )


def test_o_gesto_de_tela_escreve_o_byte_divergente() -> None:
    """O outro lado da mesma guarda: divergindo, o ato escreve."""
    d = _daemon(backend={"mic_mudo": True})  # está mudo, e a tela pede ligado
    asyncio.run(hotkey.ligar_o_microfone(d, "aa:bb:cc:00:00:01", ligado=True))
    assert d.controller.escritas == [(False, "aa:bb:cc:00:00:01")]


# ---------------------------------------------------------------------------
# 4. O eco da nossa própria escrita não é gesto dela
# ---------------------------------------------------------------------------


def test_o_eco_da_nossa_escrita_nao_executa_o_ato_de_novo() -> None:
    """MORDIDA 3: a borda que a NOSSA escrita causa não pode virar gesto.

    Medido em 04/09: escrever o bit do mudo faz o firmware devolver a mudança
    no report de input ~550 ms depois, e o laço das bordas não tem como saber,
    sozinho, se aquilo foi o dedo dela. Tratar o eco como gesto executa o ato
    duas vezes — e com `ligado=False` a segunda cai no ramo da RECUSA e deposita
    no cartão dela uma frase dizendo que o microfone está com outro controle.

    Tire o `_borda_e_eco_do_ato` de `mic_button_loop` e este teste reprova.
    """
    hotkey._marcar_eco_do_ato("aa:bb:cc:00:00:01", True)
    assert hotkey._borda_e_eco_do_ato("aa:bb:cc:00:00:01", True) is True


def test_o_eco_vale_uma_vez_so() -> None:
    """A segunda borda com o mesmo valor é gesto dela, e tem de passar."""
    hotkey._marcar_eco_do_ato("aa:bb:cc:00:00:01", True)
    assert hotkey._borda_e_eco_do_ato("aa:bb:cc:00:00:01", True) is True
    assert hotkey._borda_e_eco_do_ato("aa:bb:cc:00:00:01", True) is False


def test_o_eco_nao_engole_o_gesto_contrario() -> None:
    """Ela clica na tela e logo aperta o plástico para desfazer: TEM de valer.

    Só o tempo engoliria esse gesto — que é o uso mais provável do botão logo
    depois de um clique. Por isso o eco exige o MESMO valor, e não só a janela.
    """
    hotkey._marcar_eco_do_ato("aa:bb:cc:00:00:01", True)
    assert hotkey._borda_e_eco_do_ato("aa:bb:cc:00:00:01", False) is False


def test_o_eco_expira(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passada a janela, a borda é gesto — o eco não vive para sempre."""
    relogio = {"t": 100.0}
    monkeypatch.setattr(hotkey, "_relogio", lambda: relogio["t"])
    hotkey._marcar_eco_do_ato("aa:bb:cc:00:00:01", True)
    relogio["t"] += hotkey.ECO_DO_ATO_S + 0.1
    assert hotkey._borda_e_eco_do_ato("aa:bb:cc:00:00:01", True) is False


# ---------------------------------------------------------------------------
# 5. O ato RECUSA dizendo qual metade faltou
# ---------------------------------------------------------------------------


def test_a_recusa_diz_qual_das_duas_metades_faltou() -> None:
    """Meio ato não é ato — e a frase nomeia a metade que não aconteceu."""
    d = _daemon()
    d._eleitor_de_microfone.elege = False
    ato = asyncio.run(hotkey.ligar_o_microfone(d, "aa:bb:cc:00:00:01", ligado=True))

    assert not ato.feito
    assert ato.firmware.feita, "o firmware aceitou; a metade que faltou é o canal"
    assert not ato.canal_no_sistema.feita
    assert "canal de captura" in ato.motivo
    assert ato.como_corpo()["status"] == "incompleto", (
        "responder 'ok' sobre meio ato é o verde falso que esta casa passou "
        "04/09 inteiro arrancando"
    )


def test_o_backend_que_recusa_a_escrita_nao_vira_ok() -> None:
    """O dublê SABE RECUSAR — régua que só sabe passar não é régua."""
    d = _daemon()
    d.controller.aceita_escrita = False
    ato = asyncio.run(hotkey.ligar_o_microfone(d, "aa:bb:cc:00:00:01", ligado=True))
    assert not ato.firmware.feita
    assert not ato.feito
    assert ato.motivo == hotkey.MOTIVO_FIRMWARE_REPRESADO


def test_as_duas_metades_falhando_dao_as_duas_frases() -> None:
    """Quem lê o cartão precisa saber que não foi só um pedaço."""
    d = _daemon()
    d.controller.aceita_escrita = False
    d._eleitor_de_microfone.elege = False
    ato = asyncio.run(hotkey.ligar_o_microfone(d, "aa:bb:cc:00:00:01", ligado=True))
    assert " · " in ato.motivo


# ---------------------------------------------------------------------------
# 6. O DUBLÊ TEM DE SER TÃO ESTRITO QUANTO A PONTE REAL
# ---------------------------------------------------------------------------


def test_o_duble_confere_a_assinatura_que_o_produto_chama() -> None:
    """A cicatriz de 04/09: a máscara nunca gravou um byte e a régua deu verde.

    O gesto chamava `p.chamar("gamepad.mask.set", {…})` e a assinatura real é
    `chamar(metodo, timeout=None,  # noqa-acento: assinatura do código
    **params)` — o dicionário virava o `timeout` posicional.
    O dublê do teste era mais frouxo que a ponte, então a régua não podia ver.

    Aqui a comparação é feita por `inspect`, contra o backend de PRODUÇÃO:
    `uniq` é KEYWORD-ONLY nas duas, e o ato passa `uniq=` por nome.
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import (
        PyDualSenseController,
    )

    real = inspect.signature(PyDualSenseController.set_microphone_mute)
    duble = inspect.signature(BackendDeMentira.set_microphone_mute)
    assert list(real.parameters) == list(duble.parameters), (
        f"o dublê divergiu da ponte real: {real} != {duble}"
    )
    assert real.parameters["uniq"].kind is inspect.Parameter.KEYWORD_ONLY
    assert duble.parameters["uniq"].kind is inspect.Parameter.KEYWORD_ONLY

    # O endereço vai por KEYWORD, e ele é passado dentro do envelope `_mutar`
    # — que existe porque `_run_blocking` só aceita posicionais (ver o teste
    # abaixo). Passá-lo posicional escreveria no controle errado numa mesa
    # cheia, e a assinatura real nem aceitaria.
    fonte = inspect.getsource(hotkey._mutar)
    assert "uniq=uniq" in fonte, (
        "o ato passa o endereço POSICIONAL — numa mesa cheia isso escreve no "
        "controle errado, e a assinatura real exige keyword"
    )


def test_o_run_blocking_do_duble_e_tao_estrito_quanto_o_do_daemon() -> None:
    """A régua que faltava, e ela nasce de um defeito que o APARELHO achou.

    O dublê deste arquivo tinha `**kwargs` no `_run_blocking` e o daemon real
    não tem. Resultado: 17 testes verdes sobre um ato que, contra o daemon de
    verdade, levantava `TypeError` e nunca escrevia o byte do mudo.

    Compara as duas assinaturas por `inspect`, e confere que o produto NÃO
    passa keyword nenhuma para o `_run_blocking` — quem precisa de keyword
    embrulha em posicionais (`_mutar`, `_acender`).
    """
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    real = inspect.signature(Daemon._run_blocking)
    duble = inspect.signature(DaemonDeMentira._run_blocking)
    assert list(real.parameters) == list(duble.parameters), (
        f"o dublê divergiu do daemon real: {real} != {duble}"
    )
    assert not any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in duble.parameters.values()
    ), "o dublê aceita `**kwargs` e o daemon real não — é o defeito de 04/09"

    for nome in ("_metade_do_firmware", "_confirmar_e_devolver", "_eleger_ou_devolver"):
        fonte = inspect.getsource(getattr(hotkey, nome))
        for linha in fonte.splitlines():
            if "_run_blocking(" not in linha:
                continue
            chamada = linha.split("_run_blocking(", 1)[1]
            assert "=" not in chamada.split(")")[0], (
                f"`{nome}` passa keyword ao `_run_blocking`, que só aceita "
                f"posicionais: {linha.strip()}"
            )


def test_o_recado_do_represamento_usa_um_gesto_que_a_tela_conhece() -> None:
    """`recado_do_microfone.GESTOS` é FECHADA, e `anotar` LEVANTA fora dela.

    Medido na bancada em 04/09: a primeira redação do represamento mandava
    `gesto="firmware-represado"`, o `ValueError` subiu dentro da task de
    confirmação e o recado NUNCA chegou ao `state_full` — o log do daemon
    dizia `mic_ato_represado` e a tela não recebia uma palavra. O verde do
    teste não teria visto: quem revelou foi a foto do `state_full`.

    Troque a palavra por uma que não está na tupla e este teste reprova.
    """
    from hefesto_dualsense4unix.daemon.subsystems import recado_do_microfone

    fonte = inspect.getsource(hotkey._confirmar_e_devolver)
    # Só as linhas de CÓDIGO: o comentário logo acima da chamada cita a
    # palavra errada de propósito, porque é a cicatriz que ele registra.
    usados = [
        linha.split('gesto="', 1)[1].split('"', 1)[0]
        for linha in fonte.splitlines()
        if 'gesto="' in linha and not linha.lstrip().startswith("#")
    ]
    assert usados, "o represamento deixou de anotar recado nenhum"
    for gesto in usados:
        assert gesto in recado_do_microfone.GESTOS, (
            f"o gesto {gesto!r} não está em `GESTOS` — `anotar` levanta, a "
            "task morre calada e a frase nunca chega ao cartão dela"
        )


def test_o_estado_composto_nao_inventa_o_canal_que_ninguem_leu() -> None:
    """MORDIDA: arranque a leitura do PipeWire e o selo NÃO pode ficar verde.

    O laço `canal_do_microfone_loop` nasce com o dicionário VAZIO. Enquanto ele
    não tiver perguntado uma vez, `canal_do_microfone` devolve `None` e o
    `state_full` não publica as chaves — ausência fala. Publicar
    `canal_ativo: false` (ou, pior, `true`) sobre um canal que ninguém olhou é
    o verde falso de 29/08 outra vez.
    """
    assert hotkey.canal_do_microfone("aa:bb:cc:00:00:01") is None
    assert hotkey.canal_do_microfone(None) is None
    hotkey._CANAL_POR_UNIQ["aa:bb:cc:00:00:01"] = {
        "fonte": "fonte-x", "canal_ativo": True, "canal_mudo": False,
        "volume_captura": 60,
    }
    lido = hotkey.canal_do_microfone("aa:bb:cc:00:00:01")
    assert lido is not None and lido["canal_ativo"] is True
    # É uma CÓPIA: quem lê o estado não pode escrever nele por acidente.
    lido["canal_ativo"] = False
    assert hotkey._CANAL_POR_UNIQ["aa:bb:cc:00:00:01"]["canal_ativo"] is True


def test_o_canal_mudo_desconhecido_nao_vira_falso() -> None:
    """`None` não é `False`: "não sei" e "não está muda" dão telas diferentes."""
    assert hotkey._fonte_esta_muda("uma-fonte-que-nao-existe-em-lugar-nenhum") is None
