"""O catálogo de efeitos só tem o que funciona e é diferente, e o gatilho ganha o «Do estilo».

O usuário pediu (27/10/2026): *«ver quais efeitos funcionam e são diferentes de fato»*, e os grupos
do gatilho sem grupo de um efeito só, com o «Do estilo» no topo. Medido em 27/10: nenhum efeito sai
da lista (o único par igual, `arma-pesada`, já estava fora pelo `IGUAL_A`), e os grupos do desenho
moram agora no rótulo de cada efeito (`efeitos_de_imersao.FAMILIAS_DA_PAGINA`).

- Gatilho: o bloco de 11 bytes que cada imersão em cada acionamento manda ao aparelho difere do de
  toda outra imersão e do `Off`. Dentro da mesma imersão, dois acionamentos podem dar o mesmo
  bloco: é o mesmo efeito em dois modos, e não um repetido na lista.
- Luz: cada base de dado vivo, alimentada por um dublê do seu dado, muda de quadro, sai diferente da
  mesma base sem o dado e diferente das outras.
- A lista do produto é a do desenho aprovado, grupo por grupo, e nenhum grupo tem um efeito só.
- «Do estilo» manda ao gatilho o que o perfil dá a todos e apaga a escolha daquele controle e lado.

MORDIDAS: dar a duas imersões os mesmos ajustes faz `test_nenhuma_imersao_repete_a_outra` apontar o
par; tirar o ramo `DO_ESTILO` do gesto `imersao` reprova os casos do «Do estilo».
"""

from __future__ import annotations

import math
import pathlib
import re
import sys
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface"))

from hefesto_dualsense4unix.app.actions.trigger_specs import (
    get_spec,
    preset_to_positional_params,
)
from hefesto_dualsense4unix.core.trigger_effects import bloco_do_efeito, build_from_name, off
from hefesto_dualsense4unix.interface.monta import MODO_AUTOMATICO
from hefesto_dualsense4unix.profiles import efeitos_de_imersao as imersoes
from hefesto_dualsense4unix.profiles import efeitos_de_luz as luz

DESENHO = RAIZ / "mockup" / "03-gatilhos.html"
UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"
PERFIL = "Régua do estilo"
RECEITA = {"mode": "Machine", "params": [1, 9, 6, 20]}
DELA = {"mode": "Rigid", "params": [2, 200]}


def _blocos(ajustes: Any) -> dict[bytes, set[str]]:
    """Bloco de 11 bytes → as imersões que o mandam ao aparelho."""
    por_bloco: dict[bytes, set[str]] = defaultdict(set)
    for imersao, modo, _estilo, aj in ajustes:
        spec = get_spec(modo)
        assert spec is not None, modo
        pos = preset_to_positional_params(spec, aj)
        por_bloco[bloco_do_efeito(build_from_name(modo, list(pos)))].add(imersao.chave)
    return por_bloco


def _repetidas(ajustes: Any) -> list[str]:
    """Os blocos que duas imersões diferentes mandam, ou que são o `Off`."""
    vazio = bloco_do_efeito(off())
    fora = []
    for bloco, chaves in _blocos(ajustes).items():
        if bloco == vazio:
            fora.append(f"{sorted(chaves)} manda o Off ({bloco.hex()})")
        elif len(chaves) > 1:
            fora.append(f"{sorted(chaves)} mandam o mesmo bloco ({bloco.hex()})")
    return sorted(fora)


def test_nenhuma_imersao_repete_a_outra_nem_e_o_off() -> None:
    repetidas = _repetidas(imersoes.todos_os_ajustes())
    assert not repetidas, (
        "efeito que não é diferente sai da lista: ponha a chave dele no IGUAL_A, apontando para o "
        "mais próximo\n  " + "\n  ".join(repetidas))


def test_a_regua_aponta_o_par_quando_duas_imersoes_tem_os_mesmos_ajustes() -> None:
    itens = list(imersoes.todos_os_ajustes())
    primeiro, outro = itens[0], next(i for i in itens if i[0].chave != itens[0][0].chave)
    copia = (outro[0], primeiro[1], primeiro[2], primeiro[3])
    repetidas = _repetidas([*itens, copia])
    assert any(primeiro[0].chave in r and outro[0].chave in r for r in repetidas), repetidas


def test_o_que_saiu_da_lista_aponta_para_quem_ficou() -> None:
    for saiu, ficou in imersoes.IGUAL_A.items():
        assert saiu in imersoes.POR_CHAVE and ficou in imersoes.POR_CHAVE, (saiu, ficou)
        assert ficou not in imersoes.IGUAL_A, f"{ficou!r} também saiu da lista"


CORES = ((255, 0, 0), (0, 0, 255))
O_DADO_E_A_SEMENTE = frozenset({"estrelas"})


