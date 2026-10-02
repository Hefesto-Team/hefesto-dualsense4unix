"""Histórico versionado de perfis e o journal de cada gravação."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import (
    HISTORICO_DIR_NAME,
    HISTORICO_MAX_VERSOES,
    delete_profile,
    listar_historico,
    load_profile,
    restaurar_do_historico,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    Match,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)


@pytest.fixture
def dir_perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Aponta `profiles_dir()` para um tmp — nada toca o ~/.config dela."""
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _falso_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _falso_profiles_dir)
    return alvo


def _perfil(
    nome: str = "pragmata",
    *,
    match: Match | None = None,
    priority: int = 10,
) -> Profile:
    return Profile(
        name=nome,
        match=match if match is not None else MatchCriteria(window_class=["pragmata"]),
        priority=priority,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"), right=TriggerConfig(mode="Off")
        ),
        leds=LedsConfig(lightbar=(1, 2, 3)),
    )


def test_tres_saves_guardam_duas_versoes_anteriores(dir_perfis: Path) -> None:
    """Salvar N vezes guarda as N-1 versões ANTERIORES (a atual está no perfil)."""
    save_profile(_perfil(priority=10))
    save_profile(_perfil(priority=20))
    save_profile(_perfil(priority=30))

    versoes = listar_historico("pragmata")
    assert len(versoes) == 2, f"esperava 2 versões guardadas, veio {versoes}"

    prioridades = [json.loads(v.read_text(encoding="utf-8"))["priority"] for v in versoes]
    assert prioridades == [10, 20]
    assert load_profile("pragmata").priority == 30


def test_historico_vive_fora_do_alcance_das_varreduras(dir_perfis: Path) -> None:
    """O `.historico/` não pode virar perfil: nenhuma varredura o enxerga."""
    save_profile(_perfil(priority=10))
    save_profile(_perfil(priority=20))

    assert (dir_perfis / HISTORICO_DIR_NAME / "pragmata").is_dir()
    assert [p.name for p in sorted(dir_perfis.glob("*.json"))] == ["pragmata.json"]
    assert [p.name for p in loader_module.load_all_profiles()] == ["pragmata"]


def test_historico_retem_apenas_as_ultimas_n(dir_perfis: Path) -> None:
    """A poda mantém `HISTORICO_MAX_VERSOES` recentes, mais a primeira do dia."""
    total = HISTORICO_MAX_VERSOES + 5
    for prioridade in range(total):
        save_profile(_perfil(priority=prioridade))

    versoes = listar_historico("pragmata")
    assert len(versoes) == HISTORICO_MAX_VERSOES + 1
    prioridades = [json.loads(v.read_text(encoding="utf-8"))["priority"] for v in versoes]
    assert prioridades == [0, *range(total - HISTORICO_MAX_VERSOES - 1, total - 1)]


def test_restore_devolve_a_versao_byte_a_byte(dir_perfis: Path) -> None:
    """Restaurar tem de reproduzir os BYTES guardados, não uma reserialização."""
    escrito_a_mao = (
        b'{\n'
        b'    "priority": 10,\n'
        b'    "name": "pragmata",\n'
        b'    "version": 1,\n'
        b'    "match": {"type": "criteria", "window_class": ["pragmata"]}\n'
        b'}\n'
    )
    (dir_perfis / "pragmata.json").write_bytes(escrito_a_mao)

    save_profile(_perfil(priority=191, match=MatchAny()))
    assert (dir_perfis / "pragmata.json").read_bytes() != escrito_a_mao

    alvo, versao = restaurar_do_historico("pragmata")
    assert alvo == dir_perfis / "pragmata.json"
    assert versao.parent.name == "pragmata"
    assert alvo.read_bytes() == escrito_a_mao

    devolvido = load_profile("pragmata")
    assert devolvido.priority == 10
    assert devolvido.match.type == "criteria"


def test_restore_arquiva_a_versao_atual_antes_de_pisar(dir_perfis: Path) -> None:
    """Restaurar por engano também tem volta."""
    save_profile(_perfil(priority=10))
    save_profile(_perfil(priority=191, match=MatchAny()))
    restaurar_do_historico("pragmata")

    guardadas = [
        json.loads(v.read_text(encoding="utf-8")) for v in listar_historico("pragmata")
    ]
    assert any(d["priority"] == 191 for d in guardadas), (
        "a versão substituída pela restauração precisa estar no histórico"
    )


