import type {FC, ReactNode} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {COLORS} from './Typography';

const PARTICLES = Array.from({length: 18}, (_, index) => ({
  x: (index * 173 + 81) % 1920,
  y: (index * 97 + 43) % 1080,
  size: 4 + (index % 4) * 3,
  speed: 0.18 + (index % 5) * 0.05,
}));

export const SceneBackground: FC<{children: ReactNode; glow?: 'blue' | 'mint'}> = ({
  children,
  glow = 'blue',
}) => {
  const frame = useCurrentFrame();
  const drift = interpolate(frame % 360, [0, 359], [0, 80]);
  const glowColor = glow === 'mint' ? 'rgba(49,200,164,0.24)' : 'rgba(36,111,242,0.34)';
  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.navy,
        backgroundImage: `radial-gradient(circle at 78% 28%, ${glowColor}, transparent 42%), linear-gradient(135deg, #06142c 0%, #081d42 58%, #06142c 100%)`,
        overflow: 'hidden',
      }}
    >
      <AbsoluteFill
        style={{
          opacity: 0.13,
          backgroundImage:
            'linear-gradient(rgba(255,255,255,.12) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.12) 1px, transparent 1px)',
          backgroundSize: '72px 72px',
          transform: `translateY(${drift - 80}px)`,
        }}
      />
      {PARTICLES.map((particle, index) => (
        <div
          key={index}
          style={{
            position: 'absolute',
            left: particle.x,
            top: (particle.y + frame * particle.speed) % 1180 - 50,
            width: particle.size,
            height: particle.size,
            borderRadius: '50%',
            background: index % 3 === 0 ? COLORS.mint : COLORS.cyan,
            boxShadow: `0 0 ${particle.size * 3}px currentColor`,
            opacity: 0.22,
          }}
        />
      ))}
      <div style={{position: 'absolute', inset: 0, padding: '86px 120px 112px'}}>{children}</div>
    </AbsoluteFill>
  );
};
