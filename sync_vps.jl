#!/usr/bin/env julia
# sync_vps.jl — Sincroniza tablas MySQL locales → VPS (y baja personal del VPS)
#
# Note 1: La linea shebang (#!/usr/bin/env julia) permite ejecutar el script
# directamente como "./sync_vps.jl" en sistemas Unix sin escribir "julia" cada vez.
# `env julia` busca el ejecutable de Julia en el PATH del sistema, lo que hace
# el script mas portable que poner la ruta absoluta (ej. /usr/local/bin/julia).
#
# Uso:
#   julia sync_vps.jl            → sube TABLAS_SYNC y baja TABLAS_BAJAR
#   julia sync_vps.jl subir      → solo sube
#   julia sync_vps.jl bajar      → solo baja
#   julia sync_vps.jl verificar  → verifica conexion SSH al VPS
#
# Estrategia: dump local → scp → ssh mysql < archivo
# (El pipeline directo | ssh mysql cuelga porque SSH no reenvía EOF del pipe)

# ── Configuracion ─────────────────────────────────────────────────────────────
# Note 2: `const` en Julia declara una constante global. A diferencia de otros
# lenguajes, Julia permite reasignar `const` con una advertencia, pero su valor
# no puede cambiar de tipo. Usar `const` para configuracion ayuda al compilador
# a optimizar el codigo al saber que el tipo no cambiara en tiempo de ejecucion.
const VPS_HOST    = "204.168.150.196"
const VPS_USER    = "root"
# Note 3: `expanduser` convierte "~" al directorio home real del usuario actual.
# En WSL (Windows Subsystem for Linux) esto suele ser /home/<usuario>.
# Es equivalente a os.path.expanduser("~") en Python.
const VPS_KEY     = expanduser("~/.ssh/agrivision_vps")
const VPS_DB_USER = "root"
const VPS_DB_PASS = "Root2024!"
const LOCAL_USER  = "root"
const LOCAL_PASS  = "Vale2010"

# Note 4: TABLAS_SYNC es un Array de Tuplas. Cada tupla tiene 3 elementos:
# (nombre_bd, nombre_tabla, columna_de_proteccion).
# En Julia, `nothing` es el valor singleton del tipo `Nothing`, equivalente
# a `None` en Python o `null` en otros lenguajes. Se usa aqui para indicar
# que esa tabla no necesita proteccion de filas editadas manualmente.
const TABLAS_SYNC = [
    ("imile",     "paquetes",            nothing),
    ("logistica", "gestiones_mensajero", "editado_manualmente"),
    ("logistica", "ordenes",             nothing),
    ("logistica", "personal",            nothing),
]

# personal se sube (no se baja) para preservar columnas precio_local/precio_nacional
const TABLAS_BAJAR = Vector{Tuple{String,String}}()

# Note 5: SSH_ARGS es un Vector de Strings que representa los argumentos comunes
# para todos los comandos SSH. Factorizarlos aqui evita repeticion y hace que
# cambiar opciones SSH (ej. agregar -o ConnectTimeout=5) afecte todo el script.
# "-o StrictHostKeyChecking=no" no verifica la huella del servidor (util en CI).
# "-o BatchMode=yes" hace que SSH falle en vez de pedir contrasena interactiva.
# "-q" suprime mensajes de diagnostico del cliente SSH.
const SSH_ARGS = [
    "ssh", "-i", VPS_KEY,
    "-o", "StrictHostKeyChecking=no",
    "-o", "BatchMode=yes",
    "-q",
    "-n",   # stdin = /dev/null — SSH no espera cierre de terminal al final del comando
]

const SCP_ARGS = [
    "scp", "-i", VPS_KEY,
    "-o", "StrictHostKeyChecking=no",
    "-q",
]