def _com_o_dado(k: int) -> Any:
    """O dublê de todo dado vivo, mudando a cada quadro."""
    t = k / 30
    return luz.Entrada(
        apertos={"cross": k // 20, "dpad_up": k // 33},
        gravidade=(math.sin(t), 0.2, math.cos(t)),
        dedo=((k % 50) / 50, (k % 37) / 37) if k % 60 < 45 else None,
        som=(abs(math.sin(t * 3)), (k % 40) / 40),
        carga=(100 - k // 3, "descarregando" if k < 100 else "carregando"),
        calor=(k % 200) / 200)


def _sequencia(base: str, entrada: Any, semente: int = 7) -> tuple[Any, ...]:
    from hefesto_dualsense4unix.profiles.schema import EfeitoDaLuz

    estado = luz.estado_da_mao(EfeitoDaLuz(base, CORES, 5), semente=semente)
    assert estado is not None, f"a base {base!r} de dado vivo não tem estado"
    quadros = []
    for k in range(200):
        agora = k / 30
        q = (estado.quadro(entrada(k), agora) if hasattr(estado, "quadro")
             else estado.andar(entrada(k), agora))
        quadros.append((q.cor, q.luzinhas) if isinstance(q, luz.Quadro) else (q, None))
    return tuple(quadros)


@pytest.fixture(scope="module")
def sequencias() -> dict[str, tuple[Any, ...]]:
    return {b: _sequencia(b, _com_o_dado) for b in sorted(luz.BASES_DE_DADO_VIVO)}


def test_cada_luz_de_dado_vivo_muda_com_o_dado_e_nao_e_a_parada(
        sequencias: dict[str, tuple[Any, ...]]) -> None:
    """As Estrelas cintilam pela semente do controle, e não pela mão: o dado delas é a semente."""
    for base, seq in sequencias.items():
        assert len(set(seq)) > 1, f"a luz {base!r} fica num quadro só com o dado mudando"
        sem_o_dado = (_sequencia(base, _com_o_dado, semente=8) if base in O_DADO_E_A_SEMENTE
                      else _sequencia(base, lambda _k: luz.Entrada()))
        assert seq != sem_o_dado, f"a luz {base!r} não muda com o dado dela"


def test_nenhuma_luz_de_dado_vivo_repete_a_outra(sequencias: dict[str, tuple[Any, ...]]) -> None:
    bases = list(sequencias)
    iguais = [(a, b) for i, a in enumerate(bases) for b in bases[i + 1:]
              if sequencias[a] == sequencias[b]]
    assert not iguais, f"bases de luz que dão a mesma sequência: {iguais}"


def _grupos(lista: str) -> dict[str, set[str]]:
    from pacotes.a03_gatilhos import SEUS_EFEITOS

    return {g: set(re.findall(r'<option value="([^"]+)"', dentro))
            for g, dentro in re.findall(r'<optgroup label="([^"]+)">(.*?)</optgroup>', lista, re.S)
            if g != SEUS_EFEITOS}


def _primeira_lista_do_desenho() -> str:
    doc = DESENHO.read_text(encoding="utf-8")
    achada = re.search(r'<select class="g2-imersao"[^>]*>(.*?)</select>', doc, re.S)
    assert achada, "o desenho perdeu a lista do efeito do gatilho"
    return achada.group(1)


def test_a_lista_do_produto_e_a_do_desenho_grupo_por_grupo() -> None:
    from pacotes.a03_gatilhos import DO_ESTILO, ROTULO_DO_ESTILO, html_das_opcoes_de_imersao

    produto, desenho = html_das_opcoes_de_imersao(), _primeira_lista_do_desenho()
    assert list(_grupos(produto)) == list(imersoes.FAMILIAS_DA_PAGINA), _grupos(produto)
    assert _grupos(produto) == _grupos(desenho), "a lista do produto não é a do desenho aprovado"
    sozinhos = {g: v for g, v in _grupos(produto).items() if len(v) < 2}
    assert not sozinhos, f"grupo com um efeito só: {sozinhos}"
    for lista in (produto, desenho):
        visiveis = re.findall(r'<option value="([^"]+)"(?! disabled)', lista)
        assert visiveis[0] == DO_ESTILO, f"a lista não abre com «{ROTULO_DO_ESTILO}»: {visiveis}"


def test_todo_efeito_da_lista_esta_no_grupo_do_rotulo_dele() -> None:
    from pacotes.a03_gatilhos import html_das_opcoes_de_imersao

    for grupo, chaves in _grupos(html_das_opcoes_de_imersao()).items():
        for chave in chaves:
            assert imersoes.familia_da_pagina(imersoes.POR_CHAVE[chave]) == grupo, (chave, grupo)


class _Ponte:
    def __init__(self) -> None:
        self.enviados: list[tuple[str, str, list[int]]] = []
        self.chamadas: list[str] = []

    def _ok(self) -> tuple[bool, str, dict[str, Any]]:
        return True, "", {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}

    def trigger_set_detalhado(self, lado: str, modo: str, params: list[int],
                              uniq: str = "") -> Any:
        self.enviados.append((lado, modo, list(params)))
        return self._ok()

    def trigger_reset_detalhado(self, lado: str, uniq: str = "") -> Any:
        self.enviados.append((lado, "Off", []))
        return self._ok()

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append(metodo)
        return True


@pytest.fixture
def a03() -> Iterator[Any]:
    import pacotes  # noqa: F401
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch, a03: Any) -> tuple[dict[str, Any], list[Any]]:
    """O perfil com estilo: a receita no global, e o L2 e o R2 escolhidos naquele controle."""
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    prof = Profile.model_validate({
        "name": PERFIL, "match": {"type": "any"}, "estilo": "fps",
        "triggers": {"left": RECEITA, "right": RECEITA},
        "controllers": {CHAVE: {"triggers": {"left": DELA, "right": DELA}}},
    })
    estado = {PERFIL: prof}
    gravados: list[Any] = []

    def _grava(novo: Any, **_: Any) -> None:
        gravados.append(novo)
        estado[novo.name] = novo

    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n], raising=False)
    monkeypatch.setattr(loader, "save_profile", _grava, raising=False)
    monkeypatch.setattr(a03.perfil, "ativo",
                        lambda *_a, **_k: loader._payload_do_perfil(estado[PERFIL]))
    monkeypatch.setattr(a03.perfil, "ativo_que_vale",
                        lambda *_a, **_k: loader._payload_do_perfil(estado[PERFIL]))
    return estado, gravados


