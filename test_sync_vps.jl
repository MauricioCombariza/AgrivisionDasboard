#!/usr/bin/env julia
# test_sync_vps.jl — Diagnóstico y validación del sync VPS
#
# Ejecutar: julia test_sync_vps.jl

const VPS_HOST    = "204.168.150.196"
const VPS_USER    = "root"
const VPS_KEY     = expanduser("~/.ssh/agrivision_vps")
const VPS_DB_USER = "root"
const VPS_DB_PASS = "Root2024!"
const LOCAL_USER  = "root"
const TIMEOUT_SEG = 20

const SSH_ARGS = [
    "ssh", "-i", VPS_KEY,
    "-o", "StrictHostKeyChecking=no",
    "-o", "BatchMode=yes",
    "-q", "-n",
]
const SCP_ARGS = [
    "scp", "-i", VPS_KEY,
    "-o", "StrictHostKeyChecking=no",
    "-q",
]

ssh_cmd(remote::String)  = Cmd([SSH_ARGS; ["$VPS_USER@$VPS_HOST", remote]])
scp_to(src, dst)         = Cmd([SCP_ARGS; [src, "$VPS_USER@$VPS_HOST:$dst"]])
scp_from(src, dst)       = Cmd([SCP_ARGS; ["$VPS_USER@$VPS_HOST:$src", dst]])

# ── Utilidades ────────────────────────────────────────────────────────────────
ok_msg(msg)   = println("    ✅ $msg")
err_msg(msg)  = println("    ❌ $msg")
info_msg(msg) = println("    ℹ️  $msg")
time_msg(t)   = println("    ⏱  $(round(t, digits=2))s")

function con_timeout(cmd; timeout=TIMEOUT_SEG)
    t0 = time()
    try
        proc = run(cmd, wait=false)
        while process_running(proc)
            time() - t0 > timeout && (kill(proc); return -1, timeout, :timeout)
            sleep(0.1)
        end
        code = proc isa Base.ProcessChain ?
            maximum(p.exitcode for p in proc.processes) : proc.exitcode
        return code, time() - t0, :ok
    catch e
        return -1, time() - t0, :error
    end
end

function con_timeout_cap(cmd; timeout=TIMEOUT_SEG)
    out, err_buf = IOBuffer(), IOBuffer()
    t0 = time()
    try
        proc = run(pipeline(cmd; stdout=out, stderr=err_buf), wait=false)
        while process_running(proc)
            time() - t0 > timeout && (kill(proc); return "", "", timeout, :timeout)
            sleep(0.1)
        end
        return String(take!(out)), String(take!(err_buf)), time() - t0, :ok
    catch e
        return "", string(e), time() - t0, :error
    end
end

# ── Cada test es una función — evita los warnings de soft scope de Julia ──────

function test_mysqldump_estructura()
    out, _, elapsed, status = con_timeout_cap(
        `mysqldump -u$LOCAL_USER --no-data --no-tablespaces logistica gestiones_mensajero`
    )
    ok = status == :ok && !isempty(out)
    ok ? ok_msg("mysqldump OK — $(count('\n', out)) líneas") :
         err_msg("Falló (status=$status)")
    time_msg(elapsed)
    return ok
end

function test_mysqldump_completo()
    info_msg("Timeout: $(TIMEOUT_SEG)s")
    out, err_txt, elapsed, status = con_timeout_cap(
        `mysqldump -u$LOCAL_USER --single-transaction --no-tablespaces logistica gestiones_mensajero`
    )
    ok = status == :ok && !isempty(out)
    if ok
        ok_msg("mysqldump completo — $(round(length(out)/1024, digits=1)) KB, $(count('\n', out)) líneas")
    elseif status == :timeout
        err_msg("TIMEOUT — posible lock en tabla (revisar SHOW PROCESSLIST)")
    else
        err_msg("Falló: $(first(err_txt, 200))")
    end
    time_msg(elapsed)
    return ok
end

function test_ssh_echo()
    out, _, elapsed, status = con_timeout_cap(ssh_cmd("echo OK"); timeout=15)
    ok = status == :ok && strip(out) == "OK"
    ok ? ok_msg("SSH conecta correctamente") :
         err_msg("Falló (status=$status, out='$(strip(out))')")
    time_msg(elapsed)
    return ok
end

function test_ssh_mysql_ping()
    out, err_txt, elapsed, status = con_timeout_cap(
        ssh_cmd("MYSQL_PWD='$VPS_DB_PASS' mysql -u$VPS_DB_USER -e 'SELECT 1' logistica");
        timeout=15,
    )
    ok = status == :ok
    if ok
        ok_msg("mysql en VPS responde OK")
    else
        err_msg("Falló (status=$status)")
        isempty(err_txt) || println("    stderr: $(first(err_txt, 300))")
    end
    time_msg(elapsed)
    return ok
end

function test_pipeline_echo()
    info_msg("Timeout: $(TIMEOUT_SEG)s — valida que EOF del pipe llega a mysql")
    cmd_echo = `echo "SELECT 'pipeline_ok' AS test;"`
    cmd_ssh  = ssh_cmd("MYSQL_PWD='$VPS_DB_PASS' mysql -u$VPS_DB_USER logistica")
    code, elapsed, status = con_timeout(pipeline(cmd_echo, cmd_ssh))
    ok = status == :ok && code == 0
    if ok
        ok_msg("Pipeline echo→ssh→mysql OK (EOF propagado correctamente)")
    elseif status == :timeout
        err_msg("TIMEOUT — EOF del pipe no llega al mysql remoto")
    else
        err_msg("Falló (code=$code, status=$status)")
    end
    time_msg(elapsed)
    return ok
