import type {FC} from 'react';
import {Img, staticFile} from 'remotion';
import {COLORS} from './Typography';

export const PhoneFrame: FC<{
  screen: string;
  scale?: number;
  rotate?: number;
  glow?: string;
}> = ({screen, scale = 1, rotate = 0, glow = 'rgba(36,111,242,.46)'}) => (
  <div
    style={{
      position: 'relative',
      width: 430,
      height: 932,
      borderRadius: 72,
      padding: 14,
      background: 'linear-gradient(145deg, #dce6f5, #63718b 42%, #eaf1fb)',
      boxShadow: `0 42px 100px ${glow}, inset 0 0 0 2px rgba(255,255,255,.55)`,
      transform: `scale(${scale}) rotate(${rotate}deg)`,
      transformOrigin: 'center',
    }}
  >
    <div
      style={{
        position: 'absolute',
        inset: 14,
        overflow: 'hidden',
        borderRadius: 59,
        backgroundColor: COLORS.white,
      }}
    >
      <Img src={staticFile(`screens/${screen}.png`)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: 18,
          width: 122,
          height: 35,
          borderRadius: 22,
          transform: 'translateX(-50%)',
          backgroundColor: '#020205',
        }}
      />
    </div>
    <div
      style={{
        position: 'absolute',
        left: -5,
        top: 210,
        width: 6,
        height: 112,
        borderRadius: 4,
        backgroundColor: '#718097',
      }}
    />
  </div>
);
