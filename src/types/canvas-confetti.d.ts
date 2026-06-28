declare module 'canvas-confetti' {
  interface ConfettiOptions {
    particleCount?: number
    angle?: number
    spread?: number
    origin?: { x?: number; y?: number }
    colors?: string[]
    startVelocity?: number
    gravity?: number
    ticks?: number
    shapes?: ('circle' | 'square')[]
    scalar?: number
    zIndex?: number
    disableForReducedMotion?: boolean
  }

  function confetti(options?: ConfettiOptions): Promise<null> | null
  export = confetti
}
