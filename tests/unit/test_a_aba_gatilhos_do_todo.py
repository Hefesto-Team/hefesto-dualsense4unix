"""A aba Gatilhos do todo: os efeitos de imersão (dado) e a tela que os oferece.

MORDIDAS: pôr a pane com força 9, repetir os números de duas imersões, ou sobrar
uma família sem as três imersões reprova.
"""

from __future__ import annotations

from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS, get_spec
from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import TETO_POR_CONTROLE
from hefesto_dualsense4unix.profiles import efeitos_de_imersao as imersao
from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE

FAIXAS = {s.name: {p.name: (p.min_value, p.max_value) for p in s.params} for s in PRESETS}
PADROES = {s.name: {p.name: p.default for p in s.params} for s in PRESETS}


def _dentro_da_faixa(modo: str, ajustes: dict[str, int]) -> list[str]:
    erros = []
    for nome, valor in ajustes.items():
        if nome not in FAIXAS.get(modo, {}):
            erros.append(f"{modo}.{nome} não existe no PRESETS")
            continue
        lo, hi = FAIXAS[modo][nome]
        if not lo <= valor <= hi:
            erros.append(f"{modo}.{nome}={valor} fora de {lo}..{hi}")
    return erros


def test_cada_familia_tem_tres_imersoes_e_cada_modo_dela_as_tres() -> None:
    for familia, modos in imersao.FAMILIAS.items():
        delas = [i for i in imersao.IMERSOES if i.familia == familia]
        assert len(delas) == 3, (familia, [i.chave for i in delas])
        for modo in modos:
            assert get_spec(modo) is not None, f"{modo} não é modo do PRESETS"
            assert len(imersao.imersoes_do_acionamento(modo)) == 3, (familia, modo)


def test_todo_numero_esta_dentro_da_faixa_do_presets() -> None:
    erros: list[str] = []
    for i, modo, estilo, ajustes in imersao.todos_os_ajustes():
        erros += [f"{i.chave}/{estilo or 'base'}: {e}" for e in _dentro_da_faixa(modo, ajustes)]
        assert estilo == "" or estilo in POR_CHAVE, f"{i.chave}: estilo {estilo!r} não existe"
    for i in imersao.IMERSOES:
        for m in i.momentos:
            erros += [f"{i.chave} momento: {e}" for e in _dentro_da_faixa(m.modo, dict(m.ajustes))]
            assert not m.valem_em or set(m.valem_em) <= set(imersao.FAMILIAS[i.familia])
        for estilo in (*i.na_frente, *i.variantes):
            assert estilo in POR_CHAVE, f"{i.chave}: estilo {estilo!r} não existe"
    assert not erros, erros


def test_nenhum_momento_passa_do_teto_de_escritas_do_motor() -> None:
    for i in imersao.IMERSOES:
        for m in i.momentos:
            if m.a_cada_ms:
                assert 1000 / m.a_cada_ms <= TETO_POR_CONTROLE, (i.chave, m.a_cada_ms)
            assert m.apos_ms >= 0 and (m.dura_ms is None or m.dura_ms > 0), i.chave


def test_os_numeros_de_cada_imersao_so_se_repetem_nela_mesma() -> None:
    """A tela reconhece a imersão pelos números: dois iguais seriam a mesma opção."""
    vistos: dict[tuple[str, tuple[tuple[str, int], ...]], str] = {}
    for i, modo, estilo, ajustes in imersao.todos_os_ajustes():
        cheio = {**PADROES[modo], **ajustes}
        assert cheio != PADROES[modo], f"{i.chave}/{modo} é igual ao padrão do modo"
        chave = (modo, tuple(sorted(cheio.items())))
        dono = vistos.setdefault(chave, i.chave)
        assert dono == i.chave, f"{i.chave}/{modo}/{estilo or 'base'} repete {dono}"


def test_a_ordem_com_estilo_poe_as_dele_na_frente() -> None:
    sem = [i.chave for i in imersao.imersoes_do_acionamento("SemiAutoGun")]
    com = [i.chave for i in imersao.imersoes_do_acionamento("SemiAutoGun", "terror")]
    assert sem == ["ferrolho-que-volta", "trava-seca", "pino-que-falha"]
    assert com[0] == "pino-que-falha" and sorted(com) == sorted(sem)
    assert imersao.imersoes_do_acionamento("Off") == ()
