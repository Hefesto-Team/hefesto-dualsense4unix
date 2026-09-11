#!/usr/bin/env python3
"""A-PERNA-QUE-FALTA-01 (11/09/2026) — quatro chamadores, uma perna só.

O FATO, EM UMA LINHA
--------------------
A casa tem UM dono da pergunta *"que perfil está valendo agora"*, e ele resolve
em DUAS pernas — o daemon primeiro, o marcador em disco depois. **Quatro lugares
perguntavam só à primeira**, e sob o estado da máquina dela — o daemon
respondendo ``active_profile: null`` com um perfil valendo no disco — os quatro
erravam:

===  ======================================  =====================================
 #   onde                                    o que custava a ela
===  ======================================  =====================================
 1   ``rodape.aplicar``                      ``ValueError`` barulhento sobre um
 2   ``rodape.salvar``                       perfil que ESTAVA escolhido — ela vê
 3   ``rodape.exportar``                     e reclama
 4   ``ipc_handlers._mascara_no_perfil``     **a máscara não ia para o perfil, e
                                             a tela dizia que foi.** CALADO
===  ======================================  =====================================

O QUARTO É O CARO, e o laudo que abriu a sprint o mediu assim: na MESMA corrida,
com o store em ``None`` e os marcadores valendo, o modo entrava pela interface e
gravava; a máscara saía pelo daemon e o ``.json`` do perfil ficava
**byte-idêntico**. A escolha ficava só no ``controller_masks.json`` — cache, não
dono: vale a sessão e não volta amanhã.

**É por isso que toda régua deste arquivo termina num ``json.load``.** O que
decide esta sprint é o BYTE NO ARQUIVO, não o retorno da função: um handler pode
devolver ``gravado: True`` e não ter escrito nada, e foi exatamente essa a
folha corrida da máscara em 04/09 (*"nunca gravou um byte"*).

AS QUATRO MORDIDAS (§5 da sprint), e cada uma tem o seu bloco abaixo:

1. arrancar a segunda perna do ``salvar`` → a régua reprova;
2. arrancar a de ``_mascara_no_perfil`` → a máscara SOME do JSON com o store
   vazio, e quem vê isso é o ``json.load``, não o retorno;
3. devolver ``chamar`` no lugar de ``chamar_detalhado`` → a ressalva some da
   tela;
4. **a que morde mais** — um dublê de store que responde ``None`` **e** um
   ``session.json`` válido no lar de mentira. É a combinação da máquina dela, e
   era a que nenhuma régua exercitava.

O QUE ESTE ARQUIVO NÃO MEDE, e está dito na entrega: nenhum byte sai no fio.
``gamepad.mask.set`` atravessando o socket de verdade, e o vpad nascendo com a
máscara que o perfil guarda, é degrau de bancada.

Endereços de rádio: faixa SINTÉTICA da casa, nunca o OUI de um aparelho real.
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import pwd
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.subsystems import external_mask as mask_mod
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba
from hefesto_dualsense4unix.interface.pacotes import perfil as pac_perfil
from hefesto_dualsense4unix.interface.pacotes import ponte as pac_ponte
from hefesto_dualsense4unix.interface.pacotes import rodape
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
from hefesto_dualsense4unix.utils import session as sessao
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

#: O assento, na faixa sintética da casa (octetos 4 e 5 zerados).
P1 = "aa:bb:cc:00:00:01"
P1_CHAVE = "aabbcc000001"

#: O NOME DO PERFIL QUE ESTÁ NO DISCO DELA, nesta régua.
NO_DISCO = "bancada"


@pytest.fixture
def lar_de_mentira() -> pathlib.Path:
    """O lar isolado do ``conftest``, CONFERIDO — e a conferência é a régua.

    O ``conftest`` já desvia ``HOME`` e os cinco ``XDG_*`` para um lar de
    mentira (autouse). Esta fixture não o refaz; ela **confirma**, e aborta se o
    desvio não pegou.

    POR QUE A CONFERÊNCIA EXISTE: este arquivo escreve ``session.json``,
    ``active_profile.txt`` e um perfil. Se o desvio falhar, ele escreve no
    ``~/.config`` REAL dela — no perfil que o daemon vivo está usando neste
    instante. Uma régua que pode estragar a mesa de quem a roda não é régua.

    **A ÂNCORA É O LAR DO SISTEMA, lido do ``passwd`` e NÃO do ``$HOME``** —
    e as duas tentativas anteriores caíram, o que vale escrever:

    * *"está sob o ``$HOME``?"* reprova o lar de mentira CERTO: o ``conftest``
      põe ``HOME`` em ``…/.xdg/home`` e ``XDG_CONFIG_HOME`` em ``…/.xdg/config``
      — irmãos, não aninhados;
    * *"está sob o diretório temporário?"* também: ``TMPDIR`` aponta para o
      berço da suíte (``/tmp/hefesto-berco-…``) e o ``tmp_path`` do pytest mora
      noutro galho de ``/tmp``.

    O que decide é UMA coisa só, e é a que importa: **este caminho não pode ser
    o do daemon vivo dela**. O ``$HOME`` é justamente o que o desvio mexe, então
    perguntá-lo seria medir o desvio com o próprio desvio — a armadilha de
    07/09, *a trava que se mede contra a própria saída*. O ``passwd`` não mente.
    """
    lar_real = pathlib.Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
    alvo = profiles_dir(ensure=True).resolve()
    assert not alvo.is_relative_to(lar_real), (
        f"profiles_dir() caiu DENTRO do lar real dela: {alvo}. Esta régua "
        "escreve perfil, session.json e marcador — sem o desvio do `conftest` "
        "ela escreveria no ~/.config que o daemon vivo está usando agora.")
    mask_mod._zerar_registro_de_mascaras()
    try:
        yield alvo
    finally:
        mask_mod._zerar_registro_de_mascaras()


@pytest.fixture
def a_maquina_dela(lar_de_mentira: pathlib.Path) -> pathlib.Path:
    """A COMBINAÇÃO DA MÁQUINA DELA — a quarta mordida, e ela é a fixture.

    Um perfil no disco, os DOIS marcadores da sessão apontando para ele, e o
    daemon que **não sabe de nada**. Medido em 06/09/2026 e descrito em
    ``profiles_actions.perfil_que_esta_valendo``: o daemon responde
    ``active_profile: null`` com um perfil valendo.

    Devolve o caminho do ``.json`` do perfil — é nele que o byte se mede.
    """
    save_profile(Profile(name=NO_DISCO, match=MatchManual()), origem="regua")
    sessao.save_last_profile(NO_DISCO)
    sessao.save_active_marker(NO_DISCO)
    assert sessao.resolve_boot_profile() == NO_DISCO, (
        "o resolvedor do boot não viu os marcadores que esta régua acabou de "
        "escrever — sem isso nada abaixo mede o que promete")
    arquivo = profiles_dir() / f"{NO_DISCO}.json"
    assert arquivo.exists(), "o perfil não chegou ao disco do lar de mentira"
    return arquivo


def _no_disco(arquivo: pathlib.Path) -> dict[str, Any]:
    """O JSON COMO ELE ESTÁ NO DISCO — nenhuma camada do produto no meio.

    `load_profile` passaria pelo pydantic e normalizaria campo; o que esta
    sprint decide é o BYTE, então a leitura é crua.
    """
    return json.loads(arquivo.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. O DONO DA PERGUNTA, do lado do daemon — `_perfil_que_grava`
# ---------------------------------------------------------------------------


class _Store:
    """O ``store`` de mentira: só o ``active_profile``, como o produto o lê."""

    def __init__(self, ativo: str | None) -> None:
        self.active_profile = ativo


class _Handlers(IpcHandlersMixin):
    """O bastante do mixin para os dois gravadores que esta régua exercita."""

    def __init__(self, *, ativo: str | None) -> None:
        self.store = _Store(ativo)  # type: ignore[assignment]
        self.controller = SimpleNamespace(  # type: ignore[assignment]
            describe_controllers=lambda: []
        )
        self.daemon = None  # type: ignore[assignment]


def test_o_daemon_calado_cai_no_marcador_do_proprio_boot(
    a_maquina_dela: pathlib.Path,
) -> None:
    """Store em ``None`` + marcadores valendo → o nome do disco.

    E ELE NÃO É UMA LEITURA NOVA: `utils.session.resolve_boot_profile` é o mesmo
    resolvedor que `daemon/connection.py` usa para restaurar o perfil ao ligar.
    Curar aqui devolve a simetria que o boot já tinha.
    """
    assert _Handlers(ativo=None)._perfil_que_grava() == NO_DISCO
    # E o daemon que SABE continua mandando — a primeira perna vence.
    assert _Handlers(ativo="outro")._perfil_que_grava() == "outro"


def test_o_marcador_orfao_nao_vira_excecao_na_mao_dela(
    a_maquina_dela: pathlib.Path,
) -> None:
    """Marcador apontando para perfil apagado → ``None``, e nada estoura.

    A DOCSTRING DO RESOLVEDOR AVISA: *"esta função só resolve NOMES — não valida
    se o perfil carrega"*. Sem a confirmação que `_perfil_que_grava` faz, um
    marcador órfão trocaria o silêncio de hoje por um ``FileNotFoundError`` no
    meio de um gesto dela — piorar, não curar.

    MORDIDA: tire o ``load_profile`` de confirmação de `_perfil_que_grava` e
    esta régua passa a ver a exceção subir.
    """
    sessao.save_last_profile("um-perfil-que-ela-apagou")
    sessao.save_active_marker("um-perfil-que-ela-apagou")
    assert _Handlers(ativo=None)._perfil_que_grava() is None


# ---------------------------------------------------------------------------
# 2. A SEGUNDA MORDIDA — a máscara, e o BYTE no arquivo
# ---------------------------------------------------------------------------


def _mask_set(h: _Handlers, **params: Any) -> dict[str, Any]:
    return asyncio.run(h._handle_gamepad_mask_set(params))


def test_a_mascara_entra_no_perfil_com_o_daemon_calado(
    a_maquina_dela: pathlib.Path,
) -> None:
    """O QUARTO CHAMADOR, medido no disco: antes e depois.

    É a régua que a sprint chama de *"o único degrau que decide"*. Ela não olha
    o ``gravado`` da resposta — olha o ``.json``.
    """
    antes = _no_disco(a_maquina_dela)
    assert not antes.get("controllers"), (
        "o perfil já nasceu com opinião sobre alguma peça; a régua mediria o "
        "que ela mesma plantou")

    resposta = _mask_set(_Handlers(ativo=None), uniq=P1, flavor="xbox")

    depois = _no_disco(a_maquina_dela)
    assert depois["controllers"][P1_CHAVE]["mascara"] == "xbox", (
        f"a máscara não chegou ao disco: {depois.get('controllers')!r}")
    assert resposta["perfil"] == NO_DISCO and resposta["gravado"] is True


def test_com_a_cura_arrancada_o_json_fica_byte_identico(
    a_maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA 2, feita por dentro: sem a segunda perna, nada é escrito.

    A arrancada é literal — `_perfil_que_grava` volta a ser o
    ``getattr(self.store, "active_profile", None)`` de antes da sprint.

    E O QUE ELA PROVA É A FORMA DO DEFEITO: a resposta do daemon não muda de
    ``status``, o registro de sessão guarda a máscara, a tela acende o chip — e
    o arquivo do perfil fica **byte a byte o mesmo**. Calado.
    """
    monkeypatch.setattr(
        IpcHandlersMixin,
        "_perfil_que_grava",
        lambda self: getattr(self.store, "active_profile", None),
    )
    bytes_antes = a_maquina_dela.read_bytes()

    resposta = _mask_set(_Handlers(ativo=None), uniq=P1, flavor="xbox")

    assert resposta["status"] == "ok", (
        "o defeito não era um erro visível — era um 'ok' sobre nada")
    assert resposta["gravado"] is False and resposta["motivo"] == "sem_perfil"
    assert a_maquina_dela.read_bytes() == bytes_antes, (
        "com a cura arrancada o arquivo MUDOU — então esta régua não estava "
        "medindo o byte que ela promete medir")


