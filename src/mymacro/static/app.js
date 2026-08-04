window.MyMacro = {
  escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  },
  todayISO() {
    return new Date().toISOString().slice(0, 10);
  },
  caloriesFromMacros(proteinG, carbsG, fatG) {
    return Math.round((proteinG * 4 + carbsG * 4 + fatG * 9) * 100) / 100;
  },
  mountNav(active) {
    const host = document.getElementById("nav");
    if (!host) return;
    const items = [
      ["/", "Scan", "scan"],
      ["/logs", "Daily logs", "logs"],
      ["/micros", "Micronutrients", "micros"],
      ["/settings", "Settings", "settings"],
      ["/barcode", "Barcode", "barcode"],
    ];
    const links = items
      .map(([href, label, key]) => {
        const cls = key === active ? "active" : "";
        return `<a class="${cls}" href="${href}">${label}</a>`;
      })
      .join("");
    host.innerHTML = `
      <div class="topbar">
        <a class="brand" href="/">mymacro</a>
        <nav class="tabs" aria-label="Primary">${links}</nav>
      </div>`;
  },
};
