"""PINO-QUE-SOBE-01 — subir o pino tem de ALCANÇAR os jogos.

O DEFEITO, medido na máquina dela em 16/09/2026, no dia em que o pino subiu de
`GE-Proton10-34` para `GE-Proton11-6-x86_64` para trazer o som do alto-falante
dentro do jogo: o `--lock` respondeu `locked`, e os **25 jogos continuaram no
Proton velho**. Cada um com `action="preservado"` — a guarda de 19/08, que
existe para não atropelar escolha dela, leu como escolha dela o que o PRÓPRIO
produto tinha escrito. Os backups do `config.vdf` provam a procedência: as
entradas em `GE-Proton10-34` crescem install a install desde 19/07.

Efeito, dito por inteiro: **subir o pino nunca alcançava jogo nenhum**. Só o
default global mudava, e a versão nova ficava instalada sem ninguém usar.

E O INSTRUMENTO ESCONDIA ISSO: a linha do CLI imprimia `len(appids)` — o
tamanho do ALVO — e anunciava *"locked — 25 jogos + default global"* enquanto
os 25 ficavam onde estavam.

A REGRA: o que este produto pinou antes é NOSSO e migra; qualquer outro valor
continua sendo escolha dela e é preservado. O histórico dos pinos vive no
registro do lock e cresce sozinho a cada subida.

AS MORDIDAS: sem `pinos_nossos`, a entrada do pino velho volta a `preservado`;
sem o histórico no registro, a segunda subida repete o defeito; e a linha do
CLI volta a dizer o alvo em vez do que aconteceu.
"""
from __future__ import annotations

import json
from pathlib import Path

from hefesto_dualsense4unix.integrations import proton_pin as pp

PINO_VELHO = "GE-Proton10-34"
PINO_NOVO = "GE-Proton11-6-x86_64"
#: O Proton que ELA escolheu para o DON'T SCREAM (appid 2497900): o incidente
#: de 14/08/2026 — noutro Proton, o motor Unreal não acha captura de áudio e o
#: microfone, que é a mecânica do jogo, morre.
ESCOLHA_DELA = "proton_11"


def _config_vdf(entradas: dict[str, str]) -> str:
    """`config.vdf` mínimo, no formato que o parser do produto lê."""
    corpo = ""
    for appid, tool in entradas.items():
        corpo += (
            f'\t\t\t\t\t"{appid}"\n'
            f"\t\t\t\t\t{{\n"
            f'\t\t\t\t\t\t"name"\t\t"{tool}"\n'
            f'\t\t\t\t\t\t"config"\t\t""\n'
            f'\t\t\t\t\t\t"priority"\t\t"250"\n'
            f"\t\t\t\t\t}}\n"
        )
    return (
        '"InstallConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n'
        '\t\t\t"Steam"\n\t\t\t{\n\t\t\t\t"CompatToolMapping"\n\t\t\t\t{\n'
        f"{corpo}"
        "\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n"
    )


def _acoes(mudancas: dict[str, dict[str, str]]) -> dict[str, str]:
    return {appid: c["action"] for appid, c in mudancas.items()}


class TestOPinoVelhoNaoEEscolhaDela:
    def test_a_entrada_do_pino_nosso_migra(self) -> None:
        """A MORDIDA: sem `pinos_nossos`, isto volta a ser `preservado`."""
        texto = _config_vdf({"0": PINO_VELHO, "1599660": PINO_VELHO})

        novo, mudancas = pp.build_compat_tool_mapping(
            texto, tool_name=PINO_NOVO, appids=["1599660"],
            pinos_nossos=[PINO_VELHO],
        )

        assert _acoes(mudancas)["1599660"] == "migrado"
        assert f'"name"\t\t"{PINO_NOVO}"' in novo
        assert PINO_VELHO not in novo

    def test_a_escolha_dela_continua_preservada(self) -> None:
        """O dano de 14/08 segue impossível: só o que é NOSSO migra."""
        texto = _config_vdf({"0": PINO_VELHO, "2497900": ESCOLHA_DELA})

        novo, mudancas = pp.build_compat_tool_mapping(
            texto, tool_name=PINO_NOVO, appids=["2497900"],
            pinos_nossos=[PINO_VELHO],
        )

        assert _acoes(mudancas)["2497900"] == "preservado"
        assert ESCOLHA_DELA in novo

    def test_sem_historico_nada_migra(self) -> None:
        """Sem saber o que é nosso, o produto não adivinha — preserva."""
        texto = _config_vdf({"0": PINO_VELHO, "1599660": PINO_VELHO})

        _novo, mudancas = pp.build_compat_tool_mapping(
            texto, tool_name=PINO_NOVO, appids=["1599660"],
        )

        assert _acoes(mudancas)["1599660"] == "preservado"

    def test_o_global_muda_como_sempre_mudou(self) -> None:
        """A entrada `"0"` nunca esteve sob a guarda: é a função do recurso."""
        texto = _config_vdf({"0": PINO_VELHO})

        _novo, mudancas = pp.build_compat_tool_mapping(
            texto, tool_name=PINO_NOVO, appids=[],
        )

        assert _acoes(mudancas)["0"] == "replaced"


