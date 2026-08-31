import type {FC} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PhoneFrame} from '../components/PhoneFrame';
import {SceneBackground} from '../components/SceneBackground';
import {COLORS, Eyebrow, FONT_STACK, Headline} from '../components/Typography';
import {METRICS} from '../content';

const rows = [
  {label: 'Monthly estimate', value: METRICS.evidenceMonthly},
  {label: 'Before next paycheck', value: METRICS.evidencePaycheck},
  {label: 'Source evidence', value: '3 transactions'},
];

export const EvidenceScene: FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const phone = spring({frame: frame - 8, fps, config: {damping: 20, stiffness: 88}});
  const fade = interpolate(frame, [0, 16, 270, 300], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <SceneBackground glow="mint">
      <div style={{height: '100%', opacity: fade}}>
        <div style={{position: 'absolute', left: 135, top: 12, transform: `translateX(${(1 - phone) * -220}px)`, opacity: phone}}>
          <PhoneFrame screen="03-evidence" scale={0.9} rotate={-2} glow="rgba(49,200,164,.38)" />
        </div>
        <div style={{position: 'absolute', left: 760, right: 30, top: 70}}>
          <Eyebrow>Show your work</Eyebrow>
          <Headline style={{fontSize: 82, marginTop: 22}}>Every estimate comes with receipts.</Headline>
          <div style={{marginTop: 54, borderRadius: 32, overflow: 'hidden', border: '1px solid rgba(255,255,255,.14)', background: 'rgba(10,31,68,.78)'}}>
            {rows.map((row, index) => {
              const progress = spring({frame: frame - 38 - index * 14, fps, config: {damping: 17, stiffness: 105}});
              return (
                <div key={row.label} style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '27px 32px', borderBottom: index < rows.length - 1 ? '1px solid rgba(255,255,255,.1)' : undefined, opacity: progress, transform: `translateX(${(1 - progress) * 45}px)`, fontFamily: FONT_STACK}}>
                  <span style={{color: COLORS.muted, fontSize: 27}}>{row.label}</span>
                  <span style={{color: index < 2 ? COLORS.white : COLORS.mint, fontSize: 35, fontWeight: 760}}>{row.value}</span>
                </div>
              );
            })}
          </div>
          <div style={{color: COLORS.muted, fontFamily: FONT_STACK, fontSize: 25, lineHeight: 1.45, marginTop: 28}}>Monthly estimate × days to paycheck × 12 ÷ 365<br />rounded to cents.</div>
        </div>
      </div>
    </SceneBackground>
  );
};
