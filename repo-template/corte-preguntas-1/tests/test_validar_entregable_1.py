import json
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ARCHIVO_PREGUNTAS = BASE_DIR / "preguntas.json"

TIPOS_VALIDOS = {"verdadero_falso", "seleccion_simple"}
LECTURAS_VALIDAS = {
    "martes-semana-1",
    "jueves-semana-1",
    "martes-semana-2",
    "jueves-semana-2",
}
CAMPOS_REQUERIDOS = {"id", "lectura", "tipo", "enunciado", "opciones", "opcion_correcta", "nivel_dificultad"}

TOTAL_ESPERADO = len(LECTURAS_VALIDAS) * 10


def cargar_preguntas():
    with open(ARCHIVO_PREGUNTAS, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("preguntas", [])


def test_archivo_existe_y_es_json_valido():
    assert ARCHIVO_PREGUNTAS.exists(), f"Falta {ARCHIVO_PREGUNTAS.name}"
    cargar_preguntas()


def test_hay_exactamente_40_preguntas():
    preguntas = cargar_preguntas()
    assert len(preguntas) == TOTAL_ESPERADO, (
        f"Se esperan {TOTAL_ESPERADO} preguntas (10 por lectura x {len(LECTURAS_VALIDAS)} lecturas), "
        f"hay {len(preguntas)}"
    )


def test_campos_requeridos_presentes():
    for p in cargar_preguntas():
        faltantes = CAMPOS_REQUERIDOS - p.keys()
        assert not faltantes, f"Pregunta {p.get('id', '?')} sin campos: {faltantes}"


def test_lectura_es_valida():
    for p in cargar_preguntas():
        assert p["lectura"] in LECTURAS_VALIDAS, (
            f"Pregunta {p.get('id', '?')}: lectura inválida '{p.get('lectura')}'"
        )


def test_10_preguntas_por_lectura_5_vf_y_5_seleccion_simple():
    preguntas = cargar_preguntas()
    for lectura in LECTURAS_VALIDAS:
        de_esta_lectura = [p for p in preguntas if p.get("lectura") == lectura]
        assert len(de_esta_lectura) == 10, (
            f"Lectura '{lectura}': se esperan 10 preguntas, hay {len(de_esta_lectura)}"
        )

        conteo = Counter(p.get("tipo") for p in de_esta_lectura)
        assert conteo["verdadero_falso"] == 5, (
            f"Lectura '{lectura}': se esperan 5 V/F, hay {conteo['verdadero_falso']}"
        )
        assert conteo["seleccion_simple"] == 5, (
            f"Lectura '{lectura}': se esperan 5 de selección simple, hay {conteo['seleccion_simple']}"
        )


def test_tipos_validos():
    for p in cargar_preguntas():
        assert p.get("tipo") in TIPOS_VALIDOS, f"Tipo inválido en {p.get('id', '?')}: {p.get('tipo')}"


def test_enunciados_no_vacios():
    for p in cargar_preguntas():
        assert p["enunciado"].strip(), f"Pregunta {p.get('id', '?')} tiene enunciado vacío"


def test_enunciados_no_duplicados():
    preguntas = cargar_preguntas()
    enunciados = [p["enunciado"].strip().lower() for p in preguntas]
    duplicados = {e for e in enunciados if enunciados.count(e) > 1}
    assert not duplicados, f"Enunciados duplicados: {duplicados}"


def test_opcion_correcta_esta_en_opciones():
    for p in cargar_preguntas():
        assert p["opcion_correcta"] in p["opciones"], (
            f"Pregunta {p.get('id', '?')}: opcion_correcta no está en opciones"
        )


def test_verdadero_falso_tiene_las_2_opciones_correctas():
    for p in cargar_preguntas():
        if p["tipo"] == "verdadero_falso":
            assert set(p["opciones"]) == {"Verdadero", "Falso"}, (
                f"Pregunta {p.get('id', '?')}: las opciones de V/F deben ser exactamente Verdadero/Falso"
            )


def test_seleccion_simple_tiene_al_menos_3_opciones():
    for p in cargar_preguntas():
        if p["tipo"] == "seleccion_simple":
            assert len(p["opciones"]) >= 3, (
                f"Pregunta {p.get('id', '?')}: selección simple debe tener al menos 3 opciones"
            )


def test_nivel_dificultad_es_entero_entre_1_y_10():
    for p in cargar_preguntas():
        nivel = p["nivel_dificultad"]
        assert isinstance(nivel, int) and not isinstance(nivel, bool), (
            f"Pregunta {p.get('id', '?')}: nivel_dificultad debe ser un entero"
        )
        assert 1 <= nivel <= 10, f"Pregunta {p.get('id', '?')}: nivel_dificultad debe estar entre 1 y 10"
