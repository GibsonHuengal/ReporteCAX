/* ============================================================
   static/js/app.js  ·  v3  (EcoEco / BarrioVivo adaptado)
   - Mapa con markers coloreados por gravedad + Marker Clustering
   - Mapa de Calor (heatmap) de puntos críticos (leaflet.heat)
   - Geofencing: dibuja radio de "mi zona" y filtra reportes cercanos
   - Formulario con captura de cámara + IA local (/api/classify)
   - Geolocalización con la API del navegador (equivalente FusedLocation)
   - Votos comunitarios (upvotes) y estados
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    initCenterPinSync();
    initSeverityButtons();
    initForm();
    initMapTools();

    loadReports();
    loadHeatmap();

    // Refresco automático cada 30s (sensación de tiempo real)
    setInterval(() => { loadReports(); loadHeatmap(); }, 30000);
});

/* ============================================================
   MAPA + CAPAS
   ============================================================ */
let map = null;
let clusterLayer = null;   // agrupación de marcadores
let plainLayer = null;     // marcadores sueltos
let heatLayer = null;      // mapa de calor
let geoCircle = null;      // círculo de geofencing
let clusterEnabled = true;
let heatEnabled = false;

const markersById = new Map();       // id → { marker, report }
const allReports = [];               // último listado recibido

const SEVERITY_COLORS = {
    bajo:       "#10b981",
    intermedio: "#f59e0b",
    critico:    "#ef4444",
};
const GROUP_ICON = {
    BASURA: "🗑️",
    INFRAESTRUCTURA: "🧱",
    RIESGO: "⚠️",
    OTRO: "📍",
};

function initMap() {
    const el = document.getElementById("mapa");
    if (!el || typeof L === "undefined") return;

    const latInput = parseFloat(document.getElementById("lat")?.value) || -7.1638;
    const lngInput = parseFloat(document.getElementById("lng")?.value) || -78.5008;

    map = L.map("mapa", { zoomControl: true, attributionControl: true })
        .setView([latInput, lngInput], 14);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap",
    }).addTo(map);

    clusterLayer = (typeof L.markerClusterGroup === "function")
        ? L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 55 })
        : L.layerGroup();
    plainLayer = L.layerGroup();

    clusterLayer.addTo(map);   // por defecto: agrupado

    setTimeout(() => map.invalidateSize(), 200);
}

