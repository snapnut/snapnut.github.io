const canvas = document.getElementById('rainCanvas');
const ctx = canvas.getContext('2d');

let width, height, count;
let posX, posY, vel, lengths, opacities;

function setup() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;

    count = Math.floor((width * height) / 8000);

    // Structure of Arrays (SoA)
    posX = new Float32Array(count);
    posY = new Float32Array(count);
    vel = new Float32Array(count);
    lengths = new Float32Array(count);
    opacities = new Float32Array(count);

    for (let i = 0; i < count; i++) {
        resetDrop(i, true);
    }
}

function resetDrop(i, randomY = false) {
    posX[i] = Math.random() * width;
    posY[i] = randomY ? Math.random() * height : -20;
    vel[i] = Math.random() * 12 + 8; // Speed
    lengths[i] = Math.random() * 20 + 10; // "Two-point" length
    opacities[i] = Math.random() * 0.4 + 0.1;
}

function loop() {
    ctx.clearRect(0, 0, width, height);
    ctx.lineWidth = 1;
    ctx.lineCap = 'round';

    for (let i = 0; i < count; i++) {
        posY[i] += vel[i];

        ctx.beginPath();
        ctx.strokeStyle = `rgba(174, 194, 224, ${opacities[i]})`;
        ctx.moveTo(posX[i], posY[i]);
        ctx.lineTo(posX[i], posY[i] + lengths[i]);
        ctx.stroke();

        if (posY[i] > height) {
            resetDrop(i);
        }
    }
    requestAnimationFrame(loop);
}

window.addEventListener('resize', setup);

setup();
loop();