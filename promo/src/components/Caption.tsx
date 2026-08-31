import type {FC} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {COLORS, FONT_STACK} from './Typography';

const highlight = (text: string, accent?: string) => {
  if (!accent) return text;
  const index = text.toLowerCase().indexOf(accent.toLowerCase());
  if (index < 0) return text;
  return (
    <>
      {text.slice(0, index)}
      <span style={{color: COLORS.mint}}>{text.slice(index, index + accent.length)}</span>
      {text.slice(index + accent.length)}
    </>
  );
};

export const Caption: FC<{text: string; accent?: string; duration: number}> = ({text, accent, duration}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const entrance = spring({frame, fps, config: {damping: 18, stiffness: 115}});
  const opacity = interpolate(frame, [0, 10, duration - 14, duration], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div
      style={{
        position: 'absolute',
        zIndex: 50,
        left: 180,
        right: 180,
        bottom: 48,
        display: 'flex',
        justifyContent: 'center',
        opacity,
        transform: `translateY(${(1 - entrance) * 28}px)`,
      }}
    >
      <div
        style={{
          maxWidth: 1320,
          padding: '18px 32px 20px',
          borderRadius: 24,
          color: COLORS.white,
          background: 'rgba(4,13,29,.78)',
          border: '1px solid rgba(255,255,255,.14)',
          boxShadow: '0 18px 50px rgba(0,0,0,.24)',
          fontFamily: FONT_STACK,
          fontSize: 34,
          fontWeight: 650,
          letterSpacing: -0.5,
          textAlign: 'center',
        }}
      >
        {highlight(text, accent)}
      </div>
    </div>
  );
};
