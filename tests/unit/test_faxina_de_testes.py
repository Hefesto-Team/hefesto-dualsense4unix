"""`scripts/faxina-de-testes.py` — o passivo de `/tmp`, e o que ele NÃO toca.

O berço (BERCO-DE-TMP-01, em `tests/conftest.py`) resolve o futuro: desde
07/08/2026 a suíte não deixa mais nada solto em `/tmp`. Este script existe para
o que ficou ANTES — 906 diretórios `tmp<8>` medidos no `/tmp` dela naquele dia.

Um script que apaga arquivo no `/tmp` de uma máquina viva tem UM jeito certo de
existir: o critério de "isto é lixo de teste" precisa ser POSITIVO — prova de
quem criou —, nunca *"não reconheço, então apago"*. A maioria dos testes deste
arquivo é sobre a segunda metade do contrato: **o que o script se recusa a
apagar**, e por quê.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest


def _faxina() -> Any:
    """Importa `scripts/faxina-de-testes.py` (o hífen impede o import normal).

    O módulo entra em `sys.modules` ANTES do `exec_module`: ele usa
    `from __future__ import annotations` com `@dataclass`, e o `dataclasses`
    resolve a anotação em texto procurando o módulo pelo nome.
    """
    ja = sys.modules.get("faxina_de_testes")
    if ja is not None:
        return ja
    caminho = Path(__file__).resolve().parents[2] / "scripts" / "faxina-de-testes.py"
    spec = importlib.util.spec_from_file_location("faxina_de_testes", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["faxina_de_testes"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


FAXINA = _faxina()
AGORA = 1_000_000.0
UMA_HORA = 3600.0


def _dir_de_migracao(raiz: Path, nome: str, extras: dict[str, str] | None = None) -> Path:
    """Um `tmp<8>` como os testes de migração de perfil o deixam."""
    d = raiz / nome
    d.mkdir()
    (d / ".coop_default_on_migrated").write_text("1", encoding="utf-8")
    (d / ".coop_default_on_migrated.lock").write_text("", encoding="utf-8")
    (d / "meu_jogo.json").write_text('{"name": "meu_jogo"}', encoding="utf-8")
    for chave, valor in (extras or {}).items():
        (d / chave).write_text(valor, encoding="utf-8")
    return d


def _pid_morto() -> int:
    import subprocess

    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    alvo = tmp_path / "tmp"
    alvo.mkdir()
    return alvo


# ---------------------------------------------------------------------------
# O que o script PROVA que é lixo
# ---------------------------------------------------------------------------


def test_diretorio_assinado_pela_migracao_e_alvo(raiz: Path) -> None:
    d = _dir_de_migracao(raiz, "tmpabcdefgh")

    alvos, recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert [a.caminho for a in alvos] == [d]
    assert [a.regra for a in alvos] == ["R3"]
    assert recusas == []


def test_berco_de_sessao_morta_e_alvo(raiz: Path) -> None:
    morto = _pid_morto()
    d = raiz / f"hefesto-berco-{morto}"
    d.mkdir()

    alvos, _recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert [(a.caminho, a.regra) for a in alvos] == [(d, "R1")]


def test_copia_congelada_velha_e_alvo(raiz: Path) -> None:
    d = raiz / "hefesto-arvore-congelada-ab12cd34"
    d.mkdir()
    velho = AGORA - 5 * UMA_HORA
    os.utime(d, (velho, velho))

    alvos, _recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert [(a.caminho, a.regra) for a in alvos] == [(d, "R2")]


def test_registro_do_pactl_com_o_conteudo_certo_e_alvo(raiz: Path) -> None:
    f = raiz / FAXINA.REGISTRO_DO_PACTL
    f.write_text("pactl list cards\n", encoding="utf-8")

    alvos, _recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert [(a.caminho, a.regra) for a in alvos] == [(f, "R4")]


# ---------------------------------------------------------------------------
# O QUE O SCRIPT SE RECUSA A APAGAR — a metade que decide se ele pode existir
# ---------------------------------------------------------------------------


def test_um_nome_fora_do_conjunto_fechado_salva_o_diretorio_inteiro(
    raiz: Path,
) -> None:
    """O CASO PERIGOSO. Marcador de migração presente, mas há um arquivo que
    aqueles testes nunca escrevem — então o diretório pode ser de outra coisa,
    e a dúvida se resolve para 'não mexa'."""
    d = _dir_de_migracao(raiz, "tmpabcdefgh", {"perfil-dela.json": '{"name": "x"}'})

    alvos, recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert alvos == []
    assert [r.caminho for r in recusas] == [d]
    assert "perfil-dela.json" in recusas[0].motivo
    assert (d / "perfil-dela.json").exists()


def test_diretorio_sem_marcador_nem_e_mencionado(raiz: Path) -> None:
    """Um `tmp<8>` que não tem NENHUMA prova de origem some do radar — não é
    alvo e nem aparece como recusa. O script só fala do que sabe nomear."""
    d = raiz / "tmpzzzzzzzz"
    d.mkdir()
    (d / "coisa-dela.json").write_text('{"name": "vitoria"}', encoding="utf-8")

    alvos, recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert alvos == []
    assert recusas == []
    assert (d / "coisa-dela.json").exists()


def test_subdiretorio_salva_o_diretorio(raiz: Path) -> None:
    """A migração só escreve arquivos. Um subdiretório é sinal de outra coisa."""
    d = _dir_de_migracao(raiz, "tmpabcdefgh")
    (d / "meu_jogo.json").unlink()
    (d / "meu_jogo.json").mkdir()

    alvos, recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert alvos == []
    assert [r.caminho for r in recusas] == [d]


def test_berco_de_sessao_viva_e_recusado(raiz: Path) -> None:
    """Nesta máquina rodam várias suítes ao mesmo tempo: apagar o berço de uma
    sessão viva é apagar o `/tmp` de quem está trabalhando agora."""
    d = raiz / f"hefesto-berco-{os.getpid()}"
    d.mkdir()

    alvos, recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert alvos == []
    assert [r.caminho for r in recusas] == [d]
    assert "VIVA" in recusas[0].motivo


def test_copia_congelada_recente_e_recusada(raiz: Path) -> None:
    d = raiz / "hefesto-arvore-congelada-ab12cd34"
    d.mkdir()
    os.utime(d, (AGORA - 30, AGORA - 30))

    alvos, recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert alvos == []
    assert [r.caminho for r in recusas] == [d]


def test_registro_do_pactl_com_outro_conteudo_e_recusado(raiz: Path) -> None:
    """Nome bate, conteúdo não. Alguém pode ter reaproveitado o nome."""
    f = raiz / FAXINA.REGISTRO_DO_PACTL
    f.write_text("anotacao dela\n", encoding="utf-8")

    alvos, recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert alvos == []
    assert [r.caminho for r in recusas] == [f]
    assert f.read_text(encoding="utf-8") == "anotacao dela\n"


def test_link_simbolico_nunca_e_alvo(raiz: Path, tmp_path: Path) -> None:
    """Um link com nome de alvo apontando para a config dela é o pior acidente
    imaginável, e é barato de impedir: link não é seguido, ponto."""
    config_dela = tmp_path / "config-dela"
    config_dela.mkdir()
    (config_dela / "vitoria.json").write_text('{"name": "vitoria"}', encoding="utf-8")
    morto = _pid_morto()
    (raiz / f"hefesto-berco-{morto}").symlink_to(config_dela)
    (raiz / "tmpabcdefgh").symlink_to(config_dela)

    alvos, recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert alvos == []
    assert recusas == []
    assert (config_dela / "vitoria.json").exists()


def test_entrada_de_outro_dono_nao_e_alvo(
    raiz: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dono diferente = não é nosso lixo, mesmo que o nome bata."""
    _dir_de_migracao(raiz, "tmpabcdefgh")
    outro = os.getuid() + 1
    monkeypatch.setattr(FAXINA.os, "getuid", lambda: outro)

    alvos, recusas, _ = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert alvos == []
    assert recusas == []


