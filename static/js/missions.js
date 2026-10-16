/* ============================================================
   static/js/missions.js  ·  Página de misiones comunitarias
   - Unirse a una misión (POST /api/missions/<id>/join)
   - Completar una misión (POST /api/missions/<id>/complete)
   - Crear una misión (POST /api/missions)
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", async (ev) => {
        const btn = ev.target.closest("[data-action]");
        if (!btn) return;
        const id = btn.dataset.id;
        const action = btn.dataset.action;

        btn.disabled = true;
        try {
            const res = await fetch(`/api/missions/${id}/${action}`, {
                method: "POST", credentials: "same-origin",
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.error || "Operación fallida");
            // Recargamos para reflejar participantes/estado/puntos.
            window.location.reload();
        } catch (err) {
            alert(err.message);
            btn.disabled = false;
        }
    });

    const createBtn = document.getElementById("createMissionBtn");
    if (createBtn) {
        createBtn.addEventListener("click", async () => {
            const reportId = document.getElementById("missionReport").value;
            const title = document.getElementById("missionTitle").value;
            const date = document.getElementById("missionDate").value;
            const msg = document.getElementById("missionMsg");
            msg.textContent = "";

            if (!reportId) {
                msg.textContent = "Selecciona un reporte asociado.";
                msg.className = "small mt-3 text-danger";
                return;
            }

            const payload = { report_id: Number(reportId), title, date };
            createBtn.disabled = true;
            try {
                const res = await fetch("/api/missions", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    credentials: "same-origin",
                    body: JSON.stringify(payload),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(data.error || "No se pudo crear la misión");
                window.location.reload();
            } catch (err) {
                msg.textContent = err.message;
                msg.className = "small mt-3 text-danger";
                createBtn.disabled = false;
            }
        });
    }
});
