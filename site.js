document.write(
  `<script data-goatcounter="https://snapnut.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>`,
);

document.addEventListener("DOMContentLoaded", () => {
  const picmojis = document.querySelectorAll("[picmoji]");

  document.addEventListener("pointerdown", (e) => {
    picmojis.forEach((emoji) => {
      emoji.classList.remove("is-active");
    });
  });

  picmojis.forEach((emoji) => {
    emoji.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return; 
      
      emoji.classList.add("is-active");
      if (navigator.vibrate) navigator.vibrate(10);
    });

    const endInteraction = () => emoji.classList.remove("is-active");

    emoji.addEventListener("pointerup", endInteraction);
    emoji.addEventListener("pointerleave", endInteraction);
    emoji.addEventListener("pointercancel", endInteraction);
  });
});
