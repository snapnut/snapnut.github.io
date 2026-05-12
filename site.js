document.write(
`<script data-goatcounter="https://snapnut.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>`
)

document.addEventListener('DOMContentLoaded', () => {
  const picmojis = document.querySelectorAll('[picmoji]');

  picmojis.forEach(emoji => {
    emoji.addEventListener('touchstart', (e) => {
      emoji.classList.add('is-active');
    });

    emoji.addEventListener('touchend', () => {
      emoji.classList.remove('is-active');
    });

    emoji.addEventListener('touchcancel', () => {
      emoji.classList.remove('is-active');
    });
  });
});
