<script setup lang="ts">
/**
 * 粒子庆祝画布 —— 多样化 + 分级升级。
 *
 * 四种粒子形状：星光 / 光点圆 / 细彩带 / 微尘
 * 材质增强：发光光晕、彗尾拖尾、金色粒子、涟漪波
 * 强度 1-5 控制粒子数量与效果丰富度
 * 象限色板决定颜色倾向
 */
import { ref, watch, onUnmounted } from 'vue'

const props = defineProps<{
  active: boolean
  originX?: number
  originY?: number
  intensity?: number    // 1-5
  quadrant?: string     // 'Q1'|'Q2'|'Q3'|'Q4'
}>()

const canvasRef = ref<HTMLCanvasElement>()
let animFrame = 0

/* ================================================================
   色板
   ================================================================ */

// 象限色板 —— 每个象限 6 色
const QUADRANT_PALETTES: Record<string, string[]> = {
  Q1: ['#F87171', '#FB923C', '#FBBF24', '#FCA5A5', '#FDBA74', '#FDE68A'],  // 暖色：珊瑚/朱红/金橙
  Q2: ['#60A5FA', '#A78BFA', '#6EE7B7', '#818CF8', '#93C5FD', '#C4B5FD'],  // 冷色：天蓝/薰紫/薄荷
  Q3: ['#F59E0B', '#FB923C', '#FCD34D', '#FCA5A5', '#FDBA74', '#FDE68A'],  // 亮暖：琥珀/柑橘/杏黄
  Q4: ['#34D399', '#6EE7B7', '#A7F3D0', '#9CA3AF', '#86EFAC', '#D1FAE5'],  // 冷绿：翠绿/鼠尾草/青灰
}

// 通用粉彩色板（无象限信息时使用）
const DEFAULT_PALETTE = [
  '#F9A8D4', '#A7F3D0', '#BFDBFE', '#FDE68A',
  '#DDD6FE', '#FECACA', '#BAE6FD', '#FED7AA',
  '#C4B5FD', '#6EE7B7',
]

const GOLD_COLOR = '#F7CB4D'

function palette(): string[] {
  if (props.quadrant && QUADRANT_PALETTES[props.quadrant]) {
    return QUADRANT_PALETTES[props.quadrant]
  }
  return DEFAULT_PALETTE
}

function randomColor(): string {
  const p = palette()
  return p[Math.floor(Math.random() * p.length)]
}

/* ================================================================
   粒子类型
   ================================================================ */

type ParticleKind = 'sparkle' | 'glow' | 'strip' | 'dust' | 'comet' | 'gold'

interface Particle {
  kind: ParticleKind
  x: number; y: number
  vx: number; vy: number
  size: number
  color: string
  life: number; maxLife: number
  rotation: number; rotationSpeed: number
  driftAmpX: number; driftAmpY: number
  driftFreqX: number; driftFreqY: number
  driftPhaseX: number; driftPhaseY: number
  // 彗尾专用
  trail?: Array<{ x: number; y: number; alpha: number }>
}

/* ================================================================
   涟漪
   ================================================================ */

interface Ripple {
  x: number; y: number
  radius: number; maxRadius: number
  alpha: number
}

let ripples: Ripple[] = []

/* ================================================================
   绘制函数
   ================================================================ */

function drawSparkle(ctx: CanvasRenderingContext2D, x: number, y: number, size: number, rot: number): void {
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(rot)
  ctx.beginPath()
  for (let i = 0; i < 4; i++) {
    const a = (i * Math.PI) / 2
    const ox = Math.cos(a) * size
    const oy = Math.sin(a) * size
    const ix = Math.cos(a + Math.PI / 4) * size * 0.3
    const iy = Math.sin(a + Math.PI / 4) * size * 0.3
    if (i === 0) ctx.moveTo(ox, oy)
    else ctx.lineTo(ox, oy)
    ctx.lineTo(ix, iy)
  }
  ctx.closePath()
  ctx.fill()
  ctx.restore()
}

function drawGlow(ctx: CanvasRenderingContext2D, x: number, y: number, size: number): void {
  ctx.beginPath()
  ctx.arc(x, y, size, 0, Math.PI * 2)
  ctx.fill()
}

function drawStrip(ctx: CanvasRenderingContext2D, x: number, y: number, size: number, rot: number): void {
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(rot)
  ctx.fillRect(-size * 0.25, -size * 1.2, size * 0.5, size * 2.4)
  ctx.restore()
}

