document.addEventListener("DOMContentLoaded", () => {
  // Localize existing timestamps
  formatGuestbookTimestamps();

  const gbForm = document.getElementById("guestbook-form");
  if (!gbForm) return;

  gbForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("guestbook-input");
    if (!input) return;
    const val = input.value.trim();
    if (!val) return;

    const btn = gbForm.querySelector("button[type=submit]");
    if (btn) btn.disabled = true;

    try {
      // Don't go looking for vulnerabilities, i suck at security and i escape again on server side lol
      const resp = await fetch("/api/submit-guestbook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: val }),
      });

      if (resp.status === 429) {
        const retry = (await resp.json()).retry_after || 15;
        alert(`You're sending messages too quickly. Try again in ${retry}s.`);
        return;
      }

      const data = await resp.json();
      if (data.ok) {
        const container = document.getElementById("guestbook-entries");
        const idx = (container && container.querySelectorAll("p").length) + 1 || 1;
        const p = document.createElement("p");
        p.innerHTML = `<b>Stranger:</b> ${escapeHtml(val)} <small class="gb-ts" data-ts="${data.ts}"></small>`;
        if (container) container.insertBefore(p, container.firstChild);
        input.value = "";
        formatGuestbookTimestamps();
      } else {
        alert("Failed to submit message");
      }
    } catch (err) {
      console.error(err);
      alert("Network error");
    } finally {
      if (btn) btn.disabled = false;
    }
  });
});

function escapeHtml(unsafe) {
  return unsafe
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatGuestbookTimestamps() {
  document.querySelectorAll(".gb-ts").forEach((el) => {
    const ts = Number(el.dataset.ts || 0);
    if (!ts) return;
    const d = new Date(ts * 1000);
    el.textContent = d.toLocaleString();
  });
}
