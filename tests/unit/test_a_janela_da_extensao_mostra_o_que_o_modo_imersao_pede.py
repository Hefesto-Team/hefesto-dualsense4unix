"""A janela da extensão mostra o que o Modo imersão pede.

Sprint A-JANELA-DA-EXTENSAO-MOSTRA-O-QUE-O-MODO-IMERSAO-PEDE-01. Medido em 02/11/2026: o
``controles.lista`` dava só ``uniq`` e ``jogador``; o ``perfil.trocou`` não levava a chave
«Memória» do jogo em cena, e a janela não tinha como ligá-la; o «Agora» não tinha pedaço para o
que a extensão publica; e o ``aparece_com`` recusava tudo que não fosse outra opção.

A cura: o ``controles.lista`` leva ``cor``, o nome do plástico que a interface mostra; o
``perfil.trocou`` leva ``memoria``, e a opção ``memoria`` da janela liga e desliga a chave do jogo
em cena (só o Hefesto a grava; com anticheat, o primeiro clique mostra o aviso); o pedaço
``linhas`` do «Agora» pinta os pares ``{rotulo, valor}`` que a extensão publica, cortados no teto;
e o ``aparece_com`` aceita ``@presente``, os nomes que a extensão publica em ``presentes``.

MORDIDAS (02/11/2026, executadas sobre a cura e devolvidas, md5 conferido):

- sem o ``cor`` no ``_lista_dos_controles``, reprova ``test_a_lista_leva_a_cor_quando_se_sabe``;
- sem o ``memoria`` no dito do ``_ver_o_perfil``, reprova
  ``test_o_perfil_trocou_leva_a_memoria_e_muda_com_a_chave``;
- sem o corte em ``LINHAS_DO_AGORA``, reprova ``test_as_linhas_cortam_no_teto``;
- sem o ``@presente`` no ``aparecem``, reprova ``test_a_linha_do_presente_some_e_volta``;
- sem o aviso armado no gesto da memória, reprova
  ``test_com_anticheat_o_primeiro_clique_mostra_o_aviso``.
"""

from __future__ import annotations

import pathlib
import re
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    _a07,
    _fonte,
    _instalar,
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import _manifesto, _Ponte
from tests.unit.test_os_acessorios_seguem_os_jogos_escolhidos import _daemon, _store, _tudo
from tests.unit.test_a_porta_lista_os_controles import (  # noqa: F401
    LER_CONEXAO,
    UM,
    _pedir_a_lista,
    curto,
)

DOIS = "aa:bb:cc:00:00:02"
ESTADO = "publicar:acessorios.estado"
MEMORIA = "ler:jogo.memoria"
JOGO = "steam_app_570"
CHAVE = {"id": "memoria", "rotulo": "Memória neste jogo", "tipo": "memoria",  # (noqa-acento)
         "grupo": "Sentidos"}
PULSO = {"id": "efeito-pulso", "rotulo": "Pulso", "tipo": "ligado",
         "padrao": True, "aparece_com": {"@presente": "pulso"}}  # (noqa-acento)


def test_a_lista_leva_a_cor_quando_se_sabe(curto: pathlib.Path) -> None:  # noqa: F811
    def controles() -> list[dict[str, Any]]:
        return [{"uniq": UM, "jogador": 1, "cor": "Starlight Blue"},
                {"uniq": DOIS, "jogador": 2, "cor": ""}]

    lista = _pedir_a_lista(curto, [LER_CONEXAO], controles)["result"]["controles"]
    assert lista == [{"uniq": UM, "jogador": 1, "cor": "Starlight Blue"},
                     {"uniq": DOIS, "jogador": 2}], "a cor não chegou, ou a vazia virou nome"


def test_o_servico_da_o_nome_declarado_e_senao_o_de_fabrica() -> None:
    from hefesto_dualsense4unix.mods.porta import controles_no_servico

    fabrica = {UM: SimpleNamespace(cor=SimpleNamespace(nome="Cosmic Red")),
               DOIS: SimpleNamespace(cor=SimpleNamespace(nome="Cosmic Red"))}
    descricao = [{"connected": True, "uniq": UM}, {"connected": True, "uniq": DOIS},
                 {"connected": True, "uniq": "aa:bb:cc:00:00:03"}]
    daemon = SimpleNamespace(
        controller=SimpleNamespace(describe_controllers=lambda: descricao),
        _maquina=SimpleNamespace(controles={DOIS: SimpleNamespace(cor="Galactic Purple")}),
        identity_registry=SimpleNamespace(identidade_de_fabrica=fabrica.get))
    cores = {c["uniq"]: c.get("cor") for c in controles_no_servico(daemon)()}
    assert cores == {UM: "Cosmic Red", DOIS: "Galactic Purple", "aa:bb:cc:00:00:03": None}


