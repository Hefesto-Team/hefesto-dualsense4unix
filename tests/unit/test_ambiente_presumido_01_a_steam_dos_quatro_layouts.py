"""AMBIENTE-PRESUMIDO-01 (23/08/2026) — a Steam mora em quatro lugares.

A medição de 23/08 pegou o produto com DUAS réguas de Steam que discordavam na
MESMA máquina: o `doctor` do CLI acusava *"Steam Input ligado para appid
1599660"* e, no mesmo instante, o cartão da aba Emulação escrevia em cinza
*"Steam não encontrado"*. O CLI usava `storm_doctor.find_localconfig_vdfs` (os
quatro layouts); a janela globava `~/.steam/steam` cravado — o único layout que
existe nesta bancada.

Quem instala a Steam pela Flatpak, pela Snap ou pelo instalador que cai em
`~/.local/share/Steam` via, por isso: a linha do Steam Input em cinza, o
catálogo de jogos VAZIO (`pastas_steamapps` herdava de
`proton_pin.default_steam_root`, que exclui sandbox DE PROPÓSITO — mas para
extrair Proton, não para ler `appmanifest`), e nenhum aviso em lugar nenhum.
Frase errada com cara de medição, que é o defeito que esta casa mais odeia.

O que este arquivo trava:

1. os quatro layouts são ACHADOS pelo cartão da aba (`_steam_input_is_on` e
   `_steam_input_appids_ligados`) e pelo catálogo (`jogos_da_biblioteca_steam`);
2. a lista de raízes é UMA (`steam_launch_options.RAIZES_STEAM_RELATIVAS`) — se
   alguém acrescentar um quinto layout sem passar por aqui, o teste reprova;
3. quando não há Steam nenhuma, a tela DIZ ONDE PROCUROU;
4. o leitor da allowlist (`storm_doctor`) e o escritor (o botão "Este jogo não
   funciona") resolvem o MESMO arquivo sob `XDG_CONFIG_HOME`;
5. `reopen_steam` reabre a Steam de quem não tem o binário `steam` no PATH.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions.emulation_actions import (
    STEAM_NAO_ENCONTRADA,
    EmulationActionsMixin,
    markup_status_steam_input,
)
from hefesto_dualsense4unix.integrations import proton_pin
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.integrations import storm_doctor as sd
from hefesto_dualsense4unix.integrations.jogos_locais import (
    jogos_da_biblioteca_steam,
)

#: Sackboy: o jogo REAL da medição — ligado no `localconfig.vdf` dela e fora da
#: allowlist. Aqui é só bancada: nenhum arquivo dela é lido.
_SACKBOY = "1599660"

#: Os quatro layouts, com o nome pelo qual a pessoa os conhece. É a MESMA lista
#: do produto — a igualdade é conferida em `test_a_lista_de_raizes_e_uma_so`,
#: para que um quinto layout não entre no código sem entrar nesta prova (nem na
#: frase de "não encontrada", que cita os quatro).
_LAYOUTS = {
    "nativa": ".steam/steam",
    "nativa-antiga": ".local/share/Steam",
    "flatpak": ".var/app/com.valvesoftware.Steam/.steam/steam",
    "snap": "snap/steam/common/.steam/steam",
}


def _vdf_com_steam_input_ligado(appid: str) -> str:
    """`localconfig.vdf` de bancada no formato REAL (tabs literais)."""
    return (
        '"UserLocalConfigStore"\n{\n\t"apps"\n\t{\n'
        f'\t\t"{appid}"\n\t\t{{\n\t\t\t"UseSteamControllerConfig"\t\t"2"\n\t\t}}\n'
        "\t}\n}\n"
    )


def _casa_com_steam(home: Path, relativo: str, appid: str = _SACKBOY) -> Path:
    """HOME de bancada com UMA Steam no layout pedido, jogo instalado e SI ligado."""
    raiz = home / relativo
    (raiz / "userdata/123/config").mkdir(parents=True)
    (raiz / "userdata/123/config/localconfig.vdf").write_text(
        _vdf_com_steam_input_ligado(appid), encoding="utf-8"
    )
    (raiz / "steamapps").mkdir(parents=True)
    (raiz / "steamapps" / f"appmanifest_{appid}.acf").write_text(
        '"AppState"\n{\n'
        f'\t"appid"\t\t"{appid}"\n'
        '\t"name"\t\t"Sackboy: A Big Adventure"\n'
        "}\n",
        encoding="utf-8",
    )
    return raiz


@pytest.fixture()
def home_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HOME e XDG_CONFIG_HOME presos ao tmp.

    CANARIO-FS-01: sem prender os dois, a allowlist REAL da mantenedora entraria
    na conta — e o resultado passaria a depender do disco dela.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return tmp_path


class TestOsQuatroLayouts:
    def test_a_lista_de_raizes_e_uma_so(self) -> None:
        """Um quinto layout tem de passar por aqui — e pela frase da tela."""
        assert set(_LAYOUTS.values()) == set(slo.RAIZES_STEAM_RELATIVAS)

    @pytest.mark.parametrize("nome", sorted(_LAYOUTS))
    def test_o_cartao_da_aba_acha_o_steam_input_ligado(
        self, nome: str, home_isolado: Path
    ) -> None:
        """O defeito medido: em três dos quatro isto devolvia None ("não achei")."""
        _casa_com_steam(home_isolado, _LAYOUTS[nome])
        assert EmulationActionsMixin._steam_input_is_on() is True

    @pytest.mark.parametrize("nome", sorted(_LAYOUTS))
    def test_o_cartao_nomeia_o_jogo_em_qualquer_layout(
        self, nome: str, home_isolado: Path
    ) -> None:
        _casa_com_steam(home_isolado, _LAYOUTS[nome])
        assert EmulationActionsMixin._steam_input_appids_ligados() == [_SACKBOY]

    @pytest.mark.parametrize("nome", sorted(_LAYOUTS))
    def test_o_catalogo_de_jogos_nao_sai_vazio(
        self, nome: str, home_isolado: Path
    ) -> None:
        """Ler `appmanifest_*.acf` de dentro da sandbox é leitura PURA e sempre
        funcionou — o vazio vinha de herdar a exclusão do Proton pin."""
        _casa_com_steam(home_isolado, _LAYOUTS[nome])
        jogos = jogos_da_biblioteca_steam(home_isolado)
        assert [j.nome for j in jogos] == ["Sackboy: A Big Adventure"]

    @pytest.mark.parametrize("nome", sorted(_LAYOUTS))
    def test_a_raiz_achada_e_a_que_existe(self, nome: str, home_isolado: Path) -> None:
        raiz = _casa_com_steam(home_isolado, _LAYOUTS[nome])
        assert slo.raizes_de_jogos(home_isolado) == [raiz]

    def test_duas_steams_no_mesmo_home_nao_viram_uma(
        self, home_isolado: Path
    ) -> None:
        """Flatpak + nativa convivem — quem migra de uma para a outra tem as duas."""
        _casa_com_steam(home_isolado, _LAYOUTS["nativa"])
        _casa_com_steam(home_isolado, _LAYOUTS["flatpak"], appid="1000")
        assert len(slo.raizes_de_jogos(home_isolado)) == 2
        assert EmulationActionsMixin._steam_input_appids_ligados() == [_SACKBOY, "1000"]


class TestAusenciaSeDeclara:
    def test_sem_steam_nenhuma_o_cartao_continua_dizendo_nao_sei(
        self, home_isolado: Path
    ) -> None:
        assert EmulationActionsMixin._steam_input_is_on() is None
        assert slo.raizes_de_jogos(home_isolado) == []

    def test_a_tela_diz_onde_procurou(self) -> None:
        """O cinza seco fazia a pessoa concluir que não tem Steam instalada."""
        markup = markup_status_steam_input(None, [], [], None)
        assert STEAM_NAO_ENCONTRADA in markup
        assert "procurei em" in markup
        assert "Flatpak" in markup and "Snap" in markup


class TestAllowlistNoMesmoArquivo:
    def test_leitor_e_escritor_resolvem_o_mesmo_caminho_sob_xdg(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O botão gravava e o cartão lia outro arquivo — em silêncio."""
        monkeypatch.setenv("HOME", str(tmp_path / "casa"))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        assert sd._allowlist_path() == slo.steam_input_allowlist_path()
        assert str(sd._allowlist_path()).startswith(str(tmp_path / "cfg"))

    def test_o_que_o_botao_escreve_o_cartao_le(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path / "casa"))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        slo.add_appid_to_steam_input_allowlist(2111190)
        assert "2111190" in sd.steam_input_allowlist()