def test_a_barra_de_motor_tambem_esperava_a_segunda_perna(
    a_maquina_dela: pathlib.Path,
) -> None:
    """O levantamento da §3: `rumble.motores.set` GRAVA, logo tinha o mesmo defeito.

    A REGRA QUE MANDA CURÁ-LO JUNTO é a de 05/09: *quando a cura conhece a
    causa, ela cobre TODOS os chamadores*. Cobrir só a máscara deixaria a
    próxima pessoa remedindo isto na barra de motor.

    MORDIDA: devolva o ``getattr(self.store, …)`` em `_handle_rumble_motores_set`
    e a resposta volta a ser ``sem_perfil`` com o ``.json`` intacto.
    """
    resposta = asyncio.run(
        _Handlers(ativo=None)._handle_rumble_motores_set(
            {"uniq": P1, "forte_pct": 40}
        )
    )
    assert resposta["status"] == "ok", resposta
    depois = _no_disco(a_maquina_dela)
    assert depois["controllers"][P1_CHAVE]["rumble"]["motor_forte_pct"] == 40, (
        f"a barra não chegou ao disco: {depois.get('controllers')!r}")


def test_o_censo_dos_leitores_do_store_no_ipc_handlers() -> None:
    """§3 — TODO leitor de ``store.active_profile``, separado em GRAVA e SÓ LÊ.

    **NÃO SE CURA POR SIMETRIA**, e é isto que esta régua tranca: um método que
    só RELATA o ativo pode responder ``null`` quando o daemon não sabe — é a
    resposta certa, porque quem pergunta ao daemon quer saber o que o DAEMON
    sabe. Quem tem de cair no disco é quem GRAVA, porque aí o ``null`` custa
    dado dela.

    O QUE ELA REPROVA: um leitor NOVO do store que ninguém classificou. Ela é um
    censo, e censo que não reprova o item novo envelhece calado — que é como as
    quatro pernas chegaram a quatro.
    """
    import ast

    fonte = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "ipc_handlers.py"
    ).read_text(encoding="utf-8")

    #: A CLASSIFICAÇÃO, e ela é o produto da §3 desta sprint.
    declarados = {
        # GRAVA no perfil → as duas pernas. É o dono, e os três gravadores
        # (`gamepad.mask.set`, `rumble.motores.set`, `sensor.set`) passam por
        # ele — por isso eles não aparecem neste censo com leitura própria.
        "_perfil_que_grava": "grava",
        # SÓ RELATA o que o daemon sabe — `null` é resposta, não defeito.
        "_handle_profile_switch": "so-le",
        "_handle_daemon_status": "so-le",
        "_handle_daemon_state_full": "so-le",
    }

    achados: dict[str, list[int]] = {}

    class _Censo(ast.NodeVisitor):
        def __init__(self) -> None:
            self.pilha: list[str] = []

        def visit_FunctionDef(self, no: ast.FunctionDef) -> None:
            self._entrar(no)

        def visit_AsyncFunctionDef(self, no: ast.AsyncFunctionDef) -> None:
            self._entrar(no)

        def _entrar(self, no: Any) -> None:
            self.pilha.append(no.name)
            for filho in ast.iter_child_nodes(no):
                self.visit(filho)
            self.pilha.pop()

        def generic_visit(self, no: ast.AST) -> None:
            achou = (
                isinstance(no, ast.Constant) and no.value == "active_profile"
            ) or (isinstance(no, ast.Attribute) and no.attr == "active_profile")
            if achou and self.pilha:
                achados.setdefault(self.pilha[-1], []).append(no.lineno)
            super().generic_visit(no)

    _Censo().visit(ast.parse(fonte))

    novos = sorted(set(achados) - set(declarados))
    assert not novos, (
        f"leitor(es) de `active_profile` sem classificação: {novos}. "
        "A §3 da A-PERNA-QUE-FALTA-01 exige dizer, para cada um, se ele GRAVA "
        "no perfil (então precisa da segunda perna, `_perfil_que_grava`) ou se "
        "só RELATA o ativo (e aí `null` é a resposta certa). Classifique-o "
        "aqui.")
    sumiram = sorted(set(declarados) - set(achados))
    assert not sumiram, (
        f"o censo declara leitores que não existem mais: {sumiram} — um censo "
        "com item morto manda a próxima pessoa procurar o que já saiu")

    # E A METADE QUE DECIDE: quem GRAVA não lê o store por conta própria. Se
    # voltar a ler, ele voltou a ter uma perna só.
    fora_do_dono = [
        nome for nome in achados
        if declarados.get(nome) == "grava" and nome != "_perfil_que_grava"
    ]
    assert not fora_do_dono, (
        f"{fora_do_dono} grava no perfil e lê o store por conta própria — "
        "a pergunta tem dono, e ele é `_perfil_que_grava`")


