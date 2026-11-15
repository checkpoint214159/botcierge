// Staff queues (A08, A09): ← / → open the previous / next item, unless the user is typing.
document.addEventListener("keydown", (e) => {
  if (e.target.closest("input, textarea, select, [contenteditable]")) return;
  const link = document.getElementById(e.key === "ArrowLeft" ? "prev" : e.key === "ArrowRight" ? "next" : "");
  if (link) location.href = link.href;
});