def _ctx() -> Any:
    from pacotes import Contexto

    dele = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True}
    mesa = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua", "via": "USB",
             "cor": "starlight-blue", "mascara": "DualSense"}]
    return Contexto(state={"active_profile": PERFIL}, mesa=mesa, conectados=[dele], estados={})


def _clicar(valor: str, lado: str, ponte: _Ponte) -> Any:
    from pacotes import gesto_da_pagina

    gesto = gesto_da_pagina("03-gatilhos.html", "imersao")
    assert gesto is not None
    return gesto(_ctx(), {"uniq": UNIQ, "lado": lado, "valor": valor}, ponte)


def _pintado(a03: Any, sig: str) -> str:
    return str(a03.pacote(_ctx())["colunas"][UNIQ][f"{a03.CAMPO_DA_IMERSAO}-{sig}"])


def test_do_estilo_manda_a_receita_e_apaga_a_escolha_daquele_lado(a03: Any, disco: Any) -> None:
    estado, gravados = disco
    ponte = _Ponte()
    _clicar(a03.DO_ESTILO, "e", ponte)

    assert ponte.enviados == [("left", RECEITA["mode"], RECEITA["params"])], (
        f"o gatilho não recebeu a receita do estilo: {ponte.enviados}")
    assert len(gravados) == 1, "a escolha do controle não saiu do perfil"
    seus = estado[PERFIL].controllers[CHAVE].triggers
    assert "left" not in seus.model_fields_set, "o L2 daquele controle continua escolhido"
    assert seus.right.mode == DELA["mode"], "o «Do estilo» do L2 apagou o R2"
    assert a03._do_rascunho(UNIQ, "left") is None, "a sessão segura o efeito de antes"


def test_os_dois_lados_no_estilo_tiram_o_gatilho_do_controle(a03: Any, disco: Any) -> None:
    estado, _ = disco
    _clicar(a03.DO_ESTILO, "e", _Ponte())
    _clicar(a03.DO_ESTILO, "d", _Ponte())
    assert CHAVE not in (estado[PERFIL].controllers or {}), (
        "o controle sem nada escrito continua no perfil")


def test_o_pacote_pinta_do_estilo_so_no_lado_sem_escolha(a03: Any, disco: Any) -> None:
    assert _pintado(a03, "e") != a03.DO_ESTILO, "o L2 escolhido pintou «Do estilo»"
    _clicar(a03.DO_ESTILO, "e", _Ponte())
    assert _pintado(a03, "e") == a03.DO_ESTILO
    assert _pintado(a03, "d") != a03.DO_ESTILO
    _clicar(imersoes.IMERSOES[0].chave, "e", _Ponte())
    assert _pintado(a03, "e") == imersoes.IMERSOES[0].chave


def test_sem_estilo_e_no_automatico_o_lado_nao_pinta_do_estilo(a03: Any) -> None:
    assert not a03._a_escolha_e_do_estilo({"triggers": {}}, UNIQ, "left")
    assert not a03._a_escolha_e_do_estilo(
        {"estilo": "fps", "triggers": {"modo": MODO_AUTOMATICO}}, UNIQ, "left")
    assert a03._a_escolha_e_do_estilo({"estilo": "fps", "triggers": {}}, UNIQ, "left")


def test_do_estilo_respeita_o_modo_automatico(a03: Any, disco: Any) -> None:
    estado, gravados = disco
    estado[PERFIL] = estado[PERFIL].model_copy(update={
        "triggers": estado[PERFIL].triggers.model_copy(update={"modo": MODO_AUTOMATICO})})
    ponte = _Ponte()
    with pytest.raises(RuntimeError):
        _clicar(a03.DO_ESTILO, "e", ponte)
    assert ponte.enviados == [] and gravados == []
