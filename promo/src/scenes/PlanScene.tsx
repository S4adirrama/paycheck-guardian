import type {FC} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PhoneFrame} from '../components/PhoneFrame';
import {SceneBackground} from '../components/SceneBackground';
import {BodyCopy, COLORS, Eyebrow, FONT_STACK, Headline} from '../components/Typography';
import {METRICS} from '../content';

export const PlanScene: FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const phone = spring({frame: frame - 4, fps, config: {damping: 19, stiffness: 92}});
  const metric = spring({frame: frame - 42, fps, config: {damping: 15, stiffness: 110}});
  const fade = interpolate(frame, [0, 18, 300, 330], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <SceneBackground>
      <div style={{display: 'flex', height: '100%', alignItems: 'center', opacity: fade}}>
        <div style={{width: 900}}>
          <Eyebrow>Verified plan</Eyebrow>
          <Headline style={{fontSize: 88, marginTop: 22}}>What could stay in your account before payday?</Headline>
          <div style={{display: 'flex', alignItems: 'baseline', gap: 22, marginTop: 48, transform: `scale(${0.88 + metric * 0.12})`, transformOrigin: 'left center', opacity: metric}}>
            <div style={{fontFamily: FONT_STACK, color: COLORS.white, fontSize: 150, lineHeight: 1, fontWeight: 800, letterSpacing: -8}}>{METRICS.beforePaycheck}</div>
            <div style={{fontFamily: FONT_STACK, color: COLORS.mint, fontSize: 28, fontWeight: 760}}>BEFORE NEXT PAYCHECK</div>
          </div>
          <BodyCopy style={{marginTop: 24}}>{METRICS.monthly} estimated monthly • not guaranteed</BodyCopy>
          <div style={{display: 'inline-flex', marginTop: 42, padding: '17px 24px', borderRadius: 18, border: '1px solid rgba(49,200,164,.4)', background: 'rgba(49,200,164,.12)', color: COLORS.mint, fontFamily: FONT_STACK, fontSize: 24, fontWeight: 760}}>✓ Independently verifier-accepted</div>
        </div>
        <div style={{position: 'absolute', right: 205, top: 42, transform: `translateX(${(1 - phone) * 230}px)`, opacity: phone}}>
          <PhoneFrame screen="02-verified-plan" scale={0.9} rotate={2} />
        </div>
      </div>
    </SceneBackground>
  );
};
