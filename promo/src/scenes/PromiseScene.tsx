import type {FC} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {BrandMark} from '../components/BrandMark';
import {PhoneFrame} from '../components/PhoneFrame';
import {SceneBackground} from '../components/SceneBackground';
import {BodyCopy, COLORS, Eyebrow, FONT_STACK, Headline} from '../components/Typography';

export const PromiseScene: FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const copy = spring({frame: frame - 10, fps, config: {damping: 18, stiffness: 90}});
  const phone = spring({frame: frame - 28, fps, config: {damping: 19, stiffness: 92}});
  const fade = interpolate(frame, [0, 16, 188, 210], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <SceneBackground glow="mint">
      <div style={{display: 'flex', height: '100%', alignItems: 'center', opacity: fade}}>
        <div style={{width: 900, transform: `translateX(${(1 - copy) * -70}px)`, opacity: copy}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 24}}>
            <BrandMark size={86} />
            <div style={{fontFamily: FONT_STACK, color: COLORS.white, fontSize: 34, fontWeight: 780}}>Paycheck Guardian</div>
          </div>
          <Eyebrow style={{marginTop: 58}}>Local • synthetic demo</Eyebrow>
          <Headline style={{fontSize: 88, marginTop: 22}}>Evidence first. Action stays with you.</Headline>
          <BodyCopy style={{marginTop: 30, maxWidth: 720}}>No bank connection. No data leaves the device. No real cancellation.</BodyCopy>
        </div>
        <div style={{position: 'absolute', right: 205, top: 50, transform: `translateX(${(1 - phone) * 260}px) rotate(${(1 - phone) * 8}deg)`, opacity: phone}}>
          <PhoneFrame screen="01-welcome" scale={0.88} rotate={-2} glow="rgba(49,200,164,.42)" />
        </div>
      </div>
    </SceneBackground>
  );
};
