// TODO: put my shit in a namespace?

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
      navigator?.vibrate?.(10);
    });

    const endInteraction = () => emoji.classList.remove("is-active");

    emoji.addEventListener("pointerup", endInteraction);
    emoji.addEventListener("pointerleave", endInteraction);
    emoji.addEventListener("pointercancel", endInteraction);
  });
});

function playSoundOneshot(src) {
  const audio = new Audio(src);
  audio.addEventListener("canplaythrough", () => {
    audio.play();
  });
  return audio;
}

// This is so we can do fun shit that uses sounds/vibrations
let interactedwiththesite = false;

document.addEventListener("pointerdown", () => {
  interactedwiththesite = true;
});

document.addEventListener("keydown", () => {
  interactedwiththesite = true;
});

// no this isn't C
// void main()

function hasInteracted() {
  return interactedwiththesite;
}
