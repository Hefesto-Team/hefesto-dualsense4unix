"""GTK-2 — os três leitores do `main.glade` que NÃO são a janela."""
from __future__ import annotations

import subprocess
import sys
import warnings
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

NO_GLADE = {
    "DICA_DO_TETO_DA_MESA":
        r'id="rumble_policy_economia".*?tooltip-text[^>]*>[^<]*?'
        r'(O Perfil de Bateria pode impor um teto[^<]*?)</property>',
    "DICA_DOS_VALORES_QUE_PASSAM":
        r'id="rumble_info".*?<property name="label"[^>]*>&lt;i&gt;'
        r'(.*?)&lt;/i&gt;</property>',
}

BOTAO = "btn_storm_fix_safe"
RESERVA_DO_BOTAO = "Refazer os consertos automáticos"


def _sem_fonte_nenhuma(doutor, monkeypatch, tmp_path) -> None:
    """Tira as DUAS fontes do alcance — a página e o glade."""
    monkeypatch.setattr(doutor, "_NA_TELA_VIVA", {})
    monkeypatch.setattr(
        doutor, "__file__", str(tmp_path / "sem_gui" / "storm_doctor.py"))


def test_a_aba_05_le_as_duas_frases_do_motor_e_nao_as_digita(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O dono é `app/telas/vibracao`, e a aba **lê** dele — não redigita."""
    monkeypatch.setenv("HEFESTO_BANCADA", str(tmp_path))
    sys.path.insert(0, str(INTERFACE))
    import aba05

    from hefesto_dualsense4unix.app.telas import vibracao

    for nome in NO_GLADE:
        assert getattr(aba05, nome) is getattr(vibracao, nome), (
            f"a aba 05 deixou de LER {nome} de `app/telas/vibracao` — se ela "
            "voltar a digitar o texto, as duas cópias divergem na primeira "
            "edição (RUM-01, o botão 'Devolver ao jogo' que não existia)")


@pytest.fixture
def doutor(monkeypatch: pytest.MonkeyPatch):
    """O `storm_doctor` com os dois caches ZERADOS."""
    from hefesto_dualsense4unix.integrations import storm_doctor as sd

    monkeypatch.setattr(sd, "_ROTULOS_EM_CACHE", {})
    monkeypatch.setattr(sd, "_ROTULOS_DE_RESERVA", {})
    return sd


def test_sem_a_fonte_a_frase_fica_de_pe_e_o_produto_sabe(
    doutor, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """As DUAS metades da mordida do Passo 2, no mesmo caso."""
    _sem_fonte_nenhuma(doutor, monkeypatch, tmp_path)

    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        saiu = doutor.rotulo_do_botao(BOTAO, RESERVA_DO_BOTAO)

    assert saiu == RESERVA_DO_BOTAO, (
        "sem a fonte a frase de tela SUMIU — a reserva deixou de ser macia, e "
        "uma frase que some é pior que uma com nome velho")
    assert doutor.rotulos_de_reserva() == {BOTAO: RESERVA_DO_BOTAO}, (
        "o rótulo saiu da reserva e o produto NÃO registrou — é o silêncio que "
        "esta sprint veio matar")
    assert any(BOTAO in str(a.message) for a in avisos), (
        "nenhum aviso saiu: a reserva voltou a ser calada em runtime")


def _laudo(doutor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """O `storm_report` com TUDO por fixture — não pergunta nada à máquina."""
    monkeypatch.setattr(doutor, "_allowlist_path", lambda: tmp_path / "vazia.txt")
    return doutor.storm_report(
        tmp_path, quirks_text="", dropin_dir=tmp_path, rules_dir=tmp_path,
        snd_quirk_text="", snd_conf_path=tmp_path / "ausente.conf",
        cards_text="", controles_no_cabo=0,
    )


MARCA_DA_RESERVA = "não pôde ser conferido"


def test_o_laudo_diz_quando_o_nome_do_botao_veio_da_reserva(
    doutor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O produto CONSOME o registro — não basta expô-lo numa função.

    É a diferença entre saber e dizer. Sem esta linha, `rotulos_de_reserva()`
    seria uma promessa pública sem chamador no produto: o portão
    `portao_a_casa_sabe_e_o_produto_nao_faz` reprova exatamente isso, e reprovou
    a primeira versão desta sprint.
    """
    _sem_fonte_nenhuma(doutor, monkeypatch, tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        linhas = _laudo(doutor, tmp_path, monkeypatch)

    da_reserva = [m for _, m in linhas if MARCA_DA_RESERVA in m]
    assert len(da_reserva) == 1, (
        "o laudo NÃO diz que citou um nome de botão que ninguém conferiu — o "
        f"produto sabe e cala. Linhas: {[m[:60] for _, m in linhas]}")
    assert RESERVA_DO_BOTAO in da_reserva[0], (
        "a linha da reserva não nomeia o rótulo em questão")


def _extrair(arvore: Path, *argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "scripts/i18n_extract.sh", *argumentos],
        cwd=arvore, capture_output=True, text=True, timeout=120)


