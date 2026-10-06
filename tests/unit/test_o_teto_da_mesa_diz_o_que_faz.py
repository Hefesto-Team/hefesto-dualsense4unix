"""O perfil de desempenho diz o que faz — e nenhuma dica promete o que o clique não produz."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o perfil de desempenho da aba Configurações")

import ast
import importlib
from dataclasses import replace
from pathlib import Path

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions.config import secao_orcamento
from hefesto_dualsense4unix.core.rumble import teto_do_orcamento
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    SLOTS_POR_SEGUNDO,
)

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "src" / "hefesto_dualsense4unix" / "app"

VERBOS_DE_EFEITO = (
    "cai para",
    "chega com",
    "acompanha a bateria",
    "limita",
    "limitado",
    "reduz",
    "no máximo",
)


def test_nenhuma_dica_promete_o_que_o_botao_nao_faz() -> None:
    """MORDIDA 1. Sem teto, a dica não pode conter verbo de efeito."""
    achados = []
    for perfil in secao_orcamento.PERFIS:
        chave = secao_orcamento.TETO_POR_PERFIL[perfil]
        teto = teto_do_orcamento(chave) if isinstance(chave, str) else None
        if teto is not None:
            continue
        dica = secao_orcamento.DICAS.get(perfil, "").lower()
        achados += [
            f"perfil {perfil!r} (teto None) promete {verbo!r}: {dica!r}"
            for verbo in VERBOS_DE_EFEITO
            if verbo in dica
        ]
    assert not achados, (
        "uma dica voltou a prometer efeito que o clique não produz:\n  "
        + "\n  ".join(achados)
    )


def test_a_dica_do_auto_saiu_de_vez() -> None:
    """Fato errado se SUBSTITUI: a escada da bateria não fica ao lado do certo."""
    for dica in secao_orcamento.DICAS.values():
        assert "acompanha a bateria" not in dica.lower()
    assert "auto" not in {p.lower() for p in secao_orcamento.PERFIS}
    assert secao_orcamento.ROTULOS_DOS_PERFIS.get("auto") is None


def test_a_dica_do_perfil_de_bateria_nao_promete_mais_que_a_tabela() -> None:
    """A palavra de produto dizia "barra de luz apagada" — e não há por onde apagá-la."""
    dica = secao_orcamento.DICAS[secao_orcamento.PERFIL_BATERIA_LONGA]
    for linha in secao_orcamento.LINHAS_DO_TETO:
        if linha.tem_ponto:
            continue
        assert linha.nome in dica, (
            f"a linha {linha.nome!r} não tem ponto de aplicação e sumiu da "
            "dica — a dica passou a prometer mais do que a tabela mostra"
        )
    assert "apagada" not in dica.lower()


def test_a_tabela_tem_uma_coluna_por_opcao_oferecida() -> None:
    """MORDIDA 3. Com todas as colunas na tela, a tabela mostra o que a seção faz."""
    oferecidos = [secao_orcamento.ROTULOS_DOS_PERFIS[p] for p in secao_orcamento.PERFIS]
    faltando = [rotulo for rotulo in oferecidos if rotulo not in secao_orcamento.COLUNAS]
    assert not faltando, f"a tabela deixou de ter coluna para: {faltando}"
    assert secao_orcamento.COLUNAS[:2] == ("O que", "Vem de")
    assert len(secao_orcamento.COLUNAS) == len(oferecidos) + 2


def test_a_frase_do_alcance_deriva_da_tabela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA 4. Uma sexta linha sem ponto tem de aparecer na frase."""
    antes = secao_orcamento.alcance_de_hoje().lower()
    assert "vibração" in antes
    assert "touchpad" not in antes

    monkeypatch.setattr(
        secao_orcamento,
        "LINHAS_DO_TETO",
        (*secao_orcamento.LINHAS_DO_TETO, secao_orcamento.LinhaDoTeto("Touchpad", "Perfis")),
    )
    depois = secao_orcamento.alcance_de_hoje()
    assert "Touchpad" in depois, (
        "a frase de apoio parou de derivar da tabela — uma linha nova entrou na "
        "tabela e a frase não a viu"
    )


