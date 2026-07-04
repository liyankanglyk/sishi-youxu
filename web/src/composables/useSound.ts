/**
 * 音效合成 —— 分级升级版。
 *
 * playCompleteChime(intensity):
 *   1-2 → 基础三音上行 C5→E5→G5
 *   3-4 → 加入高八度泛音 C6→E6
 *   5   → 全和弦：C4 低音 + C5→E5→G5 + C6 高音
 *
 * playMilestoneChime():
 *   里程碑专用（第 10/25/50 项），更丰富的琶音
 */

let audioCtx: AudioContext | null = null

function ctx(): AudioContext {
  if (!audioCtx) audioCtx = new AudioContext()
  if (audioCtx.state === 'suspended') audioCtx.resume()
  return audioCtx
}

/** 创建一个音 —— oscillator + gain 包装 */
function tone(
  c: AudioContext,
  freq: number,
  startTime: number,
  duration: number,
  volume: number,
  type: OscillatorType = 'triangle',
): void {
  const osc = c.createOscillator()
  const gain = c.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(freq, startTime)
  gain.gain.setValueAtTime(0, startTime)
  gain.gain.linearRampToValueAtTime(volume, startTime + 0.012)
  gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration)
  osc.connect(gain)
  gain.connect(c.destination)
  osc.start(startTime)
  osc.stop(startTime + duration + 0.05)
}

/** 任务完成音效 —— 根据强度分级 */
export function playCompleteChime(intensity: number = 1): void {
  try {
    const c = ctx()
    const now = c.currentTime

    const master = c.createGain()
    master.gain.setValueAtTime(0.16, now)
    master.gain.exponentialRampToValueAtTime(0.001, now + 0.5)
    master.connect(c.destination)

    // 基础三音：C5 → E5 → G5
    const base = [
      { freq: 523.25, delay: 0, dur: 0.18, vol: 0.25 },
      { freq: 659.25, delay: 0.05, dur: 0.18, vol: 0.25 },
      { freq: 783.99, delay: 0.10, dur: 0.18, vol: 0.25 },
    ]

    for (const n of base) {
      tone(c, n.freq, now + n.delay, n.dur, n.vol, 'triangle')
    }

    // 强度 3+：高八度泛音
    if (intensity >= 3) {
      const hi = [
        { freq: 1046.5, delay: 0.04, dur: 0.15, vol: 0.10 },
        { freq: 1318.5, delay: 0.09, dur: 0.15, vol: 0.08 },
      ]
      for (const n of hi) {
        tone(c, n.freq, now + n.delay, n.dur, n.vol, 'sine')
      }
    }

    // 强度 5：低音衬底
    if (intensity >= 5) {
      tone(c, 261.63, now, 0.35, 0.10, 'triangle') // C4
      tone(c, 1568.0, now + 0.14, 0.15, 0.06, 'sine') // C6 高音
    }
  } catch { /* 静默降级 */ }
}

/** 里程碑音效 —— 琶音上行 + 低音共鸣 */
export function playMilestoneChime(): void {
  try {
    const c = ctx()
    const now = c.currentTime

    const master = c.createGain()
    master.gain.setValueAtTime(0.2, now)
    master.gain.exponentialRampToValueAtTime(0.001, now + 0.8)
    master.connect(c.destination)

    // C 大调琶音：C4 → E4 → G4 → C5 → E5 → G5 → C6
    const arp = [261.63, 329.63, 392.0, 523.25, 659.25, 783.99, 1046.5]

    for (let i = 0; i < arp.length; i++) {
      const delay = i * 0.06
      const dur = 0.25
      const vol = i === arp.length - 1 ? 0.18 : 0.09
      tone(c, arp[i], now + delay, dur, vol, i >= 4 ? 'sine' : 'triangle')
    }

    // 低音共鸣
    tone(c, 130.81, now, 0.6, 0.08, 'triangle')  // C3
  } catch { /* 静默降级 */ }
}

/** 删除 / 撤销音效 —— 低沉短促 */
export function playDeleteChime(): void {
  try {
    const c = ctx()
    const now = c.currentTime

    const master = c.createGain()
    master.gain.setValueAtTime(0.10, now)
    master.gain.exponentialRampToValueAtTime(0.001, now + 0.18)
    master.connect(c.destination)

    tone(c, 330, now, 0.14, 0.2, 'sine')
    const osc2 = c.createOscillator()
    const g2 = c.createGain()
    osc2.type = 'sine'
    osc2.frequency.setValueAtTime(330, now)
    osc2.frequency.exponentialRampToValueAtTime(180, now + 0.1)
    g2.gain.setValueAtTime(0.15, now)
    g2.gain.exponentialRampToValueAtTime(0.001, now + 0.12)
    osc2.connect(g2)
    g2.connect(master)
    osc2.start(now)
    osc2.stop(now + 0.15)
  } catch { /* 静默降级 */ }
}
