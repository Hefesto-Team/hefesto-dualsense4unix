"""SENTINELA-WRAPPER-01: a Steam guarda UMA linha por jogo, e comeu a nossa.

16/08/2026, defeito pego ao vivo. Ela jogou Pragmata no cabo e funcionou;
passou para o Bluetooth e o jogo parou de reconhecer o controle — *"mas o
perfil de pragmata segue ativo no controle com tudo funcionando só não sendo
reconhecido"*. O daemon estava saudável, o `launch_env` materializado, o grab
retido. O que faltava era UMA linha na Steam::

    VKD3D_CONFIG=no_upload_hvv %command%       <- Pragmata (1 jogo)
    sh -c '…' hefesto-launch %command%          <- os outros 60

O `VKD3D_CONFIG` (posto para curar o crash de 14/08) SUBSTITUIU o wrapper,
porque o campo é um só e a Steam não avisa. Sem o wrapper, o jogo herda a
lista de IGNORE da própria Steam — que inclui `0x054c/0x0df2`, o PID do nosso
vpad — e fica sem controle nenhum.

Estes testes travam as três camadas da cura, e cada asserção morde:

1. DETECTAR — o censo separa "perdeu" (regressão) de "nunca teve" (novo), e é
   read-only, portanto seguro com a Steam aberta;
2. AVISAR — a frase nomeia o JOGO;
3. REPARAR — repõe o wrapper **preservando o `VKD3D_CONFIG`**, é idempotente,
   faz backup, e ADIA com a Steam ou um jogo aberto.

Tudo com fixtures em `tmp_path`. **Nenhum localconfig.vdf real é tocado.**
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

_TAB = "\t"

#: A linha literal do Pragmata, verbatim do `localconfig.vdf` dela (conferida
#: em 16/08 em seis backups datados de 14/07 a 20/07).
PRAGMATA = "3357650"
LINHA_PRAGMATA = "VKD3D_CONFIG=no_upload_hvv %command%"

#: A lista de IGNORE ESTENDIDA à mão: linha INTOCÁVEL (mexer deixaria um
#: fragmento-comando pendurado e o jogo nunca mais abriria).
LINHA_ESTENDIDA = (
    "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6,0x057e/0x2009 %command%"
)


def _vdf(apps: dict[str, str | None]) -> str:
    """localconfig.vdf mínimo. Valor `None` = app SEM a linha LaunchOptions."""
    blocos = []
    for appid, valor in apps.items():
        linha = (
            f'{_TAB * 6}"LaunchOptions"{_TAB * 2}"{slo._vdf_escape(valor)}"\n'
            if valor is not None
            else ""
        )
        blocos.append(
            f'{_TAB * 5}"{appid}"\n{_TAB * 5}{{\n'
            f"{linha}"
            f'{_TAB * 6}"playtime"{_TAB * 2}"42"\n'
            f"{_TAB * 5}}}\n"
        )
    return (
        '"UserLocalConfigStore"\n{\n'
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f'{_TAB * 4}"apps"\n{_TAB * 4}{{\n'
        f"{''.join(blocos)}"
        f"{_TAB * 4}}}\n{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n"
    )


def _escrever(tmp_path: Path, apps: dict[str, str | None]) -> Path:
    alvo = tmp_path / "localconfig.vdf"
    alvo.write_text(_vdf(apps), encoding="utf-8")
    return alvo


def _registro(tmp_path: Path, appids: list[str]) -> Path:
    """Registro de 'já foi visto com o wrapper' — a memória que separa
    regressão de jogo novo."""
    alvo = tmp_path / "wrapper-visto.json"
    alvo.write_text(
        json.dumps({"schema": 1, "appids": {a: "1786000000" for a in appids}}),
        encoding="utf-8",
    )
    return alvo


@pytest.fixture
def steam_fechada(monkeypatch):
    """Sem Steam e sem jogo — o único estado em que a escrita é permitida.

    Precisa valer nos DOIS módulos: a sentinela consulta as suas próprias
    referências importadas, e o `apply_wrapper_to_all_games` consulta as do
    `steam_launch_options`. Patchar só um lado deixaria o outro perguntando à
    máquina de verdade.
    """
    for mod in (sw, slo):
        monkeypatch.setattr(mod, "steam_running", lambda: False)
        monkeypatch.setattr(mod, "steam_game_running", lambda: False)


@pytest.fixture(autouse=True)
def optout_isolado(monkeypatch, tmp_path):
    """Nenhum teste enxerga o `jogos_sem_wrapper.txt` da máquina real — e o
    caminho default aponta para o `tmp_path`, que é onde os testes da recusa
    escrevem."""
    alvo = tmp_path / "jogos_sem_wrapper.txt"
    monkeypatch.setattr(slo, "sem_wrapper_path", lambda *a, **k: alvo)


@pytest.fixture(autouse=True)
def sem_nome_de_jogo(monkeypatch):
    """Sem `appmanifest` de mentira, o rótulo é o appid cru — e é honesto.

    Fixar isto impede que o teste fique dependendo da biblioteca instalada na
    máquina de quem roda a suíte.
    """
    monkeypatch.setattr(sw, "rotulo_do_jogo", lambda a, home=None: f"appid {a}")


# --------------------------------------------------------------------------
# 1. DETECTAR
# --------------------------------------------------------------------------


def test_censo_separa_o_que_perdeu_do_que_nunca_teve(tmp_path: Path, steam_fechada):
    """Os quatro casos do defeito, no mesmo vdf.

    A distinção regressão/novo é o coração do desenho: só a regressão explica
    "funcionava e parou", que é a frase dela. Um censo que chamasse tudo de
    "faltando" avisaria certo e explicaria errado.
    """
    vdf = _escrever(
        tmp_path,
        {
            "111": slo.WRAPPER_LAUNCH,                        # com wrapper
            "222": f"{slo.WRAPPER_PREFIX} MANGOHUD=1 %command%",  # wrapper + var
            PRAGMATA: LINHA_PRAGMATA,                         # o caso literal
            "444": None,                                      # jogo novo, sem linha
        },
    )
    censo = sw.censo_do_wrapper(
        vdfs=[vdf], registro=_registro(tmp_path, ["111", "222", PRAGMATA])
    )

    assert sorted(censo.com_wrapper) == ["111", "222"]
    assert [j.appid for j in censo.regressoes] == [PRAGMATA]
    assert [j.appid for j in censo.novos] == ["444"]
    # A linha dela é reportada CRUA — é o que permite a tela dizer o que havia.
    assert censo.regressoes[0].opcoes == LINHA_PRAGMATA


def test_censo_nao_escreve_no_vdf_nem_com_a_steam_aberta(tmp_path: Path, monkeypatch):
    """A detecção é a camada que vale COM a Steam viva — é quando ela joga.

    Se o censo escrevesse, seria pior que inútil: a Steam regrava o arquivo ao
    sair e a edição viraria corrupção silenciosa.
    """
    for mod in (sw, slo):
        monkeypatch.setattr(mod, "steam_running", lambda: True)
        monkeypatch.setattr(mod, "steam_game_running", lambda: True)
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA})
    antes = vdf.read_bytes()

    censo = sw.censo_do_wrapper(vdfs=[vdf], registro=_registro(tmp_path, [PRAGMATA]))

    assert vdf.read_bytes() == antes
    assert censo.steam_aberta is True
    assert censo.jogo_aberto is True
    assert [j.appid for j in censo.faltantes] == [PRAGMATA]


def test_vdf_pego_no_meio_da_regravacao_nao_vira_alarme(tmp_path: Path, steam_fechada):
    """Um vdf sem bloco `apps` legível é ERRO, nunca 'nenhum jogo tem wrapper'.

    O instrumento mente mais que o produto: sem esta guarda, uma leitura
    apanhada no instante em que a Steam regrava o arquivo produziria um aviso
    convincente e falso — 'a sua biblioteca inteira perdeu o wrapper'.
    """
    vdf = tmp_path / "localconfig.vdf"
    vdf.write_text('"UserLocalConfigStore"\n{\n}\n', encoding="utf-8")

    censo = sw.censo_do_wrapper(vdfs=[vdf], registro=_registro(tmp_path, ["111"]))

    assert censo.faltantes == []
    assert len(censo.erros) == 1
    assert "regravação" in censo.erros[0]


def test_linha_com_ignore_estendido_e_intocavel(tmp_path: Path, steam_fechada):
    """Reparo automático nela deixaria um fragmento e o jogo não abriria."""
    vdf = _escrever(tmp_path, {"999": LINHA_ESTENDIDA})

    censo = sw.censo_do_wrapper(vdfs=[vdf], registro=_registro(tmp_path, []))

    assert [j.appid for j in censo.intocaveis] == ["999"]
    assert censo.reparaveis == []
    assert "não vou tocar" in sw.frase_do_aviso(censo)


# --------------------------------------------------------------------------
# 2. AVISAR
# --------------------------------------------------------------------------


def test_o_aviso_nomeia_o_jogo_e_o_sintoma(tmp_path: Path, steam_fechada):
    """'1 jogo com problema' não ajuda ninguém a agir. O nome, sim.

    E o aviso tem de descrever o sintoma CONFUSO — controle vivo, luz acesa,
    perfil aplicado, jogo cego —, porque foi ele que fez ela procurar defeito
    no lugar errado por uma noite inteira.
    """
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA})
    censo = sw.censo_do_wrapper(vdfs=[vdf], registro=_registro(tmp_path, [PRAGMATA]))

    frase = sw.frase_do_aviso(censo)

    assert PRAGMATA in frase
    assert "perdeu" in frase
    assert "Bluetooth" in frase
    assert "perfil aplicado" in frase


def test_com_a_steam_aberta_o_aviso_pede_para_fechar_e_explica(
    tmp_path: Path, monkeypatch
):
    """Adiar calado é o defeito que a HONESTIDADE-STEAM-01 já curou uma vez."""
    monkeypatch.setattr(sw, "steam_running", lambda: True)
    monkeypatch.setattr(sw, "steam_game_running", lambda: False)
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA})
    censo = sw.censo_do_wrapper(vdfs=[vdf], registro=_registro(tmp_path, [PRAGMATA]))

    frase = sw.frase_do_aviso(censo)

    assert "Steam FECHADA" in frase
    assert "regrava o arquivo" in frase


def test_sem_faltante_nao_ha_frase(tmp_path: Path, steam_fechada):
    """Aviso que aparece à toa é aviso que ela aprende a ignorar."""
    vdf = _escrever(tmp_path, {"111": slo.WRAPPER_LAUNCH})

    assert sw.frase_do_aviso(sw.censo_do_wrapper(vdfs=[vdf], registro=tmp_path / "r.json")) == ""


# --------------------------------------------------------------------------
# 3. REPARAR
# --------------------------------------------------------------------------


def test_o_reparo_repoe_o_wrapper_preservando_o_vkd3d(tmp_path: Path, steam_fechada):
    """A asserção mais cara deste arquivo.

    O Pragmata precisa do wrapper **e** do `VKD3D_CONFIG=no_upload_hvv`, que
    cura o crash de 14/08. Repor o wrapper jogando a linha dela fora trocaria
    'o jogo não vê o controle' por 'o jogo fecha sozinho' — não é conserto.
    """
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA, "111": slo.WRAPPER_LAUNCH})
    registro = _registro(tmp_path, [PRAGMATA, "111"])

    status, _, _ = sw.reparar_ou_adiar(vdfs=[vdf], registro=registro)

    assert status == sw.REPARO_FEITO
    nova = slo.read_launch_options_by_appid(vdf.read_text(encoding="utf-8"))[PRAGMATA]
    assert slo.WRAPPER_PREFIX in nova
    assert "VKD3D_CONFIG=no_upload_hvv" in nova
    assert nova.endswith("%command%")
    # E o jogo que já estava certo não foi mexido.
    assert (
        slo.read_launch_options_by_appid(vdf.read_text(encoding="utf-8"))["111"]
        == slo.WRAPPER_LAUNCH
    )


def test_o_reparo_e_idempotente(tmp_path: Path, steam_fechada):
    """Rodar duas vezes não pode duplicar o wrapper — nem no `sh -c`, nem no
    `VKD3D_CONFIG`."""
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA})
    registro = _registro(tmp_path, [PRAGMATA])

    sw.reparar_ou_adiar(vdfs=[vdf], registro=registro)
    depois_de_um = vdf.read_text(encoding="utf-8")
    status, _, _ = sw.reparar_ou_adiar(vdfs=[vdf], registro=registro)

    assert status == sw.REPARO_NADA
    assert vdf.read_text(encoding="utf-8") == depois_de_um
    assert depois_de_um.count("hefesto-launch") == 2  # `W=…` + o `$0` do sh -c
    assert depois_de_um.count("VKD3D_CONFIG") == 1


def test_ha_backup_antes_de_escrever(tmp_path: Path, steam_fechada):
    """O `localconfig.vdf` guarda a biblioteca inteira dela."""
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA})
    antes = vdf.read_text(encoding="utf-8")

    sw.reparar_ou_adiar(vdfs=[vdf], registro=_registro(tmp_path, [PRAGMATA]))

    backups = list(tmp_path.glob("localconfig.vdf.bak.hefesto-launch-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == antes


def test_com_jogo_aberto_adia_antes_de_olhar_a_steam(tmp_path: Path, monkeypatch):
    """A ordem dos portões não é negociável: fechar a Steam com um jogo aberto
    mata o jogo e o progresso não salvo."""
    monkeypatch.setattr(sw, "steam_running", lambda: True)
    monkeypatch.setattr(sw, "steam_game_running", lambda: True)
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA})
    antes = vdf.read_bytes()

    status, censo, resultado = sw.reparar_ou_adiar(
        vdfs=[vdf], registro=_registro(tmp_path, [PRAGMATA])
    )

    assert status == sw.REPARO_ADIADO_JOGO
    assert resultado is None
    assert vdf.read_bytes() == antes
    assert "mata o jogo" in sw.frase_do_aviso(censo)


def test_com_a_steam_aberta_adia_sem_tocar_no_vdf(tmp_path: Path, monkeypatch):
    """A Steam regrava o vdf ao sair: editar por baixo é edição perdida."""
    monkeypatch.setattr(sw, "steam_running", lambda: True)
    monkeypatch.setattr(sw, "steam_game_running", lambda: False)
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA})
    antes = vdf.read_bytes()

    status, _, resultado = sw.reparar_ou_adiar(
        vdfs=[vdf], registro=_registro(tmp_path, [PRAGMATA])
    )

    assert status == sw.REPARO_ADIADO_STEAM
    assert resultado is None
    assert vdf.read_bytes() == antes


def test_adiado_hoje_reparado_quando_ela_fechar(tmp_path: Path, monkeypatch):
    """Não há marcador de pendência: o censo é uma leitura de arquivo, então o
    reparo simplesmente ACONTECE na próxima passada com a Steam fechada.

    Estado guardado sobre um vdf que muda sozinho envelheceria errado.
    """
    aberta = {"steam": True}
    for mod in (sw, slo):
        monkeypatch.setattr(mod, "steam_running", lambda: aberta["steam"])
        monkeypatch.setattr(mod, "steam_game_running", lambda: False)
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA})
    registro = _registro(tmp_path, [PRAGMATA])

    assert sw.reparar_ou_adiar(vdfs=[vdf], registro=registro)[0] == sw.REPARO_ADIADO_STEAM
    aberta["steam"] = False
    assert sw.reparar_ou_adiar(vdfs=[vdf], registro=registro)[0] == sw.REPARO_FEITO
    assert "VKD3D_CONFIG=no_upload_hvv" in vdf.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# A vontade dela vence
# --------------------------------------------------------------------------


def test_jogo_recusado_por_ela_nao_avisa_nem_repara(tmp_path: Path, steam_fechada):
    """'Não quero o wrapper neste jogo' tem de ser respeitado — e o produto
    não pode brigar com a dona da máquina.

    Intenção nunca é INFERIDA da ausência (a Steam apaga sozinha, e é o caso
    comum): quem fala é o `jogos_sem_wrapper.txt`.
    """
    lista = tmp_path / "jogos_sem_wrapper.txt"
    assert slo.marcar_jogo_sem_wrapper(PRAGMATA, path=lista) == "adicionado"
    assert slo.ler_jogos_sem_wrapper(lista) == [PRAGMATA]
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA})
    antes = vdf.read_bytes()

    censo = sw.censo_do_wrapper(
        vdfs=[vdf],
        registro=_registro(tmp_path, [PRAGMATA]),
        recusados=slo.ler_jogos_sem_wrapper(lista),
    )
    status, _, _ = sw.reparar_ou_adiar(vdfs=[vdf], registro=tmp_path / "r2.json")

    assert censo.faltantes == []
    assert censo.recusados == [PRAGMATA]
    assert sw.frase_do_aviso(censo) == ""
    # E o reparo, que lê a lista sozinho, também não escreve nada.
    assert status in (sw.REPARO_NADA, sw.REPARO_FEITO)
    assert vdf.read_bytes() == antes
    # A recusa é REVERSÍVEL sem editor de texto.
    assert slo.desmarcar_jogo_sem_wrapper(PRAGMATA, path=lista) == "removido"
    assert slo.ler_jogos_sem_wrapper(lista) == []


def test_a_recusa_dela_sobrevive_ao_install(tmp_path: Path, steam_fechada, capsys):
    """O passo sem flag do install roda `--apply` em TODOS os jogos.

    Sem esta linha, o próximo `./install.sh` desfaria a escolha dela em
    silêncio — e "não quero" que dura até o próximo reinstall não é escolha.
    """
    lista = tmp_path / "jogos_sem_wrapper.txt"
    slo.marcar_jogo_sem_wrapper(PRAGMATA, path=lista)
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA, "111": None})

    rc = slo.main(["--apply", "--vdf", str(vdf)])

    assert rc == 0
    opcoes = slo.read_apps_by_appid(vdf.read_text(encoding="utf-8"))
    assert opcoes[PRAGMATA] == LINHA_PRAGMATA          # intacto: ela não quer
    assert slo.WRAPPER_PREFIX in (opcoes["111"] or "")  # o resto recebeu
    assert "escolha dela" in capsys.readouterr().out


# --------------------------------------------------------------------------
# O registro (a memória que separa 'perdeu' de 'nunca teve')
# --------------------------------------------------------------------------


def test_o_censo_anota_quem_tem_o_wrapper_hoje(tmp_path: Path, steam_fechada):
    """É assim que a regressão de amanhã fica detectável: sem a passada de
    hoje, a linha comida amanhã pareceria 'jogo novo'."""
    registro = tmp_path / "wrapper-visto.json"
    vdf = _escrever(tmp_path, {"111": slo.WRAPPER_LAUNCH})

    sw.censo_do_wrapper(vdfs=[vdf], registro=registro)

    assert "111" in sw.ler_registro(registro)
    # ...e amanhã, com a linha comida, isso é REGRESSÃO, não jogo novo.
    _escrever(tmp_path, {"111": "VKD3D_CONFIG=no_upload_hvv %command%"})
    censo = sw.censo_do_wrapper(vdfs=[vdf], registro=registro)
    assert [j.motivo for j in censo.faltantes] == [sw.MOTIVO_REGRESSAO]


def test_registro_corrompido_nao_inventa_regressao(tmp_path: Path, steam_fechada):
    """Sem memória, toda ausência é 'novo'. O produto ainda repara; só não
    afirma que aquilo funcionava antes — alegar sem base é pior que calar."""
    registro = tmp_path / "wrapper-visto.json"
    registro.write_text("{ não é json", encoding="utf-8")
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA})

    censo = sw.censo_do_wrapper(vdfs=[vdf], registro=registro)

    assert [j.motivo for j in censo.faltantes] == [sw.MOTIVO_NOVO]


# --------------------------------------------------------------------------
# A leitura estrutural que a detecção exige
# --------------------------------------------------------------------------


def test_roda_avulso_com_o_python3_do_sistema(tmp_path: Path):
    """O install e o doctor rodam este módulo como SCRIPT, sem o `.venv`.

    Defeito real encontrado ao ligar o passo do install em 16/08: o
    `pastas_steamapps` (que traduz appid em nome de jogo) tinha um
    `from hefesto_dualsense4unix…` cru, e o script solto morria com
    `ModuleNotFoundError` na primeira vez que houvesse um jogo a nomear — ou
    seja, exatamente quando o aviso importa. Estava latente porque nada avulso
    chamava aquele caminho.
    """
    import subprocess
    import sys

    modulo = (
        Path(sw.__file__).resolve().parent / "sentinela_do_wrapper.py"
    )
    vdf = _escrever(tmp_path, {PRAGMATA: LINHA_PRAGMATA, "111": slo.WRAPPER_LAUNCH})
    ambiente = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }

    proc = subprocess.run(
        [sys.executable, "-S", "-E", str(modulo), "--relatorio", "--vdf", str(vdf)],
        capture_output=True,
        text=True,
        env=ambiente,
        cwd=str(tmp_path),  # nada de achar o pacote pelo diretório de trabalho
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    assert "ModuleNotFoundError" not in proc.stderr
    assert PRAGMATA in proc.stdout


def test_read_apps_enxerga_o_app_sem_a_linha(tmp_path: Path):
    """A `read_launch_options_by_appid` só devolve quem TEM a linha — logo não
    distingue 'jogo inexistente' de 'linha APAGADA'. A segunda é regressão."""
    texto = _vdf({"111": slo.WRAPPER_LAUNCH, "222": None})

    assert slo.read_apps_by_appid(texto) == {"111": slo.WRAPPER_LAUNCH, "222": None}
    assert slo.read_launch_options_by_appid(texto) == {"111": slo.WRAPPER_LAUNCH}
