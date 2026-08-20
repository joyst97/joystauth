// Ultra-Fluid Cyber Crimson & Neon Ruby Engine (60FPS Infinite Wrap-Around)
(function () {
    const canvas = document.getElementById("bg-particles");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    let mouse = {
        x: width / 2,
        y: height / 2,
        targetX: width / 2,
        targetY: height / 2
    };

    window.addEventListener("resize", () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    });

    window.addEventListener("mousemove", (e) => {
        mouse.targetX = e.clientX;
        mouse.targetY = e.clientY + window.scrollY;
    });

    // 1. Cyber Crimson Plasma Blobs
    class CrimsonBlob {
        constructor(x, y, radius, color, vx, vy) {
            this.x = x;
            this.y = y;
            this.baseRadius = radius;
            this.radius = radius;
            this.color = color;
            this.vx = vx;
            this.vy = vy;
            this.angle = Math.random() * Math.PI * 2;
        }

        update() {
            this.x += this.vx;
            this.y += this.vy;

            // Continuous infinite toroidal wrap-around
            if (this.x < -this.radius) this.x = width + this.radius;
            if (this.x > width + this.radius) this.x = -this.radius;
            if (this.y < -this.radius) this.y = height + this.radius;
            if (this.y > height + this.radius) this.y = -this.radius;

            this.angle += 0.012;
            this.radius = this.baseRadius + Math.sin(this.angle) * 35;
        }

        draw() {
            const grad = ctx.createRadialGradient(
                this.x, this.y, 0,
                this.x, this.y, this.radius
            );
            grad.addColorStop(0, this.color.replace('ALPHA', '0.24'));
            grad.addColorStop(0.45, this.color.replace('ALPHA', '0.08'));
            grad.addColorStop(1, 'transparent');

            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    // 2. Infinite Continuous Floating Sparks (Zero Sinking)
    class CrimsonSpark {
        constructor() {
            this.init(true);
        }

        init(randomY = false) {
            this.x = Math.random() * width;
            this.y = randomY ? Math.random() * height : height + 10;
            this.size = Math.random() * 2.2 + 0.8;
            // Float consistently upwards with slight horizontal drift
            this.vy = -(Math.random() * 0.8 + 0.4);
            this.vx = (Math.random() - 0.5) * 0.5;
            this.alpha = Math.random() * 0.8 + 0.3;
            // Red / Ruby / Coral hues
            this.hue = Math.random() > 0.4 ? 350 : (Math.random() > 0.5 ? 335 : 15);
        }

        update() {
            this.y += this.vy;
            this.x += this.vx;

            // Mouse proximity interaction
            const currentMouseY = mouse.targetY - window.scrollY;
            const dx = mouse.x - this.x;
            const dy = currentMouseY - this.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 140) {
                const angle = Math.atan2(dy, dx);
                this.x -= Math.cos(angle) * 2;
                this.y -= Math.sin(angle) * 2;
            }

            // Wrap continuously when reaching top or sides
            if (this.y < -15) {
                this.init(false);
            }
            if (this.x < -10) this.x = width + 10;
            if (this.x > width + 10) this.x = -10;
        }

        draw() {
            ctx.fillStyle = `hsla(${this.hue}, 95%, 60%, ${this.alpha})`;
            ctx.shadowBlur = 12;
            ctx.shadowColor = `hsla(${this.hue}, 95%, 60%, 0.85)`;
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowBlur = 0;
        }
    }

    const blobs = [
        new CrimsonBlob(width * 0.15, height * 0.25, 440, "rgba(225, 29, 72, ALPHA)", 0.22, 0.12),
        new CrimsonBlob(width * 0.85, height * 0.35, 480, "rgba(244, 63, 94, ALPHA)", -0.18, 0.2),
        new CrimsonBlob(width * 0.5, height * 0.7, 500, "rgba(255, 42, 95, ALPHA)", 0.15, -0.16),
        new CrimsonBlob(width * 0.2, height * 0.9, 420, "rgba(159, 18, 57, ALPHA)", -0.12, -0.14)
    ];

    const sparks = [];
    const sparkCount = Math.min(Math.floor(width / 16), 90);
    for (let i = 0; i < sparkCount; i++) {
        sparks.push(new CrimsonSpark());
    }

    function animate() {
        ctx.clearRect(0, 0, width, height);

        // Smooth mouse spring
        mouse.x += (mouse.targetX - mouse.x) * 0.08;
        mouse.y += (mouse.targetY - mouse.y) * 0.08;

        // Interactive cursor aura in Cyber Crimson
        const currentMouseY = mouse.targetY - window.scrollY;
        const cursorGrad = ctx.createRadialGradient(
            mouse.x, currentMouseY, 0,
            mouse.x, currentMouseY, 340
        );
        cursorGrad.addColorStop(0, "rgba(225, 29, 72, 0.18)");
        cursorGrad.addColorStop(0.5, "rgba(244, 63, 94, 0.05)");
        cursorGrad.addColorStop(1, "transparent");
        ctx.fillStyle = cursorGrad;
        ctx.beginPath();
        ctx.arc(mouse.x, currentMouseY, 340, 0, Math.PI * 2);
        ctx.fill();

        // Render blobs
        blobs.forEach(b => {
            b.update();
            b.draw();
        });

        // Render continuous floating sparks
        sparks.forEach(s => {
            s.update();
            s.draw();
        });

        requestAnimationFrame(animate);
    }

    animate();
})();