def test_a_frase_do_alcance_muda_quando_uma_linha_ganha_ponto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A régua sabe RECUSAR: linha COM ponto sai da lista dos pendentes."""
    com_ponto = tuple(
        replace(
            linha,
            ponto_de_aplicacao="hefesto_dualsense4unix.core.rumble:_effective_mult",
        )
        for linha in secao_orcamento.LINHAS_DO_TETO
    )
    monkeypatch.setattr(secao_orcamento, "LINHAS_DO_TETO", com_ponto)
    frase = secao_orcamento.alcance_de_hoje()
    assert "entram quando ganharem" not in frase
    assert "Barra de luz" in frase


def test_so_a_vibracao_tem_ponto_de_aplicacao_hoje() -> None:
    """MORDIDA 5. Todo ponto declarado é IMPORTADO — marcar sem existir reprova."""
    com_ponto = [linha for linha in secao_orcamento.LINHAS_DO_TETO if linha.tem_ponto]
    assert [linha.nome for linha in com_ponto] == ["Vibração", "Gatilhos", "Barra de luz"], (
        "uma linha ganhou ponto de aplicação; se ele existe mesmo, o teste é "
        "que muda — mas ele tem de ser IMPORTÁVEL abaixo"
    )
    for linha in com_ponto:
        assert linha.ponto_de_aplicacao is not None
        modulo, _, atributo = linha.ponto_de_aplicacao.partition(":")
        alvo = importlib.import_module(modulo)
        assert hasattr(alvo, atributo), (
            f"a linha {linha.nome!r} declara o ponto "
            f"{linha.ponto_de_aplicacao!r}, e ele não existe"
        )


def test_ninguem_em_app_recalcula_a_conta_de_slots() -> None:
    """MORDIDA 6. As constantes do rádio têm UM dono, e ele mora em `integrations/`."""
    proibidos = {
        float(SLOTS_POR_SEGUNDO),
        HZ_INPUT_SEM_MIC,
        HZ_INPUT_COM_MIC,
        HZ_AUDIO_COM_MIC,
    }
    achados = []
    for caminho in sorted(APP.rglob("*.py")):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if (
                isinstance(no, ast.Constant)
                and isinstance(no.value, (int, float))
                and not isinstance(no.value, bool)
                and float(no.value) in proibidos
            ):
                achados.append(
                    f"{caminho.relative_to(RAIZ)}:{no.lineno} → {no.value}"
                )
    assert not achados, (
        "alguém digitou uma constante do rádio dentro de `app/` — a conta tem "
        "um dono, e ele é `integrations/radio_da_mesa.py`:\n  "
        + "\n  ".join(achados)
    )


def test_a_secao_nao_reimplementa_a_conta_e_sim_a_consome() -> None:
    """A seção DESENHA; quem calcula é `plano_de_radio`, que consome o medidor."""
    fonte = Path(secao_orcamento.__file__).read_text(encoding="utf-8")
    assert "plano_de_radio" in fonte
    for proibido in ("HZ_INPUT_SEM_MIC =", "SLOTS_POR_SEGUNDO =", "CORTE_APERTADA ="):
        assert proibido not in fonte, (
            f"a seção passou a definir `{proibido.split(' =')[0]}` — a "
            "constante tem um dono, e ele mora em `integrations/`"
        )


@pytest.mark.parametrize(
    ("gravado", "esperado"),
    [
        ("economia", "bateria_longa"),
        ("balanceado", "tudo_ligado"),
        ("max", "tudo_ligado"),
        ("auto", "tudo_ligado"),
    ],
)
def test_a_migracao_e_um_para_um_e_nao_perde_nada(gravado: str, esperado: str) -> None:
    """Cada valor que o disco aceita tem um perfil, e o teto não muda de mão."""
    assert secao_orcamento.PERFIL_POR_TETO[gravado] == esperado
    antes = teto_do_orcamento(gravado)
    chave = secao_orcamento.TETO_POR_PERFIL[esperado]
    depois = teto_do_orcamento(chave) if isinstance(chave, str) else None
    assert antes == depois, (
        f"migrar {gravado!r} para {esperado!r} mudaria o teto de {antes} para "
        f"{depois} sem ninguém pedir"
    )


