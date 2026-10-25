"""A opção da extensão só aparece quando a outra a pede.

A-OPCAO-DA-EXTENSAO-SO-APARECE-QUANDO-A-OUTRA-A-PEDE-01 (25/10/2026). A opção do manifesto
ganha ``aparece_com: {id: valor}`` (o valor de uma ``escolha``, ou a lista dos que servem, ou o
``true``/``false`` de um ``ligado``); a janela da extensão desenha só a opção cuja condição vale, e
a mostra no mesmo gesto em que a outra muda. Esconder é só da tela: o valor guardado fica.

MORDIDAS (25/10/2026, executadas sobre a cura e devolvidas):

- a janela sem o filtro do ``aparece_com`` reprova os testes da janela e o do WebKit;
- o ``_vale`` que aceita todo valor reprova a janela e o ``aparecem``;
- o ``aparecem`` que não olha se a outra também aparece reprova a escondida em cadeia;
- cada recusa do manifesto arrancada reprova o caso dela em ``test_o_manifesto_recusa``.
- o campo sem a conferência do valor cru aceita o ``1`` como ``true`` e reprova ``ligado-com-1``.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import ctx, lar  # noqa: F401
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _manifesto,
    _Ponte,
    janela,
)

USB, REDE = "Adaptador USB", "Servidor na rede"
LIGACAO: dict[str, Any] = {
    "id": "ligacao", "rotulo": "Ligação por", "tipo": "escolha",  # noqa-acento: chave
    "escolhas": [USB, REDE], "padrao": USB}  # noqa-acento: chave do manifesto
SERVIDOR: dict[str, Any] = {
    "id": "servidor", "rotulo": "Endereço do servidor", "tipo": "endereco",
    "padrao": "127.0.0.1:12345", "aparece_com": {"ligacao": REDE}}  # noqa-acento: chave do manifesto
SEGURO: dict[str, Any] = {
    "id": "seguro", "rotulo": "Ligação segura", "tipo": "ligado",  # noqa-acento: chave
    "padrao": False, "aparece_com": {"ligacao": [REDE]}}  # noqa-acento: chave do manifesto
PORTA_SEGURA: dict[str, Any] = {
    "id": "porta-segura", "rotulo": "Endereço seguro", "tipo": "endereco",
    "padrao": "", "aparece_com": {"seguro": True}}  # noqa-acento: chave do manifesto
TELEFONE: dict[str, Any] = {"id": "telefone", "rotulo": "Telefone", "tipo": "ligado",
                            "padrao": False}  # noqa-acento: chave do manifesto
DO_TELEFONE: dict[str, Any] = {
    "id": "endereco-do-telefone", "rotulo": "Endereço do telefone", "tipo": "endereco",
    "padrao": "", "aparece_com": {"telefone": True}}  # noqa-acento: chave do manifesto


def _opcoes(*extras: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(o) for o in (LIGACAO, SERVIDOR, SEGURO, PORTA_SEGURA, TELEFONE, DO_TELEFONE,
                              *extras)]


def _linhas(html: str) -> set[str]:
    """As opções que a janela desenhou, pelo ``data-v`` do controle de cada uma."""
    return set(re.findall(r'data-gesto="guardar-opcao-da-modificacao" data-v="toque:([^":]+)',
                          html))


# -- 1. o manifesto ---------------------------------------------------------------------------


def test_o_manifesto_aceita_o_aparece_com_de_escolha_lista_e_ligado() -> None:
    m = Manifesto.model_validate(_manifesto(opcoes=_opcoes()))  # noqa-acento: chave
    por_id = {o.id: o for o in m.opcoes}
    assert por_id["servidor"].aparece_com == {"ligacao": REDE}
    assert por_id["seguro"].aparece_com == {"ligacao": [REDE]}
    assert por_id["porta-segura"].aparece_com == {"seguro": True}
    assert por_id["ligacao"].aparece_com is None, "a opção sem o campo segue sem ele"


def _com(opcao_id: str, aparece_com: Any) -> list[dict[str, Any]]:
    todas = _opcoes()
    next(o for o in todas if o["id"] == opcao_id)["aparece_com"] = aparece_com
    return todas


@pytest.mark.parametrize(("declaradas", "frase"), [
    (_com("servidor", {"inventada": REDE}),
     "a opção servidor aparece com 'inventada', que não existe"),
    (_com("servidor", {"servidor": REDE}), "a opção servidor aparece com ela mesma"),
    (_com("ligacao", {"seguro": True}), "a opção ligacao fecha um ciclo de aparece_com"),
    (_com("servidor", {"ligacao": "Bluetooth"}),
     "a opção servidor aparece com 'ligacao' valendo 'Bluetooth', que não é escolha"),
    (_com("servidor", {"ligacao": [REDE, "Bluetooth"]}),
     "a opção servidor aparece com 'ligacao' valendo"),
    (_com("servidor", {"ligacao": []}), "a opção servidor aparece com 'ligacao' valendo"),
    (_com("endereco-do-telefone", {"telefone": "sim"}),
     "a opção endereco-do-telefone aparece com 'telefone', que é ligado: true ou false"),
    (_com("endereco-do-telefone", {"telefone": 1}),
     "a opção endereco-do-telefone aparece com 'telefone' valendo 1"),
    (_com("servidor", {"ligacao": [REDE, 2]}), "a opção servidor aparece com 'ligacao' valendo"),
    (_com("telefone", {"servidor": "127.0.0.1:12345"}),
     "a opção telefone aparece com 'servidor', que não é escolha nem ligado"),
    (_com("servidor", {}), "o aparece_com de servidor está vazio"),
    (_opcoes({"id": "ao-vivo", "rotulo": "Ao vivo", "tipo": "livre",
              "aparece_com": {"telefone": True}}),
     "o livre ao-vivo mora na faixa de baixo e não declara aparece_com"),
], ids=["nao-existe", "ela-mesma", "ciclo", "valor-fora", "lista-com-um-fora", "lista-vazia",
        "ligado-sem-bool", "ligado-com-1", "lista-com-numero", "alvo-de-outro-tipo", "vazio",
        "livre"])
def test_o_manifesto_recusa(declaradas: list[dict[str, Any]], frase: str) -> None:
    # D-2510-O-APARECE-COM-NAO-CONVERTE-O-1-EM-TRUE
    """Cada recusa diz o id da opção que a causou."""
    with pytest.raises(ValidationError, match=re.escape(frase)):
        Manifesto.model_validate(_manifesto(opcoes=declaradas))  # noqa-acento: chave


def test_o_ciclo_longo_tambem_se_recusa() -> None:
    todas = _com("ligacao", {"telefone": True})
    next(o for o in todas if o["id"] == "telefone")["aparece_com"] = {"seguro": False}
    with pytest.raises(ValidationError, match="fecha um ciclo de aparece_com"):
        Manifesto.model_validate(_manifesto(opcoes=todas))  # noqa-acento: chave


# -- 2. quem aparece ---------------------------------------------------------------------------


@pytest.mark.parametrize(("valores", "esperadas"), [
    ({"ligacao": USB, "seguro": True, "telefone": False}, {"ligacao", "telefone"}),
    ({"ligacao": REDE, "seguro": False, "telefone": False},
     {"ligacao", "telefone", "servidor", "seguro"}),
    ({"ligacao": REDE, "seguro": True, "telefone": True},
     {"ligacao", "telefone", "servidor", "seguro", "porta-segura", "endereco-do-telefone"}),
    # o «seguro» guardado ligado não mostra o filho enquanto ele mesmo está escondido
    ({"ligacao": USB, "seguro": True, "telefone": True},
     {"ligacao", "telefone", "endereco-do-telefone"}),
    # o ligado pede o booleano: o 1 guardado à mão não é o true
    ({"ligacao": USB, "seguro": False, "telefone": 1}, {"ligacao", "telefone"}),
], ids=["usb", "rede", "rede-tudo-ligado", "pai-escondido", "um-nao-e-true"])
def test_aparecem_pelos_valores(valores: dict[str, Any], esperadas: set[str]) -> None:
    from hefesto_dualsense4unix.mods import opcoes

    m = Manifesto.model_validate(_manifesto(opcoes=_opcoes()))  # noqa-acento: chave
    assert opcoes.aparecem(m, valores) == esperadas


# -- 3. a janela --------------------------------------------------------------------------------


def _mudar(a07: Any, ctx: Any, ponte: _Ponte, opcao: str, valor: Any = None) -> str:  # noqa: F811
    """O gesto da janela: o ``change`` da caixa, ou o clique na chave do ligado."""
    clique = {"v": f"toque:{opcao}", "evento": "click" if valor is None else "change"}
    if valor is not None:
        clique["valor"] = valor
    carga = a07.guardar_opcao_da_modificacao(ctx, clique, ponte)
    return str(carga["blocos"]["#mod-janela"])


def test_a_janela_mostra_o_dependente_na_hora_e_esconde_sem_apagar(
        janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    # D-2510-A-OPCAO-APARECE-QUANDO-A-OUTRA-A-PEDE
    """«Adaptador USB» esconde o servidor; «Servidor na rede» o mostra no mesmo gesto; a volta o
    esconde de novo, e o endereço escrito nele continua guardado depois do Guardar."""
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    a07, instalar, abrir = janela
    instalar(opcoes=_opcoes())  # noqa-acento: chave
    ponte = _Ponte(VIVO)
    aberta = _linhas(abrir(ponte)["blocos"]["#mod-janela"])
    assert aberta == {"ligacao", "telefone"}, f"com USB, o que não vale apareceu: {aberta}"

    assert _linhas(_mudar(a07, ctx, ponte, "ligacao", REDE)) == {
        "ligacao", "telefone", "servidor", "seguro"}, "o servidor não apareceu na hora"
    _mudar(a07, ctx, ponte, "servidor", "10.0.0.2:9000")
    assert "porta-segura" in _linhas(_mudar(a07, ctx, ponte, "seguro")), "o ligado não mostrou"
    assert "endereco-do-telefone" in _linhas(_mudar(a07, ctx, ponte, "telefone"))

    volta = _linhas(_mudar(a07, ctx, ponte, "ligacao", USB))
    assert volta == {"ligacao", "telefone", "endereco-do-telefone"}, (
        f"a volta ao USB deixou o servidor (ou o filho dele) na tela: {volta}")
    assert "endereco-do-telefone" not in _linhas(_mudar(a07, ctx, ponte, "telefone"))

    a07.guardar_modificacao(ctx, {"v": "toque"}, ponte)
    guardados: Any = opcoes.ler(manifesto_instalado("toque", lugares=lar), lar)
    assert guardados["servidor"] == "10.0.0.2:9000", "esconder apagou o endereço guardado"
    assert guardados["seguro"] is True and guardados["ligacao"] == USB


def test_a_janela_reaberta_le_o_guardado(janela: Any, ctx: Any) -> None:  # noqa: F811
    """A condição vale pelo valor guardado, não só pelo rascunho: reabrir a janela com «Servidor
    na rede» guardado mostra o servidor."""
    a07, instalar, abrir = janela
    instalar(opcoes=_opcoes())  # noqa-acento: chave
    ponte = _Ponte(VIVO)
    abrir(ponte)
    _mudar(a07, ctx, ponte, "ligacao", REDE)
    a07.guardar_modificacao(ctx, {"v": "toque"}, ponte)
    a07._MEXIDA.limpar()
    assert "servidor" in _linhas(abrir(ponte)["blocos"]["#mod-janela"])


# -- 4. no WebKit ---------------------------------------------------------------------------------

_VER = """(function(h){
  const j = document.getElementById('mod-janela');
  j.innerHTML = h;
  location.hash = '#' + j.closest('.tela-nova').id;
  const vista = el => { const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
  const ids = [...j.querySelectorAll('[data-gesto="guardar-opcao-da-modificacao"]')]
    .filter(vista).map(el => el.dataset.v.split(':')[1]);
  return JSON.stringify([...new Set(ids)].sort());
})(%s)"""


def test_no_webkit_o_servidor_so_aparece_com_a_rede(janela: Any, ctx: Any) -> None:  # noqa: F811
    """O HTML que a janela desenhou com USB e depois com «Servidor na rede», posto no desenho dentro
    de um WebKit de verdade: o que se lê é o que aparece na tela, não o texto."""
    import json

    from tests.unit.test_o_aparelho_da_extensao_diz_os_controles_dele import VISTAS, rodar_no_webkit

    a07, instalar, abrir = janela
    instalar(opcoes=_opcoes())  # noqa-acento: chave
    ponte = _Ponte(VIVO)
    feitas = [abrir(ponte)["blocos"]["#mod-janela"], _mudar(a07, ctx, ponte, "ligacao", REDE),
              _mudar(a07, ctx, ponte, "ligacao", USB)]
    w, h = VISTAS[1]
    lidos = rodar_no_webkit({"janela": (w, h, [["js", _VER % json.dumps(x)] for x in feitas])})
    usb, rede, volta = (json.loads(x) for x in lidos["janela"])
    assert usb == ["ligacao", "telefone"], f"com USB, o WebKit mostrou: {usb}"
    assert rede == ["ligacao", "seguro", "servidor", "telefone"], f"com a rede: {rede}"
    assert volta == usb, f"a volta ao USB deixou na tela: {volta}"
