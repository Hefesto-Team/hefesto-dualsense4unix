#!/usr/bin/env python3
"""Aplicar nos lançadores troca só o que o Hefesto escreveu na opção de lançamento."""
from __future__ import annotations

import random
import re
from collections import Counter
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import opcoes_por_jogo as opj
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

APPID = "1912410"
OPCOES = "VKD3D_CONFIG=no_upload_hvv %command%"
DELA = 'WINEDLLOVERRIDES="xgameruntime=n" &&'
TOKEN = re.compile(r"""(?:[^\s'"]|'[^']*'|"[^"]*")+""")
COOCORRENTES = ("SDL_JOYSTICK_HIDAPI=0", "PROTON_ENABLE_HIDRAW=1")
CACHE = ("__GL_SHADER_DISK_CACHE=1", "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1")
BLOCO_LEGADO = f"{COOCORRENTES[0]} {slo.IGNORE_SIGNATURE} {CACHE[0]} {CACHE[1]}"


def _tokens(linha: str) -> list[str]:
    return TOKEN.findall(linha)


def _tokens_dela(rng: random.Random) -> list[str]:
    """Pedaços que um usuário escreve à mão, inclusive os que parecem os nossos."""
    pecas = [
        "MANGOHUD=1", "DXVK_HUD=fps", "PROTON_LOG=1", "-windowed", "gamemoderun",
        COOCORRENTES[0], COOCORRENTES[1], CACHE[0], CACHE[1],
        'WINEDLLOVERRIDES="xgameruntime=n"', "&&", "sh -c 'echo oi'", 'FOO="a b"',
        "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x057e/0x2009",
    ]
    return [rng.choice(pecas) for _ in range(rng.randint(0, 5))]


def _linha_dela(rng: random.Random) -> str:
    """Uma linha sem a nossa assinatura, com `%command%` no meio de pedaços dela."""
    antes, depois = _tokens_dela(rng), _tokens_dela(rng)
    return " ".join([*antes, "%command%", *depois])


def test_o_migrate_e_o_strip_se_desfazem_em_toda_linha_sem_a_nossa_assinatura() -> None:
    """Régua de propriedade: nenhum token dela some, e `strip(migrate(v)) == v`.

    ARRANQUE o `_tirar_vizinhos_legados` (volte o `_remove_token` em qualquer posição)
    e este teste reprova: a linha dela com `SDL_JOYSTICK_HIDAPI=0` solto perde o token.
    """
    rng = random.Random(20261013)
    vistos = 0
    for _ in range(600):
        v = _linha_dela(rng)
        if slo.has_poison(v) or slo.WRAPPER_PREFIX in v or v.strip() == "%command%":
            continue
        vistos += 1
        migrado = slo.migrate_value(v)
        assert all(t in _tokens(migrado) for t in _tokens(v)), (v, migrado)
        assert slo.strip_value(migrado) == v, (v, migrado)
    assert vistos > 300


def test_o_veneno_legado_sai_inteiro_e_o_que_e_dela_fica_na_conta_exata() -> None:
    """O bloco contíguo é nosso; o mesmo token separado dele por algo dela é do usuário."""
    rng = random.Random(7)
    for _ in range(300):
        antes, depois = _tokens_dela(rng), _tokens_dela(rng)
        v = " ".join([*antes, "SEP=1", BLOCO_LEGADO, "SEP=2", *depois, "%command%"])
        dela = Counter(_tokens(" ".join([*antes, "SEP=1", "SEP=2", *depois, "%command%"])))
        tirado = Counter(_tokens(slo.strip_value(v)))
        assert tirado == dela + Counter(CACHE), (v, slo.strip_value(v))
        assert Counter(_tokens(slo.migrate_value(v))) == (
            dela + Counter(_tokens(slo.WRAPPER_PREFIX))), (v, slo.migrate_value(v))
        assert slo.IGNORE_SIGNATURE not in slo.strip_value(v)


