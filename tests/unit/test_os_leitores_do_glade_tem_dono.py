"""GTK-2 — os três leitores do `main.glade` que NÃO são a janela."""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GLADE = RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
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


@pytest.mark.skipif(not GLADE.exists(),
                    reason="o `gui/main.glade` já saiu (GTK-3) — não há duas "
                           "telas a comparar, e o dono passou a ser único")
def test_enquanto_o_glade_existir_as_duas_telas_dizem_o_mesmo() -> None:
    """A janela estável e a aba nova repetem a MESMA oração, palavra por palavra."""
    from hefesto_dualsense4unix.app.telas import vibracao

    fonte = GLADE.read_text(encoding="utf-8")
    for nome, padrao in NO_GLADE.items():
        achado = re.search(padrao, fonte, re.S)
        assert achado, (
            f"a âncora de {nome} saiu do glade. Ou a janela mudou a frase (e o "
            "dono em `app/telas/vibracao` tem de acompanhar), ou ela saiu de lá "
            "— e aí esta régua sai junto")
        assert html.unescape(achado.group(1)).strip() == getattr(vibracao, nome), (
            f"a janela estável e o dono novo divergiram em {nome}: a janela diz "
            f"{html.unescape(achado.group(1)).strip()!r} e o produto novo diz "
            f"{getattr(vibracao, nome)!r}")


def test_a_aba_05_monta_com_o_glade_apagado(tmp_path: Path) -> None:
    """A MORDIDA FORTE, e é ela que prova a sprint inteira.

    O `gui/main.glade` é **apagado de verdade** numa cópia descartável, e a aba
    05 tem de continuar montando com as duas frases dentro. Nada é remendado: o
    arquivo não existe, e é esse o mundo em que a `GTK-3` vai deixar a árvore.

    A cópia leva `src/`, `docs/data` e `assets/` (o que o gerador lê) e a
    bancada vai para o `tmp_path` pelo `HEFESTO_BANCADA` — a árvore de quem
    roda não recebe um byte.

    SEM O GTK REAL, PULA — 27/09/2026. O `aba05.py` chega ao GTK pela tela da
    vibração (`app/telas/vibracao.py` → `app/actions/rumble_actions.py`), e no
    `lint-test` do CI o filho morria com `No module named 'gi'` antes de olhar
    para o glade: a régua acusava a GTK-3 de um defeito que era do runner.
    """
    from tests.conftest import repassar_a_falta_do_gtk

    arvore = tmp_path / "descartavel"
    (arvore / "docs").mkdir(parents=True)
    ignorar = shutil.ignore_patterns("__pycache__")
    shutil.copytree(RAIZ / "src", arvore / "src", ignore=ignorar)
    shutil.copytree(RAIZ / "docs" / "data", arvore / "docs" / "data", ignore=ignorar)
    shutil.copytree(RAIZ / "assets", arvore / "assets", ignore=ignorar)

    glade = arvore / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
    if glade.exists():
        glade.unlink()
    assert not glade.exists(), "a mordida não apagou o glade — ela não mediu nada"

    bancada = tmp_path / "bancada"
    bancada.mkdir()
    saida = subprocess.run(
        [sys.executable, "aba05.py"],
        cwd=arvore / "src" / "hefesto_dualsense4unix" / "interface",
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
             "HEFESTO_BANCADA": str(bancada),
             "PYTHONPATH": str(arvore / "src")},
        capture_output=True, text=True, timeout=180,
    )
    repassar_a_falta_do_gtk(saida)
    assert saida.returncode == 0, (
        "a aba 05 NÃO monta com o `gui/main.glade` apagado — é este o defeito "
        f"que a GTK-3 encontraria no dia de apagar:\n{saida.stderr[-3000:]}")

    pagina = (bancada / "05-vibracao.html").read_text(encoding="utf-8")
    from hefesto_dualsense4unix.app.telas import vibracao

    for nome in NO_GLADE:
        frase = getattr(vibracao, nome)
        assert pagina.count(frase) == 1, (
            f"a aba montou sem o glade, mas {nome} sumiu da página — montar "
            "calado é pior que não montar")


