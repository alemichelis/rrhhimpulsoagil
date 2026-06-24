from flask import Flask, jsonify, request, session, send_from_directory, make_response
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rrhh_parametros.db")

app = Flask(__name__, static_folder='frontend', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'rrhh-dev-secret-2024')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── RUTAS ESTÁTICAS ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('frontend', 'index.html')


# ── DISPATCHER ────────────────────────────────────────────────────────────────

@app.route('/api/<method>', methods=['POST'])
def api_dispatch(method):
    data = request.get_json(force=True, silent=True) or {}
    args = data.get('args', [])
    fn = METHODS.get(method)
    if not fn:
        return jsonify({'ok': False, 'msg': 'Método no encontrado'}), 404
    try:
        return jsonify(fn(*args))
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)})


# ── AUTH ──────────────────────────────────────────────────────────────────────

def get_sesion():
    return {
        'usuario': session.get('usuario'),
        'rol':     session.get('rol'),
        'legajo':  session.get('legajo')
    }

def login_admin(usuario, password):
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id FROM admin_usuarios WHERE usuario=? AND password=?",
                (usuario, password)
            ).fetchone()
        if row:
            session['usuario'] = usuario
            session['rol']     = 'admin'
            session['legajo']  = None
            return {'ok': True}
        return {'ok': False, 'msg': 'Usuario o contraseña incorrectos'}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

def login_empleado(legajo, nro_doc):
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT legajo, apellido_nombre FROM empleados WHERE legajo=? AND nro_doc=?",
                (legajo.strip(), nro_doc.strip())
            ).fetchone()
        if row:
            session['usuario'] = row['apellido_nombre']
            session['rol']     = 'empleado'
            session['legajo']  = row['legajo']
            return {'ok': True, 'nombre': row['apellido_nombre']}
        return {'ok': False, 'msg': 'Legajo o número de documento incorrecto'}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

def logout():
    session.clear()
    return {'ok': True}


# ── MÓDULO 1: PARÁMETROS ──────────────────────────────────────────────────────

_TABLAS = {
    'CARGOS':           'cargos',
    'SECTORES':         'sectores',
    'CENTROS DE COSTO': 'centros_costo',
    'LUGAR DE TRABAJO': 'lugares_trabajo'
}

def get_parametros(tabla):
    t = _TABLAS.get(tabla)
    if not t:
        return {'ok': False, 'msg': 'Tabla inválida'}
    try:
        with get_db() as conn:
            rows = conn.execute(
                f"SELECT id, codigo, nombre FROM {t} ORDER BY nombre"
            ).fetchall()
        return {'ok': True, 'data': [dict(r) for r in rows]}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

def guardar_parametro(tabla, codigo, nombre, id=None):
    t = _TABLAS.get(tabla)
    if not t:
        return {'ok': False, 'msg': 'Tabla inválida'}
    try:
        with get_db() as conn:
            if id:
                conn.execute(
                    f"UPDATE {t} SET codigo=?, nombre=? WHERE id=?",
                    (codigo.strip(), nombre.strip(), id)
                )
            else:
                conn.execute(
                    f"INSERT INTO {t} (codigo, nombre) VALUES (?, ?)",
                    (codigo.strip(), nombre.strip())
                )
            conn.commit()
        return {'ok': True}
    except sqlite3.IntegrityError:
        return {'ok': False, 'msg': 'El código ya existe en esta tabla'}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

def eliminar_parametro(tabla, id):
    t = _TABLAS.get(tabla)
    if not t:
        return {'ok': False, 'msg': 'Tabla inválida'}
    try:
        with get_db() as conn:
            conn.execute(f"DELETE FROM {t} WHERE id=?", (id,))
            conn.commit()
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}


# ── MÓDULO 2: EMPLEADOS ───────────────────────────────────────────────────────