@pytest.mark.parametrize("posicao", ["antes", "meio", "depois"])
def test_o_co_ocorrente_dela_longe_do_nosso_par_nao_some(posicao: str) -> None:
    """Medido: com o par legado na linha, o `HIDAPI=0` que ela pôs à mão ia junto."""
    dela = COOCORRENTES[1]
    pedacos = {
        "antes": f"{dela} MANGOHUD=1 {BLOCO_LEGADO} %command%",
        "meio": f"{BLOCO_LEGADO} MANGOHUD=1 {dela} %command%",
        "depois": f"{BLOCO_LEGADO} MANGOHUD=1 {dela} %command%",
    }
    v = pedacos[posicao]
    assert dela in _tokens(slo.strip_value(v))
    assert dela in _tokens(slo.migrate_value(v))
    assert COOCORRENTES[0] not in _tokens(slo.migrate_value(v))


def test_a_linha_dela_com_prefixo_antes_do_atalho_atravessa_o_migrate_e_o_strip() -> None:
    v = f"{DELA} sh -c 'echo oi' && {BLOCO_LEGADO} %command%"
    migrado = slo.migrate_value(v)
    assert DELA in migrado and "sh -c 'echo oi'" in migrado
    assert slo.IGNORE_SIGNATURE not in migrado
    depois = slo.strip_value(migrado)
    assert depois.startswith(DELA) and "sh -c 'echo oi'" in depois


def _vdf(linha: str, copias: tuple[str, ...] = ()) -> str:
    filhos = "".join(
        f'\t\t\t\t\t\t"cloud"\n\t\t\t\t\t\t{{\n\t\t\t\t\t\t\t"LaunchOptions"\t\t"{c}"\n'
        "\t\t\t\t\t\t}\n" for c in copias
    )
    return (
        '"UserLocalConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n'
        '\t\t\t{\n\t\t\t\t"apps"\n\t\t\t\t{\n'
        f'\t\t\t\t\t"{APPID}"\n\t\t\t\t\t{{\n{filhos}'
        f'\t\t\t\t\t\t"LaunchOptions"\t\t"{slo._vdf_escape(linha)}"\n'
        '\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n'
    )


@pytest.fixture(autouse=True)
def _a_steam_esta_fechada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(opj, "steam_running", lambda: False)
    monkeypatch.setattr(opj, "steam_game_running", lambda: False)
    monkeypatch.setattr(opj, "ler_jogos_sem_wrapper", lambda *_a, **_k: [])


class _Lar:
    def __init__(self, raiz: Path, linha: str, copias: tuple[str, ...] = ()) -> None:
        self.raiz = raiz
        self.vdf = raiz / "userdata" / "1" / "config" / "localconfig.vdf"
        self.vdf.parent.mkdir(parents=True)
        self.vdf.write_text(_vdf(linha, copias), encoding="utf-8")
        self.estado = raiz / "estado"

    def tabela(self, opcoes: str) -> None:
        opj.gravar({APPID: opcoes}, config_home=self.raiz)

    def aplica(self) -> opj.Relato:
        return opj.aplicar(vdfs=[self.vdf], config_home=self.raiz, estado_home=self.estado)

    def confere(self) -> dict[str, object]:
        return opj.conferir(vdfs=[self.vdf], config_home=self.raiz, estado_home=self.estado)

    def linha(self) -> str:
        return slo.read_launch_options_by_appid(self.vdf.read_text(encoding="utf-8"))[APPID]


def test_a_tabela_sobre_a_linha_do_minecraft_mantem_o_prefixo_dela(tmp_path: Path) -> None:
    """O caso vivo: `WINEDLLOVERRIDES="…" &&` só existe no vdf. ARRANQUE a composição
    (volte a substituição inteira) e a linha perde o prefixo."""
    lar = _Lar(tmp_path, f"{DELA} {slo.WRAPPER_LAUNCH}")
    lar.tabela(OPCOES)
    relato = lar.aplica()
    assert relato["status"] == opj.APLICADO, relato
    linha = lar.linha()
    assert linha.startswith(DELA)
    assert slo.WRAPPER_PREFIX in linha and "VKD3D_CONFIG=no_upload_hvv" in linha
    assert linha.endswith("%command%")
    assert lar.confere()["defeitos"] == []