def test_restore_em_carimbo_escolhe_a_versao_pedida(dir_perfis: Path) -> None:
    """`--em <carimbo>` volta para uma versão específica, não para a última."""
    save_profile(_perfil(priority=10))
    save_profile(_perfil(priority=20))
    save_profile(_perfil(priority=30))

    primeira = listar_historico("pragmata")[0]
    restaurar_do_historico("pragmata", primeira.name)
    assert load_profile("pragmata").priority == 10

    segunda = listar_historico("pragmata")[1]
    restaurar_do_historico("pragmata", segunda.stem)
    assert load_profile("pragmata").priority == json.loads(
        segunda.read_text(encoding="utf-8")
    )["priority"]


def test_restore_sem_historico_reprova_com_mensagem(dir_perfis: Path) -> None:
    save_profile(_perfil())
    with pytest.raises(FileNotFoundError, match="sem histórico"):
        restaurar_do_historico("pragmata")


def test_restore_recusa_versao_que_nao_valida(dir_perfis: Path) -> None:
    """Lixo guardado não volta ao disco — validar antes de escrever.

    MORDIDA: arrancar o `Profile.model_validate` de `restaurar_do_historico`
    faz o JSON quebrado voltar a ser o perfil ativo.
    """
    save_profile(_perfil(priority=10))
    save_profile(_perfil(priority=20))
    guardada = listar_historico("pragmata")[0]
    guardada.write_text('{"name": "pragmata", "match": {"type": "?"}}', encoding="utf-8")

    with pytest.raises(ValueError, match="schema"):
        restaurar_do_historico("pragmata", guardada.name)
    assert load_profile("pragmata").priority == 20


def test_delete_guarda_a_ultima_versao(dir_perfis: Path) -> None:
    """Apagar é a gravação mais destrutiva — a última versão fica guardada."""
    save_profile(_perfil(priority=42))
    delete_profile("pragmata")

    assert not (dir_perfis / "pragmata.json").exists()
    guardadas = [
        json.loads(v.read_text(encoding="utf-8")) for v in listar_historico("pragmata")
    ]
    assert [d["priority"] for d in guardadas] == [42]


def test_backup_quebrado_nao_impede_a_gravacao(
    dir_perfis: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falha ao arquivar NÃO pode impedir a usuária de salvar o perfil dela."""
    save_profile(_perfil(priority=10))

    def _explode(*_a: object, **_k: object) -> Path:
        raise OSError("disco cheio")

    monkeypatch.setattr(loader_module, "historico_dir", _explode)
    caminho = save_profile(_perfil(priority=20))
    assert json.loads(caminho.read_text(encoding="utf-8"))["priority"] == 20


def test_nome_acentuado_encontra_o_proprio_historico(dir_perfis: Path) -> None:
    """O histórico é indexado pelo ARQUIVO; o display name acentuado chega nele."""
    save_profile(_perfil("Ação Rápida", priority=10))
    save_profile(_perfil("Ação Rápida", priority=20))

    assert len(listar_historico("Ação Rápida")) == 1
    assert len(listar_historico("acao_rapida")) == 1


class _Relogio:
    """Carimbos na ordem, com o dia que o teste escolhe (o do produto é o agora)."""

    def __init__(self) -> None:
        self.dia = "20260927"
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"{self.dia}T{self._n // 3600:02d}{self._n // 60 % 60:02d}{self._n % 60:02d}_000000"


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    relogio = _Relogio()
    monkeypatch.setattr(loader_module, "_carimbo_de_versao", relogio)
    return relogio


def _prioridades(nome: str = "pragmata") -> list[int]:
    return [
        json.loads(v.read_text(encoding="utf-8"))["priority"]
        for v in listar_historico(nome)
    ]


def test_doze_gravacoes_seguidas_deixam_a_versao_de_antes_delas(
    dir_perfis: Path, relogio: _Relogio
) -> None:
    """A régua da sprint: doze gravações seguidas, e a versão dela fica no disco."""
    save_profile(_perfil(priority=7))
    relogio.dia = "20260928"
    for prioridade in range(100, 112):
        save_profile(_perfil(priority=prioridade))

    guardadas = _prioridades()
    assert 7 in guardadas, f"a versão de antes da rajada sumiu: {guardadas}"
    assert guardadas[0] == 7
    assert guardadas[-HISTORICO_MAX_VERSOES:] == list(range(101, 111))
    assert load_profile("pragmata").priority == 111


def test_a_primeira_de_cada_dia_sobrevive_as_rajadas_dos_dias_seguintes(
    dir_perfis: Path, relogio: _Relogio
) -> None:
    """Uma rajada por dia, três dias: a versão de antes de cada uma fica."""
    save_profile(_perfil(priority=1))
    for dia, base in (("20260927", 2700), ("20260928", 2800), ("20260929", 2900)):
        relogio.dia = dia
        for passo in range(12):
            save_profile(_perfil(priority=base + passo))

    assert _prioridades() == [1, 2711, 2811, *range(2901, 2911)]


def test_os_dias_guardados_tem_teto(dir_perfis: Path, relogio: _Relogio) -> None:
    """Uma gravação por dia, por mais dias que o teto: o dia mais velho sai."""
    teto = max(HISTORICO_MAX_VERSOES, loader_module.HISTORICO_DIAS)
    save_profile(_perfil(priority=0))
    primeiro = date(2026, 10, 1)
    for n in range(1, teto + 6):
        relogio.dia = (primeiro + timedelta(days=n)).strftime("%Y%m%d")
        save_profile(_perfil(priority=n))

    assert _prioridades() == list(range(5, teto + 5))


class _LoggerEspiao:
    """Captura os eventos estruturados emitidos pelo loader."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, object]]] = []

    def info(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, campos))

    def warning(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, campos))

    def campos(self, evento: str) -> dict[str, object]:
        for nome, campos in self.eventos:
            if nome == evento:
                return campos
        raise AssertionError(f"evento {evento!r} não foi emitido: {self.eventos}")