def test_o_perfil_trocou_leva_a_memoria_e_muda_com_a_chave() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.autoswitch import AnunciadorDoJogo
    from hefesto_dualsense4unix.integrations.leitor_do_estado import (
        ChavesDaMemoria,
        arquivo_das_chaves,
    )

    bus = EventBus()
    fila = bus.subscribe(EventTopic.PERFIL_TROCOU)
    daemon = _daemon(570, bus, dois=False)
    anunciador = AnunciadorDoJogo(bus, _store("geral"), daemon)
    anunciador.ver()
    ChavesDaMemoria(arquivo_das_chaves()).gravar(JOGO, True)
    anunciador.ver()
    anunciador.ver()
    primeiro, segundo = _tudo(fila)
    assert (primeiro["jogo"], primeiro["memoria"]) == (JOGO, False)
    assert segundo["memoria"] is True, "ligar a chave não republicou o perfil.trocou"
    daemon.appid_em_cena = None
    anunciador.ver()
    (fora,) = _tudo(fila)
    assert (fora["jogo"], fora["memoria"]) == (None, False)


def test_a_porta_diz_o_jogo_em_cena_a_janela(curto: pathlib.Path) -> None:  # noqa: F811
    from hefesto_dualsense4unix.mods.porta import Porta, estado_vazio_dos_acessorios

    bus = EventBus()
    porta = Porta(curto / "mods.sock", bus, escritor=None, o_jogo_escreve=lambda u, c: False,
                  uniq_do_posto=lambda: UM)
    assert porta.agora_de("x") == estado_vazio_dos_acessorios("x")
    bus.publish(EventTopic.JOGO_IDENTIDADE, {"chave": JOGO})
    assert porta.agora_de("x")["jogo"] == JOGO


def test_as_linhas_cortam_no_teto() -> None:
    from hefesto_dualsense4unix.mods.porta import (
        LINHAS_DO_AGORA,
        RecusaError,
        estado_dos_acessorios,
    )

    linhas = [{"rotulo": f"Linha {n}", "valor": "coração, 92 bpm"} for n in range(9)]
    estado = estado_dos_acessorios("m", {"linhas": linhas, "presentes": ["pulso"] * 2})
    assert len(estado["linhas"]) == LINHAS_DO_AGORA == 6
    assert estado["presentes"] == ["pulso"]
    assert "linhas" not in estado_dos_acessorios("m", {}), "a linha que ninguém mandou apareceu"
    with pytest.raises(RecusaError, match="rótulo de uma linha"):
        estado_dos_acessorios("m", {"linhas": [{"rotulo": "x" * 21, "valor": "y"}]})


def test_o_pedaco_linhas_pinta_o_que_a_extensao_publicou() -> None:
    estado = {"ligado": True, "linhas": [{"rotulo": "Último", "valor": "coração, 92 bpm"},
                                         {"rotulo": "Sentem", "valor": "<b>Cosmic Red</b>"}]}
    html = exp.agora_html(["linhas"], estado)
    assert re.findall(r'<span class="ja-rot">([^<]*)</span>', html) == ["Último", "Sentem"]
    assert "&lt;b&gt;Cosmic Red" in html, "o valor de terceiro não foi escapado"
    parada = exp.agora_html(["linhas"], {**estado, "ligado": False})
    assert "Último" not in parada and exp.SEM_VALOR in parada
    assert Manifesto.model_validate(_manifesto(agora=["linhas"])).agora == ["linhas"]


def test_o_manifesto_confere_o_presente_e_a_memoria() -> None:
    m = Manifesto.model_validate(_manifesto(opcoes=[PULSO]))
    assert m.opcoes[0].aparece_com == {"@presente": "pulso"}
    for ruim, frase in ((1, "valendo 1"), ([], "valendo []"), ("x" * 41, "até 40 letras")):
        with pytest.raises(ValidationError, match=re.escape(frase)):
            Manifesto.model_validate(
                _manifesto(opcoes=[{**PULSO, "aparece_com": {"@presente": ruim}}]))
    with pytest.raises(ValidationError,
                       match=re.escape("pede a permissão publicar:acessorios.estado")):
        Manifesto.model_validate(_manifesto(opcoes=[PULSO], permissoes=[]))
    with pytest.raises(ValidationError, match=re.escape("pede a permissão ler:jogo.memoria")):
        Manifesto.model_validate(_manifesto(opcoes=[CHAVE]))
    with pytest.raises(ValidationError, match="não tem padrão"):
        Manifesto.model_validate(_manifesto(opcoes=[{**CHAVE, "padrao": True}],  # (noqa-acento)
                                            permissoes=[ESTADO, MEMORIA]))