end

function test_pipeline_grande()
    info_msg("Timeout: $(TIMEOUT_SEG)s — si cuelga, confirma deadlock de buffer SSH")
    dump_cmd = `mysqldump -u$LOCAL_USER --single-transaction --no-tablespaces logistica gestiones_mensajero`
    ssh      = ssh_cmd("MYSQL_PWD='$VPS_DB_PASS' mysql -u$VPS_DB_USER logistica")
    code, elapsed, status = con_timeout(pipeline(dump_cmd, ssh))
    ok = status == :ok && code == 0
    if ok
        ok_msg("Pipeline mysqldump→ssh→mysql OK")
    elseif status == :timeout
        err_msg("TIMEOUT — deadlock confirmado con datos grandes")
        err_msg("→ Solución: dump→scp→ssh mysql < archivo (implementada en sync_vps.jl)")
    else
        err_msg("Falló (code=$code) — esperado con -n en SSH_ARGS")
    end
    time_msg(elapsed)
    return ok
end

function test_validar_subir()
    info_msg("Estrategia actual: mysqldump --skip-lock-tables → scp → ssh mysql < archivo")
    sql_local   = tempname() * ".sql"
    remote_path = "/tmp/test_sync_julia.sql"
    t0 = time()
    ok = false
    try
        print("    [1/3] mysqldump local (--skip-lock-tables)... ")
        run(pipeline(
            `mysqldump -u$LOCAL_USER --single-transaction --no-tablespaces --skip-lock-tables logistica gestiones_mensajero`;
            stdout=sql_local, stderr=devnull,
        ))
        println("OK ($(round(filesize(sql_local)/1024, digits=1)) KB)")

        print("    [2/3] scp → VPS... ")
        run(scp_to(sql_local, remote_path))
        println("OK")

        print("    [3/3] mysql import en VPS (timeout 90s)... ")
        import_sql = "timeout 90 bash -c \"MYSQL_PWD='$VPS_DB_PASS' mysql -u$VPS_DB_USER logistica < $remote_path\" && rm -f $remote_path"
        code, elapsed, status = con_timeout(ssh_cmd(import_sql); timeout=100)
        if status == :ok && code == 0
            println("OK ($(round(elapsed, digits=1))s)")
            ok = true
            ok_msg("Estrategia subir EXITOSA en $(round(time()-t0, digits=1))s total")
        elseif code == 124
            println("FALLÓ"); err_msg("timeout 90s en mysql remoto — lock en VPS")
        else
            println("FALLÓ (code=$code, status=$status)")
        end
    catch e
        println("FALLÓ"); err_msg("$e")
    finally
        isfile(sql_local) && rm(sql_local; force=true)
    end
    time_msg(time() - t0)
    return ok
end

function test_validar_bajar()
    info_msg("Estrategia: ssh mysqldump → scp → mysql local (logistica.personal)")
    remote_path = "/tmp/test_dl_julia.sql"
    sql_local   = tempname() * ".sql"
    t0 = time()
    ok = false
    try
        print("    [1/3] mysqldump en VPS... ")
        run(ssh_cmd("MYSQL_PWD='$VPS_DB_PASS' mysqldump -u$VPS_DB_USER --single-transaction --no-tablespaces logistica personal > $remote_path"))
        println("OK")

        print("    [2/3] scp ← VPS... ")
        run(scp_from(remote_path, sql_local))
        println("OK ($(round(filesize(sql_local)/1024, digits=1)) KB)")

        print("    [3/3] mysql import local... ")
        run(pipeline(`mysql -u$LOCAL_USER logistica`; stdin=sql_local, stderr=devnull))
        run(ssh_cmd("rm -f $remote_path"))
        println("OK")

        ok = true
        ok_msg("Estrategia bajar EXITOSA en $(round(time()-t0, digits=1))s")
    catch e
        println("FALLÓ"); err_msg("$e")
    finally
        isfile(sql_local) && rm(sql_local; force=true)
    end
    time_msg(time() - t0)
    return ok
end

# ── Runner ────────────────────────────────────────────────────────────────────
const TESTS = [
    ("mysqldump --no-data",                    test_mysqldump_estructura),
    ("mysqldump completo",                     test_mysqldump_completo),
    ("SSH echo",                               test_ssh_echo),
    ("SSH mysql SELECT 1",                     test_ssh_mysql_ping),
    ("Pipeline echo→ssh (datos pequeños)",     test_pipeline_echo),
    ("Pipeline mysqldump→ssh (datos grandes)", test_pipeline_grande),
    ("VALIDACIÓN subir  (dump→scp→ssh)",       test_validar_subir),
    ("VALIDACIÓN bajar  (ssh→scp→mysql)",      test_validar_bajar),
]

resultados = Bool[]

for (i, (label, fn)) in enumerate(TESTS)
    println("\n[$i] $label")
    println("    " * "─"^46)
    push!(resultados, fn())
end

println("\n" * "="^50)
println(" RESUMEN")
println("="^50)
for (i, (label, _)) in enumerate(TESTS)
    icon = resultados[i] ? "✅" : "❌"
    println("  $icon [$i] $label")
end
println()