# ── Helpers ───────────────────────────────────────────────────────────────────
# Note 6: `Cmd` es el tipo de Julia para representar comandos externos.
# Se construye con `Cmd(vector_de_strings)`. El operador `;` concatena vectores
# de forma no destructiva. La interpolacion `"$var"` dentro del vector es Julia
# (no bash), por lo que VPS_USER y VPS_HOST se sustituyen al crear el Cmd.
ssh_cmd(remote::String) = Cmd([SSH_ARGS; ["$VPS_USER@$VPS_HOST", remote]])
scp_to_vps(local_path::String, remote_path::String) =
    Cmd([SCP_ARGS; [local_path, "$VPS_USER@$VPS_HOST:$remote_path"]])
scp_from_vps(remote_path::String, local_path::String) =
    Cmd([SCP_ARGS; ["$VPS_USER@$VPS_HOST:$remote_path", local_path]])

# ── Verificar conexion ────────────────────────────────────────────────────────
# Note 7: El tipo de retorno `::Bool` es una anotacion opcional en Julia.
# No cambia la semantica del programa pero documenta el contrato de la funcion
# y permite al compilador emitir mejores errores si el retorno no concuerda.
function verificar_conexion()::Bool
    println("Verificando conexion SSH al VPS...")
    # Note 8: `IOBuffer()` crea un buffer en memoria que funciona como un IO stream.
    # Lo usamos para capturar stdout del comando SSH en vez de imprimirlo directamente.
    out = IOBuffer()
    try
        # Note 9: `pipeline()` conecta la entrada/salida de un comando a streams de Julia.
        # `stdout=out` redirige la salida del proceso al IOBuffer.
        # `stderr=devnull` descarta los errores (equivalente a "2>/dev/null" en bash).
        run(pipeline(ssh_cmd("echo OK"); stdout=out, stderr=devnull))
        # Note 10: `take!(out)` extrae los bytes del IOBuffer (vaciandolo).
        # `String(...)` convierte bytes a texto. `strip()` elimina espacios y \n del borde.
        ok = strip(String(take!(out))) == "OK"
        ok ? println("  Conexion exitosa a $VPS_HOST") :
             println("  Respuesta inesperada del VPS")
        return ok
    catch e
        println("  No se pudo conectar: $e")
        return false
    end
end

