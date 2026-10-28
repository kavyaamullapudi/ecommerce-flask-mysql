document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach((flash) => {
    window.setTimeout(() => {
      flash.classList.add("flash-hide");
      window.setTimeout(() => flash.remove(), 350);
    }, 5000);
  });

  document.querySelectorAll('input[type="number"]').forEach((input) => {
    input.addEventListener("change", () => {
      const min = Number(input.min || 1);
      const max = Number(input.max || 99);
      let value = Number(input.value || min);
      if (!Number.isFinite(value)) value = min;
      input.value = String(Math.min(max, Math.max(min, Math.floor(value))));
    });
  });
});
