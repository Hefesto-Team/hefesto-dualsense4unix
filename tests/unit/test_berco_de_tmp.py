"""BERCO-DE-TMP-01 — a suíte devolve o ``/tmp`` como encontrou?

O PORQUÊ, MEDIDO em 07/08/2026 com retrato do disco antes e depois de uma suíte
inteira: o CANARIO-FS-01 ficou CALADO (a suíte não escreveu no ``$HOME``), e
mesmo assim a execução deixou **16 entradas novas em `/tmp`** — 9 de
`tempfile.mkdtemp()` sem limpeza nos testes de migração de perfil, 6 de `mktemp`
de shell dentro de script sob teste, 1 da libpulse. O acumulado do dia: 906
diretórios `tmp<8>`, 892 deles ainda com os arquivos que só aqueles testes
escrevem.

A cura é o BERÇO: a sessão desvia `tempfile` e `TMPDIR` para
``/tmp/hefesto-berco-<pid>`` e leva o diretório inteiro embora no fim.

Estes testes provam as DUAS metades do contrato, e a segunda importa mais que a
primeira: o berço leva o que nasceu dentro dele, **e não encosta em nada que
esteja do lado de fora** — porque do lado de fora está o `/tmp` de uma máquina
viva, com arquivo dela no meio.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

from tests import conftest as berco_mod


class _SessaoFalsa:
    """O mínimo que os hooks tocam numa Session."""

    def __init__(self, exitstatus: int = 0) -> None:
        self.exitstatus = exitstatus
        self.config = None


@pytest.fixture
def sessao() -> _SessaoFalsa:
    """A MESMA Session arma e varre — é o que acontece numa sessão de verdade,
    e é o que a guarda `_SESSAO_REAL` exige."""
    return _SessaoFalsa()


@pytest.fixture
def tmp_falso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um ``/tmp`` de mentira, com o estado do berço zerado e restaurável.

    Sem isto os testes daqui roubariam o berço da sessão VIVA que os está
    rodando — e o `sessionfinish` de verdade acharia que já tinha varrido.
    """
    falso = tmp_path / "tmp"
    falso.mkdir()
    monkeypatch.setattr(berco_mod, "_BERCO", [])
    monkeypatch.setattr(berco_mod, "_TMP_REAL", [])
    monkeypatch.setattr(berco_mod, "_TMP_ANTES", set())
    monkeypatch.setattr(berco_mod, "_SESSAO_REAL", [])
    monkeypatch.setattr(tempfile, "tempdir", str(falso))
    for var in ("TMPDIR", "TMP", "TEMP"):
        if var in os.environ:
            monkeypatch.setenv(var, os.environ[var])
        else:
            monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv(berco_mod._BERCO_DESLIGADO_ENV, raising=False)
    return falso


def _pid_morto() -> int:
    """Um pid que existiu e já foi ceifado.

    O Linux distribui pids de forma monotônica; reciclar um pid entre o `wait`
    e a linha seguinte exigiria dar a volta no `pid_max` inteiro em
    microssegundos. Ainda assim o teste CONFERE antes de usar, porque um teste
    que depende de sorte não é teste.
    """
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


# ---------------------------------------------------------------------------
# O berço nasce, e tudo passa a nascer dentro dele
# ---------------------------------------------------------------------------


def test_o_berco_leva_o_pid_da_sessao_no_nome(tmp_falso: Path) -> None:
    """O pid no nome é o que torna a varredura POSITIVA: 'foi esta sessão'."""
    berco_mod._armar_berco(_SessaoFalsa())
    nosso = berco_mod.berco()
    assert nosso is not None
    assert nosso.name == f"hefesto-berco-{os.getpid()}"
    assert nosso.parent == tmp_falso
    assert oct(nosso.stat().st_mode)[-3:] == "700"


def test_tempfile_passa_a_nascer_dentro_do_berco(tmp_falso: Path) -> None:
    """A MORDIDA: arranque o `tempfile.tempdir = ...` de `_armar_berco` e o
    diretório volta a nascer solto no `/tmp`, que é o defeito de 07/08."""
    berco_mod._armar_berco(_SessaoFalsa())
    nosso = berco_mod.berco()
    assert nosso is not None

    criado = Path(tempfile.mkdtemp())

    assert criado.parent == nosso, "mkdtemp() nasceu FORA do berço"
    assert criado.parent != tmp_falso