# ── Subir tabla local → VPS ────────────────────────────────────────────────────
# Estrategia: REPLACE INTO directo (sin DDL → sin metadata locks).
#
# protect_col: columna flag en el VPS que marca filas editadas manualmente.
#   Si se especifica, el script en VPS guarda esas filas en una tabla temporal
#   antes del import y las restaura después, preservando los ajustes manuales.
#   Las filas nuevas (solo en local) se importan normalmente.
# Note 11: `Union{String,Nothing}` es el tipo union de Julia. Significa que
# protect_col puede ser un String O el valor nothing. Es el patron estandar
# para argumentos opcionales con semantica nula (equivalente a Optional[str] en Python).
# El valor por defecto `=nothing` hace que el tercer argumento sea opcional.
function sincronizar_tabla(db::String, tabla::String, protect_col::Union{String,Nothing}=nothing)::Bool
    println("  +- $db.$tabla")
    t0 = time()
    # Note 12: `tempname()` genera una ruta unica en el directorio temporal del sistema
    # (/tmp en Linux). No crea el archivo; solo devuelve la ruta. Concatenamos la
    # extension manualmente. Esto es util para archivos intermedios que solo existen
    # durante la ejecucion del script.
    sql_local  = tempname() * ".sql"
    sh_local   = tempname() * ".sh"
    remote_sql = "/tmp/sync_$(db)_$(tabla).sql"
    remote_sh  = "/tmp/sync_$(db)_$(tabla).sh"
    prot_tabla = "$(tabla)_sync_prot"

    try
        # 1. Dump local — solo datos, sin DROP/CREATE
        print("  |  [1/4] mysqldump local... ")
        # Note 13: Los backticks `` `comando` `` en Julia crean un objeto Cmd sin ejecutarlo.
        # La interpolacion dentro de backticks (ej. $LOCAL_USER) es interpolacion Julia,
        # no sustitucion de comandos bash. Esto es seguro contra inyeccion de comandos
        # porque cada token se pasa como argumento separado al SO (no pasa por /bin/sh).
        run(pipeline(
            `mysqldump -u$LOCAL_USER -p$LOCAL_PASS --single-transaction --no-tablespaces
             --no-create-info --replace --skip-add-locks $db $tabla`;
            stdout=sql_local, stderr=devnull,
        ))
        sz = round(filesize(sql_local) / 1024, digits=1)
        println("OK ($(sz) KB, $(round(time()-t0, digits=2))s)")

        # 2. Generar script bash para el VPS
        print("  |  [2/4] preparando script... ")

        # Note 14: Las cadenas triple-comilla `"""..."""` en Julia son strings multilínea
        # con interpolacion. `$variable` se sustituye por su valor (interpolacion Julia).
        # Para incluir un signo `$` literal en el string (que el bash luego interprete),
        # se debe escapar como `\$`. Esto es crucial: `$prot_tabla` → nombre real de tabla,
        # `\$PROT_COUNT` → variable bash `$PROT_COUNT` que se evaluara en el VPS.
        #
        # Note 15: El heredoc bash `<< 'EOSQL_BEFORE'` (marcador entre comillas simples)
        # hace que bash NO interprete nada dentro del bloque: ni variables ($), ni
        # backticks (`). Esto evita el bug clasico donde los identificadores MySQL
        # entre backticks (ej. `mi_tabla`) son interpretados como comandos bash.
        # Como Julia ya sustituyo los nombres de tabla, el heredoc recibe texto plano.
        prot_before = isnothing(protect_col) ? "" : """
# Guardar filas editadas manualmente en el VPS (no deben ser sobreescritas)
mysql -u$VPS_DB_USER $db << 'EOSQL_BEFORE'
  DROP TABLE IF EXISTS $prot_tabla;
  CREATE TABLE $prot_tabla LIKE $tabla;
  INSERT INTO $prot_tabla SELECT * FROM $tabla WHERE $protect_col = 1;
EOSQL_BEFORE
PROT_COUNT=\$(mysql -u$VPS_DB_USER $db -sN -e 'SELECT COUNT(*) FROM $prot_tabla;')
echo "  -> \$PROT_COUNT fila(s) protegida(s) guardadas"
"""

        # Note 16: Las comillas simples en bash (`-e 'SELECT ...'`) evitan que bash
        # interprete caracteres especiales como $, `, \. Aqui es seguro porque
        # los nombres de tabla ya fueron sustituidos por Julia (son texto plano).
        # Si se usaran comillas dobles (`-e "SELECT ..."`), bash intentaria expandir
        # $prot_tabla como una variable bash → resultado vacio → error SQL.
        prot_after = isnothing(protect_col) ? "" : """
# Restaurar filas protegidas (sobreescriben lo que trajo el sync para esas filas)
RESTORED=\$(mysql -u$VPS_DB_USER $db -sN -e 'SELECT COUNT(*) FROM $prot_tabla;')
if [ "\$RESTORED" -gt "0" ]; then
  mysql -u$VPS_DB_USER $db << 'EOSQL_AFTER'
    REPLACE INTO $tabla SELECT * FROM $prot_tabla;
    DROP TABLE $prot_tabla;
EOSQL_AFTER
  echo "  -> \$RESTORED fila(s) protegida(s) restauradas"
else
  mysql -u$VPS_DB_USER $db -e 'DROP TABLE IF EXISTS $prot_tabla;'
fi
"""

        # Note 17: `set -e` al inicio del script bash hace que el script termine
        # inmediatamente si cualquier comando devuelve un codigo de salida distinto de 0.
        # `export MYSQL_PWD=` es la forma segura de pasar la contrasena a mysql/mysqldump:
        # evita que aparezca en la lista de procesos (ps aux) a diferencia de -pContrasena.
        script = """
set -e
export MYSQL_PWD='$VPS_DB_PASS'

$prot_before
mysql -u$VPS_DB_USER $db < $remote_sql
$prot_after
rm -f $remote_sql $remote_sh
"""
        write(sh_local, script)
        # Note 18: `isnothing(x)` es la forma idiomatica de Julia para comprobar si
        # un valor es `nothing`. Equivale a `x is None` en Python o `x == null`.
        println("OK$(isnothing(protect_col) ? "" : " (con proteccion de filas editadas)")")

        # 3. Subir SQL y script al VPS
        print("  |  [3/4] scp → VPS... ")
        run(scp_to_vps(sql_local, remote_sql))
        run(scp_to_vps(sh_local, remote_sh))
        println("OK ($(round(time()-t0, digits=2))s)")

        # 4. Ejecutar script en VPS
        # Note 19: `bash script.sh` es mas robusto que `sh script.sh` porque garantiza
        # que se usa Bash (que soporta `[[ ]]`, arrays, heredocs avanzados, etc.).
        # El script se ejecuta en el VPS via SSH. Si devuelve exit code != 0,
        # Julia lanza una excepcion `ProcessFailedException` que cae en el `catch`.
        print("  |  [4/4] import en VPS... ")
        run(ssh_cmd("bash $remote_sh"))
        println("OK ($(round(time()-t0, digits=2))s)")

        println("  +- OK $db.$tabla sincronizada en $(round(time()-t0, digits=1))s")
        return true

    catch e
        println("FALLO")
        println("  +- ERROR $db.$tabla: $e")
        return false
    finally
        # Note 20: El bloque `finally` se ejecuta SIEMPRE, haya excepcion o no.
        # Es el lugar correcto para liberar recursos (cerrar archivos, borrar temporales).
        # `isfile(path) && rm(path)` es el patron idiomatico: solo borra si existe.
        # `force=true` equivale a `rm -f`: no lanza error si el archivo no existe.
        isfile(sql_local) && rm(sql_local; force=true)
        isfile(sh_local)  && rm(sh_local;  force=true)
    end