def get_listas_parametros():
    try:
        with get_db() as conn:
            def lista(sql):
                return [r[0] for r in conn.execute(sql).fetchall()]
            return {
                'ok':          True,
                'lugares':     lista("SELECT nombre FROM lugares_trabajo ORDER BY nombre"),
                'cargos':      lista("SELECT nombre FROM cargos ORDER BY nombre"),
                'sectores':    lista("SELECT nombre FROM sectores ORDER BY nombre"),
                'centros_costo': lista("SELECT nombre FROM centros_costo ORDER BY nombre"),
                'jefes': ['Ninguno'] + lista(
                    "SELECT apellido_nombre FROM empleados ORDER BY apellido_nombre"
                )
            }
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

def get_empleados():
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT legajo, apellido_nombre, cuil, tipo_doc, nro_doc,
                       lugar_trabajo, jornada, fecha_ingreso, fecha_antiguedad,
                       cargo, tipo_empleado, sector, jefe_admin, centro_costo,
                       estado, fecha_baja, motivo_baja
                FROM empleados ORDER BY apellido_nombre
            """).fetchall()
        return {'ok': True, 'data': [dict(r) for r in rows]}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

def guardar_empleado(datos):
    try:
        leg = datos['legajo'].strip()
        with get_db() as conn:
            exists = conn.execute(
                "SELECT 1 FROM empleados WHERE legajo=?", (leg,)
            ).fetchone()
            if exists:
                conn.execute("""
                    UPDATE empleados SET
                        apellido_nombre=?, cuil=?, tipo_doc=?, nro_doc=?,
                        lugar_trabajo=?, jornada=?, fecha_ingreso=?, fecha_antiguedad=?,
                        cargo=?, tipo_empleado=?, sector=?, jefe_admin=?, centro_costo=?
                    WHERE legajo=?
                """, (
                    datos['apellido_nombre'], datos['cuil'], datos['tipo_doc'], datos['nro_doc'],
                    datos['lugar_trabajo'], datos['jornada'], datos['fecha_ingreso'],
                    datos['fecha_antiguedad'], datos['cargo'], datos['tipo_empleado'],
                    datos['sector'], datos['jefe_admin'], datos['centro_costo'], leg
                ))
            else:
                conn.execute("""
                    INSERT INTO empleados (
                        legajo, apellido_nombre, cuil, tipo_doc, nro_doc,
                        lugar_trabajo, jornada, fecha_ingreso, fecha_antiguedad,
                        cargo, tipo_empleado, sector, jefe_admin, centro_costo, estado
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'activo')
                """, (
                    leg, datos['apellido_nombre'], datos['cuil'], datos['tipo_doc'],
                    datos['nro_doc'], datos['lugar_trabajo'], datos['jornada'],
                    datos['fecha_ingreso'], datos['fecha_antiguedad'], datos['cargo'],
                    datos['tipo_empleado'], datos['sector'], datos['jefe_admin'],
                    datos['centro_costo']
                ))
            conn.commit()
        return {'ok': True}
    except sqlite3.IntegrityError:
        return {'ok': False, 'msg': 'El legajo ya existe'}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

def eliminar_empleado(legajo):
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM empleados WHERE legajo=?", (legajo,))
            conn.execute("DELETE FROM empleados_datos_personales WHERE legajo=?", (legajo,))
            conn.execute("DELETE FROM empleados_familiares WHERE legajo=?", (legajo,))
            conn.commit()
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}


# ── MÓDULO 3: ONBOARDING ──────────────────────────────────────────────────────

def get_perfil_empleado(legajo):
    try:
        with get_db() as conn:
            emp = conn.execute("""
                SELECT legajo, apellido_nombre, cuil, cargo, sector,
                       lugar_trabajo, fecha_ingreso
                FROM empleados WHERE legajo=?
            """, (legajo,)).fetchone()
            if not emp:
                return {'ok': False, 'msg': 'Empleado no encontrado'}
            pers = conn.execute(
                "SELECT * FROM empleados_datos_personales WHERE legajo=?", (legajo,)
            ).fetchone()
            fams = conn.execute(
                """SELECT id, parentesco, nombre_familiar, f_nacimiento,
                          tipo_doc, nro_doc, cuil_familiar
                   FROM empleados_familiares WHERE legajo=?""",
                (legajo,)
            ).fetchall()
        return {
            'ok':        True,
            'empleado':  dict(emp),
            'personales': dict(pers) if pers else {},
            'familiares': [dict(f) for f in fams]
        }
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

def guardar_datos_personales(legajo, datos):
    try:
        campos = (
            'sexo', 'calle', 'numero', 'piso', 'dto', 'ciudad', 'localidad',
            'provincia', 'cp', 'telefono', 'f_nacimiento', 'nacionalidad',
            'estado_civil', 'nivel_educacional', 'titulo', 'email'
        )
        vals = tuple(datos.get(c, '') for c in campos)
        with get_db() as conn:
            exists = conn.execute(
                "SELECT 1 FROM empleados_datos_personales WHERE legajo=?", (legajo,)
            ).fetchone()
            if exists:
                sets = ', '.join(f"{c}=?" for c in campos)
                conn.execute(
                    f"UPDATE empleados_datos_personales SET {sets} WHERE legajo=?",
                    vals + (legajo,)
                )
            else:
                cols = ', '.join(campos)
                phs  = ', '.join('?' * len(campos))
                conn.execute(
                    f"INSERT INTO empleados_datos_personales (legajo, {cols}) VALUES (?, {phs})",
                    (legajo,) + vals
                )
            conn.commit()
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

def agregar_familiar(legajo, parentesco, nombre_familiar, f_nacimiento, tipo_doc, nro_doc, cuil_familiar):
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO empleados_familiares
                   (legajo, parentesco, nombre_familiar, f_nacimiento, tipo_doc, nro_doc, cuil_familiar)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (legajo, parentesco, nombre_familiar, f_nacimiento, tipo_doc, nro_doc, cuil_familiar)
            )
            conn.commit()
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

def eliminar_familiar(id):
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM empleados_familiares WHERE id=?", (id,))
            conn.commit()
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}


# ── MÓDULO 5: FICHA DE EMPLEADO ──────────────────────────────────────────────

def get_ficha_empleado(criterio, valor):
    mapeo = {
        'legajo': 'e.legajo',
        'apellido_nombre': 'e.apellido_nombre',
        'cuil': 'e.cuil',
        'nro_doc': 'e.nro_doc'
    }
    col = mapeo.get(criterio)
    if not col:
        return {'ok': False, 'msg': 'Criterio inválido'}
    try:
        with get_db() as conn:
            emp = conn.execute(f"""
                SELECT e.legajo, e.apellido_nombre, e.cuil, e.tipo_doc, e.nro_doc,
                       e.lugar_trabajo, e.jornada, e.fecha_ingreso, e.fecha_antiguedad,
                       e.cargo, e.tipo_empleado, e.sector, e.jefe_admin, e.centro_costo,
                       e.estado, e.fecha_baja, e.motivo_baja,
                       p.sexo, p.f_nacimiento, p.telefono, p.email, p.nacionalidad,
                       p.estado_civil, p.nivel_educacional, p.titulo,
                       p.calle, p.numero, p.piso, p.dto, p.ciudad, p.localidad, p.provincia, p.cp
                FROM empleados e
                LEFT JOIN empleados_datos_personales p ON e.legajo = p.legajo
                WHERE {col} LIKE ?
                LIMIT 1
            """, (f'%{valor}%',)).fetchone()
            if not emp:
                return {'ok': False, 'msg': 'Empleado no encontrado'}
            fams = conn.execute(
                """SELECT parentesco, nombre_familiar, cuil_familiar
                   FROM empleados_familiares WHERE legajo=?""",
                (emp['legajo'],)
            ).fetchall()
        result = dict(emp)
        result['familiares'] = [dict(f) for f in fams]
        return {'ok': True, 'data': result}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}


# ── MÓDULO 6: BAJA DE EMPLEADOS ───────────────────────────────────────────────

def buscar_empleado_para_baja(criterio, valor):
    mapeo = {
        'legajo': 'legajo',
        'apellido_nombre': 'apellido_nombre',
        'cuil': 'cuil',
        'nro_doc': 'nro_doc'
    }
    col = mapeo.get(criterio)
    if not col:
        return {'ok': False, 'msg': 'Criterio inválido'}
    try:
        with get_db() as conn:
            row = conn.execute(
                f"SELECT legajo, apellido_nombre, estado, fecha_baja FROM empleados WHERE {col} LIKE ? LIMIT 1",
                (f'%{valor}%',)
            ).fetchone()
        if not row:
            return {'ok': False, 'msg': 'Empleado no encontrado'}
        return {'ok': True, 'data': dict(row)}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

def registrar_baja(legajo, fecha_baja, motivo_baja, comentario_baja):
    try:
        with get_db() as conn:
            conn.execute("""
                UPDATE empleados
                SET fecha_baja=?, motivo_baja=?, comentario_baja=?, estado='inactivo'
                WHERE legajo=?
            """, (fecha_baja, motivo_baja, comentario_baja, legajo))
            conn.commit()
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}


# ── MÓDULO 4: CONSOLIDADO Y EXPORTAR ─────────────────────────────────────────

def get_consolidado():
    try:
        with get_db() as conn:
            empleados = conn.execute("""
                SELECT legajo, apellido_nombre, cuil, tipo_doc, nro_doc,
                       lugar_trabajo, jornada, fecha_ingreso, fecha_antiguedad,
                       cargo, tipo_empleado, sector, jefe_admin, centro_costo,
                       estado, fecha_baja, motivo_baja
                FROM empleados ORDER BY apellido_nombre
            """).fetchall()
            resultado = []
            for emp in empleados:
                fila = dict(emp)
                leg  = fila['legajo']
                pers = conn.execute("""
                    SELECT sexo, calle, numero, piso, dto, ciudad, localidad,
                           provincia, cp, telefono, f_nacimiento, nacionalidad,
                           estado_civil, nivel_educacional, titulo, email
                    FROM empleados_datos_personales WHERE legajo=?
                """, (leg,)).fetchone()
                vacios = {c: '' for c in [
                    'sexo', 'calle', 'numero', 'piso', 'dto', 'ciudad', 'localidad',
                    'provincia', 'cp', 'telefono', 'f_nacimiento', 'nacionalidad',
                    'estado_civil', 'nivel_educacional', 'titulo', 'email',
                ]}
                fila.update(dict(pers) if pers else vacios)
                fams = conn.execute(
                    "SELECT parentesco, cuil_familiar FROM empleados_familiares WHERE legajo=?",
                    (leg,)
                ).fetchall()
                fila['familiares'] = (
                    ', '.join(f"{f[0]} ({f[1]})" for f in fams) if fams
                    else 'Sin familiares registrados'
                )
                resultado.append(fila)
        return {'ok': True, 'data': resultado}
    except Exception as e:
        return {'ok': False, 'msg': str(e)}

@app.route('/api/exportar_xls')
def exportar_xls():
    consolidado = get_consolidado()
    if not consolidado['ok']:
        return jsonify(consolidado), 500
    data = consolidado['data']
    if not data:
        return jsonify({'ok': False, 'msg': 'No hay datos para exportar'}), 400
    headers = list(data[0].keys())
    lines = ['\t'.join(headers)]
    for fila in data:
        lines.append('\t'.join(str(fila.get(h, '')) for h in headers))
    response = make_response('\n'.join(lines).encode('utf-8-sig'))
    response.headers['Content-Type'] = 'application/vnd.ms-excel'
    response.headers['Content-Disposition'] = 'attachment; filename=nomina_rrhh.xls'
    return response


# ── TABLA DE DISPATCH ─────────────────────────────────────────────────────────

METHODS = {
    'get_sesion':               get_sesion,
    'login_admin':              login_admin,
    'login_empleado':           login_empleado,
    'logout':                   logout,
    'get_parametros':           get_parametros,
    'guardar_parametro':        guardar_parametro,
    'eliminar_parametro':       eliminar_parametro,
    'get_listas_parametros':    get_listas_parametros,
    'get_empleados':            get_empleados,
    'guardar_empleado':         guardar_empleado,
    'eliminar_empleado':        eliminar_empleado,
    'get_perfil_empleado':      get_perfil_empleado,
    'guardar_datos_personales': guardar_datos_personales,
    'agregar_familiar':         agregar_familiar,
    'eliminar_familiar':        eliminar_familiar,
    'get_consolidado':          get_consolidado,
    'get_ficha_empleado':       get_ficha_empleado,
    'buscar_empleado_para_baja': buscar_empleado_para_baja,
    'registrar_baja':           registrar_baja,
}


# ── INIT DB ───────────────────────────────────────────────────────────────────

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS admin_usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE, password TEXT
            );
            CREATE TABLE IF NOT EXISTS cargos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE, nombre TEXT
            );
            CREATE TABLE IF NOT EXISTS sectores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE, nombre TEXT
            );
            CREATE TABLE IF NOT EXISTS centros_costo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE, nombre TEXT
            );
            CREATE TABLE IF NOT EXISTS lugares_trabajo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE, nombre TEXT
            );
            CREATE TABLE IF NOT EXISTS empleados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                legajo TEXT UNIQUE, apellido_nombre TEXT, cuil TEXT,
                tipo_doc TEXT, nro_doc TEXT, lugar_trabajo TEXT, jornada TEXT,
                fecha_ingreso TEXT, fecha_antiguedad TEXT, cargo TEXT,
                tipo_empleado TEXT, sector TEXT, jefe_admin TEXT, centro_costo TEXT,
                estado TEXT DEFAULT 'activo',
                fecha_baja TEXT, motivo_baja TEXT, comentario_baja TEXT
            );
            CREATE TABLE IF NOT EXISTS empleados_datos_personales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                legajo TEXT UNIQUE, sexo TEXT, calle TEXT, numero TEXT,
                piso TEXT, dto TEXT, ciudad TEXT, localidad TEXT, provincia TEXT,
                cp TEXT, telefono TEXT, f_nacimiento TEXT, nacionalidad TEXT,
                estado_civil TEXT, nivel_educacional TEXT, titulo TEXT, email TEXT
            );
            CREATE TABLE IF NOT EXISTS empleados_familiares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                legajo TEXT, parentesco TEXT, nombre_familiar TEXT,
                f_nacimiento TEXT, tipo_doc TEXT, nro_doc TEXT, cuil_familiar TEXT
            );
        """)
        # Migrations for existing databases
        migrations = [
            "ALTER TABLE empleados ADD COLUMN estado TEXT DEFAULT 'activo'",
            "ALTER TABLE empleados ADD COLUMN fecha_baja TEXT",
            "ALTER TABLE empleados ADD COLUMN motivo_baja TEXT",
            "ALTER TABLE empleados ADD COLUMN comentario_baja TEXT",
            "ALTER TABLE empleados_familiares ADD COLUMN nombre_familiar TEXT",
            "ALTER TABLE empleados_familiares ADD COLUMN f_nacimiento TEXT",
            "ALTER TABLE empleados_familiares ADD COLUMN tipo_doc TEXT",
            "ALTER TABLE empleados_familiares ADD COLUMN nro_doc TEXT",
        ]
        for sql in migrations:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass
        conn.execute("UPDATE empleados SET estado='activo' WHERE estado IS NULL")
        conn.commit()
        try:
            conn.execute(
                "INSERT INTO admin_usuarios (usuario, password) VALUES (?, ?)",
                ('admin', 'admin123')
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
