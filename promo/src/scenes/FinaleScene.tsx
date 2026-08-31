import type {FC} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {BrandMark} from '../components/BrandMark';
import {SceneBackground} from '../components/SceneBackground';
import {COLORS, FONT_STACK} from '../components/Typography';
import {DISCLOSURE} from '../content';

export const FinaleScene: FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const mark = spring({frame, fps, config: {damping: 16, stiffness: 95}});
  const line = interpolate(frame, [18, 58], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <SceneBackground glow="mint">
      <div style={{height: '100%', display: 'grid', placeItems: 'center', textAlign: 'center'}}>
        <div style={{transform: `scale(${0.76 + mark * 0.24})`, opacity: mark}}>
          <BrandMark size={116} />
          <div style={{fontFamily: FONT_STACK, color: COLORS.white, fontSize: 64, fontWeight: 820, letterSpacing: -2, marginTop: 22}}>Paycheck Guardian</div>
          <div style={{display: 'flex', justifyContent: 'center', gap: 22, marginTop: 34, opacity: line, transform: `translateY(${(1 - line) * 22}px)`, fontFamily: FONT_STACK, fontSize: 40, fontWeight: 760}}>
            <span style={{color: COLORS.white}}>Verified.</span>
            <span style={{color: COLORS.mint}}>Explainable.</span>
            <span style={{color: COLORS.white}}>In your control.</span>
          </div>
          <div style={{marginTop: 54, color: COLORS.muted, fontFamily: FONT_STACK, fontSize: 23, letterSpacing: 0.4}}>{DISCLOSURE}</div>
        </div>
      </div>
    </SceneBackground>
  );
};
