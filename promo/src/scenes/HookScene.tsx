import type {FC} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {SceneBackground} from '../components/SceneBackground';
import {BodyCopy, COLORS, Eyebrow, FONT_STACK, Headline} from '../components/Typography';

const fragments = [
  {label: 'Subscription', value: '−$15.49', x: 1180, y: 135, delay: 4},
  {label: 'Duplicate', value: '−$18.00', x: 1395, y: 385, delay: 11},
  {label: 'Delivery', value: '−$22.00', x: 1120, y: 665, delay: 18},
];

export const HookScene: FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const title = spring({frame: frame - 12, fps, config: {damping: 17, stiffness: 90}});
  const paycheckWidth = interpolate(frame, [35, 105], [0, 600], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <SceneBackground>
      <div style={{display: 'flex', height: '100%', alignItems: 'center'}}>
        <div style={{width: 1050, transform: `translateY(${(1 - title) * 70}px)`, opacity: title}}>
          <Eyebrow>Your money • your answers</Eyebrow>
          <Headline style={{fontSize: 112, marginTop: 28}}>
            Your paycheck
            <br />
            shouldn’t <span style={{color: COLORS.mint}}>disappear.</span>
          </Headline>
          <BodyCopy style={{marginTop: 34, maxWidth: 760}}>See the patterns. Verify the math. Keep control.</BodyCopy>
          <div style={{marginTop: 48, width: 680}}>
            <div style={{display: 'flex', justifyContent: 'space-between', fontFamily: FONT_STACK, color: COLORS.white, fontSize: 26}}>
              <span>PAYCHECK</span>
              <span style={{color: COLORS.mint}}>$2,400</span>
            </div>
            <div style={{height: 10, marginTop: 13, borderRadius: 12, background: 'rgba(255,255,255,.12)', overflow: 'hidden'}}>
              <div style={{height: '100%', width: paycheckWidth, borderRadius: 12, background: `linear-gradient(90deg, ${COLORS.mint}, ${COLORS.blue})`}} />
            </div>
          </div>
        </div>
        {fragments.map((item) => {
          const progress = spring({frame: frame - item.delay, fps, config: {damping: 16, stiffness: 105}});
          return (
            <div
              key={item.label}
              style={{
                position: 'absolute',
                left: item.x,
                top: item.y,
                width: 320,
                padding: '26px 28px',
                borderRadius: 26,
                background: 'rgba(15,37,77,.86)',
                border: '1px solid rgba(255,255,255,.13)',
                boxShadow: '0 25px 70px rgba(0,0,0,.28)',
                fontFamily: FONT_STACK,
                transform: `translateX(${(1 - progress) * 240}px) rotate(${(1 - progress) * 8}deg)`,
                opacity: progress,
              }}
            >
              <div style={{color: COLORS.muted, fontSize: 22, fontWeight: 650}}>{item.label}</div>
              <div style={{color: COLORS.white, fontSize: 40, fontWeight: 760, marginTop: 8}}>{item.value}</div>
            </div>
          );
        })}
      </div>
    </SceneBackground>
  );
};