def test_o_tmpdir_do_ambiente_tambem_aponta_para_o_berco(tmp_falso: Path) -> None:
    """Os 6 `tmp.<10>` medidos vieram de `mktemp` de SHELL, num subprocesso —
    só o `TMPDIR` do ambiente os alcança."""
    berco_mod._armar_berco(_SessaoFalsa())
    nosso = berco_mod.berco()
    assert nosso is not None
    for var in ("TMPDIR", "TMP", "TEMP"):
        assert os.environ[var] == str(nosso)


# ---------------------------------------------------------------------------
# A varredura: leva o que é dela, e SÓ o que é dela
# ---------------------------------------------------------------------------


def test_a_varredura_leva_o_berco_inteiro(
    tmp_falso: Path, sessao: _SessaoFalsa
) -> None:
    berco_mod._armar_berco(sessao)
    nosso = berco_mod.berco()
    assert nosso is not None
    (nosso / "lixo.json").write_text("{}", encoding="utf-8")
    (nosso / "sub").mkdir()
    (nosso / "sub" / "mais-lixo").write_text("x", encoding="utf-8")

    berco_mod._varrer_berco(sessao, 0)

    assert not nosso.exists()
    assert berco_mod.berco() is None


def test_arquivo_real_dela_ao_lado_do_berco_nao_e_tocado(
    tmp_falso: Path, sessao: _SessaoFalsa
) -> None:
    """O CASO PERIGOSO, e o que decide se este mecanismo pode existir.

    No `/tmp` de uma máquina viva há screenshot dela, buffer de clipboard,
    socket do PipeWire. A varredura só pode remover o que nasceu no berço —
    nunca o vizinho, por mais que o vizinho pareça temporário.
    """
    berco_mod._armar_berco(sessao)
    nosso = berco_mod.berco()
    assert nosso is not None

    dela = tmp_falso / "Screenshot_2026-08-07_15-49-08.png"
    dela.write_bytes(b"PNG-de-mentira-mas-dela")
    outra = tmp_falso / "tmpzzzzzzzz"
    outra.mkdir()
    (outra / "perfil-dela.json").write_text('{"name": "vitoria"}', encoding="utf-8")
    parecido = tmp_falso / "hefesto-berco-de-outra-coisa"
    parecido.mkdir()
    (parecido / "importante.txt").write_text("não apague", encoding="utf-8")

    (nosso / "lixo").write_text("x", encoding="utf-8")
    berco_mod._varrer_berco(sessao, 0)

    assert not nosso.exists()
    assert dela.read_bytes() == b"PNG-de-mentira-mas-dela"
    assert (outra / "perfil-dela.json").read_text(encoding="utf-8") == (
        '{"name": "vitoria"}'
    )
    assert (parecido / "importante.txt").read_text(encoding="utf-8") == "não apague"


def test_sessao_verde_e_sem_resto_nao_imprime_nada(
    tmp_falso: Path, sessao: _SessaoFalsa, capsys: pytest.CaptureFixture[str]
) -> None:
    """Instrumento calado quando não há o que dizer — senão vira ruído."""
    berco_mod._armar_berco(sessao)
    capsys.readouterr()

    berco_mod._varrer_berco(sessao, 0)

    assert capsys.readouterr().out == ""


def test_sessao_vermelha_preserva_o_berco(
    tmp_falso: Path, sessao: _SessaoFalsa, capsys: pytest.CaptureFixture[str]
) -> None:
    """Quando a suíte cai, o que ela deixou pode ser prova. Guardar é barato:
    a próxima sessão varre pelo pid morto."""
    berco_mod._armar_berco(sessao)
    nosso = berco_mod.berco()
    assert nosso is not None
    (nosso / "pista.txt").write_text("o que sobrou", encoding="utf-8")

    sessao.exitstatus = 1
    berco_mod._varrer_berco(sessao, 1)

    assert nosso.exists()
    assert (nosso / "pista.txt").read_text(encoding="utf-8") == "o que sobrou"
    assert "o berço FICA" in capsys.readouterr().out


def test_a_conta_do_que_a_suite_deixaria_sai_no_relato(
    tmp_falso: Path, sessao: _SessaoFalsa, capsys: pytest.CaptureFixture[str]
) -> None:
    """Varrer em silêncio esconderia o defeito de origem. O relato é o que
    permite alguém consertar o teste que vaza."""
    berco_mod._armar_berco(sessao)
    nosso = berco_mod.berco()
    assert nosso is not None
    for i in range(3):
        (nosso / f"vazamento{i}").mkdir()
    capsys.readouterr()

    berco_mod._varrer_berco(sessao, 0)

    saida = capsys.readouterr().out
    assert "3 entrada(s)" in saida
    assert "vazamento0" in saida


# ---------------------------------------------------------------------------
# Berços de sessões mortas — e NUNCA os de sessão viva
# ---------------------------------------------------------------------------


