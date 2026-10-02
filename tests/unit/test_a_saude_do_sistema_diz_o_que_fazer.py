"""BG-SAUDE-01 — o cartão que a pessoa abre quando algo está errado."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import storm_doctor as sd

PREFIXO = sd.PREFIXO_DA_CURA

COMANDO_QUE_TINHA_BOTAO = "doctor --fix-safe"


def _casa_sem_steam(tmp_path: Path) -> Path:
    casa = tmp_path / "casa-vazia"
    casa.mkdir()
    return casa


def _casa_com_steam_input(tmp_path: Path, *, global_ligado: bool) -> Path:
    """Uma HOME com um `localconfig.vdf` que liga o Steam Input."""
    casa = tmp_path / ("casa-global" if global_ligado else "casa-por-jogo")
    vdf = casa / ".steam/steam/userdata/123/config/localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    if global_ligado:
        corpo = '\t\t\t\t"SteamController_PSSupport"\t\t"2"\n'
    else:
        corpo = (
            '"apps"\n{\n\t"1599660"\n\t{\n'
            '\t\t"UseSteamControllerConfig"\t\t"2"\n\t}\n}\n'
        )
    vdf.write_text(corpo, encoding="utf-8")
    return casa


def cenas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """`{nome do ramo: a frase que a tela recebe}` — só WARN e INFO."""
    monkeypatch.setattr(sd, "_allowlist_path", lambda: tmp_path / "sem-allowlist")
    ausente = tmp_path / "nao-existe.conf"
    vazio = tmp_path / "diretorio-vazio"
    vazio.mkdir()
    com_regra = tmp_path / "com-regra"
    com_regra.mkdir()
    (com_regra / "75-ps5-controller-disable-usb-audio.rules").write_text(
        "x", encoding="utf-8"
    )
    agendada = tmp_path / "hefesto-dualsense-storm.conf"
    agendada.write_text(
        "options snd_usb_audio quirk_flags=054c:0ce6:ignore_ctl_error",
        encoding="utf-8",
    )
    uma_placa = "1 [Controller]: USB-Audio - DualSense Wireless Controller"

    def frase(par: tuple[str, str], esperado: str) -> str:
        tag, msg = par
        assert tag == esperado, f"o grau mudou: {tag} != {esperado} em {msg!r}"
        return msg

    return {
        "quirk_do_usbcore_ausente": frase(sd.check_quirk(""), sd.WARN),
        "steam_nao_instalada": frase(
            sd.check_steam_input(_casa_sem_steam(tmp_path)), sd.INFO
        ),
        "steam_input_por_jogo": frase(
            sd.check_steam_input(_casa_com_steam_input(tmp_path, global_ligado=False)),
            sd.WARN,
        ),
        "steam_input_global": frase(
            sd.check_steam_input(_casa_com_steam_input(tmp_path, global_ligado=True)),
            sd.WARN,
        ),
        "wireplumber_sem_dropin": frase(sd.check_wireplumber(vazio), sd.INFO),
        "audio_off_ativa": frase(sd.check_authorized_rule(com_regra), sd.INFO),
        "audio_off_inativa": frase(sd.check_authorized_rule(vazio), sd.INFO),
        "cura_do_usb_agendada": frase(
            sd.check_snd_quirk(quirk_flags_text="", conf_path=agendada), sd.INFO
        ),
        "cura_do_usb_ausente": frase(
            sd.check_snd_quirk(quirk_flags_text="", conf_path=ausente), sd.WARN
        ),
        "audio_ausente_sem_denominador": frase(
            sd.check_snd_audio_healthy(cards_text="0 [Generic]: HDA-Intel"), sd.INFO
        ),
        "nenhum_no_cabo": frase(
            sd.check_snd_audio_healthy(cards_text="", controles_no_cabo=0), sd.INFO
        ),
        "audio_ausente_no_cabo": frase(
            sd.check_snd_audio_healthy(cards_text="", controles_no_cabo=2), sd.INFO
        ),
        "audio_em_parte_dos_controles": frase(
            sd.check_snd_audio_healthy(cards_text=uma_placa, controles_no_cabo=2),
            sd.WARN,
        ),
    }


def test_toda_frase_de_alarme_tem_o_que_fazer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mordida, na forma mais curta: devolva uma frase antiga e ela cai."""
    mudas = {
        nome: msg for nome, msg in cenas(tmp_path, monkeypatch).items()
        if PREFIXO not in msg
    }

    assert not mudas, (
        "frase do cartão 'Saúde do sistema' que diz o QUÊ e o PORQUÊ e não diz "
        "o que fazer:\n  "
        + "\n  ".join(f"{nome}: {msg!r}" for nome, msg in mudas.items())
        + f"\n\nO molde é o da aba Configurações: '{PREFIXO}<gesto>'. Onde o "
        "gesto for um botão desta mesma tela, aponte o botão."
    )


