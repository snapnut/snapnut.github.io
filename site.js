document.write(
  `<script data-goatcounter="https://snapnut.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>`,
);

document.addEventListener("DOMContentLoaded", () => {
  const picmojis = document.querySelectorAll("[picmoji]");

  document.addEventListener("touchstart", (e) => {
    picmojis.forEach((emoji) => {
      emoji.classList.remove("is-active");
    });
  });

  // NOTE: touchstart and touchend happen on TAP! this means that touchend is called before the transition finishes, dimwit!
  picmojis.forEach((emoji) => {
    emoji.addEventListener("touchstart", (e) => {
      emoji.classList.add("is-active");
      // This is slow :(
      if (emoji.style.transitionDelay !== "0s")
        emoji.style.transitionDelay = "0s"; // This breaks when we switch between Desktop and Mobile in DevTools. But 'Desktop Mode' on mobile browsers reload the page!!
    });

    emoji.addEventListener("touchend", () => {
      emoji.classList.remove("is-active");
      navigator.vibrate(10);
    });

    emoji.addEventListener("touchcancel", () => {
      emoji.classList.remove("is-active");
    });
  });
});