def test_pid_vivo_responde_a_verdade() -> None:
    assert berco_mod._pid_vivo(os.getpid())
    morto = _pid_morto()
    assert not berco_mod._pid_vivo(morto), "pid reciclado no meio do teste"


def test_berco_de_sessao_viva_nunca_entra_na_varredura(tmp_falso: Path) -> None:
    """A regra que impede o pior acidente possível: duas suítes rodam ao mesmo
    tempo nesta máquina, e uma não pode apagar o `/tmp` da outra."""
    vivo = tmp_falso / f"hefesto-berco-{os.getpid()}"
    vivo.mkdir()

    assert berco_mod._bercos_orfaos(tmp_falso) == []


def test_berco_de_sessao_morta_e_varrido_na_proxima(tmp_falso: Path) -> None:
    """Sessão morta a `kill` não roda `sessionfinish` — sem esta regra o berço
    dela ficaria para sempre, que é como os 3 `hefesto-arvore-congelada-*`
    chegaram ao `/tmp` dela."""
    morto = _pid_morto()
    orfao = tmp_falso / f"hefesto-berco-{morto}"
    orfao.mkdir()
    (orfao / "resto").write_text("x", encoding="utf-8")
    vivo = tmp_falso / f"hefesto-berco-{os.getpid()}"
    vivo.mkdir()

    assert berco_mod._bercos_orfaos(tmp_falso) == [orfao]

    berco_mod._armar_berco(_SessaoFalsa())

    assert not orfao.exists()
    assert berco_mod.berco() is not None


@pytest.mark.parametrize(
    "nome",
    [
        "hefesto-berco",
        "hefesto-berco-",
        "hefesto-berco-abc",
        "hefesto-berco-12a",
        "hefesto-berco-de-outra-coisa",
        "hefesto-berco--1",
        "outra-coisa-qualquer",
    ],
)
def test_nome_que_nao_e_berco_nunca_e_alvo(tmp_falso: Path, nome: str) -> None:
    """O sufixo tem de ser dígito PURO. Um `hefesto-berco-de-outra-coisa` é
    diretório de alguém, e a dúvida sempre se resolve para 'não mexa'."""
    assert berco_mod._pid_do_berco(nome) is None
    (tmp_falso / nome).mkdir()
    assert berco_mod._bercos_orfaos(tmp_falso) == []


def test_link_simbolico_nunca_e_seguido(tmp_falso: Path, tmp_path: Path) -> None:
    """Um link chamado `hefesto-berco-<pid morto>` apontando para a config dela
    não pode virar alvo: o alvo dele não nasceu de teste nenhum."""
    de_verdade = tmp_path / "config-dela"
    de_verdade.mkdir()
    (de_verdade / "perfil.json").write_text("{}", encoding="utf-8")
    morto = _pid_morto()
    (tmp_falso / f"hefesto-berco-{morto}").symlink_to(de_verdade)

    assert berco_mod._bercos_orfaos(tmp_falso) == []

    berco_mod._armar_berco(_SessaoFalsa())

    assert (de_verdade / "perfil.json").exists()


# ---------------------------------------------------------------------------
# A escotilha, e o que fica FORA do berço de propósito
# ---------------------------------------------------------------------------