# ---------------------------------------------------------------------------
# 3. A PRIMEIRA MORDIDA — o rodapé, e o Salvar que escreve no disco
# ---------------------------------------------------------------------------


class _PonteDoRodape:
    """O bastante para os três gestos do rodapé, e nada mais frouxo que a real."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def apply_draft_detalhado(self, payload: dict[str, Any]) -> tuple[bool, None]:
        self.chamadas.append(("apply_draft_detalhado", (payload,), {}))
        return True, None

    def salvar_arquivo(self, titulo: str, sugestao: str = "") -> str | None:
        self.chamadas.append(("salvar_arquivo", (titulo,), {"sugestao": sugestao}))
        return None  # ela cancelou — o gesto só tinha de CHEGAR aqui


def _ctx_do_daemon_calado() -> Contexto:
    """O contexto da máquina dela: o daemon não diz quem está ativo."""
    return Contexto(state={"connected": True}, mesa=[], conectados=[], estados={})


def test_o_salvar_grava_com_o_daemon_calado(a_maquina_dela: pathlib.Path) -> None:
    """O gesto que ESCREVE NO DISCO DELA, medido no disco.

    Antes desta sprint ele levantava *"salvar: não há perfil ativo. Escolha um
    na aba Perfis."* — em cima de um perfil que ESTAVA escolhido, e que o
    próprio daemon restauraria no próximo boot pelo mesmo marcador.
    """
    antes = _no_disco(a_maquina_dela)
    rodape.salvar(_ctx_do_daemon_calado(), {}, _PonteDoRodape())
    depois = _no_disco(a_maquina_dela)

    assert depois["name"] == NO_DISCO, (
        f"o Salvar mirou outro perfil: {depois['name']!r}")
    assert antes["name"] == NO_DISCO  # e era o mesmo alvo antes do clique
    assert load_profile(NO_DISCO).name == NO_DISCO


def test_com_a_cura_arrancada_os_tres_do_rodape_recusam(
    a_maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA 1, e ela vale para os TRÊS — porque a cura foi a mesma.

    A arrancada devolve a leitura CRUA do estado, que é o que os três faziam.
    """
    monkeypatch.setattr(
        pac_perfil,
        "nome_do_ativo",
        lambda state=None: str((state or {}).get("active_profile") or ""),
    )
    ctx = _ctx_do_daemon_calado()
    bytes_antes = a_maquina_dela.read_bytes()

    for gesto in (rodape.aplicar, rodape.salvar, rodape.exportar):
        with pytest.raises((ValueError, RuntimeError)) as erro:
            gesto(ctx, {}, _PonteDoRodape())
        assert "perfil" in str(erro.value).lower(), (
            f"{gesto.__name__} recusou por outra razão: {erro.value}")

    assert a_maquina_dela.read_bytes() == bytes_antes, (
        "a recusa arrancada ainda assim escreveu — a régua não mede o que diz")