class TestReabrirASteamSemBinario:
    def test_usa_a_url_quando_nao_ha_steam_no_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Flatpak/Snap não põem `steam` no PATH: a Steam ficava fechada e muda."""
        chamadas: list[list[str]] = []
        monkeypatch.setattr(
            slo.shutil, "which", lambda nome: None if nome == "steam" else f"/bin/{nome}"
        )
        monkeypatch.setattr(
            slo.subprocess,
            "Popen",
            lambda cmd, **_k: chamadas.append(list(cmd)),  # type: ignore[misc]
        )
        assert slo.reopen_steam() is True
        assert chamadas == [["xdg-open", "steam://open/main"]]

    def test_sem_caminho_nenhum_diz_que_nao_reabriu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(slo.shutil, "which", lambda _nome: None)
        assert slo.reopen_steam() is False


def test_o_shutil_e_o_subprocess_sao_os_do_modulo() -> None:
    """Régua da régua: os dois testes acima só valem se o módulo usa ESTES."""
    assert slo.shutil is shutil
    assert slo.subprocess is subprocess


# ---------------------------------------------------------------------------
# O sandbox: permissão de VER a Steam (o defeito P0 da medição de 23/08)
# ---------------------------------------------------------------------------
#: Raiz do repositório (mesma convenção de `test_loader_svg_nos_empacotamentos`).
_RAIZ = Path(__file__).resolve().parents[2]
_MANIFESTO = _RAIZ / "flatpak" / "br.andrefarias.Hefesto.yml"


class TestOFlatpakEnxergaASteam:
    """Nenhuma das buscas acima vale dentro do sandbox sem `--filesystem`.

    O `finish-args` não tinha UMA linha para a Steam — nem `--filesystem=home`.
    Dentro da Flatpak, portanto, os quatro layouts existiam e nenhum era
    legível: a integração inteira morria em silêncio, com cara de "esta máquina
    não tem Steam". Este teste é o portão dessa permissão, e cobra a LISTA do
    produto — um quinto layout sem permissão reprova aqui.
    """

    @staticmethod
    def _permissoes() -> list[str]:
        yaml = pytest.importorskip("yaml")
        dados = yaml.safe_load(_MANIFESTO.read_text(encoding="utf-8"))
        return [
            arg.split("=", 1)[1].split(":", 1)[0]
            for arg in dados["finish-args"]
            if arg.startswith("--filesystem=")
        ]

    @pytest.mark.parametrize("nome", sorted(_LAYOUTS))
    def test_cada_layout_de_steam_tem_permissao(self, nome: str) -> None:
        alvo = f"~/{_LAYOUTS[nome]}"
        permissoes = self._permissoes()
        assert any(
            alvo == p or alvo.startswith(f"{p}/") or p == "home" for p in permissoes
        ), f"o layout {nome} ({alvo}) não é legível dentro da Flatpak: {permissoes}"

    def test_a_steam_nativa_tem_escrita(self) -> None:
        """É no `localconfig.vdf` da nativa que o produto grava as LaunchOptions
        do wrapper; `:ro` ali faria o botão falhar sem dizer por quê."""
        yaml = pytest.importorskip("yaml")
        dados = yaml.safe_load(_MANIFESTO.read_text(encoding="utf-8"))
        escritas = {
            arg.split("=", 1)[1]
            for arg in dados["finish-args"]
            if arg.startswith("--filesystem=") and not arg.endswith(":ro")
        }
        assert "~/.steam" in escritas
        assert "~/.local/share/Steam" in escritas


# ---------------------------------------------------------------------------
# Os atalhos `.desktop`: a spec XDG, não dois caminhos cravados
# ---------------------------------------------------------------------------
class TestOsAtalhosSeguemOXdg:
    """`PASTAS_DE_ATALHOS` eram dois caminhos fixos.

    Medido nesta bancada em 23/08: `XDG_DATA_DIRS` lista QUATRO diretórios e o
    produto olhava dois — e um deles (`/usr/share`) nem estava na lista da
    sessão. Quem instala a Steam por Flatpak tem os atalhos dos jogos em
    `~/.local/share/flatpak/exports/share/applications`, que o campo "Nome do
    jogo" nunca ofereceu. Degradar calado aqui é requisito, o que torna o
    silêncio deste defeito INVISÍVEL — daí o teste.
    """

    @staticmethod
    def _atalho(pasta: Path, appid: str, nome: str) -> None:
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"jogo-{appid}.desktop").write_text(
            "[Desktop Entry]\nType=Application\n"
            f"Name={nome}\nExec=/usr/bin/steam steam://rungameid/{appid}\n",
            encoding="utf-8",
        )

    def test_acha_o_atalho_de_um_diretorio_do_xdg_data_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            jogos_dos_atalhos_desktop,
        )

        exports = tmp_path / "flatpak/exports/share"
        self._atalho(exports / "applications", "851100", "Jogo da Flatpak")
        # HOME preso ao tmp: o PISO da lista (os dois caminhos históricos) lê o
        # `~/.local/share/applications` REAL, e sem isto o resultado dependeria
        # dos atalhos da mantenedora (CANARIO-FS-01).
        monkeypatch.setenv("HOME", str(tmp_path / "casa"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "vazio"))
        monkeypatch.setenv("XDG_DATA_DIRS", f"{exports}:{tmp_path / 'nao-existe'}")
        achados = [(j.appid, j.nome) for j in jogos_dos_atalhos_desktop()]
        # `in` e não `==`: o piso inclui `/usr/share/applications`, que nesta
        # máquina tem 123 `.desktop` e nenhum com `rungameid` — mas isso é
        # medição desta casa, não invariante de máquina nenhuma.
        assert ("851100", "Jogo da Flatpak") in achados

    def test_o_xdg_data_home_manda_no_diretorio_da_pessoa(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            pastas_de_atalhos,
        )

        casa = tmp_path / "dados"
        (casa / "applications").mkdir(parents=True)
        monkeypatch.setenv("XDG_DATA_HOME", str(casa))
        monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "nao-existe"))
        assert casa / "applications" in pastas_de_atalhos()

    def test_nao_devolve_diretorio_que_nao_existe_nem_repetido(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            pastas_de_atalhos,
        )

        casa = tmp_path / "dados"
        (casa / "applications").mkdir(parents=True)
        monkeypatch.setenv("XDG_DATA_HOME", str(casa))
        monkeypatch.setenv("XDG_DATA_DIRS", f"{casa}:{casa}")
        alvos = pastas_de_atalhos()
        assert alvos.count(casa / "applications") == 1
        assert all(p.is_dir() for p in alvos)


# ---------------------------------------------------------------------------
# T-10 (ONDA0-Z7, 24/08/2026) — a lista de raízes é uma só, e o portão
# alcança o scripts/doctor.sh (não só o lado Python).
# ---------------------------------------------------------------------------
class TestOPortaoAlcancaOScriptsDoctorSh:
    """Antes deste teste, o `doctor.sh` podia divergir de
    `RAIZES_STEAM_RELATIVAS` e nada acusava — é a família **F6** (duas réguas
    discordando) na escala de UM arquivo: `check_vdf_poison` já cobria os
    quatro layouts, `check_proton_pin` só dois e `_steam_input_do_appid`
    cobria dois nativos mais um terceiro caminho não-canônico
    ("debian-installation"). T-08 igualou as três; este teste é a rede.
    """

    _FUNCOES_COM_LISTA_DE_RAIZES = (
        "check_vdf_poison",
        "check_proton_pin",
        "_steam_input_do_appid",
    )

    @staticmethod
    def _corpo_da_funcao(texto: str, nome: str) -> str:
        """O corpo de `nome() { ... }` — do cabeçalho ao `}` na coluna 0."""
        inicio = texto.index(f"\n{nome}() {{\n")
        fim = texto.index("\n}\n", inicio)
        return texto[inicio:fim]

    def test_as_tres_listas_do_doctor_sh_contem_os_quatro_layouts(
        self, repo_root: Path
    ) -> None:
        texto = (repo_root / "scripts" / "doctor.sh").read_text(encoding="utf-8")
        faltando: list[str] = []
        for nome in self._FUNCOES_COM_LISTA_DE_RAIZES:
            corpo = self._corpo_da_funcao(texto, nome)
            for layout in slo.RAIZES_STEAM_RELATIVAS:
                if layout not in corpo:
                    faltando.append(f"{nome}() não cobre '{layout}'")
        assert not faltando, "\n".join(faltando)

    def test_tirar_uma_raiz_de_uma_secao_reprova_nomeando_a_secao(
        self, repo_root: Path
    ) -> None:
        """A MORDIDA de T-10: tirar o layout snap de UMA seção só (aqui,
        `check_proton_pin`) faz o teste acima reprovar, nomeando exatamente
        essa função — não as outras duas, que continuam com as quatro."""
        texto = (repo_root / "scripts" / "doctor.sh").read_text(encoding="utf-8")
        alvo = '"${HOME}/snap/steam/common/.steam/steam/config/config.vdf"'
        assert alvo in texto  # a mutação abaixo precisa achar alguma coisa
        mutilado = texto.replace(alvo, '"/dev/null/nao-existe-mais"')

        faltando: list[str] = []
        for nome in self._FUNCOES_COM_LISTA_DE_RAIZES:
            corpo = self._corpo_da_funcao(mutilado, nome)
            for layout in slo.RAIZES_STEAM_RELATIVAS:
                if layout not in corpo:
                    faltando.append(f"{nome}() não cobre '{layout}'")

        assert faltando == ["check_proton_pin() não cobre 'snap/steam/common/.steam/steam'"]


# ---------------------------------------------------------------------------
# T-09 (ONDA0-Z7, 24/08/2026) — "Travar Proton validado" diz por que não
# pode, em vez de calar.
# ---------------------------------------------------------------------------
class TestSteamRootOuRecusa:
    """`default_steam_root` CONTINUA excluindo Flatpak/Snap (decisão medida).

    O que muda é a TELA saber dizer por quê — nunca ``(None, None)``, que
    seria o F1 ("aplicado" sem prova) na forma negativa.
    """

    def test_layout_nativo_devolve_raiz_sem_motivo(self, home_isolado: Path) -> None:
        raiz = _casa_com_steam(home_isolado, _LAYOUTS["nativa"])
        resultado = proton_pin.steam_root_ou_recusa(home_isolado)
        assert resultado.raiz == raiz
        assert resultado.motivo is None

    def test_so_flatpak_devolve_recusa_com_motivo_nao_vazio(
        self, home_isolado: Path
    ) -> None:
        """A MORDIDA central de T-09."""
        _casa_com_steam(home_isolado, _LAYOUTS["flatpak"])
        resultado = proton_pin.steam_root_ou_recusa(home_isolado)
        assert resultado.raiz is None
        assert resultado.motivo  # não vazio, não None
        assert "Flatpak" in resultado.motivo
        assert "caixa" in resultado.motivo

    def test_so_snap_devolve_recusa_com_motivo_nao_vazio(
        self, home_isolado: Path
    ) -> None:
        _casa_com_steam(home_isolado, _LAYOUTS["snap"])
        resultado = proton_pin.steam_root_ou_recusa(home_isolado)
        assert resultado.raiz is None
        assert resultado.motivo
        assert "Snap" in resultado.motivo

    def test_nenhuma_steam_tambem_diz_por_que(self, home_isolado: Path) -> None:
        resultado = proton_pin.steam_root_ou_recusa(home_isolado)
        assert resultado.raiz is None
        assert resultado.motivo
        assert "nenhuma steam" in resultado.motivo.lower()

    def test_flatpak_e_nativa_juntas_prefere_a_nativa(self, home_isolado: Path) -> None:
        """Quem tem as duas pode travar na nativa -- não é recusa."""
        raiz = _casa_com_steam(home_isolado, _LAYOUTS["nativa"])
        _casa_com_steam(home_isolado, _LAYOUTS["flatpak"], appid="1000")
        resultado = proton_pin.steam_root_ou_recusa(home_isolado)
        assert resultado.raiz == raiz
        assert resultado.motivo is None

    def test_arrancar_a_propagacao_do_motivo_reprova(
        self, home_isolado: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Arrancar a cura: uma versão que devolve `(None, None)` sempre que
        não há raiz reproduz o F1 — o teste tem de reprovar contra ela."""
        _casa_com_steam(home_isolado, _LAYOUTS["flatpak"])

        def _versao_antiga_sem_motivo(
            home: Path | None = None,
        ) -> proton_pin.RaizDaSteamOuRecusa:
            base = home or Path.home()
            raiz = proton_pin.default_steam_root(base)
            return proton_pin.RaizDaSteamOuRecusa(
                raiz if raiz.is_dir() else None, None
            )

        monkeypatch.setattr(proton_pin, "steam_root_ou_recusa", _versao_antiga_sem_motivo)
        resultado = proton_pin.steam_root_ou_recusa(home_isolado)
        assert resultado == (None, None)  # reproduz F1: nem raiz, nem motivo
        with pytest.raises(AssertionError):
            assert resultado.motivo  # a régua boa reprovaria isto