def test_nenhuma_frase_manda_para_o_terminal_quando_ha_botao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O defeito com nome: `doctor --fix-safe` com o botão na mesma tela.

    "Aplicar correções" (`btn_storm_fix_safe` → `on_storm_fix_safe`) roda o
    `scripts/fix_wireplumber_default_source.sh --install`, que é EXATAMENTE o
    que aquele comando faria. Mandar a pessoa ao terminal com o botão à vista
    é pedir que ela faça à mão o que um clique faz.
    """
    culpadas = {
        nome: msg for nome, msg in cenas(tmp_path, monkeypatch).items()
        if COMANDO_QUE_TINHA_BOTAO in msg
    }

    assert not culpadas, (
        f"o cartão voltou a mandar rodar '{COMANDO_QUE_TINHA_BOTAO}' no "
        "terminal:\n  "
        + "\n  ".join(f"{nome}: {msg!r}" for nome, msg in culpadas.items())
        + "\n\nO botão 'Aplicar correções', na mesma tela, faz isso."
    )


def test_a_frase_do_wireplumber_aponta_o_caminho_que_existe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tirar o comando não basta: sem apontar o caminho, sobra um diagnóstico mudo."""
    msg = cenas(tmp_path, monkeypatch)["wireplumber_sem_dropin"]

    assert "Aplicar correções" not in msg, msg
    assert sd.gesto_de_atualizar() in msg, msg


def test_a_regua_sabe_recusar() -> None:
    """Régua que só sabe passar não é régua."""
    assert PREFIXO.strip(), "o prefixo virou vazio e a régua passou a absolver tudo"

    veneno = "quirk anti-storm AUSENTE do usbcore (storm pode reincidir sob carga)"
    assert PREFIXO not in veneno, "a régua aprovaria a frase que a BG-SAUDE-01 veio matar"

    curada = f"o cinto extra não está posto. {PREFIXO}nada, por enquanto."
    assert PREFIXO in curada, "a régua reprovaria uma frase curada"


def test_todo_ramo_de_alarme_tem_uma_cena(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O portão do portão: ramo novo sem cena reprova AQUI, não na tela dela."""
    fonte = Path(sd.__file__).read_text(encoding="utf-8")
    ramos = [
        no.lineno
        for no in ast.walk(ast.parse(fonte))
        if isinstance(no, ast.Return)
        and isinstance(no.value, ast.Tuple)
        and no.value.elts
        and isinstance(no.value.elts[0], ast.Name)
        and no.value.elts[0].id in {"WARN", "INFO"}
    ]

    assert len(ramos) == 12, (
        f"o `storm_doctor` passou a ter {len(ramos)} ramos de alarme, e esta "
        "bancada cobre 12 (em 13 cenas). Acrescente a cena do ramo novo em "
        "`cenas()` e ajuste este número no mesmo commit — senão a frase nova "
        "nasce sem o 'o que fazer' e ninguém vê.\n"
        f"Linhas: {ramos}"
    )
    assert len(cenas(tmp_path, monkeypatch)) == 13