def test_o_aplicar_e_o_exportar_atravessam_com_o_daemon_calado(
    a_maquina_dela: pathlib.Path,
) -> None:
    """Os outros dois chegam ao fim do caminho em vez de recusar.

    O `exportar` para no seletor do sistema — ela cancela — e isso basta: o que
    se mede é que ele ACHOU o perfil e o arquivo dele.
    """
    p = _PonteDoRodape()
    rodape.aplicar(_ctx_do_daemon_calado(), {}, p)
    assert [c[0] for c in p.chamadas] == ["apply_draft_detalhado"]

    q = _PonteDoRodape()
    assert rodape.exportar(_ctx_do_daemon_calado(), {}, q) is None
    assert [c[0] for c in q.chamadas] == ["salvar_arquivo"]
    assert NO_DISCO in q.chamadas[0][2]["sugestao"], (
        f"o exportar sugeriu outro arquivo: {q.chamadas[0][2]['sugestao']!r}")


# ---------------------------------------------------------------------------
# 4. A TERCEIRA MORDIDA — a ressalva na tela, e o motivo que morria na ponte
# ---------------------------------------------------------------------------


class _PonteQueRecusaNoCorpo:
    """A ponte com as DUAS funções, para a régua trocar uma pela outra.

    `chamar` devolve ``bool`` — é a que descartava o motivo.
    `chamar_detalhado` devolve ``(ok, motivo)`` — é a que o gesto usa hoje.
    """

    def __init__(self, motivo: str | None) -> None:
        self.motivo = motivo
        self.chamadas: list[tuple[str, dict]] = []

    def chamar(self, metodo: str, timeout: float | None = None, **p: Any) -> bool:
        self.chamadas.append((metodo, p))
        return True

    def chamar_detalhado(self, metodo: str, **p: Any) -> tuple[bool, str | None]:
        self.chamadas.append((metodo, p))
        return True, self.motivo


