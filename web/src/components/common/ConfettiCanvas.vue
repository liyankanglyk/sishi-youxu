<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'

const props = defineProps<{ active: boolean }>()

const canvasRef = ref<HTMLCanvasElement>()
let animFrame = 0
let particles: Array<{
  x: number; y: number; vx: number; vy: number; size: number; color: string; life: number; maxLife: number; rotation: number; rotationSpeed: number
}> = []

const COLORS = ['#6366F1', '#EC4899', '#F59E0B', '#10B981', '#3B82F6', '#EF4444', '#8B5CF6', '#14B8A6']

function start() {
  if (!canvasRef.value) return
  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  canvas.width = window.innerWidth
  canvas.height = window.innerHeight

  particles = []
  const count = 80
  for (let i = 0; i < count; i++) {
    particles.push({
      x: canvas.width / 2 + (Math.random() - 0.5) * 200,
      y: canvas.height * 0.4,
      vx: (Math.random() - 0.5) * 12,
      vy: -Math.random() * 10 - 5,
      size: Math.random() * 8 + 4,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
      life: 0,
      maxLife: 60 + Math.random() * 60,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: (Math.random() - 0.5) * 0.3,
    })
  }

  function draw() {
    if (!ctx || !canvas) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    let alive = false
    for (const p of particles) {
      p.life++
      if (p.life >= p.maxLife) continue
      alive = true

      p.x += p.vx
      p.y += p.vy
      p.vy += 0.15
      p.vx *= 0.99
      p.rotation += p.rotationSpeed

      const alpha = 1 - p.life / p.maxLife
      ctx.save()
      ctx.translate(p.x, p.y)
      ctx.rotate(p.rotation)
      ctx.globalAlpha = alpha
      ctx.fillStyle = p.color
      ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6)
      ctx.restore()
    }

    if (alive) {
      animFrame = requestAnimationFrame(draw)
    } else {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
  }

  animFrame = requestAnimationFrame(draw)
}

watch(() => props.active, (v) => {
  if (v) start()
})

onUnmounted(() => cancelAnimationFrame(animFrame))
</script>

<template>
  <canvas ref="canvasRef" class="confetti-canvas" />
</template>

<style scoped>
.confetti-canvas {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 999;
}
</style>
