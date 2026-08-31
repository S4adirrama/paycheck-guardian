import type {FC} from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {Caption} from './components/Caption';
import {CAPTIONS} from './content';
import {ApprovalScene} from './scenes/ApprovalScene';
import {EvidenceScene} from './scenes/EvidenceScene';
import {FinaleScene} from './scenes/FinaleScene';
import {HookScene} from './scenes/HookScene';
import {PlanScene} from './scenes/PlanScene';
import {ProblemScene} from './scenes/ProblemScene';
import {PromiseScene} from './scenes/PromiseScene';
import {TraceScene} from './scenes/TraceScene';
import {FPS, scene} from './timing';

const visualScenes = [
  {timing: scene('hook'), component: HookScene},
  {timing: scene('problem'), component: ProblemScene},
  {timing: scene('promise'), component: PromiseScene},
  {timing: scene('plan'), component: PlanScene},
  {timing: scene('evidence'), component: EvidenceScene},
  {timing: scene('approval'), component: ApprovalScene},
  {timing: scene('trace'), component: TraceScene},
  {timing: scene('finale'), component: FinaleScene},
] as const;

export const Promo: FC = () => (
  <AbsoluteFill>
    {visualScenes.map(({timing, component: Scene}) => (
      <Sequence key={timing.key} from={timing.from} durationInFrames={timing.duration} premountFor={FPS}>
        <Scene />
      </Sequence>
    ))}
    {CAPTIONS.map((caption) => (
      <Sequence key={`${caption.from}-${caption.text}`} from={caption.from} durationInFrames={caption.duration}>
        <Caption text={caption.text} accent={caption.accent} duration={caption.duration} />
      </Sequence>
    ))}
  </AbsoluteFill>
);