class TestOHistoricoDePinosCresceSozinho:
    def test_o_lock_grava_o_pino_de_hoje_no_historico(self, tmp_path: Path) -> None:
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_config_vdf({"0": PINO_VELHO, "1599660": PINO_VELHO}))
        estado = tmp_path / "lock.json"

        pp.lock_games_to_pinned_proton(
            tool_name=PINO_NOVO, appids=["1599660"], config_vdf=vdf,
            state_path=estado, migrar_de=[PINO_VELHO],
        )

        gravado = json.loads(estado.read_text(encoding="utf-8"))
        assert PINO_VELHO in gravado["pinos_do_hefesto"]
        assert PINO_NOVO in gravado["pinos_do_hefesto"]

    def test_a_segunda_subida_nao_precisa_de_semente(self, tmp_path: Path) -> None:
        """É isto que impede o defeito de 16/09 de voltar na próxima subida."""
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_config_vdf({"0": PINO_VELHO, "1599660": PINO_VELHO}))
        estado = tmp_path / "lock.json"
        pp.lock_games_to_pinned_proton(
            tool_name=PINO_NOVO, appids=["1599660"], config_vdf=vdf,
            state_path=estado, migrar_de=[PINO_VELHO],
        )

        # O pino sobe DE NOVO, e desta vez ninguém semeia nada.
        mais_novo = "GE-Proton12-1-x86_64"
        resultado = pp.lock_games_to_pinned_proton(
            tool_name=mais_novo, appids=["1599660"], config_vdf=vdf,
            state_path=estado,
        )

        mudancas = resultado["changes"]
        assert isinstance(mudancas, dict)
        assert _acoes(mudancas)["1599660"] == "migrado"
        assert f'"name"\t\t"{mais_novo}"' in vdf.read_text(encoding="utf-8")

    def test_registro_antigo_sem_a_chave_conta_o_tool_name(
        self, tmp_path: Path
    ) -> None:
        """Quem já tinha registro (todo mundo) não fica de fora da cura."""
        estado = tmp_path / "lock.json"
        estado.write_text(json.dumps({
            "tool_name": PINO_VELHO,
            "changes": {"1599660": {"action": "added", "previous_name": ""}},
        }), encoding="utf-8")

        assert PINO_VELHO in pp._pinos_ja_usados(estado)

    def test_registro_ilegivel_nao_derruba_o_lock(self, tmp_path: Path) -> None:
        """Falha para o lado seguro: sem histórico, preserva tudo."""
        estado = tmp_path / "lock.json"
        estado.write_text("{isto não é json", encoding="utf-8")

        assert pp._pinos_ja_usados(estado) == ()


class TestOsBaldesSaoContadosSeparados:
    def test_migrado_nao_entra_no_locked(self, tmp_path: Path) -> None:
        """Somar esconderia o número que prova que a subida chegou aos jogos."""
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_config_vdf({
            "0": PINO_VELHO,
            "1599660": PINO_VELHO,      # nosso   -> migrado
            "2497900": ESCOLHA_DELA,    # dela    -> preservado
        }))
        # `lock_proton_for_all_games` mira os jogos INSTALADOS, lidos dos
        # `appmanifest_*.acf` — sem eles a lista nasce vazia e o caso mediria
        # só o global, passando pelo motivo errado.
        steamapps = pp.default_steam_root(tmp_path) / "steamapps"
        steamapps.mkdir(parents=True, exist_ok=True)
        for appid, nome in (("1599660", "Sackboy"), ("2497900", "DON'T SCREAM")):
            (steamapps / f"appmanifest_{appid}.acf").write_text(
                f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{nome}"\n}}\n',
                encoding="utf-8",
            )

        resultado = pp.lock_proton_for_all_games(
            conf={"name": PINO_NOVO, "url": "http://exemplo.invalido",
                  "sha256": "ab" * 32},
            config_vdf=vdf,
            state_path=tmp_path / "lock.json",
            home=tmp_path,
            dry_run=True,
            migrar_de=[PINO_VELHO],
        )

        assert resultado["migrated"] == 1
        assert resultado["skipped"] == 1
        assert resultado["locked"] == 1  # só o global