end

# ── Bajar tabla del VPS → local ───────────────────────────────────────────────
# Pasos: ssh mysqldump → temp remoto → scp → mysql local → rm remoto
function descargar_tabla(db::String, tabla::String)::Bool
    println("  +- $db.$tabla")
    t0 = time()
    remote_path = "/tmp/sync_dl_$(db)_$(tabla).sql"
    sql_local   = tempname() * ".sql"

    try
        # 1. Dump en VPS a archivo remoto temporal
        # Note 21: La contrasena se pasa via variable de entorno MYSQL_PWD en el mismo
        # comando SSH. Esto funciona porque el shell del VPS expande la asignacion antes
        # de ejecutar mysqldump. La alternativa --password=X expone la contrasena en
        # `ps aux`, lo cual es un riesgo de seguridad en servidores compartidos.
        print("  |  [1/3] mysqldump en VPS... ")
        dump_cmd = "MYSQL_PWD='$VPS_DB_PASS' mysqldump -u$VPS_DB_USER --single-transaction --no-tablespaces $db $tabla > $remote_path"
        run(ssh_cmd(dump_cmd))
        println("OK ($(round(time()-t0, digits=2))s)")

        # 2. Bajar via SCP
        print("  |  [2/3] scp <- VPS... ")
        run(scp_from_vps(remote_path, sql_local))
        sz = round(filesize(sql_local) / 1024, digits=1)
        println("OK ($(sz) KB, $(round(time()-t0, digits=2))s)")

        # 3. Importar local y borrar remoto
        # Note 22: `pipeline(cmd; stdin=archivo)` redirige el contenido del archivo
        # como entrada estandar del comando. Es equivalente a `mysql < archivo.sql` en bash.
        # `stderr=devnull` suprime los warnings de MySQL (ej. "Using password on command line").
        print("  |  [3/3] mysql import local... ")
        run(pipeline(
            `mysql -u$LOCAL_USER -p$LOCAL_PASS $db`;
            stdin=sql_local, stderr=devnull,
        ))
        run(ssh_cmd("rm -f $remote_path"))
        println("OK ($(round(time()-t0, digits=2))s)")

        println("  +- OK $db.$tabla descargada en $(round(time()-t0, digits=1))s")
        return true

    catch e
        println("FALLO")
        println("  +- ERROR $db.$tabla: $e")
        return false
    finally
        isfile(sql_local) && rm(sql_local; force=true)
    end
