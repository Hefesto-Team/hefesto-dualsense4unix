"""O Status do Sistema diz o que está bem em verde e só avisa o que pede ação.

Sprint O-STATUS-DO-SISTEMA-DIZ-O-QUE-ESTA-BEM-EM-VERDE-E-SO-AVISA-O-QUE-PEDE-ACAO-01. Medido na
foto de 21/10/2026, sem controle ligado: «LIGADO» e «OK» numa pílula cinza que se lia como
desligada; os três «AVISO» em vermelho, porque `_so_o_que_a_tela_mostra` trocava todo aviso por
falha; a frase da origem do modo como aviso; o Freestyle acusado de ter perdido a regra, em texto
de programador; a ponte do prontuário em jargão e cortada no nome do jogo; duas NOTA com glifos
diferentes; e a linha do gamepad virtual sem controle nenhum.

MORDIDAS (executadas em 21/10/2026, cada uma vista reprovar e devolvida):

* `.selo.ok` de volta a `var(--texto-suave)`: `test_o_ok_e_verde_de_contorno`;
* a troca de `aviso` por `falha` de volta ao exame: `test_o_aviso_nunca_vira_falha`;
* sem o filtro `FONTES_QUE_NAO_PEDEM_ACAO`: `test_a_origem_do_modo_nao_chega_ao_status`;
* sem o `e_o_freestyle` na regra: `test_o_freestyle_nao_e_acusado`;
* a frase velha da regra ou da ponte: `test_as_frases_dizem_o_gesto_na_cabeca`;
* o «i» de volta na NOTA do exame: `test_um_glifo_por_selo`;
* a linha do gamepad de volta sem controle: `test_sem_controle_nao_ha_linha_do_gamepad`;
* sem o `longa` na linha que pede ação, ou com a linha longa na altura fixa:
  `test_a_linha_que_pede_acao_quebra_em_vez_de_cortar`.
"""

from __future__ import annotations

import pathlib
import re
from collections import defaultdict
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import daemon_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.interface import sistema as tela
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09
from hefesto_dualsense4unix.profiles.sanidade import verificar_perfis
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    Profile,
    ProfileModeConfig,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "09-sistema.html"
REGRA = "catch_all_com_cara_de_jogo"


def _estado(controles: int = 2, vpads: int = 2) -> dict[str, Any]:
    return {"controllers": [{"connected": True, "transport": "usb"} for _ in range(controles)],
            "rumble_ff": {"vpads": vpads}, "native_mode": False,
            "gamepad_emulation": {"enabled": True}}


def _exame(*vereditos: tuple[str, str]) -> dict[str, Any]:
    """Os seis do `storm_report`, todos bem, com os vereditos dados no fim."""
    base = [("[OK]", f"linha {i}") for i in range(6)]
    exame: dict[str, Any] = tela.exame([*base, *vereditos])
    return exame


def _perfil(nome: str, priority: int = 0, jogo: bool = True) -> Profile:
    return Profile(name=nome, match=MatchAny(), priority=priority,
                   leds=LedsConfig(lightbar=(0, 0, 0)),
                   mode=ProfileModeConfig(kind="gamepad") if jogo else None)


def test_o_ok_e_verde_de_contorno() -> None:
    """A peça do «Ligada»: contorno e texto no verde do tema, fundo transparente."""
    desenho = DESENHO.read_text(encoding="utf-8")
    regra = re.search(r"\.selo\.ok\{([^}]*)\}", desenho)
    assert regra, "o desenho perdeu a regra do `.selo.ok`"
    corpo = regra.group(1)
    assert "background:transparent" in corpo, corpo
    assert "color:var(--green)" in corpo, corpo
    assert "inset 0 0 0 1px var(--green)" in corpo, corpo


def test_o_aviso_nunca_vira_falha() -> None:
    """Laranja pede atenção, vermelho é a falha: o `WARN` fica aviso e o `FAIL` vira falha."""
    estado = _estado()
    exame = _exame(("[WARN]", "um aviso de outro tema"), ("[FAIL]", "uma falha de outro tema"))
    linhas = exame["linhas"]
    linhas[a09.POSICAO_NO_EXAME["steam-input"]] = tela.exame(
        [("[WARN]", "Steam Input ligado para 2 jogos")])["linhas"][0]
    saida = a09._so_o_que_a_tela_mostra(exame, [], estado)
    por_texto = {a["txt"]: a["cls"] for a in saida["linhas"]}
    assert por_texto["Steam Input ligado para 2 jogos"] == "aviso", por_texto
    assert por_texto["um aviso de outro tema"] == "aviso", por_texto
    assert por_texto["uma falha de outro tema"] == "falha", por_texto