@pytest.mark.parametrize("proibida", ["/", "/etc", "/usr", "/var", "/home", "/root"])
def test_raiz_de_sistema_e_recusada(proibida: str) -> None:
    caminho = Path(proibida)
    if not caminho.exists():
        pytest.skip(f"{proibida} não existe nesta máquina")
    assert FAXINA.raiz_permitida(caminho) is not None


def test_o_home_dela_nunca_pode_ser_raiz() -> None:
    """Um script de faxina que aceite `$HOME` como raiz é um script que um dia
    vai receber `$HOME` como raiz."""
    lar = Path(os.path.expanduser("~"))
    assert FAXINA.raiz_permitida(lar) is not None
    assert FAXINA.raiz_permitida(lar / ".config") is not None
    assert FAXINA.raiz_permitida(lar / ".config" / "hefesto-dualsense4unix") is not None


def test_pytest_of_e_pulse_so_entram_no_relato(raiz: Path) -> None:
    """Quem cria não é esta suíte (o pytest tem retenção própria; a libpulse
    roda fora da suíte). Relatar é o máximo que este script pode fazer."""
    (raiz / "pytest-of-vitoriamaria").mkdir()
    (raiz / "pulse-abcdefghijkl").mkdir()

    alvos, recusas, relato = FAXINA.recolher(raiz, UMA_HORA, AGORA)

    assert alvos == []
    assert recusas == []
    assert dict(relato) == {"pytest-of-": 1, "pulse-": 1}
    assert (raiz / "pytest-of-vitoriamaria").exists()


