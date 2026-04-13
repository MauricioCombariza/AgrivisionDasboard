/**
 * wa_service/server.js
 * ====================
 * API Express que envuelve whatsapp-web.js.
 * Escucha SOLO en localhost:3000 (no expuesto a internet).
 * Streamlit lo llama internamente para enviar mensajes.
 *
 * Endpoints:
 *   GET  /status  → estado de la sesión (ready, has_qr, error)
 *   GET  /qr      → QR como imagen base64 para mostrar en Streamlit
 *   POST /send    → enviar mensaje  { phone, message }
 *   POST /restart → reiniciar sesión (nuevo QR)
 */

const express = require("express");
const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode");

const app = express();
app.use(express.json({ limit: "10mb" }));

// ── Estado global de la sesión ─────────────────────────────────────────────
let qrData    = null;   // string del QR actual (null cuando ya está autenticado)
let isReady   = false;  // true cuando WhatsApp está conectado y listo
let initError = null;   // string con error si falló la inicialización

// ── Cliente WhatsApp ────────────────────────────────────────────────────────
// LocalAuth guarda la sesión en disco para no pedir QR en cada reinicio.
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: "/opt/carvajal/wa_service/.wwebjs_auth",
    }),
    puppeteer: {
        headless: true,
        // Flags necesarios para correr Chromium como root en Linux sin sandbox.
        args: [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--disable-gpu",
        ],
    },
});

// Evento: se generó un QR → guardar para que Streamlit lo muestre
client.on("qr", (qr) => {
    qrData  = qr;
    isReady = false;
    console.log("📱 QR generado — escanea con WhatsApp en tu teléfono");
});

// Evento: sesión autenticada y lista para enviar mensajes
client.on("ready", () => {
    isReady   = true;
    qrData    = null;
    initError = null;
    console.log("✅ WhatsApp conectado y listo para enviar mensajes");
});

// Evento: sesión desconectada (ej. teléfono sin internet o logout remoto)
client.on("disconnected", (reason) => {
    isReady = false;
    console.log("❌ WhatsApp desconectado:", reason);
});

// Evento: fallo de autenticación
client.on("auth_failure", (msg) => {
    initError = msg;
    isReady   = false;
    qrData    = null;
    console.error("❌ Error de autenticación:", msg);
});

// Arrancar el cliente al iniciar el servidor
client.initialize().catch((err) => {
    initError = err.message;
    console.error("❌ Error al inicializar WhatsApp:", err.message);
});

// ── GET /status ─────────────────────────────────────────────────────────────
// Retorna el estado actual de la sesión.
// Streamlit lo llama para mostrar badge de conexión.
app.get("/status", (req, res) => {
    res.json({
        ready:   isReady,
        has_qr:  !!qrData,
        error:   initError,
    });
});

// ── GET /qr ─────────────────────────────────────────────────────────────────
// Retorna el QR como imagen base64 (data URL) para mostrar en Streamlit.
// Si ya está autenticado retorna { status: "ready" }.
app.get("/qr", async (req, res) => {
    if (isReady) {
        return res.json({ status: "ready" });
    }
    if (initError) {
        return res.json({ status: "error", error: initError });
    }
    if (qrData) {
        try {
            // Convertir el string QR a imagen PNG en base64
            const qrImage = await qrcode.toDataURL(qrData);
            return res.json({ status: "qr", qr: qrImage });
        } catch (e) {
            return res.status(500).json({ status: "error", error: e.message });
        }
    }
    // Aún iniciando (Puppeteer cargando)
    return res.json({ status: "loading" });
});

// ── POST /send ──────────────────────────────────────────────────────────────
// Body: { "phone": "+573001234567", "message": "Hola..." }
// Envía el mensaje de texto al número indicado.
app.post("/send", async (req, res) => {
    if (!isReady) {
        return res.status(503).json({ error: "WhatsApp no está listo. Escanea el QR primero." });
    }

    const { phone, message } = req.body;
    if (!phone || !message) {
        return res.status(400).json({ error: "Faltan parámetros: phone y message son requeridos." });
    }

    try {
        // Formato chatId: solo dígitos + @c.us  (ej. 573001234567@c.us)
        const chatId = phone.replace(/\D/g, "") + "@c.us";
        const msg = await client.sendMessage(chatId, message);
        console.log(`✅ Mensaje enviado a ${phone} — ID: ${msg.id._serialized}`);
        res.json({ status: "ok", messageId: msg.id._serialized });
    } catch (e) {
        console.error(`❌ Error enviando a ${phone}:`, e.message);
        res.status(500).json({ error: e.message });
    }
});

// ── POST /restart ───────────────────────────────────────────────────────────
// Destruye la sesión actual y reinicia (genera nuevo QR).
// Útil si la sesión quedó corrupta.
app.post("/restart", async (req, res) => {
    try {
        console.log("🔄 Reiniciando sesión WhatsApp…");
        await client.destroy();
        isReady   = false;
        qrData    = null;
        initError = null;
        // Pequeña pausa antes de reiniciar para que el proceso limpie
        setTimeout(() => client.initialize().catch(console.error), 2000);
        res.json({ status: "restarting" });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

// ── Arrancar servidor ───────────────────────────────────────────────────────
// Solo escucha en localhost: Streamlit lo llama internamente,
// nunca está expuesto a internet directamente.
const PORT = process.env.WA_PORT || 3000;
app.listen(PORT, "127.0.0.1", () => {
    console.log(`🚀 WhatsApp API escuchando en http://127.0.0.1:${PORT}`);
});
