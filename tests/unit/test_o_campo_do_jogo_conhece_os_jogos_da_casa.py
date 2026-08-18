"""JOGO-QUE-SE-DIZ-01 — a lista dos jogos que JÁ estão nesta máquina.

Pedido dela, 13/08/2026: *"ou ele pré-apresenta os nomes dos jogos em .desktop
localmente instalados no pc, dessa forma ao digitar o nome do jogo ele
apareceria ali."*

**A biblioteca aqui é de MENTIRA, montada em `tmp_path`.** Ler a dela num teste
faria o resultado depender do que ela instalou hoje — e o portão de dados de
teste desta casa proíbe caminho pessoal em teste. Os nomes usados são
inventados de propósito.

A mordida está escrita no fim do arquivo: arrancar a leitura do `.acf` (o
`glob("appmanifest_*.acf")` de `jogos_da_biblioteca_steam`) faz
`test_a_lista_nasce_da_biblioteca_steam` reprovar dizendo que a lista veio
VAZIA, e leva junto o teste da fiação da janela.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.jogos_locais import (
    MSG_FORA_DA_MAQUINA,
    MSG_NAO_RECONHECI,
    JogoLocal,
    casa_com_o_que_ela_digitou,
    catalogo_de_jogos,
    chave_de_busca,
    e_ferramenta_da_steam,
    frase_do_campo_do_jogo,
    jogos_da_biblioteca_steam,
    jogos_dos_atalhos_desktop,
    nomes_por_appid,
)

#: Os jogos da biblioteca falsa: (appid, nome). Nomes inventados.
JOGOS_FALSOS: list[tuple[str, str]] = [
    ("851100", "Mar de Estrelas"),
    ("1599660", "Saco de Aventura™: O Retorno"),
    ("2111190", "Café Cósmico"),
]

#: O que a Steam instala como se fosse jogo, e a lista dela não pode mostrar.
FERRAMENTAS_FALSAS: list[tuple[str, str]] = [
    ("1493710", "Proton Experimental"),
    ("2180100", "Proton Hotfix"),
    ("3658110", "Proton 10.0"),
    ("1628350", "Steam Linux Runtime 3.0 (sniper)"),
    ("228980", "Steamworks Common Redistributables"),
]

#: O jogo que só existe como atalho `.desktop` — o caso que a fonte 2 cobre.
SO_NO_ATALHO = ("321000", "Jogo Sem Manifesto")


def _escrever_acf(steamapps: Path, appid: str, nome: str) -> None:
    steamapps.mkdir(parents=True, exist_ok=True)
    (steamapps / f"appmanifest_{appid}.acf").write_text(
        '"AppState"\n'
        "{\n"
        f'\t"appid"\t\t"{appid}"\n'
        '\t"universe"\t\t"1"\n'
        f'\t"name"\t\t"{nome}"\n'
        '\t"StateFlags"\t\t"4"\n'
        '\t"InstalledDepots"\n'
        "\t{\n"
        f'\t\t"{appid}1"\n'
        "\t\t{\n"
        '\t\t\t"manifest"\t\t"1234567890123456789"\n'
        "\t\t}\n"
        "\t}\n"
        "}\n",
        encoding="utf-8",
    )


def _escrever_desktop(pasta: Path, arquivo: str, nome: str, appid: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / arquivo).write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={nome}\n"
        f"Exec=steam steam://rungameid/{appid}\n"
        "Icon=steam\n"
        "Terminal=false\n"
        "Categories=Game;\n",
        encoding="utf-8",
    )


@pytest.fixture
def casa_de_mentira(tmp_path: Path) -> Path:
    """Uma máquina inteira de mentira: duas bibliotecas Steam e uma de atalhos.

    A segunda biblioteca entra pelo `libraryfolders.vdf`, que é como a Steam
    registra disco extra — sem ela o teste não cobriria o caminho que na
    máquina dela guarda um jogo de 150 GB.
    """
    principal = tmp_path / ".steam" / "steam" / "steamapps"
    extra = tmp_path / "OutroDisco" / "SteamLibrary" / "steamapps"
    for appid, nome in JOGOS_FALSOS[:2]:
        _escrever_acf(principal, appid, nome)
    for appid, nome in FERRAMENTAS_FALSAS:
        _escrever_acf(principal, appid, nome)
    _escrever_acf(extra, *JOGOS_FALSOS[2])

    (principal / "libraryfolders.vdf").write_text(
        '"libraryfolders"\n'
        "{\n"
        '\t"0"\n'
        "\t{\n"
        f'\t\t"path"\t\t"{tmp_path / ".steam" / "steam"}"\n'
        "\t}\n"
        '\t"1"\n'
        "\t{\n"
        f'\t\t"path"\t\t"{tmp_path / "OutroDisco" / "SteamLibrary"}"\n'
        "\t}\n"
        "}\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def atalhos_de_mentira(tmp_path: Path) -> Path:
    pasta = tmp_path / "atalhos"
    appid_orfao, nome_orfao = SO_NO_ATALHO
    _escrever_desktop(pasta, "jogo-sem-manifesto.desktop", nome_orfao, appid_orfao)
    # O atalho de um jogo que TAMBÉM está na biblioteca, com o nome cortado —
    # medido na máquina dela: `Name=ORPHEUS` para `ORPHEUS: TO HELL AND BACK`.
    _escrever_desktop(pasta, "cafe.desktop", "Café", "2111190")
    # Um atalho que o menu não mostra não entra na lista dela.
    (pasta / "escondido.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Escondido\n"
        "Exec=steam steam://rungameid/999999\nNoDisplay=true\n",
        encoding="utf-8",
    )
    return pasta


class TestABibliotecaDeMentira:
    def test_a_lista_nasce_da_biblioteca_steam(self, casa_de_mentira: Path) -> None:
        """A MORDIDA: sem a leitura do `.acf`, esta lista vem vazia."""
        jogos = jogos_da_biblioteca_steam(home=casa_de_mentira)
        nomes = sorted(j.nome for j in jogos)
        assert jogos, (
            "a lista dos jogos desta máquina veio VAZIA — a leitura dos "
            "appmanifest_*.acf é o que a alimenta"
        )
        assert nomes == [
            "Café Cósmico",
            "Mar de Estrelas",
            "Saco de Aventura™: O Retorno",
        ]

    def test_a_biblioteca_extra_do_libraryfolders_entra(
        self, casa_de_mentira: Path
    ) -> None:
        """O jogo do segundo disco não pode ficar de fora da lista."""
        appids = {j.appid for j in jogos_da_biblioteca_steam(home=casa_de_mentira)}
        assert "2111190" in appids

    def test_proton_e_runtime_nao_sao_jogos(self, casa_de_mentira: Path) -> None:
        nomes = {j.nome for j in jogos_da_biblioteca_steam(home=casa_de_mentira)}
        for _appid, ferramenta in FERRAMENTAS_FALSAS:
            assert ferramenta not in nomes

    def test_a_mesma_biblioteca_listada_duas_vezes_nao_duplica(
        self, casa_de_mentira: Path
    ) -> None:
        """O `libraryfolders.vdf` desta casa aponta para a pasta padrão.

        É o caso REAL da máquina dela (`~/.steam/steam` -> `debian-installation`):
        sem resolver o caminho, a mesma biblioteca é varrida duas vezes.
        """
        jogos = jogos_da_biblioteca_steam(home=casa_de_mentira)
        appids = [j.appid for j in jogos]
        assert len(appids) == len(set(appids))

    def test_maquina_sem_steam_devolve_lista_vazia_em_silencio(
        self, tmp_path: Path
    ) -> None:
        """Degradar calado é requisito: o campo continua aceitando o número."""
        assert jogos_da_biblioteca_steam(home=tmp_path / "nao-existe") == []


class TestOsAtalhosDesktop:
    def test_le_o_rungameid_do_exec(self, atalhos_de_mentira: Path) -> None:
        achados = jogos_dos_atalhos_desktop([atalhos_de_mentira])
        por_id = {j.appid: j.nome for j in achados}
        assert por_id["321000"] == "Jogo Sem Manifesto"

    def test_atalho_que_o_menu_esconde_fica_de_fora(
        self, atalhos_de_mentira: Path
    ) -> None:
        appids = {j.appid for j in jogos_dos_atalhos_desktop([atalhos_de_mentira])}
        assert "999999" not in appids

    def test_pasta_que_nao_existe_nao_derruba_nada(self, tmp_path: Path) -> None:
        assert jogos_dos_atalhos_desktop([tmp_path / "nao-existe"]) == []


class TestOCatalogoInteiro:
    def test_as_duas_fontes_entram_e_a_steam_desempata(
        self, casa_de_mentira: Path, atalhos_de_mentira: Path
    ) -> None:
        catalogo = catalogo_de_jogos(
            home=casa_de_mentira, pastas_de_atalhos=[atalhos_de_mentira]
        )
        por_id = {j.appid: j for j in catalogo}
        # O que só existe como atalho entra.
        assert por_id["321000"].nome == "Jogo Sem Manifesto"
        # O que existe nos dois fica com o nome COMPLETO, o do manifest.
        assert por_id["2111190"].nome == "Café Cósmico"
        assert por_id["2111190"].fonte == "steam"

    def test_a_lista_sai_em_ordem_alfabetica_sem_appid_repetido(
        self, casa_de_mentira: Path, atalhos_de_mentira: Path
    ) -> None:
        catalogo = catalogo_de_jogos(
            home=casa_de_mentira, pastas_de_atalhos=[atalhos_de_mentira]
        )
        appids = [j.appid for j in catalogo]
        assert len(appids) == len(set(appids))
        assert [j.nome for j in catalogo] == sorted(
            (j.nome for j in catalogo), key=chave_de_busca
        )

    def test_o_rotulo_carrega_o_numero_junto(self, casa_de_mentira: Path) -> None:
        """`851100` sozinho não diz nada; o nome sozinho não é conferível."""
        catalogo = catalogo_de_jogos(home=casa_de_mentira, pastas_de_atalhos=[])
        rotulos = {j.rotulo for j in catalogo}
        assert "Mar de Estrelas (appid 851100)" in rotulos


class TestOQueElaDigita:
    def test_acha_por_pedaco_do_nome_e_sem_acento(self) -> None:
        jogo = JogoLocal(appid="2111190", nome="Café Cósmico", fonte="steam")
        for digitado in ("cafe", "Café", "COSMICO", "cósm", "  cafe  "):
            assert casa_com_o_que_ela_digitou(jogo, digitado), digitado

    def test_acha_pelo_comeco_do_numero(self) -> None:
        """Depois de escolher, o campo fica com o appid — e ele é conferível."""
        jogo = JogoLocal(appid="2111190", nome="Café Cósmico", fonte="steam")
        assert casa_com_o_que_ela_digitou(jogo, "2111")

    def test_nao_acha_o_que_nao_e_dele(self) -> None:
        jogo = JogoLocal(appid="2111190", nome="Café Cósmico", fonte="steam")
        assert not casa_com_o_que_ela_digitou(jogo, "eldenring")
        assert not casa_com_o_que_ela_digitou(jogo, "")

    def test_o_simbolo_de_marca_nao_atrapalha(self) -> None:
        jogo = JogoLocal(
            appid="1599660", nome="Saco de Aventura™: O Retorno", fonte="steam"
        )
        assert casa_com_o_que_ela_digitou(jogo, "saco de aventura")


class TestAFraseAoLadoDoCampo:
    """A decisão pura do rótulo que traduz o número — sem GTK."""

    def setup_method(self) -> None:
        self.nomes = nomes_por_appid(
            [JogoLocal(appid=a, nome=n, fonte="steam") for a, n in JOGOS_FALSOS]
        )

    def test_campo_vazio_nao_fala(self) -> None:
        assert frase_do_campo_do_jogo("", self.nomes) is None
        assert frase_do_campo_do_jogo("   ", self.nomes) is None

    def test_o_numero_vira_o_nome_do_jogo(self) -> None:
        assert frase_do_campo_do_jogo("851100", self.nomes) == ("Mar de Estrelas", False)

    def test_o_endereco_colado_tambem_vira_o_nome(self) -> None:
        assert frase_do_campo_do_jogo(
            "https://store.steampowered.com/app/851100/Sea_of_Stars/", self.nomes
        ) == ("Mar de Estrelas", False)

    def test_jogo_que_nao_esta_aqui_diz_isso_sem_alarme(self) -> None:
        frase, alerta = frase_do_campo_do_jogo("999999", self.nomes)  # type: ignore[misc]
        assert frase == MSG_FORA_DA_MAQUINA
        assert alerta is False, "jogo não instalado é o caso normal, não erro"

    def test_endereco_que_nao_e_de_jogo_reclama(self) -> None:
        frase, alerta = frase_do_campo_do_jogo(  # type: ignore[misc]
            "https://www.gog.com/game/sea_of_stars", self.nomes
        )
        assert frase == MSG_NAO_RECONHECI
        assert alerta is True

    def test_enquanto_ela_digita_o_nome_a_frase_cala(self) -> None:
        for digitando in ("M", "Mar", "Mar de Est"):
            assert frase_do_campo_do_jogo(digitando, self.nomes) is None, digitando

    def test_sem_catalogo_o_numero_continua_valendo(self) -> None:
        """Máquina sem Steam: a lista fica vazia e o campo não fica quebrado."""
        assert frase_do_campo_do_jogo("851100", {}) == (MSG_FORA_DA_MAQUINA, False)


class TestOFiltroDeFerramenta:
    @pytest.mark.parametrize("nome", [n for _a, n in FERRAMENTAS_FALSAS])
    def test_reconhece_a_infraestrutura(self, nome: str) -> None:
        assert e_ferramenta_da_steam(nome)

    @pytest.mark.parametrize(
        "nome", ["Proton Pulse", "Protonwar", "Steam Marines", "Mar de Estrelas"]
    )
    def test_nao_esconde_jogo_de_verdade(self, nome: str) -> None:
        """`^Proton\\b` esconderia `Proton Pulse`, que é jogo. Por isso não é."""
        assert not e_ferramenta_da_steam(nome)