def test_reaplicar_nao_escreve_de_novo_e_a_troca_da_tabela_leva_so_o_nosso_trecho(
    tmp_path: Path,
) -> None:
    lar = _Lar(tmp_path, f"{DELA} {slo.WRAPPER_LAUNCH} -windowed")
    lar.tabela(OPCOES)
    assert lar.aplica()["status"] == opj.APLICADO
    primeira = lar.linha()
    assert primeira.endswith("%command% -windowed")
    segunda = lar.aplica()
    assert segunda["status"] == opj.NADA or segunda["aplicados"] == [], segunda
    assert lar.linha() == primeira

    lar.tabela("DXVK_ASYNC=1 %command%")
    assert lar.aplica()["status"] == opj.APLICADO
    nova = lar.linha()
    assert "VKD3D_CONFIG" not in nova and "DXVK_ASYNC=1" in nova
    assert nova.startswith(DELA) and nova.endswith("-windowed")
    assert nova.count(slo.WRAPPER_PREFIX) == 1


def test_a_variavel_dela_ao_lado_das_da_tabela_fica(tmp_path: Path) -> None:
    lar = _Lar(tmp_path, "MANGOHUD=1 %command%")
    lar.tabela(OPCOES)
    assert lar.aplica()["status"] == opj.APLICADO
    linha = lar.linha()
    assert "MANGOHUD=1" in _tokens(linha) and "VKD3D_CONFIG=no_upload_hvv" in _tokens(linha)
    assert lar.confere()["defeitos"] == []
    lar.tabela("DXVK_ASYNC=1 %command%")
    assert lar.aplica()["status"] == opj.APLICADO
    assert "MANGOHUD=1" in _tokens(lar.linha())
    assert "VKD3D_CONFIG=no_upload_hvv" not in _tokens(lar.linha())


def test_as_copias_no_bloco_filho_seguem_o_mesmo_valor_composto(tmp_path: Path) -> None:
    lar = _Lar(
        tmp_path, f"{DELA} {slo.WRAPPER_LAUNCH}", copias=(slo._vdf_escape(slo.WRAPPER_LAUNCH),))
    lar.tabela(OPCOES)
    assert lar.aplica()["status"] == opj.APLICADO
    texto = lar.vdf.read_text(encoding="utf-8")
    todas = opj.opcoes_lidas_do_jogo(texto, APPID)
    assert len(todas) == 2 and todas[0] == todas[1]
    assert slo._vdf_unescape(todas[0]).startswith(DELA)


def test_a_linha_que_nao_se_compoe_fica_como_estava_e_o_relato_diz(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ambigua = "A=1 %command% B=2 %command%"
    lar = _Lar(tmp_path, ambigua)
    lar.tabela(OPCOES)
    antes = lar.vdf.read_text(encoding="utf-8")
    relato = lar.aplica()
    assert lar.vdf.read_text(encoding="utf-8") == antes
    assert {"vdf": str(lar.vdf), "appid": APPID, "reason": opj.LINHA_DELA_DIVERGE} in relato[
        "pulados"]
    assert relato["aplicados"] == []
    opj._imprimir(relato)
    assert opj.LINHA_DELA_DIVERGE in capsys.readouterr().err


def test_o_valor_composto_e_o_que_a_releitura_confere(tmp_path: Path) -> None:
    """A releitura do `aplicar` compara com o composto, não com a linha da tabela."""
    lar = _Lar(tmp_path, f"{DELA} {slo.WRAPPER_LAUNCH}")
    lar.tabela(OPCOES)
    relato = lar.aplica()
    assert relato["desfeitos"] == [] and relato["status"] == opj.APLICADO


def test_compor_linha_nas_bordas() -> None:
    desejada = opj.linha_desejada(OPCOES, com_atalho=True)
    assert opj.compor_linha("", desejada) == desejada
    assert opj.compor_linha("%command%", desejada) == desejada
    assert opj.compor_linha(desejada, desejada) == desejada
    assert opj.compor_linha("A=1 %command% B=2 %command%", desejada) is None
    com_args = opj.compor_linha(f"{slo.WRAPPER_PREFIX} %command% -w", desejada)
    assert com_args is not None and com_args.endswith("%command% -w")
