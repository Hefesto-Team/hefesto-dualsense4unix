"""O botão do modo que a extensão pede, irmão do Modo automático, nas abas de cada seção.

Sem extensão ligada que peça a aba, nenhum botão no DOM: a vaga nasce vazia em Controles (a
seção que mora no Jogar), Gatilhos, Iluminação e Vibração. Com uma extensão de mentira ligada, o
botão aparece nas abas; aceso, apaga o automático (e o clique nele pede o Personalizado); desligar a
extensão o tira, e o perfil guarda a escolha. O gesto de cada aba grava o pedido na própria
seção; a aba Perfis não tem o par, porque cada aba já mostra o modo da sua seção. Lar de
mentira: o ``conftest`` desvia ``HOME`` e os ``XDG_*``.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _p in (str(RAIZ / "src"), str(INTERFACE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hefesto_dualsense4unix.interface import monta
from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import (
    MODO_AUTOMATICO,
    MODO_PERSONALIZADO,
    PREFIXO_DO_MODO_DA_EXTENSAO,
    LedsConfig,
    MatchAny,
    Profile,
    RumbleConfig,
    TriggersConfig,
)

MOD = "pede"
MODO = PREFIXO_DO_MODO_DA_EXTENSAO + MOD
OUTRO = PREFIXO_DO_MODO_DA_EXTENSAO + "outra"
UM = "aa:bb:cc:00:00:01"
NOME = "regua-do-par-da-extensao"
ROTULO = "Modo da extensão"
CINCO = {"02": ("01-jogar.html", "modo-dos-controles"),
         "03": ("03-gatilhos.html", "modo-dos-gatilhos"),
         "04": ("04-iluminacao.html", "modo-da-luz"),
         "05": ("05-vibracao.html", "modo-da-vibracao")}
MESA = [{"pref": "p1", "uniq": UM, "jogador": 1, "cor": "white", "nome": "White",
         "via": "USB", "mascara": "DualSense"}]
P1 = {"uniq": UM, "index": 0, "transport": "usb", "connected": True, "player": 1,
      "player_slot": 1, "is_primary": True, "inputs": {"l2_raw": 0, "r2_raw": 0},
      "lightbar_rgb": [0, 0, 255], "lightbar_on": True, "lightbar_source": "sysfs"}
MANIFESTO: dict[str, Any] = {"id": MOD, "nome": "Pede", "api": ">=2,<3", "tipos": ["tema"],
                             "tema": {}, "licenca": "MIT",
                             "modos_de_aba": [{"id": "fundo", "rotulo": ROTULO,
                                               "dica": "A extensão governa a seção.",
                                               "abas": list(CINCO)}]}
MANIFESTO["versao"] = "1.0.0"  # (noqa-acento)


@pytest.fixture
def lg(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> instalador.Lugares:
    lugares = instalador.Lugares(codigo=tmp_path / "codigo",  # (noqa-acento)
                                 dados=tmp_path / "dados", registro=tmp_path / "mods.json",
                                 estado=tmp_path / "estado.json")
    monkeypatch.setattr(instalador.Lugares, "do_xdg", classmethod(lambda cls: lugares))
    return lugares


def _instalada(lg: instalador.Lugares, *, ligada: bool = True) -> None:
    pasta = lg.codigo / MOD
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps(MANIFESTO), encoding="utf-8")
    registro = instalador.ler_registro(lg.registro)
    registro[MOD] = instalador.Entrada(
        id=MOD, nome="Pede", versao="1.0.0", origem="local", endereco=str(pasta),
        permissoes_aceitas=[], ligada=ligada, ligada_em="2026-11-01T10:00:00")
    instalador.gravar_registro(lg.registro, registro)


@pytest.fixture
def pac() -> Any:
    import pacotes

    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield pacotes
    a03_gatilhos.esquecer_o_rascunho()


@pytest.fixture
def pasta_de_perfis() -> pathlib.Path:
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    alvo = pathlib.Path(profiles_dir(ensure=True))
    for velho in alvo.glob("*.json"):
        velho.unlink()
    return alvo


class Ponte:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, nome: str) -> Any:
        def registrar(*args: Any, **kwargs: Any) -> Any:
            self.chamadas.append((nome, args, kwargs))
            return True if nome in ("chamar", "profile_switch") else {
                "aplicado_em": [UM], "guardado_em": []}

        return registrar


def _ctx(pac: Any) -> Any:
    return pac.Contexto(state={"active_profile": NOME}, mesa=[dict(m) for m in MESA],
                        conectados=[dict(P1)], estados={})


def _salvar(modo: str | None = None) -> None:
    secoes: dict[str, Any] = {}
    if modo is not None:
        secoes = {"controles_modo": modo, "triggers": TriggersConfig(modo=modo),
                  "leds": LedsConfig(modo=modo), "rumble": RumbleConfig(modo=modo)}
    save_profile(Profile(name=NOME, match=MatchAny(), **secoes), origem="regua")


def _modos_no_disco() -> tuple[Any, ...]:
    prof = load_profile(NOME)
    return (prof.controles_modo, prof.triggers.modo, prof.leds.modo, prof.rumble.modo)


def _botoes(texto: str) -> list[dict[str, str]]:
    return [dict(re.findall(r'([a-z-]+)="([^"]*)"', b))
            for b in re.findall(r'<button class="modo-ext"[^>]*>', texto)]


def _pacote(pac: Any, aba: str) -> dict[str, Any]:
    from pacotes import a03_gatilhos, a04_iluminacao, a05_vibracao

    modulo = {"03": a03_gatilhos, "04": a04_iluminacao, "05": a05_vibracao}[aba]
    return dict(modulo.pacote(_ctx(pac)))


def test_sem_extensao_a_vaga_nasce_vazia_nas_cinco_paginas(lg: instalador.Lugares) -> None:
    paginas = [*((p, g) for p, g in CINCO.values()), ("02-controles.html", CINCO["02"][1])]
    for pagina, gesto in paginas:
        html = (RAIZ / "mockup" / pagina).read_text(encoding="utf-8")
        assert 'class="modo-ext"' not in html, pagina
        vaga = f'<span class="vaga-da-extensao" data-campo="{gesto}-{monta.CAMPO_DA_EXTENSAO}"'
        assert html.count(vaga) == 1, pagina
    for aba, (_pagina, gesto) in CINCO.items():
        assert monta.campo_da_extensao(gesto, aba, MODO_PERSONALIZADO) == {
            f"{gesto}-{monta.CAMPO_DA_EXTENSAO}": ""}


def test_a_extensao_ligada_traz_o_botao_nas_cinco_e_desligada_o_tira(
        lg: instalador.Lugares) -> None:
    _instalada(lg)
    for aba, (_pagina, gesto) in CINCO.items():
        [campo] = monta.campo_da_extensao(gesto, aba, MODO_PERSONALIZADO).values()
        [botao] = _botoes(campo)
        assert botao["data-gesto"] == gesto
        assert botao["data-modo"] == MODO
        assert botao["aria-pressed"] == "false"
        assert botao["data-dica"] == "A extensão governa a seção."
        assert campo.endswith(f"{ROTULO}</button>")
    _instalada(lg, ligada=False)
    for aba, (_pagina, gesto) in CINCO.items():
        assert monta.modos_da_extensao(gesto, aba, MODO) == ""
        assert monta.modo_na_tela(MODO, aba) == MODO_PERSONALIZADO
        assert not monta.pedido_da_aba(MODO, aba)


def test_o_pedido_aceso_apaga_o_automatico_e_o_clique_nele_pede_o_personalizado(
        lg: instalador.Lugares, pac: Any, pasta_de_perfis: pathlib.Path) -> None:
    _instalada(lg)
    for modo, aceso, pedido, auto in ((MODO, "true", MODO_PERSONALIZADO, ""),
                                      (MODO_AUTOMATICO, "false", MODO, "sim")):
        _salvar(modo)
        for aba in ("03", "04", "05"):
            gesto = CINCO[aba][1]
            dados = _pacote(pac, aba)
            assert dados[f"{gesto}-{MODO_AUTOMATICO}"] == auto, aba
            [botao] = _botoes(dados[f"{gesto}-{monta.CAMPO_DA_EXTENSAO}"])
            assert (botao["aria-pressed"], botao["data-modo"]) == (aceso, pedido), aba


def test_desligada_a_aba_pinta_o_personalizado_e_o_perfil_guarda_o_pedido(
        lg: instalador.Lugares, pac: Any, pasta_de_perfis: pathlib.Path) -> None:
    _instalada(lg, ligada=False)
    _salvar(MODO)
    for aba in ("03", "04", "05"):
        gesto = CINCO[aba][1]
        dados = _pacote(pac, aba)
        assert dados[f"{gesto}-{monta.CAMPO_DA_EXTENSAO}"] == "", aba
        assert dados[f"{gesto}-{MODO_AUTOMATICO}"] == "", aba
    assert _modos_no_disco() == (MODO,) * 4


@pytest.mark.parametrize(("aba", "posicao"), [("02", 0), ("03", 1), ("04", 2), ("05", 3)])
def test_o_gesto_de_cada_aba_grava_o_pedido_so_na_propria_secao(
        aba: str, posicao: int, lg: instalador.Lugares, pac: Any,
        pasta_de_perfis: pathlib.Path) -> None:
    _instalada(lg)
    _salvar()
    antes = _modos_no_disco()
    pagina, gesto = CINCO[aba]
    funcao = pac.gesto_da_pagina(pagina, gesto)
    for ruim in (OUTRO, "extensao", ""):  # (noqa-acento)
        with pytest.raises(ValueError):
            funcao(_ctx(pac), {"modo": ruim, "uniq": UM}, Ponte())
    funcao(_ctx(pac), {"modo": MODO, "uniq": UM}, Ponte())
    depois = _modos_no_disco()
    assert depois[posicao] == MODO
    assert [m for i, m in enumerate(depois) if i != posicao] == [
        m for i, m in enumerate(antes) if i != posicao]
    funcao(_ctx(pac), {"modo": MODO_PERSONALIZADO, "uniq": UM}, Ponte())
    assert _modos_no_disco()[posicao] == MODO_PERSONALIZADO


def test_o_gesto_recusa_o_modo_da_extensao_desligada(
        lg: instalador.Lugares, pac: Any, pasta_de_perfis: pathlib.Path) -> None:
    _instalada(lg, ligada=False)
    _salvar()
    for pagina, gesto in CINCO.values():
        with pytest.raises(ValueError):
            pac.gesto_da_pagina(pagina, gesto)(_ctx(pac), {"modo": MODO, "uniq": UM}, Ponte())
    assert MODO not in _modos_no_disco()


def test_sem_perfil_a_luz_no_modo_da_extensao_acende_o_botao_e_volta(
        lg: instalador.Lugares, pac: Any, pasta_de_perfis: pathlib.Path) -> None:
    from pacotes import a04_iluminacao

    _instalada(lg)
    gesto = CINCO["04"][1]
    ctx = pac.Contexto(state={"active_profile": ""}, mesa=[dict(m) for m in MESA],
                       conectados=[dict(P1)], estados={})
    funcao = pac.gesto_da_pagina(CINCO["04"][0], gesto)
    funcao(ctx, {"modo": MODO, "uniq": UM}, Ponte())
    dados = dict(a04_iluminacao.pacote(ctx))
    [botao] = _botoes(dados[f"{gesto}-{monta.CAMPO_DA_EXTENSAO}"])
    assert (botao["aria-pressed"], botao["data-modo"]) == ("true", MODO_PERSONALIZADO)
    assert funcao(ctx, {"modo": MODO, "uniq": UM}, Ponte()) is None
    funcao(ctx, {"modo": MODO_PERSONALIZADO, "uniq": UM}, Ponte())
    [botao] = _botoes(dict(a04_iluminacao.pacote(ctx))[f"{gesto}-{monta.CAMPO_DA_EXTENSAO}"])
    assert (botao["aria-pressed"], botao["data-modo"]) == ("false", MODO)


def test_o_botao_da_extensao_nao_tem_margem_e_o_vao_e_o_da_fileira() -> None:
    """MORDIDA: devolva a margem ao `.modo-ext` e o vão dele ao vizinho dobra (02/11/2026)."""
    regra = re.search(r"\.modo-ext\{([^}]*)\}", monta.CSS_DO_MODO_DA_EXTENSAO)
    assert regra, "a folha perdeu a regra do botão da extensão"
    assert "margin" not in regra.group(1), (
        "o botão da extensão ganhou margem própria — o vão entre os três botões deixa de ser "
        "o mesmo")
