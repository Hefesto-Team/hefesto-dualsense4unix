"""ARVORE-ERRADA-01 (16/08/2026) — o censo lia o `apps` que a Steam não lê."""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations.steam_launch_options import (
    WRAPPER_LAUNCH,
    WRAPPER_PREFIX,
    _vdf_escape,
    apply_wrapper_vdf_text,
    e_a_arvore_canonica,
    read_apps_by_appid,
    read_launch_options_by_appid,
)


def _escapado(valor: str) -> str:
    """Como o valor aparece DENTRO do vdf — com as aspas escapadas."""
    return _vdf_escape(valor)

_LINHA_COMIDA = "VKD3D_CONFIG=no_upload_hvv %command%"
_PRAGMATA = "3357650"
_DUSKFADE = "2542020"


def _bloco_app(appid: str, *pares: tuple[str, str], recuo: str) -> str:
    corpo = "".join(f'{recuo}\t\t"{k}"\t\t"{v}"\n' for k, v in pares)
    return f'{recuo}\t"{appid}"\n{recuo}\t{{\n{corpo}{recuo}\t}}\n'


def _vdf_das_tres_arvores(
    *,
    canonica: str,
    outra: str | None = None,
) -> str:
    """O `localconfig.vdf` dela em miniatura: três árvores `apps`, uma boa."""
    bloco_canonico = _bloco_app(_PRAGMATA, ("LaunchOptions", canonica), recuo="\t\t\t\t")
    bloco_duskfade = _bloco_app(
        _DUSKFADE, ("LaunchOptions", _escapado(WRAPPER_LAUNCH)), recuo="\t\t\t\t"
    )
    corpo_outra = ""
    if outra is not None:
        corpo_outra = _bloco_app(
            _PRAGMATA,
            ("LaunchOptions", outra),
            ("UseSteamControllerConfig", "2"),
            ("SteamControllerRumble", "1"),
            recuo="\t",
        )
    bloco_web = _bloco_app("480", ("LaunchOptions", "lixo %command%"), recuo="\t\t\t")
    return (
        '"UserLocalConfigStore"\n{\n'
        '\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n\t\t\t{\n'
        '\t\t\t\t"apps"\n\t\t\t\t{\n'
        f"{bloco_canonico}{bloco_duskfade}"
        "\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n"
        '\t"apps"\n\t{\n'
        f"{corpo_outra}"
        "\t}\n"
        '\t"WebStorage"\n\t{\n\t\t"apps"\n\t\t{\n'
        f"{bloco_web}"
        "\t\t}\n\t}\n"
        "}\n"
    )


class TestOQueContaComoArvoreCanonica:
    @pytest.mark.parametrize(
        "pilha",
        [
            ["UserLocalConfigStore", "Software", "Valve", "Steam", "apps"],
            ["userlocalconfigstore", "software", "valve", "steam", "apps"],
            ["QualquerRaiz", "Software", "Valve", "Steam", "apps"],
        ],
    )
    def test_o_caminho_de_verdade_passa(self, pilha: list[str]) -> None:
        """A âncora é por sufixo: o nome da raiz não entra no julgamento."""
        assert e_a_arvore_canonica(pilha)

    @pytest.mark.parametrize(
        "pilha",
        [
            ["UserLocalConfigStore", "apps"],
            ["UserLocalConfigStore", "WebStorage", "apps"],
            ["UserLocalConfigStore", "Software", "Valve", "apps"],
            ["Software", "Valve", "Steam"],
            ["apps"],
            [],
        ],
    )
    def test_as_outras_arvores_nao_passam(self, pilha: list[str]) -> None:
        assert not e_a_arvore_canonica(pilha)


