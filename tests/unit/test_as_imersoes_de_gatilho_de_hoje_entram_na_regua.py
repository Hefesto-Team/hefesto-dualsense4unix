"""As imersões de gatilho de hoje entram na régua da Metralhadora
(AS-IMERSOES-DE-GATILHO-DE-HOJE-ENTRAM-NA-REGUA-DA-METRALHADORA-01).

Cada uma das dezoito sai no acionamento oficial da lista de onze, com o bloco da tabela do
catálogo; nenhuma repete o mesmo bloco por `a_cada_ms`; nenhuma pede uma frequência que o rádio
não entrega limpa; os números de ontem seguem abrindo a imersão de hoje; e o motor toca os
momentos nos dois primeiros controles sem escrever o mesmo bloco duas vezes seguidas.

MORDIDAS (cada uma reprova o teste que a nomeia, e o arquivo volta idêntico):
devolver o `a_cada_ms` à Rajada reprova `test_nenhuma_imersao_repete_o_bloco_por_a_cada_ms`;
voltar a frequência do Cano a 60 Hz reprova `test_nenhuma_frequencia_cai_fora_do_divisor_limpo`;
baixar a força da Trava seca de 255 para 200 reprova `test_cada_imersao_sai_com_o_bloco_da_tabela`;
tirar uma linha de `NUMEROS_DE_ONTEM` reprova `test_os_numeros_de_ontem_abrem_a_imersao_de_hoje`.
"""
from __future__ import annotations

from itertools import pairwise

import pytest

from hefesto_dualsense4unix.app.actions.trigger_specs import (
    PRESETS,
    get_spec,
    preset_to_positional_params,
)
from hefesto_dualsense4unix.core.trigger_effects import (
    build_from_name,
    frequencia_limpa,
    traduzir_chave_velha,
)
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import efeitos_de_imersao as ei
from tests.unit.test_os_momentos_da_imersao_tocam_no_gatilho import (
    P1,
    P2,
    _mesa,
    _perfil,
)

BLOCOS: dict[tuple[str, str, str], str] = {
    ("ferrolho-que-volta", "Weapon", ""): "2544000600000000",
    ("trava-seca", "Weapon", ""): "250c000700000000",
    ("pino-que-falha", "Weapon", ""): "2588000600000000",
    ("batida-do-coracao", "Weapon", ""): "2544000400000000",
    ("arma-pesada", "Weapon", ""): "2504010700000000",
    ("aperto-que-trava", "Weapon", ""): "2508010600000000",
    ("rajada-que-sobe-sozinha", "Machine", ""): "26ff03dbb66d1b28",
    ("cano-que-esquenta", "Machine", ""): "26ff036ddbb62d14",
    ("recuo-pesado", "Machine", ""): "26ff03ffffff3f06",
    ("corda-que-estica", "Bow", ""): "260008e0c0000000",
    ("flecha-que-escapa", "Bow", ""): "260208c0e0000000",
    ("braco-cansado", "Bow", ""): "260109a0a0000000",
    ("freio-abs-que-pulsa", "Resistance", ""): "21fc0340dbb62d00",
    ("pedal-duro", "Resistance", ""): "21fe03f8ffff3f00",
    ("porta-emperrada", "MultiPositionFeedback", ""): "21a802008aa22800",
    ("galope-no-chao", "Galloping", ""): "2600090603060000",
    ("motor-que-sobe", "Galloping", ""): "26000905050c0000",
    ("terreno-que-muda", "Galloping", ""): "2601080406100000",
}

DICAS = {
    "ferrolho-que-volta": "O gatilho rearma sozinho a cada tiro, firme e curto.",
    "trava-seca": "Pouco curso e muita resistência, como arma sem munição.",
    "pino-que-falha": "O disparo fica fundo e duro, e emperra meio segundo a cada aperto.",
    "batida-do-coracao": "Um pulso médio no meio do curso.",
    "arma-pesada": "Um disparo duro e fundo a cada aperto.",
    "aperto-que-trava": "O gatilho trava um instante no fundo a cada aperto.",
    "rajada-que-sobe-sozinha":
        "As batidas começam médias e ficam mais fortes a cada meio segundo segurando.",
    "cano-que-esquenta":
        "Batidas rápidas e fortes que ficam lentas e pesadas depois de 3 s segurando.",
    "recuo-pesado": "Solavancos espaçados e fortes, como arma de calibre grande.",
    "corda-que-estica": "A corda começa leve e pesa mais a cada meio segundo segurando.",
    "flecha-que-escapa": "O estalo da soltura chega seco, no fim do curso.",
    "braco-cansado":
        "A corda pesa menos e solta branda, e o braço treme depois de 3 s segurando.",
    "freio-abs-que-pulsa":
        "Resistência firme no começo, e o pedal pulsa depois de um instante segurando.",
    "pedal-duro": "A resistência começa cedo e fica forte, como pedal duro.",
    "porta-emperrada": "O gatilho range em degraus, como porta enferrujada.",
    "galope-no-chao": "Patas lentas e baixas, só se sentem devagar.",
    "motor-que-sobe":
        "Passadas iguais que aceleram enquanto você segura, como um motor girando.",
    "terreno-que-muda": "Passadas desiguais, uma fraca e uma forte, como piso irregular.",
}

