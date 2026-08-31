import type {FC} from 'react';
import {AbsoluteFill, Composition} from 'remotion';
import {FPS, HEIGHT, TOTAL_FRAMES, WIDTH} from './timing';

const PlaceholderPromo: FC = () => <AbsoluteFill style={{backgroundColor: '#07162e'}} />;

export const RemotionRoot: FC = () => (
  <Composition
    id="PaycheckGuardianPromo"
    component={PlaceholderPromo}
    durationInFrames={TOTAL_FRAMES}
    fps={FPS}
    width={WIDTH}
    height={HEIGHT}
  />
);
