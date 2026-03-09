#!/usr/bin/env julia

println("=" ^ 70)
println(" Instalador de Paquetes Julia - Sistema de Logística")
println("=" ^ 70)
println()

using Pkg

# Lista de paquetes necesarios
paquetes = ["CSV", "DataFrames", "MySQL", "Tables", "Dates"]

println("📦 Paquetes requeridos para Procesador_Ordenes.jl:")
for pkg in paquetes
    println("   - $pkg")
end
println()

println("🔧 Iniciando instalación...")
println()

errores = []
for (i, pkg) in enumerate(paquetes)
    println("[$i/$(length(paquetes))] Instalando $pkg...")
    try
        Pkg.add(pkg)
        println("   ✅ $pkg instalado correctamente")
    catch e
        println("   ❌ Error instalando $pkg")
        push!(errores, (pkg, e))
    end
    println()
end

println("=" ^ 70)
println(" Verificando instalación...")
println("=" ^ 70)
println()

todo_ok = true
for pkg in paquetes
    try
        eval(Meta.parse("using $pkg"))
        println("✅ $pkg - Cargado correctamente")
    catch e
        println("❌ $pkg - Error al cargar")
        todo_ok = false
    end
end

println()
println("=" ^ 70)

if todo_ok && isempty(errores)
    println(" ✅ Instalación completada exitosamente")
    println("=" ^ 70)
    println()
    println("💡 Próximos pasos:")
    println("   1. Inicia el sistema: ./iniciar_home.sh")
    println("   2. Ve a 'Procesador de Órdenes'")
    println("   3. Selecciona 'Julia (Alto Rendimiento)'")
    println("   4. ¡Procesa tus archivos 2-10x más rápido!")
else
    println(" ⚠️ Instalación completada con errores")
    println("=" ^ 70)
    println()
    if !isempty(errores)
        println("Paquetes con errores:")
        for (pkg, err) in errores
            println("   - $pkg: $err")
        end
        println()
    end
    println("💡 Intenta instalar manualmente:")
    println("   julia> using Pkg")
    for (pkg, _) in errores
        println("   julia> Pkg.add(\"$pkg\")")
    end
end

println()
