import type {FC} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PhoneFrame} from '../components/PhoneFrame';
import {SceneBackground} from '../components/SceneBackground';
import {BodyCopy, COLORS, Eyebrow, FONT_STACK, Headline} from '../components/Typography';

export const ApprovalScene: FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const phone = spring({frame: frame - 4, fps, config: {damping: 19, stiffness: 90}});
  const confirm = spring({frame: frame - 52, fps, config: {damping: 13, stiffness: 125}});
  const fade = interpolate(frame, [0, 14, 210, 240], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <SceneBackground glow="mint">
      <div style={{height: '100%', opacity: fade}}>
        <div style={{position: 'absolute', left: 170, top: 42, transform: `translateX(${(1 - phone) * -220}px)`, opacity: phone}}>
          <PhoneFrame screen="04-simulated-approval" scale={0.9} rotate={-2} glow="rgba(49,200,164,.46)" />
        </div>
        <div style={{position: 'absolute', left: 800, right: 30, top: 170}}>
          <Eyebrow>Human checkpoint</Eyebrow>
          <Headline style={{fontSize: 88, marginTop: 24}}>The final decision is always yours.</Headline>
          <div style={{display: 'flex', alignItems: 'center', gap: 20, marginTop: 52, transform: `scale(${0.82 + confirm * 0.18})`, transformOrigin: 'left center', opacity: confirm}}>
            <div style={{width: 62, height: 62, borderRadius: '50%', display: 'grid', placeItems: 'center', color: COLORS.ink, background: COLORS.mint, fontFamily: FONT_STACK, fontSize: 34, fontWeight: 900}}>✓</div>
            <div style={{color: COLORS.mint, fontFamily: FONT_STACK, fontSize: 39, fontWeight: 800}}>Local simulation confirmed</div>
          </div>
          <BodyCopy style={{marginTop: 34, maxWidth: 690}}>No merchant is contacted.<br />No real cancellation happens.</BodyCopy>
        </div>
      </div>
    </SceneBackground>
  );
};
