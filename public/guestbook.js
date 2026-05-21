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
    // client-side length enforcement
    const MAX = 100;
    if (val.length > MAX) {
      alert(`Message too long (max ${MAX} characters)`);
      return;
    }

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
        const fmsg = document.getElementById("guestbook-no-messages");
        if (fmsg) fmsg.remove();
        
        const container = document.getElementById("guestbook-entries");
        const display = (data.saved !== undefined) ? data.saved : val;
        const p = document.createElement("p");
        const mid = data.id || '';
        if (mid) p.id = `msg-${mid}`;
        const idHtml = mid ? `<span class="gb-id">${mid}</span>: ` : '';
        p.innerHTML = `${idHtml}${escapeHtml(display)} <small class="gb-ts" data-ts="${data.ts}"></small>`;
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
  const now = Math.floor(Date.now() / 1000);
  document.querySelectorAll(".gb-ts").forEach((el) => {
    const ts = Number(el.dataset.ts || 0);
    if (!ts) return;
    // Hide messages more than 100 seconds in the future
    if (ts > now + 100) {
      const p = el.closest('p');
      if (p) p.remove();
      return;
    }
    const d = new Date(ts * 1000);
    el.textContent = d.toLocaleString();
  });
}

// Live character counter
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById('guestbook-input');
  const counter = document.getElementById('gb-counter');
  const MAX = 100;
  if (!input || !counter) return;
  const update = () => {
    const val = input.value || '';
    counter.textContent = `${val.length}/${MAX}`;
    if (val.length > MAX) counter.style.color = 'salmon';
    else counter.style.color = '';
  };
  input.addEventListener('input', update);
  update();
});

// IDs are generated and stored on the server; client only displays server-provided ids.
