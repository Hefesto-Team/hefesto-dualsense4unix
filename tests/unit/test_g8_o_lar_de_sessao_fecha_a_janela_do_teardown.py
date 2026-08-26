"""LAR-DE-SESSAO-01 — o isolamento tem de sobreviver ao teardown (G8).

O DEFEITO, medido no disco DELA em 25/08/2026: quatro endereços da faixa de
fixture `aa:bb:cc:00:00:0{1..4}` moravam no `controllers.json` de PRODUÇÃO,
ocupando os postos 2 a 5 e empurrando os DualSense REAIS para 6, 7 e 8 —
`core/led_control.py` só tem cor de PS5 para 1..4, então dois dos controles
dela ficaram sem cor de jogador. É REINCIDÊNCIA: o
`backup-limpeza-20260811-233704/controllers.json` já trazia forjados em 11/08.

O MECANISMO que o forense nomeou:

  1. `identity._path()` resolve o caminho na hora do SAVE, não no import;
  2. o isolamento de `XDG_CONFIG_HOME`/`HOME` é `monkeypatch` de escopo de
     FUNÇÃO (`_hefesto_fake_env`), e o teardown dele DEVOLVE o valor de antes
     do teste — que é o `~/.config` dela;
  3. logo, qualquer escrita DEPOIS do teardown (finalizador, `atexit`, thread,
     subprocesso, singleton que atravessa os casos) cai na mesa dela.

A CURA, no `tests/conftest.py`: o `pytest_sessionstart` desvia `HOME` e os
quatro `XDG_*` para um lar de MENTIRA da sessão inteira, ANTES da coleta. O
teardown de escopo de função passa a desfazer PARA o dublê.

AS TRÊS RÉGUAS DESTE ARQUIVO, e cada uma pega uma coisa diferente:

  RÉGUA 1 (`TestOAmbienteDeForaDoCaso`) — o valor que o teardown REPÕE é o
  dublê. É a cura em uma asserção, e custa zero.

  RÉGUA 2 (`TestAEscritaTardiaNaoAlcancaAMesa`) — o fim a fim, num pytest
  ANINHADO com um `$HOME` de mentira no lugar da mesa dela. Ela roda a MORDIDA
  nos dois sentidos dentro do próprio caso: com `HEFESTO_SEM_LAR_DE_SESSAO=1`
  o vazamento VOLTA a acontecer (e o teste exige que volte — régua que só sabe
  passar não é régua), e sem a escotilha ele não acontece.

  RÉGUA 3 (`TestOSingletonNaoAtravessa`) — dois casos em sequência provam que
  `identity._registry` não carrega o que o caso anterior pôs nele. Foi esse
  acúmulo que juntou os QUATRO endereços que nenhum arquivo de teste junta
  sozinho.

A faixa usada aqui é `e8:47:3a`, não `aa:bb:cc`: a `aabbcc` está fechada para
teste NOVO desde 23/08 (é a faixa que vazou), e a `e8473a` já é allowlist
declarada em `test_anonimato_de_fixtures.py`.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests import conftest as berco

#: Endereço de fixture desta régua. Faixa sintética da casa, sem fabricante.
UNIQ_DA_REGUA = "e8473a0000f1"

#: O que a régua 2 procura na mesa de mentira. Dois arquivos: o do produto
#: (`controllers.json`, que `_save_locked` grava e que engole exceção) e um
#: marcador CRU. O marcador existe porque `_save_locked` nunca propaga erro —
#: sem ele, um `_save_locked` que falhasse por outro motivo faria a régua
#: declarar "curado" sem ter medido nada.
NOME_DO_MARCADOR = "prova-de-escrita-tardia.txt"

#: O arquivo que JÁ mora na mesa de mentira quando o ninho começa — o que
#: faz dela a mesa DELA, e não um diretório inexistente.
NOME_DA_FILA_DELA = "a-fila-que-ja-estava-la.json"


@pytest.fixture(scope="session")
def repo() -> Path:
    """A raiz do repositório, achada pelo próprio conftest que está em teste."""
    return Path(berco.__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def ambiente_de_fora_do_caso() -> dict[str, str | None]:
    """As cinco variáveis COMO ELAS ESTÃO fora de todo patch de função.

    O escopo de SESSÃO não é economia: é a régua. Fixture de sessão monta
    antes de qualquer fixture de escopo de função, então o que se lê aqui é
    exatamente o valor que o `monkeypatch` do `_hefesto_fake_env` repõe no
    teardown de CADA caso — que é o valor por onde o vazamento saía.
    """
    return {var: os.environ.get(var) for var, _sub in berco._VARS_DO_LAR}


class TestOAmbienteDeForaDoCaso:
    """RÉGUA 1 — para ONDE o teardown de escopo de função desfaz."""

    def test_o_lar_de_sessao_esta_armado(self) -> None:
        assert berco.lar_de_sessao() is not None, (
            "LAR-DE-SESSAO-01 não armou. Sem ele, o teardown do "
            "`_hefesto_fake_env` devolve `HOME`/`XDG_CONFIG_HOME` para o "
            "`~/.config` REAL de quem roda a suíte, e toda escrita tardia cai "
            "na mesa dela. Escotilha: " + berco._LAR_DESLIGADO_ENV + "=1."
        )

    def test_o_valor_que_o_teardown_repoe_e_o_duble(
        self, ambiente_de_fora_do_caso: dict[str, str | None]
    ) -> None:
        """As cinco variáveis, vistas FORA de qualquer patch de função.

        A fixture é de escopo de SESSÃO, e é isso que a torna a régua certa:
        fixture de sessão monta antes de toda fixture de função, então o que
        ela lê é exatamente o valor para o qual o `monkeypatch` do
        `_hefesto_fake_env` vai desfazer no fim de cada caso.
        """
        lar = berco.lar_de_sessao()
        assert lar is not None
        for var, valor in ambiente_de_fora_do_caso.items():
            assert valor is not None, f"{var} não está no ambiente de fora do caso"
            assert Path(valor).is_relative_to(lar), (
                f"{var}={valor} cai FORA do lar de mentira ({lar}). É para "
                "AQUI que o teardown de cada teste desfaz — se cair na casa "
                "de quem roda, o vazamento de 21/08 volta inteiro."
            )

    def test_o_lar_real_continua_conhecido(self) -> None:
        """`lar_real()` tem de devolver o `$HOME` de ANTES do desvio.

        Não é conforto: o `_hefesto_fake_env` aponta `RUSTUP_HOME`/`CARGO_HOME`
        para ele, e sem isso o `cargo` de verdade recusa com "no default
        toolchain configured" (medido em 24/08).
        """
        real = berco.lar_real()
        lar = berco.lar_de_sessao()
        assert lar is not None
        assert not real.is_relative_to(lar), (
            f"`lar_real()` devolveu {real}, que é o próprio dublê — o desvio "
            "comeu a memória do `$HOME` de verdade."
        )
        assert real == Path(berco._LAR_ENV_ANTES["HOME"] or "")


class TestOEspelhoNaoEUmDiretorioVazio:
    """O dublê ESPELHA a casa dela, e só os quatro do produto nascem vazios.

    Um lar de mentira vazio fechava o vazamento e QUEBRAVA quatro testes de
    layout: o GTK e o fontconfig leem `~/.config/gtk-3.0/settings.ini` no
    `Gtk.init()`, que roda na importação dos módulos — depois do desvio —, e
    sem os ajustes de fonte dela as larguras medidas em pixel mudam. Medido em
    25/08/2026, `test_layout_orcamento_altura.py` (3) e
    `test_status_som_02_controle_de_volume.py` (1).

    As duas metades têm de valer JUNTAS, e é por isso que este caso mede as
    duas: se o produto virar symlink, a escrita tardia atravessa e chega ao
    disco dela; se o vizinho deixar de ser symlink, o GTK perde os ajustes.
    """

    def test_o_que_o_produto_escreve_nasce_vazio_e_nao_e_symlink(
        self, tmp_path: Path
    ) -> None:
        casa = tmp_path / "casa"
        (casa / ".config" / "hefesto-dualsense4unix").mkdir(parents=True)
        (casa / ".config" / "hefesto-dualsense4unix" / "controllers.json").write_text(
            "{}", encoding="utf-8"
        )
        (casa / ".local" / "share" / "hefesto-dualsense4unix").mkdir(parents=True)
        duble = tmp_path / "duble"

        berco._espelhar_o_lar(casa, duble)

        for folha in berco._DIRS_DO_PRODUTO:
            alvo = duble.joinpath(*folha)
            assert alvo.is_dir(), f"{folha} não nasceu no dublê"
            assert not alvo.is_symlink(), (
                f"{'/'.join(folha)} virou SYMLINK para a casa dela — toda "
                "escrita tardia do produto atravessa o link e chega ao disco "
                "de verdade. É o vazamento inteiro, por outra porta."
            )
            assert list(alvo.iterdir()) == [], (
                f"{'/'.join(folha)} nasceu com conteúdo; o dublê tem de ser "
                "uma mesa limpa, senão a suíte lê a fila REAL dela."
            )

    def test_o_que_nao_e_do_produto_entra_por_symlink(self, tmp_path: Path) -> None:
        casa = tmp_path / "casa"
        (casa / ".config" / "gtk-3.0").mkdir(parents=True)
        ajuste = casa / ".config" / "gtk-3.0" / "settings.ini"
        ajuste.write_text("[Settings]\n", encoding="utf-8")
        (casa / ".gitconfig").write_text("[user]\n", encoding="utf-8")
        duble = tmp_path / "duble"

        berco._espelhar_o_lar(casa, duble)

        assert (duble / ".gitconfig").is_symlink()
        assert (duble / ".config" / "gtk-3.0").is_symlink(), (
            "o `gtk-3.0` dela deixou de ser espelhado — o `Gtk.init()` da "
            "coleta perde os ajustes de fonte e as medidas em pixel dos testes "
            "de layout mudam debaixo de quem não mexeu em nada."
        )
        assert (duble / ".config" / "gtk-3.0" / "settings.ini").read_text(
            encoding="utf-8"
        ) == "[Settings]\n"
        assert not (duble / ".config").is_symlink(), (
            "`.config` inteiro virou link: o `hefesto-dualsense4unix` de "
            "dentro dele passou a ser o dela."
        )


class TestARecusaDoInstrumento:
    """O dublê tem de saber DIZER NÃO — régua que só passa não é régua."""

    def test_o_ambiente_real_nao_volta_para_sessao_de_mentira(self) -> None:
        """Uma Session que não armou o desvio não pode desfazê-lo.

        `test_conftest_canario_fs.py` chama `pytest_sessionfinish` com uma
        Session forjada, de propósito, para provar que o canário reprova. Sem
        esta recusa, a primeira dessas chamadas devolveria o `$HOME` REAL no
        meio da sessão VIVA — e a partir dali todo teste seguinte gravaria na
        mesa dela. É o mesmo defeito que o `_SESSAO_REAL` do berço já pagou.
        """
        lar = berco.lar_de_sessao()
        assert lar is not None
        antes = os.environ.get("HOME")

        class SessaoDeMentira:
            pass

        with berco._com_o_ambiente_real(SessaoDeMentira()):
            durante = os.environ.get("HOME")

        assert durante == antes, (
            "`_com_o_ambiente_real` aceitou uma Session que não armou o "
            f"desvio e trocou o HOME para {durante}."
        )

    def test_o_ambiente_real_volta_para_a_sessao_dona(
        self, request: pytest.FixtureRequest
    ) -> None:
        """E, com a Session DONA, ele volta mesmo — senão o canário cega.

        O CANARIO-FS-01 e a FAIXA-NO-BERCO-01 resolvem os alvos contra o `HOME`
        VIVO. Se o dublê continuasse de pé enquanto eles medem, a foto do FIM
        seria de outra árvore que a do INÍCIO: o canário acusaria o `$HOME`
        inteiro de ter sumido, e a faixa ficaria calada para sempre.
        """
        lar = berco.lar_de_sessao()
        assert lar is not None
        dona = request.session
        if id(dona) not in berco._SESSAO_DO_LAR:  # pragma: no cover
            pytest.skip("esta sessão não é a que armou o desvio")
        with berco._com_o_ambiente_real(dona):
            durante = Path(os.environ["HOME"])
        assert durante == berco.lar_real()
        assert Path(os.environ["HOME"]).is_relative_to(lar), (
            "o dublê não voltou ao sair do `with` — a janela tardia reabriu."
        )

    def test_lar_orfao_de_pid_vivo_nao_e_varrido(self, tmp_path: Path) -> None:
        """A varredura é por pid MORTO. O lar de uma sessão viva fica."""
        vivo = tmp_path / f"{berco._LAR_PREFIXO}{os.getpid()}"
        vivo.mkdir()
        morto = tmp_path / f"{berco._LAR_PREFIXO}999999999"
        morto.mkdir()
        nao_e_lar = tmp_path / "hefesto-lar-de-sessao-sem-pid"
        nao_e_lar.mkdir()

        orfaos = berco._lares_orfaos(tmp_path)

        assert morto in orfaos
        assert vivo not in orfaos, (
            "a varredura levaria o lar de uma sessão VIVA — dois pytest em "
            "paralelo (é o que uma leva de agentes faz) e um apaga o outro."
        )
        assert nao_e_lar not in orfaos


class TestOSingletonNaoAtravessa:
    """RÉGUA 3 — `identity._registry` morre com o caso que o criou.

    Os dois casos abaixo dependem da ORDEM (pytest roda na ordem de
    declaração), e é essa dependência que é o ponto: o primeiro suja, o
    segundo prova que a sujeira não passou.
    """

    def test_a_um_semeia_o_singleton(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.identity import (
            get_identity_registry,
        )

        registro = get_identity_registry()
        registro.slot_for(UNIQ_DA_REGUA)
        assert registro.slot_for(UNIQ_DA_REGUA, assign=False) is not None

    def test_a_dois_nao_herda_o_que_o_a_um_semeou(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.identity import (
            get_identity_registry,
        )

        registro = get_identity_registry()
        assert registro.slot_for(UNIQ_DA_REGUA, assign=False) is None, (
            "o singleton `identity._registry` atravessou o caso anterior. É "
            "esse acúmulo que junta os QUATRO endereços de fixture que nenhum "
            "arquivo de teste junta sozinho — o primeiro save depois do "
            "teardown grava a fila inteira de uma vez. A cura é a fixture "
            "`_nenhum_registro_de_identidade_atravessa` do conftest."
        )


#: O teste ANINHADO. Ele semeia a fila e agenda a gravação para o `atexit`, que
#: é a escrita mais tardia que existe num processo Python — depois de todo
#: teardown, de todo `sessionfinish`, de todo finalizador de fixture.
_NINHO = '''
import atexit

UNIQ = "{uniq}"
MARCADOR = "{marcador}"


def _gravar_depois_de_tudo(registro):
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    registro._save_locked()
    # O marcador é CRU de propósito: `_save_locked` engole exceção por
    # contrato, então sem ele um erro qualquer pareceria cura.
    (config_dir(ensure=True) / MARCADOR).write_text(UNIQ + chr(10), encoding="utf-8")


def test_semeia_a_fila_e_agenda_a_escrita_tardia():
    from hefesto_dualsense4unix.daemon.subsystems.identity import (
        get_identity_registry,
    )

    registro = get_identity_registry()
    assert registro.slot_for(UNIQ) is not None
    atexit.register(_gravar_depois_de_tudo, registro)
'''


def _rodar_o_ninho(
    tmp_path: Path, repo: Path, *, com_a_cura: bool
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    """Um pytest ANINHADO com um `$HOME` de mentira no lugar da mesa dela.

    O `conftest.py` entra por SYMLINK, e não por cópia: o conftest resolve
    `Path(__file__).resolve().parents[1]` para achar `scripts/`, e `resolve()`
    segue o link — uma cópia apontaria para o diretório temporário e o pedaço
    da FAIXA-NO-BERCO-01 ficaria mudo dentro do próprio teste que o mede.
    """
    quintal = tmp_path / ("com-a-cura" if com_a_cura else "sem-a-cura")
    quintal.mkdir()
    (quintal / "conftest.py").symlink_to(repo / "tests" / "conftest.py")
    (quintal / "test_ninho.py").write_text(
        textwrap.dedent(_NINHO).format(uniq=UNIQ_DA_REGUA, marcador=NOME_DO_MARCADOR),
        encoding="utf-8",
    )
    # A mesa de mentira nasce COMO A DELA: com o diretório do produto já lá e
    # um arquivo dentro. Não é enfeite — foi medido em 25/08/2026 que uma mesa
    # sem esse diretório NÃO exercita o ramo do espelho que decide entre
    # symlink e dublê, e a régua ficava verde mesmo com o produto virando link
    # para o disco de verdade. Régua que só sabe passar não é régua.
    mesa = tmp_path / ("mesa-com" if com_a_cura else "mesa-sem")
    (mesa / ".config" / "hefesto-dualsense4unix").mkdir(parents=True)
    (mesa / ".config" / "hefesto-dualsense4unix" / NOME_DA_FILA_DELA).write_text(
        '{"version": 1}\n', encoding="utf-8"
    )

    ambiente = dict(os.environ)
    ambiente["HOME"] = str(mesa)
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        ambiente.pop(var, None)
    ambiente["PYTHONPATH"] = str(repo / "src")
    ambiente["PYTEST_ADDOPTS"] = ""
    # O canário do ninho compararia a mesa de mentira consigo mesma; desligá-lo
    # tira ruído sem tirar régua nenhuma desta medição.
    ambiente["HEFESTO_SEM_CANARIO_FS"] = "1"
    if com_a_cura:
        ambiente.pop(berco._LAR_DESLIGADO_ENV, None)
    else:
        ambiente[berco._LAR_DESLIGADO_ENV] = "1"

    saida = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_ninho.py"],
        cwd=str(quintal),
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return mesa, saida


def _nasceram_na_mesa(mesa: Path) -> list[str]:
    """O que NASCEU no `~/.config` da mesa de mentira durante o ninho.

    O arquivo que já estava lá antes fica de fora: a pergunta é "apareceu
    coisa nova?", e não "existe coisa?" — a mesa dela nunca está vazia.
    """
    raiz = mesa / ".config" / "hefesto-dualsense4unix"
    if not raiz.is_dir():
        return []
    return sorted(
        str(p.relative_to(mesa))
        for p in raiz.rglob("*")
        if p.is_file() and p.name != NOME_DA_FILA_DELA
    )


class TestAEscritaTardiaNaoAlcancaAMesa:
    """RÉGUA 2 — o fim a fim, e a MORDIDA nos dois sentidos.

    Custa dois pytest aninhados de UM arquivo cada. É o único instrumento
    daqui que exercita a cadeia inteira — `sessionstart`, coleta, teste,
    teardown, `sessionfinish` e `atexit` —, e é a cadeia inteira que falhou.
    """

    def test_sem_a_cura_a_escrita_tardia_alcanca_a_mesa(
        self, tmp_path: Path, repo: Path
    ) -> None:
        """A MORDIDA. Com a escotilha ligada, o vazamento volta a acontecer.

        Se este caso ficar VERDE-por-ausência (nada na mesa), a régua irmã
        abaixo não prova nada: ela estaria medindo um vazamento que já não
        existe por outro motivo qualquer.
        """
        mesa, saida = _rodar_o_ninho(tmp_path, repo, com_a_cura=False)
        assert saida.returncode == 0, saida.stdout + saida.stderr
        rastros = _nasceram_na_mesa(mesa)
        assert any(NOME_DO_MARCADOR in r for r in rastros), (
            "com " + berco._LAR_DESLIGADO_ENV + "=1 a escrita tardia deveria "
            f"ter alcançado a mesa e não alcançou. Achados: {rastros}. Sem "
            "este vermelho, a régua irmã é um verde vazio."
        )

    def test_com_a_cura_a_escrita_tardia_cai_no_duble(
        self, tmp_path: Path, repo: Path
    ) -> None:
        """E com a cura ligada, a mesma escrita não encosta na mesa."""
        mesa, saida = _rodar_o_ninho(tmp_path, repo, com_a_cura=True)
        assert saida.returncode == 0, saida.stdout + saida.stderr
        rastros = _nasceram_na_mesa(mesa)
        assert rastros == [], (
            "a suíte gravou no `~/.config` de quem a roda DEPOIS do teardown: "
            f"{rastros}. É o defeito de 21/08 inteiro — quatro endereços de "
            "fixture na fila dela, os DualSense reais empurrados para os "
            "postos 6, 7 e 8, e dois deles sem cor de jogador."
        )


class TestOCabecalhoRelataAMesaParada:
    """O `--casa` do `check_faixa_sintetica.py` ganhou chamador.

    Até 25/08 o `~/.config` REAL não era olhado por instrumento nenhum em
    estado PARADO: `scripts/portoes.sh` só roda o `--arvore`, e a
    FAIXA-NO-BERCO-01 é DELTA — cega para a sujeira que já estava lá quando a
    sessão começou. Foi essa cegueira que deixou quatro forjados morarem na
    fila dela de 22/08 a 25/08 sem ninguém ver.
    """

    def test_o_cabecalho_diz_quantos_ja_moram_la(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            berco,
            "_FAIXA_NO_INICIO",
            {f"{tmp_path}/controllers.json::{UNIQ_DA_REGUA}"},
        )
        monkeypatch.setattr(berco, "_FAIXA_DIR_REAL", [tmp_path])

        linhas = berco.pytest_report_header(None)

        assert any("faixa-no-berco-01" in linha for linha in linhas), linhas
        assert any("--casa" in linha for linha in linhas), (
            "o cabeçalho relata a contagem mas não diz o comando que lista "
            "QUAIS — o número sozinho não dá o que fazer com ele. " + str(linhas)
        )

    def test_mesa_limpa_nao_ganha_linha_nenhuma(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Relato só quando há o que relatar — linha fixa vira ruído fixo."""
        monkeypatch.setattr(berco, "_FAIXA_NO_INICIO", set())
        linhas = berco.pytest_report_header(None)
        assert not any("faixa-no-berco-01" in linha for linha in linhas), linhas