ONZE = {s.name for s in PRESETS}
CHAVES_QUE_SAIRAM = {"Rigid", "SimpleRigid", "Feedback", "SemiAutoGun", "AutoGun", "Pulse",
                     "PulseA", "PulseB", "Machine gun"}


def _bytes(modo: str, ajustes: dict[str, int]) -> str:
    spec = get_spec(modo)
    padroes = {p.name: p.default for p in spec.params} if spec is not None else {}
    efeito = build_from_name(modo, {**padroes, **ajustes})
    return bytes([efeito.mode, *efeito.forces]).hex()[:16]


def test_as_dezoito_ficam_e_so_usam_os_onze_acionamentos() -> None:
    assert set(DICAS) <= {i.chave for i in ei.IMERSOES}
    assert len(DICAS) == 18
    assert "pulso" not in ei.FAMILIAS
    for modos in ei.FAMILIAS.values():
        assert set(modos) <= ONZE and not set(modos) & CHAVES_QUE_SAIRAM
    for imersao, modo, _estilo, _ajustes in ei.todos_os_ajustes():
        assert modo in ONZE and modo in ei.FAMILIAS[imersao.familia], (imersao.chave, modo)
        for m in imersao.momentos:
            assert m.modo in ONZE, (imersao.chave, m.modo)


def test_cada_imersao_sai_com_o_bloco_da_tabela() -> None:
    for imersao, modo, estilo, ajustes in ei.todos_os_ajustes():
        if (imersao.chave, modo, estilo) in BLOCOS:
            assert _bytes(modo, ajustes) == BLOCOS[(imersao.chave, modo, estilo)], (
                imersao.chave, modo)
    visto = {(i.chave, m, e) for i, m, e, _a in ei.todos_os_ajustes()}
    assert set(BLOCOS) <= visto, set(BLOCOS) - visto


def test_as_dicas_dizem_o_que_se_sente_e_os_dois_nomes_novos_estao() -> None:
    for chave, dica in DICAS.items():
        assert ei.POR_CHAVE[chave].dica == dica, chave
    assert ei.POR_CHAVE["corda-que-estica"].rotulo == "Carga · estica"
    assert ei.POR_CHAVE["pedal-duro"].rotulo == "Peso · pedal"
    assert "corda-que-treme-no-fim" not in ei.POR_CHAVE
    assert "pedal-no-fundo" not in ei.POR_CHAVE


def test_nenhuma_imersao_repete_o_bloco_por_a_cada_ms() -> None:
    for imersao in ei.IMERSOES:
        for m in imersao.momentos:
            assert m.a_cada_ms is None, (imersao.chave, m)
    degraus = [m.ajustes["strength"] for m in ei.POR_CHAVE["rajada-que-sobe-sozinha"].momentos
               if m.modo == "Machine"]
    assert degraus == [5, 6, 7]


def test_nenhuma_frequencia_cai_fora_do_divisor_limpo() -> None:
    for imersao in ei.IMERSOES:
        pedidas = [a["frequency"] for a in imersao.ajustes.values() if "frequency" in a]
        pedidas += [a["frequency"] for por_modo in imersao.variantes.values()
                    for a in por_modo.values() if "frequency" in a]
        pedidas += [m.ajustes["frequency"] for m in imersao.momentos if "frequency" in m.ajustes]
        for f in pedidas:
            assert frequencia_limpa(f) == f, (imersao.chave, f)


def test_os_numeros_de_ontem_abrem_a_imersao_de_hoje() -> None:
    assert len(ei.NUMEROS_DE_ONTEM) == 20
    for chave, velha, ajustes in ei.NUMEROS_DE_ONTEM:
        spec = get_spec(velha)
        assert spec is not None, (chave, velha)
        posicionais = list(preset_to_positional_params(spec, dict(ajustes)))
        traduzida = traduzir_chave_velha(velha, posicionais)
        modo, params = traduzida if traduzida is not None else (velha, posicionais)
        achada = ei.imersao_dos_numeros(modo, params)
        assert achada is not None and achada[0].chave == chave, (chave, velha, modo, params)
        assert modo in ei.POR_CHAVE[chave].ajustes, (chave, modo)


@pytest.mark.parametrize("imersao", [i for i in ei.IMERSOES if i.momentos], ids=lambda i: i.chave)
def test_o_motor_toca_os_momentos_sem_repetir_o_bloco_nos_dois_controles(
    monkeypatch: pytest.MonkeyPatch, imersao: ei.Imersao
) -> None:
    modo = next(m for m in imersao.ajustes if ei.momentos_no_modo(imersao, m))
    spec = get_spec(modo)
    assert spec is not None
    params = list(preset_to_positional_params(spec, imersao.ajustes[modo]))
    perfil = _perfil(triggers={"right": {"mode": modo, "params": params}})
    mesa = _mesa(monkeypatch, perfil)
    mesa.apertar(P1)
    mesa.apertar(P2)
    mesa.rodar(3.6)
    uma = [b for _t, b in mesa.backend.de(P1, "right")]
    outra = [b for _t, b in mesa.backend.de(P2, "right")]
    assert uma and uma == outra, "os dois controles recebem a mesma sequência"
    assert all(a != b for a, b in pairwise(uma)), "bloco igual em seguida"
    assert len(uma) <= len(ei.momentos_no_modo(imersao, modo)) + 1
    por_segundo = [t for t, _b in mesa.backend.de(P1, "right") if t < 1.0]
    assert len(por_segundo) <= tv.TETO_POR_CONTROLE
