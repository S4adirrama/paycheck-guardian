import type {FC} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {SceneBackground} from '../components/SceneBackground';
import {COLORS, Eyebrow, FONT_STACK, Headline} from '../components/Typography';

const signals = [
  {icon: '↻', title: 'Recurring', detail: 'Patterns can look alike', color: '#5ba7ff'},
  {icon: '≋', title: 'Duplicate', detail: 'Two charges, one question', color: '#31c8a4'},
  {icon: '↗', title: 'Discretionary', detail: 'Small choices add up', color: '#9b7cff'},
];

export const ProblemScene: FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const fade = interpolate(frame, [0, 16, 188, 210], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <SceneBackground glow="mint">
      <div style={{opacity: fade}}>
        <Eyebrow>Patterns hide in plain sight</Eyebrow>
        <Headline style={{fontSize: 82, width: 1180, marginTop: 24}}>Finding a charge is easy. Knowing what’s safe to act on isn’t.</Headline>
        <div style={{display: 'flex', gap: 34, marginTop: 84}}>
          {signals.map((signal, index) => {
            const progress = spring({frame: frame - 25 - index * 12, fps, config: {damping: 16, stiffness: 95}});
            return (
              <div
                key={signal.title}
                style={{
                  flex: 1,
                  height: 285,
                  padding: 38,
                  borderRadius: 34,
                  background: 'linear-gradient(150deg, rgba(23,52,102,.9), rgba(10,27,59,.92))',
                  border: '1px solid rgba(255,255,255,.14)',
                  boxShadow: '0 35px 85px rgba(0,0,0,.24)',
                  transform: `translateY(${(1 - progress) * 75}px) scale(${0.92 + progress * 0.08})`,
                  opacity: progress,
                  fontFamily: FONT_STACK,
                }}
              >
                <div style={{width: 66, height: 66, borderRadius: 22, display: 'grid', placeItems: 'center', background: `${signal.color}25`, color: signal.color, fontSize: 42, fontWeight: 800}}>{signal.icon}</div>
                <div style={{color: COLORS.white, fontSize: 42, fontWeight: 760, marginTop: 30}}>{signal.title}</div>
                <div style={{color: COLORS.muted, fontSize: 26, lineHeight: 1.35, marginTop: 14}}>{signal.detail}</div>
              </div>
            );
          })}
        </div>
      </div>
    </SceneBackground>
  );
};