def test_escotilha_desliga_o_berco(
    tmp_falso: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(berco_mod._BERCO_DESLIGADO_ENV, "1")

    berco_mod._armar_berco(_SessaoFalsa())

    assert berco_mod.berco() is None
    assert list(tmp_falso.iterdir()) == []


def test_aviso_do_que_nasceu_fora_do_berco(
    tmp_falso: Path, sessao: _SessaoFalsa, capsys: pytest.CaptureFixture[str]
) -> None:
    """A classe que o berço NÃO alcança: caminho fixo escrito à mão num teste,
    que ignora `TMPDIR` por construção. Foi assim que
    `hefesto_teste_pactl_chamadas.txt` apareceu na medição de 07/08.

    É AVISO e não portão, porque a máquina dela também escreve em `/tmp`.
    """
    berco_mod._armar_berco(sessao)
    (tmp_falso / "hefesto_teste_caminho_fixo.txt").write_text("x", encoding="utf-8")
    capsys.readouterr()

    berco_mod._varrer_berco(sessao, 0)

    saida = capsys.readouterr().out
    assert "hefesto_teste_caminho_fixo.txt" in saida
    assert "não é portão" in saida
    assert sessao.exitstatus == 0, "aviso não pode reprovar a sessão"
    assert (tmp_falso / "hefesto_teste_caminho_fixo.txt").exists(), (
        "o aviso RELATA; quem apaga fora do berço é a faxina, com prova"
    )


# ---------------------------------------------------------------------------
# Contra a sessão VIVA que está rodando este arquivo
# ---------------------------------------------------------------------------


def _berco_vivo() -> Path:
    nosso = berco_mod.berco()
    if nosso is None:
        pytest.skip(f"berço desarmado ({berco_mod._BERCO_DESLIGADO_ENV}=1)")
    return nosso


def test_o_basetemp_do_pytest_fica_fora_do_berco(tmp_path: Path) -> None:
    """Decisão medida, não descuido: o `sun_path` de um `AF_UNIX` tem ~108
    bytes, e há teste desta casa cujo socket sob `tmp_path` já bate em 95.
    Empurrar `tmp_path` para dentro do berço somaria os bytes do berço a todos
    eles. Além disso o pytest já guarda as 3 últimas execuções, que é o que se
    olha quando um teste cai."""
    nosso = _berco_vivo()
    assert nosso not in tmp_path.parents


def test_a_arvore_congelada_nasce_dentro_do_berco() -> None:
    """Os 3 `hefesto-arvore-congelada-*` achados no `/tmp` dela em 07/08 são
    sessões mortas cujo `atexit` nunca rodou. Dentro do berço, a varredura da
    sessão seguinte os alcança mesmo assim."""
    nosso = _berco_vivo()
    congelada = berco_mod.arvore_congelada()
    assert nosso in congelada.parents


def test_sessao_de_mentira_nao_varre_o_berco_da_sessao_viva() -> None:
    """O defeito medido em 07/08, na primeira integração deste berço.

    Nove testes do `test_conftest_canario_fs.py` chamam `pytest_sessionfinish`
    com uma Session de MENTIRA, de propósito, para provar que o canário
    reprova. A primeira dessas chamadas varria o berço da sessão VIVA no meio
    dela e devolvia `tempfile.tempdir` para o `/tmp` real: a suíte voltava, em
    silêncio, ao comportamento que este berço veio curar.

    MORDIDA: tirar o `if _SESSAO_REAL and id(session) not in _SESSAO_REAL` de
    `_varrer_berco` faz este teste apagar o próprio berço e reprovar.
    """
    nosso = _berco_vivo()

    berco_mod.pytest_sessionfinish(_SessaoFalsa(), 0)

    assert nosso.exists(), "uma Session de mentira varreu o berço da sessão viva"
    assert berco_mod.berco() == nosso
    assert tempfile.gettempdir() == str(nosso)


def test_o_home_dela_nao_e_assunto_deste_mecanismo() -> None:
    """Contrato declarado: o berço mexe em `/tmp`, e o `$HOME` fica com o
    CANARIO-FS-01 (prevenir e DETECTAR). Restaurar arquivo em `$HOME` seria
    desfazer escrita da daemon VIVA dela — o dano maior."""
    nosso = _berco_vivo()
    lar = Path(os.path.expanduser("~")).resolve()
    assert lar not in nosso.parents
    assert nosso.resolve() != lar


def test_a_suite_viva_nao_deixou_alvo_de_faxina_no_tmp_real() -> None:
    """O portão de verdade desta leva: com o berço armado, uma sessão desta
    suíte não pode mais criar `tmp<8>` assinado no `/tmp` real.

    Roda a faxina em modo relato contra a raiz real e exige que nenhum alvo
    tenha nascido DEPOIS do início desta sessão.
    """
    nosso = _berco_vivo()
    faxina = _carregar_faxina()
    raiz = nosso.parent
    nascimento = nosso.stat().st_mtime

    alvos, _recusas, _relato = faxina.recolher(raiz, 3600.0, nascimento)
    recentes = [a.caminho.name for a in alvos if a.caminho.stat().st_mtime > nascimento]

    assert recentes == [], (
        "esta sessão criou lixo de teste FORA do berço: " f"{recentes}"
    )


def _carregar_faxina() -> Any:
    """Importa `scripts/faxina-de-testes.py`, que tem hífen no nome.

    O módulo PRECISA entrar em `sys.modules` antes do `exec_module`: ele usa
    `from __future__ import annotations` com `@dataclass`, e o `dataclasses`
    resolve a anotação em texto procurando o módulo pelo nome.
    """
    import importlib.util

    ja = sys.modules.get("faxina_de_testes")
    if ja is not None:
        return ja
    raiz = Path(__file__).resolve().parents[2]
    caminho = raiz / "scripts" / "faxina-de-testes.py"
    spec = importlib.util.spec_from_file_location("faxina_de_testes", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["faxina_de_testes"] = modulo
    spec.loader.exec_module(modulo)
    return modulo