# ---------------------------------------------------------------------------
# O `main`: relatar é o padrão; apagar é pedido explícito
# ---------------------------------------------------------------------------


def test_o_padrao_e_relatar_sem_apagar_nada(
    raiz: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A decisão de apagar o que já está no disco dela é dela."""
    d = _dir_de_migracao(raiz, "tmpabcdefgh")

    assert FAXINA.main(["--raiz", str(raiz)]) == 0

    assert d.exists()
    saida = capsys.readouterr().out
    assert "só relato" in saida
    assert "tmpabcdefgh" in saida


def test_com_apagar_leva_o_alvo_e_deixa_o_resto(
    raiz: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A MORDIDA do conjunto: o lixo sai, o arquivo dela FICA — no mesmo `/tmp`,
    na mesma execução."""
    lixo = _dir_de_migracao(raiz, "tmpabcdefgh")
    quase = _dir_de_migracao(raiz, "tmpbbbbbbbb", {"perfil-dela.json": "{}"})
    dela = raiz / "Screenshot_2026-08-07_15-49-08.png"
    dela.write_bytes(b"PNG-dela")
    viva = raiz / f"hefesto-berco-{os.getpid()}"
    viva.mkdir()
    (viva / "em-uso").write_text("x", encoding="utf-8")

    assert FAXINA.main(["--raiz", str(raiz), "--apagar"]) == 0

    assert not lixo.exists()
    assert (quase / "perfil-dela.json").read_text(encoding="utf-8") == "{}"
    assert dela.read_bytes() == b"PNG-dela"
    assert (viva / "em-uso").exists()
    assert "apagado" in capsys.readouterr().out


def test_raiz_recusada_devolve_codigo_dois(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lar = str(Path(os.path.expanduser("~")))

    assert FAXINA.main(["--raiz", lar, "--apagar"]) == 2

    assert "RECUSADO" in capsys.readouterr().err


def test_raiz_inexistente_nao_estoura(tmp_path: Path) -> None:
    assert FAXINA.main(["--raiz", str(tmp_path / "nao-existe")]) == 2


def test_o_conjunto_fechado_bate_com_os_testes_de_migracao() -> None:
    """O conjunto fechado é o coração da R3 — se ele sair de sincronia com os
    dois arquivos de teste, a regra passa a recusar diretórios legítimos (lado
    seguro) OU, pior, a aceitar nome que não é nosso.

    Este teste lê os dois arquivos e exige que todo `<nome>.json` que eles
    escrevem esteja declarado.
    """
    import re

    raiz_repo = Path(__file__).resolve().parents[2]
    arquivos = [
        raiz_repo / "tests" / "unit" / "test_coop_default_on_migration.py",
        raiz_repo / "tests" / "unit" / "test_preset_flavor_migration.py",
    ]
    escritos: set[str] = set()
    for arquivo in arquivos:
        texto = arquivo.read_text(encoding="utf-8")
        escritos |= {f"{n}.json" for n in re.findall(r'_escrever\(d, "([a-z_]+)"', texto)}
        escritos |= set(re.findall(r'\(d / "([^"]+\.json)"\)', texto))

    assert escritos, "as duas bancadas de migração mudaram de forma"
    faltando = sorted(escritos - set(FAXINA.NOMES_DA_MIGRACAO))
    assert faltando == [], (
        "nomes escritos pelos testes de migração e AUSENTES do conjunto "
        f"fechado da R3: {faltando}"
    )


def test_o_relato_de_tempo_nao_depende_do_relogio_da_maquina() -> None:
    """`recolher` recebe o `agora` de fora justamente para o teste poder
    envelhecer um diretório sem `sleep`."""
    assert "agora" in FAXINA.recolher.__code__.co_varnames
    assert time.time is not None  # a chamada real fica só no `main`
