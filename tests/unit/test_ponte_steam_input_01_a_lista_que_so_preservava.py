"""PONTE-STEAM-INPUT-01 (19/08/2026) — a lista de exceções passa a LIGAR.

O defeito estava nomeado pelo próprio produto, no estorvo `excecao_inerte`:
*"Este jogo está na sua lista de exceções do Steam Input, mas o Steam Input
está DESLIGADO para ele. A lista só preserva o que já estava ligado — ela nunca
liga."* Diagnóstico perfeito, cura escrita, e ninguém a aplicava.

O preço, na noite de 18→19/08/2026: DON'T SCREAM é da classe *"só aceita Steam
Input"* — motor Unreal falando XInput, e quem lhe entregava um dispositivo
XInput era o espelho Xbox do Steam Input. Com o Steam Input desligado ele não
via controle nenhum, e o guarda desligava a única ponte que o fazia funcionar.

Este arquivo trava quatro coisas:

1. a lista LIGA (e a mordida: com a cura arrancada, o jogo continua em `"0"`);
2. a árvore em que se escreve é a VIVA, achada por medição e não por suposição
   — e é uma árvore DIFERENTE da canônica das `LaunchOptions`;
3. as duas réguas: quando elas discordam, o produto RECUSA escrever;
4. o prontuário deixou de ser modelo sem uso: todo estorvo que ele declara
   automático tem quem o cure.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import steam_input_ponte as ponte
from hefesto_dualsense4unix.integrations.prontuario_dos_jogos import (
    _CURAS,
    _ESTORVOS,
    CURA_FEITA,
    EXCECAO_INERTE,
    Cura,
    Estorvo,
    Prontuario,
    curar_o_que_e_automatico,
)

#: Os appids reais do caso. O DON'T SCREAM aparece aqui como DADO DE TESTE, e
#: de propósito NÃO entra em lista nenhuma do produto: receita por appid
#: embarcada foi recusada por ela em 14/08/2026, porque deixa todo jogo novo
#: desprotegido. O que o produto ganha é o MECANISMO; quais jogos entram é
#: config da máquina dela.
_DONT_SCREAM = "2497900"
_SACKBOY = "1599660"
_MMJ = "2111190"


def _vdf(
    *,
    canonica: dict[str, str] | None = None,
    viva: dict[str, str | None] | None = None,
    ps_support: str | None = "0",
) -> str:
    """Um `localconfig.vdf` com o layout REAL: duas árvores `apps` distintas.

    A de cima é a canônica das `LaunchOptions`
    (`Software/Valve/Steam/apps`); a de baixo é a que guarda o
    `UseSteamControllerConfig` (`UserLocalConfigStore/apps`), com o
    `SteamController_PSSupport` como IRMÃ logo depois — exatamente a ordem
    medida no arquivo dela em 19/08/2026, inclusive o detalhe de a irmã vir
    DEPOIS do `}` que fecha a árvore.

    Em `viva`, o valor `None` significa "o bloco do app existe, mas sem a
    chave" — o caso do jogo que a Steam nunca tocou em Propriedades > Controle.
    """
    linhas = ['"UserLocalConfigStore"', "{"]
    linhas += ['\t"Software"', "\t{", '\t\t"Valve"', "\t\t{", '\t\t\t"Steam"', "\t\t\t{"]
    linhas += ['\t\t\t\t"apps"', "\t\t\t\t{"]
    for appid, opcoes in (canonica or {}).items():
        linhas += [f'\t\t\t\t\t"{appid}"', "\t\t\t\t\t{",
                   f'\t\t\t\t\t\t"LaunchOptions"\t\t"{opcoes}"', "\t\t\t\t\t}"]
    linhas += ["\t\t\t\t}", "\t\t\t}", "\t\t}", "\t}"]
    linhas += ['\t"apps"', "\t{"]
    for appid, valor in (viva or {}).items():
        linhas += [f'\t\t"{appid}"', "\t\t{"]
        if valor is not None:
            linhas.append(f'\t\t\t"UseSteamControllerConfig"\t\t"{valor}"')
        linhas.append('\t\t\t"SteamControllerRumble"\t\t"-1"')
        linhas.append("\t\t}")
    linhas += ["\t}"]
    if ps_support is not None:
        linhas.append(f'\t"SteamController_PSSupport"\t\t"{ps_support}"')
    linhas += ["}", ""]
    return "\n".join(linhas)


def _valor(texto: str, appid: str) -> str | None:
    """O `UseSteamControllerConfig` do appid na árvore VIVA, relido do zero."""
    viva = ponte.arvore_viva(ponte.ler_arvores(texto))
    if viva is None:
        return None
    achado = viva.chaves.get(appid)
    return achado[0] if achado is not None else None


# ---------------------------------------------------------------------------
# 1. A lista LIGA — a mordida
# ---------------------------------------------------------------------------
class TestAListaLiga:
    def test_o_jogo_da_lista_desligado_passa_a_ligado(self) -> None:
        """A MORDIDA. Antes desta leva o valor continuava `"0"` para sempre.

        Arranque a cura (o ramo `atual is not None` de `ligar_no_texto`, ou o
        `_CURAS[EXCECAO_INERTE]`) e este teste reprova dizendo o valor que
        sobrou.
        """
        texto = _vdf(viva={_SACKBOY: "0", _MMJ: "2"})
        assert _valor(texto, _SACKBOY) == "0"
        novo, ligados, pulados = ponte.ligar_no_texto(texto, [_SACKBOY, _MMJ])
        assert ligados == [_SACKBOY]
        assert pulados == [(_MMJ, ponte.JA_LIGADO)]
        assert _valor(novo, _SACKBOY) == "2"

    def test_o_jogo_sem_a_chave_ganha_a_chave(self) -> None:
        """Bloco do app existe e a Steam nunca escreveu a chave nele."""
        texto = _vdf(viva={_DONT_SCREAM: None})
        assert _valor(texto, _DONT_SCREAM) is None
        novo, ligados, _ = ponte.ligar_no_texto(texto, [_DONT_SCREAM])
        assert ligados == [_DONT_SCREAM]
        assert _valor(novo, _DONT_SCREAM) == "2"
        # e não inventou uma segunda ocorrência em lugar nenhum
        assert ponte.contar_chave_cru(novo) == ponte.contar_chave_cru(texto) + 1

    def test_o_jogo_sem_bloco_na_arvore_viva_ganha_o_bloco(self) -> None:
        """Jogo instalado que a Steam nunca abriu em Propriedades > Controle.

        A prova de que ele existe é o bloco na árvore CANÔNICA (onde a Steam
        guarda as `LaunchOptions` de todo jogo da biblioteca); a escrita cai na
        árvore VIVA, que ainda não tem bloco nenhum dele.
        """
        texto = _vdf(canonica={_DONT_SCREAM: "%command%"}, viva={_MMJ: "2"})
        novo, ligados, _ = ponte.ligar_no_texto(texto, [_DONT_SCREAM])
        assert ligados == [_DONT_SCREAM]
        assert _valor(novo, _DONT_SCREAM) == "2"
        assert _valor(novo, _MMJ) == "2"

    def test_appid_que_o_arquivo_desconhece_nao_vira_bloco_fantasma(self) -> None:
        """Número errado na lista, ou jogo de outra conta.

        Obedecer à lista dela não é inventar biblioteca — e uma pendência que
        nunca se resolve traria de volta o D-32: pré-voo dizendo "precisa" para
        sempre, e a Steam dela sendo fechada para não mudar byte nenhum.
        """
        texto = _vdf(viva={_MMJ: "2"})
        novo, ligados, pulados = ponte.ligar_no_texto(texto, ["404404"])
        assert novo == texto
        assert ligados == []
        assert pulados == [("404404", ponte.JOGO_DESCONHECIDO)]

    def test_rodar_duas_vezes_nao_muda_nada(self) -> None:
        texto = _vdf(viva={_SACKBOY: "0"})
        uma, _, _ = ponte.ligar_no_texto(texto, [_SACKBOY])
        duas, ligados, pulados = ponte.ligar_no_texto(uma, [_SACKBOY])
        assert duas == uma
        assert ligados == []
        assert pulados == [(_SACKBOY, ponte.JA_LIGADO)]

    def test_nada_alem_do_alvo_e_tocado(self) -> None:
        """O `localconfig.vdf` guarda a biblioteca inteira dela."""
        texto = _vdf(
            canonica={"999": "sh -c foo %command%"},
            viva={_SACKBOY: "0", "888": "0"},
        )
        novo, _, _ = ponte.ligar_no_texto(texto, [_SACKBOY])
        assert _valor(novo, "888") == "0"
        assert 'sh -c foo %command%' in novo
        assert len(novo.splitlines()) == len(texto.splitlines())


# ---------------------------------------------------------------------------
# 2. A árvore VIVA não é a canônica das LaunchOptions
# ---------------------------------------------------------------------------
class TestAArvoreViva:
    def test_a_chave_mora_na_outra_arvore(self) -> None:
        """Medido em 19/08/2026 no `localconfig.vdf` dela.

        As três árvores `apps` do arquivo, e onde cada chave estava::

            .../Software/Valve/Steam/apps   63 apps   LaunchOptions 63   UseSteamControllerConfig 0
            .../WebStorage/apps              3 apps   LaunchOptions  3   UseSteamControllerConfig 0
            UserLocalConfigStore/apps       11 apps   LaunchOptions 11   UseSteamControllerConfig 11

        Aplicar aqui a âncora do `ARVORE-ERRADA-01` (que é a certa para as
        `LaunchOptions`) seria escrever num lugar que a Steam não lê.
        """
        texto = _vdf(canonica={_SACKBOY: "%command%"}, viva={_SACKBOY: "0"})
        arvores = ponte.ler_arvores(texto)
        assert [a.caminho for a in arvores] == [
            "UserLocalConfigStore/Software/Valve/Steam/apps",
            "UserLocalConfigStore/apps",
        ]
        viva = ponte.arvore_viva(arvores)
        assert viva is not None
        assert viva.caminho == "UserLocalConfigStore/apps"

    def test_a_escrita_cai_na_arvore_viva_e_so_nela(self) -> None:
        texto = _vdf(canonica={_SACKBOY: "%command%"}, viva={_SACKBOY: "0"})
        novo, _, _ = ponte.ligar_no_texto(texto, [_SACKBOY])
        canonica, viva = ponte.ler_arvores(novo)
        assert canonica.chaves == {}
        assert viva.chaves[_SACKBOY][0] == "2"

    def test_a_irma_global_acha_a_arvore_num_arquivo_sem_a_chave(self) -> None:
        """Perfil recém-criado: nenhum jogo tem a chave ainda.

        A âncora é o `SteamController_PSSupport`, que mora no bloco PAI da
        árvore viva — e no arquivo dela ele aparece DEPOIS do `}` que a fecha,
        que é o detalhe de ordem capaz de fazer o portão responder o contrário
        do que vê.
        """
        texto = _vdf(canonica={_SACKBOY: "%command%"}, viva={_SACKBOY: None})
        viva = ponte.arvore_viva(ponte.ler_arvores(texto))
        assert viva is not None
        assert viva.caminho == "UserLocalConfigStore/apps"
        assert viva.irma_do_pssupport

    def test_sem_ancora_nenhuma_o_produto_recusa_escrever(self) -> None:
        """Nem a chave, nem a irmã. Escrever no escuro é o que não se faz."""
        texto = _vdf(canonica={_SACKBOY: "%command%"}, viva={}, ps_support=None)
        novo, ligados, pulados = ponte.ligar_no_texto(texto, [_SACKBOY])
        assert novo == texto
        assert ligados == []
        assert pulados == [(_SACKBOY, ponte.ARVORE_DESCONHECIDA)]


# ---------------------------------------------------------------------------
# 3. As duas réguas
# ---------------------------------------------------------------------------
class TestAsDuasReguas:
    def test_a_regua_bruta_e_a_estrutural_batem_no_layout_real(self) -> None:
        texto = _vdf(viva={_SACKBOY: "0", _MMJ: "2", "888": "0"})
        arvores = ponte.ler_arvores(texto)
        assert ponte.contar_chave_cru(texto) == sum(len(a.chaves) for a in arvores)
        assert ponte.conferir_reguas(texto, arvores) is None

    def test_chave_fora_de_bloco_de_app_derruba_a_escrita(self) -> None:
        """Uma ocorrência que a navegação não sabe atribuir = recusa.

        É a lição do `O PORTÃO PODE OLHAR PARA O LUGAR ERRADO`: régua sozinha
        mente com convicção. Aqui a bruta conta 2 e a estrutural atribui 1 —
        e o produto prefere não escrever a escrever no lugar errado.
        """
        texto = _vdf(viva={_SACKBOY: "0"}).replace(
            '\t"SteamController_PSSupport"',
            '\t"UseSteamControllerConfig"\t\t"1"\n\t"SteamController_PSSupport"',
        )
        arvores = ponte.ler_arvores(texto)
        assert ponte.contar_chave_cru(texto) == 2
        assert sum(len(a.chaves) for a in arvores) == 1
        novo, _ligados, pulados = ponte.ligar_no_texto(texto, [_SACKBOY])
        assert novo == texto
        assert pulados == [(_SACKBOY, ponte.REGUAS_DIVERGEM)]

    def test_duas_arvores_com_a_chave_e_ambiguidade_declarada(self) -> None:
        """O appid nas duas: daqui não dá para saber qual a Steam lê."""
        texto = _vdf(viva={_SACKBOY: "0"}).replace(
            '\t\t\t\t"apps"\n\t\t\t\t{',
            '\t\t\t\t"apps"\n\t\t\t\t{\n'
            f'\t\t\t\t\t"{_SACKBOY}"\n\t\t\t\t\t{{\n'
            '\t\t\t\t\t\t"UseSteamControllerConfig"\t\t"0"\n'
            "\t\t\t\t\t}",
        )
        assert ponte.arvore_viva(ponte.ler_arvores(texto)) is None
        novo, _, pulados = ponte.ligar_no_texto(texto, [_SACKBOY])
        assert novo == texto
        assert pulados == [(_SACKBOY, ponte.ARVORE_DESCONHECIDA)]

    def test_a_conferencia_da_escrita_e_uma_segunda_passada(self) -> None:
        """Escrever e acreditar no próprio relatório é o defeito da casa."""
        texto = _vdf(viva={_SACKBOY: "0"})
        novo, ligados, _ = ponte.ligar_no_texto(texto, [_SACKBOY])
        assert ponte.conferir_escrita(texto, novo, ligados) is None
        # o mesmo relatório sobre um texto que NÃO mudou é reprovado
        assert ponte.conferir_escrita(texto, texto, [_SACKBOY]) == f"nao_ligou:{_SACKBOY}"


# ---------------------------------------------------------------------------
# 4. O estado, os portões e a promessa honesta
# ---------------------------------------------------------------------------
class TestOEstadoEOsPortoes:
    @pytest.fixture()
    def casa(self, tmp_path: Path) -> Path:
        config = tmp_path / ".steam/steam/userdata/1/config"
        config.mkdir(parents=True)
        (config / "localconfig.vdf").write_text(
            _vdf(viva={_SACKBOY: "0", _MMJ: "2"}), encoding="utf-8"
        )
        return tmp_path

    def _vdf_de(self, casa: Path) -> Path:
        return casa / ".steam/steam/userdata/1/config/localconfig.vdf"

    def test_o_estado_nomeia_o_jogo_pendente(self, casa: Path) -> None:
        estado = ponte.estado_da_ponte(casa, allowlist=[_SACKBOY, _MMJ])
        assert [p.appid for p in estado.pendentes] == [_SACKBOY]
        assert estado.ligados == [_MMJ]
        assert _SACKBOY in estado.frase()

    def test_com_a_steam_viva_adia_e_diz_que_adiou(
        self, casa: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A promessa honesta: a escrita só sobrevive com a Steam FECHADA.

        Ela regrava o `localconfig.vdf` ao sair e engole a edição feita por
        baixo. Prometer mais que isto seria a mentira do `resultado=aplicado`
        sobre um no-op, que esta casa já pagou uma vez.
        """
        monkeypatch.setattr(ponte, "steam_running", lambda: True)
        monkeypatch.setattr(ponte, "steam_game_running", lambda: False)
        antes = self._vdf_de(casa).read_text(encoding="utf-8")
        status, estado, _ = ponte.garantir_ponte(casa, allowlist=[_SACKBOY])
        assert status == ponte.PONTE_ADIADA_STEAM
        assert self._vdf_de(casa).read_text(encoding="utf-8") == antes
        assert "assim que a Steam fechar" in estado.frase()

    def test_com_jogo_aberto_nem_cogita(
        self, casa: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fechar a Steam com jogo aberto MATA o jogo. Este portão vem antes."""
        monkeypatch.setattr(ponte, "steam_running", lambda: True)
        monkeypatch.setattr(ponte, "steam_game_running", lambda: True)
        status, _, _ = ponte.garantir_ponte(casa, allowlist=[_SACKBOY])
        assert status == ponte.PONTE_ADIADA_JOGO

    def test_com_a_steam_fechada_escreve_e_guarda_backup(
        self, casa: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ponte, "steam_running", lambda: False)
        monkeypatch.setattr(ponte, "steam_game_running", lambda: False)
        status, _, detalhe = ponte.garantir_ponte(casa, allowlist=[_SACKBOY])
        assert status == ponte.PONTE_LIGADA
        assert _valor(self._vdf_de(casa).read_text(encoding="utf-8"), _SACKBOY) == "2"
        assert [d["appid"] for d in detalhe if d["desfecho"] == ponte.PONTE_LIGADA] == [
            _SACKBOY
        ]
        backups = list(self._vdf_de(casa).parent.glob("*.bak.steam-input-ponte-*"))
        assert len(backups) == 1
        assert _valor(backups[0].read_text(encoding="utf-8"), _SACKBOY) == "0"

    def test_dry_run_nao_escreve_com_a_steam_viva(
        self, casa: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ponte, "steam_running", lambda: True)
        monkeypatch.setattr(ponte, "steam_game_running", lambda: False)
        antes = self._vdf_de(casa).read_text(encoding="utf-8")
        status, _, _ = ponte.garantir_ponte(
            casa, allowlist=[_SACKBOY], dry_run=True
        )
        assert status == ponte.PONTE_LIGADA
        assert self._vdf_de(casa).read_text(encoding="utf-8") == antes

    def test_lista_vazia_nao_inventa_trabalho(
        self, casa: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ponte, "steam_running", lambda: False)
        monkeypatch.setattr(ponte, "steam_game_running", lambda: False)
        status, _, _ = ponte.garantir_ponte(casa, allowlist=[])
        assert status == ponte.PONTE_NADA


# ---------------------------------------------------------------------------
# 5. O prontuário deixou de ser modelo sem uso
# ---------------------------------------------------------------------------
class TestOProntuarioLigado:
    def test_todo_estorvo_automatico_tem_quem_o_cure(self) -> None:
        """A MORDIDA do item 2 da frente.

        O prontuário nasceu em 16/08 modelando `Estorvo.automatica` — *"O
        produto conserta sozinho, sem ela clicar em nada?"* — e nada do produto
        o importava. Um `True` ali sem entrada em `_CURAS` é promessa sem dono,
        e é exatamente o defeito mais caro desta casa: a cura escrita e nunca
        ligada.
        """
        automaticos = {chave for chave, dados in _ESTORVOS.items() if dados[2]}
        assert automaticos, "nenhum estorvo automático — o modelo esvaziou"
        assert automaticos <= set(_CURAS), (
            f"estorvo automático sem cura ligada: {sorted(automaticos - set(_CURAS))}"
        )

    def test_a_excecao_inerte_deixou_de_ser_manual(self) -> None:
        """Era `automatica=False` com a cura mandando ELA clicar na Steam."""
        estorvo = Estorvo(EXCECAO_INERTE)
        assert estorvo.automatica
        assert "Ligue o Steam Input" not in estorvo.a_cura
        assert "sozinho" in estorvo.a_cura
        assert "Steam fechar" in estorvo.a_cura

    def test_a_cura_automatica_liga_de_verdade(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O fio inteiro: censo -> estorvo automático -> ponte -> vdf escrito.

        É esta a diferença entre modelar uma cura e APLICÁ-LA. O prontuário
        sabia tudo isto em 16/08 e nada do produto o chamava.
        """
        steamapps = tmp_path / ".steam/steam/steamapps"
        (steamapps / "common/Sackboy").mkdir(parents=True)
        (steamapps / f"appmanifest_{_SACKBOY}.acf").write_text(
            '"AppState"\n{\n'
            f'\t"appid"\t\t"{_SACKBOY}"\n'
            '\t"name"\t\t"Sackboy"\n'
            '\t"installdir"\t\t"Sackboy"\n}\n',
            encoding="utf-8",
        )
        config = tmp_path / ".steam/steam/userdata/1/config"
        config.mkdir(parents=True)
        vdf = config / "localconfig.vdf"
        vdf.write_text(
            _vdf(
                canonica={_SACKBOY: "sh -c 'x' hefesto-launch %command%"},
                viva={_SACKBOY: "0"},
            ),
            encoding="utf-8",
        )
        lista = tmp_path / ".config/hefesto-dualsense4unix/steam_input_apps.txt"
        lista.parent.mkdir(parents=True)
        lista.write_text(f"# bancada\n{_SACKBOY}\n", encoding="utf-8")
        # A lista é lida por `XDG_CONFIG_HOME`, do mesmo jeito no censo, na
        # ponte e no guarda. Sem fixar aqui, a bancada leria a allowlist REAL
        # da mantenedora e o teste passaria a depender do disco dela.
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
        monkeypatch.setattr(ponte, "steam_running", lambda: False)
        monkeypatch.setattr(ponte, "steam_game_running", lambda: False)

        cura = curar_o_que_e_automatico(tmp_path)

        assert cura.desfechos[EXCECAO_INERTE] == ponte.PONTE_LIGADA
        assert cura.tocados[EXCECAO_INERTE] == [_SACKBOY]
        assert _valor(vdf.read_text(encoding="utf-8"), _SACKBOY) == "2"

    def test_a_simulacao_nao_diz_consertei(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HONESTIDADE-STEAM-01 aplicada aqui: no-op não vira anúncio de sucesso."""
        cura = Cura(
            status=CURA_FEITA,
            tocados={EXCECAO_INERTE: [_SACKBOY]},
            simulacao=True,
        )
        assert "Consertaria" in cura.frase()
        assert "nada foi escrito" in cura.frase()
        assert "Consertei" not in cura.frase()

    def test_o_estorvo_continua_sendo_nomeado_enquanto_pendente(self) -> None:
        """Curar sozinho não é motivo para calar: enquanto a Steam está viva o
        jogo segue impedido, e a tela tem de dizer isso."""
        ficha = Prontuario(
            appid=_SACKBOY, nome="Sackboy", raiz=Path("/jogo"),
            linha="sh -c 'x' hefesto-launch %command%",
            steam_input="0", na_allowlist=True,
        )
        assert EXCECAO_INERTE in [e.chave for e in ficha.estorvos]


# ---------------------------------------------------------------------------
# 6. O guarda — bash de verdade, no instante em que a escrita sobrevive
# ---------------------------------------------------------------------------
_BASH = shutil.which("bash") or "/bin/bash"
_RAIZ = Path(__file__).resolve().parents[2]
_GUARDA = _RAIZ / "scripts" / "disable_steam_input.sh"


class TestOGuardaConstroiAPonte:
    """O gatilho já existia: o `hefesto-steam-input-guard` acorda quando o
    `userdata` muda — isto é, quando a Steam ACABOU de sair. Inventar um
    gatilho novo seria refazer o que já está de pé.

    Execução real do bash, com HOME em `tmp_path` e `pgrep`/`steam`/`sleep`
    stubados no PATH: nenhum processo desta máquina é tocado.
    """

    @pytest.fixture()
    def bancada(self, tmp_path: Path) -> dict[str, Any]:
        home = tmp_path / "home"
        vdf = home / ".steam/steam/userdata/1/config/localconfig.vdf"
        vdf.parent.mkdir(parents=True)
        # Um jogo da lista DESLIGADO (a exceção inerte), um fora dela LIGADO
        # (que o guarda tem de continuar desligando).
        vdf.write_text(
            _vdf(viva={_SACKBOY: "0", _DONT_SCREAM: "2"}, ps_support="2"),
            encoding="utf-8",
        )
        lista = home / ".config/hefesto-dualsense4unix/steam_input_apps.txt"
        lista.parent.mkdir(parents=True)
        lista.write_text(f"# bancada\n{_SACKBOY}\n", encoding="utf-8")

        stubs = tmp_path / "stubs"
        stubs.mkdir()
        for nome, corpo in (
            ("pgrep", "exit 1"),
            ("steam", "exit 0"),
            ("sleep", "exit 0"),
        ):
            alvo = stubs / nome
            alvo.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
            alvo.chmod(0o755)
        return {"home": home, "vdf": vdf, "stubs": stubs}

    def _roda(
        self, bancada: dict[str, Any], *args: str
    ) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["HOME"] = str(bancada["home"])
        # Sem fixar o XDG, um shell com ele exportado (o caso desta máquina)
        # faria a bancada ler a allowlist REAL da mantenedora.
        env["XDG_CONFIG_HOME"] = str(bancada["home"] / ".config")
        env["PATH"] = f"{bancada['stubs']}:/usr/bin:/bin"
        return subprocess.run(
            [_BASH, str(_GUARDA), *args],
            capture_output=True, text=True, check=False, env=env, timeout=120,
        )

    def test_bash_n_limpo(self) -> None:
        proc = subprocess.run(
            ["bash", "-n", str(_GUARDA)], capture_output=True, text=True, check=False
        )
        assert proc.returncode == 0, proc.stderr

    def test_o_guarda_desliga_o_de_fora_e_liga_o_da_lista(
        self, bancada: dict[str, Any]
    ) -> None:
        """A MORDIDA no shell, e as duas metades no mesmo arquivo.

        Antes desta leva o guarda só sabia descer: o de fora ia a `"0"` e o da
        lista ficava em `"0"` para sempre. É a linha exata que custou DON'T
        SCREAM — o produto desligando a única ponte que o fazia funcionar.
        """
        proc = self._roda(bancada, "--apply-quiet")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        texto = bancada["vdf"].read_text(encoding="utf-8")
        assert _valor(texto, _SACKBOY) == "2", proc.stdout
        assert _valor(texto, _DONT_SCREAM) == "0", proc.stdout
        assert '"SteamController_PSSupport"\t\t"0"' in texto

    def test_segunda_rodada_nao_mexe_em_nada(self, bancada: dict[str, Any]) -> None:
        self._roda(bancada, "--apply-quiet")
        depois_da_primeira = bancada["vdf"].read_text(encoding="utf-8")
        backups_antes = len(list(bancada["vdf"].parent.glob("*.bak.*")))

        proc = self._roda(bancada, "--apply-quiet")

        assert proc.returncode == 0
        assert bancada["vdf"].read_text(encoding="utf-8") == depois_da_primeira
        assert len(list(bancada["vdf"].parent.glob("*.bak.*"))) == backups_antes
        assert "resultado=nada-a-fazer" in proc.stdout

    def test_o_status_nao_diz_tudo_limpo_com_a_excecao_inerte(
        self, bancada: dict[str, Any]
    ) -> None:
        """O portão que olha para o lugar errado encerra a busca.

        Foi lendo um "tudo limpo" que a noite de 18/08 se perdeu.
        """
        original = bancada["vdf"].read_text(encoding="utf-8")

        proc = self._roda(bancada, "--status")

        assert "resultado=precisa-corrigir" in proc.stdout
        assert "ponte pendente" in proc.stdout
        assert bancada["vdf"].read_text(encoding="utf-8") == original

    def test_com_a_ponte_de_pe_o_status_fica_limpo(
        self, bancada: dict[str, Any]
    ) -> None:
        """Contraprova: sem esta metade, um `precisa-corrigir` fixo passaria."""
        self._roda(bancada, "--apply-quiet")

        proc = self._roda(bancada, "--status")

        assert "resultado=nada-a-fazer" in proc.stdout
        assert "ponte pendente" not in proc.stdout
