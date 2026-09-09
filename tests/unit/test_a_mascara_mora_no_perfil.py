"""MASCARA-NO-PERFIL-01 (08/09/2026) — a máscara por controle entra no perfil.

A PERGUNTA E A RESPOSTA DELA
-----------------------------
*"A máscara por controle deve entrar no perfil, junto com luz, gatilho,
vibração, som, mic e sensores — ou fica da máquina?"* — **"pode entrar sim"**.

O QUE ELA SENTIU, e é o que abriu a sprint: trocar de perfil trocava o modo e
**não trocava a máscara** de ninguém. A máscara era da SESSÃO
(``controller_masks.json``) e sobrevivia ao perfil, então um perfil de jogo que
precisa do P2 em Xbox não tinha como dizer isso.

O QUE ESTE ARQUIVO MEDE, e cada bloco é uma das três mordidas da sprint:

1. **gravar ``mascara=xbox`` no P2 e ativar** → o vpad do P2 nasce ``045e:028e``
   e o do P1 continua ``054c:0df2``; trocar de perfil → os quatro seguem o
   perfil novo;
2. **arrancar o campo do esquema** → a régua reprova nomeando o assento cuja
   máscara ficou da sessão — é o teste ``..._deixa_o_assento_na_sessao`` abaixo,
   que faz a arrancada por dentro em vez de pedir que alguém a faça;
3. **``controller_masks.json`` não decide mais nada** → apagá-lo não muda vpad
   nenhum de quem o perfil declara.

E DESDE 09/09/2026, A DECISÃO QUE FECHOU A PERGUNTA QUE SOBRAVA
----------------------------------------------------------------
*"Um perfil que não fala de máscara devolve todo mundo ao padrão, ou deixa cada
um como está?"* — **"Default é Hefesto dualsense padrão"**. A entrega de 08/09
tinha escrito a segunda leitura, marcada como PROVISÓRIA; ela escolheu a
primeira, e três réguas deste arquivo mediam o contrário. O custo do que ela
escolheu está medido em ``test_o_que_a_devolucao_custa_...``: caem só os vpads
de quem estava FORA do padrão, e **zero** quando a mesa já o seguia.

**E UMA RÉGUA DAQUI ERA FALSA.** A da ordem de decisão olhava a DOCSTRING de
``mascara_efetiva`` com três ``in`` — reprovava quem editasse o texto e passava
com a ordem trocada no código (medido: com os degraus 1 e 2 invertidos, ela
dizia "passou"). Foi reescrita para medir os três degraus pelo que cada um
vence.

O QUE NÃO ESTÁ AQUI, E POR QUÊ: nenhum gamepad virtual é CRIADO. Criar um vpad
abre ``uinput`` de verdade, e a suíte inteira já derrubou a sessão gráfica dela
uma vez por isso. O par VID/PID é lido do catálogo que o vpad usa
(``uinput_gamepad.FLAVORS``) sobre a máscara que ``mascara_efetiva`` devolve —
o degrau MONTOU fica para a bancada, com os quatro na mesa.

Endereços de rádio: faixa SINTÉTICA da casa (``aabbcc…``, octetos 4 e 5
zerados), nunca o OUI de um aparelho real.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.subsystems import external_mask as mask_mod
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    FLAVORS,
    normalize_flavor,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileModeConfig,
)
from tests.unit.test_por_unidade_01_todas_as_abas import _StoreSemTrava

#: Os quatro assentos da mesa dela, na faixa sintética da casa.
P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"
P4 = "aabbcc000004"


def _par(mascara: str) -> tuple[int, int]:
    """``(vendor, product)`` que o vpad usaria para esta máscara.

    Lido do catálogo do próprio vpad, e não digitado: uma máscara nova não pode
    exigir que esta régua seja reescrita para continuar medindo.
    """
    entrada = FLAVORS[mascara]
    return int(entrada["vendor"]), int(entrada["product"])


@pytest.fixture
def registro_limpo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um ``controller_masks.json`` só deste teste, e um registro zerado.

    O registro é um SINGLETON de processo que lê o disco uma vez por instância
    — sem zerar antes e depois, a máscara de um teste responderia pelo vizinho,
    que é exatamente o modo de falhar que ele existe para impedir no daemon.
    """
    lar = tmp_path / "config"
    lar.mkdir()

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            lar.mkdir(parents=True, exist_ok=True)
        return lar

    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.xdg_paths.config_dir", _config_dir
    )
    mask_mod._zerar_registro_de_mascaras()
    try:
        yield lar
    finally:
        mask_mod._zerar_registro_de_mascaras()


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o mesmo molde do ``isolated_profiles_dir``."""
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


def _gerente() -> ProfileManager:
    return ProfileManager(
        controller=object(),  # type: ignore[arg-type]
        store=_StoreSemTrava(),  # type: ignore[arg-type]
    )


def _perfil(nome: str, **mascaras: str | None) -> Profile:
    """Perfil com uma máscara por assento — ``None`` = aquele não tem opinião."""
    return Profile(
        name=nome,
        match=MatchAny(),
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
        controllers={
            uniq: ControllerOverrides(mascara=valor)
            for uniq, valor in mascaras.items()
            if valor is not None
        },
    )


# ---------------------------------------------------------------------------
# 1. O CAMPO — e o que ele recusa
# ---------------------------------------------------------------------------


def test_o_campo_existe_e_none_e_sem_opiniao() -> None:
    """``mascara`` está ao lado das seis irmãs, e ``None`` é o default.

    Perfil antigo carrega igual: é o que faz esta entrega não mexer em nenhum
    arquivo dela que não peça para ser mexido.
    """
    assert "mascara" in ControllerOverrides.model_fields
    assert ControllerOverrides().mascara is None
    assert ControllerOverrides(mascara="xbox").mascara == "xbox"


def test_o_disco_nao_aceita_mascara_que_o_vpad_nao_sabe_criar() -> None:
    """O catálogo é o do vpad, e a recusa é em voz alta.

    ``"xbox 360"`` é o erro de digitação clássico desta casa — o normalizador
    TOLERANTE o transformaria em ``xbox``, e a fronteira estrita existe para que
    um engano não vire uma troca silenciosa de máscara.
    """
    with pytest.raises(ValidationError):
        ControllerOverrides(mascara="xbox 360")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ControllerOverrides(mascara="banana")  # type: ignore[arg-type]
    # E o que o esquema aceita é exatamente o que o vpad sabe criar.
    for mascara in mask_mod.mascaras_validas():
        assert ControllerOverrides(mascara=mascara).mascara == mascara  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. A PRIMEIRA MORDIDA — o P2 em Xbox, o P1 intacto
# ---------------------------------------------------------------------------


def test_a_mascara_do_perfil_vale_naquele_assento_e_so_nele(
    registro_limpo: Path,
) -> None:
    """``mascara=xbox`` no P2 → ``045e:028e``; o P1 continua ``054c:0df2``.

    MORDIDA: tire a chamada de ``apply_controller_mascaras`` do
    ``apply_profile`` (ou o ``set_mask`` de dentro dela) e os dois assentos
    voltam a responder a máscara do jogo — o P2 sai ``054c:0df2``, que é o
    defeito inteiro em um par de números.
    """
    _gerente().apply_controller_mascaras(_perfil("Jogo", **{P2: "xbox"}))

    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"
    assert mask_mod.mascara_efetiva(P1, "dualsense") == "dualsense"
    assert _par(mask_mod.mascara_efetiva(P2, "dualsense")) == (0x045E, 0x028E)
    assert _par(mask_mod.mascara_efetiva(P1, "dualsense")) == (0x054C, 0x0DF2)


def test_trocar_de_perfil_troca_as_quatro_mascaras(registro_limpo: Path) -> None:
    """Os quatro seguem o perfil novo — que é o que ela não tinha.

    É a metade da queixa: antes desta sprint a máscara era da sessão e
    ATRAVESSAVA a troca de perfil, então o segundo `assert` deste teste falharia
    com os quatro valores do perfil velho.
    """
    gerente = _gerente()
    gerente.apply_controller_mascaras(
        _perfil("Antes", **{P1: "xbox", P2: "xbox", P3: "xbox", P4: "xbox"})
    )
    assert [mask_mod.mascara_efetiva(u, "dualsense") for u in (P1, P2, P3, P4)] == [
        "xbox"
    ] * 4

    gerente.apply_controller_mascaras(
        _perfil(
            "Depois",
            **{P1: "dualsense", P2: "nintendo", P3: "dualsense", P4: "xbox"},
        )
    )
    assert [mask_mod.mascara_efetiva(u, "dualsense") for u in (P1, P2, P3, P4)] == [
        "dualsense",
        "nintendo",
        "dualsense",
        "xbox",
    ]


def test_so_quem_mudou_e_repintado(registro_limpo: Path) -> None:
    """NUMA-03: o controle em uso no meio da partida não some e volta.

    ``vpad_ficou_para_tras`` é a função que o laço do co-op consulta antes de
    derrubar um vpad. Depois de ativar um perfil que repete a máscara de três
    assentos e muda a do quarto, ela tem de dizer "para trás" **uma vez só**.
    """
    gerente = _gerente()
    gerente.apply_controller_mascaras(
        _perfil("Antes", **{P1: "xbox", P2: "xbox", P3: "xbox", P4: "xbox"})
    )
    # Os quatro vpads nasceram na máscara do perfil velho.
    vivos = {u: mask_mod.mascara_efetiva(u, "dualsense") for u in (P1, P2, P3, P4)}

    gerente.apply_controller_mascaras(
        _perfil("Depois", **{P1: "xbox", P2: "nintendo", P3: "xbox", P4: "xbox"})
    )

    para_tras = [
        u
        for u, flavor in vivos.items()
        if mask_mod.vpad_ficou_para_tras(flavor, u, "dualsense")
    ]
    assert para_tras == [P2], (
        "a troca de perfil derrubaria o vpad de quem NÃO mudou de máscara — "
        f"para trás: {para_tras}"
    )


def test_o_perfil_calado_devolve_todo_mundo_ao_padrao(
    registro_limpo: Path,
) -> None:
    """DECISÃO DELA, 09/09/2026: *"Default é Hefesto dualsense padrão"*.

    **ESTA RÉGUA MEDIA O CONTRÁRIO ATÉ HOJE.** Ela se chamava
    ``test_o_perfil_sem_opiniao_nao_mexe_na_mascara_de_ninguem`` e cobrava que o
    P2 continuasse em Xbox depois de um perfil calado — a leitura PROVISÓRIA que
    a entrega de 08/09 escreveu, e que ela recusou. A pergunta era *"um perfil
    que não fala de máscara devolve todo mundo ao padrão, ou deixa cada um como
    está?"*, e a resposta foi a primeira.

    MORDIDA: tire a chamada de ``registro.manter_somente(declaradas)`` do fim de
    ``apply_controller_mascaras`` e o P2 fica em Xbox — a decisão dela deixa de
    valer, e é este `assert` que reprova.
    """
    gerente = _gerente()
    gerente.apply_controller_mascaras(_perfil("Antes", **{P2: "xbox"}))
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"

    relatorio = gerente.apply_controller_mascaras(
        Profile(
            name="Calado",
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
        )
    )

    assert mask_mod.mascara_efetiva(P2, "dualsense") == "dualsense", (
        "o perfil calado tinha de ter devolvido o P2 ao padrão"
    )
    assert relatorio == {f"mascara:{P2}": "padrão"}, (
        "quem voltou ao padrão tem de aparecer no relatório — a janela precisa "
        "poder dizer o que mudou naquela peça"
    )
    assert mask_mod.registro_de_mascaras().snapshot() == {}, (
        "a entrada do cache é o que sobrevivia à troca de perfil; ela some"
    )


def test_o_perfil_calado_devolve_ate_quem_ele_nunca_viu(
    registro_limpo: Path,
) -> None:
    """A devolução alcança QUEM O PERFIL NÃO MENCIONA — inclusive um externo.

    É a diferença entre *"o perfil manda no que declara"* e *"o perfil manda"*.
    Um 8BitDo que ganhou máscara pela tela, numa sessão sem perfil, perde-a na
    próxima ativação: o dono passou a ser o perfil, e um cache que sobrevive ao
    dono é a escolha do perfil ANTERIOR se passando por escolha dela.
    """
    externo = "aabbcc0000ff"
    mask_mod.registro_de_mascaras().set_mask(externo, "nintendo")
    assert mask_mod.mascara_efetiva(externo, "dualsense") == "nintendo"

    _gerente().apply_controller_mascaras(_perfil("Jogo", **{P1: "xbox"}))

    assert mask_mod.mascara_efetiva(externo, "dualsense") == "dualsense"
    assert mask_mod.mascara_efetiva(P1, "dualsense") == "xbox"


def test_o_que_a_devolucao_custa_e_so_o_vpad_de_quem_estava_fora(
    registro_limpo: Path,
) -> None:
    """O CUSTO DA DECISÃO DELA, medido — e ele é o que a torna barata.

    O medo escrito na entrega de 08/09 era *"derrubar e recriar os quatro vpads
    dela ao ativar um perfil calado"*. Quem derruba vpad é o laço do co-op, por
    ``vpad_ficou_para_tras``, e ele compara a máscara EFETIVA: apagar a entrada
    de quem já estava no padrão não muda a efetiva, e o vpad **não cai**.

    As quatro linhas desta régua são as quatro medidas que estão escritas em
    ``manter_somente`` e em ``apply_controller_mascaras``. A que decide é a
    última: quatro entradas apagadas, ZERO controles saindo da partida.
    """
    calado = Profile(
        name="Calado",
        match=MatchAny(),
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
    )
    assentos = (P1, P2, P3, P4)

    def _quantos_caem(antes: dict[str, str]) -> int:
        mask_mod._zerar_registro_de_mascaras()
        (registro_limpo / "controller_masks.json").unlink(missing_ok=True)
        gerente = _gerente()
        if antes:
            gerente.apply_controller_mascaras(_perfil("Antes", **antes))
        vivos = {u: mask_mod.mascara_efetiva(u, "dualsense") for u in assentos}
        gerente.apply_controller_mascaras(calado)
        return sum(
            mask_mod.vpad_ficou_para_tras(vivos[u], u, "dualsense") for u in assentos
        )

    assert _quantos_caem({}) == 0, "mesa já no padrão: ninguém pode cair"
    assert _quantos_caem({P2: "xbox"}) == 1, "só o assento que estava fora cai"
    assert _quantos_caem(dict.fromkeys(assentos, "xbox")) == 4, (
        "os quatro estavam fora do padrão; os quatro voltam, e é a decisão dela"
    )
    assert _quantos_caem(dict.fromkeys(assentos, "dualsense")) == 0, (
        "quatro entradas APAGADAS e nenhum vpad derrubado — é este número que "
        "responde ao custo levantado na entrega de 08/09"
    )


def test_o_relatorio_diz_a_peca_e_a_mascara(registro_limpo: Path) -> None:
    """``mascara:<uniq>`` — o mesmo formato-por-peça do ``mic`` e do ``sensores``.

    É por ele que a janela consegue dizer QUAL peça foi atendida, em vez de
    fundir a mesa inteira num rótulo só.
    """
    relatorio = _gerente().apply_controller_mascaras(
        _perfil("Jogo", **{P1: "dualsense", P2: "xbox"})
    )
    assert relatorio == {f"mascara:{P1}": "dualsense", f"mascara:{P2}": "xbox"}


# ---------------------------------------------------------------------------
# 3. A SEGUNDA MORDIDA — arrancar o campo deixa o assento na sessão
# ---------------------------------------------------------------------------


def test_arrancar_o_campo_deixa_o_assento_na_sessao(registro_limpo: Path) -> None:
    """A mordida da sprint, feita por dentro: um override SEM o campo.

    ``ControllerOverrides()`` sem ``mascara`` é exatamente o que o esquema
    ANTIGO produzia para o mesmo JSON dela — o campo não existia, e o valor
    caía no ``extra="forbid"`` ou era ignorado. Com ele arrancado, o assento
    fica com a máscara da SESSÃO (aqui: nenhuma, logo a do jogo), e é isso que
    esta régua nomeia.

    Se um dia alguém tirar ``mascara`` de ``ControllerOverrides``, o
    ``_perfil()`` acima levanta ``ValidationError`` e a suíte inteira desta
    frente cai — que é o barulho certo.
    """
    perfil_sem_o_campo = Profile(
        name="Velho",
        match=MatchAny(),
        controllers={P2: ControllerOverrides()},  # o campo arrancado
    )
    relatorio = _gerente().apply_controller_mascaras(perfil_sem_o_campo)

    assert relatorio == {}, (
        "um override sem `mascara` não pode escrever máscara nenhuma"
    )
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "dualsense", (
        "o assento P2 ficou com a máscara da SESSÃO — é o defeito que o campo "
        "novo existe para curar"
    )


# ---------------------------------------------------------------------------
# 4. A TERCEIRA MORDIDA — o arquivo de sessão não decide mais nada
# ---------------------------------------------------------------------------


def test_apagar_o_arquivo_de_mascaras_nao_muda_vpad_de_quem_o_perfil_declara(
    registro_limpo: Path,
) -> None:
    """``controller_masks.json`` virou cache: apagá-lo custa uma reativação.

    O arquivo continua existindo porque ``mascara_efetiva`` é consultada no
    tique do co-op — ler o perfil do disco ali seria a tempestade de syscalls
    que o mapa de motores já pagou uma vez. O que ele deixou de ser é DONO.
    """
    gerente = _gerente()
    perfil = _perfil("Jogo", **{P1: "xbox", P2: "nintendo"})
    gerente.apply_controller_mascaras(perfil)
    arquivo = registro_limpo / "controller_masks.json"
    assert arquivo.exists(), "o cache nem chegou a ser escrito"
    assert {
        e["identity"]: e["flavor"] for e in json.loads(arquivo.read_text())["masks"]
    } == {P1: "xbox", P2: "nintendo"}

    # A mesa dela: o arquivo some (limpeza, migração, um `rm` curioso).
    arquivo.unlink()
    mask_mod._zerar_registro_de_mascaras()
    assert mask_mod.mascara_efetiva(P1, "dualsense") == "dualsense", (
        "sem o cache e sem reativar, quem responde é a máscara do jogo"
    )

    # E a reativação o traz de volta inteiro, sem ela escolher nada de novo.
    gerente.apply_controller_mascaras(perfil)
    assert mask_mod.mascara_efetiva(P1, "dualsense") == "xbox"
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "nintendo"


# ---------------------------------------------------------------------------
# 5. O GESTO DA TELA — mesma forma, e agora ele grava no perfil
# ---------------------------------------------------------------------------


class _Store:
    """``store`` de mentira: só o ``active_profile``."""

    def __init__(self, ativo: str | None) -> None:
        self.active_profile = ativo


class _Handlers(IpcHandlersMixin):
    """O bastante do mixin para chamar ``_handle_gamepad_mask_set``."""

    def __init__(self, *, ativo: str | None) -> None:
        self.store = _Store(ativo)  # type: ignore[assignment]
        self.controller = SimpleNamespace(  # type: ignore[assignment]
            describe_controllers=lambda: []
        )
        self.daemon = None  # type: ignore[assignment]


def _gesto(h: _Handlers, **params: Any) -> dict[str, Any]:
    return asyncio.run(h._handle_gamepad_mask_set(params))


def test_o_gesto_do_chip_grava_no_perfil_ativo(
    registro_limpo: Path, perfis: Path
) -> None:
    """`gamepad.mask.set {uniq, flavor}` → `controllers[uniq].mascara` no disco.

    A FORMA DO GESTO NÃO MUDOU — é o que a sprint exige (`nao_toca` na aba
    Jogar). O que mudou é onde a escolha para.

    MORDIDA: apague a chamada de ``_mascara_no_perfil`` no handler — o
    ``load_profile`` abaixo devolve o perfil sem o campo, e a máscara volta a
    morrer com a sessão.
    """
    loader_module.save_profile(Profile(name="Bancada", match=MatchAny()))
    h = _Handlers(ativo="Bancada")

    corpo = _gesto(h, uniq=P2, flavor="xbox")

    assert corpo["status"] == "ok" and corpo["flavor"] == "xbox"
    assert corpo["perfil"] == "Bancada" and corpo["gravado"] is True
    dele = (loader_module.load_profile("Bancada").controllers or {})[P2]
    assert dele.mascara == "xbox"
    # E vale AGORA, sem esperar a próxima ativação de perfil.
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"


def test_o_gesto_vazio_limpa_dos_dois_lados(
    registro_limpo: Path, perfis: Path
) -> None:
    """``flavor`` vazio = *"volta a herdar a do perfil"*, no disco e na sessão.

    E a entrada que esvaziou SOME do mapa: um ``uniq`` apontando para ``{}``
    faria a coluna "Ajuste próprio" da aba Perfis acender sobre nada.
    """
    loader_module.save_profile(Profile(name="Bancada", match=MatchAny()))
    h = _Handlers(ativo="Bancada")
    _gesto(h, uniq=P2, flavor="xbox")

    corpo = _gesto(h, uniq=P2, flavor="")

    assert corpo["flavor"] is None and corpo["gravado"] is True
    assert (loader_module.load_profile("Bancada").controllers or {}) == {}
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "dualsense"


def test_sem_perfil_ativo_o_gesto_ainda_vale_na_sessao(
    registro_limpo: Path, perfis: Path
) -> None:
    """Sem perfil não há onde guardar — e recusar seria pior que a sessão.

    A tela recebe ``gravado: false`` com o ``motivo``, em vez de um "aplicado"
    sobre nada; a máscara vale enquanto o daemon viver.
    """
    corpo = _gesto(_Handlers(ativo=None), uniq=P2, flavor="xbox")

    assert corpo["status"] == "ok" and corpo["gravado"] is False
    assert corpo["motivo"] == "sem_perfil"
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"


def test_o_gesto_nao_grava_sob_uma_chave_que_ninguem_casa(
    registro_limpo: Path, perfis: Path
) -> None:
    """``path:/dev/input/event9`` não é peça de plástico — e não vira chave.

    ``norm_mac`` devolveria ``"adeee9"`` para esse caminho: uma chave que parece
    boa e que peça nenhuma casa. Para LER é inofensivo; para GRAVAR é a escolha
    dela sumindo calada, e é a medição de 04/09/2026 que o
    ``_chave_de_peca_que_grava`` guarda.
    """
    loader_module.save_profile(Profile(name="Bancada", match=MatchAny()))

    corpo = _gesto(_Handlers(ativo="Bancada"), uniq="path:/dev/input/event9",
                   flavor="xbox")

    assert corpo["gravado"] is False and corpo["motivo"] == "sem_endereco"
    assert (loader_module.load_profile("Bancada").controllers or {}) == {}


def test_o_gesto_repetido_nao_regrava_o_perfil(
    registro_limpo: Path, perfis: Path
) -> None:
    """NADA MUDOU = NÃO REGRAVA — e aqui isso vale mais que no motor.

    Um ``save_profile`` faz o daemon reaplicar o perfil inteiro, e a reaplicação
    passa por ``apply_controller_mascaras`` — que é justamente quem pode
    derrubar vpad.
    """
    loader_module.save_profile(Profile(name="Bancada", match=MatchAny()))
    h = _Handlers(ativo="Bancada")
    _gesto(h, uniq=P2, flavor="xbox")

    corpo = _gesto(h, uniq=P2, flavor="xbox")

    assert corpo["gravado"] is False and corpo["motivo"] == "sem_mudanca"


# ---------------------------------------------------------------------------
# 6. A ORDEM DE DECISÃO MORA NUM LUGAR SÓ
# ---------------------------------------------------------------------------


def test_a_ordem_de_decisao_vale_degrau_a_degrau(registro_limpo: Path) -> None:
    """Os três degraus, medidos no COMPORTAMENTO — não na prosa que os descreve.

    **ESTA RÉGUA ERA FALSA, e a assinatura é a que a casa nomeia.** Ela se
    chamava ``test_a_ordem_de_decisao_esta_escrita_onde_ela_e_executada`` e fazia
    três ``assert <substring> in mascara_efetiva.__doc__``. Ou seja: reprovava
    quem editasse a docstring e **passava se alguém trocasse a ordem no código**
    — mede o texto, não o ato. Foi apontada pelo conferente em 09/09/2026.

    Os três degraus, cada um provado pelo que ele VENCE:

    1. ``controllers[uniq].mascara`` vence o ``mode.gamepad_flavor``;
    2. ``mode.gamepad_flavor`` vence o padrão, para quem o perfil não declara;
    3. o padrão responde quando nem um nem outro disse nada — e o valor não é
       digitado aqui: sai do ``normalize_flavor``, que é o dono dele.

    MORDIDA: inverta os dois primeiros `if` de ``mascara_efetiva`` (devolver
    ``flavor_do_jogo`` antes de olhar o registro) e o degrau 1 reprova. Com a
    régua velha, essa mesma troca passava verde.
    """
    gerente = _gerente()
    # O perfil declara SÓ o P2; o eixo do perfil é "nintendo" para que os três
    # degraus tenham três valores diferentes e nenhum `assert` case por acaso.
    gerente.apply_controller_mascaras(
        Profile(
            name="Ordem",
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="nintendo"),
            controllers={P2: ControllerOverrides(mascara="xbox")},
        )
    )

    # 1. o campo do controle vence o eixo do perfil.
    assert mask_mod.mascara_efetiva(P2, "nintendo") == "xbox"
    # 2. quem o perfil não declara cai no eixo do perfil, e não no padrão.
    assert mask_mod.mascara_efetiva(P1, "nintendo") == "nintendo"
    # 3. sem os dois primeiros, o padrão — lido de quem o define.
    assert mask_mod.mascara_efetiva(P1, None) == normalize_flavor(None)
    assert mask_mod.mascara_efetiva(None, None) == normalize_flavor(None)


def test_quem_executa_o_primeiro_degrau_nao_e_a_mascara_efetiva(
    registro_limpo: Path,
) -> None:
    """O degrau 1 é EXECUTADO por quem escreve o cache, não por quem o lê.

    **CORREÇÃO DE FATO — 09/09/2026.** A entrega de 08/09 afirmava que *"a ordem
    de decisão está escrita onde é executada (``external_mask.mascara_efetiva``)"*.
    É falso na metade que importa: ``mascara_efetiva`` **lê** o registro. Quem
    executa o degrau 1 é ``apply_controller_mascaras``, escrevendo no cache — e,
    desde a decisão dela, apagando dele quem o perfil não declara.

    A prova é a diferença entre carregar o perfil e ATIVÁ-LO: com o perfil na
    mão e o applier não chamado, ``mascara_efetiva`` não sabe de nada.
    """
    perfil = _perfil("Jogo", **{P2: "xbox"})

    # O perfil existe, o campo está preenchido — e ninguém aplicou nada.
    assert perfil.controllers is not None
    assert perfil.controllers[P2].mascara == "xbox"
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "dualsense", (
        "`mascara_efetiva` não lê perfil: se ela executasse o degrau 1, este "
        "`assert` seria 'xbox' sem ninguém ter ativado o perfil"
    )

    _gerente().apply_controller_mascaras(perfil)
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"