function drawDust(ctx: CanvasRenderingContext2D, x: number, y: number, size: number): void {
  ctx.beginPath()
  ctx.arc(x, y, size, 0, Math.PI * 2)
  ctx.fill()
}

/* ================================================================
   主循环
   ================================================================ */

interface IntensityConfig {
  particleCount: number
  cometCount: number
  goldCount: number
  rippleCount: number
  secondaryBurst: boolean
  secondaryDelay: number
  secondaryCount: number
}

function getIntensityConfig(level: number): IntensityConfig {
  const map: Record<number, IntensityConfig> = {
    1: { particleCount: 25, cometCount: 2, goldCount: 0, rippleCount: 1, secondaryBurst: false, secondaryDelay: 0, secondaryCount: 0 },
    2: { particleCount: 35, cometCount: 3, goldCount: 2, rippleCount: 1, secondaryBurst: false, secondaryDelay: 0, secondaryCount: 0 },
    3: { particleCount: 50, cometCount: 4, goldCount: 5, rippleCount: 2, secondaryBurst: true, secondaryDelay: 300, secondaryCount: 15 },
    4: { particleCount: 65, cometCount: 5, goldCount: 8, rippleCount: 2, secondaryBurst: true, secondaryDelay: 250, secondaryCount: 20 },
    5: { particleCount: 80, cometCount: 6, goldCount: 12, rippleCount: 3, secondaryBurst: true, secondaryDelay: 200, secondaryCount: 30 },
  }
  return map[Math.max(1, Math.min(5, level))] ?? map[1]
}

function spawnParticles(
  ox: number, oy: number, count: number,
  kindOverride: ParticleKind | null, colorOverride: string | null,
): Particle[] {
  const result: Particle[] = []
  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2
    const speed = 2 + Math.random() * 7
    const upwardBias = -0.4
    const vx = Math.cos(angle) * speed
    const vy = Math.sin(angle) * speed + upwardBias * speed

    // 形状分配：星光 40% / 光点 30% / 彩带 20% / 微尘 10%
    let kind: ParticleKind
    if (kindOverride) {
      kind = kindOverride
    } else {
      const r = Math.random()
      if (r < 0.4) kind = 'sparkle'
      else if (r < 0.7) kind = 'glow'
      else if (r < 0.9) kind = 'strip'
      else kind = 'dust'
    }

    const color = colorOverride ?? randomColor()
    const sizeByKind: Record<ParticleKind, number> = {
      sparkle: 3 + Math.random() * 6,
      glow: 4 + Math.random() * 5,
      strip: 2 + Math.random() * 4,
      dust: 1 + Math.random() * 2,
      comet: 5 + Math.random() * 4,
      gold: 5 + Math.random() * 6,
    }

    result.push({
      kind,
      x: ox + (Math.random() - 0.5) * 40,
      y: oy + (Math.random() - 0.5) * 20,
      vx, vy,
      size: sizeByKind[kind],
      color,
      life: 0,
      maxLife: 45 + Math.random() * 75,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: (Math.random() - 0.5) * (kind === 'strip' ? 0.5 : 0.2),
      driftAmpX: 0.2 + Math.random() * 1.0,
      driftAmpY: 0.2 + Math.random() * 0.7,
      driftFreqX: 0.03 + Math.random() * 0.09,
      driftFreqY: 0.03 + Math.random() * 0.08,
      driftPhaseX: Math.random() * Math.PI * 2,
      driftPhaseY: Math.random() * Math.PI * 2,
    })
  }
  return result
}

let particles: Particle[] = []