function makeIcon(color, group) {
    const emoji = GROUP_ICON[group] || "📍";
    return L.divIcon({
        className: "eco-marker",
        html: `<div style="
                    width:30px;height:30px;border-radius:50% 50% 50% 0;
                    background:${color};transform:rotate(-45deg);
                    border:2px solid #fff;box-shadow:0 3px 8px rgba(15,23,42,.35);
                    display:flex;align-items:center;justify-content:center;">
                    <span style="transform:rotate(45deg);font-size:13px;">${emoji}</span>
               </div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 30],
        popupAnchor: [0, -28],
    });
}

/* Sincroniza el pin central con los inputs lat/lng */
function initCenterPinSync() {
    if (!map) return;
    const latInput = document.getElementById("lat");
    const lngInput = document.getElementById("lng");
    if (!latInput || !lngInput) return;

    map.on("moveend", () => {
        const c = map.getCenter();
        latInput.value = c.lat.toFixed(6);
        lngInput.value = c.lng.toFixed(6);
    });

    const c = map.getCenter();
    latInput.value = c.lat.toFixed(6);
    lngInput.value = c.lng.toFixed(6);
}

/* ============================================================
   CONSULTA DE DATOS
   ============================================================ */
async function loadReports() {
    try {
        const res = await fetch("/api/reports", { credentials: "same-origin" });
        if (!res.ok) throw new Error("HTTP " + res.status);
        const reports = await res.json();

        allReports.length = 0;
        allReports.push(...reports);

        renderMarkers(reports);
        renderList(reports);
        updateSummary(reports.length);
        await loadSummary();
        await loadLeaderboard();
    } catch (err) {
        console.error("Error cargando reportes:", err);
    }
}

async function loadSummary() {
    try {
        const res = await fetch("/api/summary", { credentials: "same-origin" });
        if (!res.ok) return;
        const s = await res.json();

        document.getElementById("criticalZoneName").textContent       = s.criticalZoneName || "--";
        document.getElementById("criticalZoneInfo").textContent       = s.criticalZoneInfo || "--";
        document.getElementById("criticalZoneCount").textContent      = s.criticalZoneCount ?? 0;
        document.getElementById("criticalZonePrediction").textContent = s.criticalZonePrediction || "--";
    } catch (err) {
        console.error("Error cargando summary:", err);
    }
}

async function loadHeatmap() {
    try {
        const res = await fetch("/api/heatmap", { credentials: "same-origin" });
        if (!res.ok || typeof L.heatLayer !== "function") return;
        const points = await res.json();
        const data = points.map((p) => [p.lat, p.lng, Math.min(p.weight / 4, 1)]);

        if (heatLayer) { map.removeLayer(heatLayer); }
        heatLayer = L.heatLayer(data, {
            radius: 28, blur: 22, maxZoom: 17, minOpacity: 0.35,
            gradient: { 0.2: "#22c55e", 0.5: "#f59e0b", 0.8: "#ef4444", 1.0: "#7f1d1d" },
        });
        if (heatEnabled) heatLayer.addTo(map);
    } catch (err) {
        console.error("Error cargando heatmap:", err);
    }
}

async function loadLeaderboard() {
    try {
        const res = await fetch("/api/leaderboard", { credentials: "same-origin" });
        if (!res.ok) return;
        const rows = await res.json();
        const box = document.getElementById("leaderboardList");
        if (!box) return;
        box.innerHTML = rows.length
            ? rows.map((r, i) => `
                <div class="lb-row">
                    <span class="lb-rank">${i + 1}</span>
                    <span class="fw-semibold">${escapeHtml(r.name)}</span>
                    <span class="lb-points">${r.eco_points} pts</span>
                </div>`).join("")
            : '<p class="text-muted mb-0 small">Aún no hay actividad comunitaria.</p>';
    } catch (err) {
        console.error("Error cargando ranking:", err);
    }
}

/* ============================================================
   MARCADORES (con clustering)
   ============================================================ */
function renderMarkers(reports) {
    if (!clusterLayer || !plainLayer) return;
    clusterLayer.clearLayers();
    plainLayer.clearLayers();
    markersById.clear();

    reports.forEach((r) => {
        if (typeof r.lat !== "number" || typeof r.lng !== "number") return;

        const color = SEVERITY_COLORS[r.severity] || "#0d9488";
        const marker = L.marker([r.lat, r.lng], { icon: makeIcon(color, r.group) });
        marker.bindPopup(buildPopupHtml(r));
        marker.bindTooltip(`${escapeHtml(r.title)} · ${r.upvotes || 0} 👍`, { direction: "top", offset: [0, -28] });

        clusterLayer.addLayer(marker);
        plainLayer.addLayer(marker);
        markersById.set(String(r.id), { marker, report: r });
    });
}

function buildPopupHtml(r) {
    const color = SEVERITY_COLORS[r.severity] || "#0d9488";
    const labels = { bajo: "No tan grave", intermedio: "Intermedio", critico: "Crítico" };
    const photo = r.photo_url
        ? `<img src="${encodeURI(r.photo_url)}" alt="" style="width:100%;height:110px;object-fit:cover;border-radius:8px;margin-bottom:.5rem;">`
        : "";
    return `
        <div style="min-width:200px;font-family:'Inter',sans-serif;">
            ${photo}
            <div style="font-weight:700;font-size:.95rem;color:#0f172a;margin-bottom:.25rem;">
                ${escapeHtml(r.title)}
            </div>
            <div style="display:flex;gap:.3rem;flex-wrap:wrap;margin-bottom:.4rem;">
                <span style="display:inline-flex;align-items:center;gap:.3rem;font-size:.72rem;
                            background:${color}1a;color:${color};padding:.15rem .55rem;
                            border-radius:999px;font-weight:600;">
                    <span style="width:8px;height:8px;border-radius:50%;background:${color};"></span>
                    ${labels[r.severity] || r.severity}
                </span>
                <span class="status-pill status-${r.status}">${(r.status || "PENDIENTE").replace("_", " ")}</span>
            </div>
            <div style="font-size:.8rem;color:#475569;line-height:1.5;">
                <div><b>Zona:</b> ${escapeHtml(r.zone)} · <b>Tipo:</b> ${escapeHtml(r.group || "OTRO")}</div>
                ${r.ai_label ? `<div><b>IA:</b> ${escapeHtml(r.ai_label)} (${Math.round((r.ai_confidence || 0) * 100)}%)</div>` : ""}
                <div style="margin-top:.35rem;color:#334155;">${escapeHtml(r.description || "")}</div>
            </div>
        </div>`;
}

/* ============================================================
   LISTA DE REPORTES
   ============================================================ */
function renderList(reports) {
    const list = document.getElementById("reportsList");
    if (!list) return;

    if (!reports.length) {
        list.innerHTML = `<div class="list-group-item text-muted text-center py-4">
            Aún no hay reportes. ¡Sé el primero en reportar!
        </div>`;
        return;
    }

    const badge = { bajo: "bg-success", intermedio: "bg-warning text-dark", critico: "bg-danger" };

    list.innerHTML = reports
        .slice().reverse().slice(0, 30)
        .map((r) => {
            const thumb = r.photo_url
                ? `<img src="${encodeURI(r.photo_url)}" class="report-thumb" alt="">`
                : `<div class="report-thumb d-flex align-items-center justify-content-center" style="background:#eef2ff;">${GROUP_ICON[r.group] || "📍"}</div>`;
            return `
            <div class="list-group-item report-item" data-report-id="${r.id}" style="cursor:pointer;">
                <div class="d-flex gap-2">
                    ${thumb}
                    <div class="flex-grow-1" style="min-width:0;">
                        <div class="d-flex justify-content-between align-items-start gap-2">
                            <div class="fw-semibold text-truncate">${escapeHtml(r.title)}</div>
                            <span class="badge ${badge[r.severity] || "bg-secondary"}">${escapeHtml(r.severity)}</span>
                        </div>
                        <div class="small text-muted mt-1 text-truncate">
                            <i class="bi bi-geo-alt"></i> ${escapeHtml(r.zone)} · ${escapeHtml(r.group || "OTRO")}
                        </div>
                        <div class="d-flex align-items-center gap-2 mt-2">
                            <span class="status-pill status-${r.status}">${(r.status || "PENDIENTE").replace("_", " ")}</span>
                            <button type="button" class="upvote-btn" data-upvote="${r.id}">
                                <i class="bi bi-hand-thumbs-up"></i> <span>${r.upvotes || 0}</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>`;
        }).join("");

    // Click en un item → zoom + popup
    list.querySelectorAll(".report-item").forEach((el) => {
        el.addEventListener("click", (ev) => {
            if (ev.target.closest("[data-upvote]")) return;  // el botón de voto tiene su propio handler
            focusReport(el.dataset.reportId);
        });
    });

    // Botones de voto
    list.querySelectorAll("[data-upvote]").forEach((btn) => {
        btn.addEventListener("click", async (ev) => {
            ev.stopPropagation();
            const id = btn.dataset.upvote;
            try {
                const res = await fetch(`/api/reports/${id}/upvote`, {
                    method: "POST", credentials: "same-origin",
                });
                if (!res.ok) throw new Error("No se pudo votar");
                const data = await res.json();
                const count = data.report.upvotes;
                btn.querySelector("span").textContent = count;
                const entry = markersById.get(String(id));
                if (entry) entry.report.upvotes = count;
                btn.animate([{ transform: "scale(1)" }, { transform: "scale(1.25)" }, { transform: "scale(1)" }], { duration: 250 });
            } catch (err) {
                console.error(err);
            }
        });
    });
}

function focusReport(id) {
    const entry = markersById.get(String(id));
    if (!entry || !map) return;

    const { marker, report } = entry;
    ensurePlainLayer();
    map.flyTo([report.lat, report.lng], 17, { duration: 0.9 });
    setTimeout(() => marker.openPopup(), 950);
}

/* ============================================================
   HERRAMIENTAS DEL MAPA (heatmap / clustering / geofence)
   ============================================================ */
function ensurePlainLayer() {
    if (clusterEnabled && clusterLayer.hasLayer) {
        map.removeLayer(clusterLayer);
        plainLayer.addTo(map);
        clusterEnabled = false;
    }
}

function initMapTools() {
    const heatBtn = document.getElementById("toggleHeat");
    const clusterBtn = document.getElementById("toggleCluster");
    const geoBtn = document.getElementById("toggleGeo");

    if (heatBtn) heatBtn.addEventListener("click", () => {
        heatEnabled = !heatEnabled;
        if (!heatLayer) return;
        if (heatEnabled) { heatLayer.addTo(map); heatBtn.classList.replace("btn-outline-danger", "btn-danger"); }
        else { map.removeLayer(heatLayer); heatBtn.classList.replace("btn-danger", "btn-outline-danger"); }
    });

    if (clusterBtn) clusterBtn.addEventListener("click", () => {
        clusterEnabled = !clusterEnabled;
        if (clusterEnabled) {
            map.removeLayer(plainLayer); clusterLayer.addTo(map);
            clusterBtn.classList.replace("btn-outline-primary", "btn-primary");
        } else {
            map.removeLayer(clusterLayer); plainLayer.addTo(map);
            clusterBtn.classList.replace("btn-primary", "btn-outline-primary");
        }
    });

    if (geoBtn) geoBtn.addEventListener("click", () => showMyZone(parseFloat(geoBtn.dataset.radius) || 3));
}

async function showMyZone(radiusKm) {
    if (!navigator.geolocation) { setHint("Geolocalización no disponible en este navegador"); return; }
    setHint("Obteniendo tu ubicación…");

    navigator.geolocation.getCurrentPosition(async (pos) => {
        const { latitude, longitude } = pos.coords;
        if (geoCircle) map.removeLayer(geoCircle);
        geoCircle = L.circle([latitude, longitude], {
            radius: radiusKm * 1000, color: "#059669", weight: 2,
            fillColor: "#10b981", fillOpacity: 0.12,
        }).addTo(map);
        map.flyTo([latitude, longitude], 15, { duration: 0.8 });

        try {
            const res = await fetch(`/api/reports?lat=${latitude}&lng=${longitude}&radius=${radiusKm}`, { credentials: "same-origin" });
            const nearby = await res.json();
            setHint(`📍 ${nearby.length} reporte(s) en un radio de ${radiusKm} km`);
        } catch {
            setHint(`Radio de ${radiusKm} km dibujado`);
        }
    }, (err) => {
        console.error(err);
        setHint("No se pudo obtener tu ubicación");
    }, { enableHighAccuracy: true, timeout: 10000 });
}

function setHint(text) {
    const el = document.getElementById("mapHintText");
    if (el) el.textContent = text;
}

/* ============================================================
   SEVERITY BUTTONS
   ============================================================ */
function initSeverityButtons() {
    const buttons = document.querySelectorAll(".severity-btn");
    const hidden  = document.getElementById("severity_level");
    const badge   = document.getElementById("zoneSeverityBadge");

    const labels = { bajo: "No tan grave", intermedio: "Intermedio", critico: "Crítico" };
    const badgeClass = { bajo: "bg-success", intermedio: "bg-warning text-dark", critico: "bg-danger" };

    buttons.forEach((btn) => {
        btn.addEventListener("click", () => {
            buttons.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            const sev = btn.dataset.severity;
            if (hidden) hidden.value = sev;
            if (badge) {
                badge.textContent = labels[sev] || sev;
                badge.className = "badge rounded-pill " + (badgeClass[sev] || "bg-secondary");
            }
        });
    });
}

/* ============================================================
   FORMULARIO (cámara + IA + geolocalización + envío)
   ============================================================ */
function initForm() {
    const form = document.getElementById("reportForm");
    if (!form) return;

    initPhotoCapture();
    initGeoButton();

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const msg = document.getElementById("formMessage");
        setMessage(msg, "");

        const lat = parseFloat(document.getElementById("lat").value);
        const lng = parseFloat(document.getElementById("lng").value);
        const center = map ? map.getCenter() : { lat, lng };

        const fd = new FormData();
        fd.append("title", document.getElementById("title").value);
        fd.append("description", document.getElementById("description").value);
        fd.append("zone", document.getElementById("zone").value);
        fd.append("group", document.getElementById("group").value);
        fd.append("lat", isFinite(lat) ? lat : center.lat);
        fd.append("lng", isFinite(lng) ? lng : center.lng);
        fd.append("severity_level", document.getElementById("severity_level").value);

        const photo = document.getElementById("photo").files[0];
        if (photo) fd.append("photo", photo);

        try {
            const res = await fetch("/api/reports", {
                method: "POST", credentials: "same-origin", body: fd,
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.error || "Error al enviar");

            let extra = "";
            if (data.reward && data.reward.points) extra = ` (+${data.reward.points} eco-puntos)`;
            if (data.reward && data.reward.unlocked && data.reward.unlocked.length) extra += " 🏅 ¡Insignia desbloqueada!";
            setMessage(msg, "✅ Reporte enviado correctamente." + extra, false);

            form.reset();
            resetFormUi();

            await loadReports();
            await loadHeatmap();
        } catch (err) {
            console.error(err);
            setMessage(msg, "❌ " + err.message, true);
        }
    });
}

function resetFormUi() {
    const preview = document.getElementById("photoPreview");
    if (preview) { preview.classList.remove("show"); preview.src = ""; }
    const ai = document.getElementById("aiResult");
    if (ai) ai.classList.remove("show");
    document.getElementById("severity_level").value = "critico";
    document.querySelectorAll(".severity-btn").forEach((b) => {
        b.classList.toggle("active", b.dataset.severity === "critico");
    });
    const badge = document.getElementById("zoneSeverityBadge");
    if (badge) { badge.textContent = "Sin evaluar"; badge.className = "badge rounded-pill bg-secondary"; }
}

/* Captura de imagen + clasificación automática con IA local */
function initPhotoCapture() {
    const input = document.getElementById("photo");
    const preview = document.getElementById("photoPreview");
    const aiBox = document.getElementById("aiResult");
    const aiLabel = document.getElementById("aiLabel");
    const aiConf = document.getElementById("aiConf");
    if (!input) return;

    input.addEventListener("change", async () => {
        const file = input.files[0];
        if (!file) return;

        // Vista previa local inmediata.
        preview.src = URL.createObjectURL(file);
        preview.classList.add("show");

        // Inferencia IA en el servidor (modelo local, sin APIs externas).
        aiBox.classList.add("show");
        aiLabel.textContent = "Analizando…";
        aiConf.textContent = "…";

        const fd = new FormData();
        fd.append("photo", file);
        try {
            const res = await fetch("/api/classify", { method: "POST", credentials: "same-origin", body: fd });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Error de clasificación");
            aiLabel.textContent = data.label;
            aiConf.textContent = Math.round((data.confidence || 0) * 100) + "%";
            // Si la IA es concluyente y el usuario no eligió tipo, lo sugerimos.
            const groupSelect = document.getElementById("group");
            if (groupSelect && !groupSelect.value && data.group && data.group !== "OTRO") {
                groupSelect.value = data.group;
            }
        } catch (err) {
            aiLabel.textContent = "No se pudo clasificar";
            aiConf.textContent = "--";
            console.error(err);
        }
    });
}

/* Botón "Mi GPS" → FusedLocation equivalente (Geolocation API) */
function initGeoButton() {
    const btn = document.getElementById("geoBtn");
    if (!btn) return;

    btn.addEventListener("click", () => {
        if (!navigator.geolocation) { setHint("Geolocalización no disponible"); return; }
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const lat = pos.coords.latitude.toFixed(6);
                const lng = pos.coords.longitude.toFixed(6);
                document.getElementById("lat").value = lat;
                document.getElementById("lng").value = lng;
                if (map) map.flyTo([parseFloat(lat), parseFloat(lng)], 17, { duration: 0.8 });
                setHint("Ubicación capturada correctamente");
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-crosshair"></i> Mi GPS';
            },
            (err) => {
                console.error(err);
                setHint("Permiso de ubicación denegado o no disponible");
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-crosshair"></i> Mi GPS';
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    });
}

/* ============================================================
   UTILIDADES
   ============================================================ */
function setMessage(el, text, isError = false) {
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("text-danger", isError);
    el.classList.toggle("text-success", !isError);
}

function updateSummary(total) {
    const el = document.getElementById("totalReports");
    if (el) el.textContent = total;
}

function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