def _clique_na_mascara(p: Any) -> Any:
    return aba.mascara_do_controle(
        Contexto(state={}, mesa=[], conectados=[], estados={}),
        {"uniq": P1, "mascara": "Xbox 360"},
        p,
    )


def test_a_recusa_do_corpo_vira_frase_no_cartao() -> None:
    """``sem_perfil`` vira o que ELA faz a seguir — nunca o nome do estado.

    Ordem dela, 07/09: *"o layout não informa os nossos defeitos"*.
    """
    resposta = _clique_na_mascara(_PonteQueRecusaNoCorpo("sem_perfil"))
    assert resposta == {"recado": aba.MASCARA_VALE_SEM_PERFIL}
    frase = aba.MASCARA_VALE_SEM_PERFIL
    assert "sem_perfil" not in frase and "active_profile" not in frase
    assert "mesa" not in frase.lower(), "a palavra banida entrou na tela"
    # AS DUAS METADES (`AS-DUAS-ABAS-FALAM-01`): o que deu e o que não deu.
    assert "vale agora" in frase and "Perfis" in frase


def test_o_sem_mudanca_nao_vira_aviso() -> None:
    """O perfil JÁ guardava essa máscara — a piscada verde responde sozinha.

    Falar aqui seria transformar um clique sem efeito nenhum num aviso de 6 s, e
    quem recebe a mesma frase em todo clique para de ler os recados.
    """
    assert _clique_na_mascara(_PonteQueRecusaNoCorpo("sem_mudanca")) is None
    assert _clique_na_mascara(_PonteQueRecusaNoCorpo(None)) is None


