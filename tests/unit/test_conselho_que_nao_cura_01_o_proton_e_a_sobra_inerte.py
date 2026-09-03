"""CONSELHO-QUE-NAO-CURA-01 — três avisos do doctor mandavam fazer o que não
resolve, ou acusavam o que a medição desmente.

MEDIDO na máquina dela em 02/09/2026, DEPOIS de um `./install.sh --yes` que
fechou com `rc=0` e nenhuma FALHA:

1. ``[WARN] Proton pinado presente (GE-Proton10-34) mas o manifesto do hefesto
   não bate — rode ./install.sh``. Rodar o install NÃO muda nada: o
   `GE-Proton10-34` dela veio de fora (03/04, ProtonUp), não tem o
   `.hefesto-proton-pin.json` dentro, e o `ensure_pinned_proton` devolve
   ``already ("instalação pré-existente sem manifesto (mantida)")`` — ele
   MANTÉM de propósito o que a dona da máquina instalou. Conselho que não
   funciona é pior que aviso nenhum: gasta a confiança de quem o segue.

   A confusão era de UMA palavra. Manifesto **divergente** (existe, aponta
   outro sha256) o install cura de verdade — cai no ramo do cache/download e
   re-extrai. Manifesto **ausente** é outra coisa: é não termos como atestar o
   SHA256 de algo que não fomos nós que extraímos, e o gesto que resolve é
   tirar o diretório do caminho, não repetir o instalador.

2. ``[WARN] Opções de Inicialização escritas por nós FORA da árvore viva …
   appid 413080 — … e o censo as conta como cobertura``. **As duas metades
   caíram na medição:**

   - *"escritas por nós"* era afirmado sem olhar o valor. O que está lá é
     ``VKD3D_CONFIG=no_upload_hvv %command%`` — **sem** a chamada do wrapper.
   - *"o censo as conta como cobertura"* descreve um defeito CURADO em
     16/08/2026 (ARVORE-ERRADA-01): o `read_apps_by_appid` ancorou o caminho e
     o `censo_do_wrapper` só lê ``Software/Valve/Steam/apps``. Medido no mesmo
     instante: `com_wrapper` = **63**, que é exatamente o total da árvore viva,
     e o 413080 **não** está na lista.

3. ``[WARN] 1 jogo(s) fora do Proton pinado``, sem nome e sem razão. O jogo é o
   DON'T SCREAM (appid 2497900) e ele está fora **porque o produto respeitou a
   escolha dela**: em 14/08/2026 a trava o arrastou de `proton_11` para o
   pinado e o microfone do jogo — a mecânica inteira dele — morreu. Desde
   19/08 o `build_compat_tool_mapping` preserva escolha por jogo e grava
   ``action="preservado"`` no `proton-pin-lock.json`. Esse registro existe; o
   aviso é que não o lia.

Aqui as funções shell REAIS rodam (molde do
`test_acusa_o_culpado_01_o_doctor_que_acusava_a_pessoa_errada`), contra um
``HOME`` de mentira. Nada é lido do lar de verdade e nada é escrito nele.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import steam_launch_options as slo

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

NOME_DO_PIN = "GE-Proton10-34"
SHA_DO_PIN = "51c580b66a833c73998fe00f0717eeac57197654040a2f2ed5189e3ee68d773d"

#: A chamada do wrapper, LIDA do módulo — nunca digitada aqui: régua que digita
#: o que devia ler é a armadilha nº 1 desta casa.
WRAPPER = slo.WRAPPER_PREFIX


def _config_vdf(por_jogo: dict[str, str], *, glob: str = NOME_DO_PIN) -> str:
    """`config.vdf` mínimo com CompatToolMapping (global + entradas por jogo)."""
    entradas = ""
    for appid, tool in {"0": glob, **por_jogo}.items():
        entradas += (
            f'\t\t\t\t\t"{appid}"\n\t\t\t\t\t{{\n'
            f'\t\t\t\t\t\t"name"\t\t"{tool}"\n'
            f'\t\t\t\t\t\t"config"\t\t""\n'
            f'\t\t\t\t\t\t"priority"\t\t"250"\n'
            "\t\t\t\t\t}\n"
        )
    return (
        '"InstallConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n'
        '\t\t\t"Steam"\n\t\t\t{\n\t\t\t\t"CompatToolMapping"\n\t\t\t\t{\n'
        f"{entradas}"
        "\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n"
    )


def _lar_do_proton(
    tmp_path: Path,
    *,
    manifesto: str,
    por_jogo: dict[str, str] | None = None,
    registro: dict[str, dict[str, str]] | None = None,
) -> Path:
    """Um ``HOME`` de mentira com Steam nativa, o pin extraído e o registro."""
    lar = tmp_path / "lar"
    raiz = lar / ".steam/steam"
    (raiz / "config").mkdir(parents=True)
    (raiz / "steamapps").mkdir(parents=True)

    alvo = raiz / "compatibilitytools.d" / NOME_DO_PIN
    alvo.mkdir(parents=True)
    (alvo / "proton").write_text("#!/bin/sh\n", encoding="utf-8")
    (alvo / "version").write_text("1 mentira\n", encoding="utf-8")
    dentro = alvo / ".hefesto-proton-pin.json"
    if manifesto == "ok":
        dentro.write_text(
            json.dumps({"name": NOME_DO_PIN, "sha256": SHA_DO_PIN}), encoding="utf-8"
        )
    elif manifesto == "divergente":
        dentro.write_text(
            json.dumps({"name": NOME_DO_PIN, "sha256": "00" * 32}), encoding="utf-8"
        )
    elif manifesto == "corrompido":
        # JSON truncado no meio — o desfecho de uma gravação interrompida.
        dentro.write_text('{"name": "GE-Proton10-34", "sha256"', encoding="utf-8")
    elif manifesto != "ausente":  # pragma: no cover - erro de quem escreve teste
        raise ValueError(manifesto)

    for appid, nome in (("2497900", "DON'T SCREAM"), ("316790", "Grim Fandango")):
        (raiz / "steamapps" / f"appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{nome}"\n}}\n',
            encoding="utf-8",
        )
    (raiz / "config" / "config.vdf").write_text(
        _config_vdf(por_jogo or {}), encoding="utf-8"
    )

    estado = lar / ".local/state/hefesto-dualsense4unix"
    estado.mkdir(parents=True)
    (estado / "proton-pin-lock.json").write_text(
        json.dumps({"tool_name": NOME_DO_PIN, "changes": registro or {}}),
        encoding="utf-8",
    )
    return lar


def _rodar(funcao: str, lar: Path) -> str:
    res = subprocess.run(
        ["bash", "-c", f'source "$DOCTOR_SH"; {funcao}'],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={
            "DOCTOR_SH": str(DOCTOR),
            "HOME": str(lar),
            "XDG_STATE_HOME": str(lar / ".local/state"),
            "XDG_CACHE_HOME": str(lar / ".cache"),
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "LC_ALL": "C.UTF-8",
            "NO_COLOR": "1",
        },
    )
    return res.stdout + res.stderr


def _mensagem(saida: str, frase: str) -> tuple[str, str]:
    """``(rótulo, linha)`` da mensagem que contém `frase`.

    O doctor imprime UMA linha por mensagem, com o rótulo no começo:
    ``[ OK ] ``, ``[WARN] ``, ``[FAIL] `` ou sete espaços (o `info`).

    **ESTA FUNÇÃO NASCEU DE UM TESTE QUE PASSOU POR ACIDENTE**, e o modo é
    instrutivo: a primeira redação fazia ``assert "INFO" in linha`` procurando
    o rótulo DENTRO do texto. Passou verde — mas não pelo rótulo: a mensagem
    cita o caminho do diretório do pin, o caminho vem do `tmp_path` do pytest,
    e o `tmp_path` carrega o NOME DO TESTE, que era
    ``test_manifesto_ausente_e_INFO_e_nao_WARN``. A régua estava lendo a si
    mesma. Rótulo se confere no COMEÇO da linha, nunca por substring.
    """
    for linha in saida.splitlines():
        if frase not in linha:
            continue
        for rotulo in ("[ OK ]", "[WARN]", "[FAIL]"):
            if linha.startswith(rotulo):
                return rotulo, linha
        return ("[INFO]" if linha.startswith("       ") else "?"), linha
    raise AssertionError(f"frase ausente da saída: {frase!r}\n{saida}")


class TestOManifestoAusenteNaoPedeOInstaladorDeNovo:
    def test_manifesto_ausente_nao_manda_rodar_o_install(self, tmp_path: Path) -> None:
        saida = _rodar("check_proton_pin", _lar_do_proton(tmp_path, manifesto="ausente"))
        assert "por FORA do hefesto" in saida, saida
        assert "rodar o instalador de novo não muda isto" in saida, saida
        # A frase velha prometia o que não entrega.
        assert "o manifesto do hefesto não bate" not in saida, saida

    def test_manifesto_ausente_nao_e_alarme(self, tmp_path: Path) -> None:
        """Estado criado DE PROPÓSITO pelo produto não é alarme."""
        saida = _rodar("check_proton_pin", _lar_do_proton(tmp_path, manifesto="ausente"))
        rotulo, linha = _mensagem(saida, "por FORA do hefesto")
        assert rotulo == "[INFO]", linha

    def test_manifesto_divergente_continua_mandando_rodar_o_install(
        self, tmp_path: Path
    ) -> None:
        """O NEGATIVO: onde o install CURA, o conselho tem de continuar lá."""
        saida = _rodar(
            "check_proton_pin", _lar_do_proton(tmp_path, manifesto="divergente")
        )
        rotulo, linha = _mensagem(saida, "OUTRO sha256")
        assert rotulo == "[WARN]", linha
        assert "install.sh" in linha, linha

    def test_manifesto_batendo_continua_passando(self, tmp_path: Path) -> None:
        saida = _rodar("check_proton_pin", _lar_do_proton(tmp_path, manifesto="ok"))
        assert "presente e íntegro" in saida, saida

    def test_manifesto_ilegivel_diz_que_o_install_nao_resolve(
        self, tmp_path: Path
    ) -> None:
        saida = _rodar(
            "check_proton_pin", _lar_do_proton(tmp_path, manifesto="corrompido")
        )
        assert "trata isso como 'sem manifesto'" in saida, saida


class TestOJogoForaDoPinTemNomeERazao:
    def test_escolha_preservada_e_informativa_com_o_nome_do_jogo(self, tmp_path: Path) -> None:
        lar = _lar_do_proton(
            tmp_path,
            manifesto="ok",
            por_jogo={"2497900": "proton_11"},
            registro={
                "2497900": {"action": "preservado", "previous_name": "proton_11"}
            },
        )
        saida = _rodar("check_proton_pin", lar)
        rotulo, linha = _mensagem(saida, "ESCOLHA SUA")
        assert rotulo == "[INFO]", linha
        assert "DON'T SCREAM" in linha, linha
        assert "proton_11" in linha, linha
        # O aviso cego, sem nome e sem razão, não pode reaparecer.
        assert "1 jogo(s) fora do Proton pinado" not in saida, saida

    def test_sem_registro_de_escolha_continua_alarmando_com_o_nome(
        self, tmp_path: Path
    ) -> None:
        """O NEGATIVO: sem prova de que foi escolha dela, o alarme fica."""
        lar = _lar_do_proton(
            tmp_path, manifesto="ok", por_jogo={"2497900": "proton_11"}, registro={}
        )
        saida = _rodar("check_proton_pin", lar)
        rotulo, linha = _mensagem(saida, "sem registro de escolha")
        assert rotulo == "[WARN]", linha
        assert "DON'T SCREAM" in linha, linha

    def test_tudo_no_pin_continua_passando(self, tmp_path: Path) -> None:
        lar = _lar_do_proton(tmp_path, manifesto="ok", por_jogo={})
        saida = _rodar("check_proton_pin", lar)
        assert "todos os jogos travados no Proton pinado" in saida, saida


# ---------------------------------------------------------------------------
# A SOBRA INERTE — check_arvore_canonica_do_wrapper
# ---------------------------------------------------------------------------

_TAB = "\t"


def _bloco_apps(nivel: int, itens: dict[str, str]) -> str:
    dentro = ""
    for appid, valor in itens.items():
        dentro += (
            f'{_TAB * (nivel + 1)}"{appid}"\n{_TAB * (nivel + 1)}{{\n'
            f'{_TAB * (nivel + 2)}"LaunchOptions"{_TAB * 2}"{slo._vdf_escape(valor)}"\n'
            f"{_TAB * (nivel + 1)}}}\n"
        )
    return f'{_TAB * nivel}"apps"\n{_TAB * nivel}{{\n{dentro}{_TAB * nivel}}}\n'


def _lar_do_wrapper(
    tmp_path: Path, *, viva: dict[str, str], solta: dict[str, str]
) -> Path:
    lar = tmp_path / "lar"
    destino = lar / ".steam/steam/userdata/1/config"
    destino.mkdir(parents=True)
    corpo = (
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f"{_bloco_apps(4, viva)}"
        f"{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n"
    )
    corpo += _bloco_apps(1, solta)
    (destino / "localconfig.vdf").write_text(
        '"UserLocalConfigStore"\n{\n' + corpo + "}\n", encoding="utf-8"
    )
    return lar


class TestASobraForaDaArvoreViva:
    def test_sobra_sem_wrapper_nao_e_acusada_de_ser_nossa(self, tmp_path: Path) -> None:
        """O retrato do vdf dela: o órfão carrega a linha VKD3D, não a nossa."""
        lar = _lar_do_wrapper(
            tmp_path,
            viva={"316790": f"{WRAPPER} %command%"},
            solta={"413080": "VKD3D_CONFIG=no_upload_hvv %command%"},
        )
        saida = _rodar("check_arvore_canonica_do_wrapper", lar)
        rotulo, linha = _mensagem(saida, "sobra inerte")
        assert rotulo == "[INFO]", linha
        assert "NÃO carrega a nossa chamada do wrapper" in linha, linha
        assert "escritas por nós" not in saida, saida
        assert "o censo as conta como cobertura" not in saida, saida
        assert "falso conforto" not in saida, saida

    def test_sobra_com_o_wrapper_continua_sendo_acusada(self, tmp_path: Path) -> None:
        """O NEGATIVO: lixo nosso de verdade tem de continuar aparecendo."""
        lar = _lar_do_wrapper(
            tmp_path,
            viva={"316790": f"{WRAPPER} %command%"},
            solta={"413080": f"{WRAPPER} %command%"},
        )
        saida = _rodar("check_arvore_canonica_do_wrapper", lar)
        rotulo, linha = _mensagem(saida, "NOSSAS")
        assert rotulo == "[WARN]", linha
        assert "--recolher-fora-da-arvore-viva" in linha, linha

    def test_a_arvore_viva_intacta_continua_passando(self, tmp_path: Path) -> None:
        lar = _lar_do_wrapper(
            tmp_path, viva={"316790": f"{WRAPPER} %command%"}, solta={}
        )
        saida = _rodar("check_arvore_canonica_do_wrapper", lar)
        assert "chamam o wrapper" in saida, saida
        assert "sobra inerte" not in saida, saida


# ---------------------------------------------------------------------------
# O LAÇO, provado: o install roda, fecha com sucesso, e o aviso volta igual
# ---------------------------------------------------------------------------

INSTALL = ROOT / "install.sh"
#: O marcador que o passo 11c do install procura na saída do `--ensure`.
MARCADOR = "instalação pré-existente sem manifesto"


class TestOLacoEntreOInstallEOAviso:
    def test_ensure_mantem_a_instalacao_de_fora_e_nao_grava_manifesto(
        self, tmp_path: Path
    ) -> None:
        """A causa do laço, exercitada de verdade (sem rede, sem cache).

        Duas passagens do `ensure`: nenhuma grava o manifesto, e nas duas o
        relatório continua dizendo ``pinned_manifest_ok=False``. É por isso
        que *"rode ./install.sh"* nunca fechava esse aviso.
        """
        from hefesto_dualsense4unix.integrations import proton_pin as pp

        compat = tmp_path / "compatibilitytools.d"
        alvo = compat / NOME_DO_PIN
        alvo.mkdir(parents=True)
        (alvo / "proton").write_text("#!/bin/sh\n", encoding="utf-8")
        (alvo / "version").write_text("1 mentira\n", encoding="utf-8")
        conf = {"name": NOME_DO_PIN, "url": "http://exemplo.invalido", "sha256": SHA_DO_PIN}

        for volta in (1, 2):
            resultado = pp.ensure_pinned_proton(
                conf,
                compat_dir=compat,
                cache_dir=tmp_path / "cache",
                downloader=None,
            )
            assert resultado.state == "already", (volta, resultado)
            assert MARCADOR in resultado.detail, (volta, resultado)
            assert not (alvo / pp.MANIFEST_BASENAME).exists(), volta
            relatorio = pp.proton_pin_report(
                conf, compat_dir=compat, config_vdf_text="", installed_appids=[]
            )
            assert relatorio["pinned_present"] is True, volta
            assert relatorio["pinned_manifest_ok"] is False, volta

    def test_o_install_procura_o_marcador_que_o_modulo_emite(self) -> None:
        """A frase é CONTRATO entre `proton_pin.py` e o passo 11c do install.

        Sem esta régua, alguém reescreve o `detail` do `EnsureResult`, o
        `if` do install para de casar e o aviso volta a ser mudo — sem nada
        reprovando, que é a forma preferida deste defeito.
        """
        assert MARCADOR in INSTALL.read_text(encoding="utf-8")
        assert MARCADOR in (ROOT / "src/hefesto_dualsense4unix/integrations"
                            "/proton_pin.py").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "morta",
    [
        "o censo as conta como cobertura",
        "é delas que vem o falso conforto do censo",
    ],
)
def test_as_frases_derrubadas_sairam_do_fonte(morta: str) -> None:
    """Fato errado se SUBSTITUI, e sai de TODOS os lugares (regra da casa).

    O `censo_do_wrapper` lê só a árvore canônica desde 16/08/2026; medido no
    vdf dela em 02/09: 63 com wrapper, exatamente o total da árvore viva.

    A varredura pula COMENTÁRIO: a frase morta continua citada no comentário
    que registra por que ela caiu, e apagar o registro junto com a frase é
    perder a memória do defeito. O que não pode voltar é a frase EMITIDA.
    """
    vivas = [
        ln
        for ln in DOCTOR.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ]
    culpadas = [ln for ln in vivas if morta in ln]
    assert not culpadas, culpadas