function start() {
  if (!canvasRef.value) return
  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  canvas.width = window.innerWidth
  canvas.height = window.innerHeight

  const ox = props.originX ?? canvas.width / 2
  const oy = props.originY ?? canvas.height * 0.35
  const level = props.intensity ?? 1
  const cfg = getIntensityConfig(level)

  // 主粒子群
  const pals = palette()
  particles = spawnParticles(ox, oy, cfg.particleCount, null, null)

  // 金色粒子
  if (cfg.goldCount > 0) {
    const golds = spawnParticles(ox, oy, cfg.goldCount, 'gold', GOLD_COLOR)
    for (const g of golds) { g.size *= 1.3; g.maxLife = Math.floor(g.maxLife * 1.3) }
    particles.push(...golds)
  }

  // 彗尾粒子
  if (cfg.cometCount > 0) {
    const comets = spawnParticles(ox, oy, cfg.cometCount, 'comet', null)
    for (const c of comets) {
      c.trail = []
      c.vx *= 1.2; c.vy *= 1.2
      c.maxLife = Math.floor(c.maxLife * 1.4)
    }
    particles.push(...comets)
  }

  // 涟漪
  ripples = []
  for (let i = 0; i < cfg.rippleCount; i++) {
    ripples.push({
      x: ox, y: oy,
      radius: 0,
      maxRadius: 120 + i * 40,
      alpha: 0.35 - i * 0.1,
    })
  }

  // 二次爆发定时器
  let secondBurstTimer: ReturnType<typeof setTimeout> | null = null
  if (cfg.secondaryBurst) {
    secondBurstTimer = setTimeout(() => {
      const extra = spawnParticles(ox, oy, cfg.secondaryCount, null, null)
      // 二次爆发的粒子更小、更散
      for (const p of extra) {
        p.size *= 0.7
        p.vx *= 1.5; p.vy *= 1.5
        p.maxLife = Math.floor(p.maxLife * 0.7)
      }
      particles.push(...extra)
    }, cfg.secondaryDelay)
  }

  let frame = 0

  function draw() {
    if (!ctx || !canvas) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    frame++

    // —— 涟漪 ——
    for (const r of ripples) {
      r.radius += 1.5
      if (r.radius >= r.maxRadius) continue
      const progress = r.radius / r.maxRadius
      const alpha = r.alpha * (1 - progress)
      ctx.beginPath()
      ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2)
      ctx.strokeStyle = `rgba(180,180,200,${alpha.toFixed(3)})`
      ctx.lineWidth = 1.5 * (1 - progress)
      ctx.stroke()
    }

    // —— 粒子 ——
    let alive = false
    for (const p of particles) {
      p.life++
      if (p.life >= p.maxLife) continue
      alive = true

      // 物理
      p.x += p.vx
      p.y += p.vy
      p.vy += p.kind === 'glow' ? 0.02 : 0.06
      p.vx *= p.kind === 'dust' ? 0.98 : 0.995
      p.vy *= p.kind === 'dust' ? 0.98 : 0.995

      // 有机漂移
      p.x += Math.sin(frame * p.driftFreqX + p.driftPhaseX) * p.driftAmpX
      p.y += Math.cos(frame * p.driftFreqY + p.driftPhaseY) * p.driftAmpY

      p.rotation += p.rotationSpeed

      const progress = p.life / p.maxLife
      const alpha = progress < 0.08
        ? progress / 0.08
        : 1 - (progress - 0.08) / 0.92

      // 彗尾记录
      if (p.trail) {
        p.trail.push({ x: p.x, y: p.y, alpha })
        if (p.trail.length > 6) p.trail.shift()
      }

      // 光晕
      const glowAmount = p.kind === 'gold' ? 2.5 : p.kind === 'glow' ? 2.0 : 1.5
      ctx.shadowColor = p.color
      ctx.shadowBlur = p.size * glowAmount
      ctx.globalAlpha = alpha
      ctx.fillStyle = p.color

      // 绘制彗尾
      if (p.trail && p.trail.length > 1) {
        for (let t = 0; t < p.trail.length - 1; t++) {
          const tr = p.trail[t]
          const trailAlpha = tr.alpha * (t / p.trail.length) * 0.4
          ctx.globalAlpha = trailAlpha
          ctx.shadowBlur = p.size * 0.8
          ctx.fillStyle = p.color
          ctx.beginPath()
          ctx.arc(tr.x, tr.y, p.size * 0.35, 0, Math.PI * 2)
          ctx.fill()
        }
        ctx.globalAlpha = alpha
        ctx.shadowBlur = p.size * glowAmount
      }

      // 绘制粒子本体
      switch (p.kind) {
        case 'sparkle':
        case 'comet':
        case 'gold':
          drawSparkle(ctx, p.x, p.y, p.size * (1 - progress * 0.4), p.rotation)
          break
        case 'glow':
          drawGlow(ctx, p.x, p.y, p.size * (1 - progress * 0.3))
          break
        case 'strip':
          drawStrip(ctx, p.x, p.y, p.size * (1 - progress * 0.2), p.rotation)
          break
        case 'dust':
          drawDust(ctx, p.x, p.y, p.size * (1 - progress * 0.5))
          break
      }
    }

    // 清理
    ctx.shadowColor = 'transparent'
    ctx.shadowBlur = 0
    ctx.globalAlpha = 1

    if (alive || ripples.some(r => r.radius < r.maxRadius)) {
      animFrame = requestAnimationFrame(draw)
    } else {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      if (secondBurstTimer) clearTimeout(secondBurstTimer)
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
