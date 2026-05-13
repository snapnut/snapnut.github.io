let tod = Math.random() * 24;

{
  const todColors = [
    { time: 0, color: [8, 8, 8] },
    { time: 5, color: [38, 38, 38] },
    { time: 5.5, color: [28, 74, 100] },
    { time: 6.5, color: [54, 133, 179] },
    { time: 12, color: [52, 159, 167] },
    { time: 15, color: [52, 159, 167] },
    { time: 17, color: [180, 180, 190] },
    { time: 18.5, color: [38, 38, 38] },
    { time: 23.9, color: [13, 13, 13] },
  ];
  let canvas, ctx;
  let width, height, count;
  let posX, posY, vel, lengths, rotation, opacities;
  let loopingTheRooms = false;

  let lastTime = 0;
  let timer = 0;

  function gettod_bgcolor() {
    const time = tod % 24;
    const palette = todColors;

    let nextIndex = palette.findIndex((p) => p.time > time);

    if (nextIndex === 0) return `rgb(${palette[0].color.join(",")})`;
    if (nextIndex === -1)
      return `rgb(${palette[palette.length - 1].color.join(",")})`;

    const prev = palette[nextIndex - 1];
    const next = palette[nextIndex];

    // the laerp is real
    const range = next.time - prev.time;
    const progress = (time - prev.time) / range;

    const r = Math.round(
      prev.color[0] + (next.color[0] - prev.color[0]) * progress,
    );
    const g = Math.round(
      prev.color[1] + (next.color[1] - prev.color[1]) * progress,
    );
    const b = Math.round(
      prev.color[2] + (next.color[2] - prev.color[2]) * progress,
    );

    return `rgb(${r}, ${g}, ${b})`;
  }

  function setup() {
    canvas = document.getElementById("rainCanvas");
    if (!canvas) return; // Safety first
    ctx = canvas.getContext("2d");

    handleResize();
    if (!loopingTheRooms) {
      loopingTheRooms = true;
      loop();
    }
  }

  function handleResize() {
    const dpr = window.devicePixelRatio || 1;

    width = window.innerWidth;
    height = window.innerHeight;

    canvas.width = width * dpr;
    canvas.height = height * dpr;

    ctx.scale(dpr, dpr);

    count = Math.floor((width * height) / 8000);

    posX = new Float32Array(count);
    posY = new Float32Array(count);
    vel = new Float32Array(count);
    lengths = new Float32Array(count);
    rotation = new Float32Array(count);
    opacities = new Float32Array(count);

    for (let i = 0; i < count; i++) {
      resetDrop(i, true);
    }
  }

  function resetDrop(i, randomY = false) {
    posX[i] = Math.random() * width;
    posY[i] = randomY ? Math.random() * height : -20;
    vel[i] = Math.random() * 12 + 8;
    lengths[i] = Math.random() * 20 + 20;
    rotation[i] = Math.random() * 2 - 1;
    opacities[i] = Math.random() * 0.4 + 0.1;
  }

  function loop(currentTime = performance.now()) {
    const td = gettod_bgcolor();

    if (!lastTime) lastTime = currentTime;
    const deltaTime = (currentTime - lastTime) / 1000;
    lastTime = currentTime;

    if (tod > 0 && tod < 6) tod += deltaTime * 0.5;
    else tod += deltaTime;

    if (tod > 24) tod = 0;

    ctx.fillStyle = td;
    ctx.fillRect(0, 0, width, height);
    ctx.lineWidth = 1;
    ctx.lineCap = "round";

    for (let i = 0; i < count; i++) {
      posY[i] += vel[i];

      ctx.beginPath();
      ctx.strokeStyle = `rgba(174, 194, 224, ${opacities[i]})`;
      ctx.moveTo(posX[i] - rotation[i], posY[i]);
      ctx.lineTo(posX[i] + rotation[i], posY[i] + lengths[i]);
      ctx.stroke();

      if (posY[i] > height) {
        resetDrop(i);
      }
    }
    requestAnimationFrame(loop);
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", setup);
  else setup();

  window.addEventListener("resize", handleResize);
}