class TestORegistroDizOQueAconteceu:
    """O registro do lock tem de descrever a corrida que ACONTECEU.

    Medido na máquina dela em 16/09/2026, depois de os 24 jogos migrarem de
    verdade: o registro ainda dizia `preservado` para os 24, porque a fusão era
    por ENTRADA e o registro da corrida que FALHARA vencia inteiro. Registro que
    conta a corrida errada não desfaz nada.
    """

    def _lock(self, tmp_path: Path, *, tool: str, migrar_de: list[str]) -> Path:
        vdf = tmp_path / "config.vdf"
        estado = tmp_path / "lock.json"
        pp.lock_games_to_pinned_proton(
            tool_name=tool, appids=["1599660"], config_vdf=vdf,
            state_path=estado, migrar_de=migrar_de,
        )
        return estado

    def test_a_acao_de_agora_vence_a_da_corrida_anterior(self, tmp_path: Path) -> None:
        """A MORDIDA: com a fusão por entrada, isto volta a dizer `preservado`."""
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_config_vdf({"0": PINO_VELHO, "1599660": PINO_VELHO}))
        estado = tmp_path / "lock.json"

        # A corrida que falhou: sem semente, o jogo é preservado.
        pp.lock_games_to_pinned_proton(
            tool_name=PINO_NOVO, appids=["1599660"], config_vdf=vdf,
            state_path=estado,
        )
        assert json.loads(estado.read_text())["changes"]["1599660"]["action"] == (
            "preservado"
        )

        # A corrida que curou: o mesmo pino, agora sabendo o que é nosso.
        pp.lock_games_to_pinned_proton(
            tool_name=PINO_NOVO, appids=["1599660"], config_vdf=vdf,
            state_path=estado, migrar_de=[PINO_VELHO],
        )

        gravado = json.loads(estado.read_text())["changes"]["1599660"]
        assert gravado["action"] == "migrado"
        assert f'"name"\t\t"{PINO_NOVO}"' in vdf.read_text(encoding="utf-8")

    def test_o_veio_de_desfaz_uma_subida(self, tmp_path: Path) -> None:
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_config_vdf({"0": PINO_VELHO, "1599660": PINO_VELHO}))
        estado = tmp_path / "lock.json"

        pp.lock_games_to_pinned_proton(
            tool_name=PINO_NOVO, appids=["1599660"], config_vdf=vdf,
            state_path=estado, migrar_de=[PINO_VELHO],
        )

        assert json.loads(estado.read_text())["changes"]["1599660"]["veio_de"] == (
            PINO_VELHO
        )

    def test_o_previous_name_dela_sobrevive_a_subida_de_pino(
        self, tmp_path: Path
    ) -> None:
        """A MORDIDA: exigir `tool_name` igual apaga isto a cada subida.

        E é o único valor que sabe devolver o jogo ao estado de ANTES de este
        produto encostar nele.
        """
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_config_vdf({"0": ESCOLHA_DELA, "1599660": ESCOLHA_DELA}))
        estado = tmp_path / "lock.json"

        # A primeira trava, num pino antigo: o valor dela fica registrado.
        pp.lock_games_to_pinned_proton(
            tool_name=PINO_VELHO, appids=["1599660"], config_vdf=vdf,
            state_path=estado, migrar_de=[ESCOLHA_DELA],
        )
        assert json.loads(estado.read_text())["changes"]["1599660"][
            "previous_name"
        ] == ESCOLHA_DELA

        # O pino sobe. O appid muda de Proton — a procedência dele, não.
        pp.lock_games_to_pinned_proton(
            tool_name=PINO_NOVO, appids=["1599660"], config_vdf=vdf,
            state_path=estado, migrar_de=[PINO_VELHO],
        )

        gravado = json.loads(estado.read_text())["changes"]["1599660"]
        assert gravado["previous_name"] == ESCOLHA_DELA   # desfaz TUDO
        assert gravado["veio_de"] == PINO_VELHO           # desfaz UMA subida

    def test_preservado_nao_promete_desfazer_o_que_nao_fez(
        self, tmp_path: Path
    ) -> None:
        """Sem `veio_de`, quem lê sabe que esta corrida não mexeu no appid."""
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_config_vdf({"0": PINO_VELHO, "2497900": ESCOLHA_DELA}))
        estado = tmp_path / "lock.json"

        pp.lock_games_to_pinned_proton(
            tool_name=PINO_NOVO, appids=["2497900"], config_vdf=vdf,
            state_path=estado, migrar_de=[PINO_VELHO],
        )

        gravado = json.loads(estado.read_text())["changes"]["2497900"]
        assert gravado["action"] == "preservado"
        assert "veio_de" not in gravado
