using CSV
using DataFrames
using Dates
using Base.Threads

function clasificar_destino(ciudad)
    """Clasifica destino como local si contiene 'bog' o está vacío, sino nacional"""
    # Convertir a string y limpiar
    ciudad_str = string(ciudad)
    ciudad_lower = lowercase(strip(ciudad_str))

    # Si está vacío o es "missing", clasificar como local
    if isempty(ciudad_lower) || ciudad_lower == "missing"
        return "local"
    end

    # Si contiene "bog", es local
    return occursin("bog", ciudad_lower) ? "local" : "nacional"
end

# --- PROCESO PRINCIPAL ---
function procesar_masivo(ruta_archivo, orden_minima=123273)
    println("=" ^ 70)
    println("PROCESADOR DE ÓRDENES JULIA")
    println("=" ^ 70)
    println("Hilo principal activo: ", threadid(), " de ", nthreads(), " hilos.")
    println("Orden mínima configurada: ", orden_minima)
    println()

    # Leer archivo
    println("📂 Leyendo archivo: ", ruta_archivo)
    df = CSV.read(ruta_archivo, DataFrame;
                  types=String,
                  threaded=true,
                  silencewarnings=true)

    println("✓ Registros iniciales: ", nrow(df))
    println("✓ Columnas encontradas: ", names(df))
    println()

    # Verificar que existan las columnas necesarias
    columnas_requeridas = ["orden", "f_emi", "no_entidad", "ciudad1", "serial"]

    for col in columnas_requeridas
        if !(col in names(df))
            println("❌ ERROR: Falta la columna '$col' en el archivo")
            println("   Columnas disponibles: ", names(df))
            return
        end
    end

    println("✓ Todas las columnas requeridas están presentes")
    println()

    # Filtrado con mejor parsing
    println("🔍 Filtrando registros...")

    # Mostrar ejemplos de órdenes antes de filtrar
    println("📋 Ejemplos de valores en columna 'orden' (primeros 5):")
    for i in 1:min(5, nrow(df))
        println("   [$i] '$(df.orden[i])' (tipo: $(typeof(df.orden[i])))")
    end
    println()

    # Función mejorada para parsear orden
    function parsear_orden(orden_str)
        # Limpiar: quitar espacios, tabs, ceros a la izquierda
        orden_limpia = strip(string(orden_str))
        # Quitar ceros a la izquierda pero mantener al menos un dígito
        orden_limpia = replace(orden_limpia, r"^0+(?=\d)" => "")
        # Intentar parsear
        return tryparse(Int64, orden_limpia)
    end

    # Contadores detallados
    no_parseables = 0
    no_parseables_ejemplos = []
    menores_minimo = 0
    menores_minimo_ejemplos = []

    # Agregar columna con orden parseada
    df[!, :orden_num] = [parsear_orden(o) for o in df.orden]

    # Filtrar usando la columna numérica
    df_filtrado = filter(row -> begin
        if isnothing(row.orden_num)
            no_parseables += 1
            if length(no_parseables_ejemplos) < 5
                push!(no_parseables_ejemplos, row.orden)
            end
            return false
        elseif row.orden_num < orden_minima
            menores_minimo += 1
            if length(menores_minimo_ejemplos) < 5
                push!(menores_minimo_ejemplos, string(row.orden_num))
            end
            return false
        else
            return true
        end
    end, df)

    println("✓ Registros tras filtrado: ", nrow(df_filtrado))
    println()
    println("📊 Estadísticas de filtrado:")
    println("   Total original:           ", nrow(df))
    println("   Aceptados (>= $orden_minima): ", nrow(df_filtrado))
    println("   Rechazados por < $orden_minima: ", menores_minimo)
    println("   Rechazados por no parsear: ", no_parseables)

    if nrow(df_filtrado) > 0
        println()
        println("📋 Ejemplos de órdenes ACEPTADAS (primeras 5):")
        for i in 1:min(5, nrow(df_filtrado))
            println("   [$i] orden_num=$(df_filtrado.orden_num[i]) (original: '$(df_filtrado.orden[i])')")
        end
    end
    println()

    if no_parseables > 0
        println("⚠️  Ejemplos de órdenes que NO se pudieron parsear:")
        for ejemplo in no_parseables_ejemplos
            try
                ejemplo_str = string(ejemplo)
                println("     - '$(ejemplo_str)' (tipo: $(typeof(ejemplo)))")
            catch e
                println("     - [valor no representable] (tipo: $(typeof(ejemplo)))")
            end
        end
        println()
    end

    if menores_minimo > 0 && length(menores_minimo_ejemplos) > 0
        println("ℹ️  Ejemplos de órdenes < $orden_minima (rechazadas):")
        for ejemplo in menores_minimo_ejemplos
            println("     - $(ejemplo)")
        end
        println()
    end

    if nrow(df_filtrado) == 0
        println("❌ ERROR: No hay registros para procesar después del filtrado.")
        println()
        println("   Posibles causas:")
        println("   1. Todas las órdenes son < $orden_minima")
        println("   2. La columna 'orden' no se puede parsear como número")
        println()
        println("   Ajustes sugeridos:")
        println("   - Reduce orden_minima a un valor menor (ej: 0)")
        println("   - Verifica el formato de la columna 'orden'")
        return
    end
    println()

    # Clasificar destinos y agrupar
    println("📊 Clasificando destinos y agrupando por orden...")
    df_filtrado[!, :destino] = map(clasificar_destino, df_filtrado.ciudad1)
    println("✓ Destinos clasificados")

    # Agrupar por orden_num (numérico) y destino, contar items
    println("🔄 Agrupando por orden y destino...")
    df_agrupado = combine(groupby(df_filtrado, [:orden_num, :destino]), nrow => :cantidad)
    println("✓ Agrupación completada: ", nrow(df_agrupado), " registros")

    # Pivotar para tener columnas local y nacional
    println("🔄 Pivotando datos...")
    df_pivot = unstack(df_agrupado, :orden_num, :destino, :cantidad, fill=0)
    println("✓ Pivot completado: ", nrow(df_pivot), " órdenes únicas")

    # Renombrar columnas si existen
    if "local" in names(df_pivot)
        rename!(df_pivot, :local => :cantidad_local)
    else
        df_pivot[!, :cantidad_local] .= 0
    end

    if "nacional" in names(df_pivot)
        rename!(df_pivot, :nacional => :cantidad_nacional)
    else
        df_pivot[!, :cantidad_nacional] .= 0
    end

    # Agregar información adicional (fecha, cliente)
    println("🔄 Extrayendo información de fechas y clientes...")
    df_info = combine(groupby(df_filtrado, :orden_num),
                      :f_emi => first => :fecha_recepcion,
                      :no_entidad => first => :nombre_cliente)
    println("✓ Información extraída: ", nrow(df_info), " órdenes")

    # Merge
    println("🔄 Combinando información...")
    df_final = leftjoin(df_info, df_pivot, on=:orden_num)
    println("✓ Combinación completada")

    # Agregar tipo_servicio (asumiendo sobres por ahora)
    df_final[!, :tipo_servicio] .= "sobre"

    println("✓ Órdenes únicas procesadas: ", nrow(df_final))
    println("✓ Total items locales: ", sum(df_final.cantidad_local))
    println("✓ Total items nacionales: ", sum(df_final.cantidad_nacional))
    println()

    # Preparar DataFrame final para exportar
    println("🔄 Preparando DataFrame para exportar...")
    # Renombrar orden_num a orden para mantener compatibilidad
    df_export = select(df_final,
                       :orden_num => :orden,
                       :fecha_recepcion,
                       :nombre_cliente,
                       :tipo_servicio,
                       :cantidad_local,
                       :cantidad_nacional)
    println("✓ DataFrame preparado: ", nrow(df_export), " registros")

    # Mostrar clientes únicos
    clientes_unicos = unique(df_export.nombre_cliente)
    println("👥 Clientes únicos identificados: ", length(clientes_unicos))
    println()

    # Guardar CSV procesado en carpeta Downloads
    nombre_base = basename(ruta_archivo)
    nombre_salida = replace(nombre_base, r"\.csv$" => "_procesado_julia.csv")
    ruta_salida = "/mnt/c/Users/mcomb/Downloads/" * nombre_salida

    println("💾 Guardando CSV procesado...")
    try
        CSV.write(ruta_salida, df_export)
        println("✓ Archivo guardado: ", ruta_salida)
    catch e
        println("❌ ERROR al guardar CSV:")
        println(e)
        return
    end
    println()

    println("=" ^ 70)
    println("✅ PROCESAMIENTO COMPLETADO CON JULIA")
    println("=" ^ 70)
    println("📊 RESUMEN:")
    println("   Archivo procesado:  ", ruta_archivo)
    println("   Archivo generado:   ", ruta_salida)
    println("   Órdenes procesadas: ", nrow(df_export))
    println("   Clientes únicos:    ", length(clientes_unicos))
    println("   Items locales:      ", sum(df_export.cantidad_local))
    println("   Items nacionales:   ", sum(df_export.cantidad_nacional))
    println()
    println("📋 SIGUIENTE PASO:")
    println("   El sistema ahora cargará automáticamente el archivo procesado.")
    println("   Podrá mapear los nombres de clientes antes de la carga final.")
    println("=" ^ 70)
end

# Ejecutar (esta línea será reemplazada por Python cuando se ejecute desde Streamlit)
procesar_masivo("/mnt/c/Users/mcomb/Desktop/Carvajal/python/basesHisto.csv")