@pytest.fixture
def janela(lar: Any, ctx: Any, tmp_path: pathlib.Path,  # noqa: F811
           monkeypatch: pytest.MonkeyPatch) -> Any:
    a07 = _a07()
    a07._MEXIDA.limpar()
    monkeypatch.setattr(a07, "_AGORA", a07._Agora())
    monkeypatch.setattr(a07, "_VIVA", a07._Viva())
    monkeypatch.setattr(a07, "_anticheat_de", lambda jogo: "")
    _instalar(a07, ctx, _fonte(tmp_path, permissoes=(ESTADO, MEMORIA),
                               opcoes=[CHAVE, PULSO]))

    def abrir(ponte: _Ponte) -> str:
        return str(a07.configurar_modificacao(ctx, {"v": "toque"}, ponte)["blocos"]["#mod-janela"])

    yield a07, abrir
    a07._MEXIDA.limpar()


def _chave_da_memoria(html: str) -> tuple[str, str] | None:
    achado = re.search(r'<span class="([^"]*)" data-gesto="memoria-do-jogo-da-modificacao"'
                       r'[^>]*>.*?<span class="txt">([^<]*)</span>', html)
    return (achado.group(1), achado.group(2)) if achado else None


def _ligada() -> bool:
    from hefesto_dualsense4unix.integrations.leitor_do_estado import (
        ChavesDaMemoria,
        arquivo_das_chaves,
    )

    return ChavesDaMemoria(arquivo_das_chaves()).ligada(JOGO)


def test_a_memoria_liga_e_desliga_o_jogo_em_cena(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, abrir = janela
    assert _chave_da_memoria(abrir(_Ponte({"ligado": True}))) is None, "sem jogo, a linha ficou"
    ponte = _Ponte({"ligado": True, "jogo": JOGO})
    assert _chave_da_memoria(abrir(ponte)) == ("nj-tog", "Desligado")
    carga = a07.memoria_do_jogo_da_modificacao(ctx, {"v": "toque"}, ponte)
    assert _ligada() and _chave_da_memoria(exp.janela_pintada(carga["blocos"])) == (
        "nj-tog ligado", "Ligado")
    a07.memoria_do_jogo_da_modificacao(ctx, {"v": "toque"}, ponte)
    assert not _ligada(), "o segundo clique não desligou"


def test_com_anticheat_o_primeiro_clique_mostra_o_aviso(janela: Any, ctx: Any,  # noqa: F811
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.integrations.leitor_do_estado import (
        ChavesDaMemoria,
        arquivo_das_chaves,
    )

    a07, abrir = janela
    monkeypatch.setattr(a07, "_anticheat_de", lambda jogo: "EasyAntiCheat")
    ponte = _Ponte({"ligado": True, "jogo": JOGO})
    abrir(ponte)
    armada = a07.memoria_do_jogo_da_modificacao(ctx, {"v": "toque"}, ponte)
    html = exp.janela_pintada(armada["blocos"])
    assert _chave_da_memoria(html) == ("nj-tog pede", exp.ROTULO_DO_SIM) and not _ligada()
    assert "EasyAntiCheat" in html, "o aviso não foi à dica"
    a07.memoria_do_jogo_da_modificacao(ctx, {"v": "toque"}, ponte)
    assert ChavesDaMemoria(arquivo_das_chaves()).liberada(JOGO, "EasyAntiCheat")


def _linhas_das_opcoes(html: str) -> set[str]:
    return set(re.findall(r'data-gesto="guardar-opcao-da-modificacao" data-v="toque:([^":]+)',
                          html))


def test_a_linha_do_presente_some_e_volta(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, abrir = janela
    ponte = _Ponte({"ligado": True, "presentes": ["pulso"]})
    assert "efeito-pulso" in _linhas_das_opcoes(abrir(ponte))
    ponte.estado["presentes"] = ["tiro"]
    a07._AGORA.ler("toque", ponte)
    sem = exp.janela_pintada(a07._a_pintura_agora(ctx)["blocos"])
    assert "efeito-pulso" not in _linhas_das_opcoes(sem), "a receita sem o efeito o mostrou"
    ponte.estado["presentes"] = ["pulso", "tiro"]
    a07._AGORA.ler("toque", ponte)
    assert "efeito-pulso" in _linhas_das_opcoes(
        exp.janela_pintada(a07._a_pintura_agora(ctx)["blocos"]))


def test_a_memoria_nao_se_grava_no_arquivo_das_opcoes(janela: Any, lar: Any) -> None:  # noqa: F811
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError, manifesto_instalado

    manifesto = manifesto_instalado("toque", lugares=lar)
    opcoes.guardar(manifesto, "efeito-pulso", False, lar)
    assert "memoria" not in opcoes.caminho("toque", lar).read_text(encoding="utf-8")
    with pytest.raises(InstalacaoRecusadaError, match="chave do jogo em cena"):
        opcoes.guardar(manifesto, "memoria", True, lar)