def test_a_origem_do_modo_nao_chega_ao_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar

    origem = painel.FRASE_DA_ORIGEM_DO_MODO.format(modo="Sony DualSense")
    monkeypatch.setattr(a01_jogar, "coluna_de_atencao", lambda _c: [
        {"selo": "PERFIL", "texto": origem, "fonte": "painel.aviso_da_origem_do_modo"},
        {"selo": "JOGO", "texto": "um aviso que pede ação", "fonte": "outra"},
    ])
    ctx = Contexto(state=_estado(), mesa=[], conectados=[], estados={})
    textos = [a["txt"] for a in a09._avisos_do_produto(ctx)]
    assert textos == ["um aviso que pede ação"], textos
    nomes = {a.nome for a in painel.AVISOS_DA_TELA}
    assert set(a09.FONTES_QUE_NAO_PEDEM_ACAO) <= nomes, "o filtro aponta para fonte que não existe"


def test_o_freestyle_nao_e_acusado() -> None:
    """O Freestyle é o botão de fora do jogo: vale para qualquer janela e pede o modo de jogo."""
    for nome in ("Freestyle", "freestyle"):
        assert REGRA not in {a.regra for a in verificar_perfis([_perfil(nome)])}, nome
    assert REGRA in {a.regra for a in verificar_perfis([_perfil("pragmata")])}


@pytest.mark.parametrize("frase", [
    pytest.param(lambda: next(a.mensagem for a in verificar_perfis([_perfil("pragmata")])
                              if a.regra == REGRA), id="jogo-declarado"),
    pytest.param(lambda: next(a.mensagem for a in verificar_perfis(
        [_perfil("Sackboy", 100, jogo=False)]) if a.regra == REGRA), id="nome-de-programa"),
    pytest.param(lambda: daemon_actions.interpretar_prontuario_dos_jogos(type(
        "Censo", (), {"jogos": [type("J", (), {"nome": "Lure of Passion",
                                              "ponte_divergente": True})()]})())[1],
        id="ponte"),
])
def test_as_frases_dizem_o_gesto_na_cabeca(frase: Any) -> None:
    """A tela escreve a cabeça da frase: o nome inteiro e o gesto têm de estar nela."""
    texto = a09._sem_o_prefixo_da_cura(frase())
    cabeca = a09.frase_curta_do_exame(texto)
    assert "aba Perfis" in cabeca, cabeca
    for jargao in ("QUALQUER", "casa com", "'", "Ponte confirmada", "lista de hoje"):
        assert jargao not in texto, f"«{jargao}» em {texto!r}"
    if "Lure" in texto:
        assert "Lure of Passion" in cabeca, cabeca


def test_um_glifo_por_selo() -> None:
    """A palavra do selo tem um glifo só, venha do exame ou da linha do gamepad."""
    glifos: dict[str, set[str]] = defaultdict(set)
    for veredito in ("[OK]", "[WARN]", "[FAIL]", "[INFO]", "[NOTE]", "[?]"):
        linha = tela.exame([(veredito, "x")])["linhas"][0]
        glifos[linha["selo"]].add(linha["g"])
    for estado in (_estado(2, 2), _estado(2, 0), _estado(2, 1), None):
        linha = a09.linha_do_gamepad_por_jogador(estado)
        assert linha is not None
        glifos[linha["selo"]].add(linha["g"])
    assert all(len(g) == 1 for g in glifos.values()), dict(glifos)


def test_sem_controle_nao_ha_linha_do_gamepad() -> None:
    saida = a09._so_o_que_a_tela_mostra(_exame(), [], _estado(0, 0))
    assert all(a.get("id") != a09.ID_DO_GAMEPAD for a in saida["linhas"]), saida
    com = a09._so_o_que_a_tela_mostra(_exame(), [], _estado(2, 2))
    assert any(a.get("id") == a09.ID_DO_GAMEPAD for a in com["linhas"]), com


def test_a_linha_que_pede_acao_quebra_em_vez_de_cortar() -> None:
    aviso, ok = (tela.exame([(v, "uma frase")])["linhas"][0] for v in ("[WARN]", "[OK]"))
    assert 'class="saude longa"' in a09._linha_do_exame(aviso)
    assert "longa" not in a09._linha_do_exame(ok)
    assert 'class="saude longa"' in a09.linha_do_status({**aviso, "id": "x"})
    desenho = DESENHO.read_text(encoding="utf-8")
    assert re.search(r"\.saude\.longa \.txt span:last-child\{white-space:normal", desenho)
    # a linha cresce com a frase: na altura fixa a segunda linha invadia a de cima
    assert re.search(r"\.saude\.longa\{height:auto", desenho), "a linha longa ficou na altura fixa"
    assert 'class="saude longa"' in desenho, "o desenho não mostra o aviso que quebra"
