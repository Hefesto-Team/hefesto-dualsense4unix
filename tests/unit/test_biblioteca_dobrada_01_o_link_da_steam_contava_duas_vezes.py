"""BIBLIOTECA-DOBRADA-01 (16/08/2026) — o link da Steam contava tudo em dobro.

**Como apareceu.** Escrevendo o censo de prontidão dos jogos, a primeira
execução na máquina dela imprimiu **65 jogos instalados** — e a biblioteca tem
**33 `appmanifest`**. Cada jogo saiu duas vezes, com tempos de leitura
diferentes, o que descarta erro de impressão: os arquivos foram MESMO lidos duas
vezes.

**A causa.** `pastas_steamapps()` monta a lista com a `steamapps` da raiz padrão
e acrescenta as do `libraryfolders.vdf`, pulando repetida com ``not in pastas``
— que compara TEXTO de caminho. Nesta máquina::

    ~/.steam/steam            -> link para ~/.steam/debian-installation
    libraryfolders.vdf        -> lista  ~/.steam/debian-installation

Dois textos diferentes, um diretório só. A lista saía com três entradas para
duas pastas de verdade.

**Por que ninguém tinha percebido.** Os dois consumidores da época não erravam a
conta, por sorte de forma: `nome_do_appid` para no primeiro achado, e
`jogos_da_biblioteca_steam` faz `setdefault` por appid. O defeito estava armado
esperando o próximo consumidor — e o próximo consumidor era um CENSO, o tipo de
código cujo produto é justamente um número.

**Por que isto vira teste, e não só um `resolve()`.** É a mesma família do
`WRAPPER-EM-TODOS-01`, o portão que passou a noite verde com o Pragmata
quebrado: um número que parece cobertura e não é. Um censo que diz "65 jogos
medidos" quando mediu 33 duas vezes mente na direção mais cara — a de parecer
mais completo do que é.

Este arquivo trava a fonte, e não cada consumidor: pasta repetida não sai de
`pastas_steamapps()`, mesmo quando os caminhos têm nomes diferentes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.jogos_locais import jogos_da_biblioteca_steam
from hefesto_dualsense4unix.integrations.steam_launch_options import (
    nome_do_appid,
    pastas_steamapps,
)


def _manifest(steamapps: Path, appid: str, nome: str) -> None:
    """O `appmanifest_<appid>.acf` como a Steam o escreve (tabs literais)."""
    steamapps.mkdir(parents=True, exist_ok=True)
    (steamapps / f"appmanifest_{appid}.acf").write_text(
        '"AppState"\n{\n'
        f'\t"appid"\t\t"{appid}"\n'
        f'\t"name"\t\t"{nome}"\n'
        f'\t"installdir"\t\t"{nome.replace(" ", "")}"\n'
        "}\n",
        encoding="utf-8",
    )


def _libraryfolders(steamapps: Path, caminhos: list[Path]) -> None:
    """O `libraryfolders.vdf`, cujo `path` aponta a RAIZ (sem `steamapps`)."""
    blocos = "".join(
        f'\t"{i}"\n\t{{\n\t\t"path"\t\t"{p}"\n\t}}\n'
        for i, p in enumerate(caminhos)
    )
    (steamapps / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n{blocos}}}\n', encoding="utf-8"
    )


@pytest.fixture()
def casa_com_link(tmp_path: Path) -> Path:
    """A forma REAL da máquina dela: `.steam/steam` é link, e o vdf cita o alvo.

    Reproduzida a partir do que foi medido em 16/08/2026 — não é hipótese de
    laboratório, é o layout que a instalação Debian da Steam deixa.
    """
    real = tmp_path / ".steam/debian-installation"
    (real / "steamapps").mkdir(parents=True)
    (tmp_path / ".steam/steam").symlink_to(real, target_is_directory=True)

    steamapps = tmp_path / ".steam/steam/steamapps"
    _manifest(steamapps, "2542020", "Duskfade")
    _manifest(steamapps, "2497900", "DONT SCREAM")
    _libraryfolders(steamapps, [real])
    return tmp_path


class TestAPastaNaoSaiRepetida:
    def test_o_link_e_o_alvo_valem_por_uma_pasta_so(self, casa_com_link: Path) -> None:
        """A MORDIDA. Sem a comparação por diretório real, aqui saem 2."""
        pastas = pastas_steamapps(casa_com_link)
        assert len(pastas) == 1, [str(p) for p in pastas]

    def test_o_caminho_devolvido_e_o_primeiro_visto_nao_o_resolvido(
        self, casa_com_link: Path
    ) -> None:
        """O texto que aparece na mensagem de erro continua o do link.

        Resolver a lista inteira seria a cura preguiçosa: trocaria
        `~/.steam/steam` por `~/.steam/debian-installation` em todo relatório, e
        ela reconhece o primeiro.
        """
        (pasta,) = pastas_steamapps(casa_com_link)
        assert pasta == casa_com_link / ".steam/steam/steamapps"

    def test_biblioteca_de_verdade_em_outro_disco_continua_entrando(
        self, casa_com_link: Path
    ) -> None:
        """Deduplicar não pode virar "só a primeira pasta"."""
        outro = casa_com_link / "mnt/Disco2"
        (outro / "steamapps").mkdir(parents=True)
        _manifest(outro / "steamapps", "3357650", "PRAGMATA")
        _libraryfolders(
            casa_com_link / ".steam/steam/steamapps",
            [casa_com_link / ".steam/debian-installation", outro],
        )

        pastas = pastas_steamapps(casa_com_link)
        assert len(pastas) == 2, [str(p) for p in pastas]
        assert outro / "steamapps" in pastas

    def test_biblioteca_inexistente_no_vdf_e_pulada(self, casa_com_link: Path) -> None:
        """Disco desmontado é comum, e não pode derrubar nem duplicar nada."""
        _libraryfolders(
            casa_com_link / ".steam/steam/steamapps",
            [casa_com_link / ".steam/debian-installation", Path("/mnt/nao-montado")],
        )
        assert len(pastas_steamapps(casa_com_link)) == 1


class TestQuemContaNaoContaEmDobro:
    def test_o_catalogo_lista_cada_jogo_uma_vez(self, casa_com_link: Path) -> None:
        jogos = jogos_da_biblioteca_steam(casa_com_link)
        assert [j.appid for j in jogos] == sorted({j.appid for j in jogos})
        assert len(jogos) == 2

    def test_varrer_as_pastas_a_mao_ve_cada_manifest_uma_vez(
        self, casa_com_link: Path
    ) -> None:
        """O gesto que ERROU: iterar as pastas e ler os `.acf` sem deduplicar.

        É este o consumidor que o defeito esperava. Ele não pode precisar saber
        que a fonte pode repetir — a fonte é que não repete.
        """
        vistos = [
            acf.name
            for pasta in pastas_steamapps(casa_com_link)
            for acf in sorted(pasta.glob("appmanifest_*.acf"))
        ]
        assert sorted(vistos) == [
            "appmanifest_2497900.acf",
            "appmanifest_2542020.acf",
        ]


class TestOQueJaFuncionavaContinua:
    def test_traducao_de_appid_em_nome(self, casa_com_link: Path) -> None:
        assert nome_do_appid("2542020", casa_com_link) == "Duskfade"

    def test_jogo_ausente_continua_devolvendo_none(self, casa_com_link: Path) -> None:
        assert nome_do_appid("9999999", casa_com_link) is None

    def test_casa_sem_steam_nenhuma_nao_levanta(self, tmp_path: Path) -> None:
        """Máquina sem Steam: uma pasta inexistente, e silêncio."""
        assert len(pastas_steamapps(tmp_path)) == 1
        assert nome_do_appid("2542020", tmp_path) is None