@pytest.fixture
def doutor(monkeypatch: pytest.MonkeyPatch):
    """O `storm_doctor` com os dois caches ZERADOS."""
    from hefesto_dualsense4unix.integrations import storm_doctor as sd

    monkeypatch.setattr(sd, "_ROTULOS_EM_CACHE", {})
    monkeypatch.setattr(sd, "_ROTULOS_DE_RESERVA", {})
    return sd


@pytest.mark.skipif(not GLADE.exists(), reason="o `gui/main.glade` já saiu (GTK-3)")
def test_a_reserva_fica_vazia_quando_a_leitura_acerta(doutor) -> None:
    """Com a fonte ao alcance, NADA é declarado reserva."""
    lido = doutor.rotulo_do_botao(BOTAO, RESERVA_DO_BOTAO)
    assert lido == RESERVA_DO_BOTAO, (
        f"o rótulo lido da tela viva é {lido!r} e a reserva desta casa diz "
        f"{RESERVA_DO_BOTAO!r}. A reserva tem de acompanhar a tela: ela é o "
        "que a frase publica no dia em que fonte nenhuma responder.")
    assert doutor.rotulos_de_reserva() == {}, (
        "o produto declarou RESERVA sobre um rótulo que ele acabou de LER — a "
        "bandeira `lido_da_fonte` virou uma comparação de strings")


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


def test_o_produto_nao_publica_nenhum_rotulo_de_reserva(doutor) -> None:
    """O PORTÃO QUE FICA: rodado o produto, a lista de reserva tem de ser VAZIA."""
    doutor.check_snd_quirk(quirk_flags_text="", conf_path=Path("/nao/existe.conf"))
    assert doutor.rotulos_de_reserva() == {}, (
        "o produto está publicando rótulo de RESERVA na tela: "
        f"{doutor.rotulos_de_reserva()}. A frase manda clicar num nome que "
        "ninguém conferiu. Dê um dono ao rótulo — o `gui/main.glade` está "
        "sendo aposentado (D-0609-GTK-LEVA-INTEIRA)")


