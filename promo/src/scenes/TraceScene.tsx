import type {FC} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PhoneFrame} from '../components/PhoneFrame';
import {SceneBackground} from '../components/SceneBackground';
import {COLORS, Eyebrow, FONT_STACK, Headline} from '../components/Typography';

const steps = [
  {label: 'Tool Called', color: '#5ba7ff'},
  {label: 'Tool Result', color: '#5ba7ff'},
  {label: 'Verified', color: '#31c8a4'},
];

export const TraceScene: FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const phone = spring({frame: frame - 5, fps, config: {damping: 18, stiffness: 92}});
  const fade = interpolate(frame, [0, 12, 156, 180], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <SceneBackground>
      <div style={{height: '100%', opacity: fade}}>
        <div style={{position: 'absolute', left: 90, top: 125, width: 900}}>
          <Eyebrow>Transparent orchestration</Eyebrow>
          <Headline style={{fontSize: 82, marginTop: 24}}>See how the agent decided.</Headline>
          <div style={{display: 'flex', alignItems: 'center', gap: 16, marginTop: 58}}>
            {steps.map((step, index) => {
              const progress = spring({frame: frame - 28 - index * 13, fps, config: {damping: 15, stiffness: 110}});
              return (
                <div key={step.label} style={{display: 'flex', alignItems: 'center', gap: 16, opacity: progress, transform: `translateX(${(1 - progress) * 30}px)`}}>
                  <div style={{padding: '18px 22px', borderRadius: 18, color: step.color, border: `1px solid ${step.color}66`, background: `${step.color}16`, fontFamily: FONT_STACK, fontSize: 25, fontWeight: 760}}>{step.label}</div>
                  {index < steps.length - 1 ? <div style={{color: COLORS.muted, fontSize: 28}}>→</div> : null}
                </div>
              );
            })}
          </div>
          <div style={{marginTop: 34, color: COLORS.muted, fontFamily: FONT_STACK, fontSize: 27, lineHeight: 1.45}}>Opaque IDs. Redacted payloads.<br />No merchant names in the trace.</div>
        </div>
        <div style={{position: 'absolute', right: 210, top: 42, transform: `translateX(${(1 - phone) * 220}px)`, opacity: phone}}>
          <PhoneFrame screen="05-agent-trace" scale={0.9} rotate={2} />
        </div>
      </div>
    </SceneBackground>
  );
};