@pytest.fixture
def espiao(monkeypatch: pytest.MonkeyPatch) -> _LoggerEspiao:
    espiao = _LoggerEspiao()
    monkeypatch.setattr(loader_module, "logger", espiao)
    return espiao


def test_journal_registra_a_transicao_criteria_para_any(
    dir_perfis: Path, espiao: _LoggerEspiao
) -> None:
    """Gravar `any` por cima de `criteria` registra a PERDA da regra."""
    save_profile(_perfil(match=MatchCriteria(window_class=["pragmata"]), priority=10))
    espiao.eventos.clear()
    save_profile(_perfil(match=MatchAny(), priority=191))

    campos = espiao.campos("profile_salvo")
    assert campos["nome"] == "pragmata"
    assert campos["match_antes"] == "criteria"
    assert campos["match_depois"] == "any"
    assert campos["priority_antes"] == 10
    assert campos["priority_depois"] == 191
    assert campos["criado"] is False
    assert campos["origem"], "a origem da gravação tem de aparecer"
    assert campos["backup"], "o journal aponta para a versão guardada"


def test_journal_marca_o_perfil_que_nasce(
    dir_perfis: Path, espiao: _LoggerEspiao
) -> None:
    """Primeira gravação: sem `antes`, e `criado=True` para distinguir."""
    save_profile(_perfil(priority=7))
    campos = espiao.campos("profile_salvo")
    assert campos["criado"] is True
    assert campos["match_antes"] is None
    assert campos["priority_antes"] is None
    assert campos["backup"] is None


def test_journal_confessa_o_arquivo_ilegivel(
    dir_perfis: Path, espiao: _LoggerEspiao
) -> None:
    """Gravar por cima de um JSON corrompido registra `match_antes=ilegivel`."""
    (dir_perfis / "pragmata.json").write_text("{ isto não é json", encoding="utf-8")
    save_profile(_perfil(priority=5))

    campos = espiao.campos("profile_salvo")
    assert campos["match_antes"] == "ilegivel"
    assert campos["priority_antes"] is None
    guardadas = listar_historico("pragmata")
    assert len(guardadas) == 1
    assert guardadas[0].read_text(encoding="utf-8") == "{ isto não é json"


def test_journal_aceita_origem_declarada(
    dir_perfis: Path, espiao: _LoggerEspiao
) -> None:
    """Quem sabe quem é (janela, IPC, migração) declara a origem."""
    save_profile(_perfil(), origem="janela:aba-perfis")
    assert espiao.campos("profile_salvo")["origem"] == "janela:aba-perfis"


def test_journal_registra_o_delete(dir_perfis: Path, espiao: _LoggerEspiao) -> None:
    save_profile(_perfil())
    espiao.eventos.clear()
    delete_profile("pragmata")
    campos = espiao.campos("profile_apagado")
    assert campos["nome"] == "pragmata"
    assert campos["backup"], "apagar também deixa a versão guardada"