def _laudo(doutor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """O `storm_report` com TUDO por fixture — não pergunta nada à máquina."""
    monkeypatch.setattr(doutor, "_allowlist_path", lambda: tmp_path / "vazia.txt")
    return doutor.storm_report(
        tmp_path, quirks_text="", dropin_dir=tmp_path, rules_dir=tmp_path,
        snd_quirk_text="", snd_conf_path=tmp_path / "ausente.conf",
        cards_text="", controles_no_cabo=0,
    )


MARCA_DA_RESERVA = "não pôde ser conferido"


@pytest.mark.skipif(not GLADE.exists(), reason="o `gui/main.glade` já saiu (GTK-3)")
def test_o_laudo_nao_ganha_linha_quando_o_rotulo_foi_lido(
    doutor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A linha da reserva é CONDICIONAL, e hoje ela não aparece."""
    linhas = _laudo(doutor, tmp_path, monkeypatch)
    assert not [m for _, m in linhas if MARCA_DA_RESERVA in m], (
        "o laudo ganhou a linha da reserva com o rótulo LIDO da fonte — a cura "
        "está cobrando preço de quem não devia nada")


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


def _arvore_de_extracao(tmp_path: Path, *, com_glade: bool) -> Path:
    """Uma árvore mínima onde o `i18n_extract.sh` roda de verdade."""
    arvore = tmp_path / ("com" if com_glade else "sem")
    (arvore / "scripts").mkdir(parents=True)
    pacote = arvore / "src" / "hefesto_dualsense4unix"
    (pacote / "gui").mkdir(parents=True)
    (arvore / "po").mkdir()
    shutil.copy(RAIZ / "scripts" / "i18n_extract.sh", arvore / "scripts")
    (pacote / "frases.py").write_text(
        'from gettext import gettext as _\n\nTITULO = _("Frase do Python — çã")\n',
        encoding="utf-8")
    if com_glade:
        (pacote / "gui" / "main.glade").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<interface>\n'
            '  <object class="GtkLabel" id="rotulo">\n'
            '    <property name="label" translatable="yes">Frase da Janela — çã'
            '</property>\n'
            '  </object>\n'
            '</interface>\n',
            encoding="utf-8")
    return arvore


def _extrair(arvore: Path, *argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "scripts/i18n_extract.sh", *argumentos],
        cwd=arvore, capture_output=True, text=True, timeout=120)


@pytest.mark.skipif(shutil.which("xgettext") is None,
                    reason="gettext ausente nesta máquina")
def test_com_o_glade_o_extrator_continua_o_de_sempre(tmp_path: Path) -> None:
    """A cura não pode cobrar o preço no caminho que já funcionava."""
    arvore = _arvore_de_extracao(tmp_path, com_glade=True)
    saida = _extrair(arvore)
    assert saida.returncode == 0, saida.stderr
    pot = (arvore / "po" / "hefesto-dualsense4unix.pot").read_text(encoding="utf-8")
    assert "Frase do Python" in pot and "Frase da Janela" in pot, (
        "com o glade no lugar o catálogo perdeu uma das duas fontes")
    assert not list((arvore / "po").glob("*.pot.python")), (
        "o parcial ficou para trás no `po/` — o `trap` de limpeza caiu")


@pytest.mark.skipif(shutil.which("xgettext") is None,
                    reason="gettext ausente nesta máquina")
def test_sem_o_glade_o_extrator_para_e_diz_o_que_sumiu(tmp_path: Path) -> None:
    """A MORDIDA do Passo 3: sem a fonte, o comportamento MUDA e se OUVE."""
    arvore = _arvore_de_extracao(tmp_path, com_glade=False)
    pot = arvore / "po" / "hefesto-dualsense4unix.pot"
    pot.write_text('msgid "o catálogo de ontem"\nmsgstr ""\n', encoding="utf-8")

    saida = _extrair(arvore)
    assert saida.returncode != 0, (
        "o extrator seguiu sem a fonte da janela — é assim que um catálogo "
        "encolhe em silêncio")
    assert "main.glade" in saida.stderr, "a recusa não nomeia o que sumiu"
    assert "D-0609-GTK-LEVA-INTEIRA" in saida.stderr, (
        "a recusa não diz POR QUE o arquivo sumiu — sem isso ela vira mais um "
        "erro de ferramenta para alguém contornar")
    assert "--sem-a-janela" in saida.stderr, "a recusa não diz como seguir"
    assert pot.read_text(encoding="utf-8") == 'msgid "o catálogo de ontem"\nmsgstr ""\n', (
        "o `.pot` foi mexido numa execução que falhou")
    assert not list((arvore / "po").glob("*.pot.python")), (
        "o parcial ficou para trás numa execução interrompida")


@pytest.mark.skipif(shutil.which("xgettext") is None,
                    reason="gettext ausente nesta máquina")
def test_a_bandeira_deixa_o_catalogo_menor_sair_por_escrito(tmp_path: Path) -> None:
    """`--sem-a-janela` é a saída, e ela DIZ o tamanho do buraco."""
    arvore = _arvore_de_extracao(tmp_path, com_glade=False)
    saida = _extrair(arvore, "--sem-a-janela")
    assert saida.returncode == 0, saida.stderr
    assert "SEM A JANELA" in saida.stdout, (
        "o catálogo menor saiu sem dizer que é menor")
    pot = (arvore / "po" / "hefesto-dualsense4unix.pot").read_text(encoding="utf-8")
    assert "Frase do Python" in pot