end

# ── Subir todas ───────────────────────────────────────────────────────────────
function subir_todas()::Bool
    println("\nSubiendo $(length(TABLAS_SYNC)) tablas...\n")
    t0 = time()
    # Note 23: Esta es una comprension de array (array comprehension) en Julia.
    # Itera sobre TABLAS_SYNC, desempaqueta cada tupla en (db, t, pc) mediante
    # desestructuracion, y llama sincronizar_tabla para cada una.
    # El resultado es un Vector{Bool} con true/false por cada tabla.
    # Las tablas se procesan en orden secuencial (no en paralelo) para evitar
    # condiciones de carrera en el VPS si comparten recursos.
    resultados = [sincronizar_tabla(db, t, pc) for (db, t, pc) in TABLAS_SYNC]
    # Note 24: `count(v)` sobre un Vector{Bool} cuenta los elementos `true`.
    ok  = count(resultados)
    mal = length(resultados) - ok
    println()
    if mal == 0
        println("OK Sincronizacion completa — $ok tablas ($(round(time()-t0, digits=1))s total)")
    else
        println("WARN Sincronizacion con errores — $ok ok, $mal fallidas")
    end
    return mal == 0
end

# ── Bajar tablas del VPS ──────────────────────────────────────────────────────
function bajar_todas()::Bool
    println("\nDescargando $(length(TABLAS_BAJAR)) tablas del VPS...\n")
    t0 = time()
    resultados = [descargar_tabla(db, t) for (db, t) in TABLAS_BAJAR]
    # Note 25: `all(v)` devuelve true solo si todos los elementos de v son true.
    # Es equivalente a `all(resultados)` en Python. Usar `all` es mas expresivo
    # que contar: comunica la intencion de "necesitamos exito total".
    ok = all(resultados)
    println()
    ok ? println("OK Descarga completa ($(round(time()-t0, digits=1))s)") :
         println("WARN Descarga con errores")
    return ok
end

# ── Main ──────────────────────────────────────────────────────────────────────
# Note 26: Definir `main()` como funcion (en vez de codigo suelto al nivel del modulo)
# es una buena practica en Julia: el codigo dentro de funciones es compilado JIT
# (Just-In-Time) y corre mucho mas rapido que el codigo a nivel global.
function main()::Int
    # Note 27: `ARGS` es la constante global de Julia que contiene los argumentos
    # de linea de comandos como un Vector{String}. Es equivalente a sys.argv[1:]
    # en Python (sin el nombre del script). `length(ARGS) > 0` comprueba si se
    # paso al menos un argumento antes de intentar acceder a ARGS[1].
    modo = length(ARGS) > 0 ? ARGS[1] : "todo"

    println("=" ^ 50)
    println(" Sincronizador VPS — Julia $VERSION")
    println("=" ^ 50)

    # Note 28: Esta es una expresion `if/elseif/else` usada como valor (no como
    # sentencia). En Julia, casi todo es una expresion que devuelve un valor,
    # incluyendo los bloques if. El resultado se asigna a `ok`. Esto es mas
    # conciso que declarar `ok` antes y asignarlo dentro de cada rama.
    ok = if modo == "verificar"
        verificar_conexion()
    elseif modo == "subir"
        subir_todas()
    elseif modo == "bajar"
        bajar_todas()
    else
        a = subir_todas()
        b = bajar_todas()
        a && b
    end

    println("=" ^ 50)
    # Note 29: El patron convencional en scripts Unix es retornar 0 para exito
    # y un valor distinto de 0 para error. Los shells y CI/CD (GitHub Actions,
    # etc.) usan este codigo de salida para determinar si el script tuvo exito.
    return ok ? 0 : 1
end

# Note 30: `exit(main())` es el punto de entrada del script. Llamar `main()`
# como funcion garantiza que el compilador JIT de Julia optimice todo el codigo
# dentro de ella. El resultado de `main()` (0 o 1) se pasa a `exit()` para que
# el proceso reporte el estado correcto al sistema operativo.
exit(main())