class TestOLeitorNaoLeMaisDaArvoreErrada:
    def test_o_caso_do_pragmata_o_valor_bom_nao_engole_o_ruim(self) -> None:
        """A MORDIDA. Sem a âncora, sai o wrapper e o censo diz que está tudo bem."""
        texto = _vdf_das_tres_arvores(
            canonica=_LINHA_COMIDA,
            outra=_escapado(WRAPPER_LAUNCH),
        )
        lido = read_apps_by_appid(texto)
        assert lido[_PRAGMATA] == _LINHA_COMIDA
        assert WRAPPER_PREFIX not in lido[_PRAGMATA]

    def test_o_jogo_que_so_existe_na_arvore_errada_some_do_censo(self) -> None:
        """Um appid fora da árvore canônica não é jogo da Steam para nós."""
        texto = _vdf_das_tres_arvores(canonica=_LINHA_COMIDA, outra=None).replace(
            '\t"apps"\n\t{\n\t}\n',
            '\t"apps"\n\t{\n'
            + _bloco_app("413080", ("LaunchOptions", "x %command%"), recuo="\t")
            + "\t}\n",
        )
        assert "413080" not in read_apps_by_appid(texto)

    def test_a_webstorage_tambem_fica_de_fora(self) -> None:
        texto = _vdf_das_tres_arvores(canonica=_LINHA_COMIDA)
        assert "480" not in read_apps_by_appid(texto)

    def test_a_arvore_boa_continua_sendo_lida_inteira(self) -> None:
        """Ancorar não pode virar "não acha mais nada"."""
        lido = read_apps_by_appid(_vdf_das_tres_arvores(canonica=_LINHA_COMIDA))
        assert set(lido) == {_PRAGMATA, _DUSKFADE}

    def test_o_filtro_de_quem_tem_a_linha_herda_a_ancora(self) -> None:
        texto = _vdf_das_tres_arvores(
            canonica=_LINHA_COMIDA, outra=_escapado(WRAPPER_LAUNCH)
        )
        assert read_launch_options_by_appid(texto)[_PRAGMATA] == _LINHA_COMIDA


class TestOEscritorNaoSujaOQueNaoEDele:
    def test_nao_escreve_na_arvore_da_steam(self) -> None:
        """A MORDIDA do outro lado: os 11 blocos dela ganharam chave à toa."""
        texto = _vdf_das_tres_arvores(
            canonica=_LINHA_COMIDA,
            outra=None,
        ).replace(
            '\t"apps"\n\t{\n\t}\n',
            '\t"apps"\n\t{\n'
            + _bloco_app(_PRAGMATA, ("UseSteamControllerConfig", "2"), recuo="\t")
            + "\t}\n",
        )
        novo, aplicados, _ = apply_wrapper_vdf_text(texto)

        trecho_original = texto.split('\t"apps"\n\t{\n', 1)[1].split("\t}\n", 1)[0]
        trecho_novo = novo.split('\t"apps"\n\t{\n', 1)[1].split("\t}\n", 1)[0]
        assert trecho_novo == trecho_original
        assert "LaunchOptions" not in trecho_novo
        assert _PRAGMATA in aplicados
        assert WRAPPER_PREFIX in read_apps_by_appid(novo)[_PRAGMATA]

    def test_repor_preserva_a_variavel_que_ela_pos(self) -> None:
        """O `VKD3D_CONFIG` dela é cura de crash — o wrapper convive, não come."""
        novo, _, _ = apply_wrapper_vdf_text(
            _vdf_das_tres_arvores(canonica=_LINHA_COMIDA)
        )
        linha = read_apps_by_appid(novo)[_PRAGMATA]
        assert linha is not None
        assert WRAPPER_PREFIX in linha
        assert "VKD3D_CONFIG=no_upload_hvv" in linha
        assert "%command%" in linha

    def test_aplicar_duas_vezes_nao_muda_nada(self) -> None:
        uma, _, _ = apply_wrapper_vdf_text(
            _vdf_das_tres_arvores(canonica=_LINHA_COMIDA)
        )
        duas, aplicados, _ = apply_wrapper_vdf_text(uma)
        assert duas == uma
        assert aplicados == []


class TestOCensoEnxergaARegressao:
    def test_a_sentinela_nomeia_o_pragmata(self, tmp_path, monkeypatch) -> None:
        """O caminho inteiro: vdf com as três árvores -> censo que NOMEIA."""
        from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

        vdf = tmp_path / "localconfig.vdf"
        vdf.write_text(
            _vdf_das_tres_arvores(
                canonica=_LINHA_COMIDA, outra=_escapado(WRAPPER_LAUNCH)
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(sw, "discover_vdfs", lambda *a, **k: [vdf])
        monkeypatch.setattr(sw, "steam_running", lambda: False)
        monkeypatch.setattr(sw, "steam_game_running", lambda: False)
        monkeypatch.setattr(sw, "ler_jogos_sem_wrapper", lambda *a, **k: [])

        visto = tmp_path / "wrapper-visto.json"
        visto.write_text(
            '{"appids": {"' + _PRAGMATA + '": "1755300000"}}', encoding="utf-8"
        )

        censo = sw.censo_do_wrapper(registro=visto)
        assert [j.appid for j in censo.faltantes] == [_PRAGMATA]
        assert censo.faltantes[0].motivo == sw.MOTIVO_REGRESSAO
        assert _PRAGMATA in sw.frase_do_aviso(censo)