def test_um_motivo_desconhecido_nao_chega_cru_ao_cartao() -> None:
    """Token interno não é texto de tela. A frase genérica cobre o caso novo."""
    resposta = _clique_na_mascara(_PonteQueRecusaNoCorpo("um_motivo_que_nasce_amanha"))
    assert resposta == {"recado": aba.MASCARA_VALE_SEM_GUARDAR}


def test_com_o_chamar_de_volta_a_ressalva_some(monkeypatch: pytest.MonkeyPatch) -> None:
    """A MORDIDA 3, literal: devolva `chamar` e a tela volta a ficar calada.

    A arrancada troca a função que o gesto pede à ponte. O `chamar` devolve
    ``bool``: o `motivo` que o daemon acabou de mandar não tem por onde chegar,
    e o cartão pisca verde sobre um perfil que não mudou.
    """
    ponte_velha = _PonteQueRecusaNoCorpo("sem_perfil")
    ponte_velha.chamar_detalhado = (  # type: ignore[assignment]
        lambda metodo, **p: (ponte_velha.chamar(metodo, **p), None)
    )
    assert _clique_na_mascara(ponte_velha) is None, (
        "com o `chamar` de volta a régua ainda viu a ressalva — então ela não "
        "estava medindo a ponte")


def test_a_ponte_junta_as_duas_formas_de_o_daemon_dizer_nao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ponte.chamar_detalhado` lê a recusa NO CORPO — e `chamar` não.

    É a diferença medida, e não a docstring: com o daemon respondendo
    ``{"status": "ok", "gravado": false, "motivo": "sem_perfil"}``, o RPC deu
    certo. `_call_checked` sozinho responderia ``(True, None)``.
    """
    corpo = {"status": "ok", "gravado": False, "motivo": "sem_perfil"}
    monkeypatch.setattr(
        pac_ponte._b, "_run_call", lambda metodo, params, timeout=None: corpo
    )
    assert pac_ponte.chamar_detalhado("gamepad.mask.set", uniq=P1, flavor="xbox") == (
        True,
        "sem_perfil",
    )
    # E o `chamar` continua sendo o que joga fora — é por isso que ele não serve
    # a um botão que precisa DIZER.
    assert pac_ponte.chamar("gamepad.mask.set", uniq=P1, flavor="xbox") is True
