"""LUZ-CEGA-01/E8 — o berço da suíte não vaza para o `config_dir()` real.

O DEFEITO, medido em 25/08/2026 no journal DELA. Quatro endereços da faixa de
fixture `aa:bb:cc:*` moram no `controllers.json` de produção dela e empurram os
DualSense REAIS para os postos 6, 7 e 8. A escrita foi datada: até
`2026-08-11T23:50` a fila gravada tinha os quatro DualSense dela; em
`2026-08-22T02:13:43` o daemon a restaurou como **só** os quatro forjados
(`identity_fila_restaurada`), com `identity_slots_restaurados_de_outro_boot
arquivo_boot=df8018bc…` — ou seja, quem escreveu resolveu o `config_dir()`
VERDADEIRO e leu o `boot_id` VERDADEIRO, dentro do boot de 21/08 15:56 →
22/08 01:55.

Este arquivo não persegue o autor daquele dia: persegue a CLASSE de buraco que
o torna possível, com duas réguas.

RÉGUA 1 — nenhum módulo do produto congela um caminho de `$HOME` numa
constante de MÓDULO. Constante de módulo é avaliada na IMPORTAÇÃO, e a
importação acontece na COLETA do pytest, antes de qualquer fixture: o
isolamento de `XDG_CONFIG_HOME` do `conftest` (escopo de FUNÇÃO) não a alcança
nunca. É o buraco que o CANARIO-FS-01 nomeia no próprio texto de reprovação, e
que 05/08/2026 curou em dois lugares (`storm_doctor._allowlist_path`,
`EmulationActionsMixin._wp_dropin_dir`) — deixando um terceiro vivo:
`app/gui_prefs.py`, que assim gravava as preferências DELA a cada
`save_gui_prefs` sob teste. O portão é AST, não regex: ele lê a árvore e olha
só o que é atribuição no nível do módulo.

RÉGUA 2 — a função que a suíte usa para vigiar o `config_dir()` real
(`scripts/check_faixa_sintetica.enderecos`, chamada pela FAIXA-NO-BERCO-01 do
`conftest`) sabe RECUSAR e sabe ACEITAR. Régua que só sabe passar não é régua.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

sys.path.insert(0, str(RAIZ / "scripts"))
import check_faixa_sintetica  # import DEPOIS do sys.path acima, de propósito

#: As chamadas que resolvem um caminho do `$HOME` e por isso NÃO podem virar
#: constante de módulo. As seis primeiras são o `utils/xdg_paths`; as duas
#: últimas são o caminho de fora dele, que o BERÇO-DE-TMP-01 (24/08) mediu
#: escapando pela cauda do `$HOME`.
_RESOLVEM_O_LAR = frozenset({
    "config_dir",
    "data_dir",
    "cache_dir",
    "state_dir",
    "runtime_dir",
    "profiles_dir",
    "launch_env_dir",
    "wireplumber_config_dir",
    "home",
    "expanduser",
})


def _nome_chamado(no: ast.AST) -> str:
    """O nome final da chamada: `xdg_paths.config_dir()` → `config_dir`."""
    alvo = getattr(no, "func", None)
    if isinstance(alvo, ast.Attribute):
        return alvo.attr
    if isinstance(alvo, ast.Name):
        return alvo.id
    return ""


def _constantes_congeladas(caminho: Path) -> list[str]:
    """`NOME (linha N)` para cada constante de módulo que congela o `$HOME`."""
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):  # pragma: no cover — árvore quebrada é outro portão
        return []
    achados: list[str] = []
    for no in arvore.body:  # SÓ o nível do módulo: dentro de função é o certo
        if not isinstance(no, (ast.Assign, ast.AnnAssign)):
            continue
        valor = no.value
        if valor is None:
            continue
        for filho in ast.walk(valor):
            if isinstance(filho, ast.Call) and _nome_chamado(filho) in _RESOLVEM_O_LAR:
                alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
                nomes = [
                    a.id for a in alvos if isinstance(a, ast.Name)
                ] or ["<anônimo>"]
                achados.append(
                    f"{nomes[0]} (linha {no.lineno}, chama "
                    f"`{_nome_chamado(filho)}()`)"
                )
                break
    return achados


class TestNenhumaConstanteCongelaOLar:
    """RÉGUA 1 — o caminho do `$HOME` se resolve na CHAMADA, nunca no import."""

    def test_nenhum_modulo_do_produto_congela_caminho_de_home(self) -> None:
        culpados: list[str] = []
        for caminho in sorted(SRC.rglob("*.py")):
            for achado in _constantes_congeladas(caminho):
                culpados.append(f"{caminho.relative_to(RAIZ)}: {achado}")
        assert not culpados, (
            "Constante de MÓDULO congelando um caminho do `$HOME`:\n  "
            + "\n  ".join(culpados)
            + "\n  Ela é avaliada na IMPORTAÇÃO — que na suíte acontece na"
            "\n  COLETA, antes de qualquer fixture. O isolamento de"
            "\n  XDG_CONFIG_HOME do conftest (escopo de FUNÇÃO) não a alcança,"
            "\n  e o que o produto gravar sob teste vai para o disco de quem"
            "\n  roda. Mova para dentro de uma função (`def _caminho() ->"
            "\n  Path: return config_dir() / NOME`) — em produção nada muda."
        )

    def test_gui_prefs_le_o_config_dir_do_momento(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A prova de comportamento da cura, e ela NÃO grava em disco nenhum.

        Só LEITURA de propósito: com a constante congelada de volta, um
        `save_gui_prefs` aqui escreveria no `~/.config` de quem rodasse o
        teste — a régua não pode reproduzir o defeito que mede.
        """
        from hefesto_dualsense4unix.app import gui_prefs

        outro = tmp_path / "config-de-outro-lugar"
        (outro / "hefesto-dualsense4unix").mkdir(parents=True)
        (outro / "hefesto-dualsense4unix" / "gui_preferences.json").write_text(
            json.dumps({"advanced_editor": True}), encoding="utf-8"
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(outro))

        assert gui_prefs.load_gui_prefs()["advanced_editor"] is True, (
            "`gui_prefs` leu de outro lugar que não o `config_dir()` de agora "
            "— é o sintoma do caminho congelado no import."
        )

    def test_gui_prefs_grava_no_config_dir_do_momento(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ponta de ESCRITA — com o pré-teste que a torna segura de rodar."""
        from hefesto_dualsense4unix.app import gui_prefs

        congeladas = _constantes_congeladas(Path(gui_prefs.__file__))
        assert not congeladas, (
            f"`gui_prefs` voltou a congelar o caminho ({congeladas}) — este "
            "teste PARA aqui de propósito: gravar agora escreveria no "
            "`~/.config` de quem o roda."
        )

        destino = tmp_path / "config-do-save"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(destino))
        gui_prefs.save_gui_prefs({"advanced_editor": True})
        gravado = destino / "hefesto-dualsense4unix" / "gui_preferences.json"
        assert gravado.exists()
        assert json.loads(gravado.read_text(encoding="utf-8"))["advanced_editor"]


class TestAReguaDaFaixaSabeRecusarEAceitar:
    """RÉGUA 2 — a função que a FAIXA-NO-BERCO-01 chama, nas duas respostas."""

    def _mesa(self, pasta: Path, addrs: list[str]) -> None:
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "controllers.json").write_text(
            json.dumps(
                {
                    "version": 3,
                    "boot_id": "boot-de-teste",
                    "order": [
                        {"addr": a, "kind": "dualsense", "rank": i + 1}
                        for i, a in enumerate(addrs)
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_aceita_a_mesa_so_com_endereco_de_verdade(self, tmp_path: Path) -> None:
        # OUI de fabricante com a máscara da casa (octetos 4 e 5 zerados) —
        # a única forma de "endereço que parece real" que o portão de
        # anonimato de fixtures aceita em `tests/`.
        self._mesa(tmp_path, ["e417d80000a1", "e417d80000b2"])
        assert check_faixa_sintetica.enderecos(tmp_path) == set()

    def test_recusa_a_mesa_com_faixa_de_fixture(self, tmp_path: Path) -> None:
        self._mesa(tmp_path, ["e417d80000a1", "aabbcc000001"])
        achados = check_faixa_sintetica.enderecos(tmp_path)
        assert achados == {f"{tmp_path / 'controllers.json'}::aabbcc000001"}

    def test_a_chave_carrega_o_arquivo_para_o_delta_enxergar_migracao(
        self, tmp_path: Path
    ) -> None:
        """O mesmo endereço em outro arquivo é escrita NOVA, e tem de aparecer."""
        self._mesa(tmp_path, ["aabbcc000001"])
        antes = check_faixa_sintetica.enderecos(tmp_path)
        (tmp_path / "session.json").write_text(
            json.dumps({"alvo": "aabbcc000001"}), encoding="utf-8"
        )
        depois = check_faixa_sintetica.enderecos(tmp_path)
        assert depois - antes == {f"{tmp_path / 'session.json'}::aabbcc000001"}

    def test_diretorio_que_nao_existe_nao_levanta(self, tmp_path: Path) -> None:
        """A régua nunca derruba a sessão por não conseguir medir."""
        assert check_faixa_sintetica.enderecos(tmp_path / "nao-existe") == set()


class TestOPortaoDaArvoreVersionada:
    """O modo `--arvore`, que é o chamador de CI — e ele também recusa."""

    def test_aceita_arvore_sem_artefato_de_tempo_de_execucao(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "codigo.py").write_text("x = 1\n", encoding="utf-8")
        assert check_faixa_sintetica.achados_na_arvore(tmp_path) == []

    def test_recusa_controllers_json_commitado_com_faixa(self, tmp_path: Path) -> None:
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "controllers.json").write_text(
            json.dumps({"order": [{"addr": "aabbcc000001"}]}), encoding="utf-8"
        )
        achados = check_faixa_sintetica.achados_na_arvore(tmp_path)
        assert len(achados) == 1
        assert "assets/controllers.json" in achados[0]

    def test_fixture_de_teste_continua_legitima(self, tmp_path: Path) -> None:
        """`tests/` e `docs/` usam a faixa POR CONTRATO — ali não se procura."""
        (tmp_path / "tests" / "fixtures").mkdir(parents=True)
        (tmp_path / "tests" / "fixtures" / "controllers.json").write_text(
            json.dumps({"order": [{"addr": "aabbcc000001"}]}), encoding="utf-8"
        )
        assert check_faixa_sintetica.achados_na_arvore(tmp_path) == []


class TestAReguaEnxergaBackup:
    """Todo backup carrega sufixo próprio, e era essa a classe que escapava.

    PONTO CEGO MEDIDO em 25/08/2026, e a forma como ele apareceu é o próprio
    argumento: quem coordenava fez um backup do `controllers.json` VIVO dela
    antes de limpar os quatro endereços de fixture, salvou-o ao lado do
    original como `controllers.json.antes-de-tirar-fixtures-20260825` — e a
    régua devolveu VERDE sobre um arquivo com os quatro endereços dentro.

    `Path.suffix` devolve só o ÚLTIMO sufixo. `.bak`, `.old`, `.orig`,
    `.2026-08-25`, `.antes-de-X`: **backup era exatamente o que esta régua não
    conseguia ver.** É a pior forma de ponto cego — some justamente onde alguém
    guardou uma cópia do estado que a régua existe para vigiar, e a cópia é o
    que sobrevive a uma limpeza.

    A MORDIDA: troque `_vale_varrer(caminho)` por
    `caminho.suffix.lower() in _EXTENSOES_VARRIDAS` em `achados()` e
    `test_o_backup_do_controllers_nao_escapa` reprova.
    """

    def test_o_backup_do_controllers_nao_escapa(self, tmp_path: Path) -> None:
        alvo = tmp_path / "controllers.json.antes-de-tirar-fixtures-20260825"
        alvo.write_text(
            json.dumps({"order": [{"addr": "aabbcc000001", "rank": 1}]}),
            encoding="utf-8",
        )
        achados = check_faixa_sintetica.achados(tmp_path)
        assert achados, (
            "a régua devolveu VERDE sobre um BACKUP do controllers.json com "
            "endereço de fixture dentro. Todo backup tem sufixo próprio, e "
            "`Path.suffix` só devolve o último — era a classe inteira dos "
            "backups escapando da vigilância."
        )
        assert "aabbcc000001" in achados[0]

    @pytest.mark.parametrize(
        ("nome", "esperado", "porque"),
        [
            ("controllers.json", True, "o caso de sempre"),
            ("controllers.json.bak", True, "o sufixo de backup mais comum"),
            ("session.json.2026-08-25", True, "backup datado"),
            ("maquina.json.orig", True, "sufixo de conflito de merge"),
            ("notas.txt.old", True, "texto com sufixo de backup"),
            ("semponto", True, "arquivo sem sufixo continua varrido"),
            ("icone.png", False, "binário conhecido continua de fora"),
            ("dump.sqlite", False, "sufixo desconhecido e sozinho fica de fora"),
        ],
    )
    def test_a_regua_escolhe_pelo_conjunto_de_sufixos(
        self, nome: str, esperado: bool, porque: str
    ) -> None:
        assert check_faixa_sintetica._vale_varrer(Path(nome)) is esperado, porque

    def test_a_regua_continua_recusando_binario(self, tmp_path: Path) -> None:
        """A cura não pode ter aberto a porta para tudo.

        Sem esta guarda passaria um "conserto" que varresse todo arquivo — e a
        régua começaria a ler PNG e a acusar coincidência de bytes.
        """
        (tmp_path / "captura.png").write_bytes(b"\x89PNG\r\n\x1a\naabbcc000001")
        assert check_faixa_sintetica.achados(tmp_path) == []
