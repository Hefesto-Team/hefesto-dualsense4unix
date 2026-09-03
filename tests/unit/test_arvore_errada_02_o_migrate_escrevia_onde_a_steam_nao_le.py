"""ARVORE-ERRADA-02 — o `migrate` plantava a chamada do wrapper onde a Steam
não lê.

O irmão deste teste, `test_arvore_errada_01_o_censo_lia_o_apps_que_a_steam_nao_le`,
fechou o LEITOR (`read_apps_by_appid`) e o ESCRITOR em massa
(`apply_wrapper_vdf_text`) em 16/08/2026: os dois passaram a exigir o caminho
inteiro ``…/Software/Valve/Steam/apps/<appid>``.

**`transform_vdf_text` ficou para trás.** Ela varria o arquivo LINHA a LINHA,
sem saber em que bloco estava, e por isso o modo `migrate` reescrevia qualquer
`LaunchOptions` envenenada — inclusive as das duas árvores `apps` que a Steam
não consulta.

MEDIDO no `localconfig.vdf` dela em 02/09/2026, com a régua deste arquivo:

===============================================  =========================
árvore                                           blocos com LaunchOptions
===============================================  =========================
``UserLocalConfigStore/Software/Valve/Steam/apps``  63  (a viva)
``UserLocalConfigStore/apps``                       10
``UserLocalConfigStore/WebStorage/apps``             3
===============================================  =========================

As treze de fora nasceram da aplicação em massa de 21/07 e são inertes: a Steam
nunca as lê. O custo delas não é o jogo — é a leitura humana, e já custou uma
acusação falsa no `doctor.sh` (*"o censo as conta como cobertura"*, que o censo
não faz desde 16/08).

**A ASSIMETRIA É O CONTRATO, e é o que este arquivo trava:**

- `migrate` só escreve na árvore canônica. Fora dela, o modo `migrate` age
  como `strip`: tira o nosso pedaço e devolve o resto do valor a quem escreveu.
  Plantar a chamada do wrapper onde ninguém lê é criar cobertura de mentira.
- `strip` continua alcançando TODAS as árvores. É o único caminho de volta do
  que já foi plantado; ancorá-lo deixaria o lixo lá para sempre.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import steam_launch_options as slo

ROOT_DO_MODULO = Path(slo.__file__)

#: A variante de onda anterior persistida no vdf real (a "linha 914").
LINHA_914 = (
    "SDL_JOYSTICK_HIDAPI=0 SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6 "
    "__GL_SHADER_DISK_CACHE=1 __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1 %command%"
)

_TAB = "\t"


def _bloco_apps(nivel: int, launch_options: dict[str, str]) -> str:
    """Um bloco ``"apps" { "<appid>" { "LaunchOptions" "<v>" } }`` indentado."""
    dentro = ""
    for appid, valor in launch_options.items():
        dentro += (
            f'{_TAB * (nivel + 1)}"{appid}"\n{_TAB * (nivel + 1)}{{\n'
            f'{_TAB * (nivel + 2)}"LaunchOptions"{_TAB * 2}"{valor}"\n'
            f'{_TAB * (nivel + 2)}"playtime"{_TAB * 2}"42"\n'
            f"{_TAB * (nivel + 1)}}}\n"
        )
    return f'{_TAB * nivel}"apps"\n{_TAB * nivel}{{\n{dentro}{_TAB * nivel}}}\n'


def _vdf_das_tres_arvores(
    *,
    viva: dict[str, str] | None = None,
    solta: dict[str, str] | None = None,
    web: dict[str, str] | None = None,
) -> str:
    """As TRÊS árvores `apps` do arquivo dela, no mesmo aninhamento medido.

    ``viva``  -> UserLocalConfigStore/Software/Valve/Steam/apps  (a que a Steam lê)
    ``solta`` -> UserLocalConfigStore/apps
    ``web``   -> UserLocalConfigStore/WebStorage/apps
    """
    corpo = (
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f"{_bloco_apps(4, viva or {})}"
        f"{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n"
    )
    corpo += _bloco_apps(1, solta or {})
    corpo += (
        f'{_TAB}"WebStorage"\n{_TAB}{{\n'
        f"{_bloco_apps(2, web or {})}"
        f"{_TAB}}}\n"
    )
    return '"UserLocalConfigStore"\n{\n' + corpo + "}\n"


def _valores_por_arvore(texto: str) -> dict[str, dict[str, str]]:
    """Régua INDEPENDENTE do produto: caminho inteiro -> {appid: valor}.

    Reimplementa a pilha de blocos em vinte linhas de propósito — uma régua que
    compartilha o parser com o código que ela audita não pode acusá-lo.
    """
    fora: dict[str, dict[str, str]] = {}
    pilha: list[str] = []
    pendente: str | None = None
    for bruta in texto.splitlines():
        linha = bruta.strip()
        if not linha:
            continue
        if linha == "{":
            pilha.append(pendente or "")
            pendente = None
            continue
        if linha == "}":
            if pilha:
                pilha.pop()
            pendente = None
            continue
        par = slo._VDF_PAIR_RE.match(linha)
        if par is not None:
            pendente = None
            if slo._vdf_unescape(par.group("key")).lower() != "launchoptions":
                continue
            if not pilha:
                continue
            caminho = "/".join(pilha[:-1])
            fora.setdefault(caminho, {})[pilha[-1]] = slo._vdf_unescape(
                par.group("value")
            )
            continue
        so_chave = slo._VDF_KEY_ONLY_RE.match(linha)
        pendente = (
            slo._vdf_unescape(so_chave.group("key")) if so_chave is not None else None
        )
    return fora


CANONICA = "UserLocalConfigStore/Software/Valve/Steam/apps"
SOLTA = "UserLocalConfigStore/apps"
WEB = "UserLocalConfigStore/WebStorage/apps"


class TestOMigrateSoEscreveOndeASteamLe:
    def test_a_regua_deste_arquivo_enxerga_as_tres_arvores(self) -> None:
        """CONTROLE DA RÉGUA: sem isto, um `not in` passa por cegueira."""
        texto = _vdf_das_tres_arvores(
            viva={"620": LINHA_914}, solta={"620": LINHA_914}, web={"620": LINHA_914}
        )
        arvores = _valores_por_arvore(texto)
        assert set(arvores) == {CANONICA, SOLTA, WEB}, arvores
        assert arvores[SOLTA]["620"] == LINHA_914

    def test_o_wrapper_nao_entra_na_arvore_que_a_steam_nao_le(self) -> None:
        texto = _vdf_das_tres_arvores(solta={"620": LINHA_914}, web={"440": LINHA_914})
        novo, mudadas = slo.transform_vdf_text(texto, "migrate")
        arvores = _valores_por_arvore(novo)
        assert mudadas == 2, novo
        for caminho, appid in ((SOLTA, "620"), (WEB, "440")):
            valor = arvores[caminho][appid]
            assert slo.WRAPPER_PREFIX not in valor, (caminho, valor)
            # E o veneno saiu: fora da canônica o `migrate` age como `strip`.
            assert slo.IGNORE_SIGNATURE not in valor, (caminho, valor)
            # O que era dela fica: o shader-cache é escolha de quem escreveu.
            assert "__GL_SHADER_DISK_CACHE=1" in valor, (caminho, valor)

    def test_na_arvore_viva_o_migrate_continua_embrulhando(self) -> None:
        """O NEGATIVO que impede a cura de virar 'não faz nada em lugar nenhum'."""
        texto = _vdf_das_tres_arvores(viva={"620": LINHA_914})
        novo, mudadas = slo.transform_vdf_text(texto, "migrate")
        assert mudadas == 1
        assert slo.WRAPPER_PREFIX in _valores_por_arvore(novo)[CANONICA]["620"]

    def test_o_mesmo_appid_nas_duas_arvores_so_ganha_wrapper_na_viva(self) -> None:
        """O retrato do arquivo dela: o appid existe nas duas árvores."""
        texto = _vdf_das_tres_arvores(
            viva={"2358720": LINHA_914}, solta={"2358720": LINHA_914}
        )
        novo, _ = slo.transform_vdf_text(texto, "migrate")
        arvores = _valores_por_arvore(novo)
        assert slo.WRAPPER_PREFIX in arvores[CANONICA]["2358720"]
        assert slo.WRAPPER_PREFIX not in arvores[SOLTA]["2358720"]

    def test_o_strip_continua_alcancando_todas_as_arvores(self) -> None:
        """Ancorar o `strip` deixaria o lixo já plantado lá para sempre."""
        # O wrapper carrega aspas: no arquivo ele vive ESCAPADO (KeyValues).
        plantado = slo._vdf_escape(f"{slo.WRAPPER_PREFIX} MANGOHUD=1 %command%")
        texto = _vdf_das_tres_arvores(
            viva={"620": plantado}, solta={"620": plantado}, web={"440": plantado}
        )
        novo, mudadas = slo.transform_vdf_text(texto, "strip")
        assert mudadas == 3, novo
        arvores = _valores_por_arvore(novo)
        for caminho, appid in ((CANONICA, "620"), (SOLTA, "620"), (WEB, "440")):
            assert arvores[caminho][appid] == "MANGOHUD=1 %command%", caminho

    def test_modo_desconhecido_continua_explodindo(self) -> None:
        with pytest.raises(ValueError):
            slo.transform_vdf_text("", "apagar_tudo")

    def test_linha_alheia_fora_da_canonica_passa_intacta(self) -> None:
        """A linha VKD3D dela, sem veneno e sem wrapper, não é nossa para mexer.

        É o estado real do `UserLocalConfigStore/apps` dela em 02/09/2026: dez
        blocos com `VKD3D_CONFIG=no_upload_hvv %command%` e nada de nosso.
        """
        dela = "VKD3D_CONFIG=no_upload_hvv %command%"
        texto = _vdf_das_tres_arvores(solta={"413080": dela})
        for modo in ("migrate", "strip"):
            novo, mudadas = slo.transform_vdf_text(texto, modo)
            assert mudadas == 0, modo
            assert novo == texto, modo


class TestORecolherEOCaminhoDeVolta:
    """`recolher` apaga a linha INTEIRA, e só fora da árvore viva.

    É a resposta para o que já foi plantado e não dá mais para reconhecer pelo
    valor: em 02/09/2026 as dez linhas de `UserLocalConfigStore/apps` dela
    carregam `VKD3D_CONFIG=no_upload_hvv %command%` — texto DELA, sobrando de
    um `strip` que comeu a nossa parte. Nem o `strip` nem o `migrate` as veem,
    porque os dois só tocam linha com veneno ou com o wrapper.

    NUNCA roda sozinho: só pela flag `--recolher-fora-da-arvore-viva`.
    """

    def test_apaga_a_linha_de_fora_e_nao_a_de_dentro(self) -> None:
        dela = "VKD3D_CONFIG=no_upload_hvv %command%"
        texto = _vdf_das_tres_arvores(
            viva={"316790": LINHA_914}, solta={"413080": dela}, web={"440": ""}
        )
        novo, mudadas = slo.transform_vdf_text(texto, "recolher")
        assert mudadas == 2, novo
        arvores = _valores_por_arvore(novo)
        assert arvores[CANONICA]["316790"] == LINHA_914
        assert SOLTA not in arvores, arvores
        assert WEB not in arvores, arvores

    def test_o_resto_do_bloco_da_steam_fica_de_pe(self) -> None:
        """Só a linha nossa sai — o bloco continua sendo da Steam."""
        texto = _vdf_das_tres_arvores(solta={"413080": "seja o que for"})
        novo, _ = slo.transform_vdf_text(texto, "recolher")
        assert '"playtime"' in novo
        assert novo.count("{") == texto.count("{")
        assert novo.count("}") == texto.count("}")
        assert "LaunchOptions" not in novo

    def test_arvore_so_com_a_viva_nao_muda_um_byte(self) -> None:
        texto = _vdf_das_tres_arvores(viva={"316790": LINHA_914})
        novo, mudadas = slo.transform_vdf_text(texto, "recolher")
        assert mudadas == 0
        assert novo == texto

    def test_a_flag_do_cli_existe_e_e_a_unica_porta(self) -> None:
        """Modo que APAGA não pode ser alcançável por acidente."""
        fonte = (
            ROOT_DO_MODULO.read_text(encoding="utf-8")
        )
        assert '"--recolher-fora-da-arvore-viva"' in fonte
        assert fonte.count('mode = "recolher"') == 1
